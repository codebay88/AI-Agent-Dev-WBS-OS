"""WP9410 学習データ統合テスト
Phase 7：学習層（Knowledge Learning Layer）

テスト対象:
  - src/knowledge/learning_dataset.py
    - LearningDatasetBuilder.build_from_failure_repository()
    - LearningDatasetBuilder.extract_success_patterns_from_log()
    - LearningDatasetBuilder.build_from_wbs_history()
    - LearningDatasetBuilder.build_from_os_report()
    - LearningDatasetBuilder.compile_dataset()
    - LearningDatasetBuilder.save_dataset()
    - LearningDatasetBuilder.write_summary_entry()
    - LearningDatasetBuilder.load_dataset()
    - LearningDatasetBuilder.get_learning_targets()
  - src/knowledge/knowledge_cycle.py（追加メソッド）
    - KnowledgeCycle.load_learning_dataset()
    - KnowledgeCycle.get_learning_targets()
"""

import json
from pathlib import Path

import pytest

from src.knowledge.learning_dataset import (
    LearningDatasetBuilder,
    CAT_OPERATIONAL,
    CAT_IMPROVEMENT,
    CAT_MAINTENANCE,
    CAT_ENVIRONMENT,
)
from src.knowledge.knowledge_cycle import KnowledgeCycle


# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_failure_repo(tmp_path):
    data = {
        "generated_at": "2026-07-22T00:00:00",
        "failures": [
            {
                "failure_id": "FL-001",
                "module": "F10",
                "category": "hitl",
                "description": "曖昧語 HITL 発動",
                "condition": "AMBIGUOUS_WORDS が含まれる",
                "resolution": "ユーザーが曖昧語を除去して再入力する",
                "source": "WP8230",
            },
            {
                "failure_id": "FL-002",
                "module": "F10",
                "category": "retry_exceeded",
                "description": "API MAX_RETRY 超過",
                "condition": "ネットワーク障害",
                "resolution": "フェイルセーフ発動・エラーを上位に伝播",
                "source": "WP8220",
            },
        ],
        "prevention_patterns": [],
        "clusters": [],
        "phase7_ready": True,
    }
    p = tmp_path / "failure_repository.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def tmp_summary_log(tmp_path):
    content = (
        "[PASS] F10〜F90 因果構造マップ完全一致\n"
        "[PASS] trace_id / source_trace_id チェーン完全性\n"
        "[PASS] テンプレート適用（TMP_HIGH/MED/LOW）正確性\n"
    )
    p = tmp_path / "summary.log"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def tmp_wbs_history(tmp_path):
    content = (
        "[2026-07-22T20:03:28] WBS差分記録\n"
        "  追加フェーズ: ['Phase1-3', 'Phase4']\n"
        "  削除フェーズ: なし\n"
        "  変更フェーズ: なし\n"
        "  変更総件数  : 2\n"
        "  備考: WP9300 初回 WBS 構造生成\n"
        "---\n"
    )
    p = tmp_path / "wbs_history.log"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def tmp_os_report(tmp_path):
    data = {
        "generated_at": "2026-07-22T20:03:29",
        "environment": {
            "python_version": "3.11.9",
            "platform": "Windows",
            "architecture": "AMD64",
        },
        "packages": [
            {"name": "pytest", "installed": "9.1.1", "required_min": "7.0.0",
             "status": "ok", "update_type": "optional"},
        ],
        "safety_score": 100,
        "hitl_required": False,
        "summary": "全パッケージ正常",
        "phase6_5_ready": True,
    }
    p = tmp_path / "os_update_report.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def builder(tmp_path, tmp_failure_repo, tmp_summary_log, tmp_wbs_history, tmp_os_report):
    return LearningDatasetBuilder(
        failure_repo_path=tmp_failure_repo,
        summary_log_path=tmp_summary_log,
        wbs_history_path=tmp_wbs_history,
        os_report_path=tmp_os_report,
        dataset_path=tmp_path / "learning_dataset.json",
    )


# ════════════════════════════════════════════════════════════════
# TestLD01 — failure_repository → 因果分解エントリ
# ════════════════════════════════════════════════════════════════

class TestLD01_FailureRepositoryIngestion:

    def test_returns_list(self, builder):
        result = builder.build_from_failure_repository()
        assert isinstance(result, list)

    def test_entry_count_matches_failures(self, builder):
        result = builder.build_from_failure_repository()
        assert len(result) == 2

    def test_entries_have_entry_id(self, builder):
        for entry in builder.build_from_failure_repository():
            assert "entry_id" in entry and entry["entry_id"].startswith("LE-IMP")

    def test_entries_have_cause(self, builder):
        for entry in builder.build_from_failure_repository():
            assert "cause" in entry and entry["cause"]

    def test_entries_have_action(self, builder):
        for entry in builder.build_from_failure_repository():
            assert "action" in entry and entry["action"]

    def test_entries_have_result(self, builder):
        for entry in builder.build_from_failure_repository():
            assert "result" in entry and entry["result"]

    def test_category_is_improvement(self, builder):
        for entry in builder.build_from_failure_repository():
            assert entry["category"] == CAT_IMPROVEMENT

    def test_hitl_category_result_is_classified(self, builder):
        entries = builder.build_from_failure_repository()
        hitl_entries = [e for e in entries if e.get("failure_category") == "hitl"]
        assert hitl_entries
        # FL-001: resolution は「再入力」→ フィードバック系結果
        assert hitl_entries[0]["result"]

    def test_missing_file_returns_empty(self, tmp_path):
        b = LearningDatasetBuilder(failure_repo_path=tmp_path / "nonexistent.json")
        assert b.build_from_failure_repository() == []

    def test_reproducibility_is_high(self, builder):
        for entry in builder.build_from_failure_repository():
            assert entry["reproducibility"] == "high"


# ════════════════════════════════════════════════════════════════
# TestLD02 — summary.log → 成功パターン
# ════════════════════════════════════════════════════════════════

class TestLD02_SuccessPatternExtraction:

    def test_returns_list(self, builder):
        result = builder.extract_success_patterns_from_log()
        assert isinstance(result, list)

    def test_count_matches_pass_lines(self, builder):
        result = builder.extract_success_patterns_from_log()
        assert len(result) == 3

    def test_entries_have_operational_category(self, builder):
        for entry in builder.extract_success_patterns_from_log():
            assert entry["category"] == CAT_OPERATIONAL

    def test_pattern_type_is_success(self, builder):
        for entry in builder.extract_success_patterns_from_log():
            assert entry["pattern_type"] == "success"

    def test_action_contains_pass_description(self, builder):
        entries = builder.extract_success_patterns_from_log()
        assert any("因果構造" in e["action"] for e in entries)

    def test_missing_log_returns_empty(self, tmp_path):
        b = LearningDatasetBuilder(summary_log_path=tmp_path / "no.log")
        assert b.extract_success_patterns_from_log() == []

    def test_entry_ids_have_opr_prefix(self, builder):
        for entry in builder.extract_success_patterns_from_log():
            assert entry["entry_id"].startswith("LE-OPR")

    def test_source_is_summary_log(self, builder):
        for entry in builder.extract_success_patterns_from_log():
            assert entry["source"] == "summary.log"


# ════════════════════════════════════════════════════════════════
# TestLD03 — wbs_history.log → 構造変化パターン
# ════════════════════════════════════════════════════════════════

class TestLD03_WbsHistoryIngestion:

    def test_returns_list(self, builder):
        result = builder.build_from_wbs_history()
        assert isinstance(result, list)

    def test_entry_count_matches_blocks(self, builder):
        result = builder.build_from_wbs_history()
        assert len(result) == 1

    def test_category_is_maintenance(self, builder):
        for entry in builder.build_from_wbs_history():
            assert entry["category"] == CAT_MAINTENANCE

    def test_entry_has_total_changes(self, builder):
        entry = builder.build_from_wbs_history()[0]
        assert entry["total_changes"] == 2

    def test_change_type_is_addition(self, builder):
        entry = builder.build_from_wbs_history()[0]
        assert entry["change_type"] == "addition"

    def test_missing_file_returns_empty(self, tmp_path):
        b = LearningDatasetBuilder(wbs_history_path=tmp_path / "no.log")
        assert b.build_from_wbs_history() == []

    def test_entry_ids_have_mnt_prefix(self, builder):
        for entry in builder.build_from_wbs_history():
            assert entry["entry_id"].startswith("LE-MNT")


# ════════════════════════════════════════════════════════════════
# TestLD04 — os_update_report.json → 環境変化パターン
# ════════════════════════════════════════════════════════════════

class TestLD04_OsReportIngestion:

    def test_returns_list(self, builder):
        result = builder.build_from_os_report()
        assert isinstance(result, list)

    def test_entry_count_is_packages_plus_assessment(self, builder):
        result = builder.build_from_os_report()
        assert len(result) == 2  # 1 pkg + 1 assessment

    def test_category_is_environment(self, builder):
        for entry in builder.build_from_os_report():
            assert entry["category"] == CAT_ENVIRONMENT

    def test_last_entry_is_assessment(self, builder):
        entries = builder.build_from_os_report()
        assert entries[-1]["pattern_type"] == "environment_assessment"

    def test_entry_ids_have_env_prefix(self, builder):
        for entry in builder.build_from_os_report():
            assert entry["entry_id"].startswith("LE-ENV")

    def test_missing_file_returns_empty(self, tmp_path):
        b = LearningDatasetBuilder(os_report_path=tmp_path / "no.json")
        assert b.build_from_os_report() == []

    def test_assessment_entry_mentions_score(self, builder):
        entries = builder.build_from_os_report()
        assessment = [e for e in entries if e["pattern_type"] == "environment_assessment"]
        assert assessment and "100" in assessment[0]["action"]


# ════════════════════════════════════════════════════════════════
# TestLD05 — compile_dataset（統合）
# ════════════════════════════════════════════════════════════════

class TestLD05_CompileDataset:

    @pytest.fixture
    def all_entries(self, builder):
        entries = []
        entries += builder.build_from_failure_repository()
        entries += builder.extract_success_patterns_from_log()
        entries += builder.build_from_wbs_history()
        entries += builder.build_from_os_report()
        return entries

    def test_compile_returns_dict(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert isinstance(ds, dict)

    def test_total_entries_correct(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert ds["total_entries"] == len(all_entries)

    def test_phase_is_7(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert ds["phase"] == 7

    def test_category_counts_present(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        cc = ds["category_counts"]
        assert CAT_OPERATIONAL in cc
        assert CAT_IMPROVEMENT in cc
        assert CAT_MAINTENANCE in cc
        assert CAT_ENVIRONMENT in cc

    def test_success_patterns_extracted(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert len(ds["success_patterns"]) == 3

    def test_failure_patterns_extracted(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert len(ds["failure_patterns"]) == 2

    def test_learning_entries_all_present(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert len(ds["learning_entries"]) == len(all_entries)

    def test_phase8_ready_is_false(self, builder, all_entries):
        ds = builder.compile_dataset(all_entries)
        assert ds["phase8_ready"] is False


# ════════════════════════════════════════════════════════════════
# TestLD06 — save / load
# ════════════════════════════════════════════════════════════════

class TestLD06_SaveLoad:

    @pytest.fixture
    def dataset(self, builder):
        entries = (
            builder.build_from_failure_repository()
            + builder.extract_success_patterns_from_log()
            + builder.build_from_wbs_history()
            + builder.build_from_os_report()
        )
        return builder.compile_dataset(entries)

    def test_save_creates_file(self, builder, dataset, tmp_path):
        p = tmp_path / "ds.json"
        builder.save_dataset(dataset, path=p)
        assert p.exists()

    def test_saved_file_is_valid_json(self, builder, dataset, tmp_path):
        p = tmp_path / "ds.json"
        builder.save_dataset(dataset, path=p)
        with open(p, encoding="utf-8") as f:
            loaded = json.load(f)
        assert isinstance(loaded, dict)

    def test_load_dataset_returns_dict(self, builder, dataset, tmp_path):
        p = tmp_path / "ds.json"
        builder.save_dataset(dataset, path=p)
        loaded = builder.load_dataset(path=p)
        assert isinstance(loaded, dict)

    def test_load_nonexistent_returns_empty(self, tmp_path):
        b = LearningDatasetBuilder(dataset_path=tmp_path / "no.json")
        assert b.load_dataset() == {}

    def test_get_learning_targets_returns_list(self, builder, dataset, tmp_path):
        p = tmp_path / "ds.json"
        builder.save_dataset(dataset, path=p)
        targets = builder.get_learning_targets(dataset=dataset)
        assert isinstance(targets, list)

    def test_get_learning_targets_by_category(self, builder, dataset):
        targets = builder.get_learning_targets(category=CAT_OPERATIONAL, dataset=dataset)
        assert all(e["category"] == CAT_OPERATIONAL for e in targets)

    def test_get_learning_targets_all_entries(self, builder, dataset):
        targets = builder.get_learning_targets(dataset=dataset)
        assert len(targets) == dataset["total_entries"]

    def test_write_summary_entry_creates_log(self, builder, dataset, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(dataset, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_wp9410(self, builder, dataset, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(dataset, log_path=log)
        assert "WP9410" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_total_entries(self, builder, dataset, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(dataset, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "学習エントリ総数" in content

    def test_write_summary_entry_has_phase7_flag(self, builder, dataset, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(dataset, log_path=log)
        assert "Phase 7" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# TestLD07 — KnowledgeCycle 連携 I/O
# ════════════════════════════════════════════════════════════════

class TestLD07_KnowledgeCycleIntegration:

    @pytest.fixture
    def kc_with_dataset(self, tmp_path):
        builder = LearningDatasetBuilder(
            failure_repo_path=tmp_path / "failure_repository.json",
            summary_log_path=tmp_path / "summary.log",
            wbs_history_path=tmp_path / "wbs_history.log",
            os_report_path=tmp_path / "os_update_report.json",
            dataset_path=tmp_path / "knowledge_cycle" / "learning_dataset.json",
        )
        # failure_repository を最小限だけ用意
        (tmp_path / "failure_repository.json").write_text(
            json.dumps({
                "failures": [
                    {"failure_id": "FL-001", "module": "F10", "category": "hitl",
                     "description": "test", "condition": "x", "resolution": "HITL 移譲", "source": "WP"},
                ],
                "prevention_patterns": [], "clusters": [], "phase7_ready": True,
            }),
            encoding="utf-8",
        )
        entries = builder.build_from_failure_repository()
        ds      = builder.compile_dataset(entries)
        builder.save_dataset(ds)

        kc = KnowledgeCycle(
            cycle_dir=tmp_path / "knowledge_cycle",
            summary_log=tmp_path / "summary.log",
        )
        return kc, tmp_path / "knowledge_cycle" / "learning_dataset.json"

    def test_load_learning_dataset_returns_dict(self, kc_with_dataset):
        kc, path = kc_with_dataset
        ds = kc.load_learning_dataset(path=path)
        assert isinstance(ds, dict)

    def test_load_learning_dataset_has_entries(self, kc_with_dataset):
        kc, path = kc_with_dataset
        ds = kc.load_learning_dataset(path=path)
        assert "learning_entries" in ds

    def test_load_learning_dataset_missing_returns_empty(self, tmp_path):
        kc = KnowledgeCycle(cycle_dir=tmp_path / "kc")
        assert kc.load_learning_dataset() == {}

    def test_get_learning_targets_returns_list(self, kc_with_dataset):
        kc, path = kc_with_dataset
        targets = kc.get_learning_targets(path=path)
        assert isinstance(targets, list)

    def test_get_learning_targets_by_category(self, kc_with_dataset):
        kc, path = kc_with_dataset
        targets = kc.get_learning_targets(category=CAT_IMPROVEMENT, path=path)
        assert all(e["category"] == CAT_IMPROVEMENT for e in targets)

    def test_get_learning_targets_empty_when_no_file(self, tmp_path):
        kc = KnowledgeCycle(cycle_dir=tmp_path / "kc")
        assert kc.get_learning_targets() == []
