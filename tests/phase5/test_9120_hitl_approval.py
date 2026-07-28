"""WP9120 HITL承認フローテスト（Human-in-the-Loop Approval Flow Test）
Phase 5：運用層（9000番台）

テスト対象:
  - src/monitoring/hitl_approval.py
    - HITLApprovalFlow.detect_hitl()
    - HITLApprovalFlow.submit_decision()
    - HITLApprovalFlow.get_session_summary()
    - HITLApprovalFlow.write_approval_record()
    - HITLApprovalFlow.reprocess_count()
    - HITLApprovalFlow.over_max_reprocess()
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.monitoring.hitl_approval import HITLApprovalFlow, MAX_REPROCESS
from src.monitoring.hitl_tracker import HITLTracker


# ════════════════════════════════════════════════════════════════════════════
# TestWP9121 — HITL 発動条件の検出
# ════════════════════════════════════════════════════════════════════════════

class TestWP9121_HITLTriggerDetection:

    @pytest.fixture
    def flow(self):
        return HITLApprovalFlow()

    def test_detect_hitl_from_hitl_true(self, flow):
        result = {"hitl": True, "hitl_reason": "曖昧語検出", "goal": None}
        info = flow.detect_hitl("F10", result)
        assert info is not None

    def test_detect_hitl_returns_none_when_no_hitl(self, flow):
        result = {"hitl": False, "hitl_required": False, "goal": "OK"}
        assert flow.detect_hitl("F10", result) is None

    def test_detect_hitl_from_hitl_required(self, flow):
        result = {"hitl": False, "hitl_required": True, "hitl_reason": "タスク空"}
        info = flow.detect_hitl("F40", result)
        assert info is not None

    def test_detect_hitl_has_module_name(self, flow):
        result = {"hitl": True, "hitl_reason": "x"}
        info = flow.detect_hitl("F20", result)
        assert info["module"] == "F20"

    def test_detect_hitl_has_reason(self, flow):
        result = {"hitl": True, "hitl_reason": "曖昧入力:など"}
        info = flow.detect_hitl("F10", result)
        assert info["reason"] == "曖昧入力:など"

    def test_detect_hitl_has_elements(self, flow):
        result = {"hitl": True, "hitl_elements": ["E001", "E002"], "hitl_reason": "x"}
        info = flow.detect_hitl("F80", result)
        assert info["elements"] == ["E001", "E002"]

    def test_detect_hitl_needs_approval_is_true(self, flow):
        result = {"hitl_required": True, "hitl_reason": "空タスク"}
        info = flow.detect_hitl("F40", result)
        assert info["needs_approval"] is True

    def test_detect_hitl_both_false_returns_none(self, flow):
        result = {"hitl": False, "hitl_required": False}
        assert flow.detect_hitl("F60", result) is None

    def test_detect_hitl_empty_result_returns_none(self, flow):
        assert flow.detect_hitl("F10", {}) is None

    def test_detect_hitl_reason_defaults_to_empty_string(self, flow):
        result = {"hitl": True}
        info = flow.detect_hitl("F10", result)
        assert info["reason"] == ""


# ════════════════════════════════════════════════════════════════════════════
# TestWP9122 — 承認フロー実行
# ════════════════════════════════════════════════════════════════════════════

class TestWP9122_ApprovalExecution:

    @pytest.fixture
    def flow(self):
        return HITLApprovalFlow()

    def test_approve_recorded_in_tracker(self, flow):
        flow.submit_decision("F10", "E001", "approve")
        assert flow.tracker.approval_rate() == 1.0

    def test_reject_recorded_in_tracker(self, flow):
        flow.submit_decision("F10", "E001", "reject")
        assert flow.tracker.approval_rate() == 0.0

    def test_reprocess_decision_increments_reprocess_count(self, flow):
        flow.submit_decision("F10", "E001", "reprocess")
        assert flow.reprocess_count("E001") == 1

    def test_session_decisions_has_module(self, flow):
        flow.submit_decision("F20", "E002", "approve")
        assert flow.decisions[0]["module"] == "F20"

    def test_session_decisions_has_element_id(self, flow):
        flow.submit_decision("F30", "ELEM-001", "approve")
        assert flow.decisions[0]["element_id"] == "ELEM-001"

    def test_session_decisions_has_decision(self, flow):
        flow.submit_decision("F40", "E003", "reject")
        assert flow.decisions[0]["decision"] == "reject"

    def test_session_decisions_has_timestamp(self, flow):
        flow.submit_decision("F50", "E004", "approve")
        ts = flow.decisions[0]["timestamp"]
        datetime.fromisoformat(ts)  # パース可能か

    def test_invalid_decision_raises_value_error(self, flow):
        with pytest.raises(ValueError, match="Invalid decision"):
            flow.submit_decision("F10", "E001", "skip")  # type: ignore[arg-type]

    def test_reason_stored_in_decision(self, flow):
        flow.submit_decision("F10", "E001", "approve", reason="内容確認済")
        assert flow.decisions[0]["reason"] == "内容確認済"

    def test_multiple_decisions_accumulated(self, flow):
        flow.submit_decision("F10", "E001", "approve")
        flow.submit_decision("F20", "E002", "approve")
        flow.submit_decision("F30", "E003", "reject")
        assert len(flow.decisions) == 3


# ════════════════════════════════════════════════════════════════════════════
# TestWP9123 — 承認履歴・セッションサマリー
# ════════════════════════════════════════════════════════════════════════════

class TestWP9123_ApprovalHistory:

    @pytest.fixture
    def flow_with_decisions(self):
        flow = HITLApprovalFlow()
        flow.submit_decision("F10", "E001", "approve")
        flow.submit_decision("F20", "E002", "approve")
        flow.submit_decision("F30", "E003", "reject")
        flow.submit_decision("F40", "E004", "reprocess")
        return flow

    def test_session_summary_has_total(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert s["total"] == 4

    def test_session_summary_has_counts(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert "counts" in s

    def test_session_summary_approve_count_correct(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert s["counts"]["approve"] == 2

    def test_session_summary_reject_count_correct(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert s["counts"]["reject"] == 1

    def test_session_summary_reprocess_count_correct(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert s["counts"]["reprocess"] == 1

    def test_session_summary_has_approval_rate(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert "approval_rate" in s
        assert isinstance(s["approval_rate"], float)

    def test_session_summary_has_misapproval_warning(self, flow_with_decisions):
        s = flow_with_decisions.get_session_summary()
        assert "misapproval_warning" in s

    def test_session_summary_zero_on_empty_flow(self):
        flow = HITLApprovalFlow()
        s = flow.get_session_summary()
        assert s["total"] == 0
        assert s["approval_rate"] == 0.0


# ════════════════════════════════════════════════════════════════════════════
# TestWP9124 — summary.log への出力
# ════════════════════════════════════════════════════════════════════════════

class TestWP9124_SummaryLogOutput:

    @pytest.fixture
    def flow_with_log(self, tmp_path):
        log = tmp_path / "summary.log"
        flow = HITLApprovalFlow(summary_log=log)
        flow.submit_decision("F10", "E001", "approve", reason="確認済")
        flow.submit_decision("F20", "E002", "reject", reason="不適切")
        return flow, log

    def test_approval_record_written_to_log(self, flow_with_log):
        flow, log = flow_with_log
        flow.write_approval_record()
        assert log.exists() and len(log.read_text(encoding="utf-8")) > 0

    def test_approval_record_has_wp9120_header(self, flow_with_log):
        flow, log = flow_with_log
        flow.write_approval_record()
        assert "WP9120 HITL承認記録" in log.read_text(encoding="utf-8")

    def test_approval_record_has_module_counts(self, flow_with_log):
        flow, log = flow_with_log
        flow.write_approval_record()
        content = log.read_text(encoding="utf-8")
        assert "承認" in content
        assert "却下" in content

    def test_approval_record_has_approval_rate(self, flow_with_log):
        flow, log = flow_with_log
        flow.write_approval_record()
        assert "承認率" in log.read_text(encoding="utf-8")

    def test_approval_record_has_phase5_flag(self, flow_with_log):
        flow, log = flow_with_log
        flow.write_approval_record()
        assert "READY" in log.read_text(encoding="utf-8")

    def test_approval_record_custom_log_path(self, tmp_path):
        other_log = tmp_path / "other.log"
        flow = HITLApprovalFlow()
        flow.submit_decision("F10", "E001", "approve")
        flow.write_approval_record(log_path=other_log)
        assert other_log.exists()


# ════════════════════════════════════════════════════════════════════════════
# TestWP9125 — 誤承認検知（承認率異常）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9125_MisapprovalDetection:

    def test_no_warning_below_90_percent(self):
        flow = HITLApprovalFlow()
        for i in range(8):
            flow.submit_decision("F10", f"E{i:03}", "approve")
        flow.submit_decision("F10", "E009", "reject")
        flow.submit_decision("F10", "E010", "reject")
        s = flow.get_session_summary()
        assert s["misapproval_warning"] is False

    def test_warning_when_approval_rate_over_90(self):
        flow = HITLApprovalFlow()
        for i in range(10):
            flow.submit_decision("F10", f"E{i:03}", "approve")
        flow.submit_decision("F10", "E010", "reject")
        s = flow.get_session_summary()
        assert s["misapproval_warning"] is True

    def test_all_approve_triggers_misapproval_warning(self):
        flow = HITLApprovalFlow()
        for i in range(5):
            flow.submit_decision("F10", f"E{i:03}", "approve")
        s = flow.get_session_summary()
        assert s["misapproval_warning"] is True

    def test_half_approve_no_warning(self):
        flow = HITLApprovalFlow()
        flow.submit_decision("F10", "E001", "approve")
        flow.submit_decision("F10", "E002", "reject")
        s = flow.get_session_summary()
        assert s["misapproval_warning"] is False

    def test_misapproval_flag_shown_in_log(self, tmp_path):
        log = tmp_path / "summary.log"
        flow = HITLApprovalFlow(summary_log=log)
        for i in range(5):
            flow.submit_decision("F10", f"E{i:03}", "approve")
        flow.write_approval_record()
        assert "誤承認検知" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# TestWP9126 — フェイルセーフ：却下・再処理上限
# ════════════════════════════════════════════════════════════════════════════

class TestWP9126_FailsafeOnReject:

    def test_reject_reason_stored(self):
        flow = HITLApprovalFlow()
        flow.submit_decision("F10", "E001", "reject", reason="曖昧語を修正してください")
        assert flow.decisions[0]["reason"] == "曖昧語を修正してください"

    def test_reprocess_increments_count_each_time(self):
        flow = HITLApprovalFlow()
        flow.submit_decision("F10", "E001", "reprocess")
        flow.submit_decision("F10", "E001", "reprocess")
        assert flow.reprocess_count("E001") == 2

    def test_over_max_reprocess_false_within_limit(self):
        flow = HITLApprovalFlow()
        for _ in range(MAX_REPROCESS):
            flow.submit_decision("F10", "E001", "reprocess")
        assert flow.over_max_reprocess("E001") is False

    def test_over_max_reprocess_true_when_exceeded(self):
        flow = HITLApprovalFlow()
        for _ in range(MAX_REPROCESS + 1):
            flow.submit_decision("F10", "E001", "reprocess")
        assert flow.over_max_reprocess("E001") is True

    def test_reprocess_count_independent_per_element(self):
        flow = HITLApprovalFlow()
        flow.submit_decision("F10", "E001", "reprocess")
        flow.submit_decision("F10", "E001", "reprocess")
        flow.submit_decision("F20", "E002", "reprocess")
        assert flow.reprocess_count("E001") == 2
        assert flow.reprocess_count("E002") == 1

    def test_tracker_property_returns_hitl_tracker(self):
        flow = HITLApprovalFlow()
        assert isinstance(flow.tracker, HITLTracker)
