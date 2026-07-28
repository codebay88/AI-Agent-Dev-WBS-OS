"""
tests/phase10/test_f10100_api_auth.py

F10100 api_authentication_verification のテストスイート。
実 API は呼ばない（api_mock を使用）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.phase10.f10100_api_auth import (
    AUTH_LOG_PATH,
    AUTH_REPORT_PATH,
    ENV_KEY_NAME,
    HITL_LOG_PATH,
    LATENCY_THRESHOLD,
    PHASE10_DIR,
    VALIDATION_ERR,
    F10100ApiAuthVerification,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_outputs(tmp_path, monkeypatch):
    """各テスト前に出力ファイルをクリアし、PHASE10_DIR を一時ディレクトリに向ける。"""
    monkeypatch.setattr("src.phase10.f10100_api_auth.PHASE10_DIR", tmp_path)
    monkeypatch.setattr("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", tmp_path / "api_auth_report.json")
    monkeypatch.setattr("src.phase10.f10100_api_auth.AUTH_LOG_PATH",    tmp_path / "api_auth_log.json")
    monkeypatch.setattr("src.phase10.f10100_api_auth.HITL_LOG_PATH",    tmp_path / "hitl_api_approval_log.json")
    monkeypatch.setattr("src.phase10.f10100_api_auth.VALIDATION_ERR",   tmp_path / "validation_error.json")
    monkeypatch.setattr("src.phase10.f10100_api_auth.SUMMARY_LOG",      tmp_path / "summary.log")
    yield tmp_path


def _mock_ok(latency: float = 0.5) -> dict:
    return {"status": "authenticated", "latency": latency, "error_count": 0}


def _mock_failed() -> dict:
    return {"status": "failed", "latency": None, "error_count": 1, "error": "Unauthorized"}


def _mock_high_latency() -> dict:
    return {"status": "authenticated", "latency": 3.5, "error_count": 0}


def _mock_error_count() -> dict:
    return {"status": "authenticated", "latency": 0.3, "error_count": 2}


def make_verifier() -> F10100ApiAuthVerification:
    return F10100ApiAuthVerification()


# ---------------------------------------------------------------------------
# 1. step1_check_env_key
# ---------------------------------------------------------------------------

class TestStep1CheckEnvKey:
    def test_returns_true_when_key_present(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test-key")
        v = make_verifier()
        assert v.step1_check_env_key() is True

    def test_returns_false_when_key_absent(self, monkeypatch):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)
        v = make_verifier()
        assert v.step1_check_env_key() is False

    def test_returns_false_when_key_empty(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY_NAME, "")
        v = make_verifier()
        assert v.step1_check_env_key() is False

    def test_key_value_not_logged(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-secret-value")
        v = make_verifier()
        v.step1_check_env_key()
        log_str = json.dumps(v._log)
        assert "sk-secret-value" not in log_str


# ---------------------------------------------------------------------------
# 2. step2_send_ping
# ---------------------------------------------------------------------------

class TestStep2SendPing:
    def test_mock_returns_expected_structure(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.step2_send_ping(lambda: _mock_ok())
        assert result["status"] == "authenticated"
        assert result["latency"] == 0.5
        assert result["error_count"] == 0

    def test_mock_failure_returns_failed_status(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.step2_send_ping(lambda: _mock_failed())
        assert result["status"] == "failed"

    def test_api_key_not_in_log_after_ping(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-top-secret")
        v = make_verifier()
        v.step2_send_ping(lambda: _mock_ok())
        log_str = json.dumps(v._log)
        assert "sk-top-secret" not in log_str

    def test_mode_recorded_as_mock(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        v.step2_send_ping(lambda: _mock_ok())
        assert any(e.get("mode") == "mock" for e in v._log)


# ---------------------------------------------------------------------------
# 3. step3_determine_status
# ---------------------------------------------------------------------------

class TestStep3DetermineStatus:
    def test_authenticated(self):
        v = make_verifier()
        assert v.step3_determine_status(_mock_ok()) == "authenticated"

    def test_failed(self):
        v = make_verifier()
        assert v.step3_determine_status(_mock_failed()) == "failed"

    def test_missing_key_defaults_to_failed(self):
        v = make_verifier()
        assert v.step3_determine_status({}) == "failed"


# ---------------------------------------------------------------------------
# 4. step4_check_latency
# ---------------------------------------------------------------------------

class TestStep4CheckLatency:
    def test_within_threshold_no_warning(self):
        v = make_verifier()
        ok, warning = v.step4_check_latency(_mock_ok(latency=0.5))
        assert ok is True
        assert warning is False

    def test_exactly_at_threshold_is_ok(self):
        v = make_verifier()
        ok, warning = v.step4_check_latency(_mock_ok(latency=1.9999))
        assert ok is True

    def test_above_threshold_triggers_warning(self):
        v = make_verifier()
        ok, warning = v.step4_check_latency(_mock_high_latency())
        assert ok is False
        assert warning is True

    def test_none_latency_produces_warning(self):
        v = make_verifier()
        ok, warning = v.step4_check_latency({"latency": None})
        assert warning is True

    def test_threshold_value_is_2_seconds(self):
        assert LATENCY_THRESHOLD == 2.0


# ---------------------------------------------------------------------------
# 5. step5_verify_error_count
# ---------------------------------------------------------------------------

class TestStep5VerifyErrorCount:
    def test_zero_errors_ok(self):
        v = make_verifier()
        assert v.step5_verify_error_count(_mock_ok()) is True

    def test_nonzero_errors_fail(self):
        v = make_verifier()
        assert v.step5_verify_error_count(_mock_error_count()) is False

    def test_missing_error_count_treated_as_nonzero(self):
        v = make_verifier()
        assert v.step5_verify_error_count({}) is False


# ---------------------------------------------------------------------------
# 6. step6_generate_report
# ---------------------------------------------------------------------------

class TestStep6GenerateReport:
    def test_report_file_created(self, clean_outputs):
        v = make_verifier()
        report_path = clean_outputs / "api_auth_report.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", report_path), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", clean_outputs / "api_auth_log.json"):
            v.step6_generate_report(_mock_ok(), latency_warning=False)
        assert report_path.exists()

    def test_report_contains_auth_status(self, clean_outputs):
        v = make_verifier()
        report_path = clean_outputs / "api_auth_report.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", report_path), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", clean_outputs / "api_auth_log.json"):
            v.step6_generate_report(_mock_ok(), latency_warning=False)
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["result"]["auth_status"] == "authenticated"

    def test_report_module_is_f10100(self, clean_outputs):
        v = make_verifier()
        report_path = clean_outputs / "api_auth_report.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", report_path), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", clean_outputs / "api_auth_log.json"):
            v.step6_generate_report(_mock_ok(), latency_warning=False)
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["module"] == "F10100"

    def test_latency_warning_reflected_in_report(self, clean_outputs):
        v = make_verifier()
        report_path = clean_outputs / "api_auth_report.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", report_path), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", clean_outputs / "api_auth_log.json"):
            v.step6_generate_report(_mock_high_latency(), latency_warning=True)
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["result"]["latency_warning"] is True

    def test_log_file_created(self, clean_outputs):
        v = make_verifier()
        log_path = clean_outputs / "api_auth_log.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", clean_outputs / "api_auth_report.json"), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", log_path):
            v.step6_generate_report(_mock_ok(), latency_warning=False)
        assert log_path.exists()

    def test_api_key_not_in_report(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-do-not-expose")
        v = make_verifier()
        report_path = clean_outputs / "api_auth_report.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", report_path), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", clean_outputs / "api_auth_log.json"):
            v.step6_generate_report(_mock_ok(), latency_warning=False)
        assert "sk-do-not-expose" not in report_path.read_text(encoding="utf-8")

    def test_hitl_point_id_in_report(self, clean_outputs):
        v = make_verifier()
        report_path = clean_outputs / "api_auth_report.json"
        with patch("src.phase10.f10100_api_auth.AUTH_REPORT_PATH", report_path), \
             patch("src.phase10.f10100_api_auth.AUTH_LOG_PATH", clean_outputs / "api_auth_log.json"):
            v.step6_generate_report(_mock_ok(), latency_warning=False)
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["hitl_point"] == "H-P10-002"


# ---------------------------------------------------------------------------
# 7. step7_set_hitl_checkpoint
# ---------------------------------------------------------------------------

class TestStep7SetHitlCheckpoint:
    def _make_report(self) -> dict:
        return {
            "module": "F10100",
            "result": {
                "auth_status": "authenticated",
                "latency_warning": False,
                "phase10_stage": "api_verified_pending_hitl",
            },
        }

    def test_approve_decision_recorded(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            decision = v.step7_set_hitl_checkpoint(
                self._make_report(), lambda _: "approve", False
            )
        assert decision == "approve"

    def test_reject_decision_recorded(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            decision = v.step7_set_hitl_checkpoint(
                self._make_report(), lambda _: "reject", False
            )
        assert decision == "reject"

    def test_hitl_log_file_created(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            v.step7_set_hitl_checkpoint(
                self._make_report(), lambda _: "approve", False
            )
        assert hitl_path.exists()

    def test_hitl_log_contains_point_id(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            v.step7_set_hitl_checkpoint(
                self._make_report(), lambda _: "approve", False
            )
        data = json.loads(hitl_path.read_text(encoding="utf-8"))
        assert data["hitl_point_id"] == "H-P10-002"

    def test_stage_after_approve(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            v.step7_set_hitl_checkpoint(
                self._make_report(), lambda _: "approve", False
            )
        data = json.loads(hitl_path.read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "api_verified"

    def test_stage_after_reject(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            v.step7_set_hitl_checkpoint(
                self._make_report(), lambda _: "reject", False
            )
        data = json.loads(hitl_path.read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "hitl_rejected"

    def test_no_hitl_fn_defaults_to_approve(self, clean_outputs):
        v = make_verifier()
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        with patch("src.phase10.f10100_api_auth.HITL_LOG_PATH", hitl_path):
            decision = v.step7_set_hitl_checkpoint(
                self._make_report(), None, False
            )
        assert decision == "approve"


# ---------------------------------------------------------------------------
# 8. Full run — success path
# ---------------------------------------------------------------------------

class TestRunSuccessPath:
    def test_success_result(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert result["success"] is True

    def test_phase10_stage_api_verified(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert result["phase10_stage"] == "api_verified"

    def test_auth_status_authenticated(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert result["auth_status"] == "authenticated"

    def test_no_latency_warning_for_fast_response(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(0.2), hitl_fn=lambda _: "approve")
        assert result["latency_warning"] is False

    def test_output_files_created(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert (clean_outputs / "api_auth_report.json").exists()
        assert (clean_outputs / "api_auth_log.json").exists()
        assert (clean_outputs / "hitl_api_approval_log.json").exists()

    def test_api_key_not_in_any_output(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-must-not-appear")
        v = make_verifier()
        v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        for p in clean_outputs.iterdir():
            if p.suffix == ".json":
                assert "sk-must-not-appear" not in p.read_text(encoding="utf-8"), p.name


# ---------------------------------------------------------------------------
# 9. Run — key missing path
# ---------------------------------------------------------------------------

class TestRunKeyMissingPath:
    def test_failure_on_missing_key(self, monkeypatch, clean_outputs):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert result["success"] is False

    def test_reason_api_key_missing(self, monkeypatch, clean_outputs):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert result["reason"] == "api_key_missing"

    def test_validation_error_file_created_on_missing_key(self, monkeypatch, clean_outputs):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)
        v = make_verifier()
        v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert (clean_outputs / "validation_error.json").exists()

    def test_hitl_pending_on_missing_key(self, monkeypatch, clean_outputs):
        monkeypatch.delenv(ENV_KEY_NAME, raising=False)
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        assert result["hitl_decision"] == "pending"


# ---------------------------------------------------------------------------
# 10. Run — authentication failed path
# ---------------------------------------------------------------------------

class TestRunAuthFailedPath:
    def test_failure_on_auth_failed(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_failed(), hitl_fn=lambda _: "approve")
        assert result["success"] is False

    def test_reason_authentication_failed(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_failed(), hitl_fn=lambda _: "approve")
        assert result["reason"] == "authentication_failed"

    def test_validation_error_file_created_on_auth_failed(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        v.run(api_mock=lambda: _mock_failed(), hitl_fn=lambda _: "approve")
        assert (clean_outputs / "validation_error.json").exists()

    def test_phase10_stage_api_auth_failed(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_failed(), hitl_fn=lambda _: "approve")
        assert result["phase10_stage"] == "api_auth_failed"


# ---------------------------------------------------------------------------
# 11. Run — high latency (warning but success if HITL approves)
# ---------------------------------------------------------------------------

class TestRunHighLatencyPath:
    def test_success_with_latency_warning_when_hitl_approves(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_high_latency(), hitl_fn=lambda _: "approve")
        assert result["success"] is True

    def test_latency_warning_true(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_high_latency(), hitl_fn=lambda _: "approve")
        assert result["latency_warning"] is True

    def test_stage_still_api_verified_if_approved(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_high_latency(), hitl_fn=lambda _: "approve")
        assert result["phase10_stage"] == "api_verified"


# ---------------------------------------------------------------------------
# 12. Run — HITL reject path
# ---------------------------------------------------------------------------

class TestRunHitlRejectPath:
    def test_failure_on_hitl_reject(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "reject")
        assert result["success"] is False

    def test_reason_hitl_rejected(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "reject")
        assert result["reason"] == "hitl_rejected"

    def test_phase10_stage_api_auth_failed_on_reject(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "reject")
        assert result["phase10_stage"] == "api_auth_failed"


# ---------------------------------------------------------------------------
# 13. Run — error_count nonzero path
# ---------------------------------------------------------------------------

class TestRunErrorCountPath:
    def test_failure_on_nonzero_error_count(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_error_count(), hitl_fn=lambda _: "approve")
        assert result["success"] is False

    def test_reason_error_count(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_error_count(), hitl_fn=lambda _: "approve")
        assert result["reason"] == "error_count > 0"

    def test_validation_error_file_on_error_count(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-test")
        v = make_verifier()
        v.run(api_mock=lambda: _mock_error_count(), hitl_fn=lambda _: "approve")
        assert (clean_outputs / "validation_error.json").exists()


# ---------------------------------------------------------------------------
# 14. write_summary_entry
# ---------------------------------------------------------------------------

class TestWriteSummaryEntry:
    def test_pass_tag_on_success(self, clean_outputs):
        v = make_verifier()
        log_path = clean_outputs / "summary.log"
        with patch("src.phase10.f10100_api_auth.SUMMARY_LOG", log_path):
            v.write_summary_entry({"success": True, "phase10_stage": "api_verified",
                                   "auth_status": "authenticated", "latency_warning": False,
                                   "hitl_decision": "approve"})
        assert "[PASS]" in log_path.read_text(encoding="utf-8")

    def test_fail_tag_on_failure(self, clean_outputs):
        v = make_verifier()
        log_path = clean_outputs / "summary.log"
        with patch("src.phase10.f10100_api_auth.SUMMARY_LOG", log_path):
            v.write_summary_entry({"success": False, "phase10_stage": "api_auth_failed",
                                   "auth_status": "failed", "latency_warning": False,
                                   "hitl_decision": None})
        assert "[FAIL]" in log_path.read_text(encoding="utf-8")

    def test_f10100_tag_in_log(self, clean_outputs):
        v = make_verifier()
        log_path = clean_outputs / "summary.log"
        with patch("src.phase10.f10100_api_auth.SUMMARY_LOG", log_path):
            v.write_summary_entry({"success": True, "phase10_stage": "api_verified",
                                   "auth_status": "authenticated", "latency_warning": False,
                                   "hitl_decision": "approve"})
        assert "[F10100]" in log_path.read_text(encoding="utf-8")

    def test_appends_to_existing_log(self, clean_outputs):
        v = make_verifier()
        log_path = clean_outputs / "summary.log"
        log_path.write_text("existing line\n", encoding="utf-8")
        with patch("src.phase10.f10100_api_auth.SUMMARY_LOG", log_path):
            v.write_summary_entry({"success": True, "phase10_stage": "api_verified",
                                   "auth_status": "authenticated", "latency_warning": False,
                                   "hitl_decision": "approve"})
        content = log_path.read_text(encoding="utf-8")
        assert "existing line" in content
        assert "[PASS]" in content


# ---------------------------------------------------------------------------
# 15. Security — API key never exposed
# ---------------------------------------------------------------------------

class TestSecurityApiKeyNeverExposed:
    def test_key_not_in_run_result(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-private-key-xyz")
        v = make_verifier()
        result = v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        result_str = json.dumps(result)
        assert "sk-private-key-xyz" not in result_str

    def test_key_not_in_internal_log(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-private-key-xyz")
        v = make_verifier()
        v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        log_str = json.dumps(v._log)
        assert "sk-private-key-xyz" not in log_str

    def test_key_not_in_hitl_log_file(self, monkeypatch, clean_outputs):
        monkeypatch.setenv(ENV_KEY_NAME, "sk-private-key-xyz")
        v = make_verifier()
        v.run(api_mock=lambda: _mock_ok(), hitl_fn=lambda _: "approve")
        hitl_path = clean_outputs / "hitl_api_approval_log.json"
        if hitl_path.exists():
            assert "sk-private-key-xyz" not in hitl_path.read_text(encoding="utf-8")
