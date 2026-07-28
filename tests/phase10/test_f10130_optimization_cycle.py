"""
tests/phase10/test_f10130_optimization_cycle.py

F10130 continuous_optimization_cycle のテストスイート。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.phase10.f10130_optimization_cycle import (
    CYCLE_LOG_PATH,
    EXCEPTION_LOG,
    HITL_LOG_PATH,
    HITL_POINT_ID,
    MAX_RETRAINING,
    OPT_SUMMARY,
    PHASE10_DIR,
    RETRAIN_PATH,
    THRESHOLD_PATH,
    VALIDATION_ERR,
    WEEKLY_REPORT,
    F10130OptimizationCycle,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.PHASE10_DIR",    tmp_path)
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.CYCLE_LOG_PATH", tmp_path / "optimization_cycle_log.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.THRESHOLD_PATH", tmp_path / "threshold_adjustment_report.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.RETRAIN_PATH",   tmp_path / "retraining_trigger.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.HITL_LOG_PATH",  tmp_path / "hitl_optimization_approval_log.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.EXCEPTION_LOG",  tmp_path / "exception_log.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.VALIDATION_ERR", tmp_path / "validation_error.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.WEEKLY_REPORT",  tmp_path / "weekly_stability_report.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.OPT_SUMMARY",    tmp_path / "optimization_summary.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.FAILURE_REPO",   tmp_path / "failure_repository.json")
    monkeypatch.setattr("src.phase10.f10130_optimization_cycle.SUMMARY_LOG",    tmp_path / "summary.log")
    yield tmp_path


def _ok_weekly_report() -> dict:
    return {
        "weekly_stability_index": 0.97,
        "weekly_stability_ok":    True,
        "reproducibility":        {"rate": 1.0, "ok": True},
        "safety":                 {"api_auth_status": "authenticated"},
        "relearning_candidate":   False,
    }


def _low_stability_report() -> dict:
    return {
        "weekly_stability_index": 0.80,
        "weekly_stability_ok":    False,
        "reproducibility":        {"rate": 1.0, "ok": True},
        "safety":                 {"api_auth_status": "authenticated"},
        "relearning_candidate":   True,
    }


def _ok_proposals() -> list[str]:
    return ["no_action_required_system_stable"]


def _action_proposals() -> list[str]:
    return [
        "stability_threshold_adjustment_required",
        "latency_optimization_required",
    ]


def _failure_repo() -> dict:
    return {
        "failures": [
            {"id": "FL-001", "category": "hitl"},
            {"id": "FL-002", "category": "retry"},
        ],
        "prevention_patterns": [
            {"applies_to": "hitl",  "action": "delegate_to_hitl"},
            {"applies_to": "retry", "action": "stop_and_alert"},
        ],
    }


def make_opt() -> F10130OptimizationCycle:
    return F10130OptimizationCycle()


# ---------------------------------------------------------------------------
# 1. step1_load_weekly_report
# ---------------------------------------------------------------------------

class TestStep1LoadWeeklyReport:
    def test_injected_report_used(self):
        o = make_opt()
        report = o.step1_load_weekly_report(_ok_weekly_report())
        assert report["weekly_stability_index"] == 0.97

    def test_no_arg_empty_when_no_file(self, patch_paths):
        o = make_opt()
        report = o.step1_load_weekly_report(None)
        assert report == {}

    def test_reads_file_when_no_arg(self, patch_paths):
        weekly_path = patch_paths / "weekly_stability_report.json"
        weekly_path.write_text(
            json.dumps(_ok_weekly_report()), encoding="utf-8"
        )
        o = make_opt()
        report = o.step1_load_weekly_report(None)
        assert report["weekly_stability_index"] == 0.97

    def test_logged(self):
        o = make_opt()
        o.step1_load_weekly_report(_ok_weekly_report())
        assert any(e["step"] == "step1_load_weekly_report" for e in o._log)


# ---------------------------------------------------------------------------
# 2. step2_extract_proposals
# ---------------------------------------------------------------------------

class TestStep2ExtractProposals:
    def test_injected_proposals_used(self):
        o = make_opt()
        proposals = o.step2_extract_proposals({"proposals": _action_proposals()})
        assert "stability_threshold_adjustment_required" in proposals

    def test_no_arg_returns_default(self, patch_paths):
        o = make_opt()
        proposals = o.step2_extract_proposals(None)
        assert proposals == ["no_action_required_system_stable"]

    def test_reads_file_when_no_arg(self, patch_paths):
        opt_path = patch_paths / "optimization_summary.json"
        opt_path.write_text(
            json.dumps({"proposals": ["latency_optimization_required"]}), encoding="utf-8"
        )
        o = make_opt()
        proposals = o.step2_extract_proposals(None)
        assert "latency_optimization_required" in proposals

    def test_logged(self):
        o = make_opt()
        o.step2_extract_proposals({"proposals": _ok_proposals()})
        assert any(e["step"] == "step2_extract_proposals" for e in o._log)


# ---------------------------------------------------------------------------
# 3. step3_analyze_failure_repository
# ---------------------------------------------------------------------------

class TestStep3AnalyzeFailureRepository:
    def test_prevention_generated_for_each_failure(self):
        o = make_opt()
        prevention = o.step3_analyze_failure_repository(_failure_repo())
        assert len(prevention) == 2

    def test_prevention_contains_failure_id(self):
        o = make_opt()
        prevention = o.step3_analyze_failure_repository(_failure_repo())
        ids = [p["failure_id"] for p in prevention]
        assert "FL-001" in ids
        assert "FL-002" in ids

    def test_no_arg_no_file_returns_empty(self, patch_paths):
        o = make_opt()
        prevention = o.step3_analyze_failure_repository(None)
        assert prevention == []

    def test_reads_file_when_no_arg(self, patch_paths):
        repo_path = patch_paths / "failure_repository.json"
        repo_path.write_text(
            json.dumps({
                "failures": [{"id": "FL-X", "category": "test"}],
                "prevention_patterns": [],
            }),
            encoding="utf-8",
        )
        o = make_opt()
        prevention = o.step3_analyze_failure_repository(None)
        assert len(prevention) == 1

    def test_logged_with_counts(self):
        o = make_opt()
        o.step3_analyze_failure_repository(_failure_repo())
        entry = next(e for e in o._log if e["step"] == "step3_analyze_failure_repository")
        assert entry["failure_count"] == 2


# ---------------------------------------------------------------------------
# 4. step4_threshold_adjustment
# ---------------------------------------------------------------------------

class TestStep4ThresholdAdjustment:
    def test_valid_true_for_stable_system(self, patch_paths):
        o = make_opt()
        result = o.step4_threshold_adjustment(_ok_weekly_report(), _ok_proposals())
        assert result["valid"] is True

    def test_no_changes_for_stable_system(self, patch_paths):
        o = make_opt()
        result = o.step4_threshold_adjustment(_ok_weekly_report(), _ok_proposals())
        assert result["changes"] == []

    def test_threshold_file_created(self, patch_paths):
        o = make_opt()
        o.step4_threshold_adjustment(_ok_weekly_report(), _ok_proposals())
        assert (patch_paths / "threshold_adjustment_report.json").exists()

    def test_latency_adjusted_when_proposed(self, patch_paths):
        o = make_opt()
        result = o.step4_threshold_adjustment(_ok_weekly_report(), _action_proposals())
        assert any("latency_limit" in c for c in result["changes"])

    def test_stability_threshold_adjusted_when_low(self, patch_paths):
        o = make_opt()
        result = o.step4_threshold_adjustment(_low_stability_report(), _action_proposals())
        assert any("weekly_stability_threshold" in c for c in result["changes"])

    def test_adjusted_values_in_file(self, patch_paths):
        o = make_opt()
        o.step4_threshold_adjustment(_ok_weekly_report(), _ok_proposals())
        data = json.loads((patch_paths / "threshold_adjustment_report.json").read_text(encoding="utf-8"))
        assert "adjusted" in data
        assert "previous" in data

    def test_stability_threshold_not_below_minimum(self, patch_paths):
        o = make_opt()
        # 超低安定性を繰り返しても 0.80 を下回らない
        report = {**_low_stability_report(), "weekly_stability_index": 0.50}
        result = o.step4_threshold_adjustment(report, _action_proposals())
        assert result["adjusted"]["weekly_stability_threshold"] >= 0.80


# ---------------------------------------------------------------------------
# 5. step5_retraining_trigger
# ---------------------------------------------------------------------------

class TestStep5RetrainingTrigger:
    def test_no_trigger_for_stable(self, patch_paths):
        o = make_opt()
        count, detail = o.step5_retraining_trigger(_ok_weekly_report(), _ok_proposals())
        assert count == 0
        assert detail["triggers"] == []

    def test_trigger_when_stability_critical(self, patch_paths):
        report = {**_ok_weekly_report(), "weekly_stability_index": 0.85}
        o = make_opt()
        count, detail = o.step5_retraining_trigger(report, _ok_proposals())
        assert count == 1
        assert "stability_critical" in detail["triggers"]

    def test_trigger_for_repro_degraded(self, patch_paths):
        o = make_opt()
        count, detail = o.step5_retraining_trigger(
            _ok_weekly_report(), ["reproducibility_improvement_required"]
        )
        assert count == 1

    def test_over_limit_detected(self, patch_paths):
        o = make_opt()
        count, detail = o.step5_retraining_trigger(
            {**_ok_weekly_report(), "weekly_stability_index": 0.85},
            _ok_proposals(),
        )
        assert detail["over_limit"] == (count > MAX_RETRAINING)

    def test_retrain_file_created(self, patch_paths):
        o = make_opt()
        o.step5_retraining_trigger(_ok_weekly_report(), _ok_proposals())
        assert (patch_paths / "retraining_trigger.json").exists()

    def test_max_retraining_is_1(self):
        assert MAX_RETRAINING == 1

    def test_max_allowed_in_detail(self, patch_paths):
        o = make_opt()
        _, detail = o.step5_retraining_trigger(_ok_weekly_report(), _ok_proposals())
        assert detail["max_allowed"] == MAX_RETRAINING


# ---------------------------------------------------------------------------
# 6. step6_generate_cycle_log
# ---------------------------------------------------------------------------

class TestStep6GenerateCycleLog:
    def _run_steps1_5(self, o: F10130OptimizationCycle):
        report = o.step1_load_weekly_report(_ok_weekly_report())
        proposals = o.step2_extract_proposals({"proposals": _ok_proposals()})
        prevention = o.step3_analyze_failure_repository(_failure_repo())
        adj = o.step4_threshold_adjustment(report, proposals)
        retrain_count, retrain_detail = o.step5_retraining_trigger(report, proposals)
        return report, proposals, prevention, adj, retrain_count, retrain_detail

    def test_cycle_log_file_created(self, patch_paths):
        o = make_opt()
        args = self._run_steps1_5(o)
        o.step6_generate_cycle_log(*args)
        assert (patch_paths / "optimization_cycle_log.json").exists()

    def test_cycle_completed_true(self, patch_paths):
        o = make_opt()
        args = self._run_steps1_5(o)
        log = o.step6_generate_cycle_log(*args)
        assert log["optimization_cycle_completed"] is True

    def test_module_field(self, patch_paths):
        o = make_opt()
        args = self._run_steps1_5(o)
        o.step6_generate_cycle_log(*args)
        data = json.loads((patch_paths / "optimization_cycle_log.json").read_text(encoding="utf-8"))
        assert data["module"] == "F10130"

    def test_hitl_point_in_log(self, patch_paths):
        o = make_opt()
        args = self._run_steps1_5(o)
        o.step6_generate_cycle_log(*args)
        data = json.loads((patch_paths / "optimization_cycle_log.json").read_text(encoding="utf-8"))
        assert data["hitl_point"] == "H-P10-004"


# ---------------------------------------------------------------------------
# 7. step7_set_hitl_checkpoint
# ---------------------------------------------------------------------------

class TestStep7SetHitlCheckpoint:
    def _dummy_log(self) -> dict:
        return {"module": "F10130", "optimization_cycle_completed": True}

    def _dummy_adj(self) -> dict:
        return {"changes": [], "valid": True}

    def test_approve_decision(self, patch_paths):
        o = make_opt()
        dec = o.step7_set_hitl_checkpoint(self._dummy_log(), lambda _: "approve", self._dummy_adj())
        assert dec == "approve"

    def test_reject_decision(self, patch_paths):
        o = make_opt()
        dec = o.step7_set_hitl_checkpoint(self._dummy_log(), lambda _: "reject", self._dummy_adj())
        assert dec == "reject"

    def test_hitl_log_created(self, patch_paths):
        o = make_opt()
        o.step7_set_hitl_checkpoint(self._dummy_log(), lambda _: "approve", self._dummy_adj())
        assert (patch_paths / "hitl_optimization_approval_log.json").exists()

    def test_hitl_point_id_in_log(self, patch_paths):
        o = make_opt()
        o.step7_set_hitl_checkpoint(self._dummy_log(), lambda _: "approve", self._dummy_adj())
        data = json.loads((patch_paths / "hitl_optimization_approval_log.json").read_text(encoding="utf-8"))
        assert data["hitl_point_id"] == "H-P10-004"

    def test_stage_after_approve(self, patch_paths):
        o = make_opt()
        o.step7_set_hitl_checkpoint(self._dummy_log(), lambda _: "approve", self._dummy_adj())
        data = json.loads((patch_paths / "hitl_optimization_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "optimization_cycle_verified"

    def test_stage_after_reject(self, patch_paths):
        o = make_opt()
        o.step7_set_hitl_checkpoint(self._dummy_log(), lambda _: "reject", self._dummy_adj())
        data = json.loads((patch_paths / "hitl_optimization_approval_log.json").read_text(encoding="utf-8"))
        assert data["context"]["phase10_stage_after"] == "hitl_rejected"

    def test_no_fn_defaults_approve(self, patch_paths):
        o = make_opt()
        dec = o.step7_set_hitl_checkpoint(self._dummy_log(), None, self._dummy_adj())
        assert dec == "approve"


# ---------------------------------------------------------------------------
# 8. Full run — success path
# ---------------------------------------------------------------------------

class TestRunSuccessPath:
    def test_success(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is True

    def test_phase10_stage(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["phase10_stage"] == "optimization_cycle_verified"

    def test_cycle_completed(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["cycle_completed"] is True

    def test_output_files_created(self, patch_paths):
        o = make_opt()
        o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert (patch_paths / "optimization_cycle_log.json").exists()
        assert (patch_paths / "threshold_adjustment_report.json").exists()
        assert (patch_paths / "retraining_trigger.json").exists()
        assert (patch_paths / "hitl_optimization_approval_log.json").exists()

    def test_no_retraining_when_stable(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["retraining_triggered"] == 0

    def test_hitl_decision_approve(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["hitl_decision"] == "approve"


# ---------------------------------------------------------------------------
# 9. Run — HITL reject
# ---------------------------------------------------------------------------

class TestRunHitlRejectPath:
    def test_failure_on_reject(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "reject",
        )
        assert result["success"] is False

    def test_reason_hitl_rejected(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "reject",
        )
        assert result["reason"] == "hitl_rejected"

    def test_stage_failed(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "reject",
        )
        assert result["phase10_stage"] == "optimization_cycle_failed"


# ---------------------------------------------------------------------------
# 10. Run — retraining over limit
# ---------------------------------------------------------------------------

class TestRunRetrainingOverLimitPath:
    def test_failure_when_retrain_over(self, patch_paths, monkeypatch):
        # retraining_trigger を強制的に 2 返す mock
        def _mock_retrain(self_inner, report, proposals):
            return 2, {"triggered": 2, "triggers": ["x", "y"], "max_allowed": 1, "over_limit": True}

        monkeypatch.setattr(
            "src.phase10.f10130_optimization_cycle.F10130OptimizationCycle.step5_retraining_trigger",
            _mock_retrain,
        )
        o = make_opt()
        result = o.run(
            weekly_report=_ok_weekly_report(),
            opt_summary={"proposals": _ok_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["success"] is False
        assert result["reason"] == "retraining_triggered_over_limit"


# ---------------------------------------------------------------------------
# 11. Run — with action proposals (threshold adjustments happen)
# ---------------------------------------------------------------------------

class TestRunWithActionProposals:
    def test_threshold_changes_recorded(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_low_stability_report(),
            opt_summary={"proposals": _action_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["threshold_changes"] > 0

    def test_retraining_triggered_when_low(self, patch_paths):
        o = make_opt()
        result = o.run(
            weekly_report=_low_stability_report(),
            opt_summary={"proposals": _action_proposals()},
            failure_repo=_failure_repo(),
            hitl_fn=lambda _: "approve",
        )
        assert result["retraining_triggered"] == 1


# ---------------------------------------------------------------------------
# 12. write_summary_entry
# ---------------------------------------------------------------------------

class TestWriteSummaryEntry:
    def test_pass_tag(self, patch_paths):
        o = make_opt()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10130_optimization_cycle.SUMMARY_LOG", log_path):
            o.write_summary_entry({
                "success": True, "phase10_stage": "optimization_cycle_verified",
                "cycle_completed": True, "retraining_triggered": 0, "hitl_decision": "approve",
            })
        assert "[PASS]" in log_path.read_text(encoding="utf-8")

    def test_fail_tag(self, patch_paths):
        o = make_opt()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10130_optimization_cycle.SUMMARY_LOG", log_path):
            o.write_summary_entry({
                "success": False, "phase10_stage": "optimization_cycle_failed",
                "cycle_completed": False, "retraining_triggered": 0, "hitl_decision": None,
            })
        assert "[FAIL]" in log_path.read_text(encoding="utf-8")

    def test_f10130_tag(self, patch_paths):
        o = make_opt()
        log_path = patch_paths / "summary.log"
        with patch("src.phase10.f10130_optimization_cycle.SUMMARY_LOG", log_path):
            o.write_summary_entry({
                "success": True, "phase10_stage": "optimization_cycle_verified",
                "cycle_completed": True, "retraining_triggered": 0, "hitl_decision": "approve",
            })
        assert "[F10130]" in log_path.read_text(encoding="utf-8")

    def test_appends(self, patch_paths):
        o = make_opt()
        log_path = patch_paths / "summary.log"
        log_path.write_text("existing\n", encoding="utf-8")
        with patch("src.phase10.f10130_optimization_cycle.SUMMARY_LOG", log_path):
            o.write_summary_entry({
                "success": True, "phase10_stage": "optimization_cycle_verified",
                "cycle_completed": True, "retraining_triggered": 0, "hitl_decision": "approve",
            })
        content = log_path.read_text(encoding="utf-8")
        assert "existing" in content
        assert "[PASS]" in content
