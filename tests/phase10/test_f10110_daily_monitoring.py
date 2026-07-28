"""
tests/phase10/test_f10110_daily_monitoring.py

F10110 daily_operation_monitoring_and_logging のテストスイート。
外部システムは呼ばない（system_status_fn / repro_test_fn を mock で使用）。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.phase10.f10110_daily_monitoring import (
    DAILY_LOG_PATH,
    EXCEPTION_LOG,
    HITL_LOG_PATH,
    HITL_POINT_ID,
    PHASE10_DIR,
    REPRODUCIBILITY_THRESHOLD,
    STABILITY_PATH,
    STABILITY_THRESHOLD,
    F10110DailyMonitoring,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.PHASE10_DIR",    tmp_path)
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.DAILY_LOG_PATH", tmp_path / "daily_operation_log.json")
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.STABILITY_PATH", tmp_path / "stability_report.json")
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.HITL_LOG_PATH",  tmp_path / "hitl_monitoring_approval_log.json")
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.EXCEPTION_LOG",  tmp_path / "exception_log.json")
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.AUTH_REPORT",    tmp_path / "api_auth_report.json")
    monkeypatch.setattr("src.phase10.f10110_daily_monitoring.SUMMARY_LOG",    tmp_path / "summary.log")
    yield tmp_path


def _ok_status() -> dict:
    return {
        "uptime_rate":     1.0,
        "error_rate":      0.0,
        "error_count":     0,
        "avg_latency":     0.4,
        "exception_count": 0,
        "api_auth_status": "authenticated",
    }


def _error_status() -> dict:
    return {
        "uptime_rate":     0.9,
        "error_rate":      0.05,
        "error_count":     2,
        "avg_latency":     1.0,
        "exception_count": 0,
        "api_auth_status": "authenticated",
    }


def _unauth_status() -> dict:
    return {
        "uptime_rate":     1.0,
        "error_rate":      0.0,
        "error_count":     0,
        "avg_latency":     0.4,
        "exception_count": 0,
        "api_auth_status": "unknown",
    }


def _low_stability_status() -> dict:
    return {
        "uptime_rate":     0.5,
        "error_rate":      0.4,
        "error_count":     0,
        "avg_latency":     8.0,
        "exception_count": 0,
        "api_auth_status": "authenticated",
    }


def make_monitor() -> F10110DailyMonitoring:
    return F10110DailyMonitoring()


# ---------------------------------------------------------------------------
# 1. step1_load_previous_logs
# ---------------------------------------------------------------------------

class TestStep1LoadPreviousLogs:
    def test_no_prev_log_returns_empty(self):
        m = make_monitor()
        prev, anomalies = m.step1_load_previous_logs(None)
        assert prev == {}
        assert anomalies == []

    def test_injected_prev_log_used(self):
        m = make_monitor()
        prev_data = {"stability_index": 0.95, "error_count": 0, "hitl_approved": True}
        prev, anomalies = m.step1_load_previous_logs(prev_data)
        assert prev == prev_data

    def test_low_stability_in_prev_creates_anomaly(self):
        m = make_monitor()
        prev_data = {"stability_index": 0.7, "error_count": 0, "hitl_approved": True}
        _, anomalies = m.step1_load_previous_logs(prev_data)
        assert "stability_index_below_threshold" in anomalies

    def test_prev_error_creates_anomaly(self):
        m = make_monitor()
        prev_data = {"stability_index": 0.95, "error_count": 3, "hitl_approved": True}
        _, anomalies = m.step1_load_previous_logs(prev_data)
        assert "previous_error_detected" in anomalies

    def test_prev_hitl_not_approved_creates_anomaly(self):
        m = make_monitor()
        prev_data = {"stability_index": 0.95, "error_count": 0, "hitl_approved": False}
        _, anomalies = m.step1_load_previous_logs(prev_data)
        assert "previous_hitl_not_approved" in anomalies

    def test_reads_existing_daily_log_file(self, patch_paths):
        daily_path = patch_paths / "daily_operation_log.json"
        daily_path.write_text(
            json.dumps({"stability_index": 0.6, "error_count": 0, "hitl_approved": True}),
            encoding="utf-8",
        )
        m = make_monitor()
        prev, anomalies = m.step1_load_previous_logs(None)
        assert prev["stability_index"] == 0.6
        assert "stability_index_below_threshold" in anomalies


# ---------------------------------------------------------------------------
# 2. step2_get_system_status
# ---------------------------------------------------------------------------

class TestStep2GetSystemStatus:
    def test_returns_mock_status(self):
        m = make_monitor()
        status = m.step2_get_system_status(lambda: _ok_status())
        assert status["uptime_rate"] == 1.0
        assert status["error_count"] == 0

    def test_no_fn_returns_default(self):
        m = make_monitor()
        status = m.step2_get_system_status(None)
        assert "uptime_rate" in status
        assert status["error_count"] == 0

    def test_status_logged(self):
        m = make_monitor()
        m.step2_get_system_status(lambda: _ok_status())
        assert any(e["step"] == "step2_get_system_status" for e in m._log)


# ---------------------------------------------------------------------------
# 3. step3_calculate_stability
# ---------------------------------------------------------------------------

class TestStep3CalculateStability:
    def test_perfect_status_high_stability(self):
        m = make_monitor()
        idx, _ = m.step3_calculate_stability(_ok_status())
        assert idx >= STABILITY_THRESHOLD

    def test_low_uptime_lowers_stability(self):
        m = make_monitor()
        status = {"uptime_rate": 0.5, "error_rate": 0.0, "avg_latency": 0.5}
        idx, _ = m.step3_calculate_stability(status)
        assert idx < 1.0

    def test_high_error_rate_lowers_stability(self):
        m = make_monitor()
        status = {"uptime_rate": 1.0, "error_rate": 0.5, "avg_latency": 0.5}
        idx, _ = m.step3_calculate_stability(status)
        assert idx < 1.0

    def test_stability_index_clamped_0_to_1(self):
        m = make_monitor()
        # エラー率 > 1.0 でも 0 以下にならない
        status = {"uptime_rate": 1.0, "error_rate": 2.0, "avg_latency": 0.5}
        idx, _ = m.step3_calculate_stability(status)
        assert 0.0 <= idx <= 1.0

    def test_metrics_contains_stability_ok(self):
        m = make_monitor()
        idx, metrics = m.step3_calculate_stability(_ok_status())
        assert "stability_ok" in metrics
        assert metrics["stability_ok"] == (idx >= STABILITY_THRESHOLD)

    def test_threshold_value(self):
        assert STABILITY_THRESHOLD == 0.90


# ---------------------------------------------------------------------------
# 4. step4_reproducibility_test
# ---------------------------------------------------------------------------

class TestStep4ReproducibilityTest:
    def test_repro_fn_result_returned(self):
        m = make_monitor()
        rate = m.step4_reproducibility_test(lambda: 0.98)
        assert rate == 0.98

    def test_no_fn_returns_1(self):
        m = make_monitor()
        rate = m.step4_reproducibility_test(None)
        assert rate == 1.0

    def test_rate_below_threshold_detected(self):
        m = make_monitor()
        rate = m.step4_reproducibility_test(lambda: 0.80)
        assert rate < REPRODUCIBILITY_THRESHOLD

    def test_threshold_value(self):
        assert REPRODUCIBILITY_THRESHOLD == 0.95

    def test_result_logged_with_ok_flag(self):
        m = make_monitor()
        m.step4_reproducibility_test(lambda: 1.0)
        entry = next(e for e in m._log if e["step"] == "step4_reproducibility_test")
        assert entry["ok"] is True


# ---------------------------------------------------------------------------
# 5. step5_safety_check
# ---------------------------------------------------------------------------

class TestStep5SafetyCheck:
    def test_authenticated_no_exceptions_is_safe(self):
        m = make_monitor()
        ok, detail = m.step5_safety_check(_ok_status())
        assert ok is True
        assert detail["safety_ok"] is True

    def test_unknown_auth_status_is_unsafe(self):
        m = make_monitor()
        ok, detail = m.step5_safety_check(_unauth_status())
        assert ok is False

    def test_exception_count_nonzero_is_unsafe(self):
        m = make_monitor()
        status = {**_ok_status(), "exception_count": 1}
        ok, _ = m.step5_safety_check(status)
        assert ok is False

    def test_reads_auth_report_when_status_missing_key(self, patch_paths):
        auth_report = patch_paths / "api_auth_report.json"
        auth_report.write_text(
            json.dumps({"result": {"auth_status": "authenticated"}}),
            encoding="utf-8",
        )
        status = {"uptime_rate": 1.0, "error_rate": 0.0, "error_count": 0,
                  "avg_latency": 0.5, "exception_count": 0}
        m = make_monitor()
        ok, detail = m.step5_safety_check(status)
        assert detail["api_auth_status"] == "authenticated"
        assert ok is True

    def test_missing_auth_report_gives_unknown(self):
        m = make_monitor()
        status = {"uptime_rate": 1.0, "error_rate": 0.0, "error_count": 0,
                  "avg_latency": 0.5, "exception_count": 0}
        ok, detail = m.step5_safety_check(status)
        assert detail["api_auth_status"] == "unknown"


# ---------------------------------------------------------------------------
# 6. step6_generate_daily_log
# ---------------------------------------------------------------------------

class TestStep6GenerateDailyLog:
    def _run_step6(self, m: F10110DailyMonitoring, patch_paths: Path) -> dict:
        status = _ok_status()
        _, metrics = m.step3_calculate_stability(status)
        _, safety_detail = m.step5_safety_check(status)
        return m.step6_generate_daily_log(
            prev={}, anomalies=[], status=status,
            stability_index=0.95, metrics=metrics,
            repro_rate=1.0, safety_detail=safety_detail,
        )

    def test_daily_log_file_created(self, patch_paths):
        m = make_monitor()
        self._run_step6(m, patch_paths)
        assert (patch_paths / "daily_operation_log.json").exists()

    def test_stability_report_file_created(self, patch_paths):
        m = make_monitor()
        self._run_step6(m, patch_paths)
        assert (patch_paths / "stability_report.json").exists()

    def test_daily_log_module_field(self, patch_paths):
        m = make_monitor()
        self._run_step6(m, patch_paths)
        data = json.loads((patch_paths / "daily_operation_log.json").read_text(encoding="utf-8"))
        assert data["module"] == "F10110"

    def test_stability_index_in_report(self, patch_paths):
        m = make_monitor()
        self._run_step6(m, patch_paths)
        data = json.loads((patch_paths / "stability_report.json").read_text(encoding="utf-8"))
        assert "stability_index" in data

    def test_hitl_point_id_in_daily_log(self, patch_paths):
        m = make_monitor()
        self._run_step6(m, patch_paths)
        data = json.loads((patch_paths / "daily_operation_log.json").read_text(encoding="utf-8"))
        assert data["hitl_point"] == "H-P10-003"

    def test_no_api_key_in_output(self, patch_paths):
        m = make_monitor()
        status = {**_ok_status(), "api_key": "sk-secret"}
        _, metrics = m.step3_calculate_stability(status)
        _, safety_detail = m.step5_safety_check(status)
        m.step6_generate_daily_log(
            prev={}, anomalies=[], status=status,
            stability_index=0.95, metrics=metrics,
            repro_rate=1.0, safety_detail=safety_detail,
        )
        for p in patch_paths.iterdir():
            if p.suffix == ".json":
                assert "sk-secret" not in p.read_text(encoding="utf-8"), p.name


# ---------------------------------------------------------------------------
# 7. step7_set_hitl_checkpoint
# ---------------------------------------------------------------------------

class TestStep7SetHitlCheckpoint:
    def _dummy_report(self) -> dict:
        return {"module": "F10110", "stability_index": 0.95, "phase10_stage": "daily_monitoring_pending_hitl"}

    def test_approve_decision(self, patch_paths):
        m = make_monitor()
        dec = m.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.95, 1.0)
        assert dec == "approve"

    def test_reject_decision(self, patch_paths):
        m = make_monitor()
        dec = m.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "reject", 0.95, 1.0)
        assert dec == "reject"

    def test_hitl_log_file_created(self, patch_paths):
        m = make_monitor()
        m.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.95, 1.0)
        assert (patch_paths / "hitl_monitoring_approval_log.json").exists()

    def test_hitl_log_point_id(self, patch_paths):
        m = make_monitor()
        m.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.95, 1.0)
        data = json.loads((patch_paths / "hitl_monitoring_approval_log.json").read_text(encoding="utf-8"))
        assert data["hitl_point_id"] == "H-P10-003"

    def test_stage_after_approve(self, patch_paths):
        m = make_monitor()
        m.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "approve", 0.95, 1.0)
        data = json.loads((patch_paths / "hitl_monitoring_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "daily_monitoring_verified"

    def test_stage_after_reject(self, patch_paths):
        m = make_monitor()
        m.step7_set_hitl_checkpoint(self._dummy_report(), lambda _: "reject", 0.95, 1.0)
        data = json.loads((patch_paths / "hitl_monitoring_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "hitl_rejected"

    def test_no_hitl_fn_defaults_to_approve(self, patch_paths):
        m = make_monitor()
        dec = m.step7_set_hitl_checkpoint(self._dummy_report(), None, 0.95, 1.0)
        assert dec == "approve"


# ---------------------------------------------------------------------------
# 8. Full run — success path
# ---------------------------------------------------------------------------

class TestRunSuccessPath:
    def test_success_result(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is True

    def test_phase10_stage_daily_monitoring_verified(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["phase10_stage"] == "daily_monitoring_verified"

    def test_stability_ok(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["stability_ok"] is True

    def test_output_files_created(self, patch_paths):
        m = make_monitor()
        m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert (patch_paths / "daily_operation_log.json").exists()
        assert (patch_paths / "stability_report.json").exists()
        assert (patch_paths / "hitl_monitoring_approval_log.json").exists()

    def test_api_auth_status_authenticated(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["api_auth_status"] == "authenticated"

    def test_hitl_decision_approve(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["hitl_decision"] == "approve"


# ---------------------------------------------------------------------------
# 9. Run — error_count > 0 path
# ---------------------------------------------------------------------------

class TestRunErrorCountPath:
    def test_failure_on_error_count(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _error_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is False

    def test_reason_error_count(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _error_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["reason"] == "error_count > 0"

    def test_exception_log_created(self, patch_paths):
        m = make_monitor()
        m.run(
            system_status_fn=lambda: _error_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert (patch_paths / "exception_log.json").exists()


# ---------------------------------------------------------------------------
# 10. Run — api_auth_status not authenticated
# ---------------------------------------------------------------------------

class TestRunUnauthPath:
    def test_failure_on_unauth(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _unauth_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is False

    def test_reason_unauth(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _unauth_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["reason"] == "api_auth_status_not_authenticated"


# ---------------------------------------------------------------------------
# 11. Run — reproducibility_rate low
# ---------------------------------------------------------------------------

class TestRunLowReproPath:
    def test_failure_on_low_repro(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 0.80,
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is False

    def test_reason_repro_low(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 0.80,
            hitl_fn=lambda _: "approve",
        )
        assert result["reason"] == "reproducibility_rate_low"


# ---------------------------------------------------------------------------
# 12. Run — HITL reject
# ---------------------------------------------------------------------------

class TestRunHitlRejectPath:
    def test_failure_on_hitl_reject(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "reject",
        )
        assert result["success"] is False

    def test_reason_hitl_rejected(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "reject",
        )
        assert result["reason"] == "hitl_rejected"


# ---------------------------------------------------------------------------
# 13. Run — low stability (warning, but continues if no errors)
# ---------------------------------------------------------------------------

class TestRunLowStabilityPath:
    def test_low_stability_still_runs_to_hitl(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _low_stability_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        # low stability alone doesn't stop the run — HITL decides
        assert result["hitl_decision"] == "approve"

    def test_stability_ok_false_when_below_threshold(self, patch_paths):
        m = make_monitor()
        result = m.run(
            system_status_fn=lambda: _low_stability_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
        )
        assert result["stability_ok"] is False


# ---------------------------------------------------------------------------
# 14. write_summary_entry
# ---------------------------------------------------------------------------

class TestWriteSummaryEntry:
    def test_pass_tag_on_success(self, patch_paths):
        m = make_monitor()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10110_daily_monitoring.SUMMARY_LOG", log_path):
            m.write_summary_entry({
                "success": True, "phase10_stage": "daily_monitoring_verified",
                "stability_index": 0.95, "reproducibility_rate": 1.0, "hitl_decision": "approve",
            })
        assert "[PASS]" in log_path.read_text(encoding="utf-8")

    def test_fail_tag_on_failure(self, patch_paths):
        m = make_monitor()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10110_daily_monitoring.SUMMARY_LOG", log_path):
            m.write_summary_entry({
                "success": False, "phase10_stage": "daily_monitoring_failed",
                "stability_index": 0.5, "reproducibility_rate": 0.8, "hitl_decision": None,
            })
        assert "[FAIL]" in log_path.read_text(encoding="utf-8")

    def test_f10110_tag_in_log(self, patch_paths):
        m = make_monitor()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10110_daily_monitoring.SUMMARY_LOG", log_path):
            m.write_summary_entry({
                "success": True, "phase10_stage": "daily_monitoring_verified",
                "stability_index": 0.95, "reproducibility_rate": 1.0, "hitl_decision": "approve",
            })
        assert "[F10110]" in log_path.read_text(encoding="utf-8")

    def test_appends_to_existing_log(self, patch_paths):
        m = make_monitor()
        log_path = patch_paths / "summary.log"
        log_path.write_text("existing\n", encoding="utf-8")
        with patch("src.phase10.f10110_daily_monitoring.SUMMARY_LOG", log_path):
            m.write_summary_entry({
                "success": True, "phase10_stage": "daily_monitoring_verified",
                "stability_index": 0.95, "reproducibility_rate": 1.0, "hitl_decision": "approve",
            })
        content = log_path.read_text(encoding="utf-8")
        assert "existing" in content
        assert "[PASS]" in content


# ---------------------------------------------------------------------------
# 15. Previous anomalies carried into daily log
# ---------------------------------------------------------------------------

class TestPreviousAnomaliesInLog:
    def test_anomalies_in_daily_log_json(self, patch_paths):
        prev_data = {"stability_index": 0.5, "error_count": 0, "hitl_approved": True}
        m = make_monitor()
        m.run(
            system_status_fn=lambda: _ok_status(),
            repro_test_fn=lambda: 1.0,
            hitl_fn=lambda _: "approve",
            previous_log=prev_data,
        )
        data = json.loads((patch_paths / "daily_operation_log.json").read_text(encoding="utf-8"))
        assert "stability_index_below_threshold" in data["previous_anomalies"]
