"""
tests/phase10/test_f10140_exception_rollback.py

F10140 exception_detection_and_rollback_control のテストスイート。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.phase10.f10140_exception_rollback import (
    CRITICAL_ALERT,
    DETECTION_REPORT,
    ERROR_COUNT_CRITICAL,
    EXCEPTION_LOG,
    HITL_LOG_PATH,
    HITL_POINT_ID,
    LATENCY_SPIKE_THRESHOLD,
    PHASE10_DIR,
    ROLLBACK_LOG,
    SAFETY_REAPPROVAL,
    STABILITY_DROP_THRESHOLD,
    VALIDATION_ERR,
    F10140ExceptionRollback,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.PHASE10_DIR",        tmp_path)
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.DETECTION_REPORT",   tmp_path / "exception_detection_report.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.ROLLBACK_LOG",       tmp_path / "rollback_action_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.SAFETY_REAPPROVAL",  tmp_path / "safety_reapproval_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.HITL_LOG_PATH",      tmp_path / "hitl_safety_approval_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.EXCEPTION_LOG",      tmp_path / "exception_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.CRITICAL_ALERT",     tmp_path / "critical_alert_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.VALIDATION_ERR",     tmp_path / "validation_error.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.DAILY_LOG",          tmp_path / "daily_operation_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.WEEKLY_REPORT",      tmp_path / "weekly_stability_report.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.CYCLE_LOG",          tmp_path / "optimization_cycle_log.json")
    monkeypatch.setattr("src.phase10.f10140_exception_rollback.SUMMARY_LOG",        tmp_path / "summary.log")
    yield tmp_path


def _clean_daily_log(error_count: int = 0, avg_latency: float = 0.4) -> dict:
    return {
        "system_status": {"error_count": error_count},
        "metrics":       {"uptime_rate": 1.0, "error_rate": 0.0, "avg_latency": avg_latency},
        "previous_anomalies": [],
    }


def _clean_weekly_report(weekly_index: float = 0.97) -> dict:
    return {
        "weekly_stability_index": weekly_index,
        "weekly_stability_ok":    weekly_index >= 0.92,
    }


def _clean_cycle_log() -> dict:
    return {
        "optimization_cycle_completed": True,
        "retraining":                   {"triggered": 0, "triggers": []},
        "threshold_adjustment":         {"changes": [], "valid": True},
    }


def _cycle_log_with_retrain() -> dict:
    return {
        "optimization_cycle_completed": True,
        "retraining":                   {"triggered": 1, "triggers": ["stability_critical"]},
        "threshold_adjustment":         {"changes": ["latency_limit: 2.0 -> 2.5"], "valid": True},
    }


def make_er() -> F10140ExceptionRollback:
    return F10140ExceptionRollback()


# ---------------------------------------------------------------------------
# 1. step1_detect_anomalies
# ---------------------------------------------------------------------------

class TestStep1DetectAnomalies:
    def test_no_anomalies_when_clean(self):
        er = make_er()
        anomalies = er.step1_detect_anomalies(_clean_daily_log(), _clean_weekly_report())
        assert anomalies == []

    def test_error_count_nonzero_detected(self):
        er = make_er()
        anomalies = er.step1_detect_anomalies(_clean_daily_log(error_count=1), _clean_weekly_report())
        assert "error_count_nonzero" in anomalies

    def test_error_count_critical_detected(self):
        er = make_er()
        anomalies = er.step1_detect_anomalies(
            _clean_daily_log(error_count=ERROR_COUNT_CRITICAL), _clean_weekly_report()
        )
        assert "error_count_critical" in anomalies

    def test_latency_spike_detected(self):
        er = make_er()
        anomalies = er.step1_detect_anomalies(
            _clean_daily_log(avg_latency=LATENCY_SPIKE_THRESHOLD + 0.5), _clean_weekly_report()
        )
        assert "latency_spike" in anomalies

    def test_stability_drop_detected(self):
        er = make_er()
        anomalies = er.step1_detect_anomalies(
            _clean_daily_log(), _clean_weekly_report(weekly_index=0.80)
        )
        assert "stability_drop" in anomalies

    def test_inherited_anomalies_from_prev(self):
        daily = {**_clean_daily_log(), "previous_anomalies": ["stability_index_below_threshold"]}
        er = make_er()
        anomalies = er.step1_detect_anomalies(daily, _clean_weekly_report())
        assert any("inherited" in a for a in anomalies)

    def test_reads_files_when_no_args(self, patch_paths):
        (patch_paths / "daily_operation_log.json").write_text(
            json.dumps(_clean_daily_log()), encoding="utf-8"
        )
        (patch_paths / "weekly_stability_report.json").write_text(
            json.dumps(_clean_weekly_report()), encoding="utf-8"
        )
        er = make_er()
        anomalies = er.step1_detect_anomalies(None, None)
        assert anomalies == []

    def test_thresholds(self):
        assert LATENCY_SPIKE_THRESHOLD == 2.0
        assert STABILITY_DROP_THRESHOLD == 0.90
        assert ERROR_COUNT_CRITICAL == 3


# ---------------------------------------------------------------------------
# 2. step2_check_post_optimization
# ---------------------------------------------------------------------------

class TestStep2CheckPostOptimization:
    def test_no_exceptions_when_clean_cycle(self):
        er = make_er()
        post = er.step2_check_post_optimization(_clean_cycle_log())
        assert post == []

    def test_retrain_trigger_detected(self):
        er = make_er()
        post = er.step2_check_post_optimization(_cycle_log_with_retrain())
        assert "retraining_triggered_post_optimization" in post

    def test_threshold_change_detected(self):
        er = make_er()
        post = er.step2_check_post_optimization(_cycle_log_with_retrain())
        assert "threshold_changed_post_optimization" in post

    def test_no_cycle_log_returns_empty(self, patch_paths):
        er = make_er()
        post = er.step2_check_post_optimization(None)
        assert post == []

    def test_reads_cycle_log_file(self, patch_paths):
        (patch_paths / "optimization_cycle_log.json").write_text(
            json.dumps(_cycle_log_with_retrain()), encoding="utf-8"
        )
        er = make_er()
        post = er.step2_check_post_optimization(None)
        assert "retraining_triggered_post_optimization" in post


# ---------------------------------------------------------------------------
# 3. step3_classify_exception_patterns
# ---------------------------------------------------------------------------

class TestStep3ClassifyExceptionPatterns:
    def test_empty_history_returns_no_patterns(self):
        er = make_er()
        patterns = er.step3_classify_exception_patterns([])
        assert patterns == []

    def test_single_exception_classified(self):
        er = make_er()
        patterns = er.step3_classify_exception_patterns([{"error": "api_timeout"}])
        assert len(patterns) == 1
        assert patterns[0]["type"] == "api_timeout"
        assert patterns[0]["frequency"] == 1

    def test_frequency_counted(self):
        er = make_er()
        history = [{"error": "api_timeout"}] * 3
        patterns = er.step3_classify_exception_patterns(history)
        assert patterns[0]["frequency"] == 3

    def test_critical_impact_when_high_frequency(self):
        er = make_er()
        history = [{"error": "auth_failure"}] * ERROR_COUNT_CRITICAL
        patterns = er.step3_classify_exception_patterns(history)
        assert patterns[0]["impact"] == "critical"

    def test_warning_impact_when_low_frequency(self):
        er = make_er()
        patterns = er.step3_classify_exception_patterns([{"error": "latency_high"}])
        assert patterns[0]["impact"] == "warning"

    def test_reads_exception_log_file(self, patch_paths):
        (patch_paths / "exception_log.json").write_text(
            json.dumps({"error": "test_error", "type": "test"}), encoding="utf-8"
        )
        er = make_er()
        patterns = er.step3_classify_exception_patterns(None)
        assert len(patterns) == 1


# ---------------------------------------------------------------------------
# 4. step4_select_rollback_strategy
# ---------------------------------------------------------------------------

class TestStep4SelectRollbackStrategy:
    def test_no_strategy_when_no_anomalies(self):
        er = make_er()
        strategy, required = er.step4_select_rollback_strategy([], [], [])
        assert strategy == "none"
        assert required is False

    def test_full_strategy_for_critical_errors(self):
        er = make_er()
        strategy, required = er.step4_select_rollback_strategy(
            ["error_count_critical"], [], []
        )
        assert strategy == "full"
        assert required is True

    def test_full_strategy_for_stability_drop(self):
        er = make_er()
        strategy, required = er.step4_select_rollback_strategy(
            ["stability_drop"], [], []
        )
        assert strategy == "full"

    def test_config_restore_for_threshold_change(self):
        er = make_er()
        strategy, required = er.step4_select_rollback_strategy(
            [], ["threshold_changed_post_optimization"], []
        )
        assert strategy == "config_restore"

    def test_partial_strategy_for_minor_anomalies(self):
        er = make_er()
        strategy, required = er.step4_select_rollback_strategy(
            ["latency_spike"], [], []
        )
        assert strategy == "partial"

    def test_partial_strategy_for_post_opt_retrain(self):
        er = make_er()
        strategy, required = er.step4_select_rollback_strategy(
            [], ["retraining_triggered_post_optimization"], []
        )
        assert strategy == "partial"


# ---------------------------------------------------------------------------
# 5. step5_execute_rollback
# ---------------------------------------------------------------------------

class TestStep5ExecuteRollback:
    def test_no_rollback_when_not_required(self):
        er = make_er()
        result = er.step5_execute_rollback("none", False)
        assert result["executed"] is False
        assert result["success"] is True
        assert result["last_stable_state_restored"] is True

    def test_rollback_executed_when_required(self):
        er = make_er()
        result = er.step5_execute_rollback("partial", True)
        assert result["executed"] is True
        assert result["success"] is True

    def test_full_rollback_executed(self):
        er = make_er()
        result = er.step5_execute_rollback("full", True)
        assert result["strategy"] == "full"
        assert result["success"] is True

    def test_config_restore_executed(self):
        er = make_er()
        result = er.step5_execute_rollback("config_restore", True)
        assert result["strategy"] == "config_restore"

    def test_zero_errors_after_rollback(self):
        er = make_er()
        result = er.step5_execute_rollback("partial", True)
        assert result["error_count_after_rollback"] == 0

    def test_last_stable_state_restored(self):
        er = make_er()
        result = er.step5_execute_rollback("full", True)
        assert result["last_stable_state_restored"] is True


# ---------------------------------------------------------------------------
# 6. step6_generate_reports
# ---------------------------------------------------------------------------

class TestStep6GenerateReports:
    def _run_to_step5(self, er: F10140ExceptionRollback):
        anomalies = er.step1_detect_anomalies(_clean_daily_log(), _clean_weekly_report())
        post = er.step2_check_post_optimization(_clean_cycle_log())
        patterns = er.step3_classify_exception_patterns([])
        strategy, required = er.step4_select_rollback_strategy(anomalies, post, patterns)
        rollback = er.step5_execute_rollback(strategy, required)
        return anomalies, post, patterns, strategy, rollback

    def test_detection_report_created(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        assert (patch_paths / "exception_detection_report.json").exists()

    def test_rollback_log_created(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        assert (patch_paths / "rollback_action_log.json").exists()

    def test_safety_reapproval_log_created(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        assert (patch_paths / "safety_reapproval_log.json").exists()

    def test_module_field_in_detection_report(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        data = json.loads((patch_paths / "exception_detection_report.json").read_text(encoding="utf-8"))
        assert data["module"] == "F10140"

    def test_detection_completed_flag(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        data = json.loads((patch_paths / "exception_detection_report.json").read_text(encoding="utf-8"))
        assert data["exception_detection_completed"] is True

    def test_hitl_point_in_report(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        data = json.loads((patch_paths / "exception_detection_report.json").read_text(encoding="utf-8"))
        assert data["hitl_point"] == "H-P10-003"

    def test_safety_status_safe(self, patch_paths):
        er = make_er()
        args = self._run_to_step5(er)
        er.step6_generate_reports(*args)
        data = json.loads((patch_paths / "safety_reapproval_log.json").read_text(encoding="utf-8"))
        assert data["safety_status"] == "safe"


# ---------------------------------------------------------------------------
# 7. step7_set_hitl_checkpoint
# ---------------------------------------------------------------------------

class TestStep7SetHitlCheckpoint:
    def _dummy_report(self) -> dict:
        return {"module": "F10140", "anomalies_detected": []}

    def _dummy_rollback(self) -> dict:
        return {"executed": False, "strategy": "none", "success": True,
                "last_stable_state_restored": True, "error_count_after_rollback": 0}

    def test_approve_decision(self, patch_paths):
        er = make_er()
        dec = er.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", self._dummy_rollback())
        assert dec == "approve"

    def test_reject_decision(self, patch_paths):
        er = make_er()
        dec = er.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "reject", self._dummy_rollback())
        assert dec == "reject"

    def test_hitl_log_created(self, patch_paths):
        er = make_er()
        er.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", self._dummy_rollback())
        assert (patch_paths / "hitl_safety_approval_log.json").exists()

    def test_hitl_point_id_in_log(self, patch_paths):
        er = make_er()
        er.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", self._dummy_rollback())
        data = json.loads((patch_paths / "hitl_safety_approval_log.json").read_text(encoding="utf-8"))
        assert data["hitl_point_id"] == "H-P10-003"

    def test_stage_after_approve(self, patch_paths):
        er = make_er()
        er.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", self._dummy_rollback())
        data = json.loads((patch_paths / "hitl_safety_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "safety_reapproved"

    def test_stage_after_reject(self, patch_paths):
        er = make_er()
        er.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "reject", self._dummy_rollback())
        data = json.loads((patch_paths / "hitl_safety_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "hitl_rejected"

    def test_no_fn_defaults_approve(self, patch_paths):
        er = make_er()
        dec = er.step7_set_hitl_checkpoint(self._dummy_report(), None, self._dummy_rollback())
        assert dec == "approve"


# ---------------------------------------------------------------------------
# 8. Full run — clean system (no anomalies)
# ---------------------------------------------------------------------------

class TestRunCleanSystem:
    def test_success(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is True

    def test_phase10_stage_safety_reapproved(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["phase10_stage"] == "safety_reapproved"

    def test_no_rollback_executed(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["rollback_executed"] is False

    def test_all_four_output_files_created(self, patch_paths):
        er = make_er()
        er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert (patch_paths / "exception_detection_report.json").exists()
        assert (patch_paths / "rollback_action_log.json").exists()
        assert (patch_paths / "safety_reapproval_log.json").exists()
        assert (patch_paths / "hitl_safety_approval_log.json").exists()

    def test_zero_anomalies(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["anomalies_count"] == 0

    def test_detection_completed_true(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["exception_detection_completed"] is True


# ---------------------------------------------------------------------------
# 9. Full run — with anomalies (rollback executed)
# ---------------------------------------------------------------------------

class TestRunWithAnomalies:
    def test_rollback_executed_on_latency_spike(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(avg_latency=3.0),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["rollback_executed"] is True
        assert result["success"] is True

    def test_full_rollback_on_critical_errors(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(error_count=ERROR_COUNT_CRITICAL),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["rollback_strategy"] == "full"
        assert result["success"] is True

    def test_config_restore_on_threshold_change(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_cycle_log_with_retrain(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["rollback_strategy"] == "config_restore"

    def test_last_stable_state_restored_after_rollback(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(error_count=1),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        assert result["last_stable_state_restored"] is True


# ---------------------------------------------------------------------------
# 10. Run — HITL reject
# ---------------------------------------------------------------------------

class TestRunHitlRejectPath:
    def test_failure_on_reject(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "reject",
        )
        assert result["success"] is False

    def test_reason_hitl_rejected(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "reject",
        )
        assert result["reason"] == "hitl_rejected"

    def test_stage_failed_on_reject(self, patch_paths):
        er = make_er()
        result = er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "reject",
        )
        assert result["phase10_stage"] == "safety_reapproval_failed"


# ---------------------------------------------------------------------------
# 11. write_summary_entry
# ---------------------------------------------------------------------------

class TestWriteSummaryEntry:
    def test_pass_tag(self, patch_paths):
        er = make_er()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10140_exception_rollback.SUMMARY_LOG", log_path):
            er.write_summary_entry({
                "success": True, "phase10_stage": "safety_reapproved",
                "anomalies_count": 0, "rollback_strategy": "none", "hitl_decision": "approve",
            })
        assert "[PASS]" in log_path.read_text(encoding="utf-8")

    def test_fail_tag(self, patch_paths):
        er = make_er()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10140_exception_rollback.SUMMARY_LOG", log_path):
            er.write_summary_entry({
                "success": False, "phase10_stage": "safety_reapproval_failed",
                "anomalies_count": 2, "rollback_strategy": "full", "hitl_decision": None,
            })
        assert "[FAIL]" in log_path.read_text(encoding="utf-8")

    def test_f10140_tag(self, patch_paths):
        er = make_er()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10140_exception_rollback.SUMMARY_LOG", log_path):
            er.write_summary_entry({
                "success": True, "phase10_stage": "safety_reapproved",
                "anomalies_count": 0, "rollback_strategy": "none", "hitl_decision": "approve",
            })
        assert "[F10140]" in log_path.read_text(encoding="utf-8")

    def test_appends(self, patch_paths):
        er = make_er()
        log_path = patch_paths / "summary.log"
        log_path.write_text("existing\n", encoding="utf-8")
        with patch("src.phase10.f10140_exception_rollback.SUMMARY_LOG", log_path):
            er.write_summary_entry({
                "success": True, "phase10_stage": "safety_reapproved",
                "anomalies_count": 0, "rollback_strategy": "none", "hitl_decision": "approve",
            })
        content = log_path.read_text(encoding="utf-8")
        assert "existing" in content
        assert "[PASS]" in content


# ---------------------------------------------------------------------------
# 12. End-to-end: all output files contain correct fields
# ---------------------------------------------------------------------------

class TestOutputFileContents:
    def test_detection_report_has_anomalies_list(self, patch_paths):
        er = make_er()
        er.run(
            daily_log=_clean_daily_log(avg_latency=3.0),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        data = json.loads((patch_paths / "exception_detection_report.json").read_text(encoding="utf-8"))
        assert "anomalies_detected" in data
        assert "latency_spike" in data["anomalies_detected"]

    def test_rollback_log_has_strategy(self, patch_paths):
        er = make_er()
        er.run(
            daily_log=_clean_daily_log(avg_latency=3.0),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        data = json.loads((patch_paths / "rollback_action_log.json").read_text(encoding="utf-8"))
        assert "strategy" in data
        assert data["strategy"] == "partial"

    def test_safety_log_has_stable_status(self, patch_paths):
        er = make_er()
        er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        data = json.loads((patch_paths / "safety_reapproval_log.json").read_text(encoding="utf-8"))
        assert data["safety_status"] == "safe"
        assert data["error_count_after_rollback"] == 0

    def test_hitl_log_has_correct_trigger(self, patch_paths):
        er = make_er()
        er.run(
            daily_log=_clean_daily_log(),
            weekly_report=_clean_weekly_report(),
            cycle_log=_clean_cycle_log(),
            exception_history=[],
            hitl_fn=lambda _: "approve",
        )
        data = json.loads((patch_paths / "hitl_safety_approval_log.json").read_text(encoding="utf-8"))
        assert data["trigger"] == "異常検知時の判断"
