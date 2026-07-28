"""WP9430 自己最適化評価テスト
Phase 7：学習層（Knowledge Learning Layer）

テスト対象:
  - src/knowledge/optimization_evaluator.py
    - OptimizationEvaluator.load_patterns()
    - OptimizationEvaluator.load_dataset()
    - OptimizationEvaluator.evaluate_reproducibility()
    - OptimizationEvaluator.evaluate_impact()
    - OptimizationEvaluator.calculate_optimization_index()
    - OptimizationEvaluator.export_report()
    - OptimizationEvaluator.save_report()
    - OptimizationEvaluator.load_report()
    - OptimizationEvaluator.write_summary_entry()
  - src/knowledge/knowledge_cycle.py
    - KnowledgeCycle.get_optimization_report()
"""

import json
from pathlib import Path

import pytest

from src.knowledge.optimization_evaluator import OptimizationEvaluator
from src.knowledge.knowledge_cycle import KnowledgeCycle


# ────────────────────────────────────────────────────────────────
# 共通フィクスチャ
# ────────────────────────────────────────────────────────────────

_SAMPLE_PATTERNS = [
    {"pattern_id": "OP-001", "category": "operational",  "source": "summary.log",
     "cause": "定常運用", "action": "因果構造確認", "result": "PASS（再現性確認済み）",
     "score": 1.0, "reproducibility": "high", "pattern_type": "success"},
    {"pattern_id": "OP-002", "category": "operational",  "source": "summary.log",
     "cause": "定常運用", "action": "trace_id チェーン確認", "result": "PASS（再現性確認済み）",
     "score": 1.0, "reproducibility": "high", "pattern_type": "success"},
    {"pattern_id": "IM-001", "category": "improvement",  "source": "FL-001",
     "cause": "AMBIGUOUS_WORDS", "action": "ユーザー再入力",
     "result": "ユーザーへフィードバック → 入力修正後に再実行",
     "score": 1.03, "reproducibility": "high", "pattern_type": "failure_resolved",
     "module": "F10", "failure_category": "hitl", "description": "曖昧語 HITL"},
    {"pattern_id": "MN-001", "category": "maintenance",  "source": "wbs_history.log",
     "cause": "WBS 更新要求", "action": "追加=Phase7", "result": "変更総件数=1件",
     "score": 0.7, "reproducibility": "medium", "pattern_type": "maintenance"},
    {"pattern_id": "EN-001", "category": "environment",  "source": "os_update_report.json",
     "cause": "パッケージ確認", "action": "update_type=optional", "result": "status=ok",
     "score": 0.7, "reproducibility": "medium", "pattern_type": "environment_check"},
    {"pattern_id": "EN-002", "category": "environment",  "source": "os_update_report.json",
     "cause": "OS環境確認", "action": "安全性スコア算出: 100/100",
     "result": "hitl_required=False",
     "score": 0.75, "reproducibility": "high", "pattern_type": "environment_assessment"},
]


@pytest.fixture
def tmp_patterns_file(tmp_path):
    data = {
        "generated_at": "2026-07-22T00:00:00",
        "total_patterns": len(_SAMPLE_PATTERNS),
        "patterns": _SAMPLE_PATTERNS,
        "by_category": {},
        "mece_log": {"is_mece": True},
        "phase8_ready": False,
    }
    p = tmp_path / "learning_patterns.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def evaluator(tmp_path, tmp_patterns_file):
    return OptimizationEvaluator(
        patterns_path=tmp_patterns_file,
        dataset_path=tmp_path / "learning_dataset.json",
        report_path=tmp_path / "optimization_report.json",
        summary_log=tmp_path / "summary.log",
    )


@pytest.fixture
def evaluated(evaluator):
    patterns = evaluator.load_patterns()
    patterns = evaluator.evaluate_reproducibility(patterns)
    patterns = evaluator.evaluate_impact(patterns)
    return evaluator.calculate_optimization_index(patterns)


# ════════════════════════════════════════════════════════════════
# TestOE01 — データ読み込み
# ════════════════════════════════════════════════════════════════

class TestOE01_DataLoading:

    def test_load_patterns_returns_list(self, evaluator):
        assert isinstance(evaluator.load_patterns(), list)

    def test_load_patterns_count_correct(self, evaluator):
        patterns = evaluator.load_patterns()
        assert len(patterns) == len(_SAMPLE_PATTERNS)

    def test_load_patterns_missing_returns_empty(self, tmp_path):
        e = OptimizationEvaluator(patterns_path=tmp_path / "no.json")
        assert e.load_patterns() == []

    def test_load_dataset_missing_returns_empty(self, tmp_path):
        e = OptimizationEvaluator(dataset_path=tmp_path / "no.json")
        assert e.load_dataset() == {}

    def test_load_patterns_has_pattern_id(self, evaluator):
        patterns = evaluator.load_patterns()
        for p in patterns:
            assert "pattern_id" in p


# ════════════════════════════════════════════════════════════════
# TestOE02 — 再現性スコア評価
# ════════════════════════════════════════════════════════════════

class TestOE02_EvaluateReproducibility:

    def test_returns_list(self, evaluator):
        patterns = evaluator.load_patterns()
        assert isinstance(evaluator.evaluate_reproducibility(patterns), list)

    def test_adds_reproducibility_score_field(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_reproducibility(patterns)
        for p in result:
            assert "reproducibility_score" in p

    def test_score_is_float_between_0_and_1(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_reproducibility(patterns)
        for p in result:
            assert 0.0 <= p["reproducibility_score"] <= 1.0

    def test_high_repro_has_higher_score_than_medium(self, evaluator):
        high_p   = {"pattern_id": "X", "category": "operational", "cause": "c",
                    "action": "a", "result": "r", "score": 1.0,
                    "reproducibility": "high", "pattern_type": "success"}
        medium_p = dict(high_p) | {"reproducibility": "medium", "score": 0.7}
        h_list   = evaluator.evaluate_reproducibility([high_p])
        m_list   = evaluator.evaluate_reproducibility([medium_p])
        assert h_list[0]["reproducibility_score"] > m_list[0]["reproducibility_score"]

    def test_success_pattern_type_has_top_coeff(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_reproducibility(patterns)
        success  = [p for p in result if p.get("pattern_type") == "success"]
        assert all(p["reproducibility_score"] >= 0.85 for p in success)

    def test_original_fields_preserved(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_reproducibility(patterns)
        for orig, evaled in zip(patterns, result):
            assert evaled["pattern_id"] == orig["pattern_id"]
            assert evaled["category"]   == orig["category"]


# ════════════════════════════════════════════════════════════════
# TestOE03 — 改善効果スコア評価
# ════════════════════════════════════════════════════════════════

class TestOE03_EvaluateImpact:

    def test_returns_list(self, evaluator):
        patterns = evaluator.load_patterns()
        assert isinstance(evaluator.evaluate_impact(patterns), list)

    def test_adds_impact_score_field(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_impact(patterns)
        for p in result:
            assert "impact_score" in p

    def test_impact_score_between_0_and_1(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_impact(patterns)
        for p in result:
            assert 0.0 <= p["impact_score"] <= 1.0

    def test_pass_result_gets_bonus(self, evaluator):
        pass_p = {"pattern_id": "X", "category": "operational",
                  "cause": "c", "action": "a", "result": "PASS（再現性確認済み）",
                  "score": 1.0, "reproducibility": "high", "pattern_type": "success"}
        nope_p = dict(pass_p) | {"result": "通常状態"}
        p_list = evaluator.evaluate_impact([pass_p])
        n_list = evaluator.evaluate_impact([nope_p])
        assert p_list[0]["impact_score"] >= n_list[0]["impact_score"]

    def test_improvement_category_has_highest_weight(self, evaluator):
        imp_p = {"pattern_id": "X", "category": "improvement",
                 "cause": "c", "action": "a", "result": "r",
                 "score": 1.0, "reproducibility": "high", "pattern_type": "failure_resolved"}
        env_p = dict(imp_p) | {"category": "environment", "pattern_type": "environment_check"}
        i_list = evaluator.evaluate_impact([imp_p])
        e_list = evaluator.evaluate_impact([env_p])
        assert i_list[0]["impact_score"] >= e_list[0]["impact_score"]

    def test_original_pattern_id_preserved(self, evaluator):
        patterns = evaluator.load_patterns()
        result   = evaluator.evaluate_impact(patterns)
        for orig, evaled in zip(patterns, result):
            assert evaled["pattern_id"] == orig["pattern_id"]


# ════════════════════════════════════════════════════════════════
# TestOE04 — 最適化指数算出
# ════════════════════════════════════════════════════════════════

class TestOE04_CalculateOptimizationIndex:

    def test_returns_list(self, evaluator, evaluated):
        assert isinstance(evaluated, list)

    def test_adds_optimization_index(self, evaluated):
        for p in evaluated:
            assert "optimization_index" in p

    def test_optimization_index_between_0_and_1(self, evaluated):
        for p in evaluated:
            assert 0.0 <= p["optimization_index"] <= 1.0

    def test_adds_status_field(self, evaluated):
        for p in evaluated:
            assert "status" in p
            assert p["status"] in ("stable", "warning", "critical")

    def test_high_score_patterns_are_stable(self, evaluated):
        high_score = [p for p in evaluated if p.get("score", 0) >= 1.0]
        assert all(p["status"] == "stable" for p in high_score)

    def test_optimization_index_is_weighted_avg(self, evaluator):
        pattern = {"pattern_id": "X", "category": "operational",
                   "cause": "c", "action": "a", "result": "PASS",
                   "score": 1.0, "reproducibility": "high", "pattern_type": "success"}
        with_repro  = evaluator.evaluate_reproducibility([pattern])
        with_impact = evaluator.evaluate_impact(with_repro)
        with_index  = evaluator.calculate_optimization_index(with_impact)
        repro  = with_index[0]["reproducibility_score"]
        impact = with_index[0]["impact_score"]
        index  = with_index[0]["optimization_index"]
        expected = round(repro * 0.6 + impact * 0.4, 4)
        assert abs(index - expected) < 0.0001

    def test_pattern_id_preserved(self, evaluated):
        assert evaluated[0]["pattern_id"] == "OP-001"


# ════════════════════════════════════════════════════════════════
# TestOE05 — レポート生成
# ════════════════════════════════════════════════════════════════

class TestOE05_ExportReport:

    @pytest.fixture
    def report(self, evaluator, evaluated):
        return evaluator.export_report(evaluated)

    def test_returns_dict(self, report):
        assert isinstance(report, dict)

    def test_total_patterns_correct(self, report, evaluated):
        assert report["total_patterns"] == len(evaluated)

    def test_phase_is_7(self, report):
        assert report["phase"] == 7

    def test_summary_has_avg_scores(self, report):
        s = report["summary"]
        assert "avg_reproducibility_score" in s
        assert "avg_impact_score" in s
        assert "avg_optimization_index" in s

    def test_summary_avg_between_0_and_1(self, report):
        s = report["summary"]
        for key in ("avg_reproducibility_score", "avg_impact_score", "avg_optimization_index"):
            assert 0.0 <= s[key] <= 1.0

    def test_status_distribution_present(self, report):
        sd = report["summary"]["status_distribution"]
        assert "stable" in sd and "warning" in sd and "critical" in sd

    def test_status_sums_to_total(self, report, evaluated):
        sd    = report["summary"]["status_distribution"]
        total = sd["stable"] + sd["warning"] + sd["critical"]
        assert total == len(evaluated)

    def test_by_category_has_four_categories(self, report):
        cats = set(report["by_category"].keys())
        assert {"operational", "improvement", "maintenance", "environment"} == cats

    def test_by_category_has_avg_optimization_index(self, report):
        for cat, info in report["by_category"].items():
            assert "avg_optimization_index" in info

    def test_phase7_complete_is_true(self, report):
        assert report["phase7_complete"] is True

    def test_phase8_ready_is_true(self, report):
        assert report["phase8_ready"] is True

    def test_evaluated_patterns_in_report(self, report, evaluated):
        assert len(report["evaluated_patterns"]) == len(evaluated)

    def test_empty_patterns_returns_valid_report(self, evaluator):
        report = evaluator.export_report([])
        assert report["total_patterns"] == 0
        assert report["phase7_complete"] is True


# ════════════════════════════════════════════════════════════════
# TestOE06 — 保存 / 読み込み / summary.log
# ════════════════════════════════════════════════════════════════

class TestOE06_SaveLoad:

    @pytest.fixture
    def report(self, evaluator, evaluated):
        return evaluator.export_report(evaluated)

    def test_save_creates_file(self, evaluator, report, tmp_path):
        p = tmp_path / "report.json"
        evaluator.save_report(report, path=p)
        assert p.exists()

    def test_saved_is_valid_json(self, evaluator, report, tmp_path):
        p = tmp_path / "report.json"
        evaluator.save_report(report, path=p)
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)

    def test_load_report_returns_dict(self, evaluator, report, tmp_path):
        p = tmp_path / "report.json"
        evaluator.save_report(report, path=p)
        loaded = evaluator.load_report(path=p)
        assert isinstance(loaded, dict)

    def test_load_nonexistent_returns_empty(self, tmp_path):
        e = OptimizationEvaluator(report_path=tmp_path / "no.json")
        assert e.load_report() == {}

    def test_write_summary_creates_log(self, evaluator, report, tmp_path):
        log = tmp_path / "summary.log"
        evaluator.write_summary_entry(report, log_path=log)
        assert log.exists()

    def test_write_summary_has_wp9430(self, evaluator, report, tmp_path):
        log = tmp_path / "summary.log"
        evaluator.write_summary_entry(report, log_path=log)
        assert "WP9430" in log.read_text(encoding="utf-8")

    def test_write_summary_has_phase8_ready(self, evaluator, report, tmp_path):
        log = tmp_path / "summary.log"
        evaluator.write_summary_entry(report, log_path=log)
        assert "Phase 8" in log.read_text(encoding="utf-8")

    def test_write_summary_has_overall_status(self, evaluator, report, tmp_path):
        log = tmp_path / "summary.log"
        evaluator.write_summary_entry(report, log_path=log)
        assert "総合ステータス" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# TestOE07 — KnowledgeCycle 連携
# ════════════════════════════════════════════════════════════════

class TestOE07_KnowledgeCycleIntegration:

    @pytest.fixture
    def kc_with_report(self, tmp_path, tmp_patterns_file):
        e        = OptimizationEvaluator(
            patterns_path=tmp_patterns_file,
            report_path=tmp_path / "knowledge_cycle" / "optimization_report.json",
            summary_log=tmp_path / "summary.log",
        )
        patterns = e.load_patterns()
        patterns = e.evaluate_reproducibility(patterns)
        patterns = e.evaluate_impact(patterns)
        patterns = e.calculate_optimization_index(patterns)
        report   = e.export_report(patterns)
        e.save_report(report)

        kc   = KnowledgeCycle(cycle_dir=tmp_path / "knowledge_cycle",
                               summary_log=tmp_path / "summary.log")
        path = tmp_path / "knowledge_cycle" / "optimization_report.json"
        return kc, path

    def test_get_optimization_report_returns_dict(self, kc_with_report):
        kc, path = kc_with_report
        result = kc.get_optimization_report(path=path)
        assert isinstance(result, dict)

    def test_get_optimization_report_has_summary(self, kc_with_report):
        kc, path = kc_with_report
        result = kc.get_optimization_report(path=path)
        assert "summary" in result

    def test_get_optimization_report_phase7_complete(self, kc_with_report):
        kc, path = kc_with_report
        result = kc.get_optimization_report(path=path)
        assert result.get("phase7_complete") is True

    def test_get_optimization_report_phase8_ready(self, kc_with_report):
        kc, path = kc_with_report
        result = kc.get_optimization_report(path=path)
        assert result.get("phase8_ready") is True

    def test_get_optimization_report_missing_returns_empty(self, tmp_path):
        kc = KnowledgeCycle(cycle_dir=tmp_path / "kc")
        assert kc.get_optimization_report() == {}

    def test_get_optimization_report_has_by_category(self, kc_with_report):
        kc, path = kc_with_report
        result = kc.get_optimization_report(path=path)
        assert "by_category" in result
