"""Unit tests for F20_Goal_Expansion_Module (WP5100準拠)

F10 との共通パターン（INVALID_INPUTS / assert_wrapped_cause / assert_warning_contains）
を再利用し、F20 固有の検証を追加する。
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.agents.f20_module import (
    _check_hitl,
    _expand_goals,
    _preprocess,
    _validate_elements,
    _validate_input,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー（F10 パターンを踏襲）
# ════════════════════════════════════════════════════════

VALID_INPUT = {
    "trace_id": "F10",
    "goal": {
        "L1": "売上を前年比120%に成長させる",
        "L2": ["新規顧客獲得施策を推進する", "既存顧客リテンションを強化する"],
        "L3": ["LPを作成する", "広告配信を開始する", "フォローアップメールを設計する"],
    },
}

# 不正入力の共通定数（F10 の INVALID_INPUTS と同構造）
INVALID_INPUTS = [
    pytest.param(None,          id="none"),
    pytest.param("string",      id="string_type"),
    pytest.param(42,            id="int_type"),
    pytest.param([],            id="list_type"),
]

# goal 欠落・型不正の共通定数
INVALID_GOAL_INPUTS = [
    pytest.param({},                                           id="empty_dict"),
    pytest.param({"trace_id": "F10"},                         id="missing_goal"),
    pytest.param({"goal": None,    "trace_id": "F10"},        id="goal_is_none"),
    pytest.param({"goal": {},      "trace_id": "F10"},        id="goal_empty"),
    pytest.param({"goal": {"L1": "", "L2": [], "L3": []},     "trace_id": "F10"}, id="l1_empty"),
    pytest.param({"goal": {"L2": ["x"], "L3": []},            "trace_id": "F10"}, id="missing_l1"),
    pytest.param({"goal": {"L1": "x", "L3": []},              "trace_id": "F10"}, id="missing_l2"),
    pytest.param({"goal": {"L1": "x", "L2": []},              "trace_id": "F10"}, id="missing_l3"),
    pytest.param({"goal": {"L1": 123,  "L2": [], "L3": []},   "trace_id": "F10"}, id="l1_not_str"),
    pytest.param({"goal": {"L1": "x",  "L2": "bad", "L3": []}, "trace_id": "F10"}, id="l2_not_list"),
]


def assert_warning_contains(caplog_records, keyword: str, category: str) -> None:
    """WARNING ログに指定キーワードが含まれることを検証（F10 共通ヘルパーと同実装）。"""
    matched = [r for r in caplog_records if keyword in r.message and r.levelno == logging.WARNING]
    assert matched, (
        f"WARNING カテゴリ [{category}] のログが見つかりません（keyword='{keyword}'）\n"
        f"実際の WARNING ログ: {[r.message for r in caplog_records if r.levelno == logging.WARNING]}"
    )


def assert_wrapped_cause(exc_info, expected_cause_type, label: str = "") -> None:
    """RuntimeError が期待する例外型を __cause__ に保持しているか検証（F10 共通ヘルパーと同実装）。"""
    cause = exc_info.value.__cause__
    assert cause is not None, f"[{label}] __cause__ が None です"
    assert isinstance(cause, expected_cause_type), (
        f"[{label}] __cause__ の型: expected={expected_cause_type.__name__}, "
        f"actual={type(cause).__name__}"
    )


# ════════════════════════════════════════════════════════
# Test1 — 正常系：L1/L2/L3 の展開結果検証
# ════════════════════════════════════════════════════════

class TestNormalExpansion:
    """execute() が正常入力に対して正しい expanded_goals を返すことを検証する。"""

    def test_returns_trace_id_f20(self):
        result = execute(VALID_INPUT)
        assert result["trace_id"] == "F20"
        assert result["hitl"] is False

    def test_source_trace_id_preserved(self):
        result = execute(VALID_INPUT)
        assert result["source_trace_id"] == "F10"

    def test_expanded_goals_is_list(self):
        result = execute(VALID_INPUT)
        assert isinstance(result["expanded_goals"], list)
        assert len(result["expanded_goals"]) > 0

    def test_element_count_matches_input(self):
        """L1(1) + L2(2) + L3(3) = 6 要素が展開されること。"""
        result = execute(VALID_INPUT)
        goals = result["expanded_goals"]
        assert len(goals) == 6

    def test_element_id_sequential(self):
        """element_id が E1 から連番で付与されること。"""
        result = execute(VALID_INPUT)
        ids = [e["element_id"] for e in result["expanded_goals"]]
        assert ids == [f"E{i}" for i in range(1, len(ids) + 1)]

    def test_parent_values_are_correct(self):
        """parent が L1/L2/L3 に正しく対応していること。"""
        result = execute(VALID_INPUT)
        goals = result["expanded_goals"]
        l1_elems = [e for e in goals if e["parent"] == "L1"]
        l2_elems = [e for e in goals if e["parent"] == "L2"]
        l3_elems = [e for e in goals if e["parent"] == "L3"]
        assert len(l1_elems) == 1
        assert len(l2_elems) == 2
        assert len(l3_elems) == 3

    def test_l1_text_is_preserved(self):
        result = execute(VALID_INPUT)
        l1_elem = next(e for e in result["expanded_goals"] if e["parent"] == "L1")
        assert l1_elem["text"] == VALID_INPUT["goal"]["L1"]

    def test_all_required_fields_in_element(self):
        """各要素に element_id / text / parent が存在すること。"""
        result = execute(VALID_INPUT)
        required = {"element_id", "text", "parent"}
        for elem in result["expanded_goals"]:
            assert required <= elem.keys(), f"フィールド不足: {elem}"

    def test_empty_l2_l3_produces_only_l1(self):
        """L2/L3 が空リストの場合、L1 の1要素のみが展開されること。"""
        data = {"trace_id": "F10", "goal": {"L1": "大目的", "L2": [], "L3": []}}
        result = execute(data)
        assert len(result["expanded_goals"]) == 1
        assert result["expanded_goals"][0]["parent"] == "L1"


# ════════════════════════════════════════════════════════
# Test2 — 異常系：入力不正（型・None・空 dict・フィールド欠落）
# ════════════════════════════════════════════════════════

class TestInvalidInput:
    """不正な型入力に対して TypeError、欠落・型不正に対して ValueError が送出されることを検証する。"""

    @pytest.mark.parametrize("bad_input", INVALID_INPUTS)
    def test_raises_type_error(self, bad_input):
        """dict 以外の入力は TypeError。"""
        with pytest.raises(TypeError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_GOAL_INPUTS)
    def test_raises_value_error(self, bad_input):
        """goal 欠落・型不正・フィールド欠落は ValueError（ただし L1 空文字列は HITL 移譲）。"""
        # L1 空文字列ケースは Test3 で検証するため HITL 返却を許容
        result_or_exc = None
        try:
            result_or_exc = execute(bad_input)
        except (ValueError, TypeError):
            return  # 期待通り
        # HITL 移譲（L1 が空文字列）は許容
        if isinstance(result_or_exc, dict) and result_or_exc.get("hitl") is True:
            return
        pytest.fail(f"例外が送出されませんでした（返却値: {result_or_exc}）")

    def test_validate_input_none_raises_type_error(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input(None)

    def test_validate_input_empty_dict_raises_value_error(self):
        with pytest.raises(ValueError):
            _validate_input({})

    def test_validate_input_missing_goal_key(self):
        with pytest.raises(ValueError, match="goal"):
            _validate_input({"trace_id": "F10"})

    def test_validate_input_l1_not_str(self):
        with pytest.raises(ValueError, match="L1"):
            _validate_input({"goal": {"L1": 123, "L2": [], "L3": []}})

    def test_validate_input_l2_not_list(self):
        with pytest.raises(ValueError, match="L2"):
            _validate_input({"goal": {"L1": "大目的", "L2": "bad", "L3": []}})


# ════════════════════════════════════════════════════════
# Test3 — HITL移譲：空文字・曖昧語
# ════════════════════════════════════════════════════════

class TestHitlDelegation:
    """空文字列・曖昧語で HITL 移譲（hitl: True）が返ることを検証する。"""

    def test_empty_l1_triggers_hitl(self):
        data = {"trace_id": "F10", "goal": {"L1": "", "L2": [], "L3": []}}
        result = execute(data)
        assert result["hitl"] is True
        assert result["expanded_goals"] == []

    def test_whitespace_l1_triggers_hitl(self):
        data = {"trace_id": "F10", "goal": {"L1": "   ", "L2": [], "L3": []}}
        result = execute(data)
        assert result["hitl"] is True

    def test_ambiguous_word_triggers_hitl(self):
        data = {"trace_id": "F10", "goal": {"L1": "売上などを改善したい", "L2": [], "L3": []}}
        result = execute(data)
        assert result["hitl"] is True
        assert "HITL移譲" in result.get("hitl_reason", "")

    def test_hitl_reason_is_populated(self):
        data = {"trace_id": "F10", "goal": {"L1": "", "L2": [], "L3": []}}
        result = execute(data)
        assert "hitl_reason" in result
        assert result["hitl_reason"]  # 空でないこと

    def test_check_hitl_empty_string(self):
        reason = _check_hitl({"L1": "", "L2": [], "L3": []})
        assert reason == "Goal text is empty"

    def test_check_hitl_ambiguous(self):
        reason = _check_hitl({"L1": "売上などを上げたい", "L2": [], "L3": []})
        assert reason is not None and "HITL" in reason

    def test_check_hitl_normal_returns_none(self):
        assert _check_hitl({"L1": "売上を前年比120%に成長させる", "L2": [], "L3": []}) is None

    def test_trace_id_preserved_in_hitl_response(self):
        data = {"trace_id": "F10", "goal": {"L1": "", "L2": [], "L3": []}}
        result = execute(data)
        assert result["trace_id"] == "F20"
        assert result["source_trace_id"] == "F10"


# ════════════════════════════════════════════════════════
# Test4 — トークン化失敗：RuntimeError・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestTokenizationError:
    """トークン化処理（_expand_goals）が失敗した場合に RuntimeError が送出され、
    __cause__ に元の例外が保持されることを検証する。
    """

    def test_runtime_error_on_expansion_failure(self, mocker):
        mocker.patch(
            "src.agents.f20_module._expand_goals",
            side_effect=RuntimeError("トークン化失敗テスト"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_is_preserved_on_expansion_error(self, mocker):
        """_expand_goals が内部で例外を送出し RuntimeError にラップされることを検証。"""
        original_exc = ValueError("内部エラー")

        def _bad_expand(goal):
            try:
                raise original_exc
            except Exception as exc:
                wrapped = RuntimeError("目的展開処理（トークン化）に失敗しました")
                wrapped.__cause__ = exc
                raise wrapped from exc

        mocker.patch("src.agents.f20_module._expand_goals", side_effect=_bad_expand)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, ValueError, label="トークン化失敗")

    def test_expand_goals_direct_success(self):
        """_expand_goals が正常な goal を受け取り要素リストを返すことを単体検証。"""
        goal = {
            "L1": "大目的",
            "L2": ["中目的A", "中目的B"],
            "L3": ["小目的A-1"],
        }
        elements = _expand_goals(goal)
        assert len(elements) == 4
        assert elements[0]["parent"] == "L1"
        assert elements[1]["parent"] == "L2"
        assert elements[3]["parent"] == "L3"


# ════════════════════════════════════════════════════════
# Test5 — WARNING継続：重複要素・親子不整合
# ════════════════════════════════════════════════════════

class TestWarningContinuation:
    """重複要素・不正 parent・不明 trace_id が WARNING ログを出力し、処理継続することを検証する。"""

    def test_duplicate_element_id_logs_warning(self, caplog):
        """重複 element_id を持つ要素リストで Duplicate WARNING が出ることを検証。"""
        elements = [
            {"element_id": "E1", "text": "大目的", "parent": "L1"},
            {"element_id": "E1", "text": "重複要素", "parent": "L2"},  # 意図的に重複
        ]
        with caplog.at_level(logging.WARNING):
            _validate_elements(elements)
        assert_warning_contains(caplog.records, "重複", "Duplicate")

    def test_invalid_parent_logs_warning(self, caplog):
        """不正な parent 値（"L1"/"L2"/"L3" 以外）で ParentMismatch WARNING が出ることを検証。"""
        elements = [
            {"element_id": "E1", "text": "大目的", "parent": "L1"},
            {"element_id": "E2", "text": "孤立要素", "parent": "L4"},  # 不正な parent
        ]
        with caplog.at_level(logging.WARNING):
            _validate_elements(elements)
        assert_warning_contains(caplog.records, "不正な parent", "ParentMismatch")

    def test_duplicate_l2_element_logs_warning(self, caplog):
        """goal.L2 に重複要素が含まれる場合に Duplicate WARNING が出ることを検証。"""
        data = {
            "trace_id": "F10",
            "goal": {
                "L1": "大目的",
                "L2": ["中目的A", "中目的A"],  # 重複
                "L3": [],
            },
        }
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複", "DuplicateL2")

    def test_unknown_trace_id_logs_warning(self, caplog):
        """source trace_id が 'F10' 以外の場合に WARNING が出ることを検証。"""
        data = {
            "trace_id": "F99",  # 想定外
            "goal": VALID_INPUT["goal"],
        }
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_empty_l2_element_logs_warning(self, caplog):
        """goal.L2 に空文字列要素が含まれる場合に WARNING が出ることを検証。"""
        data = {
            "trace_id": "F10",
            "goal": {
                "L1": "大目的",
                "L2": ["中目的A", ""],  # 空文字列
                "L3": [],
            },
        }
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "空文字列", "EmptyElement")

    def test_processing_continues_after_warning(self, caplog):
        """WARNING 発生後も処理が継続し、正常に結果が返ることを検証。"""
        data = {
            "trace_id": "F10",
            "goal": {
                "L1": "大目的",
                "L2": ["中目的A", "中目的A"],  # 重複（WARNING を誘発）
                "L3": ["小目的"],
            },
        }
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F20"
        assert result["hitl"] is False
        assert len(result["expanded_goals"]) > 0


# ════════════════════════════════════════════════════════
# Test6 — trace_id="F20" の確認
# ════════════════════════════════════════════════════════

class TestTraceId:
    """出力の trace_id が常に 'F20' であることを、正常系・HITL系・各入力パターンで検証する。"""

    def test_normal_output_has_trace_id_f20(self):
        result = execute(VALID_INPUT)
        assert result["trace_id"] == "F20"

    def test_hitl_output_has_trace_id_f20(self):
        data = {"trace_id": "F10", "goal": {"L1": "", "L2": [], "L3": []}}
        result = execute(data)
        assert result["trace_id"] == "F20"

    def test_unknown_source_output_has_trace_id_f20(self, caplog):
        data = {"trace_id": "UNKNOWN", "goal": VALID_INPUT["goal"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F20"

    def test_source_trace_id_reflects_input(self):
        """source_trace_id が入力の trace_id を正確に反映すること。"""
        result = execute(VALID_INPUT)
        assert result["source_trace_id"] == "F10"

    def test_source_trace_id_when_missing(self, caplog):
        """入力に trace_id がない場合でも trace_id='F20' で返却されること。"""
        data = {"goal": VALID_INPUT["goal"]}  # trace_id なし
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F20"
        assert result["source_trace_id"] == ""
