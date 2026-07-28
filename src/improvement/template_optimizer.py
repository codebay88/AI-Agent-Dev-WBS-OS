"""
TemplateOptimizer — Phase 6 WP9220 テンプレ改善モジュール

feedback_report.json の改善候補を読み込み、
閾値設定・テンプレート構造・再試行ロジックを最適化する。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR       = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG    = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
FEEDBACK_PATH  = BASE_DIR / "docs" / "phase6" / "feedback_report.json"
THRESHOLD_PATH = BASE_DIR / "src" / "config" / "thresholds.yaml"
TEMPLATE_INDEX = BASE_DIR / "src" / "templates" / "template_index.yaml"

# 改善候補キーワード → 調整内容
_ADJUSTMENT_RULES: list[tuple[str, str, callable]] = [
    ("RETRY閾値",   "retry_per_session",      lambda v: max(1, v - 1)),
    ("フェイルセーフ", "hitl_per_session",      lambda v: max(1, v - 2)),
    ("誤承認",       "approval_rate_warning",  lambda v: max(0.80, v - 0.05)),
    ("HITL発動",    "hitl_per_session",       lambda v: max(1, v - 1)),
]


class TemplateOptimizer:
    """
    feedback_report.json の分析結果を読み込み、
    閾値・テンプレート・再試行ロジックを最適化する。

    使い方:
        opt = TemplateOptimizer()
        feedback    = opt.load_feedback()
        adjustments = opt.apply_threshold_adjustments(feedback)
        summary     = opt.generate_optimization_summary(feedback, adjustments)
        opt.save_thresholds(adjustments["updated_thresholds"])
        opt.write_summary_entry(summary)
    """

    def __init__(
        self,
        feedback_path:  Path | None = None,
        threshold_path: Path | None = None,
        template_index: Path | None = None,
        summary_log:    Path | None = None,
    ) -> None:
        self._feedback_path  = feedback_path  or FEEDBACK_PATH
        self._threshold_path = threshold_path or THRESHOLD_PATH
        self._template_index = template_index or TEMPLATE_INDEX
        self._summary_log    = summary_log    or SUMMARY_LOG

    # ── フィードバック読み込み ─────────────────────────────────

    def load_feedback(self, path: Path | None = None) -> dict:
        """
        feedback_report.json を読み込んで返す。

        Returns:
            JSON の内容 dict。ファイル不在時は空の安定状態 dict。
        """
        p = path or self._feedback_path
        if not p.exists():
            return {
                "improvement_targets": [],
                "anomaly_trends": [],
                "phase6_ready": True,
            }
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ── 閾値調整 ──────────────────────────────────────────────

    def load_thresholds(self, path: Path | None = None) -> dict:
        """thresholds.yaml を読み込んで返す。"""
        p = path or self._threshold_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def apply_threshold_adjustments(
        self,
        feedback:   dict,
        base:       dict | None = None,
    ) -> dict:
        """
        feedback の improvement_targets に基づき閾値を調整する。

        改善候補がない場合は「安定稼働状態」として変更なしを返す。

        Returns:
            status              : "stable_no_change" | "adjusted"
            changes             : {field: {"before": v, "after": v}} の dict
            updated_thresholds  : 調整後の thresholds dict（base を更新したもの）
        """
        thresholds = base if base is not None else self.load_thresholds()
        targets    = feedback.get("improvement_targets", [])

        if not targets:
            return {
                "status":             "stable_no_change",
                "changes":            {},
                "updated_thresholds": thresholds,
            }

        changes: dict[str, dict] = {}
        monitoring = thresholds.get("monitoring", {})
        hitl_cfg   = thresholds.get("hitl", {})

        for target in targets:
            for keyword, field, adjuster in _ADJUSTMENT_RULES:
                if keyword in target:
                    if field in monitoring:
                        before = monitoring[field]
                        monitoring[field] = adjuster(before)
                        changes[field] = {"before": before, "after": monitoring[field]}
                    elif field in hitl_cfg:
                        before = hitl_cfg[field]
                        hitl_cfg[field] = adjuster(before)
                        changes[field] = {"before": before, "after": hitl_cfg[field]}

        updated = dict(thresholds)
        updated["monitoring"] = monitoring
        updated["hitl"]       = hitl_cfg

        return {
            "status":             "adjusted",
            "changes":            changes,
            "updated_thresholds": updated,
        }

    def save_thresholds(
        self,
        thresholds: dict,
        path: Path | None = None,
    ) -> None:
        """調整済み閾値を thresholds.yaml に保存する。"""
        p = path or self._threshold_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(thresholds, f, allow_unicode=True, sort_keys=False)

    # ── テンプレート構造確認 ──────────────────────────────────

    def load_template_index(self, path: Path | None = None) -> dict:
        """template_index.yaml を読み込んで返す。"""
        p = path or self._template_index
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def validate_template_structure(self, index: dict) -> list[str]:
        """
        テンプレートインデックスの構造を検証する。

        Returns:
            問題点リスト（空なら正常）
        """
        issues: list[str] = []
        templates = index.get("templates", [])
        if not templates:
            issues.append("templates リストが空です")
            return issues

        required_ids = {"TMP_HIGH", "TMP_MEDIUM", "TMP_LOW"}
        found_ids    = {t.get("id") for t in templates}
        missing      = required_ids - found_ids
        if missing:
            issues.append(f"必須テンプレートが不足: {sorted(missing)}")

        for t in templates:
            for key in ("id", "priority", "module", "pattern"):
                if not t.get(key):
                    issues.append(f"テンプレート {t.get('id', '?')} に '{key}' が未設定")

        return issues

    # ── 最適化サマリー生成 ────────────────────────────────────

    def generate_optimization_summary(
        self,
        feedback:    dict,
        adjustments: dict,
    ) -> dict:
        """最適化結果のサマリー dict を生成する。"""
        return {
            "optimized_at":       datetime.now().isoformat(),
            "feedback_source":    str(self._feedback_path),
            "improvements_applied": feedback.get("improvement_targets", []),
            "threshold_changes":  adjustments.get("changes", {}),
            "stability_status":   adjustments.get("status", "stable_no_change"),
            "phase6_ready":       True,
        }

    # ── 記録書き込み ─────────────────────────────────────────

    def write_summary_entry(
        self,
        summary:  dict,
        log_path: Path | None = None,
    ) -> None:
        """WP9220 完了エントリを summary.log に追記する。"""
        path    = log_path or self._summary_log
        ts      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        status  = summary.get("stability_status", "stable_no_change")
        applied = summary.get("improvements_applied", [])
        changes = summary.get("threshold_changes", {})

        applied_str = "なし（安定稼働状態）" if not applied else "\n" + "\n".join(
            f"    - {a}" for a in applied
        )
        changes_str = "変更なし" if not changes else "\n" + "\n".join(
            f"    - {k}: {v['before']} → {v['after']}" for k, v in changes.items()
        )

        entry = (
            f"\n[{ts}] WP9220 テンプレ改善完了\n"
            f"  最適化ステータス: {status}\n"
            f"  適用改善候補    : {applied_str}\n"
            f"  閾値変更        : {changes_str}\n"
            f"  Phase 6 フラグ  : READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
