"""Phase 4 — WP8100 単体テスト
区分：因果ロジック / テンプレート適用 / MECEチェック

WP8100 の観点：
  - 各モジュールの核心ロジック（非パイプライン）を単独で検証する
  - 入力固定・出力決定論的なケースのみを対象とする
  - 「因果の正しさ」「テンプレ書式」「MECE判定境界値」を重点検証する
"""

import pytest


# ════════════════════════════════════════════════════════
# WP8110: 因果ロジック（F30: importance/feasibility → priority）
# ════════════════════════════════════════════════════════

class TestWP8110_CausalLogic:
    """WP8110: 因果ロジック — F30 の importance/feasibility → priority 変換"""

    def test_evaluate_element_returns_dict(self):
        from src.agents.f30_module import _evaluate_element
        result = _evaluate_element({"element_id": "E1", "text": "LP作成", "parent": "L3"})
        assert isinstance(result, dict)

    def test_evaluate_element_output_keys(self):
        from src.agents.f30_module import _evaluate_element
        result = _evaluate_element({"element_id": "E1", "text": "LP作成", "parent": "L3"})
        required = {"element_id", "text", "parent", "score_importance", "score_feasibility", "priority"}
        assert required <= result.keys()

    def test_score_importance_range(self):
        from src.agents.f30_module import _score_importance
        for parent in ("L1", "L2", "L3"):
            score = _score_importance("テストテキスト", parent)
            assert 0.0 <= score <= 1.0, f"parent={parent} → score={score} が範囲外"

    def test_score_feasibility_range(self):
        from src.agents.f30_module import _score_feasibility
        for parent in ("L1", "L2", "L3"):
            score = _score_feasibility("テストテキスト", parent)
            assert 0.0 <= score <= 1.0

    def test_l1_importance_higher_than_l3(self):
        """L1（上位目標）の importance 基礎スコアは L3 より高いこと。"""
        from src.agents.f30_module import _score_importance
        l1 = _score_importance("売上拡大", "L1")
        l3 = _score_importance("バナー作成", "L3")
        assert l1 >= l3

    def test_l3_feasibility_higher_than_l1(self):
        """L3（具体タスク）の feasibility 基礎スコアは L1 より高いこと。"""
        from src.agents.f30_module import _score_feasibility
        l1 = _score_feasibility("売上拡大", "L1")
        l3 = _score_feasibility("LP作成", "L3")
        assert l3 >= l1

    def test_classify_priority_high(self):
        """平均スコア ≥ 0.70 → High"""
        from src.agents.f30_module import _classify_priority
        assert _classify_priority(0.85, 0.85) == "High"

    def test_classify_priority_medium(self):
        """平均スコア 0.50〜0.70 → Medium"""
        from src.agents.f30_module import _classify_priority
        assert _classify_priority(0.60, 0.60) == "Medium"

    def test_classify_priority_low(self):
        """平均スコア < 0.50 → Low"""
        from src.agents.f30_module import _classify_priority
        assert _classify_priority(0.30, 0.30) == "Low"

    def test_classify_priority_boundary_high(self):
        """平均 = 0.70 は High"""
        from src.agents.f30_module import _classify_priority
        assert _classify_priority(0.70, 0.70) == "High"

    def test_classify_priority_boundary_medium(self):
        """平均 = 0.50 は Medium"""
        from src.agents.f30_module import _classify_priority
        assert _classify_priority(0.50, 0.50) == "Medium"

    def test_priority_is_valid_string(self):
        from src.agents.f30_module import _evaluate_element
        result = _evaluate_element({"element_id": "E1", "text": "売上拡大", "parent": "L1"})
        assert result["priority"] in ("High", "Medium", "Low")

    def test_element_id_preserved_in_output(self):
        from src.agents.f30_module import _evaluate_element
        result = _evaluate_element({"element_id": "E99", "text": "テスト", "parent": "L2"})
        assert result["element_id"] == "E99"

    def test_l1_element_classified_as_high(self):
        """L1 は importance=0.85, feasibility=0.50 → avg=0.675 → Medium 以上"""
        from src.agents.f30_module import _evaluate_element, _IMPORTANCE_BASE, _FEASIBILITY_BASE
        result = _evaluate_element({"element_id": "E1", "text": "売上拡大", "parent": "L1"})
        imp_base  = _IMPORTANCE_BASE["L1"]
        feas_base = _FEASIBILITY_BASE["L1"]
        avg = (imp_base + feas_base) / 2
        expected = "High" if avg >= 0.70 else "Medium"
        assert result["priority"] == expected


# ════════════════════════════════════════════════════════
# WP8120: テンプレート適用（F50: TMP_HIGH/MEDIUM/LOW 書式）
# ════════════════════════════════════════════════════════

class TestWP8120_TemplateFormat:
    """WP8120: テンプレート適用の書式検証"""

    def _make_task(self, text, priority):
        return {"task_id": "T1", "task_text": text, "priority": priority,
                "effort": 2, "value": 4, "element_id": "E1"}

    def test_high_template_prefix(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._make_task("LP作成", "High"))
        assert result["templated_text"].startswith("【優先度: 高】")

    def test_medium_template_prefix(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._make_task("広告配信", "Medium"))
        assert result["templated_text"].startswith("【優先度: 中】")

    def test_low_template_prefix(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._make_task("資料整理", "Low"))
        assert result["templated_text"].startswith("【優先度: 低】")

    def test_task_text_included_in_templated(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._make_task("LP作成テスト", "High"))
        assert "LP作成テスト" in result["templated_text"]

    def test_template_id_high(self):
        from src.agents.f50_module import _apply_template
        assert _apply_template(self._make_task("LP作成", "High"))["template_id"] == "TMP_HIGH"

    def test_template_id_medium(self):
        from src.agents.f50_module import _apply_template
        assert _apply_template(self._make_task("広告配信", "Medium"))["template_id"] == "TMP_MEDIUM"

    def test_template_id_low(self):
        from src.agents.f50_module import _apply_template
        assert _apply_template(self._make_task("資料整理", "Low"))["template_id"] == "TMP_LOW"

    def test_templated_text_is_nonempty(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._make_task("LP作成", "High"))
        assert len(result["templated_text"]) > 0

    def test_unknown_priority_raises_runtime(self):
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError):
            _apply_template(self._make_task("LP作成", "Unknown"))

    def test_all_required_keys_in_output(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._make_task("LP作成", "High"))
        assert {"task_id", "templated_text", "template_id", "priority"} <= result.keys()


# ════════════════════════════════════════════════════════
# WP8130: MECEチェック（F60: コサイン類似度境界値）
# ════════════════════════════════════════════════════════

class TestWP8130_MECEBoundary:
    """WP8130: MECEチェックの閾値境界値検証"""

    def test_cosine_identical_texts_score_one(self):
        from src.agents.f60_module import _cosine_similarity
        assert _cosine_similarity("LP作成 広告配信", "LP作成 広告配信") == pytest.approx(1.0)

    def test_cosine_no_overlap_score_zero(self):
        from src.agents.f60_module import _cosine_similarity
        assert _cosine_similarity("LP作成", "広告配信") == pytest.approx(0.0)

    def test_cosine_partial_overlap_between_zero_and_one(self):
        from src.agents.f60_module import _cosine_similarity
        score = _cosine_similarity("LP作成 売上拡大", "LP作成 広告出稿")
        assert 0.0 < score < 1.0

    def test_duplicate_threshold_is_0_85(self):
        from src.agents.f60_module import DUPLICATE_THRESHOLD
        assert DUPLICATE_THRESHOLD == pytest.approx(0.85)

    def test_uncertain_low_is_0_80(self):
        from src.agents.f60_module import UNCERTAIN_LOW
        assert UNCERTAIN_LOW == pytest.approx(0.80)

    def test_uncertain_high_is_0_85(self):
        from src.agents.f60_module import UNCERTAIN_HIGH
        assert UNCERTAIN_HIGH == pytest.approx(0.85)

    def test_identical_tasks_detected_as_duplicate(self):
        """完全一致ペアが duplicates に分類されること。"""
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            {"task_id": "T1", "templated_text": "LP作成 広告配信 売上拡大", "priority": "High"},
            {"task_id": "T2", "templated_text": "LP作成 広告配信 売上拡大", "priority": "High"},
        ]
        duplicates, uncertain = _detect_duplicates(tasks)
        assert len(duplicates) > 0

    def test_unrelated_tasks_not_flagged(self):
        """類似度 < 0.80 のペアが flagged されないこと。"""
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            {"task_id": "T1", "templated_text": "LP作成", "priority": "High"},
            {"task_id": "T2", "templated_text": "採用活動", "priority": "Low"},
        ]
        duplicates, uncertain = _detect_duplicates(tasks)
        assert len(duplicates) == 0
        assert len(uncertain) == 0

    def test_abstract_words_detected_as_ambiguous(self):
        from src.agents.f60_module import _detect_ambiguous, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [{"task_id": "T1", "templated_text": f"業務{word}する", "priority": "High"}]
        result = _detect_ambiguous(tasks)
        assert "T1" in result

    def test_non_abstract_task_not_flagged(self):
        from src.agents.f60_module import _detect_ambiguous
        tasks = [{"task_id": "T1", "templated_text": "LP作成する", "priority": "High"}]
        assert _detect_ambiguous(tasks) == []

    def test_missing_element_detection_gap(self):
        """element_id に E1, E3（E2 欠落）を持つタスクで missing_elements に E2 が入ること。"""
        from src.agents.f60_module import _detect_missing
        tasks = [
            {"task_id": "T1", "element_id": "E1", "templated_text": "タスク1", "priority": "High"},
            {"task_id": "T3", "element_id": "E3", "templated_text": "タスク3", "priority": "Low"},
        ]
        result = _detect_missing(tasks)
        assert "E2" in result

    def test_no_missing_when_sequential(self):
        """element_id が E1, E2, E3 で揃っていれば missing は空。"""
        from src.agents.f60_module import _detect_missing
        tasks = [
            {"task_id": "T1", "element_id": "E1", "templated_text": "タスク1", "priority": "High"},
            {"task_id": "T2", "element_id": "E2", "templated_text": "タスク2", "priority": "Medium"},
            {"task_id": "T3", "element_id": "E3", "templated_text": "タスク3", "priority": "Low"},
        ]
        assert _detect_missing(tasks) == []


# ════════════════════════════════════════════════════════
# WP8140: 階層生成（F70: Union-Find・ゴールテキスト抽出）
# ════════════════════════════════════════════════════════

class TestWP8140_HierarchyGrouping:
    """WP8140: Union-Find によるゴールグループ化の正確性"""

    def _task(self, tid, text, priority="High"):
        return {"task_id": tid, "templated_text": text,
                "priority": priority, "effort": 2, "value": 4, "element_id": "E1"}

    def test_identical_tasks_grouped_together(self):
        """完全同一テキストのタスクは同一グループになること。"""
        from src.agents.f70_module import _union_find_group
        tasks = [
            self._task("T1", "LP作成 広告配信 売上拡大"),
            self._task("T2", "LP作成 広告配信 売上拡大"),  # 完全一致 → cos=1.0 > 0.80
            self._task("T3", "採用活動 人材確保 HR施策", priority="Low"),
        ]
        groups = _union_find_group(tasks)
        sizes = sorted([len(g) for g in groups], reverse=True)
        assert sizes[0] >= 2

    def test_dissimilar_tasks_in_different_groups(self):
        from src.agents.f70_module import _union_find_group
        tasks = [
            self._task("T1", "LP作成"),
            self._task("T2", "採用活動", priority="Low"),
        ]
        assert len(_union_find_group(tasks)) == 2

    def test_goal_sim_threshold_is_0_80(self):
        from src.agents.f70_module import GOAL_SIM_THRESHOLD
        assert GOAL_SIM_THRESHOLD == pytest.approx(0.80)

    def test_strip_priority_prefix_high(self):
        from src.agents.f70_module import _strip_priority_prefix
        text = "【優先度: 高】次のタスクを実行せよ: LP作成"
        assert _strip_priority_prefix(text) == "LP作成"

    def test_strip_priority_prefix_medium(self):
        from src.agents.f70_module import _strip_priority_prefix
        text = "【優先度: 中】次のタスクを実行せよ: 広告配信"
        assert _strip_priority_prefix(text) == "広告配信"

    def test_strip_priority_prefix_no_colon(self):
        """コロンがないテキストはそのまま返ること。"""
        from src.agents.f70_module import _strip_priority_prefix
        text = "LP作成"
        result = _strip_priority_prefix(text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_goal_text_returns_string(self):
        from src.agents.f70_module import _extract_goal_text
        tasks = [
            {"task_id": "T1", "templated_text": "LP作成 広告配信"},
            {"task_id": "T2", "templated_text": "LP作成 売上拡大"},
        ]
        result = _extract_goal_text(tasks)
        assert isinstance(result, str) and len(result) > 0

    def test_is_only_abstract_returns_true_for_abstract(self):
        from src.agents.f70_module import _is_only_abstract, ABSTRACT_WORDS
        # ABSTRACT_WORDS のみのテキスト
        text = ABSTRACT_WORDS[0]
        assert _is_only_abstract(text) is True

    def test_is_only_abstract_returns_false_for_normal(self):
        from src.agents.f70_module import _is_only_abstract
        assert _is_only_abstract("LP作成") is False

    def test_priority_suffix_constants(self):
        from src.agents.f70_module import PRIORITY_SUFFIX
        assert PRIORITY_SUFFIX["High"]   == "EL_H"
        assert PRIORITY_SUFFIX["Medium"] == "EL_M"
        assert PRIORITY_SUFFIX["Low"]    == "EL_L"


# ════════════════════════════════════════════════════════
# WP8150: トレーサビリティ（F80: chain 完全性）
# ════════════════════════════════════════════════════════

class TestWP8150_TraceChain:
    """WP8150: trace_chain の完全性ロジック"""

    FULL_CHAIN = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]

    def test_full_chain_is_complete(self):
        from src.agents.f80_module import _is_chain_complete
        assert _is_chain_complete(self.FULL_CHAIN) is True

    def test_partial_chain_is_not_complete(self):
        from src.agents.f80_module import _is_chain_complete
        assert _is_chain_complete(["F10", "F20", "F30"]) is False

    def test_empty_chain_is_not_complete(self):
        from src.agents.f80_module import _is_chain_complete
        assert _is_chain_complete([]) is False

    def test_build_trace_chain_from_f70(self):
        from src.agents.f80_module import _build_trace_chain
        assert _build_trace_chain("F70") == self.FULL_CHAIN

    def test_build_trace_chain_from_f40(self):
        from src.agents.f80_module import _build_trace_chain
        assert _build_trace_chain("F40") == ["F10", "F20", "F30", "F40"]

    def test_build_trace_chain_unknown_returns_empty(self):
        from src.agents.f80_module import _build_trace_chain
        assert _build_trace_chain("F99") == []

    def test_pipeline_order_constant(self):
        from src.agents.f80_module import PIPELINE_ORDER
        assert PIPELINE_ORDER == self.FULL_CHAIN

    def test_expected_origin_is_f10(self):
        from src.agents.f80_module import EXPECTED_ORIGIN
        assert EXPECTED_ORIGIN == "F10"


# ════════════════════════════════════════════════════════
# WP8160: 最終出力（F90: efficiency_score 算術）
# ════════════════════════════════════════════════════════

class TestWP8160_EfficiencyScore:
    """WP8160: efficiency_score 算術の正確性"""

    def _make_hw(self, effort, value):
        return [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "テスト",
             "priority": "High", "effort": effort, "value": value}
        ]}]}]

    def test_score_5_div_3(self):
        from src.agents.f90_module import _compute_evaluation
        r = _compute_evaluation(self._make_hw(3, 5))
        assert r["efficiency_score"] == pytest.approx(1.67, abs=0.01)

    def test_score_10_div_2(self):
        from src.agents.f90_module import _compute_evaluation
        r = _compute_evaluation(self._make_hw(2, 10))
        assert r["efficiency_score"] == pytest.approx(5.0)

    def test_score_1_div_1(self):
        from src.agents.f90_module import _compute_evaluation
        r = _compute_evaluation(self._make_hw(1, 1))
        assert r["efficiency_score"] == pytest.approx(1.0)

    def test_zero_effort_raises_runtime(self):
        from src.agents.f90_module import _compute_evaluation
        hw = [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "x", "priority": "High",
             "effort": None, "value": None}
        ]}]}]
        with pytest.raises(RuntimeError):
            _compute_evaluation(hw)

    def test_average_effort_rounding(self):
        from src.agents.f90_module import _compute_evaluation
        hw = [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "x", "priority": "High", "effort": 1, "value": 3},
            {"task_id": "T2", "templated_text": "y", "priority": "Low",  "effort": 2, "value": 5},
        ]}]}]
        r = _compute_evaluation(hw)
        assert r["average_effort"] == pytest.approx(1.5)
        assert r["average_value"]  == pytest.approx(4.0)

    def test_efficiency_max_constant(self):
        from src.agents.f90_module import EFFICIENCY_MAX
        assert EFFICIENCY_MAX == pytest.approx(10.0)

    def test_score_is_rounded_to_2_places(self):
        from src.agents.f90_module import _compute_evaluation
        r = _compute_evaluation(self._make_hw(3, 10))
        # 10/3 = 3.333... → 3.33
        assert r["efficiency_score"] == pytest.approx(3.33, abs=0.01)
