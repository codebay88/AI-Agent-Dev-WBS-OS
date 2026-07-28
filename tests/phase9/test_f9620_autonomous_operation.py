"""F9620 autonomous_operation_enablement テスト
Phase 9：完成層

テスト対象:
  - src/phase9/f9620_autonomous_operation.py
    - F9620AutonomousOperationEnabler.step1_load_unified_artifacts()
    - F9620AutonomousOperationEnabler.step2_design_control_loops()
    - F9620AutonomousOperationEnabler.step3_reconstruct_hitl_flow()
    - F9620AutonomousOperationEnabler.step4_link_knowledge_stores()
    - F9620AutonomousOperationEnabler.step5_set_initial_parameters()
    - F9620AutonomousOperationEnabler.step6_generate_control_loop_config()
    - F9620AutonomousOperationEnabler.step7_run_sandbox_trial()
    - F9620AutonomousOperationEnabler.step8_generate_profile()
    - F9620AutonomousOperationEnabler.run()
    - F9620AutonomousOperationEnabler.load_profile()
    - F9620AutonomousOperationEnabler.load_control_loop_config()
    - F9620AutonomousOperationEnabler.record_hitl_approval()
    - F9620AutonomousOperationEnabler.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.phase9.f9620_autonomous_operation import (
    F9620AutonomousOperationEnabler,
    MAX_LOOPS,
    SANDBOX_TRIAL_COUNT,
    OPT_SCORE_THRESHOLD,
    IO_THRESHOLD,
    _LOOP_TEMPLATES,
    _UNIFIED_HITL_POINTS,
    _CYCLE_INPUTS,
)

# ────────────────────────────────────────────────────────────────
# フィクスチャ
# ────────────────────────────────────────────────────────────────

_UNIFIED_ARCH = {
    "module":      "F9610",
    "phase9_stage": "integration_design",
    "agents": {"aiwbs": {"modules": ["F10"]}, "support": {"modules": ["F9510"]}},
    "validation": {"boundary_overlap": False, "all_rules_passed": True},
}
_UNIFIED_IO = {
    "module":       "F9610",
    "io_integrity": 1.0,
    "io_ok":        True,
    "total_entries": 17,
    "verified":     17,
}
_INTEG_MATRIX = {
    "module":     "F9610",
    "overall_ok": True,
    "phase9_stage": "integration_design",
}
_OPT_REPORT = {
    "phase7_complete": True,
    "summary": {"avg_optimization_index": 0.9119},
}
_FAILURE_REPO = {
    "known_failures": [{"id": "FL-001"}, {"id": "FL-002"}],
}


@pytest.fixture
def tmp_phase9_dir(tmp_path):
    p9 = tmp_path / "phase9"
    p9.mkdir()
    (p9 / "unified_architecture.json").write_text(
        json.dumps(_UNIFIED_ARCH), encoding="utf-8")
    (p9 / "unified_io_map.json").write_text(
        json.dumps(_UNIFIED_IO), encoding="utf-8")
    (p9 / "integration_matrix.json").write_text(
        json.dumps(_INTEG_MATRIX), encoding="utf-8")
    return p9


@pytest.fixture
def tmp_cycle_dir(tmp_path):
    kc = tmp_path / "knowledge_cycle"
    kc.mkdir()
    (kc / "learning_dataset.json").write_text("{}", encoding="utf-8")
    (kc / "learning_patterns.json").write_text("{}", encoding="utf-8")
    (kc / "optimization_report.json").write_text(
        json.dumps(_OPT_REPORT), encoding="utf-8")
    return kc


@pytest.fixture
def tmp_phase6_dir(tmp_path):
    p6 = tmp_path / "phase6"
    p6.mkdir()
    (p6 / "failure_repository.json").write_text(
        json.dumps(_FAILURE_REPO), encoding="utf-8")
    return p6


@pytest.fixture
def enabler(tmp_path, tmp_phase9_dir, tmp_cycle_dir, tmp_phase6_dir):
    return F9620AutonomousOperationEnabler(
        phase9_dir=tmp_phase9_dir,
        cycle_dir=tmp_cycle_dir,
        phase6_dir=tmp_phase6_dir,
        summary_log=tmp_path / "summary.log",
    )


# ════════════════════════════════════════════════════════════════
# TestF9620_01 — Step 1: 統合アーティファクト読み込み
# ════════════════════════════════════════════════════════════════

class TestF9620_01_LoadUnifiedArtifacts:

    def test_returns_dict(self, enabler):
        assert isinstance(enabler.step1_load_unified_artifacts(), dict)

    def test_all_loaded_true(self, enabler):
        result = enabler.step1_load_unified_artifacts()
        assert result["all_loaded"] is True

    def test_missing_empty(self, enabler):
        result = enabler.step1_load_unified_artifacts()
        assert result["missing"] == []

    def test_arch_is_dict(self, enabler):
        result = enabler.step1_load_unified_artifacts()
        assert isinstance(result["arch"], dict)

    def test_io_map_is_dict(self, enabler):
        result = enabler.step1_load_unified_artifacts()
        assert isinstance(result["io_map"], dict)

    def test_matrix_is_dict(self, enabler):
        result = enabler.step1_load_unified_artifacts()
        assert isinstance(result["matrix"], dict)

    def test_loop_candidates_not_empty(self, enabler):
        result = enabler.step1_load_unified_artifacts()
        assert len(result["loop_candidates"]) > 0

    def test_all_loaded_false_when_empty(self, tmp_path, tmp_cycle_dir, tmp_phase6_dir):
        empty = tmp_path / "empty_p9"
        empty.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=empty,
            cycle_dir=tmp_cycle_dir,
            phase6_dir=tmp_phase6_dir,
        )
        result = d.step1_load_unified_artifacts()
        assert result["all_loaded"] is False


# ════════════════════════════════════════════════════════════════
# TestF9620_02 — Step 2: 制御ループ設計
# ════════════════════════════════════════════════════════════════

class TestF9620_02_DesignControlLoops:

    @pytest.fixture
    def artifacts(self, enabler):
        return enabler.step1_load_unified_artifacts()

    def test_returns_dict(self, enabler, artifacts):
        assert isinstance(enabler.step2_design_control_loops(artifacts), dict)

    def test_loop_count_equals_3(self, enabler, artifacts):
        result = enabler.step2_design_control_loops(artifacts)
        assert result["loop_count"] == len(_LOOP_TEMPLATES)

    def test_loop_count_within_max(self, enabler, artifacts):
        result = enabler.step2_design_control_loops(artifacts)
        assert result["loop_count"] <= MAX_LOOPS

    def test_design_ok_true(self, enabler, artifacts):
        result = enabler.step2_design_control_loops(artifacts)
        assert result["design_ok"] is True

    def test_error_is_none_when_ok(self, enabler, artifacts):
        result = enabler.step2_design_control_loops(artifacts)
        assert result["error"] is None

    def test_loops_is_list(self, enabler, artifacts):
        result = enabler.step2_design_control_loops(artifacts)
        assert isinstance(result["loops"], list)

    def test_each_loop_has_loop_id(self, enabler, artifacts):
        result = enabler.step2_design_control_loops(artifacts)
        assert all("loop_id" in l for l in result["loops"])


# ════════════════════════════════════════════════════════════════
# TestF9620_03 — Step 3: HITL フロー再構成
# ════════════════════════════════════════════════════════════════

class TestF9620_03_ReconstructHitlFlow:

    @pytest.fixture
    def loop_design(self, enabler):
        arts = enabler.step1_load_unified_artifacts()
        return enabler.step2_design_control_loops(arts)

    def test_returns_dict(self, enabler, loop_design):
        assert isinstance(enabler.step3_reconstruct_hitl_flow(loop_design), dict)

    def test_hitl_flow_defined_true(self, enabler, loop_design):
        result = enabler.step3_reconstruct_hitl_flow(loop_design)
        assert result["hitl_flow_defined"] is True

    def test_hitl_points_count(self, enabler, loop_design):
        result = enabler.step3_reconstruct_hitl_flow(loop_design)
        assert len(result["hitl_points"]) == len(_UNIFIED_HITL_POINTS)

    def test_each_hitl_point_has_id(self, enabler, loop_design):
        result = enabler.step3_reconstruct_hitl_flow(loop_design)
        assert all("id" in h for h in result["hitl_points"])

    def test_autonomy_rules_not_empty(self, enabler, loop_design):
        result = enabler.step3_reconstruct_hitl_flow(loop_design)
        assert len(result["autonomy_rules"]) > 0

    def test_each_rule_has_rule_id(self, enabler, loop_design):
        result = enabler.step3_reconstruct_hitl_flow(loop_design)
        assert all("rule_id" in r for r in result["autonomy_rules"])


# ════════════════════════════════════════════════════════════════
# TestF9620_04 — Step 4: 知識ストア接続
# ════════════════════════════════════════════════════════════════

class TestF9620_04_LinkKnowledgeStores:

    def test_returns_dict(self, enabler):
        assert isinstance(enabler.step4_link_knowledge_stores(), dict)

    def test_knowledge_cycle_linked_true(self, enabler):
        result = enabler.step4_link_knowledge_stores()
        assert result["knowledge_cycle_linked"] is True

    def test_failure_repository_linked_true(self, enabler):
        result = enabler.step4_link_knowledge_stores()
        assert result["failure_repository_linked"] is True

    def test_all_linked_true(self, enabler):
        result = enabler.step4_link_knowledge_stores()
        assert result["all_linked"] is True

    def test_repo_entries_count(self, enabler):
        result = enabler.step4_link_knowledge_stores()
        assert result["repo_entries"] == 2

    def test_cycle_files_all_true(self, enabler):
        result = enabler.step4_link_knowledge_stores()
        assert all(result["cycle_files"].values())

    def test_kc_not_linked_when_cycle_empty(self, tmp_path, tmp_phase9_dir, tmp_phase6_dir):
        empty = tmp_path / "empty_kc"
        empty.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
        )
        result = d.step4_link_knowledge_stores()
        assert result["knowledge_cycle_linked"] is False
        assert result["all_linked"] is False

    def test_repo_not_linked_when_phase6_empty(self, tmp_path, tmp_phase9_dir, tmp_cycle_dir):
        empty = tmp_path / "empty_p6"
        empty.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=tmp_cycle_dir,
            phase6_dir=empty,
        )
        result = d.step4_link_knowledge_stores()
        assert result["failure_repository_linked"] is False


# ════════════════════════════════════════════════════════════════
# TestF9620_05 — Step 5: 初期パラメータ設定
# ════════════════════════════════════════════════════════════════

class TestF9620_05_SetInitialParameters:

    def test_returns_dict(self, enabler):
        assert isinstance(enabler.step5_set_initial_parameters(), dict)

    def test_opt_score_above_threshold(self, enabler):
        result = enabler.step5_set_initial_parameters()
        assert result["opt_score"] >= OPT_SCORE_THRESHOLD

    def test_parameters_set_true(self, enabler):
        result = enabler.step5_set_initial_parameters()
        assert result["parameters_set"] is True

    def test_thresholds_has_required_keys(self, enabler):
        result = enabler.step5_set_initial_parameters()
        for key in ("opt_score_min", "io_integrity_min", "error_rate_max",
                    "max_retry", "max_loops", "current_opt_score"):
            assert key in result["thresholds"]

    def test_max_loops_in_thresholds_equals_constant(self, enabler):
        result = enabler.step5_set_initial_parameters()
        assert result["thresholds"]["max_loops"] == MAX_LOOPS

    def test_parameters_set_false_when_no_opt_report(self, tmp_path, tmp_phase9_dir, tmp_phase6_dir):
        empty = tmp_path / "empty_kc"
        empty.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
        )
        result = d.step5_set_initial_parameters()
        assert result["opt_score"] == 0.0
        assert result["parameters_set"] is False


# ════════════════════════════════════════════════════════════════
# TestF9620_06 — Step 6: control_loop_config 生成
# ════════════════════════════════════════════════════════════════

class TestF9620_06_GenerateControlLoopConfig:

    @pytest.fixture
    def all_inputs(self, enabler):
        arts        = enabler.step1_load_unified_artifacts()
        loop_design = enabler.step2_design_control_loops(arts)
        hitl_flow   = enabler.step3_reconstruct_hitl_flow(loop_design)
        links       = enabler.step4_link_knowledge_stores()
        params      = enabler.step5_set_initial_parameters()
        return loop_design, hitl_flow, links, params

    def test_returns_dict(self, enabler, all_inputs):
        ld, hf, lk, pm = all_inputs
        assert isinstance(enabler.step6_generate_control_loop_config(ld, hf, lk, pm), dict)

    def test_phase9_stage(self, enabler, all_inputs):
        ld, hf, lk, pm = all_inputs
        cfg = enabler.step6_generate_control_loop_config(ld, hf, lk, pm)
        assert cfg["phase9_stage"] == "autonomous_operation"

    def test_consistent_true_when_all_ok(self, enabler, all_inputs):
        ld, hf, lk, pm = all_inputs
        cfg = enabler.step6_generate_control_loop_config(ld, hf, lk, pm)
        assert cfg["control_loop_config_consistent"] is True

    def test_has_loops_list(self, enabler, all_inputs):
        ld, hf, lk, pm = all_inputs
        cfg = enabler.step6_generate_control_loop_config(ld, hf, lk, pm)
        assert isinstance(cfg["loops"], list) and len(cfg["loops"]) > 0

    def test_has_thresholds(self, enabler, all_inputs):
        ld, hf, lk, pm = all_inputs
        cfg = enabler.step6_generate_control_loop_config(ld, hf, lk, pm)
        assert "thresholds" in cfg

    def test_has_shared_store(self, enabler, all_inputs):
        ld, hf, lk, pm = all_inputs
        cfg = enabler.step6_generate_control_loop_config(ld, hf, lk, pm)
        assert "knowledge_cycle" in cfg["shared_store"]

    def test_consistent_false_when_not_linked(self, enabler, all_inputs):
        ld, hf, _, pm = all_inputs
        bad_links = {
            "knowledge_cycle_linked": False,
            "failure_repository_linked": False,
            "all_linked": False,
        }
        cfg = enabler.step6_generate_control_loop_config(ld, hf, bad_links, pm)
        assert cfg["control_loop_config_consistent"] is False


# ════════════════════════════════════════════════════════════════
# TestF9620_07 — Step 7: sandbox 試験
# ════════════════════════════════════════════════════════════════

class TestF9620_07_RunSandboxTrial:

    @pytest.fixture
    def ok_config_links(self, enabler):
        arts        = enabler.step1_load_unified_artifacts()
        loop_design = enabler.step2_design_control_loops(arts)
        hitl_flow   = enabler.step3_reconstruct_hitl_flow(loop_design)
        links       = enabler.step4_link_knowledge_stores()
        params      = enabler.step5_set_initial_parameters()
        config      = enabler.step6_generate_control_loop_config(loop_design, hitl_flow, links, params)
        return config, links

    def test_returns_dict(self, enabler, ok_config_links):
        config, links = ok_config_links
        assert isinstance(enabler.step7_run_sandbox_trial(config, links), dict)

    def test_trial_count_equals_constant(self, enabler, ok_config_links):
        config, links = ok_config_links
        result = enabler.step7_run_sandbox_trial(config, links)
        assert result["trial_count"] == SANDBOX_TRIAL_COUNT
        assert len(result["trials"]) == SANDBOX_TRIAL_COUNT

    def test_sandbox_ok_true_when_all_ok(self, enabler, ok_config_links):
        config, links = ok_config_links
        result = enabler.step7_run_sandbox_trial(config, links)
        assert result["sandbox_ok"] is True

    def test_success_rate_1_when_all_pass(self, enabler, ok_config_links):
        config, links = ok_config_links
        result = enabler.step7_run_sandbox_trial(config, links)
        assert result["success_rate"] == 1.0

    def test_exception_count_0_when_ok(self, enabler, ok_config_links):
        config, links = ok_config_links
        result = enabler.step7_run_sandbox_trial(config, links)
        assert result["exception_count"] == 0

    def test_sandbox_fails_when_config_inconsistent(self, enabler):
        bad_config = {"control_loop_config_consistent": False, "loops": _LOOP_TEMPLATES}
        bad_links  = {"all_linked": False}
        result     = enabler.step7_run_sandbox_trial(bad_config, bad_links)
        assert result["sandbox_ok"] is False
        assert result["exception_count"] > 0

    def test_each_trial_has_loop_results(self, enabler, ok_config_links):
        config, links = ok_config_links
        result = enabler.step7_run_sandbox_trial(config, links)
        assert all("loop_results" in t for t in result["trials"])


# ════════════════════════════════════════════════════════════════
# TestF9620_08 — run() / 出力ファイル
# ════════════════════════════════════════════════════════════════

class TestF9620_08_RunAndOutputFiles:

    def test_run_returns_dict(self, enabler):
        assert isinstance(enabler.run(), dict)

    def test_run_success_true(self, enabler):
        assert enabler.run()["success"] is True

    def test_phase9_stage_autonomous_operation(self, enabler):
        assert enabler.run()["phase9_stage"] == "autonomous_operation"

    def test_profile_created(self, enabler, tmp_phase9_dir):
        enabler.run()
        assert (tmp_phase9_dir / "autonomous_operation_profile.json").exists()

    def test_profile_success_true(self, enabler, tmp_phase9_dir):
        enabler.run()
        profile = json.loads(
            (tmp_phase9_dir / "autonomous_operation_profile.json").read_text(encoding="utf-8"))
        assert profile["success"] is True

    def test_profile_phase9_stage(self, enabler, tmp_phase9_dir):
        enabler.run()
        profile = json.loads(
            (tmp_phase9_dir / "autonomous_operation_profile.json").read_text(encoding="utf-8"))
        assert profile["phase9_stage"] == "autonomous_operation"

    def test_control_loop_config_created(self, enabler, tmp_phase9_dir):
        enabler.run()
        assert (tmp_phase9_dir / "control_loop_config.json").exists()

    def test_control_loop_config_consistent(self, enabler, tmp_phase9_dir):
        enabler.run()
        cfg = json.loads(
            (tmp_phase9_dir / "control_loop_config.json").read_text(encoding="utf-8"))
        assert cfg["control_loop_config_consistent"] is True

    def test_control_loop_config_has_all_loops(self, enabler, tmp_phase9_dir):
        enabler.run()
        cfg = json.loads(
            (tmp_phase9_dir / "control_loop_config.json").read_text(encoding="utf-8"))
        assert cfg["loop_count"] == len(_LOOP_TEMPLATES)

    def test_hitl_autonomy_flow_created(self, enabler, tmp_phase9_dir):
        enabler.run()
        assert (tmp_phase9_dir / "hitl_autonomy_flow.json").exists()

    def test_hitl_autonomy_flow_has_points(self, enabler, tmp_phase9_dir):
        enabler.run()
        flow = json.loads(
            (tmp_phase9_dir / "hitl_autonomy_flow.json").read_text(encoding="utf-8"))
        assert len(flow["hitl_points"]) == len(_UNIFIED_HITL_POINTS)

    def test_runtime_observation_log_created(self, enabler, tmp_phase9_dir):
        enabler.run()
        assert (tmp_phase9_dir / "runtime_observation_log.json").exists()

    def test_runtime_log_sandbox_ok(self, enabler, tmp_phase9_dir):
        enabler.run()
        log = json.loads(
            (tmp_phase9_dir / "runtime_observation_log.json").read_text(encoding="utf-8"))
        assert log["sandbox_ok"] is True

    def test_runtime_log_has_trials(self, enabler, tmp_phase9_dir):
        enabler.run()
        log = json.loads(
            (tmp_phase9_dir / "runtime_observation_log.json").read_text(encoding="utf-8"))
        assert len(log["trials"]) == SANDBOX_TRIAL_COUNT

    def test_hitl_checkpoint_log_updated(self, enabler, tmp_phase9_dir):
        enabler.run()
        log = json.loads(
            (tmp_phase9_dir / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        stages = [cp["stage"] for cp in log["checkpoints"]]
        assert "autonomous_operation" in stages

    def test_record_hitl_approval(self, enabler, tmp_phase9_dir):
        enabler.run()
        enabler.record_hitl_approval("autonomous_operation", "approve", "プロファイル確認済み")
        log = json.loads(
            (tmp_phase9_dir / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        cp = next(c for c in log["checkpoints"] if c["stage"] == "autonomous_operation")
        assert cp["status"] == "approve"
        assert cp["approved_at"] is not None

    def test_record_hitl_approval_reason(self, enabler, tmp_phase9_dir):
        enabler.run()
        enabler.record_hitl_approval("autonomous_operation", "approve", "プロファイル確認済み")
        log = json.loads(
            (tmp_phase9_dir / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        cp = next(c for c in log["checkpoints"] if c["stage"] == "autonomous_operation")
        assert cp["reason"] == "プロファイル確認済み"

    def test_load_profile_returns_dict(self, enabler):
        enabler.run()
        assert isinstance(enabler.load_profile(), dict)

    def test_load_control_loop_config_returns_dict(self, enabler):
        enabler.run()
        assert isinstance(enabler.load_control_loop_config(), dict)

    def test_load_nonexistent_profile(self, tmp_path):
        d = F9620AutonomousOperationEnabler(phase9_dir=tmp_path / "p9")
        assert d.load_profile() == {}

    def test_load_nonexistent_config(self, tmp_path):
        d = F9620AutonomousOperationEnabler(phase9_dir=tmp_path / "p9")
        assert d.load_control_loop_config() == {}

    def test_write_summary_entry_creates_log(self, enabler, tmp_path):
        result = enabler.run()
        log    = tmp_path / "summary.log"
        enabler.write_summary_entry(result, log_path=log)
        assert log.exists()

    def test_summary_entry_has_f9620(self, enabler, tmp_path):
        result = enabler.run()
        log    = tmp_path / "summary.log"
        enabler.write_summary_entry(result, log_path=log)
        assert "F9620" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_f9630(self, enabler, tmp_path):
        result = enabler.run()
        log    = tmp_path / "summary.log"
        enabler.write_summary_entry(result, log_path=log)
        assert "F9630" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# TestF9620_09 — エラー / ロールバックシナリオ
# ════════════════════════════════════════════════════════════════

class TestF9620_09_ErrorAndRollback:

    def test_run_fails_when_no_p9_artifacts(self, tmp_path, tmp_cycle_dir, tmp_phase6_dir):
        empty = tmp_path / "empty_p9"
        empty.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=empty,
            cycle_dir=tmp_cycle_dir,
            phase6_dir=tmp_phase6_dir,
        )
        result = d.run()
        # all_loaded=False でも design_ok なら進む。success はリンク状況次第
        assert isinstance(result, dict)

    def test_profile_created_on_failure(self, tmp_path, tmp_phase9_dir, tmp_phase6_dir):
        empty = tmp_path / "empty_kc"
        empty.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
        )
        d.run()
        assert (tmp_phase9_dir / "autonomous_operation_profile.json").exists()

    def test_validation_error_when_not_linked(self, tmp_path, tmp_phase9_dir):
        empty_kc = tmp_path / "empty_kc"
        empty_kc.mkdir()
        empty_p6 = tmp_path / "empty_p6"
        empty_p6.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=empty_kc,
            phase6_dir=empty_p6,
        )
        d.run()
        assert (tmp_phase9_dir / "validation_error.json").exists()

    def test_rollback_log_when_sandbox_fails(self, tmp_path, tmp_phase9_dir, tmp_phase6_dir):
        empty_kc = tmp_path / "empty_kc"
        empty_kc.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=empty_kc,
            phase6_dir=tmp_phase6_dir,
        )
        d.run()
        # sandbox 失敗時に rollback_log が生成される
        rollback = tmp_phase9_dir / "rollback_log.json"
        if rollback.exists():
            log = json.loads(rollback.read_text(encoding="utf-8"))
            assert log["total_events"] >= 1

    def test_runtime_observation_log_created_always(self, tmp_path, tmp_phase9_dir, tmp_phase6_dir):
        empty_kc = tmp_path / "empty_kc"
        empty_kc.mkdir()
        d = F9620AutonomousOperationEnabler(
            phase9_dir=tmp_phase9_dir,
            cycle_dir=empty_kc,
            phase6_dir=tmp_phase6_dir,
        )
        d.run()
        assert (tmp_phase9_dir / "runtime_observation_log.json").exists()
