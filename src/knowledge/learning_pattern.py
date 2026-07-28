"""
LearningPatternBuilder — Phase 7 WP9420 学習パターン生成

learning_dataset.json を解析し、因果分解・MECE構造・改善スコアを適用した
学習パターン（learning_patterns.json）を生成する。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR       = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG    = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
DATASET_PATH   = BASE_DIR / "docs" / "knowledge_cycle" / "learning_dataset.json"
FAILURE_REPO   = BASE_DIR / "docs" / "phase6" / "failure_repository.json"
PATTERNS_PATH  = BASE_DIR / "docs" / "knowledge_cycle" / "learning_patterns.json"

# パターン ID プレフィックス（カテゴリ別）
_PREFIX = {
    "operational":  "OP",
    "improvement":  "IM",
    "maintenance":  "MN",
    "environment":  "EN",
}

# 再現性スコア
_REPRO_SCORE = {"high": 1.0, "medium": 0.7, "low": 0.4}

# パターンタイプ別スコアオフセット
_TYPE_OFFSET = {
    "success":            0.0,
    "failure_resolved":   0.05,
    "failure_stopped":   -0.05,
    "maintenance":        0.0,
    "environment_check":  0.0,
    "environment_assessment": 0.05,
}


def _base_score(entry: dict) -> float:
    """再現性とパターンタイプから基本スコアを算出する。"""
    repro  = _REPRO_SCORE.get(entry.get("reproducibility", "medium"), 0.7)
    offset = _TYPE_OFFSET.get(entry.get("pattern_type", ""), 0.0)
    return round(min(1.0, max(0.0, repro + offset)), 2)


def _dedup_key(entry: dict) -> str:
    """重複判定キー（cause + action の正規化文字列）。"""
    cause  = re.sub(r"\s+", " ", entry.get("cause",  "")).strip()
    action = re.sub(r"\s+", " ", entry.get("action", "")).strip()
    return f"{cause}||{action}"


class LearningPatternBuilder:
    """
    learning_dataset.json から学習パターンを生成する。

    使い方:
        builder  = LearningPatternBuilder()
        dataset  = builder.load_dataset()
        patterns = builder.build_learning_patterns(dataset)
        mece_log = builder.validate_mece_structure(patterns)
        result   = builder.export_patterns(patterns, mece_log)
        builder.save_patterns(result)
        builder.write_summary_entry(result)
    """

    def __init__(
        self,
        dataset_path:   Path | None = None,
        failure_repo:   Path | None = None,
        patterns_path:  Path | None = None,
        summary_log:    Path | None = None,
    ) -> None:
        self._dataset_path  = dataset_path  or DATASET_PATH
        self._failure_repo  = failure_repo  or FAILURE_REPO
        self._patterns_path = patterns_path or PATTERNS_PATH
        self._summary_log   = summary_log   or SUMMARY_LOG

    # ── データ読み込み ────────────────────────────────────────

    def load_dataset(self, path: Path | None = None) -> dict:
        """learning_dataset.json を読み込む。"""
        p = path or self._dataset_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def load_failure_repository(self, path: Path | None = None) -> dict:
        """failure_repository.json を読み込む。"""
        p = path or self._failure_repo
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ── 学習パターン生成 ─────────────────────────────────────

    def build_learning_patterns(self, dataset: dict) -> list[dict]:
        """
        dataset の各カテゴリエントリを因果分解構造に展開し、
        重複除去・スコア付与を行った学習パターンリストを返す。

        Args:
            dataset: load_dataset() の戻り値

        Returns:
            list[dict] — 学習パターンのリスト（pattern_id 付き）
        """
        categories = dataset.get("categories", {})
        failure_repo = self.load_failure_repository()
        improvement_scores = self._build_improvement_score_map(failure_repo)

        patterns: list[dict] = []
        seen_keys: set[str] = set()

        for cat, entries in categories.items():
            prefix = _PREFIX.get(cat, "XX")
            cat_counter = 1
            for entry in entries:
                key = _dedup_key(entry)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                score = _base_score(entry)
                # 改善履歴がある失敗事例はスコアを加算
                src = entry.get("source", "")
                if src in improvement_scores:
                    score = round(min(1.0, score + improvement_scores[src]), 2)

                pattern: dict = {
                    "pattern_id":      f"{prefix}-{cat_counter:03d}",
                    "category":        cat,
                    "source":          src,
                    "cause":           entry.get("cause",  ""),
                    "action":          entry.get("action", ""),
                    "result":          entry.get("result", ""),
                    "score":           score,
                    "reproducibility": entry.get("reproducibility", "medium"),
                    "pattern_type":    entry.get("pattern_type", ""),
                }
                # improvement カテゴリには追加フィールドを付与
                if cat == "improvement":
                    pattern["module"]           = entry.get("module", "")
                    pattern["failure_category"] = entry.get("failure_category", "")
                    pattern["description"]      = entry.get("description", "")

                patterns.append(pattern)
                cat_counter += 1

        return patterns

    # ── MECE 検証 ────────────────────────────────────────────

    def validate_mece_structure(self, patterns: list[dict]) -> dict:
        """
        パターンリストに対して MECE（相互排他・網羅性）チェックを行う。

        Returns:
            mece_log — {
                checked_count, duplicate_count, category_coverage,
                category_counts, issues, is_mece
            }
        """
        # 相互排他チェック（同一 cause+action の重複）
        seen: dict[str, list[str]] = {}
        for p in patterns:
            key = _dedup_key(p)
            seen.setdefault(key, []).append(p["pattern_id"])
        duplicates = {k: v for k, v in seen.items() if len(v) > 1}

        # 網羅性チェック（4カテゴリすべてが存在するか）
        required_cats  = {"operational", "improvement", "maintenance", "environment"}
        present_cats   = {p["category"] for p in patterns}
        missing_cats   = required_cats - present_cats

        cat_counts: dict[str, int] = {}
        for p in patterns:
            cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1

        issues: list[str] = []
        if duplicates:
            issues.append(f"重複パターン {len(duplicates)} 件検出")
        if missing_cats:
            issues.append(f"カテゴリ不足: {sorted(missing_cats)}")

        return {
            "checked_count":     len(patterns),
            "duplicate_count":   len(duplicates),
            "duplicates":        duplicates,
            "category_coverage": sorted(present_cats),
            "category_counts":   cat_counts,
            "missing_categories": sorted(missing_cats),
            "issues":            issues,
            "is_mece":           len(duplicates) == 0 and len(missing_cats) == 0,
        }

    # ── エクスポート統合 ─────────────────────────────────────

    def export_patterns(
        self,
        patterns: list[dict],
        mece_log: dict,
    ) -> dict:
        """
        パターンリストと MECE ログを統合した出力 dict を生成する。

        Returns:
            dict — learning_patterns.json に保存する完全データ構造
        """
        scores      = [p["score"] for p in patterns]
        avg_score   = round(sum(scores) / len(scores), 4) if scores else 0.0
        high_conf   = [p for p in patterns if p["score"] >= 0.9]
        medium_conf = [p for p in patterns if 0.7 <= p["score"] < 0.9]
        low_conf    = [p for p in patterns if p["score"] < 0.7]

        by_category: dict[str, list[dict]] = {}
        for p in patterns:
            by_category.setdefault(p["category"], []).append(p)

        return {
            "generated_at":    datetime.now().isoformat(),
            "version":         "1.0.0",
            "phase":           7,
            "total_patterns":  len(patterns),
            "average_score":   avg_score,
            "score_distribution": {
                "high_confidence":   len(high_conf),
                "medium_confidence": len(medium_conf),
                "low_confidence":    len(low_conf),
            },
            "patterns":        patterns,
            "by_category":     by_category,
            "mece_log":        mece_log,
            "phase8_ready":    False,
        }

    # ── 保存 / 読み込み ──────────────────────────────────────

    def save_patterns(
        self,
        result: dict,
        path:   Path | None = None,
    ) -> None:
        """docs/knowledge_cycle/learning_patterns.json に保存する。"""
        p = path or self._patterns_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def load_patterns(self, path: Path | None = None) -> dict:
        """learning_patterns.json を読み込む。"""
        p = path or self._patterns_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ── summary.log 追記 ─────────────────────────────────────

    def write_summary_entry(
        self,
        result:   dict,
        log_path: Path | None = None,
    ) -> None:
        """WP9420 完了エントリを summary.log に追記する。"""
        path     = log_path or self._summary_log
        ts       = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        mece     = result.get("mece_log", {})
        sd       = result.get("score_distribution", {})

        entry = (
            f"\n[{ts}] WP9420 学習パターン生成完了\n"
            f"  学習パターン総数  : {result.get('total_patterns', 0)}件\n"
            f"  スコア平均        : {result.get('average_score', 0.0):.4f}\n"
            f"  高信頼度（≥0.9）  : {sd.get('high_confidence', 0)}件\n"
            f"  中信頼度（0.7〜）  : {sd.get('medium_confidence', 0)}件\n"
            f"  低信頼度（<0.7）  : {sd.get('low_confidence', 0)}件\n"
            f"  MECE判定          : {'OK（相互排他・網羅性確認済み）' if mece.get('is_mece') else 'WARN — ' + ' / '.join(mece.get('issues', []))}\n"
            f"  出力ファイル      : docs/knowledge_cycle/learning_patterns.json\n"
            f"  Phase 7 フラグ    : READY（WP9430 実行可）\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── 内部ヘルパ ───────────────────────────────────────────

    def _build_improvement_score_map(self, failure_repo: dict) -> dict[str, float]:
        """
        failure_repository の各失敗 ID に改善スコアを割り当てる。
        resolution パターンに応じてスコアを付与する。
        """
        score_map: dict[str, float] = {}
        for failure in failure_repo.get("failures", []):
            fid        = failure.get("failure_id", "")
            resolution = failure.get("resolution", "")
            # HITL 移譲・フェイルセーフは実績あり → +0.05
            if "HITL" in resolution or "移譲" in resolution or "フェイルセーフ" in resolution:
                score_map[fid] = 0.05
            # 再入力・見直しは対話的解決 → +0.03
            elif "再入力" in resolution or "見直し" in resolution:
                score_map[fid] = 0.03
            else:
                score_map[fid] = 0.02
        return score_map
