"""Unit tests for F30_Goal_Element_Evaluator (WP5100準拠)

F10/F20 と共通のヘルパーパターン（assert_warning_contains / assert_wrapped_cause）
を再利用し、F30 固有のスコア評価ロジックを検証する。
"""

import json
import logging

import pytest

from src.agents.f30_module import (
    _check_hitl_element,
    _classify_priority,
    _evaluate_element,
    _preprocess,
    _score_feasibility,
    _score_importance,
    _validate_evaluated,
    _validate_input,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー
# ════════════════════════════════════════════════════════

VALID_INPUT = {
    "trace_id": "F20",
    "expanded_goals": [
        {"element_id": "E1", "text": "売上を前年比120%に成長させる", "parent": "L1"},
        {"element_id": "E2", "text": "新規顧客獲得施策を推進する",   "parent": "L2"},
        {"element_id": "E3", "text": "LPを作成する",                "parent": "L3"},
    ],
}

# dict 以外の入力 → TypeError
INVALID_TYPE_INPUTS = [
    pytest.param(None,     id="none"),
    pytest.param("string", id="string"),
    pytest.param(42,       id="int"),
    pytest.param([],       id="list"),
]

# dict だが構造不正 → ValueError
INVALID_STRUCT_INPUTS = [
    pytest.param({},                                                   id="empty_dict"),
    pytest.param({"trace_id": "F20"},                                  id="missing_expanded_goals"),
    pytest.param({"expanded_goals": "not_a_list", "trace_id": "F20"}, id="goals_not_list"),
    pytest.param(
        {"expanded_goals": [{"text": "x", "parent": "L1"}], "trace_id": "F20"},
        id="missing_element_id",
    ),
    pytest.param(
        {"expanded_goals": [{"element_id": "E1", "parent": "L1"}], "trace_id": "F20"},
        id="missing_text",
    ),
    pytest.param(
        {"expanded_goals": [{"element_id": "E1", "text": "x"}], "trace_id": "F20"},
        id="missing_parent",
    ),
    pytest.param(
        {"expanded_goals": ["not_a_dict"], "trace_id": "F20"},
        id="element_not_dict",
    ),
]


def assert_warning_contains(caplog_records, keyword: str, category: str) -> None:
    """WARNING ログに指定キーワードが含まれることを検証（F10/F20 共通ヘルパーと同実装）。"""
    matched = [r for r in caplog_records if keyword in r.message and r.levelno == logging.WARNING]
    assert matched, (
        f"WARNING カテゴリ [{category}] のログが見つかりません（keyword='{keyword}'）\n"
        f"実際の WARNING ログ: {[r.message for r in caplog_records if r.levelno == logging.WARNING]}"
    )


def assert_wrapped_cause(exc_info, expected_cause_type, label: str = "") -> None:
    """RuntimeError が期待する例外型を __cause__ に保持しているか検証（F10/F20 共通ヘルパーと同実装）。"""
    cause = exc_info.value.__cause__
    assert cause is not None, f"[{label}] __cause__ が None です"
    assert isinstance(cause, expected_cause_type), (
        f"[{label}] __cause__ の型: expected={expected_cause_type.__name__}, "
        f"actual={type(cause).__name__}"
    )


# ════════════════════════════════════════════════════════
# Test1 — 正常系：スコア算出・priority 分類
# ════════════════════════════════════════════════════════

class TestNormalEvaluation:
    """execute() が正常入力に対して正しい evaluated_goals を返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)

    def test_trace_id_is_f30(self):
        assert self.result["trace_id"] == "F30"
        assert self.result["hitl"] is False

    def test_source_trace_id_preserved(self):
        assert self.result["source_trace_id"] == "F20"

    def test_evaluated_goals_length_matches_input(self):
        """入力と同数の evaluated_goals が返ること（HITL なし）。"""
        assert len(self.result["evaluated_goals"]) == 3

    def test_all_required_fields_present(self):
        required = {"element_id", "text", "parent", "score_importance", "score_feasibility", "priority"}
        for elem in self.result["evaluated_goals"]:
            assert required <= elem.keys(), f"フィールド不足: {elem}"

    def test_scores_in_valid_range(self):
        """score_importance / score_feasibility が 0.0〜1.0 の範囲内であること。"""
        for elem in self.result["evaluated_goals"]:
            assert 0.0 <= elem["score_importance"]  <= 1.0, f"importance 範囲外: {elem}"
            assert 0.0 <= elem["score_feasibility"] <= 1.0, f"feasibility 範囲外: {elem}"

    def test_priority_is_valid_value(self):
        """priority が High / Medium / Low のいずれかであること。"""
        valid = {"High", "Medium", "Low"}
        for elem in self.result["evaluated_goals"]:
            assert elem["priority"] in valid, f"不正な priority: {elem}"

    def test_l1_has_highest_importance(self):
        """L1 要素の importance が L3 より高いこと。"""
        goals = self.result["evaluated_goals"]
        l1 = next(e for e in goals if e["parent"] == "L1")
        l3 = next(e for e in goals if e["parent"] == "L3")
        assert l1["score_importance"] > l3["score_importance"]

    def test_l3_has_highest_feasibility(self):
        """L3 要素の feasibility が L1 より高いこと。"""
        goals = self.result["evaluated_goals"]
        l1 = next(e for e in goals if e["parent"] == "L1")
        l3 = next(e for e in goals if e["parent"] == "L3")
        assert l3["score_feasibility"] > l1["score_feasibility"]

    def test_element_id_and_text_preserved(self):
        """element_id と text が入力から正しく引き継がれること。"""
        goals = self.result["evaluated_goals"]
        for orig, eval_ in zip(VALID_INPUT["expanded_goals"], goals):
            assert eval_["element_id"] == orig["element_id"]
            assert eval_["text"]       == orig["text"]
            assert eval_["parent"]     == orig["parent"]

    def test_hitl_elements_empty_when_no_hitl(self):
        assert self.result["hitl_elements"] == []

    def test_empty_expanded_goals_returns_empty_evaluated(self):
        """expanded_goals が空リストの場合、evaluated_goals も空で返ること。"""
        data   = {"trace_id": "F20", "expanded_goals": []}
        result = execute(data)
        assert result["evaluated_goals"] == []
        assert result["trace_id"] == "F30"

    # ── スコア算出ロジック単体検証 ──

    def test_importance_bonus_for_numeric_ratio(self):
        """数値比率表現を含む L2 テキストで importance にボーナスが付くこと。"""
        score = _score_importance("売上を120%に向上させる", "L2")
        assert score > _score_importance("売上を向上させる", "L2")

    def test_importance_penalty_for_short_abstract(self):
        """短い抽象語のみのテキストで importance にペナルティが付くこと。"""
        score_abstract = _score_importance("改善", "L2")
        score_normal   = _score_importance("新規顧客獲得施策を推進する", "L2")
        assert score_abstract < score_normal

    def test_feasibility_bonus_for_action_verb(self):
        """動作動詞を含むテキストで feasibility にボーナスが付くこと。"""
        score_with    = _score_feasibility("LPを作成する", "L3")
        score_without = _score_feasibility("LP整備", "L3")
        assert score_with > score_without

    def test_feasibility_penalty_for_short_text(self):
        """5文字以下のテキストで feasibility にペナルティが付くこと。"""
        score_short  = _score_feasibility("改善", "L3")
        score_normal = _score_feasibility("LPを作成する", "L3")
        assert score_short < score_normal

    def test_priority_high_threshold(self):
        assert _classify_priority(0.85, 0.75) == "High"

    def test_priority_medium_threshold(self):
        assert _classify_priority(0.60, 0.55) == "Medium"

    def test_priority_low_threshold(self):
        assert _classify_priority(0.35, 0.40) == "Low"

    def test_priority_boundary_exactly_070(self):
        """平均ちょうど 0.70 は High になること。"""
        assert _classify_priority(0.70, 0.70) == "High"

    def test_priority_boundary_exactly_050(self):
        """平均ちょうど 0.50 は Medium になること。"""
        assert _classify_priority(0.50, 0.50) == "Medium"


# ════════════════════════════════════════════════════════
# Test2 — 異常系：入力不正
# ════════════════════════════════════════════════════════

class TestInvalidInput:
    """dict 以外は TypeError、構造不正・フィールド欠落は ValueError を検証する。"""

    @pytest.mark.parametrize("bad_input", INVALID_TYPE_INPUTS)
    def test_type_error_for_non_dict(self, bad_input):
        with pytest.raises(TypeError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_STRUCT_INPUTS)
    def test_value_error_for_invalid_structure(self, bad_input):
        with pytest.raises(ValueError):
            execute(bad_input)

    def test_validate_input_none(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input(None)

    def test_validate_input_empty_dict(self):
        with pytest.raises(ValueError, match="空"):
            _validate_input({})

    def test_validate_input_missing_expanded_goals(self):
        with pytest.raises(ValueError, match="expanded_goals"):
            _validate_input({"trace_id": "F20"})

    def test_validate_input_goals_not_list(self):
        with pytest.raises(ValueError, match="list"):
            _validate_input({"expanded_goals": "bad"})

    def test_validate_input_missing_element_id(self):
        with pytest.raises(ValueError, match="element_id"):
            _validate_input({"expanded_goals": [{"text": "x", "parent": "L1"}]})

    def test_validate_input_missing_text(self):
        with pytest.raises(ValueError, match="text"):
            _validate_input({"expanded_goals": [{"element_id": "E1", "parent": "L1"}]})

    def test_validate_input_missing_parent(self):
        with pytest.raises(ValueError, match="parent"):
            _validate_input({"expanded_goals": [{"element_id": "E1", "text": "x"}]})


# ════════════════════════════════════════════════════════
# Test3 — HITL移譲：空文字・曖昧語（要素単位）
# ════════════════════════════════════════════════════════

class TestHitlDelegation:
    """空文字列・曖昧語要素が hitl_elements に追加され、
    全要素が対象の場合に hitl: True が返ることを検証する。
    """

    def test_empty_text_element_goes_to_hitl(self):
        data = {
            "trace_id": "F20",
            "expanded_goals": [
                {"element_id": "E1", "text": "", "parent": "L1"},
                {"element_id": "E2", "text": "LPを作成する", "parent": "L3"},
            ],
        }
        result = execute(data)
        assert "E1" in result["hitl_elements"]
        assert "E2" not in result["hitl_elements"]
        assert result["hitl"] is False  # E2 は評価済み

    def test_whitespace_text_triggers_hitl(self):
        data = {
            "trace_id": "F20",
            "expanded_goals": [{"element_id": "E1", "text": "   ", "parent": "L1"}],
        }
        result = execute(data)
        assert "E1" in result["hitl_elements"]

    def test_ambiguous_word_triggers_hitl(self):
        data = {
            "trace_id": "F20",
            "expanded_goals": [{"element_id": "E1", "text": "売上などを改善したい", "parent": "L2"}],
        }
        result = execute(data)
        assert "E1" in result["hitl_elements"]

    def test_all_elements_hitl_sets_hitl_true(self):
        """全要素が HITL 対象の場合、hitl: True で返ること。"""
        data = {
            "trace_id": "F20",
            "expanded_goals": [
                {"element_id": "E1", "text": "",          "parent": "L1"},
                {"element_id": "E2", "text": "売上など", "parent": "L2"},
            ],
        }
        result = execute(data)
        assert result["hitl"] is True
        assert result["evaluated_goals"] == []

    def test_partial_hitl_evaluated_goals_not_empty(self):
        """一部 HITL でも残りは evaluated_goals に含まれること。"""
        data = {
            "trace_id": "F20",
            "expanded_goals": [
                {"element_id": "E1", "text": "",          "parent": "L1"},
                {"element_id": "E2", "text": "LPを作成する", "parent": "L3"},
            ],
        }
        result = execute(data)
        assert result["hitl"] is False
        assert len(result["evaluated_goals"]) == 1
        assert result["evaluated_goals"][0]["element_id"] == "E2"

    def test_check_hitl_element_empty(self):
        reason = _check_hitl_element({"element_id": "E1", "text": "", "parent": "L1"})
        assert reason == "Goal element text is empty"

    def test_check_hitl_element_ambiguous(self):
        reason = _check_hitl_element({"element_id": "E1", "text": "売上などを上げたい", "parent": "L2"})
        assert reason is not None and "HITL" in reason

    def test_check_hitl_element_normal_returns_none(self):
        assert _check_hitl_element({"element_id": "E1", "text": "LPを作成する", "parent": "L3"}) is None


# ════════════════════════════════════════════════════════
# Test4 — スコア算出失敗：RuntimeError・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestScoringError:
    """スコア算出処理が失敗した場合に RuntimeError が送出され、
    __cause__ に元の例外が保持されることを検証する。
    """

    def test_runtime_error_on_score_failure(self, mocker):
        mocker.patch(
            "src.agents.f30_module._score_importance",
            side_effect=ValueError("スコア算出テストエラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_is_preserved(self, mocker):
        original = ValueError("内部スコアエラー")
        mocker.patch("src.agents.f30_module._score_importance", side_effect=original)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, ValueError, label="スコア算出失敗")

    def test_evaluate_element_wraps_exception(self, mocker):
        """_evaluate_element 内部で例外が起きた場合に RuntimeError にラップすること。"""
        mocker.patch(
            "src.agents.f30_module._score_importance",
            side_effect=ZeroDivisionError("ゼロ除算テスト"),
        )
        elem = {"element_id": "E1", "text": "テスト", "parent": "L1"}
        with pytest.raises(RuntimeError) as exc_info:
            _evaluate_element(elem)
        assert_wrapped_cause(exc_info, ZeroDivisionError, label="_evaluate_element ラップ")

    def test_runtime_error_message_contains_element_id(self, mocker):
        mocker.patch("src.agents.f30_module._score_importance", side_effect=ValueError("err"))
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert "element_id" in str(exc_info.value)


# ════════════════════════════════════════════════════════
# Test5 — WARNING継続：重複 element_id・不正 parent・スコア範囲外
# ════════════════════════════════════════════════════════

class TestWarningContinuation:
    """重複・不整合・スコア範囲外が WARNING ログを出力し、処理継続することを検証する。"""

    def test_duplicate_element_id_in_input_logs_warning(self, caplog):
        """入力の expanded_goals に重複 element_id が含まれる場合に Duplicate WARNING。"""
        data = {
            "trace_id": "F20",
            "expanded_goals": [
                {"element_id": "E1", "text": "大目的", "parent": "L1"},
                {"element_id": "E1", "text": "重複要素", "parent": "L2"},  # 重複
            ],
        }
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複", "Duplicate")

    def test_invalid_parent_in_evaluated_logs_warning(self, caplog):
        """評価結果の parent が不正な場合に ParentMismatch WARNING。"""
        evaluated = [
            {"element_id": "E1", "score_importance": 0.8, "score_feasibility": 0.7,
             "priority": "High", "parent": "L4"},  # 不正
        ]
        with caplog.at_level(logging.WARNING):
            _validate_evaluated(evaluated)
        assert_warning_contains(caplog.records, "不正な parent", "ParentMismatch")

    def test_score_out_of_range_logs_warning(self, caplog):
        """スコアが 0.0〜1.0 の範囲外の場合に ScoreRange WARNING。"""
        evaluated = [
            {"element_id": "E1", "score_importance": 1.5, "score_feasibility": 0.7,
             "priority": "High", "parent": "L1"},  # importance 範囲外
        ]
        with caplog.at_level(logging.WARNING):
            _validate_evaluated(evaluated)
        assert_warning_contains(caplog.records, "スコア範囲外", "ScoreRange")

    def test_invalid_priority_logs_warning(self, caplog):
        """priority が High/Medium/Low 以外の場合に Priority WARNING。"""
        evaluated = [
            {"element_id": "E1", "score_importance": 0.8, "score_feasibility": 0.7,
             "priority": "Critical", "parent": "L1"},  # 不正
        ]
        with caplog.at_level(logging.WARNING):
            _validate_evaluated(evaluated)
        assert_warning_contains(caplog.records, "不正な priority", "InvalidPriority")

    def test_unknown_trace_id_logs_warning(self, caplog):
        """source trace_id が 'F20' 以外の場合に WARNING。"""
        data = {"trace_id": "F99", "expanded_goals": VALID_INPUT["expanded_goals"]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_processing_continues_after_duplicate_warning(self, caplog):
        """重複 WARNING 後も処理が継続し、evaluated_goals が返ること。"""
        data = {
            "trace_id": "F20",
            "expanded_goals": [
                {"element_id": "E1", "text": "大目的", "parent": "L1"},
                {"element_id": "E1", "text": "重複要素", "parent": "L2"},
            ],
        }
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F30"
        assert len(result["evaluated_goals"]) == 2  # 重複でも両方評価

    def test_empty_goals_logs_warning(self, caplog):
        """expanded_goals が空リストの場合に WARNING が出ること。"""
        data = {"trace_id": "F20", "expanded_goals": []}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "空リスト", "EmptyGoals")


# ════════════════════════════════════════════════════════
# Test6 — trace_id="F30" の確認
# ════════════════════════════════════════════════════════

class TestTraceId:
    """出力の trace_id が常に 'F30' であることを各ケースで検証する。"""

    def test_normal_output_trace_id_is_f30(self):
        assert execute(VALID_INPUT)["trace_id"] == "F30"

    def test_hitl_output_trace_id_is_f30(self):
        data = {
            "trace_id": "F20",
            "expanded_goals": [{"element_id": "E1", "text": "", "parent": "L1"}],
        }
        assert execute(data)["trace_id"] == "F30"

    def test_empty_goals_trace_id_is_f30(self):
        data = {"trace_id": "F20", "expanded_goals": []}
        assert execute(data)["trace_id"] == "F30"

    def test_unknown_source_trace_id_output_is_f30(self, caplog):
        data = {"trace_id": "UNKNOWN", "expanded_goals": VALID_INPUT["expanded_goals"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F30"

    def test_source_trace_id_reflects_input(self):
        result = execute(VALID_INPUT)
        assert result["source_trace_id"] == "F20"

    def test_missing_trace_id_in_input(self, caplog):
        """入力に trace_id がない場合でも trace_id='F30' で返ること。"""
        data = {"expanded_goals": VALID_INPUT["expanded_goals"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F30"
        assert result["source_trace_id"] == ""

    def test_f10_to_f20_to_f30_pipeline(self):
        """F10→F20→F30 のパイプラインを模擬し、trace_id が正しく伝播することを検証。"""
        # F10 出力を模擬
        f10_out = {
            "trace_id": "F10",
            "goal": {
                "L1": "売上を前年比120%に成長させる",
                "L2": ["新規顧客獲得施策を推進する"],
                "L3": ["LPを作成する"],
            },
        }
        # F20 出力を模擬（F20 モジュールを直接呼ぶ）
        from src.agents.f20_module import execute as f20_execute
        f20_out = f20_execute(f10_out)
        assert f20_out["trace_id"] == "F20"

        # F30 に渡す
        f30_out = execute(f20_out)
        assert f30_out["trace_id"] == "F30"
        assert f30_out["source_trace_id"] == "F20"
        assert len(f30_out["evaluated_goals"]) == 3
