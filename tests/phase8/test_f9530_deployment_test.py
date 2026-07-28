"""F9530 deployment_test_and_stabilization テスト
Phase 8：展開層

テスト対象:
  - src/deployment/f9530_deployment_test.py
    - F9530DeploymentTestAndStabilization.step1_load_and_integrate()
    - F9530DeploymentTestAndStabilization.step2_load_test()
    - F9530DeploymentTestAndStabilization.step3_monitor_exceptions()
    - F9530DeploymentTestAndStabilization.step4_reproducibility_test()
    - F9530DeploymentTestAndStabilization.step5_evaluate_stability()
    - F9530DeploymentTestAndStabilization.step6_set_hitl_final_approval()
    - F9530DeploymentTestAndStabilization.step7_generate_reports()
    - F9530DeploymentTestAndStabilization.step8_write_complete_flag()
    - F9530DeploymentTestAndStabilization.run()
    - F9530DeploymentTestAndStabilization.load_stability_report()
    - F9530DeploymentTestAndStabilization.load_deployment_summary()
    - F9530DeploymentTestAndStabilization.record_hitl_final_approval()
    - F9530DeploymentTestAndStabilization.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.deployment.f9530_deployment_test import (
    F9530DeploymentTestAndStabilization,
    IO_INTEGRITY_REQUIRED,
    ERROR_RATE_THRESHOLD,
    OPT_SCORE_THRESHOLD,
    REPRO_TEST_COUNT,
    LOAD_TEST_REQUESTS,
    _CYCLE_INPUTS,
)

# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

_PLAN = {
    "module":       "F9510",
    "phase8_stage": "limited_environment",
    "io_integrity": 100.0,
    "hitl_count":   5,
    "success":      True,
}
_INTEG = {
    "module":                      "F9520",
    "phase8_stage":                "trial_operation",
    "success":                     True,
    "io_integrity":                1.0,
    "reproducibility_test_passed": True,
    "failure_repository_sync":     "success",
    "knowledge_cycle_update":      "success",
}
_SYNC_LOG = {"module": "F9520", "success_message": "F9520 executed successfully"}
_HITL_LOG = {
    "module":          "F9520",
    "total_checkpoints": 5,
    "checkpoints": [
        {"stage": s, "status": "pending", "approved_at": None}
        for s in ["limited_environment", "trial_operation",
                  "evaluation", "expansion", "full_deployment"]
    ],
    "current_stage": "trial_operation",
}
_OPT_REPORT = {
    "phase7_complete": True,
    "phase8_ready":    True,
    "summary": {"avg_optimization_index": 0.9119},
}


@pytest.fixture
def tmp_cycle_dir(tmp_path):
    kc = tmp_path / "knowledge_cycle"
    kc.mkdir()
    (kc / "learning_dataset.json").write_text(
        json.dumps({"total_entries": 48}), encoding="utf-8")
    (kc / "optimization_report.json").write_text(
        json.dumps(_OPT_REPORT), encoding="utf-8")
    return kc


@pytest.fixture
def tmp_phase8_dir(tmp_path, tmp_cycle_dir):
    p8 = tmp_path / "phase8"
    p8.mkdir()
    (p8 / "deployment_plan.json").write_text(json.dumps(_PLAN), encoding="utf-8")
    (p8 / "integration_report.json").write_text(json.dumps(_INTEG), encoding="utf-8")
    (p8 / "sync_log.json").write_text(json.dumps(_SYNC_LOG), encoding="utf-8")
    (p8 / "hitl_checkpoint_log.json").write_text(json.dumps(_HITL_LOG), encoding="utf-8")
    return p8


@pytest.fixture
def tester(tmp_path, tmp_cycle_dir, tmp_phase8_dir):
    return F9530DeploymentTestAndStabilization(
        plan_path=tmp_phase8_dir / "deployment_plan.json",
        cycle_dir=tmp_cycle_dir,
        phase8_dir=tmp_phase8_dir,
        summary_log=tmp_path / "summary.log",
    )


# ════════════════════════════════════════════════════════════════
# TestF9530_01 — Step 1: 全環境状態の統合
# ════════════════════════════════════════════════════════════════

class TestF9530_01_LoadAndIntegrate:

    def test_returns_dict(self, tester):
        assert isinstance(tester.step1_load_and_integrate(), dict)

    def test_all_loaded_true_when_all_present(self, tester):
        state = tester.step1_load_and_integrate()
        assert state["all_loaded"] is True

    def test_missing_inputs_empty_when_all_present(self, tester):
        state = tester.step1_load_and_integrate()
        assert state["missing_inputs"] == []

    def test_plan_is_dict(self, tester):
        state = tester.step1_load_and_integrate()
        assert isinstance(state["plan"], dict)

    def test_integration_is_dict(self, tester):
        state = tester.step1_load_and_integrate()
        assert isinstance(state["integration"], dict)

    def test_all_loaded_false_when_files_missing(self, tmp_path, tmp_cycle_dir):
        empty = tmp_path / "empty_phase8"
        empty.mkdir()
        d = F9530DeploymentTestAndStabilization(
            plan_path=empty / "deployment_plan.json",
            cycle_dir=tmp_cycle_dir,
            phase8_dir=empty,
        )
        state = d.step1_load_and_integrate()
        assert state["all_loaded"] is False
        assert len(state["missing_inputs"]) > 0

    def test_plan_has_io_integrity(self, tester):
        state = tester.step1_load_and_integrate()
        assert "io_integrity" in state["plan"]

    def test_integration_has_success(self, tester):
        state = tester.step1_load_and_integrate()
        assert "success" in state["integration"]


# ════════════════════════════════════════════════════════════════
# TestF9530_02 — Step 2: ロードテスト
# ════════════════════════════════════════════════════════════════

class TestF9530_02_LoadTest:

    @pytest.fixture
    def state(self, tester):
        return tester.step1_load_and_integrate()

    def test_returns_dict(self, tester, state):
        assert isinstance(tester.step2_load_test(state), dict)

    def test_requests_sent_equals_constant(self, tester, state):
        result = tester.step2_load_test(state)
        assert result["requests_sent"] == LOAD_TEST_REQUESTS

    def test_io_integrity_1_when_all_files_present(self, tester, state):
        result = tester.step2_load_test(state)
        assert result["io_integrity"] == 1.0

    def test_error_rate_0_when_integrity_ok(self, tester, state):
        result = tester.step2_load_test(state)
        assert result["error_rate"] == 0.0

    def test_load_test_passed_true_when_ok(self, tester, state):
        result = tester.step2_load_test(state)
        assert result["load_test_passed"] is True

    def test_requests_ok_equals_sent_when_no_errors(self, tester, state):
        result = tester.step2_load_test(state)
        assert result["requests_ok"] == LOAD_TEST_REQUESTS

    def test_load_test_fails_when_cycle_empty(self, tmp_path, tmp_phase8_dir):
        empty_cycle = tmp_path / "empty_cycle"
        empty_cycle.mkdir()
        d = F9530DeploymentTestAndStabilization(
            cycle_dir=empty_cycle,
            phase8_dir=tmp_phase8_dir,
        )
        state  = d.step1_load_and_integrate()
        result = d.step2_load_test(state)
        assert result["load_test_passed"] is False

    def test_has_avg_response_sec(self, tester, state):
        result = tester.step2_load_test(state)
        assert "avg_response_sec" in result


# ════════════════════════════════════════════════════════════════
# TestF9530_03 — Step 3: 異常監視
# ════════════════════════════════════════════════════════════════

class TestF9530_03_MonitorExceptions:

    @pytest.fixture
    def ok_load(self):
        return {
            "error_rate":    0.0,
            "io_integrity":  1.0,
            "load_test_passed": True,
        }

    @pytest.fixture
    def bad_load(self):
        return {
            "error_rate":    0.05,
            "io_integrity":  0.9,
            "load_test_passed": False,
        }

    def test_returns_dict(self, tester, ok_load):
        assert isinstance(tester.step3_monitor_exceptions(ok_load), dict)

    def test_no_exception_when_ok(self, tester, ok_load):
        result = tester.step3_monitor_exceptions(ok_load)
        assert result["exception_detected"] is False
        assert result["monitoring_ok"] is True

    def test_exception_detected_when_error_rate_high(self, tester, bad_load):
        result = tester.step3_monitor_exceptions(bad_load)
        assert result["exception_detected"] is True
        assert result["monitoring_ok"] is False

    def test_exception_count_0_when_ok(self, tester, ok_load):
        result = tester.step3_monitor_exceptions(ok_load)
        assert result["exception_count"] == 0

    def test_exception_count_positive_when_bad(self, tester, bad_load):
        result = tester.step3_monitor_exceptions(bad_load)
        assert result["exception_count"] >= 1

    def test_exception_entries_is_list(self, tester, ok_load):
        result = tester.step3_monitor_exceptions(ok_load)
        assert isinstance(result["exception_entries"], list)


# ════════════════════════════════════════════════════════════════
# TestF9530_04 — Step 4: 再現性テスト
# ════════════════════════════════════════════════════════════════

class TestF9530_04_ReproducibilityTest:

    @pytest.fixture
    def ok_load(self):
        return {
            "load_test_passed": True,
            "io_integrity": 1.0,
            "error_rate": 0.0,
        }

    @pytest.fixture
    def bad_load(self):
        return {
            "load_test_passed": False,
            "io_integrity": 0.5,
            "error_rate": 0.1,
        }

    def test_returns_dict(self, tester, ok_load):
        assert isinstance(tester.step4_reproducibility_test(ok_load), dict)

    def test_passed_true_when_load_ok_and_files_present(self, tester, ok_load):
        result = tester.step4_reproducibility_test(ok_load)
        assert result["passed"] is True

    def test_trial_count_equals_3(self, tester, ok_load):
        result = tester.step4_reproducibility_test(ok_load)
        assert result["trial_count"] == REPRO_TEST_COUNT
        assert len(result["trials"]) == REPRO_TEST_COUNT

    def test_repro_rate_1_when_all_pass(self, tester, ok_load):
        result = tester.step4_reproducibility_test(ok_load)
        assert result["repro_rate"] == 1.0

    def test_passed_false_when_load_failed(self, tester, bad_load):
        result = tester.step4_reproducibility_test(bad_load)
        assert result["passed"] is False

    def test_repro_rate_0_when_all_fail(self, tester, bad_load):
        result = tester.step4_reproducibility_test(bad_load)
        assert result["repro_rate"] == 0.0

    def test_trials_have_passed_key(self, tester, ok_load):
        result = tester.step4_reproducibility_test(ok_load)
        assert all("passed" in t for t in result["trials"])


# ════════════════════════════════════════════════════════════════
# TestF9530_05 — Step 5: 安定性評価
# ════════════════════════════════════════════════════════════════

class TestF9530_05_EvaluateStability:

    @pytest.fixture
    def all_ok_inputs(self, tester):
        state  = tester.step1_load_and_integrate()
        load_r = tester.step2_load_test(state)
        mon_r  = tester.step3_monitor_exceptions(load_r)
        repro_r = tester.step4_reproducibility_test(load_r)
        return state, load_r, mon_r, repro_r

    def test_returns_dict(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        assert isinstance(tester.step5_evaluate_stability(load_r, mon_r, repro_r, state), dict)

    def test_stable_when_all_criteria_met(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        result = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        assert result["stability_status"] == "stable"

    def test_overall_ok_true_when_stable(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        result = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        assert result["overall_ok"] is True

    def test_opt_score_above_threshold(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        result = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        assert result["opt_score"] >= OPT_SCORE_THRESHOLD

    def test_error_rate_below_threshold(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        result = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        assert result["error_rate"] <= ERROR_RATE_THRESHOLD

    def test_log_completeness_range(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        result = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        assert 0.0 <= result["log_completeness"] <= 1.0

    def test_has_criteria_met(self, tester, all_ok_inputs):
        state, load_r, mon_r, repro_r = all_ok_inputs
        result = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        assert "criteria_met" in result

    def test_critical_when_error_rate_high(self, tester, all_ok_inputs):
        state, _, mon_r, repro_r = all_ok_inputs
        bad_load = {
            "error_rate": 0.1, "io_integrity": 1.0,
            "load_test_passed": False, "requests_ok": 9, "requests_sent": 10,
        }
        bad_mon  = {"exception_detected": True, "exception_count": 1,
                    "exception_entries": ["err"], "monitoring_ok": False}
        result   = tester.step5_evaluate_stability(bad_load, bad_mon, repro_r, state)
        assert result["stability_status"] == "critical"
        assert result["overall_ok"] is False


# ════════════════════════════════════════════════════════════════
# TestF9530_06 — Step 6: HITL 最終承認
# ════════════════════════════════════════════════════════════════

class TestF9530_06_HitlFinalApproval:

    def test_returns_dict(self, tester):
        assert isinstance(tester.step6_set_hitl_final_approval(), dict)

    def test_stage_is_full_deployment(self, tester):
        result = tester.step6_set_hitl_final_approval()
        assert result["stage"] == "full_deployment"

    def test_status_is_pending(self, tester):
        result = tester.step6_set_hitl_final_approval()
        assert result["status"] == "pending"

    def test_hitl_final_log_created(self, tester, tmp_phase8_dir):
        tester.step6_set_hitl_final_approval()
        assert (tmp_phase8_dir / "hitl_final_approval_log.json").exists()

    def test_hitl_final_log_stage_is_full_deployment(self, tester, tmp_phase8_dir):
        tester.step6_set_hitl_final_approval()
        log = json.loads(
            (tmp_phase8_dir / "hitl_final_approval_log.json").read_text(encoding="utf-8"))
        assert log["stage"] == "full_deployment"

    def test_hitl_checkpoint_log_updated(self, tester, tmp_phase8_dir):
        tester.step6_set_hitl_final_approval()
        log = json.loads(
            (tmp_phase8_dir / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        assert log["current_stage"] == "full_deployment"

    def test_record_hitl_final_approval_approve(self, tester, tmp_phase8_dir):
        tester.step6_set_hitl_final_approval()
        tester.record_hitl_final_approval("full_deployment", "approve", "最終確認済み")
        log = json.loads(
            (tmp_phase8_dir / "hitl_final_approval_log.json").read_text(encoding="utf-8"))
        assert log["status"] == "approve"
        assert log["approved_at"] is not None

    def test_record_hitl_final_approval_reason(self, tester, tmp_phase8_dir):
        tester.step6_set_hitl_final_approval()
        tester.record_hitl_final_approval("full_deployment", "approve", "最終確認済み")
        log = json.loads(
            (tmp_phase8_dir / "hitl_final_approval_log.json").read_text(encoding="utf-8"))
        assert log["reason"] == "最終確認済み"


# ════════════════════════════════════════════════════════════════
# TestF9530_07 — Step 7: レポート生成
# ════════════════════════════════════════════════════════════════

class TestF9530_07_GenerateReports:

    @pytest.fixture
    def all_results(self, tester):
        state   = tester.step1_load_and_integrate()
        load_r  = tester.step2_load_test(state)
        mon_r   = tester.step3_monitor_exceptions(load_r)
        repro_r = tester.step4_reproducibility_test(load_r)
        stab    = tester.step5_evaluate_stability(load_r, mon_r, repro_r, state)
        hitl_i  = tester.step6_set_hitl_final_approval()
        return state, load_r, mon_r, repro_r, stab, hitl_i

    def test_returns_tuple_of_two_dicts(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        sr, ds = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert isinstance(sr, dict) and isinstance(ds, dict)

    def test_stability_report_success_true(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        sr, _ = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert sr["success"] is True

    def test_deployment_summary_phase8_complete_true(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        _, ds = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert ds["phase8_complete"] is True

    def test_deployment_summary_stage_full_deployment(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        _, ds = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert ds["phase8_stage"] == "full_deployment"

    def test_stability_report_has_f9510_f9520_summaries(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        _, ds = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert "f9510_summary" in ds and "f9520_summary" in ds

    def test_stability_report_has_load_test(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        sr, _ = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert "load_test" in sr

    def test_stability_report_has_stability_log(self, tester, all_results):
        state, load_r, mon_r, repro_r, stab, hitl_i = all_results
        sr, _ = tester.step7_generate_reports(
            state, load_r, mon_r, repro_r, stab, hitl_i)
        assert "stability_log" in sr
        assert isinstance(sr["stability_log"], list)


# ════════════════════════════════════════════════════════════════
# TestF9530_08 — Step 8 / run() / 出力ファイル
# ════════════════════════════════════════════════════════════════

class TestF9530_08_RunAndOutputFiles:

    def test_run_returns_dict(self, tester):
        assert isinstance(tester.run(), dict)

    def test_run_success_true(self, tester):
        assert tester.run()["success"] is True

    def test_phase8_complete_true(self, tester):
        assert tester.run()["phase8_complete"] is True

    def test_phase8_stage_full_deployment(self, tester):
        assert tester.run()["phase8_stage"] == "full_deployment"

    def test_stability_report_created(self, tester, tmp_phase8_dir):
        tester.run()
        assert (tmp_phase8_dir / "stability_report.json").exists()

    def test_stability_report_success_true(self, tester, tmp_phase8_dir):
        tester.run()
        report = json.loads(
            (tmp_phase8_dir / "stability_report.json").read_text(encoding="utf-8"))
        assert report["success"] is True

    def test_deployment_summary_created(self, tester, tmp_phase8_dir):
        tester.run()
        assert (tmp_phase8_dir / "deployment_summary.json").exists()

    def test_deployment_summary_phase8_complete_true(self, tester, tmp_phase8_dir):
        tester.run()
        ds = json.loads(
            (tmp_phase8_dir / "deployment_summary.json").read_text(encoding="utf-8"))
        assert ds["phase8_complete"] is True

    def test_hitl_final_approval_log_created(self, tester, tmp_phase8_dir):
        tester.run()
        assert (tmp_phase8_dir / "hitl_final_approval_log.json").exists()

    def test_hitl_final_approval_log_approved(self, tester, tmp_phase8_dir):
        tester.run()
        log = json.loads(
            (tmp_phase8_dir / "hitl_final_approval_log.json").read_text(encoding="utf-8"))
        assert log["status"] == "approve"

    def test_phase8_complete_flag_created(self, tester, tmp_phase8_dir):
        tester.run()
        assert (tmp_phase8_dir / "phase8_complete_flag").exists()

    def test_phase8_complete_flag_content(self, tester, tmp_phase8_dir):
        tester.run()
        content = (tmp_phase8_dir / "phase8_complete_flag").read_text(encoding="utf-8")
        assert "phase8_complete: true" in content

    def test_deployment_trace_updated(self, tester, tmp_phase8_dir):
        tester.run()
        trace = json.loads(
            (tmp_phase8_dir / "deployment_trace.json").read_text(encoding="utf-8"))
        assert "full_deployment" in trace["stages"]

    def test_trace_phase8_complete_true(self, tester, tmp_phase8_dir):
        tester.run()
        trace = json.loads(
            (tmp_phase8_dir / "deployment_trace.json").read_text(encoding="utf-8"))
        assert trace["phase8_complete"] is True

    def test_trace_f9530_entry(self, tester, tmp_phase8_dir):
        tester.run()
        trace = json.loads(
            (tmp_phase8_dir / "deployment_trace.json").read_text(encoding="utf-8"))
        entry = trace["stages"]["full_deployment"]["f9530_entry"]
        assert "F9530 executed successfully" in entry

    def test_load_stability_report_returns_dict(self, tester):
        tester.run()
        loaded = tester.load_stability_report()
        assert isinstance(loaded, dict)

    def test_load_deployment_summary_returns_dict(self, tester):
        tester.run()
        loaded = tester.load_deployment_summary()
        assert isinstance(loaded, dict)

    def test_load_nonexistent_stability_report(self, tmp_path):
        d = F9530DeploymentTestAndStabilization(phase8_dir=tmp_path / "ph8")
        assert d.load_stability_report() == {}

    def test_load_nonexistent_deployment_summary(self, tmp_path):
        d = F9530DeploymentTestAndStabilization(phase8_dir=tmp_path / "ph8")
        assert d.load_deployment_summary() == {}

    def test_write_summary_entry_creates_log(self, tester, tmp_path):
        result = tester.run()
        log    = tmp_path / "summary.log"
        tester.write_summary_entry(result, log_path=log)
        assert log.exists()

    def test_summary_entry_has_f9530(self, tester, tmp_path):
        result = tester.run()
        log    = tmp_path / "summary.log"
        tester.write_summary_entry(result, log_path=log)
        assert "F9530" in log.read_text(encoding="utf-8")

    def test_summary_entry_phase8_complete_true(self, tester, tmp_path):
        result = tester.run()
        log    = tmp_path / "summary.log"
        tester.write_summary_entry(result, log_path=log)
        assert "phase8_complete" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_phase9(self, tester, tmp_path):
        result = tester.run()
        log    = tmp_path / "summary.log"
        tester.write_summary_entry(result, log_path=log)
        assert "Phase 9" in log.read_text(encoding="utf-8")

    def test_hitl_fn_reject_aborts(self, tester):
        result = tester.run(hitl_fn=lambda: "reject")
        assert result["success"] is False
        assert result["phase8_complete"] is False


# ════════════════════════════════════════════════════════════════
# TestF9530_09 — エラー / ロールバックシナリオ
# ════════════════════════════════════════════════════════════════

class TestF9530_09_ErrorAndRollback:

    def test_run_fails_when_cycle_dir_empty(self, tmp_path, tmp_phase8_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9530DeploymentTestAndStabilization(
            cycle_dir=empty,
            phase8_dir=tmp_phase8_dir,
        )
        result = d.run()
        assert result["success"] is False
        assert result["phase8_complete"] is False

    def test_stability_report_created_on_failure(self, tmp_path, tmp_phase8_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9530DeploymentTestAndStabilization(
            cycle_dir=empty,
            phase8_dir=tmp_phase8_dir,
        )
        d.run()
        assert (tmp_phase8_dir / "stability_report.json").exists()

    def test_deployment_summary_created_on_failure(self, tmp_path, tmp_phase8_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9530DeploymentTestAndStabilization(
            cycle_dir=empty,
            phase8_dir=tmp_phase8_dir,
        )
        d.run()
        assert (tmp_phase8_dir / "deployment_summary.json").exists()

    def test_rollback_log_updated_on_io_failure(self, tmp_path, tmp_phase8_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9530DeploymentTestAndStabilization(
            cycle_dir=empty,
            phase8_dir=tmp_phase8_dir,
        )
        d.run()
        log = json.loads(
            (tmp_phase8_dir / "rollback_log.json").read_text(encoding="utf-8"))
        assert log["total_events"] >= 1

    def test_validation_error_json_on_io_failure(self, tmp_path, tmp_phase8_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9530DeploymentTestAndStabilization(
            cycle_dir=empty,
            phase8_dir=tmp_phase8_dir,
        )
        d.run()
        assert (tmp_phase8_dir / "validation_error.json").exists()

    def test_step8_write_complete_flag_true(self, tester, tmp_phase8_dir):
        ds = {"phase8_complete": True, "phase8_stage": "full_deployment"}
        tester.step8_write_complete_flag(ds)
        content = (tmp_phase8_dir / "phase8_complete_flag").read_text(encoding="utf-8")
        assert "phase8_complete: true" in content

    def test_step8_write_complete_flag_false(self, tester, tmp_phase8_dir):
        ds = {"phase8_complete": False, "phase8_stage": "full_deployment"}
        tester.step8_write_complete_flag(ds)
        content = (tmp_phase8_dir / "phase8_complete_flag").read_text(encoding="utf-8")
        assert "phase8_complete: false" in content
