"""
FeedbackCollector — Phase 6 WP9210 フィードバック収集モジュール

Phase 5 運用結果（ログ・承認履歴・フェイルセーフ）を集約し、
改善層へのフィードバックとして整理・出力する。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.monitoring.daily_operation import LogReviewer, ANOMALY_THRESHOLDS

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
REPORT_DIR  = BASE_DIR / "docs" / "phase6"
REPORT_PATH = REPORT_DIR / "feedback_report.json"

# 改善候補を判断するルール
_IMPROVEMENT_RULES: list[tuple[str, str]] = [
    ("retry_rate",         0.10, "RETRY閾値の見直し（retry_per_session の再設定）"),
    ("hitl_rate",          0.30, "HITL発動条件の緩和（曖昧語辞書の精査）"),
    ("failsafe_rate",      0.05, "フェイルセーフ発動頻度が高い（API安定性の確認）"),
    ("misapproval_warning",True, "誤承認率が高い（承認フローの見直し）"),
]


class FeedbackCollector:
    """
    Phase 5 の運用データを収集・分析し、改善層フィードバックを生成する。

    使い方:
        fc = FeedbackCollector()
        log_data      = fc.collect_from_log(log_path)
        hitl_data     = fc.collect_from_hitl_tracker(tracker)
        failsafe_data = fc.collect_from_monitor(handler)
        report        = fc.analyze(log_data, hitl_data, failsafe_data)
        fc.save_report(report)
        fc.write_summary_entry(report)
    """

    def __init__(
        self,
        thresholds:  dict[str, int] | None = None,
        summary_log: Path | None = None,
        report_path: Path | None = None,
    ) -> None:
        self._reviewer    = LogReviewer()
        self._thresholds  = thresholds or ANOMALY_THRESHOLDS
        self._summary_log = summary_log or SUMMARY_LOG
        self._report_path = report_path or REPORT_PATH

    # ── データ収集 ────────────────────────────────────────────

    def collect_from_log(self, log_path: Path) -> dict:
        """
        summary.log から ERROR／WARNING／RETRY／HITL 件数を抽出する。

        Returns:
            counts     : INFO/WARNING/ERROR/RETRY/HITL の件数 dict
            total_ops  : ERROR+WARNING+RETRY+HITL の合計（INFO除く）
            anomalies  : 閾値超過リスト
        """
        counts   = self._reviewer.parse_log(log_path)
        lines    = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
        anomalies = self._reviewer.detect_anomaly(counts, lines, self._thresholds)
        total_ops = sum(counts.get(k, 0) for k in ("WARNING", "ERROR", "RETRY", "HITL"))
        return {
            "counts":    counts,
            "total_ops": total_ops,
            "anomalies": anomalies,
        }

    def collect_from_hitl_tracker(self, tracker) -> dict:
        """
        HITLTracker の承認・却下・再処理履歴を取得する。

        Returns:
            approved, rejected, reprocessed : 各件数
            total       : 全判断件数
            approval_rate : 承認率
            misapproval_warning : 承認率 > 90% フラグ
        """
        history     = tracker._history  # type: ignore[attr-defined]
        approved    = sum(1 for e in history if e.decision == "approve")
        rejected    = sum(1 for e in history if e.decision == "reject")
        reprocessed = sum(1 for e in history if e.decision == "reprocess")
        return {
            "approved":            approved,
            "rejected":            rejected,
            "reprocessed":         reprocessed,
            "total":               len(history),
            "approval_rate":       tracker.approval_rate(),
            "misapproval_warning": tracker.is_approval_rate_high(),
        }

    def collect_from_monitor(self, handler) -> dict:
        """
        MonitoringHandler のフェイルセーフ・アラート履歴を取得する。

        Returns:
            failsafe_count     : フェイルセーフ発動件数
            alert_count        : 総アラート件数
            retry_alert_count  : RETRY アラート件数
            error_alert_count  : ERROR アラート件数
            max_retry_exceeded : RETRY アラートが 1 件以上あるか
        """
        alerts         = handler.alerts
        failsafe_events = handler.failsafe_events
        return {
            "failsafe_count":    len(failsafe_events),
            "alert_count":       len(alerts),
            "retry_alert_count": sum(1 for a in alerts if a.get("level") == "RETRY"),
            "error_alert_count": sum(1 for a in alerts if a.get("level") == "ERROR"),
            "max_retry_exceeded": any(a.get("level") == "RETRY" for a in alerts),
        }

    # ── 分析 ──────────────────────────────────────────────────

    def analyze(
        self,
        log_data:      dict,
        hitl_data:     dict,
        failsafe_data: dict,
    ) -> dict:
        """
        収集データを統合分析し、改善フィードバックを生成する。

        Returns:
            collected_at       : 収集日時 ISO8601
            anomaly_trends     : 異常傾向リスト
            approval_rate      : HITL 承認率
            retry_rate         : RETRY アラート率 (retry_alert / total_ops or 0)
            failsafe_rate      : フェイルセーフ発動率 (failsafe_count / total_ops or 0)
            misapproval_warning: 誤承認フラグ
            improvement_targets: 改善候補リスト
            phase6_ready       : True（常に）
        """
        total_ops = max(log_data.get("total_ops", 0), 1)  # ゼロ除算防止
        retry_rate    = failsafe_data.get("retry_alert_count", 0) / total_ops
        failsafe_rate = failsafe_data.get("failsafe_count", 0)    / total_ops
        approval_rate = hitl_data.get("approval_rate", 0.0)
        misapproval   = hitl_data.get("misapproval_warning", False)

        improvement_targets = self._extract_targets(
            retry_rate, failsafe_rate, misapproval,
            log_data.get("anomalies", []),
        )

        return {
            "collected_at":        datetime.now().isoformat(),
            "anomaly_trends":      log_data.get("anomalies", []),
            "approval_rate":       approval_rate,
            "retry_rate":          retry_rate,
            "failsafe_rate":       failsafe_rate,
            "misapproval_warning": misapproval,
            "improvement_targets": improvement_targets,
            "phase6_ready":        True,
        }

    def _extract_targets(
        self,
        retry_rate:    float,
        failsafe_rate: float,
        misapproval:   bool,
        anomalies:     list[str],
    ) -> list[str]:
        targets: list[str] = []
        if retry_rate > 0.10:
            targets.append("RETRY閾値の見直し（retry_per_session の再設定）")
        if failsafe_rate > 0.05:
            targets.append("フェイルセーフ発動頻度が高い（API安定性の確認）")
        if misapproval:
            targets.append("誤承認率が高い（承認フローの見直し）")
        if any("HITL" in a for a in anomalies):
            targets.append("HITL発動条件の緩和（曖昧語辞書の精査）")
        return targets

    # ── 出力 ──────────────────────────────────────────────────

    def save_report(self, report: dict, path: Path | None = None) -> None:
        """分析結果を feedback_report.json に保存する。"""
        target = path or self._report_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def write_summary_entry(self, report: dict, log_path: Path | None = None) -> None:
        """WP9210 完了エントリを summary.log に追記する。"""
        path = log_path or self._summary_log
        ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        targets_str = "なし" if not report["improvement_targets"] else (
            "\n" + "\n".join(f"    - {t}" for t in report["improvement_targets"])
        )
        entry = (
            f"\n[{ts}] WP9210 フィードバック収集完了\n"
            f"  承認率         : {report['approval_rate']:.1%}\n"
            f"  RETRY率        : {report['retry_rate']:.2%}\n"
            f"  フェイルセーフ率: {report['failsafe_rate']:.2%}\n"
            f"  誤承認警告     : {'あり ⚠' if report['misapproval_warning'] else 'なし'}\n"
            f"  異常傾向       : {'なし' if not report['anomaly_trends'] else '; '.join(report['anomaly_trends'])}\n"
            f"  改善候補       : {targets_str}\n"
            f"  Phase 6 フラグ : READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
