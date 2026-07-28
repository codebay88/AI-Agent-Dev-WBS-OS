"""WP9420 学習パターン生成テスト
Phase 7：学習層（Knowledge Learning Layer）

テスト対象:
  - src/knowledge/learning_pattern.py
    - LearningPatternBuilder.load_dataset()
    - LearningPatternBuilder.load_failure_repository()
    - LearningPatternBuilder.build_learning_patterns()
    - LearningPatternBuilder.validate_mece_structure()
    - LearningPatternBuilder.export_patterns()
    - LearningPatternBuilder.save_patterns()
    - LearningPatternBuilder.load_patterns()
    - LearningPatternBuilder.write_summary_entry()
  - src/knowledge/knowledge_cycle.py
    - KnowledgeCycle.get_learning_patterns()
"""

import json
from pathlib import Path

import pytest

from src.knowledge.learning_pattern import LearningPatternBuilder
from src.knowledge.knowledge_cycle import KnowledgeCycle


# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dataset(tmp_path):
    data = {
        "generated_at": "2026-07-22T00:00:00",
        "total_entries": 5,
        "categories": {
            "operational": [
                {"entry_id": "LE-OPR-001", "category": "operational", "source": "summary.log",
                 "cause": "定常運用条件", "action": "F10〜F90 因果構造確認",
                 "result": "PASS", "pattern_type": "success", "reproducibility": "high"},
                {"entry_id": "LE-OPR-002", "category": "operational", "source": "summary.log",
                 "cause": "定常運用条件", "action": "trace_id チェーン確認",
                 "result": "PASS", "pattern_type": "success", "reproducibility": "high"},
            ],
            "improvement": [
                {"entry_id": "LE-IMP-001", "category": "improvement", "source": "FL-001",
                 "module": "F10", "failure_category": "hitl",
                 "description": "曖昧語 HITL 発動",
                 "cause": "AMBIGUOUS_WORDS が含まれる", "action": "ユーザーが再入力",
                 "result": "ユーザーへフィードバック", "pattern_type": "failure_resolved",
                 "reproducibility": "high"},
                {"entry_id": "LE-IMP-002", "category": "improvement", "source": "FL-002",
                 "module": "F10", "failure_category": "retry_exceeded",
                 "description": "API MAX_RETRY 超過",
                 "cause": "ネットワーク障害", "action": "フェイルセーフ発動",
                 "result": "パイプライン即時停止", "pattern_type": "failure_stopped",
                 "reproducibility": "high"},
            ],
            "maintenance": [
                {"entry_id": "LE-MNT-001", "category": "maintenance", "source": "wbs_history.log",
                 "cause": "WBS 更新要求", "action": "追加=Phase7 / 削除=なし",
                 "result": "変更総件数=1件", "change_type": "addition",
                 "total_changes": 1, "pattern_type": "maintenance", "reproducibility": "medium"},
            ],
            "environment": [
                {"entry_id": "LE-ENV-001", "category": "environment", "source": "os_update_report.json",
                 "cause": "パッケージ確認: pytest installed=9.1.1", "action": "update_type=optional",
                 "result": "status=ok", "pattern_type": "environment_check", "reproducibility": "medium"},
            ],
        },
    }
    p = tmp_path / "learning_dataset.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def tmp_failure_repo(tmp_path):
    data = {
        "failures": [
            {"failure_id": "FL-001", "module": "F10", "category": "hitl",
             "description": "曖昧語 HITL", "condition": "AMBIGUOUS_WORDS",
             "resolution": "ユーザーが曖昧語を除去して再入力する", "source": "WP8230"},
            {"failure_id": "FL-002", "module": "F10", "category": "retry_exceeded",
             "description": "MAX_RETRY 超過", "condition": "ネットワーク障害",
             "resolution": "フェイルセーフ発動・エラーを上位に伝播", "source": "WP8220"},
        ],
        "prevention_patterns": [], "clusters": [], "phase7_ready": True,
    }
    p = tmp_path / "failure_repository.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def builder(tmp_path, tmp_dataset, tmp_failure_repo):
    return LearningPatternBuilder(
        dataset_path=tmp_dataset,
        failure_repo=tmp_failure_repo,
        patterns_path=tmp_path / "learning_patterns.json",
        summary_log=tmp_path / "summary.log",
    )


@pytest.fixture
def patterns(builder):
    ds = builder.load_dataset()
    return builder.build_learning_patterns(ds)


# ════════════════════════════════════════════════════════════════
# TestLP01 — データ読み込み
# ════════════════════════════════════════════════════════════════

class TestLP01_DataLoading:

    def test_load_dataset_returns_dict(self, builder):
        assert isinstance(builder.load_dataset(), dict)

    def test_load_dataset_has_categories(self, builder):
        ds = builder.load_dataset()
        assert "categories" in ds

    def test_load_failure_repo_returns_dict(self, builder):
        assert isinstance(builder.load_failure_repository(), dict)

    def test_load_failure_repo_has_failures(self, builder):
        assert "failures" in builder.load_failure_repository()

    def test_load_dataset_missing_returns_empty(self, tmp_path):
        b = LearningPatternBuilder(dataset_path=tmp_path / "no.json")
        assert b.load_dataset() == {}

    def test_load_failure_repo_missing_returns_empty(self, tmp_path):
        b = LearningPatternBuilder(failure_repo=tmp_path / "no.json")
        assert b.load_failure_repository() == {}


# ════════════════════════════════════════════════════════════════
# TestLP02 — 学習パターン生成
# ════════════════════════════════════════════════════════════════

class TestLP02_BuildLearningPatterns:

    def test_returns_list(self, builder):
        ds = builder.load_dataset()
        assert isinstance(builder.build_learning_patterns(ds), list)

    def test_pattern_count_matches_entries(self, builder, patterns):
        # fixture: operational=2, improvement=2, maintenance=1, environment=1 → 6
        assert len(patterns) == 6

    def test_patterns_have_pattern_id(self, patterns):
        for p in patterns:
            assert "pattern_id" in p and p["pattern_id"]

    def test_patterns_have_cause(self, patterns):
        for p in patterns:
            assert "cause" in p and p["cause"]

    def test_patterns_have_action(self, patterns):
        for p in patterns:
            assert "action" in p and p["action"]

    def test_patterns_have_result(self, patterns):
        for p in patterns:
            assert "result" in p and p["result"]

    def test_patterns_have_score(self, patterns):
        for p in patterns:
            assert "score" in p
            assert 0.0 <= p["score"] <= 1.0

    def test_operational_patterns_have_op_prefix(self, patterns):
        op = [p for p in patterns if p["category"] == "operational"]
        assert all(p["pattern_id"].startswith("OP-") for p in op)

    def test_improvement_patterns_have_im_prefix(self, patterns):
        im = [p for p in patterns if p["category"] == "improvement"]
        assert all(p["pattern_id"].startswith("IM-") for p in im)

    def test_maintenance_patterns_have_mn_prefix(self, patterns):
        mn = [p for p in patterns if p["category"] == "maintenance"]
        assert all(p["pattern_id"].startswith("MN-") for p in mn)

    def test_environment_patterns_have_en_prefix(self, patterns):
        en = [p for p in patterns if p["category"] == "environment"]
        assert all(p["pattern_id"].startswith("EN-") for p in en)

    def test_improvement_patterns_have_module(self, patterns):
        im = [p for p in patterns if p["category"] == "improvement"]
        for p in im:
            assert "module" in p

    def test_high_reproducibility_score_gte_090(self, patterns):
        high_repro = [p for p in patterns if p["reproducibility"] == "high"]
        assert all(p["score"] >= 0.90 for p in high_repro)

    def test_duplicate_cause_action_deduplicated(self, builder):
        ds = {
            "categories": {
                "operational": [
                    {"entry_id": "LE-OPR-001", "category": "operational", "source": "s",
                     "cause": "同一原因", "action": "同一対策",
                     "result": "PASS", "pattern_type": "success", "reproducibility": "high"},
                    {"entry_id": "LE-OPR-002", "category": "operational", "source": "s",
                     "cause": "同一原因", "action": "同一対策",
                     "result": "PASS", "pattern_type": "success", "reproducibility": "high"},
                ],
                "improvement": [], "maintenance": [], "environment": [],
            }
        }
        result = builder.build_learning_patterns(ds)
        assert len(result) == 1

    def test_failure_resolved_has_positive_score(self, patterns):
        resolved = [p for p in patterns if p["pattern_type"] == "failure_resolved"]
        assert all(p["score"] > 0.0 for p in resolved)


# ════════════════════════════════════════════════════════════════
# TestLP03 — MECE 検証
# ════════════════════════════════════════════════════════════════

class TestLP03_MeceValidation:

    def test_returns_dict(self, builder, patterns):
        assert isinstance(builder.validate_mece_structure(patterns), dict)

    def test_checked_count_correct(self, builder, patterns):
        log = builder.validate_mece_structure(patterns)
        assert log["checked_count"] == len(patterns)

    def test_is_mece_true_for_no_issues(self, builder, patterns):
        log = builder.validate_mece_structure(patterns)
        assert log["is_mece"] is True

    def test_duplicate_count_zero(self, builder, patterns):
        log = builder.validate_mece_structure(patterns)
        assert log["duplicate_count"] == 0

    def test_category_coverage_has_four_categories(self, builder, patterns):
        log = builder.validate_mece_structure(patterns)
        assert len(log["category_coverage"]) == 4

    def test_category_counts_present(self, builder, patterns):
        log = builder.validate_mece_structure(patterns)
        assert "category_counts" in log

    def test_missing_categories_empty_when_ok(self, builder, patterns):
        log = builder.validate_mece_structure(patterns)
        assert log["missing_categories"] == []

    def test_duplicate_detected_when_present(self, builder):
        dup_patterns = [
            {"pattern_id": "OP-001", "category": "operational",
             "cause": "同一原因", "action": "同一対策", "result": "r",
             "score": 1.0, "reproducibility": "high", "pattern_type": "success"},
            {"pattern_id": "OP-002", "category": "operational",
             "cause": "同一原因", "action": "同一対策", "result": "r",
             "score": 1.0, "reproducibility": "high", "pattern_type": "success"},
        ]
        log = builder.validate_mece_structure(dup_patterns)
        assert log["duplicate_count"] == 1
        assert log["is_mece"] is False

    def test_missing_category_detected(self, builder):
        partial = [
            {"pattern_id": "OP-001", "category": "operational",
             "cause": "c", "action": "a", "result": "r",
             "score": 1.0, "reproducibility": "high", "pattern_type": "success"},
        ]
        log = builder.validate_mece_structure(partial)
        assert "improvement" in log["missing_categories"]
        assert log["is_mece"] is False


# ════════════════════════════════════════════════════════════════
# TestLP04 — エクスポート統合
# ════════════════════════════════════════════════════════════════

class TestLP04_ExportPatterns:

    @pytest.fixture
    def exported(self, builder, patterns):
        mece = builder.validate_mece_structure(patterns)
        return builder.export_patterns(patterns, mece)

    def test_returns_dict(self, exported):
        assert isinstance(exported, dict)

    def test_total_patterns_correct(self, exported, patterns):
        assert exported["total_patterns"] == len(patterns)

    def test_phase_is_7(self, exported):
        assert exported["phase"] == 7

    def test_average_score_between_0_and_1(self, exported):
        assert 0.0 <= exported["average_score"] <= 1.0

    def test_score_distribution_present(self, exported):
        sd = exported["score_distribution"]
        assert "high_confidence" in sd
        assert "medium_confidence" in sd
        assert "low_confidence" in sd

    def test_score_distribution_sums_to_total(self, exported):
        sd = exported["score_distribution"]
        total = sd["high_confidence"] + sd["medium_confidence"] + sd["low_confidence"]
        assert total == exported["total_patterns"]

    def test_by_category_has_all_categories(self, exported):
        assert "operational" in exported["by_category"]
        assert "improvement" in exported["by_category"]

    def test_mece_log_present(self, exported):
        assert "mece_log" in exported and exported["mece_log"]

    def test_phase8_ready_is_false(self, exported):
        assert exported["phase8_ready"] is False

    def test_patterns_list_matches(self, exported, patterns):
        assert len(exported["patterns"]) == len(patterns)


# ════════════════════════════════════════════════════════════════
# TestLP05 — 保存 / 読み込み
# ════════════════════════════════════════════════════════════════

class TestLP05_SaveLoad:

    @pytest.fixture
    def result(self, builder, patterns):
        mece = builder.validate_mece_structure(patterns)
        return builder.export_patterns(patterns, mece)

    def test_save_creates_file(self, builder, result, tmp_path):
        p = tmp_path / "lp.json"
        builder.save_patterns(result, path=p)
        assert p.exists()

    def test_saved_is_valid_json(self, builder, result, tmp_path):
        p = tmp_path / "lp.json"
        builder.save_patterns(result, path=p)
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)

    def test_load_patterns_returns_dict(self, builder, result, tmp_path):
        p = tmp_path / "lp.json"
        builder.save_patterns(result, path=p)
        loaded = builder.load_patterns(path=p)
        assert isinstance(loaded, dict)

    def test_load_nonexistent_returns_empty(self, tmp_path):
        b = LearningPatternBuilder(patterns_path=tmp_path / "no.json")
        assert b.load_patterns() == {}

    def test_write_summary_entry_creates_log(self, builder, result, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(result, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_wp9420(self, builder, result, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(result, log_path=log)
        assert "WP9420" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_mece(self, builder, result, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(result, log_path=log)
        assert "MECE" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_phase7_flag(self, builder, result, tmp_path):
        log = tmp_path / "summary.log"
        builder.write_summary_entry(result, log_path=log)
        assert "Phase 7" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# TestLP06 — KnowledgeCycle 連携
# ════════════════════════════════════════════════════════════════

class TestLP06_KnowledgeCycleIntegration:

    @pytest.fixture
    def kc_with_patterns(self, tmp_path, tmp_dataset, tmp_failure_repo):
        b = LearningPatternBuilder(
            dataset_path=tmp_dataset,
            failure_repo=tmp_failure_repo,
            patterns_path=tmp_path / "knowledge_cycle" / "learning_patterns.json",
            summary_log=tmp_path / "summary.log",
        )
        ds       = b.load_dataset()
        patterns = b.build_learning_patterns(ds)
        mece     = b.validate_mece_structure(patterns)
        result   = b.export_patterns(patterns, mece)
        b.save_patterns(result)

        kc = KnowledgeCycle(
            cycle_dir=tmp_path / "knowledge_cycle",
            summary_log=tmp_path / "summary.log",
        )
        patterns_path = tmp_path / "knowledge_cycle" / "learning_patterns.json"
        return kc, patterns_path

    def test_get_learning_patterns_returns_list(self, kc_with_patterns):
        kc, path = kc_with_patterns
        result = kc.get_learning_patterns(path=path)
        assert isinstance(result, list)

    def test_get_learning_patterns_has_patterns(self, kc_with_patterns):
        kc, path = kc_with_patterns
        result = kc.get_learning_patterns(path=path)
        assert len(result) > 0

    def test_get_learning_patterns_by_category(self, kc_with_patterns):
        kc, path = kc_with_patterns
        result = kc.get_learning_patterns(category="operational", path=path)
        assert all(p["category"] == "operational" for p in result)

    def test_get_learning_patterns_improvement_category(self, kc_with_patterns):
        kc, path = kc_with_patterns
        result = kc.get_learning_patterns(category="improvement", path=path)
        assert len(result) > 0

    def test_get_learning_patterns_missing_file_returns_empty(self, tmp_path):
        kc = KnowledgeCycle(cycle_dir=tmp_path / "kc")
        assert kc.get_learning_patterns() == []

    def test_get_learning_patterns_unknown_category_returns_empty(self, kc_with_patterns):
        kc, path = kc_with_patterns
        result = kc.get_learning_patterns(category="unknown_cat", path=path)
        assert result == []
