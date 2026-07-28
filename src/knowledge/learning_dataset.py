"""
LearningDatasetBuilder — Phase 7 WP9410 学習データ統合

failure_repository.json / summary.log / wbs_history.log / os_update_report.json
から学習エントリを抽出し、因果分解構造に再構造化して learning_dataset.json を生成する。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

BASE_DIR       = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG    = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
FAILURE_REPO   = BASE_DIR / "docs" / "phase6" / "failure_repository.json"
CYCLE_INDEX    = BASE_DIR / "docs" / "knowledge_cycle" / "index.yaml"
WBS_HISTORY    = BASE_DIR / "docs" / "wbs_history.log"
OS_REPORT      = BASE_DIR / "docs" / "system" / "os_update_report.json"
DATASET_PATH   = BASE_DIR / "docs" / "knowledge_cycle" / "learning_dataset.json"

# 学習カテゴリ定数
CAT_OPERATIONAL  = "operational"   # 運用パターン（Phase 5 WP9100〜9130）
CAT_IMPROVEMENT  = "improvement"   # 改善パターン（Phase 6 WP9210〜9230）
CAT_MAINTENANCE  = "maintenance"   # 基盤維持パターン（Phase 6.5 WP9300〜9320）
CAT_ENVIRONMENT  = "environment"   # 環境変化パターン（OS・パッケージ）

# 再現性ラベル
REPRO_HIGH   = "high"
REPRO_MEDIUM = "medium"
REPRO_LOW    = "low"


def _new_entry_id(prefix: str, n: int) -> str:
    return f"{prefix}-{n:03d}"


class LearningDatasetBuilder:
    """
    Phase 5〜6.5 の蓄積知識を学習エントリとして統合する。

    使い方:
        builder = LearningDatasetBuilder()
        entries = builder.build_from_failure_repository()
        entries += builder.extract_success_patterns_from_log()
        entries += builder.build_from_wbs_history()
        entries += builder.build_from_os_report()
        dataset = builder.compile_dataset(entries)
        builder.save_dataset(dataset)
        builder.write_summary_entry(dataset)
    """

    def __init__(
        self,
        failure_repo_path: Path | None = None,
        summary_log_path:  Path | None = None,
        wbs_history_path:  Path | None = None,
        os_report_path:    Path | None = None,
        dataset_path:      Path | None = None,
        cycle_index_path:  Path | None = None,
    ) -> None:
        self._failure_repo  = failure_repo_path or FAILURE_REPO
        self._summary_log   = summary_log_path  or SUMMARY_LOG
        self._wbs_history   = wbs_history_path  or WBS_HISTORY
        self._os_report     = os_report_path    or OS_REPORT
        self._dataset_path  = dataset_path      or DATASET_PATH
        self._cycle_index   = cycle_index_path  or CYCLE_INDEX

    # ── 失敗知識 → 因果分解エントリ ────────────────────────────

    def build_from_failure_repository(
        self,
        path: Path | None = None,
    ) -> list[dict]:
        """
        failure_repository.json の失敗事例を因果分解構造（原因→対策→結果）に変換する。

        各事例:
          cause  : condition（発生条件）
          action : resolution（対処方法）
          result : 改善後状態（HITL 移譲 / 停止 / 再入力）
        """
        p    = path or self._failure_repo
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as f:
            data = json.load(f)

        entries: list[dict] = []
        for i, failure in enumerate(data.get("failures", []), start=1):
            pattern_type = (
                "failure_resolved"
                if failure.get("category") in ("hitl", "mece_uncertainty", "trace_chain")
                else "failure_stopped"
            )
            entries.append({
                "entry_id":      _new_entry_id("LE-IMP", i),
                "category":      CAT_IMPROVEMENT,
                "source":        failure.get("failure_id", ""),
                "module":        failure.get("module", ""),
                "failure_category": failure.get("category", ""),
                "description":   failure.get("description", ""),
                "cause":         failure.get("condition", ""),
                "action":        failure.get("resolution", ""),
                "result":        _classify_result(failure.get("resolution", "")),
                "pattern_type":  pattern_type,
                "reproducibility": REPRO_HIGH,
            })
        return entries

    # ── summary.log → 成功パターン抽出 ──────────────────────────

    def extract_success_patterns_from_log(
        self,
        path: Path | None = None,
    ) -> list[dict]:
        """
        summary.log の [PASS] 行から再現性の高い成功パターンを抽出する。
        """
        p = path or self._summary_log
        if not p.exists():
            return []
        text   = p.read_text(encoding="utf-8")
        passes = re.findall(r"\[PASS\] (.+)", text)

        entries: list[dict] = []
        for i, desc in enumerate(passes, start=1):
            entries.append({
                "entry_id":       _new_entry_id("LE-OPR", i),
                "category":       CAT_OPERATIONAL,
                "source":         "summary.log",
                "cause":          "定常運用条件（テスト全件 PASS 環境）",
                "action":         desc.strip(),
                "result":         "PASS（再現性確認済み）",
                "pattern_type":   "success",
                "reproducibility": REPRO_HIGH,
            })
        return entries

    # ── wbs_history.log → 構造変化パターン ─────────────────────

    def build_from_wbs_history(
        self,
        path: Path | None = None,
    ) -> list[dict]:
        """
        wbs_history.log の WBS 差分記録を構造変化パターンとして変換する。
        """
        p = path or self._wbs_history
        if not p.exists():
            return []
        text = p.read_text(encoding="utf-8")

        entries: list[dict] = []
        blocks  = [b.strip() for b in text.split("---") if b.strip()]
        for i, block in enumerate(blocks, start=1):
            added   = re.search(r"追加フェーズ: (.+)", block)
            removed = re.search(r"削除フェーズ: (.+)", block)
            changed = re.search(r"変更フェーズ: (.+)", block)
            total   = re.search(r"変更総件数\s*: (\d+)", block)
            note    = re.search(r"備考: (.+)", block)
            ts      = re.search(r"\[(.+?)\]", block)

            added_val   = added.group(1).strip()   if added   else "なし"
            removed_val = removed.group(1).strip() if removed else "なし"
            changed_val = changed.group(1).strip() if changed else "なし"
            total_val   = int(total.group(1))      if total   else 0
            note_val    = note.group(1).strip()    if note    else ""

            change_type = "addition"
            if removed_val not in ("なし", "[]"):
                change_type = "removal"
            elif changed_val not in ("なし", "[]"):
                change_type = "modification"

            entries.append({
                "entry_id":    _new_entry_id("LE-MNT", i),
                "category":    CAT_MAINTENANCE,
                "source":      "wbs_history.log",
                "timestamp":   ts.group(1) if ts else "",
                "cause":       f"WBS 構造更新要求（{note_val or '詳細なし'}）",
                "action":      f"追加={added_val} / 削除={removed_val} / 変更={changed_val}",
                "result":      f"変更総件数={total_val}件 — wbs_history.log に記録済み",
                "change_type": change_type,
                "total_changes": total_val,
                "pattern_type": "maintenance",
                "reproducibility": REPRO_MEDIUM,
            })
        return entries

    # ── os_update_report.json → 環境変化パターン ────────────────

    def build_from_os_report(
        self,
        path: Path | None = None,
    ) -> list[dict]:
        """
        os_update_report.json のパッケージ情報を環境変化パターンとして変換する。
        """
        p = path or self._os_report
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as f:
            data = json.load(f)

        env     = data.get("environment", {})
        pkgs    = data.get("packages", [])
        score   = data.get("safety_score", 100)
        summary = data.get("summary", "")

        entries: list[dict] = []
        for i, pkg in enumerate(pkgs, start=1):
            entries.append({
                "entry_id":    _new_entry_id("LE-ENV", i),
                "category":    CAT_ENVIRONMENT,
                "source":      "os_update_report.json",
                "cause":       f"パッケージ確認: {pkg['name']} installed={pkg['installed']} required>={pkg['required_min']}",
                "action":      f"update_type={pkg['update_type']} / status={pkg['status']}",
                "result":      f"status={pkg['status']} — {summary}",
                "pattern_type": "environment_check",
                "reproducibility": REPRO_MEDIUM,
            })

        entries.append({
            "entry_id":    _new_entry_id("LE-ENV", len(pkgs) + 1),
            "category":    CAT_ENVIRONMENT,
            "source":      "os_update_report.json",
            "cause":       f"OS環境確認: Python {env.get('python_version','')} / {env.get('platform','')} {env.get('architecture','')}",
            "action":      f"安全性スコア算出: {score}/100",
            "result":      f"hitl_required={data.get('hitl_required', False)} — {summary}",
            "pattern_type": "environment_assessment",
            "reproducibility": REPRO_HIGH,
        })
        return entries

    # ── データセット統合 ─────────────────────────────────────────

    def compile_dataset(
        self,
        entries: list[dict],
    ) -> dict:
        """
        全学習エントリを統合し、カテゴリ別に集約したデータセットを返す。
        """
        by_category: dict[str, list[dict]] = {
            CAT_OPERATIONAL:  [],
            CAT_IMPROVEMENT:  [],
            CAT_MAINTENANCE:  [],
            CAT_ENVIRONMENT:  [],
        }
        success_patterns: list[dict] = []
        failure_patterns: list[dict] = []

        for entry in entries:
            cat = entry.get("category", "")
            if cat in by_category:
                by_category[cat].append(entry)
            pt = entry.get("pattern_type", "")
            if pt == "success":
                success_patterns.append(entry)
            elif pt in ("failure_resolved", "failure_stopped"):
                failure_patterns.append(entry)

        return {
            "generated_at":      datetime.now().isoformat(),
            "version":           "1.0.0",
            "phase":             7,
            "total_entries":     len(entries),
            "category_counts": {
                CAT_OPERATIONAL: len(by_category[CAT_OPERATIONAL]),
                CAT_IMPROVEMENT: len(by_category[CAT_IMPROVEMENT]),
                CAT_MAINTENANCE: len(by_category[CAT_MAINTENANCE]),
                CAT_ENVIRONMENT: len(by_category[CAT_ENVIRONMENT]),
            },
            "learning_entries":  entries,
            "categories":        by_category,
            "success_patterns":  success_patterns,
            "failure_patterns":  failure_patterns,
            "phase8_ready":      False,
        }

    # ── 保存 ─────────────────────────────────────────────────────

    def save_dataset(
        self,
        dataset:  dict,
        path:     Path | None = None,
    ) -> None:
        """docs/knowledge_cycle/learning_dataset.json に保存する。"""
        p = path or self._dataset_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

    # ── summary.log 追記 ─────────────────────────────────────────

    def write_summary_entry(
        self,
        dataset:  dict,
        log_path: Path | None = None,
    ) -> None:
        """WP9410 完了エントリを summary.log に追記する。"""
        path = log_path or self._summary_log
        ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cc   = dataset.get("category_counts", {})

        entry = (
            f"\n[{ts}] WP9410 学習データ統合完了\n"
            f"  学習エントリ総数  : {dataset.get('total_entries', 0)}件\n"
            f"  運用パターン      : {cc.get(CAT_OPERATIONAL, 0)}件\n"
            f"  改善パターン      : {cc.get(CAT_IMPROVEMENT, 0)}件\n"
            f"  基盤維持パターン  : {cc.get(CAT_MAINTENANCE, 0)}件\n"
            f"  環境変化パターン  : {cc.get(CAT_ENVIRONMENT, 0)}件\n"
            f"  成功パターン数    : {len(dataset.get('success_patterns', []))}件\n"
            f"  失敗パターン数    : {len(dataset.get('failure_patterns', []))}件\n"
            f"  出力ファイル      : docs/knowledge_cycle/learning_dataset.json\n"
            f"  Phase 7 フラグ    : READY（WP9420/9430 実行可）\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── knowledge_cycle 連携用 I/O ───────────────────────────────

    def load_dataset(
        self,
        path: Path | None = None,
    ) -> dict:
        """保存済みの learning_dataset.json を読み込む。"""
        p = path or self._dataset_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def get_learning_targets(
        self,
        category: str | None = None,
        dataset:  dict | None = None,
    ) -> list[dict]:
        """
        学習対象エントリを返す。category が指定された場合はそのカテゴリのみ。
        dataset が None の場合は load_dataset() で読み込む。
        """
        ds = dataset or self.load_dataset()
        if not ds:
            return []
        if category:
            return ds.get("categories", {}).get(category, [])
        return ds.get("learning_entries", [])


# ── ヘルパ ─────────────────────────────────────────────────────

def _classify_result(resolution: str) -> str:
    """resolution 文字列から改善後状態ラベルを生成する。"""
    if "HITL" in resolution or "移譲" in resolution:
        return "HITL 移譲 → ユーザー承認待ち"
    if "RuntimeError" in resolution or "停止" in resolution or "伝播" in resolution:
        return "パイプライン即時停止 → エラー上位伝播"
    if "再入力" in resolution or "見直し" in resolution:
        return "ユーザーへフィードバック → 入力修正後に再実行"
    return "処理継続"
