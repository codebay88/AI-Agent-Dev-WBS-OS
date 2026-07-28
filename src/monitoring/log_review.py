"""
OperationalLogReview — Phase 5 WP9130 ログ確認・安定性チェック

summary.log の傾向分析・フェイルセーフ履歴・HITL承認履歴を集計し、
運用品質を評価する。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .daily_operation import LogReviewer, ANOMALY_THRESHOLDS
from .hitl_tracker import HITLDecision, HITLTracker

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

# 安定性評価の文字列定数
STABILITY_STABLE   = "stable"
STABILITY_WARNING  = "warning"
STABILITY_CRITICAL = "critical"


class OperationalLogReview:
    """
    運用ログ全体の傾向分析・フェイルセーフ確認・HITL承認確認・安定性評価を行う。

    使い方:
        review = OperationalLogReview()
        counts   = review.collect_log_counts(log_path)
        trend    = review.analyze_trends(log_path)
        failsafe = review.summarize_failsafe(handler)
        hitl     = review.summarize_hitl_approval(tracker)
        stability = review.evaluate_stability(counts, failsafe, hitl)
        review.write_review_record(counts, trend, failsafe, hitl, stability, log_path)
    """

    def __init__(
        self,
        thresholds: dict[str, int] | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._reviewer   = LogReviewer()
        self._thresholds = thresholds or ANOMALY_THRESHOLDS
        self._summary_log = summary_log or SUMMARY_LOG

    # ── ログ収集と件数集計 ─────────────────────────────────────

    def collect_log_counts(self, log_path: Path) -> dict[str, int]:
        """INFO/WARNING/ERROR/RETRY/HITL の累計件数を返す。"""
        return self._reviewer.parse_log(log_path)

    # ── 傾向分析 ───────────────────────────────────────────────

    def analyze_trends(self, log_path: Path) -> dict:
        """
        summary.log の傾向を分析する。

        Returns:
            consecutive_errors : ログ内で最大何件連続 ERROR が出たか
            trend_warnings     : 傾向警告メッセージリスト
            anomalies          : 閾値超過リスト（LogReviewer.detect_anomaly と同形式）
        """
        if not log_path.exists():
            return {"consecutive_errors": 0, "trend_warnings": [], "anomalies": []}

        lines = log_path.read_text(encoding="utf-8").splitlines()
        counts = self.collect_log_counts(log_path)
        anomalies = self._reviewer.detect_anomaly(counts, lines, self._thresholds)

        consecutive = 0
        max_consec  = 0
        for line in lines:
            if "ALERT ERROR" in line:
                consecutive += 1
                max_consec = max(max_consec, consecutive)
            else:
                consecutive = 0

        trend_warnings: list[str] = []
        if max_consec >= self._thresholds["consecutive_errors"]:
            trend_warnings.append(
                f"連続ERROR {max_consec}件を検出（閾値: {self._thresholds['consecutive_errors']}件）"
            )
        if counts.get("RETRY", 0) > self._thresholds["retry_per_session"]:
            trend_warnings.append(
                f"RETRY頻発 {counts['RETRY']}件（閾値: {self._thresholds['retry_per_session']}件）"
            )
        if counts.get("HITL", 0) > self._thresholds["hitl_per_session"]:
            trend_warnings.append(
                f"HITL過多 {counts['HITL']}件（閾値: {self._thresholds['hitl_per_session']}件）"
            )

        return {
            "consecutive_errors": max_consec,
            "trend_warnings":     trend_warnings,
            "anomalies":          anomalies,
        }

    # ── フェイルセーフ履歴確認 ─────────────────────────────────

    def summarize_failsafe(self, handler) -> dict:
        """
        MonitoringHandler のフェイルセーフ発動履歴を集計する。

        Returns:
            count               : 発動件数
            events              : イベントリスト
            max_retry_exceeded  : MAX_RETRY 超過フラグ（alerts に RETRY が含まれるか）
            alert_count         : handler が発火したアラート総数
        """
        events = handler.failsafe_events
        alerts = handler.alerts
        retry_alerts = [a for a in alerts if a.get("level") == "RETRY"]
        return {
            "count":              len(events),
            "events":             events,
            "max_retry_exceeded": len(retry_alerts) > 0,
            "alert_count":        len(alerts),
        }

    # ── HITL 承認履歴確認 ─────────────────────────────────────

    def summarize_hitl_approval(self, tracker: HITLTracker) -> dict:
        """
        HITLTracker の承認・却下・再処理件数と承認率を集計する。

        Returns:
            approved            : 承認件数
            rejected            : 却下件数
            reprocessed         : 再処理件数
            total               : 全判断件数
            approval_rate       : 承認率（承認件数 / 全判断件数）
            misapproval_warning : 承認率 > 90% なら True
        """
        history = tracker._history  # type: ignore[attr-defined]
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

    # ── 安定性評価 ────────────────────────────────────────────

    def evaluate_stability(
        self,
        counts:   dict[str, int],
        failsafe: dict,
        hitl:     dict,
    ) -> str:
        """
        ログ件数・フェイルセーフ状況・HITL 承認率から総合安定性を評価する。

        Returns:
            "stable"   : 正常稼働
            "warning"  : 注意（軽微な異常あり）
            "critical" : 重大（ERROR 3件以上、または即時対応が必要）
        """
        errors = counts.get("ERROR", 0)
        th     = self._thresholds["consecutive_errors"]

        if errors >= th:
            return STABILITY_CRITICAL

        if (
            errors > 0
            or failsafe.get("max_retry_exceeded", False)
            or hitl.get("misapproval_warning", False)
            or counts.get("RETRY", 0) > self._thresholds["retry_per_session"]
            or counts.get("HITL", 0) > self._thresholds["hitl_per_session"]
        ):
            return STABILITY_WARNING

        return STABILITY_STABLE

    # ── 運用記録書き込み ──────────────────────────────────────

    def write_review_record(
        self,
        counts:    dict[str, int],
        trend:     dict,
        failsafe:  dict,
        hitl:      dict,
        stability: str,
        log_path:  Path | None = None,
    ) -> None:
        """ログ確認結果を summary.log に追記する。"""
        path    = log_path or self._summary_log
        ts      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        anomaly_str = "なし" if not trend["anomalies"] else "; ".join(trend["anomalies"])
        warn_str    = "なし" if not trend["trend_warnings"] else "; ".join(trend["trend_warnings"])
        rate        = hitl["approval_rate"]
        mis_warn    = " ⚠ 誤承認検知" if hitl["misapproval_warning"] else ""

        entry = (
            f"\n[{ts}] WP9130 ログ確認記録\n"
            f"  安定性評価   : {stability}\n"
            f"  ERROR件数    : {counts.get('ERROR', 0)}\n"
            f"  WARNING件数  : {counts.get('WARNING', 0)}\n"
            f"  RETRY件数    : {counts.get('RETRY', 0)}\n"
            f"  HITL件数     : {counts.get('HITL', 0)}\n"
            f"  異常傾向     : {anomaly_str}\n"
            f"  傾向警告     : {warn_str}\n"
            f"  フェイルセーフ発動: {failsafe['count']}件\n"
            f"  HITL承認率   : {rate:.1%}{mis_warn}\n"
            f"  Phase 5 フラグ: READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
