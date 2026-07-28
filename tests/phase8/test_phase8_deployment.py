"""Phase 8 展開層テスト
Phase 8：展開層（Deployment Layer）

テスト対象:
  - src/deployment/phase8_deployer.py
    - Phase8DeploymentManager.load_phase7_artifacts()
    - Phase8DeploymentManager.load_spec()
    - Phase8DeploymentManager.validate_start_conditions()
    - Phase8DeploymentManager.execute_f9510()
    - Phase8DeploymentManager.execute_f9520()
    - Phase8DeploymentManager.execute_f9530()
    - Phase8DeploymentManager.check_abort_conditions()
    - Phase8DeploymentManager.rollback()
    - Phase8DeploymentManager.run_full_deployment()
    - Phase8DeploymentManager.save_deployment_trace()
    - Phase8DeploymentManager.save_rollback_log()
    - Phase8DeploymentManager.write_phase8_complete_flag()
    - Phase8DeploymentManager.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.deployment.phase8_deployer import (
    Phase8DeploymentManager,
    STAGES,
    OPT_SCORE_THRESHOLD,
)


# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_artifacts():
    """Phase 7 成果物の最小モック。"""
    return {
        "dataset": {
            "total_entries": 48,
            "category_counts": {"operational": 38, "improvement": 5,
                                  "maintenance": 1, "environment": 4},
        },
        "patterns": {
            "total_patterns": 48,
            "average_score": 0.975,
        },
        "optimization_report": {
            "phase7_complete": True,
            "phase8_ready": True,
            "summary": {
                "avg_optimization_index": 0.9119,
                "overall_status": "critical",
                "status_distribution": {"stable": 43, "warning": 1, "critical": 4},
            },
        },
        "all_present": True,
        "missing": [],
    }


@pytest.fixture
def manager(tmp_path):
    return Phase8DeploymentManager(
        cycle_dir=tmp_path / "knowledge_cycle",
        phase8_dir=tmp_path / "phase8",
        summary_log=tmp_path / "summary.log",
    )


@pytest.fixture
def manager_with_artifacts(tmp_path, mock_artifacts):
    """実ファイルを用意した manager。"""
    kc_dir  = tmp_path / "knowledge_cycle"
    kc_dir.mkdir(parents=True)
    (kc_dir / "learning_dataset.json").write_text(
        json.dumps(mock_artifacts["dataset"]), encoding="utf-8")
    (kc_dir / "learning_patterns.json").write_text(
        json.dumps(mock_artifacts["patterns"]), encoding="utf-8")
    (kc_dir / "optimization_report.json").write_text(
        json.dumps(mock_artifacts["optimization_report"]), encoding="utf-8")
    return Phase8DeploymentManager(
        cycle_dir=kc_dir,
        phase8_dir=tmp_path / "phase8",
        summary_log=tmp_path / "summary.log",
    )


# ════════════════════════════════════════════════════════════════
# TestPH8_01 — Phase 7 成果物読み込み
# ════════════════════════════════════════════════════════════════

class TestPH8_01_ArtifactLoading:

    def test_load_artifacts_returns_dict(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert isinstance(result, dict)

    def test_load_artifacts_has_all_present_flag(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert "all_present" in result

    def test_load_artifacts_all_present_true_when_files_exist(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert result["all_present"] is True

    def test_load_artifacts_missing_empty_when_all_present(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert result["missing"] == []

    def test_load_artifacts_has_dataset(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert "dataset" in result and result["dataset"]

    def test_load_artifacts_has_patterns(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert "patterns" in result and result["patterns"]

    def test_load_artifacts_has_optimization_report(self, manager_with_artifacts):
        result = manager_with_artifacts.load_phase7_artifacts()
        assert "optimization_report" in result and result["optimization_report"]

    def test_load_artifacts_missing_files_reported(self, manager):
        result = manager.load_phase7_artifacts()
        assert result["all_present"] is False
        assert len(result["missing"]) > 0


# ════════════════════════════════════════════════════════════════
# TestPH8_02 — 開始条件検証
# ════════════════════════════════════════════════════════════════

class TestPH8_02_StartConditions:

    def test_limited_env_ok_with_full_artifacts(self, manager, mock_artifacts):
        result = manager.validate_start_conditions("limited_environment", {}, mock_artifacts)
        assert result["ok"] is True

    def test_limited_env_fails_without_phase7_complete(self, manager, mock_artifacts):
        mock_artifacts["optimization_report"]["phase7_complete"] = False
        result = manager.validate_start_conditions("limited_environment", {}, mock_artifacts)
        assert result["ok"] is False

    def test_trial_operation_requires_prev_hitl(self, manager, mock_artifacts):
        # 前ステージ HITL 未承認
        state  = {"limited_environment": {"hitl": "reject"}}
        result = manager.validate_start_conditions("trial_operation", state, mock_artifacts)
        assert result["ok"] is False

    def test_trial_operation_ok_after_approval(self, manager, mock_artifacts):
        state  = {"limited_environment": {"hitl": "approve"}}
        result = manager.validate_start_conditions("trial_operation", state, mock_artifacts)
        assert result["ok"] is True

    def test_evaluation_requires_trial_approval(self, manager, mock_artifacts):
        state  = {"trial_operation": {"hitl": "reject"}}
        result = manager.validate_start_conditions("evaluation", state, mock_artifacts)
        assert result["ok"] is False

    def test_expansion_requires_evaluation_approval(self, manager, mock_artifacts):
        state  = {"evaluation": {"hitl": "approve"}}
        result = manager.validate_start_conditions("expansion", state, mock_artifacts)
        assert result["ok"] is True

    def test_full_deployment_requires_expansion_approval(self, manager, mock_artifacts):
        state  = {"expansion": {"hitl": "approve"}}
        result = manager.validate_start_conditions("full_deployment", state, mock_artifacts)
        assert result["ok"] is True

    def test_returns_satisfied_and_failed_lists(self, manager, mock_artifacts):
        result = manager.validate_start_conditions("limited_environment", {}, mock_artifacts)
        assert isinstance(result["satisfied"], list)
        assert isinstance(result["failed"], list)


# ════════════════════════════════════════════════════════════════
# TestPH8_03 — F9510 deployment_plan_design
# ════════════════════════════════════════════════════════════════

class TestPH8_03_F9510:

    def test_returns_dict(self, manager, mock_artifacts):
        assert isinstance(manager.execute_f9510(mock_artifacts), dict)

    def test_module_is_f9510(self, manager, mock_artifacts):
        result = manager.execute_f9510(mock_artifacts)
        assert result["module"] == "F9510"

    def test_success_when_all_present(self, manager, mock_artifacts):
        result = manager.execute_f9510(mock_artifacts)
        assert result["success"] is True

    def test_io_integrity_100_when_all_present(self, manager, mock_artifacts):
        result = manager.execute_f9510(mock_artifacts)
        assert result["io_integrity"] == 100.0

    def test_io_integrity_0_when_missing(self, manager, mock_artifacts):
        mock_artifacts["all_present"] = False
        mock_artifacts["missing"]     = ["learning_dataset.json"]
        result = manager.execute_f9510(mock_artifacts)
        assert result["io_integrity"] == 0.0

    def test_log_output_normal(self, manager, mock_artifacts):
        result = manager.execute_f9510(mock_artifacts)
        assert result["log_output"] == "normal"

    def test_plan_has_stages(self, manager, mock_artifacts):
        result = manager.execute_f9510(mock_artifacts)
        assert result["plan"]["stage_sequence"] == STAGES

    def test_plan_has_hitl_checkpoints(self, manager, mock_artifacts):
        result = manager.execute_f9510(mock_artifacts)
        assert result["plan"]["hitl_checkpoints"] == STAGES


# ════════════════════════════════════════════════════════════════
# TestPH8_04 — F9520 support_agent_integration
# ════════════════════════════════════════════════════════════════

class TestPH8_04_F9520:

    def test_returns_dict(self, manager, mock_artifacts):
        assert isinstance(manager.execute_f9520({}, mock_artifacts), dict)

    def test_module_is_f9520(self, manager, mock_artifacts):
        result = manager.execute_f9520({}, mock_artifacts)
        assert result["module"] == "F9520"

    def test_failure_repository_sync_success(self, manager, mock_artifacts):
        result = manager.execute_f9520({}, mock_artifacts)
        assert result["failure_repository_sync"] == "success"

    def test_knowledge_cycle_update_success(self, manager, mock_artifacts):
        result = manager.execute_f9520({}, mock_artifacts)
        assert result["knowledge_cycle_update"] == "success"

    def test_reproducibility_3_runs(self, manager, mock_artifacts):
        result = manager.execute_f9520({}, mock_artifacts)
        assert result["reproducibility_test"]["runs"] == 3

    def test_reproducibility_test_passed(self, manager, mock_artifacts):
        result = manager.execute_f9520({}, mock_artifacts)
        assert result["reproducibility_test"]["passed"] is True

    def test_success_when_repro_passed(self, manager, mock_artifacts):
        result = manager.execute_f9520({}, mock_artifacts)
        assert result["success"] is True


# ════════════════════════════════════════════════════════════════
# TestPH8_05 — F9530 deployment_test_and_stabilization
# ════════════════════════════════════════════════════════════════

class TestPH8_05_F9530:

    def test_returns_dict(self, manager, mock_artifacts):
        assert isinstance(manager.execute_f9530({}, mock_artifacts), dict)

    def test_module_is_f9530(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["module"] == "F9530"

    def test_load_test_passed(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["load_test"]["passed"] is True

    def test_rollback_test_passed(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["rollback_test"]["passed"] is True

    def test_error_rate_within_threshold(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["error_rate"] <= 0.05

    def test_opt_score_above_threshold(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["opt_score"] >= OPT_SCORE_THRESHOLD

    def test_all_logs_saved(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["all_logs_saved"] is True

    def test_success_true(self, manager, mock_artifacts):
        result = manager.execute_f9530({}, mock_artifacts)
        assert result["success"] is True


# ════════════════════════════════════════════════════════════════
# TestPH8_06 — 中断・ロールバック条件
# ════════════════════════════════════════════════════════════════

class TestPH8_06_AbortRollback:

    def test_check_abort_false_on_success(self, manager):
        assert manager.check_abort_conditions({"success": True, "io_integrity": 100.0}) is False

    def test_check_abort_true_on_failure(self, manager):
        assert manager.check_abort_conditions({"success": False}) is True

    def test_check_abort_true_on_io_failure(self, manager):
        assert manager.check_abort_conditions({"success": True, "io_integrity": 0.0}) is True

    def test_check_abort_true_on_high_error_rate(self, manager):
        assert manager.check_abort_conditions({"error_rate": 0.10}) is True

    def test_rollback_returns_event(self, manager):
        trace  = {"stages": {}, "rollback_events": []}
        event  = manager.rollback("trial_operation", trace)
        assert isinstance(event, dict)

    def test_rollback_sets_from_stage(self, manager):
        trace = {"rollback_events": []}
        event = manager.rollback("trial_operation", trace)
        assert event["from_stage"] == "trial_operation"

    def test_rollback_sets_prev_stage(self, manager):
        trace = {"rollback_events": []}
        event = manager.rollback("trial_operation", trace)
        assert event["to_stage"] == "limited_environment"

    def test_rollback_appended_to_trace(self, manager):
        trace = {"rollback_events": []}
        manager.rollback("evaluation", trace)
        assert len(trace["rollback_events"]) == 1

    def test_rollback_first_stage_goes_to_pre_deployment(self, manager):
        trace = {"rollback_events": []}
        event = manager.rollback("limited_environment", trace)
        assert event["to_stage"] == "pre_deployment"


# ════════════════════════════════════════════════════════════════
# TestPH8_07 — フルデプロイメント実行
# ════════════════════════════════════════════════════════════════

class TestPH8_07_RunFullDeployment:

    def test_returns_dict(self, manager, mock_artifacts):
        trace = manager.run_full_deployment(artifacts=mock_artifacts)
        assert isinstance(trace, dict)

    def test_phase8_complete_when_all_approved(self, manager, mock_artifacts):
        trace = manager.run_full_deployment(artifacts=mock_artifacts)
        assert trace["phase8_complete"] is True

    def test_all_stages_completed(self, manager, mock_artifacts):
        trace = manager.run_full_deployment(artifacts=mock_artifacts)
        for stage in STAGES:
            assert stage in trace["stages"]
            assert trace["stages"][stage]["status"] == "completed"

    def test_all_stages_have_hitl_approve(self, manager, mock_artifacts):
        trace = manager.run_full_deployment(artifacts=mock_artifacts)
        for stage in STAGES:
            assert trace["stages"][stage]["hitl"] == "approve"

    def test_no_rollback_events_on_success(self, manager, mock_artifacts):
        trace = manager.run_full_deployment(artifacts=mock_artifacts)
        assert trace["rollback_events"] == []

    def test_abort_when_hitl_rejects(self, manager, mock_artifacts):
        def reject_first(stage):
            return "reject" if stage == "limited_environment" else "approve"
        trace = manager.run_full_deployment(hitl_fn=reject_first, artifacts=mock_artifacts)
        assert trace["phase8_complete"] is False

    def test_rollback_event_on_hitl_abort(self, manager, mock_artifacts):
        def abort_at_trial(stage):
            return "abort" if stage == "trial_operation" else "approve"
        trace = manager.run_full_deployment(hitl_fn=abort_at_trial, artifacts=mock_artifacts)
        assert len(trace["rollback_events"]) > 0

    def test_abort_reason_set_on_failure(self, manager, mock_artifacts):
        def reject_all(stage):
            return "reject"
        trace = manager.run_full_deployment(hitl_fn=reject_all, artifacts=mock_artifacts)
        assert trace["abort_reason"] is not None

    def test_phase8_false_when_no_artifacts(self, manager):
        empty_arts = {"dataset": {}, "patterns": {}, "optimization_report": {},
                      "all_present": False, "missing": ["all"]}
        trace = manager.run_full_deployment(artifacts=empty_arts)
        assert trace["phase8_complete"] is False


# ════════════════════════════════════════════════════════════════
# TestPH8_08 — 出力ファイル保存
# ════════════════════════════════════════════════════════════════

class TestPH8_08_OutputFiles:

    @pytest.fixture
    def complete_trace(self, manager, mock_artifacts):
        return manager.run_full_deployment(artifacts=mock_artifacts)

    def test_save_deployment_trace_creates_file(self, manager, complete_trace, tmp_path):
        p = tmp_path / "trace.json"
        manager.save_deployment_trace(complete_trace, path=p)
        assert p.exists()

    def test_saved_trace_is_valid_json(self, manager, complete_trace, tmp_path):
        p = tmp_path / "trace.json"
        manager.save_deployment_trace(complete_trace, path=p)
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert loaded["phase"] == 8

    def test_save_rollback_log_creates_file(self, manager, complete_trace, tmp_path):
        p = tmp_path / "rollback.json"
        manager.save_rollback_log(complete_trace["rollback_events"], path=p)
        assert p.exists()

    def test_rollback_log_has_total_events(self, manager, complete_trace, tmp_path):
        p = tmp_path / "rollback.json"
        manager.save_rollback_log(complete_trace["rollback_events"], path=p)
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert "total_events" in loaded

    def test_complete_flag_created_when_phase8_complete(self, manager, complete_trace, tmp_path):
        p = tmp_path / "phase8_complete_flag"
        manager.write_phase8_complete_flag(complete_trace, path=p)
        assert p.exists()

    def test_complete_flag_not_created_when_incomplete(self, manager, mock_artifacts, tmp_path):
        trace = manager.run_full_deployment(
            hitl_fn=lambda s: "reject", artifacts=mock_artifacts)
        p = tmp_path / "phase8_complete_flag"
        manager.write_phase8_complete_flag(trace, path=p)
        assert not p.exists()

    def test_complete_flag_contains_true(self, manager, complete_trace, tmp_path):
        p = tmp_path / "phase8_complete_flag"
        manager.write_phase8_complete_flag(complete_trace, path=p)
        assert "phase8_complete=True" in p.read_text(encoding="utf-8")

    def test_write_summary_entry_creates_log(self, manager, complete_trace, tmp_path):
        log = tmp_path / "summary.log"
        manager.write_summary_entry(complete_trace, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_phase8(self, manager, complete_trace, tmp_path):
        log = tmp_path / "summary.log"
        manager.write_summary_entry(complete_trace, log_path=log)
        assert "Phase 8" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_complete_when_success(self, manager, complete_trace, tmp_path):
        log = tmp_path / "summary.log"
        manager.write_summary_entry(complete_trace, log_path=log)
        assert "完了" in log.read_text(encoding="utf-8")
