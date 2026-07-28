"""Unit tests for F40_Task_Generation_Module (WP5100準拠)

F_series_overview.md の Unit Test 方針を継承し、
F10〜F30 と共通の assert_warning_contains / assert_wrapped_cause を再利用する。
"""

import json
import logging

import pytest

from src.agents.f40_module import (
    _calc_effort,
    _calc_value,
    _check_hitl_element,
    _generate_task,
    _preprocess,
    _validate_input,
    _validate_tasks,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー（F_series_overview 方針準拠）
# ════════════════════════════════════════════════════════

VALID_INPUT = {
    "trace_id": "F30",
    "evaluated_goals": [
        {
            "element_id":       "E1",
            "text":             "売上を前年比120%に成長させる",
            "parent":           "L1",
            "score_importance": 0.85,
            "score_feasibility": 0.70,
            "priority":         "High",
        },
        {
            "element_id":       "E2",
            "text":             "新規顧客獲得施策を推進する",
            "parent":           "L2",
            "score_importance": 0.60,
            "score_feasibility": 0.80,
            "priority":         "Medium",
        },
        {
            "element_id":       "E3",
            "text":             "LPを作成する",
            "parent":           "L3",
            "score_importance": 0.40,
            "score_feasibility": 0.90,
            "priority":         "Low",
        },
    ],
}

# dict 以外 → TypeError
INVALID_TYPE_INPUTS = [
    pytest.param(None,     id="none"),
    pytest.param("string", id="string"),
    pytest.param(42,       id="int"),
    pytest.param([],       id="list"),
]

# dict だが構造不正 → ValueError
INVALID_STRUCT_INPUTS = [
    pytest.param({},                                                               id="empty_dict"),
    pytest.param({"trace_id": "F30"},                                              id="missing_evaluated_goals"),
    pytest.param({"evaluated_goals": "not_a_list", "trace_id": "F30"},            id="goals_not_list"),
    pytest.param(
        {"evaluated_goals": [{"priority": "High", "score_importance": 0.8,
                              "score_feasibility": 0.7}], "trace_id": "F30"},
        id="missing_element_id",
    ),
    pytest.param(
        {"evaluated_goals": [{"element_id": "E1", "score_importance": 0.8,
                              "score_feasibility": 0.7}], "trace_id": "F30"},
        id="missing_priority",
    ),
    pytest.param(
        {"evaluated_goals": [{"element_id": "E1", "priority": "High",
                              "score_feasibility": 0.7}], "trace_id": "F30"},
        id="missing_score_importance",
    ),
    pytest.param(
        {"evaluated_goals": [{"element_id": "E1", "priority": "High",
                              "score_importance": 0.8}], "trace_id": "F30"},
        id="missing_score_feasibility",
    ),
    pytest.param(
        {"evaluated_goals": ["not_a_dict"], "trace_id": "F30"},
        id="element_not_dict",
    ),
]


def assert_warning_contains(caplog_records, keyword: str, category: str) -> None:
    """F_series_overview 共通ヘルパー: WARNING ログにキーワードが含まれることを検証。"""
    matched = [r for r in caplog_records if keyword in r.message and r.levelno == logging.WARNING]
    assert matched, (
        f"WARNING [{category}] が見つかりません（keyword='{keyword}'）\n"
        f"実際の WARNING: {[r.message for r in caplog_records if r.levelno == logging.WARNING]}"
    )


def assert_wrapped_cause(exc_info, expected_cause_type, label: str = "") -> None:
    """F_series_overview 共通ヘルパー: RuntimeError.__cause__ の型を検証。"""
    cause = exc_info.value.__cause__
    assert cause is not None, f"[{label}] __cause__ が None です"
    assert isinstance(cause, expected_cause_type), (
        f"[{label}] __cause__ の型: expected={expected_cause_type.__name__}, "
        f"actual={type(cause).__name__}"
    )


# ════════════════════════════════════════════════════════
# Test1 — 正常系：タスク生成・スコア算出・priority プレフィックス
# ════════════════════════════════════════════════════════

class TestNormalTaskGeneration:
    """execute() が正常入力に対して期待するタスクリストを返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)
        self.tasks  = self.result["tasks"]

    def test_trace_id_is_f40(self):
        assert self.result["trace_id"] == "F40"
        assert self.result["hitl"] is False

    def test_source_trace_id_preserved(self):
        assert self.result["source_trace_id"] == "F30"

    def test_task_count_matches_input(self):
        """HITL なしの場合、入力と同数のタスクが生成されること。"""
        assert len(self.tasks) == 3

    def test_task_id_sequential(self):
        """task_id が T1 から連番で付与されること。"""
        assert [t["task_id"] for t in self.tasks] == ["T1", "T2", "T3"]

    def test_element_id_preserved(self):
        """element_id が入力から正しく引き継がれること。"""
        assert [t["element_id"] for t in self.tasks] == ["E1", "E2", "E3"]

    def test_all_required_fields_present(self):
        required = {"task_id", "element_id", "task_text", "priority", "estimated_effort", "estimated_value"}
        for task in self.tasks:
            assert required <= task.keys(), f"フィールド不足: {task}"

    def test_effort_in_valid_range(self):
        for task in self.tasks:
            assert 1 <= task["estimated_effort"] <= 5, f"effort 範囲外: {task}"

    def test_value_in_valid_range(self):
        for task in self.tasks:
            assert 1 <= task["estimated_value"] <= 5, f"value 範囲外: {task}"

    def test_high_priority_prefix(self):
        high_task = next(t for t in self.tasks if t["priority"] == "High")
        assert high_task["task_text"].startswith("【即実行】")

    def test_medium_priority_prefix(self):
        mid_task = next(t for t in self.tasks if t["priority"] == "Medium")
        assert mid_task["task_text"].startswith("【計画】")

    def test_low_priority_prefix(self):
        low_task = next(t for t in self.tasks if t["priority"] == "Low")
        assert low_task["task_text"].startswith("【検討】")

    def test_high_importance_yields_high_value(self):
        """importance=0.85（E1）の value が importance=0.40（E3）より高いこと。"""
        e1 = next(t for t in self.tasks if t["element_id"] == "E1")
        e3 = next(t for t in self.tasks if t["element_id"] == "E3")
        assert e1["estimated_value"] > e3["estimated_value"]

    def test_high_feasibility_yields_low_effort(self):
        """feasibility=0.90（E3）の effort が feasibility=0.70（E1）より低いこと。"""
        e1 = next(t for t in self.tasks if t["element_id"] == "E1")
        e3 = next(t for t in self.tasks if t["element_id"] == "E3")
        assert e3["estimated_effort"] < e1["estimated_effort"]

    def test_hitl_elements_empty(self):
        assert self.result["hitl_elements"] == []

    def test_empty_evaluated_goals_returns_empty_tasks(self):
        data   = {"trace_id": "F30", "evaluated_goals": []}
        result = execute(data)
        assert result["tasks"] == []
        assert result["trace_id"] == "F40"

    # ── スコア算出ロジック単体検証 ──────────────────────

    @pytest.mark.parametrize("feasibility, expected_effort", [
        (1.00, 1),   # 最大 feasibility → 最小 effort
        (0.75, 2),
        (0.50, 3),
        (0.25, 4),
        (0.00, 5),   # 最小 feasibility → 最大 effort
    ])
    def test_calc_effort_formula(self, feasibility, expected_effort):
        assert _calc_effort(feasibility) == expected_effort

    @pytest.mark.parametrize("importance, expected_value", [
        (1.00, 5),   # 最大 importance → 最大 value
        (0.75, 4),
        (0.50, 3),
        (0.25, 2),
        (0.00, 1),   # 最小 importance → 最小 value
    ])
    def test_calc_value_formula(self, importance, expected_value):
        assert _calc_value(importance) == expected_value

    def test_generate_task_without_text_field(self):
        """text フィールドが存在しない場合、element_id をベースにタスク文を生成すること。"""
        elem = {
            "element_id":        "E9",
            "priority":          "High",
            "score_importance":  0.80,
            "score_feasibility": 0.60,
        }
        task = _generate_task(elem, "T9")
        assert task["task_text"].startswith("【即実行】")
        assert "E9" in task["task_text"]


# ════════════════════════════════════════════════════════
# Test2 — 異常系：型不正・構造不正・フィールド欠落
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

    def test_validate_input_missing_evaluated_goals(self):
        with pytest.raises(ValueError, match="evaluated_goals"):
            _validate_input({"trace_id": "F30"})

    def test_validate_input_goals_not_list(self):
        with pytest.raises(ValueError, match="list"):
            _validate_input({"evaluated_goals": "bad"})

    def test_validate_input_missing_element_id(self):
        with pytest.raises(ValueError, match="element_id"):
            _validate_input({"evaluated_goals": [
                {"priority": "High", "score_importance": 0.8, "score_feasibility": 0.7}
            ]})

    def test_validate_input_missing_priority(self):
        with pytest.raises(ValueError, match="priority"):
            _validate_input({"evaluated_goals": [
                {"element_id": "E1", "score_importance": 0.8, "score_feasibility": 0.7}
            ]})

    def test_validate_input_element_not_dict(self):
        with pytest.raises(ValueError, match="dict"):
            _validate_input({"evaluated_goals": ["not_a_dict"]})


# ════════════════════════════════════════════════════════
# Test3 — HITL移譲：空文字・曖昧語・全体/部分
# ════════════════════════════════════════════════════════

class TestHitlDelegation:
    """HITL 条件（空文字・曖昧語・priority 不明・スコア極端に曖昧）を検証する。"""

    def _make_elem(self, **kwargs):
        base = {
            "element_id": "E1", "priority": "High",
            "score_importance": 0.80, "score_feasibility": 0.70,
        }
        base.update(kwargs)
        return base

    def test_empty_text_goes_to_hitl(self):
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(text=""),
            {**self._make_elem(element_id="E2", text="LPを作成する")},
        ]}
        result = execute(data)
        assert "E1" in result["hitl_elements"]
        assert "E2" not in result["hitl_elements"]

    def test_whitespace_text_goes_to_hitl(self):
        data = {"trace_id": "F30", "evaluated_goals": [self._make_elem(text="   ")]}
        result = execute(data)
        assert "E1" in result["hitl_elements"]

    def test_ambiguous_word_goes_to_hitl(self):
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(text="売上などを改善したい")
        ]}
        result = execute(data)
        assert "E1" in result["hitl_elements"]

    def test_invalid_priority_goes_to_hitl(self):
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(priority="Unknown")
        ]}
        result = execute(data)
        assert "E1" in result["hitl_elements"]

    def test_ambiguous_scores_goes_to_hitl(self):
        """importance=0.30 / feasibility=0.30（差 0.0 ≤ 0.05）で HITL 移譲。"""
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(score_importance=0.30, score_feasibility=0.30)
        ]}
        result = execute(data)
        assert "E1" in result["hitl_elements"]

    def test_all_elements_hitl_sets_hitl_true(self):
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(text=""),
            self._make_elem(element_id="E2", text="売上など"),
        ]}
        result = execute(data)
        assert result["hitl"] is True
        assert result["tasks"] == []

    def test_partial_hitl_tasks_not_empty(self):
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(text=""),
            self._make_elem(element_id="E2", text="LPを作成する"),
        ]}
        result = execute(data)
        assert result["hitl"] is False
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["element_id"] == "E2"

    def test_task_id_skips_hitl_elements(self):
        """HITL 要素をスキップして task_id が T1 から連番になること。"""
        data = {"trace_id": "F30", "evaluated_goals": [
            self._make_elem(text=""),              # HITL → スキップ
            self._make_elem(element_id="E2", text="LPを作成する"),   # T1
            self._make_elem(element_id="E3", text="広告配信を開始する"),  # T2
        ]}
        result = execute(data)
        task_ids = [t["task_id"] for t in result["tasks"]]
        assert task_ids == ["T1", "T2"]

    def test_check_hitl_element_empty_text(self):
        assert _check_hitl_element({"element_id": "E1", "text": "",
                                     "priority": "High", "score_importance": 0.8,
                                     "score_feasibility": 0.7}) == "Goal element text is empty"

    def test_check_hitl_element_ambiguous(self):
        reason = _check_hitl_element({"element_id": "E1", "text": "売上などを上げたい",
                                       "priority": "High", "score_importance": 0.8,
                                       "score_feasibility": 0.7})
        assert reason is not None and "HITL" in reason

    def test_check_hitl_element_normal_returns_none(self):
        assert _check_hitl_element({
            "element_id": "E1", "text": "LPを作成する", "priority": "High",
            "score_importance": 0.8, "score_feasibility": 0.7,
        }) is None

    def test_hitl_reason_in_result(self):
        """全体 HITL 時も trace_id='F40' で返ること。"""
        data = {"trace_id": "F30", "evaluated_goals": [
            {"element_id": "E1", "text": "", "priority": "High",
             "score_importance": 0.8, "score_feasibility": 0.7}
        ]}
        result = execute(data)
        assert result["trace_id"] == "F40"
        assert result["hitl"] is True


# ════════════════════════════════════════════════════════
# Test4 — RuntimeError：タスク生成失敗・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestTaskGenerationError:
    """タスク生成処理が失敗した場合に RuntimeError が送出され、
    __cause__ に元の例外が保持されることを検証する。
    """

    def test_runtime_error_on_generate_failure(self, mocker):
        mocker.patch(
            "src.agents.f40_module._generate_task",
            side_effect=RuntimeError("タスク生成テストエラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_is_preserved_on_failure(self, mocker):
        original = ValueError("内部タスク生成エラー")
        mocker.patch("src.agents.f40_module._calc_effort", side_effect=original)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, ValueError, label="タスク生成失敗")

    def test_generate_task_wraps_exception(self, mocker):
        """_generate_task が _calc_effort 失敗時に RuntimeError にラップすること。"""
        mocker.patch("src.agents.f40_module._calc_effort", side_effect=ZeroDivisionError("err"))
        elem = {
            "element_id": "E1", "text": "テスト", "priority": "High",
            "score_importance": 0.8, "score_feasibility": 0.7,
        }
        with pytest.raises(RuntimeError) as exc_info:
            _generate_task(elem, "T1")
        assert_wrapped_cause(exc_info, ZeroDivisionError, label="_generate_task ラップ")

    def test_runtime_error_message_contains_element_id(self, mocker):
        mocker.patch("src.agents.f40_module._calc_effort", side_effect=ValueError("err"))
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert "element_id" in str(exc_info.value)


# ════════════════════════════════════════════════════════
# Test5 — WARNING継続：重複・範囲外・不正値
# ════════════════════════════════════════════════════════

class TestWarningContinuation:
    """WARNING が出力され処理継続することを Duplicate / ScoreRange / Priority / TraceId 別に検証する。"""

    def test_duplicate_element_id_logs_warning(self, caplog):
        data = {"trace_id": "F30", "evaluated_goals": [
            {"element_id": "E1", "text": "大目的", "priority": "High",
             "score_importance": 0.8, "score_feasibility": 0.7},
            {"element_id": "E1", "text": "重複", "priority": "Medium",  # 重複
             "score_importance": 0.6, "score_feasibility": 0.8},
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複", "Duplicate")

    def test_score_out_of_range_logs_warning(self, caplog):
        data = {"trace_id": "F30", "evaluated_goals": [
            {"element_id": "E1", "text": "テスト", "priority": "High",
             "score_importance": 1.5,   # 範囲外
             "score_feasibility": 0.7},
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "スコア範囲外", "ScoreRange")

    def test_invalid_priority_logs_warning(self, caplog):
        data = {"trace_id": "F30", "evaluated_goals": [
            {"element_id": "E1", "text": "テスト", "priority": "Critical",  # 不正
             "score_importance": 0.8, "score_feasibility": 0.7},
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "不正な priority", "InvalidPriority")

    def test_unknown_trace_id_logs_warning(self, caplog):
        data = {"trace_id": "F99", "evaluated_goals": VALID_INPUT["evaluated_goals"]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_empty_goals_logs_warning(self, caplog):
        data = {"trace_id": "F30", "evaluated_goals": []}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "空リスト", "EmptyGoals")

    def test_validate_tasks_out_of_range_effort(self, caplog):
        """_validate_tasks が範囲外 effort で WARNING を出すこと。"""
        tasks = [{"task_id": "T1", "estimated_effort": 9,
                  "estimated_value": 3, "priority": "High"}]
        with caplog.at_level(logging.WARNING):
            _validate_tasks(tasks)
        assert_warning_contains(caplog.records, "スコア範囲外", "TaskScoreRange")

    def test_validate_tasks_duplicate_task_id(self, caplog):
        tasks = [
            {"task_id": "T1", "estimated_effort": 2, "estimated_value": 4, "priority": "High"},
            {"task_id": "T1", "estimated_effort": 3, "estimated_value": 3, "priority": "Medium"},
        ]
        with caplog.at_level(logging.WARNING):
            _validate_tasks(tasks)
        assert_warning_contains(caplog.records, "重複 task_id", "DuplicateTaskId")

    def test_processing_continues_after_warning(self, caplog):
        data = {"trace_id": "F30", "evaluated_goals": [
            {"element_id": "E1", "text": "大目的", "priority": "High",
             "score_importance": 0.8, "score_feasibility": 0.7},
            {"element_id": "E1", "text": "重複",   "priority": "Low",
             "score_importance": 0.4, "score_feasibility": 0.9},
        ]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F40"
        assert len(result["tasks"]) == 2


# ════════════════════════════════════════════════════════
# Test6 — trace_id="F40"・パイプライン統合
# ════════════════════════════════════════════════════════

class TestTraceId:
    """出力の trace_id が常に 'F40' であることと F10→F20→F30→F40 パイプラインを検証する。"""

    def test_normal_output_trace_id_is_f40(self):
        assert execute(VALID_INPUT)["trace_id"] == "F40"

    def test_hitl_output_trace_id_is_f40(self):
        data = {"trace_id": "F30", "evaluated_goals": [
            {"element_id": "E1", "text": "", "priority": "High",
             "score_importance": 0.8, "score_feasibility": 0.7}
        ]}
        assert execute(data)["trace_id"] == "F40"

    def test_empty_goals_trace_id_is_f40(self):
        assert execute({"trace_id": "F30", "evaluated_goals": []})["trace_id"] == "F40"

    def test_source_trace_id_reflects_input(self):
        assert execute(VALID_INPUT)["source_trace_id"] == "F30"

    def test_missing_trace_id_in_input(self, caplog):
        data = {"evaluated_goals": VALID_INPUT["evaluated_goals"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F40"
        assert result["source_trace_id"] == ""

    def test_unknown_source_trace_id_output_is_f40(self, caplog):
        data = {"trace_id": "UNKNOWN", "evaluated_goals": VALID_INPUT["evaluated_goals"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F40"

    def test_f10_to_f20_to_f30_to_f40_pipeline(self, mocker):
        """F10→F20→F30→F40 の完全パイプラインを模擬して trace_id の伝播を検証する。"""
        # F10 出力を模擬（API モック）
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規獲得","リテンション"],"L3":["LP作成","広告配信"]}',
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec

        f10_out = f10_exec({"goal_text": "売上を前年比120%に成長させる"})
        assert f10_out["trace_id"] == "F10"

        f20_out = f20_exec(f10_out)
        assert f20_out["trace_id"] == "F20"

        f30_out = f30_exec(f20_out)
        assert f30_out["trace_id"] == "F30"

        f40_out = execute(f30_out)
        assert f40_out["trace_id"] == "F40"
        assert f40_out["source_trace_id"] == "F30"
        assert len(f40_out["tasks"]) > 0

    def test_pipeline_task_ids_are_sequential(self, mocker):
        """パイプライン末端の task_id が T1 から連番であること。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規獲得"],"L3":["LP作成","広告配信"]}',
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec

        f40_out = execute(f30_exec(f20_exec(f10_exec({"goal_text": "売上を前年比120%に成長させる"}))))
        ids = [t["task_id"] for t in f40_out["tasks"]]
        assert ids == [f"T{i}" for i in range(1, len(ids) + 1)]
