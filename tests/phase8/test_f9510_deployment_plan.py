"""F9510 deployment_plan_design テスト
Phase 8：展開層

テスト対象:
  - src/deployment/f9510_deployment_plan.py
    - F9510DeploymentPlanDesigner.step1_load_spec()
    - F9510DeploymentPlanDesigner.step2_register_conditions()
    - F9510DeploymentPlanDesigner.step3_check_io_integrity()
    - F9510DeploymentPlanDesigner.step4_initialize_logging()
    - F9510DeploymentPlanDesigner.step5_mark_hitl_points()
    - F9510DeploymentPlanDesigner.step6_init_rollback()
    - F9510DeploymentPlanDesigner.step7_validate_consistency()
    - F9510DeploymentPlanDesigner.step8_generate_plan()
    - F9510DeploymentPlanDesigner.run()
    - F9510DeploymentPlanDesigner.save_deployment_plan()
    - F9510DeploymentPlanDesigner.load_deployment_plan()
    - F9510DeploymentPlanDesigner.record_hitl_approval()
    - F9510DeploymentPlanDesigner.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.deployment.f9510_deployment_plan import (
    F9510DeploymentPlanDesigner,
    REQUIRED_STAGES,
    DEFAULT_ROLLBACK_POLICY,
)


# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

_SPEC_CONTENT = {
    "phase8": {
        "version": "2026-07-23",
        "deployment_stages": REQUIRED_STAGES,
        "stage_details": {
            s: {
                "start_conditions":      [f"{s}_start_cond"],
                "completion_conditions": [f"{s}_complete_cond"],
            }
            for s in REQUIRED_STAGES
        },
        "hitl_points": {"required": REQUIRED_STAGES},
        "rollback_policy": {
            "strategy": "step_back_one_stage",
            "log_file":  "rollback_log.json",
        },
        "io_map": {
            "inputs":  ["learning_dataset.json", "learning_patterns.json", "optimization_report.json"],
            "outputs": ["deployment_plan.json", "deployment_trace.json", "hitl_checkpoint_log.json"],
        },
    }
}

_OPT_REPORT = {
    "phase7_complete": True,
    "phase8_ready":    True,
    "summary": {"avg_optimization_index": 0.9119},
}


@pytest.fixture
def tmp_cycle_dir(tmp_path):
    """Phase 7 成果物を配置した一時ディレクトリ。"""
    kc = tmp_path / "knowledge_cycle"
    kc.mkdir()
    (kc / "learning_dataset.json").write_text(
        json.dumps({"total_entries": 48}), encoding="utf-8")
    (kc / "learning_patterns.json").write_text(
        json.dumps({"total_patterns": 48}), encoding="utf-8")
    (kc / "optimization_report.json").write_text(
        json.dumps(_OPT_REPORT), encoding="utf-8")
    return kc


@pytest.fixture
def tmp_spec(tmp_path):
    p = tmp_path / "phase8" / "phase8_spec.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_SPEC_CONTENT), encoding="utf-8")
    return p


@pytest.fixture
def designer(tmp_path, tmp_cycle_dir, tmp_spec):
    return F9510DeploymentPlanDesigner(
        spec_path=tmp_spec,
        cycle_dir=tmp_cycle_dir,
        phase8_dir=tmp_path / "phase8",
        summary_log=tmp_path / "summary.log",
    )


# ════════════════════════════════════════════════════════════════
# TestF9510_01 — Step 1: 展開仕様読み込み
# ════════════════════════════════════════════════════════════════

class TestF9510_01_LoadSpec:

    def test_returns_dict(self, designer):
        assert isinstance(designer.step1_load_spec(), dict)

    def test_has_deployment_stages(self, designer):
        spec = designer.step1_load_spec()
        assert "deployment_stages" in spec

    def test_has_5_stages(self, designer):
        spec = designer.step1_load_spec()
        assert len(spec["deployment_stages"]) == 5

    def test_has_stage_details(self, designer):
        spec = designer.step1_load_spec()
        assert "stage_details" in spec

    def test_has_hitl_points(self, designer):
        spec = designer.step1_load_spec()
        assert "hitl_points" in spec

    def test_missing_spec_returns_empty(self, tmp_path):
        d = F9510DeploymentPlanDesigner(
            spec_path=tmp_path / "no_spec.json",
            cycle_dir=tmp_path,
            phase8_dir=tmp_path,
        )
        assert d.step1_load_spec() == {}


# ════════════════════════════════════════════════════════════════
# TestF9510_02 — Step 2: 開始/完了条件の登録
# ════════════════════════════════════════════════════════════════

class TestF9510_02_RegisterConditions:

    def test_returns_dict(self, designer):
        spec = designer.step1_load_spec()
        assert isinstance(designer.step2_register_conditions(spec), dict)

    def test_has_all_stages(self, designer):
        spec       = designer.step1_load_spec()
        conditions = designer.step2_register_conditions(spec)
        for stage in REQUIRED_STAGES:
            assert stage in conditions

    def test_each_stage_has_start(self, designer):
        spec       = designer.step1_load_spec()
        conditions = designer.step2_register_conditions(spec)
        for stage in REQUIRED_STAGES:
            assert "start" in conditions[stage]

    def test_each_stage_has_completion(self, designer):
        spec       = designer.step1_load_spec()
        conditions = designer.step2_register_conditions(spec)
        for stage in REQUIRED_STAGES:
            assert "completion" in conditions[stage]

    def test_limited_env_start_conditions_not_empty(self, designer):
        spec       = designer.step1_load_spec()
        conditions = designer.step2_register_conditions(spec)
        assert len(conditions["limited_environment"]["start"]) > 0


# ════════════════════════════════════════════════════════════════
# TestF9510_03 — Step 3: I/O 整合性チェック
# ════════════════════════════════════════════════════════════════

class TestF9510_03_IoIntegrity:

    def test_returns_dict(self, designer):
        assert isinstance(designer.step3_check_io_integrity(), dict)

    def test_integrity_100_when_all_files_exist(self, designer):
        result = designer.step3_check_io_integrity()
        assert result["integrity"] == 100.0

    def test_ok_true_when_all_present_and_phase7_complete(self, designer):
        result = designer.step3_check_io_integrity()
        assert result["ok"] is True

    def test_phase7_complete_true(self, designer):
        result = designer.step3_check_io_integrity()
        assert result["phase7_complete"] is True

    def test_missing_list_empty_when_all_present(self, designer):
        result = designer.step3_check_io_integrity()
        assert result["missing"] == []

    def test_integrity_0_when_no_files(self, tmp_path):
        empty_dir = tmp_path / "empty_cycle"
        empty_dir.mkdir()
        d = F9510DeploymentPlanDesigner(cycle_dir=empty_dir, phase8_dir=tmp_path)
        result = d.step3_check_io_integrity()
        assert result["integrity"] == 0.0

    def test_hitl_required_false_when_ok(self, designer):
        result = designer.step3_check_io_integrity()
        assert result["hitl_required"] is False

    def test_hitl_required_true_when_missing(self, tmp_path):
        empty_dir = tmp_path / "empty_cycle"
        empty_dir.mkdir()
        d = F9510DeploymentPlanDesigner(cycle_dir=empty_dir, phase8_dir=tmp_path)
        result = d.step3_check_io_integrity()
        assert result["hitl_required"] is True


# ════════════════════════════════════════════════════════════════
# TestF9510_04 — Step 4: ログ初期化
# ════════════════════════════════════════════════════════════════

class TestF9510_04_InitLogging:

    def test_returns_string(self, designer):
        io_r = designer.step3_check_io_integrity()
        assert isinstance(designer.step4_initialize_logging(io_r), str)

    def test_normal_when_ok(self, designer):
        io_r = designer.step3_check_io_integrity()
        assert designer.step4_initialize_logging(io_r) == "normal"

    def test_error_when_no_files(self, tmp_path):
        d = F9510DeploymentPlanDesigner(
            cycle_dir=tmp_path / "empty", phase8_dir=tmp_path)
        (tmp_path / "empty").mkdir()
        io_r = d.step3_check_io_integrity()
        status = d.step4_initialize_logging(io_r)
        assert status == "error"

    def test_warning_when_partial(self, tmp_path, tmp_cycle_dir):
        """1ファイルのみ存在する場合は warning。"""
        partial = tmp_path / "partial_cycle"
        partial.mkdir()
        (partial / "learning_dataset.json").write_text("{}", encoding="utf-8")
        d  = F9510DeploymentPlanDesigner(cycle_dir=partial, phase8_dir=tmp_path)
        io_r = d.step3_check_io_integrity()
        assert d.step4_initialize_logging(io_r) == "warning"


# ════════════════════════════════════════════════════════════════
# TestF9510_05 — Step 5: HITL ポイントのマーキング
# ════════════════════════════════════════════════════════════════

class TestF9510_05_MarkHitlPoints:

    def test_returns_list(self, designer):
        spec = designer.step1_load_spec()
        assert isinstance(designer.step5_mark_hitl_points(spec), list)

    def test_5_hitl_points(self, designer):
        spec    = designer.step1_load_spec()
        points  = designer.step5_mark_hitl_points(spec)
        assert len(points) == 5

    def test_all_stages_are_hitl_points(self, designer):
        spec   = designer.step1_load_spec()
        points = designer.step5_mark_hitl_points(spec)
        assert set(points) == set(REQUIRED_STAGES)

    def test_fallback_to_required_stages_when_missing(self, designer):
        points = designer.step5_mark_hitl_points({})
        assert points == REQUIRED_STAGES


# ════════════════════════════════════════════════════════════════
# TestF9510_06 — Step 6: rollback_policy 初期化
# ════════════════════════════════════════════════════════════════

class TestF9510_06_InitRollback:

    def test_returns_dict(self, designer):
        spec = designer.step1_load_spec()
        assert isinstance(designer.step6_init_rollback(spec), dict)

    def test_strategy_is_step_back(self, designer):
        spec   = designer.step1_load_spec()
        policy = designer.step6_init_rollback(spec)
        assert policy["strategy"] == "step_back_one_stage"

    def test_rollback_log_created(self, designer, tmp_path):
        spec = designer.step1_load_spec()
        designer.step6_init_rollback(spec)
        assert (tmp_path / "phase8" / "rollback_log.json").exists()

    def test_default_policy_applied_when_missing(self, designer):
        policy = designer.step6_init_rollback({})
        assert policy == DEFAULT_ROLLBACK_POLICY

    def test_rollback_log_has_events_list(self, designer, tmp_path):
        spec = designer.step1_load_spec()
        designer.step6_init_rollback(spec)
        log = json.loads(
            (tmp_path / "phase8" / "rollback_log.json").read_text(encoding="utf-8"))
        assert "rollback_events" in log


# ════════════════════════════════════════════════════════════════
# TestF9510_07 — Step 7: 整合性検証
# ════════════════════════════════════════════════════════════════

class TestF9510_07_ValidateConsistency:

    @pytest.fixture
    def valid_inputs(self, designer):
        spec    = designer.step1_load_spec()
        io_r    = designer.step3_check_io_integrity()
        hitl_pts = designer.step5_mark_hitl_points(spec)
        policy  = designer.step6_init_rollback(spec)
        return spec, io_r, hitl_pts, policy

    def test_valid_true_when_all_ok(self, designer, valid_inputs):
        spec, io_r, hitl_pts, policy = valid_inputs
        result = designer.step7_validate_consistency(spec, io_r, hitl_pts, policy)
        assert result["valid"] is True

    def test_errors_empty_when_valid(self, designer, valid_inputs):
        spec, io_r, hitl_pts, policy = valid_inputs
        result = designer.step7_validate_consistency(spec, io_r, hitl_pts, policy)
        assert result["errors"] == []

    def test_error_when_io_not_100(self, designer, valid_inputs):
        spec, io_r, hitl_pts, policy = valid_inputs
        io_r_bad = dict(io_r) | {"integrity": 66.7, "ok": False, "phase7_complete": True}
        result   = designer.step7_validate_consistency(spec, io_r_bad, hitl_pts, policy)
        assert result["valid"] is False
        assert any("io_integrity" in e for e in result["errors"])

    def test_error_when_hitl_not_5(self, designer, valid_inputs):
        spec, io_r, hitl_pts, policy = valid_inputs
        result = designer.step7_validate_consistency(spec, io_r, hitl_pts[:3], policy)
        assert result["valid"] is False

    def test_error_when_phase7_not_complete(self, designer, valid_inputs):
        spec, io_r, hitl_pts, policy = valid_inputs
        io_r_bad = dict(io_r) | {"phase7_complete": False, "ok": False}
        result   = designer.step7_validate_consistency(spec, io_r_bad, hitl_pts, policy)
        assert any("phase7_complete" in e for e in result["errors"])

    def test_error_when_wrong_rollback_strategy(self, designer, valid_inputs):
        spec, io_r, hitl_pts, policy = valid_inputs
        bad_policy = {"strategy": "full_reset"}
        result     = designer.step7_validate_consistency(spec, io_r, hitl_pts, bad_policy)
        assert result["valid"] is False


# ════════════════════════════════════════════════════════════════
# TestF9510_08 — Step 8 / run() / 出力ファイル
# ════════════════════════════════════════════════════════════════

class TestF9510_08_GeneratePlanAndRun:

    def test_run_returns_dict(self, designer):
        assert isinstance(designer.run(), dict)

    def test_run_success_true(self, designer):
        result = designer.run()
        assert result["success"] is True

    def test_deployment_plan_json_created(self, designer, tmp_path):
        designer.run()
        assert (tmp_path / "phase8" / "deployment_plan.json").exists()

    def test_deployment_plan_has_phase8_stage(self, designer, tmp_path):
        designer.run()
        plan = json.loads(
            (tmp_path / "phase8" / "deployment_plan.json").read_text(encoding="utf-8"))
        assert plan["phase8_stage"] == "limited_environment"

    def test_deployment_plan_io_integrity_100(self, designer, tmp_path):
        designer.run()
        plan = json.loads(
            (tmp_path / "phase8" / "deployment_plan.json").read_text(encoding="utf-8"))
        assert plan["io_integrity"] == 100.0

    def test_deployment_plan_hitl_count_5(self, designer, tmp_path):
        designer.run()
        plan = json.loads(
            (tmp_path / "phase8" / "deployment_plan.json").read_text(encoding="utf-8"))
        assert plan["hitl_count"] == 5

    def test_deployment_trace_updated(self, designer, tmp_path):
        designer.run()
        trace = json.loads(
            (tmp_path / "phase8" / "deployment_trace.json").read_text(encoding="utf-8"))
        assert "limited_environment" in trace["stages"]

    def test_trace_has_f9510_executed(self, designer, tmp_path):
        designer.run()
        trace = json.loads(
            (tmp_path / "phase8" / "deployment_trace.json").read_text(encoding="utf-8"))
        entry = trace["stages"]["limited_environment"]["f9510_entry"]
        assert "F9510 executed successfully" in entry

    def test_hitl_checkpoint_log_created(self, designer, tmp_path):
        designer.run()
        assert (tmp_path / "phase8" / "hitl_checkpoint_log.json").exists()

    def test_hitl_checkpoint_log_has_5_checkpoints(self, designer, tmp_path):
        designer.run()
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        assert log["total_checkpoints"] == 5

    def test_hitl_checkpoints_all_pending(self, designer, tmp_path):
        designer.run()
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        assert all(cp["status"] == "pending" for cp in log["checkpoints"])

    def test_record_hitl_approval_updates_status(self, designer, tmp_path):
        designer.run()
        designer.record_hitl_approval("limited_environment", "approve", "内容確認済み")
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        le_cp = next(cp for cp in log["checkpoints"] if cp["stage"] == "limited_environment")
        assert le_cp["status"] == "approve"
        assert le_cp["approved_at"] is not None

    def test_load_deployment_plan_returns_dict(self, designer, tmp_path):
        designer.run()
        loaded = designer.load_deployment_plan()
        assert isinstance(loaded, dict)

    def test_load_nonexistent_returns_empty(self, tmp_path):
        d = F9510DeploymentPlanDesigner(phase8_dir=tmp_path / "ph8")
        assert d.load_deployment_plan() == {}

    def test_write_summary_entry_creates_log(self, designer, tmp_path):
        result = designer.run()
        log    = tmp_path / "summary.log"
        designer.write_summary_entry(result, log_path=log)
        assert log.exists()

    def test_summary_entry_has_f9510(self, designer, tmp_path):
        result = designer.run()
        log    = tmp_path / "summary.log"
        designer.write_summary_entry(result, log_path=log)
        assert "F9510" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_next_stage(self, designer, tmp_path):
        result = designer.run()
        log    = tmp_path / "summary.log"
        designer.write_summary_entry(result, log_path=log)
        assert "F9520" in log.read_text(encoding="utf-8")

    def test_validation_error_json_on_io_failure(self, tmp_path):
        """I/O 整合性失敗時に validation_error.json が出力される。"""
        spec_path = tmp_path / "phase8" / "phase8_spec.json"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text(json.dumps(_SPEC_CONTENT), encoding="utf-8")

        d = F9510DeploymentPlanDesigner(
            spec_path=spec_path,
            cycle_dir=tmp_path / "empty_cycle",   # ファイルなし
            phase8_dir=tmp_path / "phase8",
            summary_log=tmp_path / "summary.log",
        )
        (tmp_path / "empty_cycle").mkdir()
        result = d.run()
        assert result["success"] is False
        assert (tmp_path / "phase8" / "validation_error.json").exists()


# インポート
_SPEC_CONTENT = {
    "phase8": {
        "version": "2026-07-23",
        "deployment_stages": REQUIRED_STAGES,
        "stage_details": {
            s: {
                "start_conditions":      [f"{s}_start_cond"],
                "completion_conditions": [f"{s}_complete_cond"],
            }
            for s in REQUIRED_STAGES
        },
        "hitl_points": {"required": REQUIRED_STAGES},
        "rollback_policy": {
            "strategy": "step_back_one_stage",
            "log_file":  "rollback_log.json",
        },
        "io_map": {
            "inputs":  ["learning_dataset.json", "learning_patterns.json", "optimization_report.json"],
            "outputs": ["deployment_plan.json", "deployment_trace.json", "hitl_checkpoint_log.json"],
        },
    }
}
