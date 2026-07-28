"""WP9130 ログ確認テスト（Operational Log Review and Stability Check Test）
Phase 5：運用層（9000番台）

テスト対象:
  - src/monitoring/log_review.py
    - OperationalLogReview.collect_log_counts()
    - OperationalLogReview.analyze_trends()
    - OperationalLogReview.summarize_failsafe()
    - OperationalLogReview.summarize_hitl_approval()
    - OperationalLogReview.evaluate_stability()
    - OperationalLogReview.write_review_record()
"""

from pathlib import Path

import pytest

from src.monitoring.log_review import (
    OperationalLogReview,
    STABILITY_STABLE,
    STABILITY_WARNING,
    STABILITY_CRITICAL,
)
from src.monitoring.hitl_tracker import HITLTracker
from src.monitoring.monitor import MonitoringHandler


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _make_log(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════════════════════════
# TestWP9131 — ログ収集と件数集計
# ════════════════════════════════════════════════════════════════════════════

class TestWP9131_LogCollection:

    @pytest.fixture
    def review(self):
        return OperationalLogReview()

    def test_collect_returns_dict_with_all_keys(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log", "")
        counts = review.collect_log_counts(log)
        for k in ("INFO", "WARNING", "ERROR", "RETRY", "HITL"):
            assert k in counts

    def test_collect_empty_log_all_zeros(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log", "")
        counts = review.collect_log_counts(log)
        assert all(v == 0 for v in counts.values())

    def test_collect_counts_error_lines(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT ERROR module=f10 msg=X\n"
            "[T] ALERT ERROR module=f20 msg=Y\n")
        assert review.collect_log_counts(log)["ERROR"] == 2

    def test_collect_counts_warning_lines(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT WARNING module=f30 msg=W\n")
        assert review.collect_log_counts(log)["WARNING"] == 1

    def test_collect_counts_retry_lines(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT RETRY module=f10 msg=リトライ\n"
            "[T] ALERT RETRY module=f10 msg=リトライ\n"
            "[T] ALERT RETRY module=f10 msg=リトライ\n")
        assert review.collect_log_counts(log)["RETRY"] == 3

    def test_collect_counts_hitl_lines(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT HITL module=f10 msg=HITL移譲\n")
        assert review.collect_log_counts(log)["HITL"] == 1

    def test_collect_counts_mixed_lines(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT ERROR module=f10 msg=X\n"
            "[T] ALERT WARNING module=f20 msg=W\n"
            "[T] ALERT RETRY module=f10 msg=R\n"
            "[T] ALERT HITL module=f10 msg=H\n")
        c = review.collect_log_counts(log)
        assert c["ERROR"] == 1 and c["WARNING"] == 1
        assert c["RETRY"] == 1 and c["HITL"] == 1

    def test_collect_nonexistent_log_returns_zeros(self, review, tmp_path):
        log = tmp_path / "nonexistent.log"
        counts = review.collect_log_counts(log)
        assert all(v == 0 for v in counts.values())


# ════════════════════════════════════════════════════════════════════════════
# TestWP9132 — 異常傾向検出
# ════════════════════════════════════════════════════════════════════════════

class TestWP9132_AnomalyTrend:

    @pytest.fixture
    def review(self):
        return OperationalLogReview()

    def test_analyze_returns_consecutive_errors_key(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log", "")
        result = review.analyze_trends(log)
        assert "consecutive_errors" in result

    def test_analyze_returns_trend_warnings_list(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log", "")
        result = review.analyze_trends(log)
        assert isinstance(result["trend_warnings"], list)

    def test_analyze_returns_anomalies_list(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log", "")
        result = review.analyze_trends(log)
        assert isinstance(result["anomalies"], list)

    def test_consecutive_error_detected(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT ERROR module=f10 msg=X\n"
            "[T] ALERT ERROR module=f10 msg=X\n"
            "[T] ALERT ERROR module=f10 msg=X\n")
        result = review.analyze_trends(log)
        assert result["consecutive_errors"] >= 3

    def test_consecutive_error_triggers_trend_warning(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT ERROR module=f10 msg=X\n" * 3)
        result = review.analyze_trends(log)
        assert any("連続ERROR" in w for w in result["trend_warnings"])

    def test_retry_overload_triggers_trend_warning(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT RETRY module=f10 msg=リトライ\n" * 6)
        result = review.analyze_trends(log)
        assert any("RETRY" in w for w in result["trend_warnings"])

    def test_hitl_overload_triggers_trend_warning(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT HITL module=f10 msg=H\n" * 11)
        result = review.analyze_trends(log)
        assert any("HITL" in w for w in result["trend_warnings"])

    def test_clean_log_has_no_trend_warnings(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log", "通常稼働\n")
        result = review.analyze_trends(log)
        assert result["trend_warnings"] == []

    def test_nonconsecutive_errors_not_counted(self, review, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT ERROR module=f10 msg=X\n"
            "[T] 通常ログ\n"
            "[T] ALERT ERROR module=f10 msg=X\n")
        result = review.analyze_trends(log)
        assert result["consecutive_errors"] == 1

    def test_nonexistent_log_returns_empty(self, review, tmp_path):
        result = review.analyze_trends(tmp_path / "no.log")
        assert result["consecutive_errors"] == 0
        assert result["trend_warnings"] == []
        assert result["anomalies"] == []


# ════════════════════════════════════════════════════════════════════════════
# TestWP9133 — フェイルセーフ履歴確認
# ════════════════════════════════════════════════════════════════════════════

class TestWP9133_FailsafeHistory:

    @pytest.fixture
    def review(self):
        return OperationalLogReview()

    @pytest.fixture
    def handler(self, tmp_path):
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def test_summarize_failsafe_has_count(self, review, handler):
        result = review.summarize_failsafe(handler)
        assert "count" in result

    def test_summarize_failsafe_count_zero_initially(self, review, handler):
        assert review.summarize_failsafe(handler)["count"] == 0

    def test_summarize_failsafe_count_increments(self, review, handler):
        handler.record_failsafe("F10", "TRC-001", "SRC-001", "L")
        handler.record_failsafe("F20", "TRC-002", "SRC-002", "M")
        assert review.summarize_failsafe(handler)["count"] == 2

    def test_summarize_failsafe_has_events_list(self, review, handler):
        result = review.summarize_failsafe(handler)
        assert isinstance(result["events"], list)

    def test_summarize_failsafe_event_has_module(self, review, handler):
        handler.record_failsafe("F10", "TRC-001", "SRC-001", "L")
        events = review.summarize_failsafe(handler)["events"]
        assert events[0]["module"] == "F10"

    def test_summarize_failsafe_has_max_retry_exceeded_flag(self, review, handler):
        result = review.summarize_failsafe(handler)
        assert "max_retry_exceeded" in result

    def test_summarize_failsafe_alert_count_reflects_errors(self, review, handler):
        import logging
        logger = logging.getLogger("src.agents.f10_module")
        logger.addHandler(handler)
        logger.error("テストエラー")
        logger.removeHandler(handler)
        result = review.summarize_failsafe(handler)
        assert result["alert_count"] >= 1


# ════════════════════════════════════════════════════════════════════════════
# TestWP9134 — HITL 承認履歴確認
# ════════════════════════════════════════════════════════════════════════════

class TestWP9134_HITLApprovalHistory:

    @pytest.fixture
    def review(self):
        return OperationalLogReview()

    @pytest.fixture
    def tracker(self):
        return HITLTracker()

    def test_summarize_hitl_has_approved_key(self, review, tracker):
        assert "approved" in review.summarize_hitl_approval(tracker)

    def test_summarize_hitl_has_rejected_key(self, review, tracker):
        assert "rejected" in review.summarize_hitl_approval(tracker)

    def test_summarize_hitl_has_reprocessed_key(self, review, tracker):
        assert "reprocessed" in review.summarize_hitl_approval(tracker)

    def test_summarize_hitl_counts_correctly(self, review, tracker):
        tracker.record_decision("F10", "E001", "approve")
        tracker.record_decision("F10", "E002", "approve")
        tracker.record_decision("F10", "E003", "reject")
        tracker.record_decision("F10", "E004", "reprocess")
        r = review.summarize_hitl_approval(tracker)
        assert r["approved"] == 2
        assert r["rejected"] == 1
        assert r["reprocessed"] == 1

    def test_summarize_hitl_has_approval_rate(self, review, tracker):
        tracker.record_decision("F10", "E001", "approve")
        r = review.summarize_hitl_approval(tracker)
        assert r["approval_rate"] == 1.0

    def test_summarize_hitl_misapproval_warning_false_on_normal(self, review, tracker):
        for i in range(8):
            tracker.record_decision("F10", f"E{i:03}", "approve")
        for i in range(8, 10):
            tracker.record_decision("F10", f"E{i:03}", "reject")
        r = review.summarize_hitl_approval(tracker)
        assert r["misapproval_warning"] is False

    def test_summarize_hitl_misapproval_warning_true_on_high_rate(self, review, tracker):
        for i in range(10):
            tracker.record_decision("F10", f"E{i:03}", "approve")
        r = review.summarize_hitl_approval(tracker)
        assert r["misapproval_warning"] is True


# ════════════════════════════════════════════════════════════════════════════
# TestWP9135 — 安定性評価
# ════════════════════════════════════════════════════════════════════════════

class TestWP9135_StabilityEvaluation:

    @pytest.fixture
    def review(self):
        return OperationalLogReview()

    @pytest.fixture
    def clean_counts(self):
        return {"INFO": 10, "WARNING": 0, "ERROR": 0, "RETRY": 0, "HITL": 0}

    @pytest.fixture
    def clean_failsafe(self):
        return {"count": 0, "events": [], "max_retry_exceeded": False, "alert_count": 0}

    @pytest.fixture
    def clean_hitl(self):
        return {"approved": 3, "rejected": 2, "reprocessed": 0,
                "total": 5, "approval_rate": 0.6, "misapproval_warning": False}

    def test_stable_on_clean_state(self, review, clean_counts, clean_failsafe, clean_hitl):
        assert review.evaluate_stability(clean_counts, clean_failsafe, clean_hitl) == STABILITY_STABLE

    def test_critical_on_three_or_more_errors(self, review, clean_failsafe, clean_hitl):
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 3, "RETRY": 0, "HITL": 0}
        assert review.evaluate_stability(counts, clean_failsafe, clean_hitl) == STABILITY_CRITICAL

    def test_warning_on_single_error(self, review, clean_failsafe, clean_hitl):
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 1, "RETRY": 0, "HITL": 0}
        assert review.evaluate_stability(counts, clean_failsafe, clean_hitl) == STABILITY_WARNING

    def test_warning_on_misapproval(self, review, clean_counts, clean_failsafe):
        hitl = {"approved": 10, "rejected": 0, "reprocessed": 0,
                "total": 10, "approval_rate": 1.0, "misapproval_warning": True}
        assert review.evaluate_stability(clean_counts, clean_failsafe, hitl) == STABILITY_WARNING

    def test_warning_on_max_retry_exceeded(self, review, clean_counts, clean_hitl):
        failsafe = {"count": 1, "events": [], "max_retry_exceeded": True, "alert_count": 1}
        assert review.evaluate_stability(clean_counts, failsafe, clean_hitl) == STABILITY_WARNING

    def test_warning_on_excessive_retry_count(self, review, clean_failsafe, clean_hitl):
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "RETRY": 6, "HITL": 0}
        assert review.evaluate_stability(counts, clean_failsafe, clean_hitl) == STABILITY_WARNING


# ════════════════════════════════════════════════════════════════════════════
# TestWP9136 — 運用記録書き込み（summary.log 出力）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9136_OperationalRecord:

    @pytest.fixture
    def review(self):
        return OperationalLogReview()

    @pytest.fixture
    def sample_args(self):
        counts   = {"INFO": 10, "WARNING": 0, "ERROR": 0, "RETRY": 0, "HITL": 0}
        trend    = {"consecutive_errors": 0, "trend_warnings": [], "anomalies": []}
        failsafe = {"count": 0, "events": [], "max_retry_exceeded": False, "alert_count": 0}
        hitl     = {"approved": 2, "rejected": 1, "reprocessed": 0,
                    "total": 3, "approval_rate": 0.667, "misapproval_warning": False}
        stability = STABILITY_STABLE
        return counts, trend, failsafe, hitl, stability

    def test_review_record_written_to_log(self, review, tmp_path, sample_args):
        log = tmp_path / "summary.log"
        review.write_review_record(*sample_args, log_path=log)
        assert log.exists() and len(log.read_text(encoding="utf-8")) > 0

    def test_review_record_has_wp9130_header(self, review, tmp_path, sample_args):
        log = tmp_path / "summary.log"
        review.write_review_record(*sample_args, log_path=log)
        assert "WP9130 ログ確認記録" in log.read_text(encoding="utf-8")

    def test_review_record_has_stability(self, review, tmp_path, sample_args):
        log = tmp_path / "summary.log"
        review.write_review_record(*sample_args, log_path=log)
        assert STABILITY_STABLE in log.read_text(encoding="utf-8")

    def test_review_record_has_hitl_approval_rate(self, review, tmp_path, sample_args):
        log = tmp_path / "summary.log"
        review.write_review_record(*sample_args, log_path=log)
        assert "HITL承認率" in log.read_text(encoding="utf-8")

    def test_review_record_has_phase5_ready_flag(self, review, tmp_path, sample_args):
        log = tmp_path / "summary.log"
        review.write_review_record(*sample_args, log_path=log)
        assert "READY" in log.read_text(encoding="utf-8")
