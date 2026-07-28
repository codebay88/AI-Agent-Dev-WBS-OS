"""
Tests for F9630 final_validation_and_approval
"""
import json
import pytest
from pathlib import Path
from datetime import datetime

from src.phase9.f9630_final_validation import (
    F9630FinalValidationAndApproval,
    OPT_SCORE_THRESHOLD,
    IO_INTEGRITY_REQUIRED,
    HITL_APPROVAL_COUNT,
    _HITL_APPROVAL_POINTS,
)

# ── フィクスチャ ────────────────────────────────────────────────

_ARCH = {
    "generated_at": "2026-07-23T00:00:00",
    "module": "F9610",
    "agents": {
        "AIWBS": {
            "id": "AIWBS",
            "modules": ["F10", "F20", "F30", "F40", "F50", "F60", "F70", "F80", "F90"],
        },
        "SUPPORT": {
            "id": "SUPPORT",
            "modules": ["F9510", "F9520", "F9530"],
        },
    },
    "io_integrity": 1.0,
    "all_rules_passed": True,
    "mece_ok": True,
    "overall_ok": True,
}

_MATRIX = {
    "generated_at": "2026-07-23T00:00:00",
    "module": "F9610",
    "overall_ok": True,
    "checks": [],
}

_PROFILE = {
    "generated_at": "2026-07-23T00:00:00",
    "module": "F9620",
    "phase9_stage": "autonomous_operation",
    "loop_count": 3,
    "hitl_flow_defined": True,
    "knowledge_cycle_linked": True,
    "failure_repository_linked": True,
    "opt_score": 0.9119,
    "sandbox_ok": True,
    "sandbox_success_rate": 1.0,
    "control_loop_config_consistent": True,
    "success": True,
}

_OBS_LOG = {
    "generated_at": "2026-07-23T00:00:00",
    "module": "F9620",
    "sandbox_ok": True,
    "success_rate": 1.0,
    "trials": [
        {"trial": 1, "status": "PASS"},
        {"trial": 2, "status": "PASS"},
        {"trial": 3, "status": "PASS"},
    ],
}

_CTRL_CFG = {
    "generated_at": "2026-07-23T00:00:00",
    "module": "F9620",
    "loop_count": 3,
    "control_loop_config_consistent": True,
    "loops": [
        {"loop_id": "L-001", "name": "WBS 生成ループ"},
        {"loop_id": "L-002", "name": "展開・安定化ループ"},
        {"loop_id": "L-003", "name": "知識循環ループ"},
    ],
}

_OPT_REPORT = {
    "generated_at": "2026-07-23T00:00:00",
    "module": "OptimizationEvaluator",
    "phase7_complete": True,
    "phase8_ready": True,
    "summary": {
        "total_patterns": 48,
        "avg_optimization_index": 0.9119,
    },
    "by_category": {
        "operational":   {"avg_opt": 0.9310},
        "improvement":   {"avg_opt": 0.9838},
        "maintenance":   {"avg_opt": 0.6760},
        "environment":   {"avg_opt": 0.6998},
    },
}

_LEARNING_DATASET = {
    "generated_at": "2026-07-23T00:00:00",
    "total_entries": 48,
    "entries": [],
}

_LEARNING_PATTERNS = {
    "generated_at": "2026-07-23T00:00:00",
    "total_patterns": 48,
    "patterns": [],
}

_FAILURE_REPO = {
    "generated_at": "2026-07-23T00:00:00",
    "known_failures": [
        {"id": "FL-001", "module": "F10", "type": "HITL"},
        {"id": "FL-002", "module": "F10", "type": "RETRY"},
        {"id": "FL-003", "module": "F60", "type": "HITL_required"},
        {"id": "FL-004", "module": "F80", "type": "HITL"},
        {"id": "FL-005", "module": "F40", "type": "HITL_required"},
    ],
}


@pytest.fixture()
def tmp_dirs(tmp_path):
    phase9_dir = tmp_path / "docs" / "phase9"
    cycle_dir  = tmp_path / "docs" / "knowledge_cycle"
    phase6_dir = tmp_path / "docs" / "phase6"
    log_dir    = tmp_path / "docs" / "phase4" / "logs"

    for d in (phase9_dir, cycle_dir, phase6_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Phase 9 入力
    (phase9_dir / "unified_architecture.json").write_text(
        json.dumps(_ARCH), encoding="utf-8")
    (phase9_dir / "integration_matrix.json").write_text(
        json.dumps(_MATRIX), encoding="utf-8")
    (phase9_dir / "autonomous_operation_profile.json").write_text(
        json.dumps(_PROFILE), encoding="utf-8")
    (phase9_dir / "runtime_observation_log.json").write_text(
        json.dumps(_OBS_LOG), encoding="utf-8")
    (phase9_dir / "control_loop_config.json").write_text(
        json.dumps(_CTRL_CFG), encoding="utf-8")

    # knowledge_cycle 入力
    (cycle_dir / "optimization_report.json").write_text(
        json.dumps(_OPT_REPORT), encoding="utf-8")
    (cycle_dir / "learning_dataset.json").write_text(
        json.dumps(_LEARNING_DATASET), encoding="utf-8")
    (cycle_dir / "learning_patterns.json").write_text(
        json.dumps(_LEARNING_PATTERNS), encoding="utf-8")

    # failure_repository
    (phase6_dir / "failure_repository.json").write_text(
        json.dumps(_FAILURE_REPO), encoding="utf-8")

    # summary.log
    (log_dir / "summary.log").write_text("", encoding="utf-8")

    return {
        "phase9_dir": phase9_dir,
        "cycle_dir":  cycle_dir,
        "phase6_dir": phase6_dir,
        "log_dir":    log_dir,
        "log_path":   log_dir / "summary.log",
    }


@pytest.fixture()
def validator(tmp_dirs):
    return F9630FinalValidationAndApproval(
        phase9_dir  = tmp_dirs["phase9_dir"],
        cycle_dir   = tmp_dirs["cycle_dir"],
        phase6_dir  = tmp_dirs["phase6_dir"],
        summary_log = tmp_dirs["log_path"],
    )


# ── Step 1: 自律運用結果の読み込み ────────────────────────────

class TestStep1LoadAndExtractMetrics:
    def test_returns_dict(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert isinstance(r, dict)

    def test_loaded_key(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert "loaded" in r

    def test_missing_key(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert "missing" in r

    def test_all_loaded_true(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert r["all_loaded"] is True

    def test_all_loaded_false_when_missing(self, tmp_dirs):
        # runtime_observation_log を削除
        (tmp_dirs["phase9_dir"] / "runtime_observation_log.json").unlink()
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.step1_load_and_extract_metrics()
        assert r["all_loaded"] is False
        assert "runtime_observation_log" in r["missing"]

    def test_sandbox_ok_true(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert r["sandbox_ok"] is True

    def test_success_rate(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert r["success_rate"] == 1.0

    def test_loop_count(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert r["loop_count"] == 3

    def test_config_consistent(self, validator):
        r = validator.step1_load_and_extract_metrics()
        assert r["config_consistent"] is True

    def test_sandbox_ok_false_when_no_file(self, tmp_dirs):
        (tmp_dirs["phase9_dir"] / "runtime_observation_log.json").unlink()
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.step1_load_and_extract_metrics()
        assert r["sandbox_ok"] is False


# ── Step 2: 構造整合性検証 ────────────────────────────────────

class TestStep2VerifyStructuralConsistency:
    @pytest.fixture(autouse=True)
    def _setup(self, validator):
        self.v = validator
        self.metrics = self.v.step1_load_and_extract_metrics()

    def test_returns_dict(self):
        r = self.v.step2_verify_structural_consistency(self.metrics)
        assert isinstance(r, dict)

    def test_arch_ok_true(self):
        r = self.v.step2_verify_structural_consistency(self.metrics)
        assert r["arch_ok"] is True

    def test_loop_ok_true(self):
        r = self.v.step2_verify_structural_consistency(self.metrics)
        assert r["loop_ok"] is True

    def test_matrix_ok_true(self):
        r = self.v.step2_verify_structural_consistency(self.metrics)
        assert r["matrix_ok"] is True

    def test_structural_ok_true(self):
        r = self.v.step2_verify_structural_consistency(self.metrics)
        assert r["structural_ok"] is True

    def test_checks_list(self):
        r = self.v.step2_verify_structural_consistency(self.metrics)
        assert isinstance(r["checks"], list)
        assert len(r["checks"]) >= 3

    def test_structural_ok_false_when_no_arch(self, tmp_dirs):
        (tmp_dirs["phase9_dir"] / "unified_architecture.json").write_text(
            json.dumps({}), encoding="utf-8")
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        m = v.step1_load_and_extract_metrics()
        r = v.step2_verify_structural_consistency(m)
        assert r["structural_ok"] is False

    def test_loop_ok_false_when_loop_count_zero(self, tmp_dirs):
        bad_cfg = dict(_CTRL_CFG)
        bad_cfg["loop_count"] = 0
        (tmp_dirs["phase9_dir"] / "control_loop_config.json").write_text(
            json.dumps(bad_cfg), encoding="utf-8")
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        m = v.step1_load_and_extract_metrics()
        r = v.step2_verify_structural_consistency(m)
        assert r["loop_ok"] is False


# ── Step 3: knowledge_cycle / failure_repository 循環確認 ────

class TestStep3VerifyKnowledgeCycle:
    def test_returns_dict(self, validator):
        r = validator.step3_verify_knowledge_cycle()
        assert isinstance(r, dict)

    def test_cycle_ok_true(self, validator):
        r = validator.step3_verify_knowledge_cycle()
        assert r["cycle_ok"] is True

    def test_repo_ok_true(self, validator):
        r = validator.step3_verify_knowledge_cycle()
        assert r["repo_ok"] is True

    def test_cycle_files_all_exist(self, validator):
        r = validator.step3_verify_knowledge_cycle()
        assert all(r["cycle_files"].values())

    def test_repo_entries(self, validator):
        r = validator.step3_verify_knowledge_cycle()
        assert r["repo_entries"] == 5

    def test_cycle_complete_true(self, validator):
        r = validator.step3_verify_knowledge_cycle()
        assert r["cycle_complete"] is True

    def test_cycle_ok_false_when_missing_file(self, tmp_dirs):
        (tmp_dirs["cycle_dir"] / "learning_patterns.json").unlink()
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.step3_verify_knowledge_cycle()
        assert r["cycle_ok"] is False
        assert r["cycle_complete"] is False

    def test_repo_entries_zero_when_empty_repo(self, tmp_dirs):
        (tmp_dirs["phase6_dir"] / "failure_repository.json").write_text(
            json.dumps({"known_failures": []}), encoding="utf-8")
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.step3_verify_knowledge_cycle()
        assert r["repo_entries"] == 0


# ── Step 4: optimization_report 最終評価 ─────────────────────

class TestStep4EvaluateOptimizationScore:
    def test_returns_dict(self, validator):
        r = validator.step4_evaluate_optimization_score()
        assert isinstance(r, dict)

    def test_opt_score(self, validator):
        r = validator.step4_evaluate_optimization_score()
        assert r["opt_score"] == pytest.approx(0.9119, abs=0.001)

    def test_score_ok_true(self, validator):
        r = validator.step4_evaluate_optimization_score()
        assert r["score_ok"] is True

    def test_phase7_complete_true(self, validator):
        r = validator.step4_evaluate_optimization_score()
        assert r["phase7_complete"] is True

    def test_by_category_dict(self, validator):
        r = validator.step4_evaluate_optimization_score()
        assert isinstance(r["by_category"], dict)

    def test_score_ok_false_when_low_score(self, tmp_dirs):
        bad_opt = dict(_OPT_REPORT)
        bad_opt["summary"] = {"total_patterns": 48, "avg_optimization_index": 0.50}
        (tmp_dirs["cycle_dir"] / "optimization_report.json").write_text(
            json.dumps(bad_opt), encoding="utf-8")
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.step4_evaluate_optimization_score()
        assert r["score_ok"] is False

    def test_score_zero_when_no_file(self, tmp_dirs):
        (tmp_dirs["cycle_dir"] / "optimization_report.json").unlink()
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.step4_evaluate_optimization_score()
        assert r["opt_score"] == 0.0
        assert r["score_ok"] is False

    def test_opt_score_threshold(self):
        assert OPT_SCORE_THRESHOLD == 0.90


# ── Step 5: HITL 最終承認（6箇所）────────────────────────────

class TestStep5ConfirmHitlApprovals:
    def test_returns_dict(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        assert isinstance(r, dict)

    def test_approvals_list(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        assert isinstance(r["approvals"], list)

    def test_approvals_count_six(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        assert len(r["approvals"]) == HITL_APPROVAL_COUNT

    def test_all_approved_auto(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        assert r["all_approved"] is True
        assert r["hitl_final_ok"] is True

    def test_approved_count_six_auto(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        assert r["approved_count"] == HITL_APPROVAL_COUNT

    def test_rejected_count_zero_auto(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        assert r["rejected_count"] == 0

    def test_custom_hitl_fn_approve(self, validator):
        r = validator.step5_confirm_hitl_approvals(hitl_fn=lambda p: "approve")
        assert r["all_approved"] is True

    def test_custom_hitl_fn_reject_all(self, validator):
        r = validator.step5_confirm_hitl_approvals(hitl_fn=lambda p: "reject")
        assert r["all_approved"] is False
        assert r["rejected_count"] == HITL_APPROVAL_COUNT
        assert r["hitl_final_ok"] is False

    def test_custom_hitl_fn_partial(self, validator):
        # H-006 のみ reject
        def fn(point_id):
            return "reject" if point_id == "H-006" else "approve"
        r = validator.step5_confirm_hitl_approvals(hitl_fn=fn)
        assert r["rejected_count"] == 1
        assert r["all_approved"] is False

    def test_approval_entries_have_id(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        for a in r["approvals"]:
            assert "id" in a

    def test_approval_entries_have_decided_at(self, validator):
        r = validator.step5_confirm_hitl_approvals()
        for a in r["approvals"]:
            assert "decided_at" in a

    def test_hitl_approval_count_constant(self):
        assert HITL_APPROVAL_COUNT == 6

    def test_hitl_approval_points_count(self):
        assert len(_HITL_APPROVAL_POINTS) == 6

    def test_hitl_approval_points_ids(self):
        ids = {p["id"] for p in _HITL_APPROVAL_POINTS}
        for expected in ("H-001", "H-002", "H-003", "H-004", "H-005", "H-006"):
            assert expected in ids


# ── Step 6: final_validation_report.json 生成 ─────────────────

class TestStep6GenerateFinalReport:
    @pytest.fixture(autouse=True)
    def _setup(self, validator):
        self.v = validator
        m = self.v.step1_load_and_extract_metrics()
        st = self.v.step2_verify_structural_consistency(m)
        cy = self.v.step3_verify_knowledge_cycle()
        op = self.v.step4_evaluate_optimization_score()
        ht = self.v.step5_confirm_hitl_approvals()
        self.report = self.v.step6_generate_final_report(m, st, cy, op, ht)

    def test_returns_dict(self):
        assert isinstance(self.report, dict)

    def test_module(self):
        assert self.report["module"] == "F9630"

    def test_phase9_stage(self):
        assert self.report["phase9_stage"] == "final_validation"

    def test_success_true(self):
        assert self.report["success"] is True

    def test_validation_dict(self):
        assert isinstance(self.report["validation"], dict)

    def test_io_integrity_ok(self):
        assert self.report["validation"]["io_integrity_ok"] is True

    def test_io_integrity_value(self):
        assert self.report["validation"]["io_integrity"] == IO_INTEGRITY_REQUIRED

    def test_opt_score_ok(self):
        assert self.report["validation"]["opt_score_ok"] is True

    def test_reproducibility_passed(self):
        assert self.report["validation"]["reproducibility_passed"] is True

    def test_structural_ok(self):
        assert self.report["validation"]["structural_ok"] is True

    def test_cycle_complete(self):
        assert self.report["validation"]["cycle_complete"] is True

    def test_hitl_final_approval(self):
        assert self.report["validation"]["hitl_final_approval"] is True

    def test_all_passed(self):
        assert self.report["validation"]["all_passed"] is True

    def test_generated_at(self):
        assert "generated_at" in self.report

    def test_validation_log_list(self):
        assert isinstance(self.report["validation_log"], list)


# ── Step 7: completion_summary.json 統合 ─────────────────────

class TestStep7GenerateCompletionSummary:
    @pytest.fixture(autouse=True)
    def _setup(self, validator):
        self.v = validator
        m  = self.v.step1_load_and_extract_metrics()
        st = self.v.step2_verify_structural_consistency(m)
        cy = self.v.step3_verify_knowledge_cycle()
        op = self.v.step4_evaluate_optimization_score()
        ht = self.v.step5_confirm_hitl_approvals()
        rp = self.v.step6_generate_final_report(m, st, cy, op, ht)
        self.summary = self.v.step7_generate_completion_summary(
            rp, m, st, cy, op, ht)

    def test_returns_dict(self):
        assert isinstance(self.summary, dict)

    def test_system_complete_true(self):
        assert self.summary["system_complete"] is True

    def test_phase9_stage(self):
        assert self.summary["phase9_stage"] == "final_validation"

    def test_module(self):
        assert self.summary["module"] == "F9630"

    def test_phase_summary_has_phase9(self):
        assert "Phase9" in self.summary["phase_summary"]

    def test_phase9_status_complete(self):
        assert self.summary["phase_summary"]["Phase9"]["status"] == "complete"

    def test_final_metrics_dict(self):
        assert isinstance(self.summary["final_metrics"], dict)

    def test_final_metrics_opt_score(self):
        assert self.summary["final_metrics"]["opt_score"] == pytest.approx(0.9119, abs=0.001)

    def test_final_metrics_loop_count(self):
        assert self.summary["final_metrics"]["loop_count"] == 3

    def test_final_metrics_hitl_approvals(self):
        assert self.summary["final_metrics"]["hitl_approvals"] == HITL_APPROVAL_COUNT

    def test_validation_criteria_dict(self):
        assert isinstance(self.summary["validation_criteria"], dict)

    def test_validation_criteria_all_true(self):
        for v in self.summary["validation_criteria"].values():
            assert v is True

    def test_outputs_dict(self):
        assert isinstance(self.summary["outputs"], dict)
        assert "system_complete_flag" in self.summary["outputs"]

    def test_phase7_info(self):
        p7 = self.summary["phase_summary"]["Phase7"]
        assert p7["learning_entries"] == 48

    def test_phase8_info(self):
        p8 = self.summary["phase_summary"]["Phase8"]
        assert "F9510" in p8["modules"]


# ── Step 8: system_complete_flag 書き込み ────────────────────

class TestStep8WriteSystemCompleteFlag:
    def test_flag_file_created(self, validator, tmp_dirs):
        m  = validator.step1_load_and_extract_metrics()
        st = validator.step2_verify_structural_consistency(m)
        cy = validator.step3_verify_knowledge_cycle()
        op = validator.step4_evaluate_optimization_score()
        ht = validator.step5_confirm_hitl_approvals()
        rp = validator.step6_generate_final_report(m, st, cy, op, ht)
        sm = validator.step7_generate_completion_summary(rp, m, st, cy, op, ht)
        result = validator.step8_write_system_complete_flag(sm)
        assert result is True
        flag_path = tmp_dirs["phase9_dir"] / "system_complete_flag"
        assert flag_path.exists()

    def test_flag_content_true(self, validator, tmp_dirs):
        m  = validator.step1_load_and_extract_metrics()
        st = validator.step2_verify_structural_consistency(m)
        cy = validator.step3_verify_knowledge_cycle()
        op = validator.step4_evaluate_optimization_score()
        ht = validator.step5_confirm_hitl_approvals()
        rp = validator.step6_generate_final_report(m, st, cy, op, ht)
        sm = validator.step7_generate_completion_summary(rp, m, st, cy, op, ht)
        validator.step8_write_system_complete_flag(sm)
        content = (tmp_dirs["phase9_dir"] / "system_complete_flag").read_text(
            encoding="utf-8")
        assert "system_complete: true" in content

    def test_flag_content_false_when_incomplete(self, validator, tmp_dirs):
        summary = {"system_complete": False, "phase9_stage": "final_validation"}
        validator.step8_write_system_complete_flag(summary)
        content = (tmp_dirs["phase9_dir"] / "system_complete_flag").read_text(
            encoding="utf-8")
        assert "system_complete: false" in content

    def test_flag_content_phase9_stage(self, validator, tmp_dirs):
        m  = validator.step1_load_and_extract_metrics()
        st = validator.step2_verify_structural_consistency(m)
        cy = validator.step3_verify_knowledge_cycle()
        op = validator.step4_evaluate_optimization_score()
        ht = validator.step5_confirm_hitl_approvals()
        rp = validator.step6_generate_final_report(m, st, cy, op, ht)
        sm = validator.step7_generate_completion_summary(rp, m, st, cy, op, ht)
        validator.step8_write_system_complete_flag(sm)
        content = (tmp_dirs["phase9_dir"] / "system_complete_flag").read_text(
            encoding="utf-8")
        assert "phase9_stage: final_validation" in content


# ── run() 統合テスト ──────────────────────────────────────────

class TestRunIntegration:
    def test_run_returns_dict(self, validator):
        r = validator.run()
        assert isinstance(r, dict)

    def test_run_success_true(self, validator):
        r = validator.run()
        assert r["success"] is True

    def test_run_system_complete_true(self, validator):
        r = validator.run()
        assert r["system_complete"] is True

    def test_run_phase9_stage(self, validator):
        r = validator.run()
        assert r["phase9_stage"] == "final_validation"

    def test_run_creates_final_report_json(self, validator, tmp_dirs):
        validator.run()
        assert (tmp_dirs["phase9_dir"] / "final_validation_report.json").exists()

    def test_run_creates_hitl_final_approval_log(self, validator, tmp_dirs):
        validator.run()
        assert (tmp_dirs["phase9_dir"] / "hitl_final_approval_log.json").exists()

    def test_run_creates_system_complete_flag(self, validator, tmp_dirs):
        validator.run()
        assert (tmp_dirs["phase9_dir"] / "system_complete_flag").exists()

    def test_run_creates_completion_summary_json(self, validator, tmp_dirs):
        validator.run()
        assert (tmp_dirs["phase9_dir"] / "completion_summary.json").exists()

    def test_run_final_report_json_valid(self, validator, tmp_dirs):
        validator.run()
        data = json.loads(
            (tmp_dirs["phase9_dir"] / "final_validation_report.json").read_text(
                encoding="utf-8"))
        assert data["success"] is True
        assert data["phase9_stage"] == "final_validation"

    def test_run_completion_summary_system_complete(self, validator, tmp_dirs):
        validator.run()
        data = json.loads(
            (tmp_dirs["phase9_dir"] / "completion_summary.json").read_text(
                encoding="utf-8"))
        assert data["system_complete"] is True

    def test_run_hitl_approval_log_valid(self, validator, tmp_dirs):
        validator.run()
        data = json.loads(
            (tmp_dirs["phase9_dir"] / "hitl_final_approval_log.json").read_text(
                encoding="utf-8"))
        assert data["approved_count"] == HITL_APPROVAL_COUNT
        assert data["all_approved"] is True

    def test_run_with_reject_hitl(self, validator):
        r = validator.run(hitl_fn=lambda p: "reject")
        assert r["success"] is False
        assert r["system_complete"] is False

    def test_run_rollback_log_created_on_failure(self, validator, tmp_dirs):
        # sandbox_ok = False にする
        bad_obs = dict(_OBS_LOG)
        bad_obs["sandbox_ok"] = False
        bad_obs["success_rate"] = 0.0
        (tmp_dirs["phase9_dir"] / "runtime_observation_log.json").write_text(
            json.dumps(bad_obs), encoding="utf-8")
        validator.run()
        rollback = tmp_dirs["phase9_dir"] / "rollback_log.json"
        assert rollback.exists()

    def test_run_no_flag_when_success_false(self, validator, tmp_dirs):
        # opt_score を下げて失敗にする
        bad_opt = dict(_OPT_REPORT)
        bad_opt["summary"] = {"total_patterns": 48, "avg_optimization_index": 0.50}
        (tmp_dirs["cycle_dir"] / "optimization_report.json").write_text(
            json.dumps(bad_opt), encoding="utf-8")
        bad_obs = dict(_OBS_LOG)
        bad_obs["sandbox_ok"] = False
        (tmp_dirs["phase9_dir"] / "runtime_observation_log.json").write_text(
            json.dumps(bad_obs), encoding="utf-8")
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        r = v.run()
        assert r["success"] is False

    def test_run_updates_hitl_checkpoint_log(self, validator, tmp_dirs):
        validator.run()
        ckpt = tmp_dirs["phase9_dir"] / "hitl_checkpoint_log.json"
        assert ckpt.exists()
        data = json.loads(ckpt.read_text(encoding="utf-8"))
        assert "checkpoints" in data

    def test_run_hitl_checkpoint_system_complete(self, validator, tmp_dirs):
        validator.run()
        data = json.loads(
            (tmp_dirs["phase9_dir"] / "hitl_checkpoint_log.json").read_text(
                encoding="utf-8"))
        assert data.get("system_complete") is True

    def test_run_report_has_detail(self, validator):
        r = validator.run()
        assert "detail" in r["report"]


# ── write_summary_entry テスト ────────────────────────────────

class TestWriteSummaryEntry:
    def test_summary_log_updated(self, validator, tmp_dirs):
        r = validator.run()
        validator.write_summary_entry(r, tmp_dirs["log_path"])
        content = tmp_dirs["log_path"].read_text(encoding="utf-8")
        assert "F9630" in content

    def test_summary_log_contains_system_complete(self, validator, tmp_dirs):
        r = validator.run()
        validator.write_summary_entry(r, tmp_dirs["log_path"])
        content = tmp_dirs["log_path"].read_text(encoding="utf-8")
        assert "system_complete" in content

    def test_summary_log_contains_phase9_stage(self, validator, tmp_dirs):
        r = validator.run()
        validator.write_summary_entry(r, tmp_dirs["log_path"])
        content = tmp_dirs["log_path"].read_text(encoding="utf-8")
        assert "final_validation" in content


# ── 公開メソッドテスト ────────────────────────────────────────

class TestPublicLoaders:
    def test_load_final_report_after_run(self, validator):
        validator.run()
        data = validator.load_final_report()
        assert data["module"] == "F9630"
        assert data["success"] is True

    def test_load_final_report_empty_when_no_file(self, tmp_dirs):
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        assert v.load_final_report() == {}

    def test_load_completion_summary_after_run(self, validator):
        validator.run()
        data = validator.load_completion_summary()
        assert data["system_complete"] is True

    def test_load_completion_summary_empty_when_no_file(self, tmp_dirs):
        v = F9630FinalValidationAndApproval(
            phase9_dir=tmp_dirs["phase9_dir"],
            cycle_dir=tmp_dirs["cycle_dir"],
            phase6_dir=tmp_dirs["phase6_dir"],
        )
        assert v.load_completion_summary() == {}
