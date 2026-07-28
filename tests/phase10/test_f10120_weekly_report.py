"""
tests/phase10/test_f10120_weekly_report.py

F10120 weekly_stability_report_generation のテストスイート。
外部システムは呼ばない（daily_logs / repro_test_fn を mock で使用）。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.phase10.f10120_weekly_report import (
    DAYS_IN_WEEK,
    EXCEPTION_LOG,
    HITL_LOG_PATH,
    HITL_POINT_ID,
    OPT_SUMMARY_PATH,
    PHASE10_DIR,
    REPRODUCIBILITY_THRESHOLD,
    WEEKLY_REPORT_PATH,
    WEEKLY_STABILITY_THRESHOLD,
    F10120WeeklyReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("src.phase10.f10120_weekly_report.PHASE10_DIR",        tmp_path)
    monkeypatch.setattr("src.phase10.f10120_weekly_report.WEEKLY_REPORT_PATH", tmp_path / "weekly_stability_report.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.OPT_SUMMARY_PATH",   tmp_path / "optimization_summary.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.HITL_LOG_PATH",      tmp_path / "hitl_weekly_approval_log.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.EXCEPTION_LOG",      tmp_path / "exception_log.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.DAILY_LOG_PATH",     tmp_path / "daily_operation_log.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.STABILITY_PATH",     tmp_path / "stability_report.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.AUTH_REPORT",        tmp_path / "api_auth_report.json")
    monkeypatch.setattr("src.phase10.f10120_weekly_report.SUMMARY_LOG",        tmp_path / "summary.log")
    yield tmp_path


def _make_daily_log(stability_index: float = 0.97, error_count: int = 0,
                     api_auth: str = "authenticated") -> dict:
    return {
        "stability_index": stability_index,
        "metrics": {
            "uptime_rate": 1.0,
            "error_rate": 0.0,
            "avg_latency": 0.4,
        },
        "system_status": {"error_count": error_count},
        "safety": {"api_auth_status": api_auth},
    }


def _seven_ok_logs() -> list[dict]:
    return [_make_daily_log() for _ in range(7)]


def _logs_with_errors() -> list[dict]:
    logs = [_make_daily_log() for _ in range(6)]
    logs.append(_make_daily_log(error_count=2))
    return logs


def _logs_low_stability() -> list[dict]:
    return [_make_daily_log(stability_index=0.80) for _ in range(7)]


def _logs_unauth() -> list[dict]:
    return [_make_daily_log(api_auth="unknown") for _ in range(7)]


def make_reporter() -> F10120WeeklyReport:
    return F10120WeeklyReport()


# ---------------------------------------------------------------------------
# 1. step1_aggregate_daily_logs
# ---------------------------------------------------------------------------

class TestStep1AggregateDailyLogs:
    def test_seven_logs_aggregated(self):
        r = make_reporter()
        logs, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        assert agg["days_count"] == 7

    def test_truncates_to_seven(self):
        r = make_reporter()
        logs, agg = r.step1_aggregate_daily_logs([_make_daily_log()] * 10)
        assert agg["days_count"] == 7

    def test_empty_logs_gives_defaults(self):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs([])
        assert agg["days_count"] == 0
        assert agg["total_error_count"] == 0

    def test_error_count_summed(self):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_logs_with_errors())
        assert agg["total_error_count"] == 2

    def test_stability_indices_collected(self):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        assert len(agg["stability_indices"]) == 7

    def test_reads_daily_log_file_when_no_arg(self, patch_paths):
        daily_path = patch_paths / "daily_operation_log.json"
        daily_path.write_text(
            json.dumps(_make_daily_log(stability_index=0.95)), encoding="utf-8"
        )
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(None)
        assert agg["days_count"] == 1
        assert agg["stability_indices"] == [0.95]

    def test_no_file_no_arg_gives_empty(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(None)
        assert agg["days_count"] == 0


# ---------------------------------------------------------------------------
# 2. step2_calculate_weekly_stability
# ---------------------------------------------------------------------------

class TestStep2CalculateWeeklyStability:
    def test_average_of_indices(self):
        r = make_reporter()
        logs, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        idx = r.step2_calculate_weekly_stability(logs, agg)
        assert abs(idx - 0.97) < 0.001

    def test_low_stability_below_threshold(self):
        r = make_reporter()
        logs, agg = r.step1_aggregate_daily_logs(_logs_low_stability())
        idx = r.step2_calculate_weekly_stability(logs, agg)
        assert idx < WEEKLY_STABILITY_THRESHOLD

    def test_clamped_0_to_1(self):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs([])
        idx = r.step2_calculate_weekly_stability([], agg)
        assert 0.0 <= idx <= 1.0

    def test_threshold_value(self):
        assert WEEKLY_STABILITY_THRESHOLD == 0.92

    def test_logged_with_ok_flag(self):
        r = make_reporter()
        logs, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        r.step2_calculate_weekly_stability(logs, agg)
        entry = next(e for e in r._log if e["step"] == "step2_calculate_weekly_stability")
        assert "ok" in entry


# ---------------------------------------------------------------------------
# 3. step3_reproducibility_test
# ---------------------------------------------------------------------------

class TestStep3ReproducibilityTest:
    def test_fn_result_used(self):
        r = make_reporter()
        assert r.step3_reproducibility_test(lambda: 0.97) == 0.97

    def test_none_fn_returns_1(self):
        r = make_reporter()
        assert r.step3_reproducibility_test(None) == 1.0

    def test_below_threshold_detected(self):
        r = make_reporter()
        rate = r.step3_reproducibility_test(lambda: 0.80)
        assert rate < REPRODUCIBILITY_THRESHOLD

    def test_logged(self):
        r = make_reporter()
        r.step3_reproducibility_test(lambda: 1.0)
        assert any(e["step"] == "step3_reproducibility_test" for e in r._log)


# ---------------------------------------------------------------------------
# 4. step4_safety_check
# ---------------------------------------------------------------------------

class TestStep4SafetyCheck:
    def test_authenticated_is_safe(self):
        r = make_reporter()
        ok, status = r.step4_safety_check(_seven_ok_logs())
        assert ok is True
        assert status == "authenticated"

    def test_unknown_auth_is_unsafe(self):
        r = make_reporter()
        ok, status = r.step4_safety_check(_logs_unauth())
        assert ok is False

    def test_empty_logs_falls_back_to_auth_report(self, patch_paths):
        auth_path = patch_paths / "api_auth_report.json"
        auth_path.write_text(
            json.dumps({"result": {"auth_status": "authenticated"}}), encoding="utf-8"
        )
        r = make_reporter()
        ok, status = r.step4_safety_check([])
        assert ok is True
        assert status == "authenticated"

    def test_empty_logs_no_report_gives_unknown(self):
        r = make_reporter()
        ok, status = r.step4_safety_check([])
        assert ok is False
        assert status == "unknown"

    def test_uses_last_log_for_auth_status(self):
        logs = [_make_daily_log(api_auth="unknown")] * 6
        logs.append(_make_daily_log(api_auth="authenticated"))
        r = make_reporter()
        ok, status = r.step4_safety_check(logs)
        assert status == "authenticated"
        assert ok is True


# ---------------------------------------------------------------------------
# 5. step5_generate_weekly_report
# ---------------------------------------------------------------------------

class TestStep5GenerateWeeklyReport:
    def _run_step5(self, r: F10120WeeklyReport) -> dict:
        logs = _seven_ok_logs()
        _, agg = r.step1_aggregate_daily_logs(logs)
        idx = r.step2_calculate_weekly_stability(logs, agg)
        return r.step5_generate_weekly_report(logs, agg, idx, 1.0, "authenticated")

    def test_file_created(self, patch_paths):
        r = make_reporter()
        self._run_step5(r)
        assert (patch_paths / "weekly_stability_report.json").exists()

    def test_module_field(self, patch_paths):
        r = make_reporter()
        self._run_step5(r)
        data = json.loads((patch_paths / "weekly_stability_report.json").read_text(encoding="utf-8"))
        assert data["module"] == "F10120"

    def test_weekly_index_in_report(self, patch_paths):
        r = make_reporter()
        self._run_step5(r)
        data = json.loads((patch_paths / "weekly_stability_report.json").read_text(encoding="utf-8"))
        assert "weekly_stability_index" in data

    def test_hitl_point_in_report(self, patch_paths):
        r = make_reporter()
        self._run_step5(r)
        data = json.loads((patch_paths / "weekly_stability_report.json").read_text(encoding="utf-8"))
        assert data["hitl_point"] == "H-P10-005"

    def test_period_days_recorded(self, patch_paths):
        r = make_reporter()
        self._run_step5(r)
        data = json.loads((patch_paths / "weekly_stability_report.json").read_text(encoding="utf-8"))
        assert data["period_days"] == 7


# ---------------------------------------------------------------------------
# 6. step6_generate_optimization_summary
# ---------------------------------------------------------------------------

class TestStep6GenerateOptimizationSummary:
    def test_file_created(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        r.step6_generate_optimization_summary(agg, 0.97, 1.0)
        assert (patch_paths / "optimization_summary.json").exists()

    def test_stable_system_no_action(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        summary = r.step6_generate_optimization_summary(agg, 0.97, 1.0)
        assert "no_action_required_system_stable" in summary["proposals"]

    def test_low_stability_triggers_proposal(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_logs_low_stability())
        summary = r.step6_generate_optimization_summary(agg, 0.80, 1.0)
        assert "stability_threshold_adjustment_required" in summary["proposals"]

    def test_low_repro_triggers_proposal(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        summary = r.step6_generate_optimization_summary(agg, 0.97, 0.80)
        assert "reproducibility_improvement_required" in summary["proposals"]

    def test_relearning_candidate_true_when_low_stability(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_logs_low_stability())
        summary = r.step6_generate_optimization_summary(agg, 0.80, 1.0)
        assert summary["relearning_candidate"] is True

    def test_next_module_is_f10130(self, patch_paths):
        r = make_reporter()
        _, agg = r.step1_aggregate_daily_logs(_seven_ok_logs())
        summary = r.step6_generate_optimization_summary(agg, 0.97, 1.0)
        assert summary["next_module"] == "F10130"


# ---------------------------------------------------------------------------
# 7. step7_set_hitl_checkpoint
# ---------------------------------------------------------------------------

class TestStep7SetHitlCheckpoint:
    def _dummy_report(self) -> dict:
        return {"module": "F10120", "weekly_stability_index": 0.97}

    def test_approve_decision(self, patch_paths):
        r = make_reporter()
        dec = r.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.97, 1.0)
        assert dec == "approve"

    def test_reject_decision(self, patch_paths):
        r = make_reporter()
        dec = r.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "reject", 0.97, 1.0)
        assert dec == "reject"

    def test_hitl_log_file_created(self, patch_paths):
        r = make_reporter()
        r.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.97, 1.0)
        assert (patch_paths / "hitl_weekly_approval_log.json").exists()

    def test_hitl_log_point_id(self, patch_paths):
        r = make_reporter()
        r.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.97, 1.0)
        data = json.loads((patch_paths / "hitl_weekly_approval_log.json").read_text(encoding="utf-8"))
        assert data["hitl_point_id"] == "H-P10-005"

    def test_stage_after_approve(self, patch_paths):
        r = make_reporter()
        r.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.97, 1.0)
        data = json.loads((patch_paths / "hitl_weekly_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "weekly_stability_verified"

    def test_stage_after_reject(self, patch_paths):
        r = make_reporter()
        r.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "reject", 0.97, 1.0)
        data = json.loads((patch_paths / "hitl_weekly_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "hitl_rejected"

    def test_no_hitl_fn_defaults_approve(self, patch_paths):
        r = make_reporter()
        dec = r.step7_set_hitl_checkpoint(self._dummy_report(), None, 0.97, 1.0)
        assert dec == "approve"


# ---------------------------------------------------------------------------
# 8. Full run — success path
# ---------------------------------------------------------------------------

class TestRunSuccessPath:
    def test_success_result(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["success"] is True

    def test_phase10_stage(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["phase10_stage"] == "weekly_stability_verified"

    def test_weekly_stability_ok(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["weekly_stability_ok"] is True

    def test_days_aggregated(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["days_aggregated"] == 7

    def test_output_files_created(self, patch_paths):
        r = make_reporter()
        r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert (patch_paths / "weekly_stability_report.json").exists()
        assert (patch_paths / "optimization_summary.json").exists()
        assert (patch_paths / "hitl_weekly_approval_log.json").exists()

    def test_hitl_decision_approve(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["hitl_decision"] == "approve"


# ---------------------------------------------------------------------------
# 9. Run — error_count > 0
# ---------------------------------------------------------------------------

class TestRunErrorCountPath:
    def test_failure_on_errors(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_logs_with_errors(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["success"] is False

    def test_reason_error_count(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_logs_with_errors(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["reason"] == "error_count > 0"

    def test_exception_log_created(self, patch_paths):
        r = make_reporter()
        r.run(daily_logs=_logs_with_errors(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert (patch_paths / "exception_log.json").exists()


# ---------------------------------------------------------------------------
# 10. Run — api_auth not authenticated
# ---------------------------------------------------------------------------

class TestRunUnauthPath:
    def test_failure_on_unauth(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_logs_unauth(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["success"] is False

    def test_reason_unauth(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_logs_unauth(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["reason"] == "api_auth_status_not_authenticated"


# ---------------------------------------------------------------------------
# 11. Run — low reproducibility
# ---------------------------------------------------------------------------

class TestRunLowReproPath:
    def test_failure_low_repro(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 0.80, hitl_fn=lambda _: "approve")
        assert result["success"] is False

    def test_reason_repro_low(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 0.80, hitl_fn=lambda _: "approve")
        assert result["reason"] == "reproducibility_rate_low"


# ---------------------------------------------------------------------------
# 12. Run — HITL reject
# ---------------------------------------------------------------------------

class TestRunHitlRejectPath:
    def test_failure_on_reject(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "reject")
        assert result["success"] is False

    def test_reason_hitl_rejected(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "reject")
        assert result["reason"] == "hitl_rejected"

    def test_phase10_stage_failed(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_seven_ok_logs(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "reject")
        assert result["phase10_stage"] == "weekly_stability_failed"


# ---------------------------------------------------------------------------
# 13. Run — low stability (continues to HITL)
# ---------------------------------------------------------------------------

class TestRunLowStabilityPath:
    def test_low_stability_reaches_hitl(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_logs_low_stability(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["hitl_decision"] == "approve"

    def test_weekly_stability_ok_false(self, patch_paths):
        r = make_reporter()
        result = r.run(daily_logs=_logs_low_stability(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        assert result["weekly_stability_ok"] is False

    def test_optimization_proposal_generated(self, patch_paths):
        r = make_reporter()
        r.run(daily_logs=_logs_low_stability(), repro_test_fn=lambda: 1.0, hitl_fn=lambda _: "approve")
        data = json.loads((patch_paths / "optimization_summary.json").read_text(encoding="utf-8"))
        assert "stability_threshold_adjustment_required" in data["proposals"]


# ---------------------------------------------------------------------------
# 14. write_summary_entry
# ---------------------------------------------------------------------------

class TestWriteSummaryEntry:
    def test_pass_tag(self, patch_paths):
        r = make_reporter()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10120_weekly_report.SUMMARY_LOG", log_path):
            r.write_summary_entry({"success": True, "phase10_stage": "weekly_stability_verified",
                                   "weekly_stability_index": 0.97, "reproducibility_rate": 1.0,
                                   "hitl_decision": "approve"})
        assert "[PASS]" in log_path.read_text(encoding="utf-8")

    def test_fail_tag(self, patch_paths):
        r = make_reporter()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10120_weekly_report.SUMMARY_LOG", log_path):
            r.write_summary_entry({"success": False, "phase10_stage": "weekly_stability_failed",
                                   "weekly_stability_index": 0.80, "reproducibility_rate": 1.0,
                                   "hitl_decision": None})
        assert "[FAIL]" in log_path.read_text(encoding="utf-8")

    def test_f10120_tag(self, patch_paths):
        r = make_reporter()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10120_weekly_report.SUMMARY_LOG", log_path):
            r.write_summary_entry({"success": True, "phase10_stage": "weekly_stability_verified",
                                   "weekly_stability_index": 0.97, "reproducibility_rate": 1.0,
                                   "hitl_decision": "approve"})
        assert "[F10120]" in log_path.read_text(encoding="utf-8")

    def test_appends(self, patch_paths):
        r = make_reporter()
        log_path = patch_paths / "summary.log"
        log_path.write_text("existing\n", encoding="utf-8")
        with patch("src.phase10.f10120_weekly_report.SUMMARY_LOG", log_path):
            r.write_summary_entry({"success": True, "phase10_stage": "weekly_stability_verified",
                                   "weekly_stability_index": 0.97, "reproducibility_rate": 1.0,
                                   "hitl_decision": "approve"})
        content = log_path.read_text(encoding="utf-8")
        assert "existing" in content
        assert "[PASS]" in content
