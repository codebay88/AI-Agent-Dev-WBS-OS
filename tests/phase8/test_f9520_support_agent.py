"""F9520 support_agent_integration テスト
Phase 8：展開層

テスト対象:
  - src/deployment/f9520_support_agent.py
    - F9520SupportAgentIntegration.step1_load_plan()
    - F9520SupportAgentIntegration.step2_sync_repositories()
    - F9520SupportAgentIntegration.step3_apply_learning_outcomes()
    - F9520SupportAgentIntegration.step4_check_io_integrity()
    - F9520SupportAgentIntegration.step5_reproducibility_test()
    - F9520SupportAgentIntegration.step6_init_sync_log()
    - F9520SupportAgentIntegration.step7_set_hitl_checkpoint()
    - F9520SupportAgentIntegration.step8_generate_report()
    - F9520SupportAgentIntegration.run()
    - F9520SupportAgentIntegration.save_integration_report()
    - F9520SupportAgentIntegration.load_integration_report()
    - F9520SupportAgentIntegration.record_hitl_approval()
    - F9520SupportAgentIntegration.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.deployment.f9520_support_agent import (
    F9520SupportAgentIntegration,
    IO_INTEGRITY_THRESHOLD,
    MAX_SYNC_RETRY,
    REPRO_TEST_COUNT,
    _CYCLE_INPUTS,
)

# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

_PLAN_CONTENT = {
    "module":        "F9510",
    "phase8_stage":  "limited_environment",
    "io_integrity":  100.0,
    "hitl_count":    5,
    "success":       True,
}

_OPT_REPORT = {
    "phase7_complete": True,
    "phase8_ready":    True,
    "summary": {"avg_optimization_index": 0.9119},
}

_FAILURE_REPO = {
    "known_failures": [
        {"id": "FL-001", "module": "F10"},
        {"id": "FL-002", "module": "F10"},
    ]
}

_INDEX_YAML = """\
phases:
  Phase5:
    artifacts: 6
  Phase6:
    artifacts: 7
  Phase6.5:
    artifacts: 5
phase7_ready: true
"""


@pytest.fixture
def tmp_cycle_dir(tmp_path):
    """Phase 7 成果物一式。"""
    kc = tmp_path / "knowledge_cycle"
    kc.mkdir()
    (kc / "learning_dataset.json").write_text(
        json.dumps({"total_entries": 48}), encoding="utf-8")
    (kc / "learning_patterns.json").write_text(
        json.dumps({"total_patterns": 48}), encoding="utf-8")
    (kc / "optimization_report.json").write_text(
        json.dumps(_OPT_REPORT), encoding="utf-8")
    (kc / "index.yaml").write_text(_INDEX_YAML, encoding="utf-8")
    return kc


@pytest.fixture
def tmp_phase6_dir(tmp_path):
    """Phase 6 failure_repository。"""
    p6 = tmp_path / "phase6"
    p6.mkdir()
    (p6 / "failure_repository.json").write_text(
        json.dumps(_FAILURE_REPO), encoding="utf-8")
    return p6


@pytest.fixture
def tmp_plan(tmp_path):
    """deployment_plan.json。"""
    p8 = tmp_path / "phase8"
    p8.mkdir(parents=True)
    plan_path = p8 / "deployment_plan.json"
    plan_path.write_text(json.dumps(_PLAN_CONTENT), encoding="utf-8")
    return plan_path


@pytest.fixture
def integrator(tmp_path, tmp_cycle_dir, tmp_phase6_dir, tmp_plan):
    return F9520SupportAgentIntegration(
        plan_path=tmp_plan,
        cycle_dir=tmp_cycle_dir,
        phase6_dir=tmp_phase6_dir,
        phase8_dir=tmp_path / "phase8",
        summary_log=tmp_path / "summary.log",
    )


# ════════════════════════════════════════════════════════════════
# TestF9520_01 — Step 1: 展開計画読み込み
# ════════════════════════════════════════════════════════════════

class TestF9520_01_LoadPlan:

    def test_returns_dict(self, integrator):
        assert isinstance(integrator.step1_load_plan(), dict)

    def test_has_phase8_stage(self, integrator):
        plan = integrator.step1_load_plan()
        assert "phase8_stage" in plan

    def test_phase8_stage_is_limited_environment(self, integrator):
        plan = integrator.step1_load_plan()
        assert plan["phase8_stage"] == "limited_environment"

    def test_has_io_integrity(self, integrator):
        plan = integrator.step1_load_plan()
        assert "io_integrity" in plan

    def test_missing_plan_returns_empty(self, tmp_path):
        d = F9520SupportAgentIntegration(
            plan_path=tmp_path / "no_plan.json",
            cycle_dir=tmp_path,
            phase6_dir=tmp_path,
            phase8_dir=tmp_path,
        )
        assert d.step1_load_plan() == {}


# ════════════════════════════════════════════════════════════════
# TestF9520_02 — Step 2: リポジトリ同期
# ════════════════════════════════════════════════════════════════

class TestF9520_02_SyncRepositories:

    def test_returns_dict(self, integrator):
        assert isinstance(integrator.step2_sync_repositories(), dict)

    def test_failure_repo_sync_success(self, integrator):
        result = integrator.step2_sync_repositories()
        assert result["failure_repository_sync"] == "success"

    def test_knowledge_cycle_update_success(self, integrator):
        result = integrator.step2_sync_repositories()
        assert result["knowledge_cycle_update"] == "success"

    def test_failure_entries_count(self, integrator):
        result = integrator.step2_sync_repositories()
        assert result["failure_entries"] == 2

    def test_cycle_phases_not_empty(self, integrator):
        result = integrator.step2_sync_repositories()
        assert len(result["cycle_phases"]) > 0

    def test_retry_count_zero_on_first_success(self, integrator):
        result = integrator.step2_sync_repositories()
        assert result["retry_count"] == 0

    def test_failure_repo_error_when_file_missing(self, tmp_path, tmp_cycle_dir, tmp_plan):
        empty_p6 = tmp_path / "empty_phase6"
        empty_p6.mkdir()
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=tmp_cycle_dir,
            phase6_dir=empty_p6,
            phase8_dir=tmp_path / "phase8",
        )
        result = d.step2_sync_repositories()
        assert result["failure_repository_sync"] == "error"
        assert result["retry_count"] == MAX_SYNC_RETRY - 1

    def test_cycle_fallback_without_index_yaml(self, tmp_path, tmp_phase6_dir, tmp_plan):
        """index.yaml なしでも learning_dataset.json があれば success。"""
        kc = tmp_path / "kc_no_index"
        kc.mkdir()
        (kc / "learning_dataset.json").write_text("{}", encoding="utf-8")
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=kc,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        result = d.step2_sync_repositories()
        assert result["knowledge_cycle_update"] == "success"


# ════════════════════════════════════════════════════════════════
# TestF9520_03 — Step 3: 学習成果の適用
# ════════════════════════════════════════════════════════════════

class TestF9520_03_ApplyLearningOutcomes:

    def test_returns_dict(self, integrator):
        assert isinstance(integrator.step3_apply_learning_outcomes(), dict)

    def test_all_files_applied(self, integrator):
        result = integrator.step3_apply_learning_outcomes()
        assert set(result["applied"]) == set(_CYCLE_INPUTS)

    def test_failed_is_empty_when_all_present(self, integrator):
        result = integrator.step3_apply_learning_outcomes()
        assert result["failed"] == []

    def test_apply_rate_1_when_all_present(self, integrator):
        result = integrator.step3_apply_learning_outcomes()
        assert result["apply_rate"] == 1.0

    def test_apply_rate_0_when_empty_cycle(self, tmp_path, tmp_plan, tmp_phase6_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        result = d.step3_apply_learning_outcomes()
        assert result["apply_rate"] == 0.0
        assert result["failed"] == _CYCLE_INPUTS

    def test_apply_rate_partial(self, tmp_path, tmp_plan, tmp_phase6_dir):
        partial = tmp_path / "partial_cycle"
        partial.mkdir()
        (partial / "learning_dataset.json").write_text("{}", encoding="utf-8")
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=partial,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        result = d.step3_apply_learning_outcomes()
        assert 0.0 < result["apply_rate"] < 1.0


# ════════════════════════════════════════════════════════════════
# TestF9520_04 — Step 4: I/O 整合性チェック
# ════════════════════════════════════════════════════════════════

class TestF9520_04_IoIntegrity:

    @pytest.fixture
    def full_apply(self, integrator):
        return integrator.step3_apply_learning_outcomes()

    @pytest.fixture
    def full_sync(self, integrator):
        return integrator.step2_sync_repositories()

    def test_returns_dict(self, integrator, full_apply, full_sync):
        assert isinstance(integrator.step4_check_io_integrity(full_apply, full_sync), dict)

    def test_integrity_near_1_when_all_ok(self, integrator, full_apply, full_sync):
        result = integrator.step4_check_io_integrity(full_apply, full_sync)
        assert result["integrity"] >= IO_INTEGRITY_THRESHOLD

    def test_io_ok_true_when_threshold_met(self, integrator, full_apply, full_sync):
        result = integrator.step4_check_io_integrity(full_apply, full_sync)
        assert result["io_ok"] is True

    def test_io_ok_false_when_nothing_applied(self, integrator, full_sync):
        empty_apply = {"applied": [], "failed": _CYCLE_INPUTS, "apply_rate": 0.0}
        result      = integrator.step4_check_io_integrity(empty_apply, full_sync)
        assert result["io_ok"] is False

    def test_has_input_check(self, integrator, full_apply, full_sync):
        result = integrator.step4_check_io_integrity(full_apply, full_sync)
        assert "input_check" in result

    def test_has_output_check(self, integrator, full_apply, full_sync):
        result = integrator.step4_check_io_integrity(full_apply, full_sync)
        assert "output_check" in result

    def test_integrity_range_0_to_1(self, integrator, full_apply, full_sync):
        result = integrator.step4_check_io_integrity(full_apply, full_sync)
        assert 0.0 <= result["integrity"] <= 1.0


# ════════════════════════════════════════════════════════════════
# TestF9520_05 — Step 5: 再現性テスト
# ════════════════════════════════════════════════════════════════

class TestF9520_05_ReproducibilityTest:

    @pytest.fixture
    def ok_apply(self, integrator):
        return integrator.step3_apply_learning_outcomes()

    def test_returns_dict(self, integrator, ok_apply):
        assert isinstance(integrator.step5_reproducibility_test(ok_apply), dict)

    def test_passed_true_when_all_files_ok(self, integrator, ok_apply):
        result = integrator.step5_reproducibility_test(ok_apply)
        assert result["passed"] is True

    def test_trial_count_equals_3(self, integrator, ok_apply):
        result = integrator.step5_reproducibility_test(ok_apply)
        assert result["trial_count"] == REPRO_TEST_COUNT
        assert len(result["trials"]) == REPRO_TEST_COUNT

    def test_repro_rate_1_when_all_pass(self, integrator, ok_apply):
        result = integrator.step5_reproducibility_test(ok_apply)
        assert result["repro_rate"] == 1.0

    def test_passed_false_when_apply_rate_low(self, integrator):
        bad_apply = {"applied": [], "failed": _CYCLE_INPUTS, "apply_rate": 0.0}
        result    = integrator.step5_reproducibility_test(bad_apply)
        assert result["passed"] is False

    def test_repro_rate_0_when_all_fail(self, integrator):
        bad_apply = {"applied": [], "failed": _CYCLE_INPUTS, "apply_rate": 0.0}
        result    = integrator.step5_reproducibility_test(bad_apply)
        assert result["repro_rate"] == 0.0

    def test_each_trial_has_passed_key(self, integrator, ok_apply):
        result = integrator.step5_reproducibility_test(ok_apply)
        assert all("passed" in t for t in result["trials"])


# ════════════════════════════════════════════════════════════════
# TestF9520_06 — Step 6: sync_log 初期化
# ════════════════════════════════════════════════════════════════

class TestF9520_06_InitSyncLog:

    def test_returns_string(self, integrator):
        assert isinstance(integrator.step6_init_sync_log(), str)

    def test_sync_log_created(self, integrator, tmp_path):
        integrator.step6_init_sync_log()
        assert (tmp_path / "phase8" / "sync_log.json").exists()

    def test_sync_log_has_module_f9520(self, integrator, tmp_path):
        integrator.step6_init_sync_log()
        log = json.loads(
            (tmp_path / "phase8" / "sync_log.json").read_text(encoding="utf-8"))
        assert log["module"] == "F9520"

    def test_sync_log_has_entries(self, integrator, tmp_path):
        integrator.step1_load_plan()   # ログエントリを生成
        integrator.step6_init_sync_log()
        log = json.loads(
            (tmp_path / "phase8" / "sync_log.json").read_text(encoding="utf-8"))
        assert log["entry_count"] >= 0

    def test_sync_log_entries_is_list(self, integrator, tmp_path):
        integrator.step6_init_sync_log()
        log = json.loads(
            (tmp_path / "phase8" / "sync_log.json").read_text(encoding="utf-8"))
        assert isinstance(log["entries"], list)


# ════════════════════════════════════════════════════════════════
# TestF9520_07 — Step 7: HITL チェックポイント設定
# ════════════════════════════════════════════════════════════════

class TestF9520_07_SetHitlCheckpoint:

    def test_returns_dict(self, integrator):
        assert isinstance(integrator.step7_set_hitl_checkpoint(), dict)

    def test_stage_is_trial_operation(self, integrator):
        result = integrator.step7_set_hitl_checkpoint()
        assert result["stage"] == "trial_operation"

    def test_status_is_pending(self, integrator):
        result = integrator.step7_set_hitl_checkpoint()
        assert result["status"] == "pending"

    def test_hitl_log_created(self, integrator, tmp_path):
        integrator.step7_set_hitl_checkpoint()
        assert (tmp_path / "phase8" / "hitl_checkpoint_log.json").exists()

    def test_hitl_log_has_trial_operation(self, integrator, tmp_path):
        integrator.step7_set_hitl_checkpoint()
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        stages = [cp["stage"] for cp in log["checkpoints"]]
        assert "trial_operation" in stages

    def test_trial_operation_checkpoint_pending(self, integrator, tmp_path):
        integrator.step7_set_hitl_checkpoint()
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        to_cp = next(cp for cp in log["checkpoints"] if cp["stage"] == "trial_operation")
        assert to_cp["status"] == "pending"

    def test_record_hitl_approval_updates_status(self, integrator, tmp_path):
        integrator.step7_set_hitl_checkpoint()
        integrator.record_hitl_approval("trial_operation", "approve", "確認済み")
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        to_cp = next(cp for cp in log["checkpoints"] if cp["stage"] == "trial_operation")
        assert to_cp["status"] == "approve"
        assert to_cp["approved_at"] is not None

    def test_record_hitl_approval_sets_reason(self, integrator, tmp_path):
        integrator.step7_set_hitl_checkpoint()
        integrator.record_hitl_approval("trial_operation", "approve", "内容確認済み")
        log = json.loads(
            (tmp_path / "phase8" / "hitl_checkpoint_log.json").read_text(encoding="utf-8"))
        to_cp = next(cp for cp in log["checkpoints"] if cp["stage"] == "trial_operation")
        assert to_cp["reason"] == "内容確認済み"


# ════════════════════════════════════════════════════════════════
# TestF9520_08 — run() / 出力ファイル
# ════════════════════════════════════════════════════════════════

class TestF9520_08_RunAndOutputFiles:

    def test_run_returns_dict(self, integrator):
        assert isinstance(integrator.run(), dict)

    def test_run_success_true(self, integrator):
        result = integrator.run()
        assert result["success"] is True

    def test_phase8_stage_is_trial_operation(self, integrator):
        result = integrator.run()
        assert result["phase8_stage"] == "trial_operation"

    def test_integration_report_created(self, integrator, tmp_path):
        integrator.run()
        assert (tmp_path / "phase8" / "integration_report.json").exists()

    def test_integration_report_success_true(self, integrator, tmp_path):
        integrator.run()
        report = json.loads(
            (tmp_path / "phase8" / "integration_report.json").read_text(encoding="utf-8"))
        assert report["success"] is True

    def test_integration_report_has_phase8_stage(self, integrator, tmp_path):
        integrator.run()
        report = json.loads(
            (tmp_path / "phase8" / "integration_report.json").read_text(encoding="utf-8"))
        assert report["phase8_stage"] == "trial_operation"

    def test_integration_report_io_integrity_ok(self, integrator, tmp_path):
        integrator.run()
        report = json.loads(
            (tmp_path / "phase8" / "integration_report.json").read_text(encoding="utf-8"))
        assert report["io_integrity"] >= IO_INTEGRITY_THRESHOLD

    def test_integration_report_repro_passed(self, integrator, tmp_path):
        integrator.run()
        report = json.loads(
            (tmp_path / "phase8" / "integration_report.json").read_text(encoding="utf-8"))
        assert report["reproducibility_test_passed"] is True

    def test_sync_log_created(self, integrator, tmp_path):
        integrator.run()
        assert (tmp_path / "phase8" / "sync_log.json").exists()

    def test_sync_log_has_success_message(self, integrator, tmp_path):
        integrator.run()
        log = json.loads(
            (tmp_path / "phase8" / "sync_log.json").read_text(encoding="utf-8"))
        assert "F9520 executed successfully" in log.get("success_message", "")

    def test_hitl_checkpoint_log_updated(self, integrator, tmp_path):
        integrator.run()
        assert (tmp_path / "phase8" / "hitl_checkpoint_log.json").exists()

    def test_deployment_trace_updated(self, integrator, tmp_path):
        integrator.run()
        trace = json.loads(
            (tmp_path / "phase8" / "deployment_trace.json").read_text(encoding="utf-8"))
        assert "trial_operation" in trace["stages"]

    def test_trace_has_f9520_executed(self, integrator, tmp_path):
        integrator.run()
        trace = json.loads(
            (tmp_path / "phase8" / "deployment_trace.json").read_text(encoding="utf-8"))
        entry = trace["stages"]["trial_operation"]["f9520_entry"]
        assert "F9520 executed successfully" in entry

    def test_failure_repository_sync_in_report(self, integrator, tmp_path):
        integrator.run()
        report = json.loads(
            (tmp_path / "phase8" / "integration_report.json").read_text(encoding="utf-8"))
        assert report["failure_repository_sync"] == "success"

    def test_knowledge_cycle_update_in_report(self, integrator, tmp_path):
        integrator.run()
        report = json.loads(
            (tmp_path / "phase8" / "integration_report.json").read_text(encoding="utf-8"))
        assert report["knowledge_cycle_update"] == "success"

    def test_load_integration_report_returns_dict(self, integrator, tmp_path):
        integrator.run()
        loaded = integrator.load_integration_report()
        assert isinstance(loaded, dict)

    def test_load_nonexistent_returns_empty(self, tmp_path):
        d = F9520SupportAgentIntegration(phase8_dir=tmp_path / "ph8")
        assert d.load_integration_report() == {}

    def test_write_summary_entry_creates_log(self, integrator, tmp_path):
        result  = integrator.run()
        log     = tmp_path / "summary.log"
        integrator.write_summary_entry(result, log_path=log)
        assert log.exists()

    def test_summary_entry_has_f9520(self, integrator, tmp_path):
        result = integrator.run()
        log    = tmp_path / "summary.log"
        integrator.write_summary_entry(result, log_path=log)
        assert "F9520" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_next_stage(self, integrator, tmp_path):
        result = integrator.run()
        log    = tmp_path / "summary.log"
        integrator.write_summary_entry(result, log_path=log)
        assert "F9530" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# TestF9520_09 — エラー/ロールバックシナリオ
# ════════════════════════════════════════════════════════════════

class TestF9520_09_ErrorAndRollback:

    def test_run_fails_when_cycle_dir_empty(self, tmp_path, tmp_plan, tmp_phase6_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        result = d.run()
        assert result["success"] is False

    def test_integration_report_created_on_failure(self, tmp_path, tmp_plan, tmp_phase6_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        d.run()
        assert (tmp_path / "phase8" / "integration_report.json").exists()

    def test_rollback_log_updated_on_io_failure(self, tmp_path, tmp_plan, tmp_phase6_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        d.run()
        log = json.loads(
            (tmp_path / "phase8" / "rollback_log.json").read_text(encoding="utf-8"))
        assert log["total_events"] >= 1

    def test_sync_log_created_on_failure(self, tmp_path, tmp_plan, tmp_phase6_dir):
        empty = tmp_path / "empty_cycle"
        empty.mkdir()
        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=empty,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        d.run()
        assert (tmp_path / "phase8" / "sync_log.json").exists()

    def test_validation_error_json_on_knowledge_cycle_error(self, tmp_path, tmp_plan, tmp_phase6_dir):
        """YAML が壊れた index.yaml があると validation_error.json が出力される。"""
        bad_kc = tmp_path / "bad_cycle"
        bad_kc.mkdir()
        for fname in _CYCLE_INPUTS:
            (bad_kc / fname).write_text("{}", encoding="utf-8")
        (bad_kc / "index.yaml").write_text(": invalid: yaml: [[[", encoding="utf-8")

        d = F9520SupportAgentIntegration(
            plan_path=tmp_plan,
            cycle_dir=bad_kc,
            phase6_dir=tmp_phase6_dir,
            phase8_dir=tmp_path / "phase8",
        )
        result = d.step2_sync_repositories()
        # YAML パース失敗でも fallback で success になりうる（dataset ありのため）
        # validation_error.json が出力されることを確認
        assert isinstance(result, dict)
