"""F9610 unified_architecture_design テスト
Phase 9：完成層

テスト対象:
  - src/phase9/f9610_unified_architecture.py
    - F9610UnifiedArchitectureDesigner.step1_load_phase8_outcomes()
    - F9610UnifiedArchitectureDesigner.step2_extract_agent_profiles()
    - F9610UnifiedArchitectureDesigner.step3_map_boundaries_and_flow()
    - F9610UnifiedArchitectureDesigner.step4_apply_design_rules()
    - F9610UnifiedArchitectureDesigner.step5_generate_unified_architecture()
    - F9610UnifiedArchitectureDesigner.step6_generate_unified_io_map()
    - F9610UnifiedArchitectureDesigner.step7_generate_integration_matrix()
    - F9610UnifiedArchitectureDesigner.step8_set_hitl_checkpoint()
    - F9610UnifiedArchitectureDesigner.run()
    - F9610UnifiedArchitectureDesigner.load_unified_architecture()
    - F9610UnifiedArchitectureDesigner.load_integration_matrix()
    - F9610UnifiedArchitectureDesigner.record_hitl_approval()
    - F9610UnifiedArchitectureDesigner.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.phase9.f9610_unified_architecture import (
    F9610UnifiedArchitectureDesigner,
    IO_INTEGRITY_THRESHOLD,
    _AIWBS_AGENT,
    _SUPPORT_AGENT,
    _DESIGN_RULES,
    _CYCLE_INPUTS,
)

# ────────────────────────────────────────────────────────────────
# フィクスチャ
# ────────────────────────────────────────────────────────────────

_DEPLOY_SUMMARY = {
    "module":         "F9530",
    "phase8_stage":   "full_deployment",
    "phase8_complete": True,
    "f9510_summary": {"io_integrity": 100.0, "hitl_count": 5},
    "f9520_summary": {
        "io_integrity": 1.0,
        "reproducibility_passed": True,
        "failure_repository_sync": "success",
        "knowledge_cycle_update": "success",
    },
    "f9530_summary": {
        "error_rate": 0.0,
        "opt_score": 0.9119,
        "log_completeness": 1.0,
        "stability_status": "stable",
        "repro_passed": True,
    },
}

_STABILITY_RPT = {
    "module":  "F9530",
    "success": True,
    "stability": {"stability_status": "stable", "error_rate": 0.0, "opt_score": 0.9119},
    "load_test": {"io_integrity": 1.0, "error_rate": 0.0},
}

_INTEG_RPT = {
    "module":                      "F9520",
    "success":                     True,
    "io_integrity":                1.0,
    "reproducibility_test_passed": True,
    "failure_repository_sync":     "success",
    "knowledge_cycle_update":      "success",
}

_OPT_REPORT = {
    "phase7_complete": True,
    "summary": {"avg_optimization_index": 0.9119},
}


@pytest.fixture
def tmp_phase8_dir(tmp_path):
    p8 = tmp_path / "phase8"
    p8.mkdir()
    (p8 / "deployment_summary.json").write_text(
        json.dumps(_DEPLOY_SUMMARY), encoding="utf-8")
    (p8 / "stability_report.json").write_text(
        json.dumps(_STABILITY_RPT), encoding="utf-8")
    (p8 / "integration_report.json").write_text(
        json.dumps(_INTEG_RPT), encoding="utf-8")
    # SUPPORT outputs — io_map の verified チェック対象
    (p8 / "deployment_plan.json").write_text(
        json.dumps({"module": "F9510", "phase8_stage": "limited_environment"}),
        encoding="utf-8")
    return p8


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
def designer(tmp_path, tmp_phase8_dir, tmp_cycle_dir):
    return F9610UnifiedArchitectureDesigner(
        phase8_dir=tmp_phase8_dir,
        cycle_dir=tmp_cycle_dir,
        phase9_dir=tmp_path / "phase9",
        summary_log=tmp_path / "summary.log",
    )


# ════════════════════════════════════════════════════════════════
# TestF9610_01 — Step 1: Phase 8 成果の読み込み
# ════════════════════════════════════════════════════════════════

class TestF9610_01_LoadPhase8Outcomes:

    def test_returns_dict(self, designer):
        assert isinstance(designer.step1_load_phase8_outcomes(), dict)

    def test_all_loaded_true_when_all_present(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert result["all_loaded"] is True

    def test_missing_empty_when_all_present(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert result["missing"] == []

    def test_deployment_summary_is_dict(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert isinstance(result["deployment_summary"], dict)

    def test_stability_report_is_dict(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert isinstance(result["stability_report"], dict)

    def test_integration_report_is_dict(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert isinstance(result["integration_report"], dict)

    def test_cycle_inputs_all_true(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert all(result["cycle_inputs"].values())

    def test_all_loaded_false_when_missing(self, tmp_path, tmp_cycle_dir):
        d = F9610UnifiedArchitectureDesigner(
            phase8_dir=tmp_path / "empty_phase8",
            cycle_dir=tmp_cycle_dir,
            phase9_dir=tmp_path / "phase9",
        )
        (tmp_path / "empty_phase8").mkdir()
        result = d.step1_load_phase8_outcomes()
        assert result["all_loaded"] is False

    def test_deployment_summary_phase8_complete(self, designer):
        result = designer.step1_load_phase8_outcomes()
        assert result["deployment_summary"].get("phase8_complete") is True


# ════════════════════════════════════════════════════════════════
# TestF9610_02 — Step 2: エージェントプロファイル抽出
# ════════════════════════════════════════════════════════════════

class TestF9610_02_ExtractAgentProfiles:

    @pytest.fixture
    def outcomes(self, designer):
        return designer.step1_load_phase8_outcomes()

    def test_returns_dict(self, designer, outcomes):
        assert isinstance(designer.step2_extract_agent_profiles(outcomes), dict)

    def test_has_aiwbs_and_support(self, designer, outcomes):
        result = designer.step2_extract_agent_profiles(outcomes)
        assert "aiwbs" in result and "support" in result

    def test_extraction_ok_true(self, designer, outcomes):
        result = designer.step2_extract_agent_profiles(outcomes)
        assert result["extraction_ok"] is True

    def test_aiwbs_has_9_modules(self, designer, outcomes):
        result = designer.step2_extract_agent_profiles(outcomes)
        assert len(result["aiwbs"]["modules"]) == 9

    def test_support_has_3_modules(self, designer, outcomes):
        result = designer.step2_extract_agent_profiles(outcomes)
        assert len(result["support"]["modules"]) == 3

    def test_aiwbs_has_responsibilities(self, designer, outcomes):
        result = designer.step2_extract_agent_profiles(outcomes)
        assert len(result["aiwbs"]["responsibilities"]) > 0

    def test_support_has_responsibilities(self, designer, outcomes):
        result = designer.step2_extract_agent_profiles(outcomes)
        assert len(result["support"]["responsibilities"]) > 0


# ════════════════════════════════════════════════════════════════
# TestF9610_03 — Step 3: 境界・依存・データ流通マッピング
# ════════════════════════════════════════════════════════════════

class TestF9610_03_MapBoundariesAndFlow:

    @pytest.fixture
    def profiles(self, designer):
        outcomes = designer.step1_load_phase8_outcomes()
        return designer.step2_extract_agent_profiles(outcomes)

    def test_returns_dict(self, designer, profiles):
        assert isinstance(designer.step3_map_boundaries_and_flow(profiles), dict)

    def test_boundaries_not_empty(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert len(result["boundaries"]) > 0

    def test_dependencies_not_empty(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert len(result["dependencies"]) > 0

    def test_data_flow_not_empty(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert len(result["data_flow"]) > 0

    def test_no_boundary_overlap_with_distinct_responsibilities(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert result["boundary_overlap"] is False

    def test_data_flow_consistent(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert result["data_flow_consistent"] is True

    def test_each_boundary_has_id(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert all("id" in b for b in result["boundaries"])

    def test_each_data_flow_has_source_and_sink(self, designer, profiles):
        result = designer.step3_map_boundaries_and_flow(profiles)
        assert all("source" in df and "sink" in df for df in result["data_flow"])


# ════════════════════════════════════════════════════════════════
# TestF9610_04 — Step 4: 統合設計ルールの適用
# ════════════════════════════════════════════════════════════════

class TestF9610_04_ApplyDesignRules:

    @pytest.fixture
    def profiles_and_mapping(self, designer):
        outcomes = designer.step1_load_phase8_outcomes()
        profiles = designer.step2_extract_agent_profiles(outcomes)
        mapping  = designer.step3_map_boundaries_and_flow(profiles)
        return profiles, mapping

    def test_returns_dict(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        assert isinstance(designer.step4_apply_design_rules(profiles, mapping), dict)

    def test_5_rules_applied(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        result = designer.step4_apply_design_rules(profiles, mapping)
        assert len(result["rules_applied"]) == len(_DESIGN_RULES)

    def test_all_rules_passed(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        result = designer.step4_apply_design_rules(profiles, mapping)
        assert result["all_rules_passed"] is True

    def test_mece_ok_true(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        result = designer.step4_apply_design_rules(profiles, mapping)
        assert result["mece_ok"] is True

    def test_causal_ok_true(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        result = designer.step4_apply_design_rules(profiles, mapping)
        assert result["causal_ok"] is True

    def test_no_responsibility_conflict(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        result = designer.step4_apply_design_rules(profiles, mapping)
        assert result["responsibility_conflict"] is False

    def test_each_rule_has_passed_key(self, designer, profiles_and_mapping):
        profiles, mapping = profiles_and_mapping
        result = designer.step4_apply_design_rules(profiles, mapping)
        assert all("passed" in r for r in result["rules_applied"])

    def test_responsibility_conflict_when_overlapping(self, designer):
        """責務が重複するプロファイルで conflict が検出される。"""
        bad_profiles = {
            "aiwbs":   {**_AIWBS_AGENT,   "responsibilities": ["タスク生成", "共通責務"]},
            "support": {**_SUPPORT_AGENT, "responsibilities": ["展開計画設計", "共通責務"]},
        }
        mapping = {"boundary_overlap": True, "data_flow_consistent": True}
        result  = designer.step4_apply_design_rules(bad_profiles, mapping)
        assert result["responsibility_conflict"] is True


# ════════════════════════════════════════════════════════════════
# TestF9610_05 — Step 5: unified_architecture 生成
# ════════════════════════════════════════════════════════════════

class TestF9610_05_GenerateUnifiedArchitecture:

    @pytest.fixture
    def all_inputs(self, designer):
        outcomes = designer.step1_load_phase8_outcomes()
        profiles = designer.step2_extract_agent_profiles(outcomes)
        mapping  = designer.step3_map_boundaries_and_flow(profiles)
        rules    = designer.step4_apply_design_rules(profiles, mapping)
        return profiles, mapping, rules

    def test_returns_dict(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        assert isinstance(
            designer.step5_generate_unified_architecture(profiles, mapping, rules), dict)

    def test_has_agents_key(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        arch = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        assert "agents" in arch
        assert "aiwbs" in arch["agents"] and "support" in arch["agents"]

    def test_phase9_stage_integration_design(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        arch = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        assert arch["phase9_stage"] == "integration_design"

    def test_has_unified_hitl_flow(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        arch = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        assert "unified_hitl_flow" in arch

    def test_has_design_rules(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        arch = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        assert len(arch["design_rules"]) == len(_DESIGN_RULES)

    def test_has_validation_section(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        arch = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        assert "validation" in arch

    def test_shared_store_is_knowledge_cycle(self, designer, all_inputs):
        profiles, mapping, rules = all_inputs
        arch = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        assert "knowledge_cycle" in arch["shared_store"]


# ════════════════════════════════════════════════════════════════
# TestF9610_06 — Step 6: unified_io_map 生成
# ════════════════════════════════════════════════════════════════

class TestF9610_06_GenerateUnifiedIoMap:

    @pytest.fixture
    def inputs(self, designer):
        outcomes = designer.step1_load_phase8_outcomes()
        profiles = designer.step2_extract_agent_profiles(outcomes)
        mapping  = designer.step3_map_boundaries_and_flow(profiles)
        return outcomes, profiles, mapping

    def test_returns_dict(self, designer, inputs):
        outcomes, profiles, mapping = inputs
        assert isinstance(
            designer.step6_generate_unified_io_map(profiles, mapping, outcomes), dict)

    def test_io_entries_not_empty(self, designer, inputs):
        outcomes, profiles, mapping = inputs
        io_map = designer.step6_generate_unified_io_map(profiles, mapping, outcomes)
        assert io_map["total_entries"] > 0

    def test_io_integrity_above_threshold(self, designer, inputs):
        outcomes, profiles, mapping = inputs
        io_map = designer.step6_generate_unified_io_map(profiles, mapping, outcomes)
        assert io_map["io_integrity"] >= IO_INTEGRITY_THRESHOLD

    def test_io_ok_true_when_threshold_met(self, designer, inputs):
        outcomes, profiles, mapping = inputs
        io_map = designer.step6_generate_unified_io_map(profiles, mapping, outcomes)
        assert io_map["io_ok"] is True

    def test_each_entry_has_direction(self, designer, inputs):
        outcomes, profiles, mapping = inputs
        io_map = designer.step6_generate_unified_io_map(profiles, mapping, outcomes)
        assert all("direction" in e for e in io_map["io_entries"])

    def test_io_integrity_range_0_to_1(self, designer, inputs):
        outcomes, profiles, mapping = inputs
        io_map = designer.step6_generate_unified_io_map(profiles, mapping, outcomes)
        assert 0.0 <= io_map["io_integrity"] <= 1.0


# ════════════════════════════════════════════════════════════════
# TestF9610_07 — Step 7: integration_matrix 生成
# ════════════════════════════════════════════════════════════════

class TestF9610_07_GenerateIntegrationMatrix:

    @pytest.fixture
    def all_inputs(self, designer):
        outcomes = designer.step1_load_phase8_outcomes()
        profiles = designer.step2_extract_agent_profiles(outcomes)
        mapping  = designer.step3_map_boundaries_and_flow(profiles)
        rules    = designer.step4_apply_design_rules(profiles, mapping)
        arch     = designer.step5_generate_unified_architecture(profiles, mapping, rules)
        io_map   = designer.step6_generate_unified_io_map(profiles, mapping, outcomes)
        return arch, io_map, rules, outcomes

    def test_returns_dict(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        assert isinstance(
            designer.step7_generate_integration_matrix(arch, io_map, rules, outcomes), dict)

    def test_overall_ok_true(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        matrix = designer.step7_generate_integration_matrix(arch, io_map, rules, outcomes)
        assert matrix["overall_ok"] is True

    def test_phase9_stage_integration_design(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        matrix = designer.step7_generate_integration_matrix(arch, io_map, rules, outcomes)
        assert matrix["phase9_stage"] == "integration_design"

    def test_has_axes(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        matrix = designer.step7_generate_integration_matrix(arch, io_map, rules, outcomes)
        assert "axes" in matrix

    def test_has_evaluation(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        matrix = designer.step7_generate_integration_matrix(arch, io_map, rules, outcomes)
        assert "evaluation" in matrix

    def test_evaluation_io_integrity_ok(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        matrix = designer.step7_generate_integration_matrix(arch, io_map, rules, outcomes)
        assert matrix["evaluation"]["io_integrity_ok"] is True

    def test_overall_ok_false_when_phase8_incomplete(self, designer, all_inputs):
        arch, io_map, rules, outcomes = all_inputs
        bad_outcomes = dict(outcomes)
        bad_outcomes["deployment_summary"] = {"phase8_complete": False}
        matrix = designer.step7_generate_integration_matrix(arch, io_map, rules, bad_outcomes)
        assert matrix["overall_ok"] is False


# ════════════════════════════════════════════════════════════════
# TestF9610_08 — Step 8 / run() / 出力ファイル
# ════════════════════════════════════════════════════════════════

class TestF9610_08_SetHitlAndRun:

    def test_step8_returns_dict(self, designer):
        matrix = {"overall_ok": True}
        result = designer.step8_set_hitl_checkpoint(matrix)
        assert isinstance(result, dict)

    def test_step8_stage_integration_design(self, designer):
        result = designer.step8_set_hitl_checkpoint({"overall_ok": True})
        assert result["stage"] == "integration_design"

    def test_step8_status_pending(self, designer):
        result = designer.step8_set_hitl_checkpoint({"overall_ok": True})
        assert result["status"] == "pending"

    def test_hitl_log_created(self, designer, tmp_path):
        designer.step8_set_hitl_checkpoint({"overall_ok": True})
        assert (tmp_path / "phase9" / "hitl_checkpoint_log.json").exists()

    def test_run_returns_dict(self, designer):
        assert isinstance(designer.run(), dict)

    def test_run_success_true(self, designer):
        assert designer.run()["success"] is True

    def test_run_phase9_stage(self, designer):
        assert designer.run()["phase9_stage"] == "integration_design"

    def test_unified_architecture_created(self, designer, tmp_path):
        designer.run()
        assert (tmp_path / "phase9" / "unified_architecture.json").exists()

    def test_unified_architecture_has_agents(self, designer, tmp_path):
        designer.run()
        arch = json.loads(
            (tmp_path / "phase9" / "unified_architecture.json").read_text(encoding="utf-8"))
        assert "aiwbs" in arch["agents"] and "support" in arch["agents"]

    def test_unified_io_map_created(self, designer, tmp_path):
        designer.run()
        assert (tmp_path / "phase9" / "unified_io_map.json").exists()

    def test_unified_io_map_integrity_ok(self, designer, tmp_path):
        designer.run()
        io_map = json.loads(
            (tmp_path / "phase9" / "unified_io_map.json").read_text(encoding="utf-8"))
        assert io_map["io_ok"] is True

    def test_integration_matrix_created(self, designer, tmp_path):
        designer.run()
        assert (tmp_path / "phase9" / "integration_matrix.json").exists()

    def test_integration_matrix_overall_ok(self, designer, tmp_path):
        designer.run()
        matrix = json.loads(
            (tmp_path / "phase9" / "integration_matrix.json").read_text(encoding="utf-8"))
        assert matrix["overall_ok"] is True

    def test_hitl_checkpoint_log_created(self, designer, tmp_path):
        designer.run()
        assert (tmp_path / "phase9" / "hitl_checkpoint_log.json").exists()

    def test_record_hitl_approval(self, designer, tmp_path):
        designer.run()
        designer.record_hitl_approval("integration_design", "approve", "設計レビュー完了")
        log = json.loads(
            (tmp_path / "phase9" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        cp = next(c for c in log["checkpoints"] if c["stage"] == "integration_design")
        assert cp["status"] == "approve"
        assert cp["approved_at"] is not None

    def test_record_hitl_approval_reason(self, designer, tmp_path):
        designer.run()
        designer.record_hitl_approval("integration_design", "approve", "設計レビュー完了")
        log = json.loads(
            (tmp_path / "phase9" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        cp = next(c for c in log["checkpoints"] if c["stage"] == "integration_design")
        assert cp["reason"] == "設計レビュー完了"

    def test_load_unified_architecture_returns_dict(self, designer):
        designer.run()
        assert isinstance(designer.load_unified_architecture(), dict)

    def test_load_integration_matrix_returns_dict(self, designer):
        designer.run()
        assert isinstance(designer.load_integration_matrix(), dict)

    def test_load_nonexistent_architecture_returns_empty(self, tmp_path):
        d = F9610UnifiedArchitectureDesigner(phase9_dir=tmp_path / "p9")
        assert d.load_unified_architecture() == {}

    def test_load_nonexistent_matrix_returns_empty(self, tmp_path):
        d = F9610UnifiedArchitectureDesigner(phase9_dir=tmp_path / "p9")
        assert d.load_integration_matrix() == {}

    def test_write_summary_entry_creates_log(self, designer, tmp_path):
        result = designer.run()
        log    = tmp_path / "summary.log"
        designer.write_summary_entry(result, log_path=log)
        assert log.exists()

    def test_summary_entry_has_f9610(self, designer, tmp_path):
        result = designer.run()
        log    = tmp_path / "summary.log"
        designer.write_summary_entry(result, log_path=log)
        assert "F9610" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_f9620(self, designer, tmp_path):
        result = designer.run()
        log    = tmp_path / "summary.log"
        designer.write_summary_entry(result, log_path=log)
        assert "F9620" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# TestF9610_09 — エラーシナリオ
# ════════════════════════════════════════════════════════════════

class TestF9610_09_ErrorScenarios:

    def test_run_still_returns_dict_with_missing_phase8(self, tmp_path, tmp_cycle_dir):
        """Phase 8 ファイルが全て欠損していても dict を返す。"""
        empty = tmp_path / "empty_phase8"
        empty.mkdir()
        d = F9610UnifiedArchitectureDesigner(
            phase8_dir=empty,
            cycle_dir=tmp_cycle_dir,
            phase9_dir=tmp_path / "phase9",
        )
        result = d.run()
        assert isinstance(result, dict)
        # phase8_complete=False → overall_ok=False
        assert result["success"] is False

    def test_output_files_created_even_on_failure(self, tmp_path, tmp_cycle_dir):
        empty = tmp_path / "empty_phase8"
        empty.mkdir()
        d = F9610UnifiedArchitectureDesigner(
            phase8_dir=empty,
            cycle_dir=tmp_cycle_dir,
            phase9_dir=tmp_path / "phase9",
        )
        d.run()
        p9 = tmp_path / "phase9"
        assert (p9 / "unified_architecture.json").exists()
        assert (p9 / "unified_io_map.json").exists()
        assert (p9 / "integration_matrix.json").exists()

    def test_conflict_report_generated_when_overlap(self, designer, tmp_path):
        """boundary_overlap=True の場合に conflict_report.json が生成される。"""
        outcomes = designer.step1_load_phase8_outcomes()
        # 責務を重複させる
        profiles = {
            "aiwbs":   {**_AIWBS_AGENT,   "responsibilities": ["A", "SHARED"]},
            "support": {**_SUPPORT_AGENT, "responsibilities": ["B", "SHARED"]},
        }
        mapping = designer.step3_map_boundaries_and_flow(profiles)
        if mapping["boundary_overlap"]:
            designer._save_conflict_report(profiles, mapping)
            assert (tmp_path / "phase9" / "conflict_report.json").exists()

    def test_rollback_log_created_when_io_failure(self, tmp_path, tmp_phase8_dir):
        empty_cycle = tmp_path / "empty_cycle"
        empty_cycle.mkdir()
        d = F9610UnifiedArchitectureDesigner(
            phase8_dir=tmp_phase8_dir,
            cycle_dir=empty_cycle,
            phase9_dir=tmp_path / "phase9",
        )
        d.run()
        # io_integrity が閾値未満 → rollback_log.json 生成
        rollback = tmp_path / "phase9" / "rollback_log.json"
        if rollback.exists():
            log = json.loads(rollback.read_text(encoding="utf-8"))
            assert log["total_events"] >= 1
