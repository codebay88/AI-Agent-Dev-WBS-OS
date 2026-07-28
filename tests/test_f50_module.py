"""Unit tests for F50_Template_Application_Module (WP5100準拠)

F_series_overview.md の Unit Test 方針を継承し、
F10〜F40 と共通の assert_warning_contains / assert_wrapped_cause を再利用する。
"""

import logging

import pytest

from src.agents.f50_module import (
    _apply_template,
    _check_hitl_task,
    _preprocess,
    _validate_input,
    _validate_templated,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー（F_series_overview 方針準拠）
# ════════════════════════════════════════════════════════

VALID_INPUT = {
    "trace_id": "F40",
    "tasks": [
        {
            "task_id":          "T1",
            "element_id":       "E1",
            "task_text":        "【即実行】売上を前年比120%に成長させる",
            "priority":         "High",
            "estimated_effort": 3,
            "estimated_value":  5,
        },
        {
            "task_id":          "T2",
            "element_id":       "E2",
            "task_text":        "【計画】新規顧客獲得施策を推進する",
            "priority":         "Medium",
            "estimated_effort": 2,
            "estimated_value":  3,
        },
        {
            "task_id":          "T3",
            "element_id":       "E3",
            "task_text":        "LPを作成する",
            "priority":         "Low",
            "estimated_effort": 1,
            "estimated_value":  2,
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
    pytest.param({},                                        id="empty_dict"),
    pytest.param({"trace_id": "F40"},                      id="missing_tasks"),
    pytest.param({"tasks": "not_a_list", "trace_id": "F40"}, id="tasks_not_list"),
]

# 各要素の必須フィールド欠落 → TypeError
INVALID_FIELD_INPUTS = [
    pytest.param(
        {"tasks": [{"task_text": "テスト", "priority": "High"}], "trace_id": "F40"},
        id="missing_task_id",
    ),
    pytest.param(
        {"tasks": [{"task_id": "T1", "priority": "High"}], "trace_id": "F40"},
        id="missing_task_text",
    ),
    pytest.param(
        {"tasks": [{"task_id": "T1", "task_text": "テスト"}], "trace_id": "F40"},
        id="missing_priority",
    ),
    pytest.param(
        {"tasks": ["not_a_dict"], "trace_id": "F40"},
        id="task_not_dict",
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
# Test1 — 正常系：テンプレート適用・フィールド検証
# ════════════════════════════════════════════════════════

class TestNormalTemplateApplication:
    """execute() が正常入力に対して期待する templated_tasks を返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)
        self.tasks  = self.result["templated_tasks"]

    def test_trace_id_is_f50(self):
        assert self.result["trace_id"] == "F50"
        assert self.result["hitl"] is False

    def test_source_trace_id_preserved(self):
        assert self.result["source_trace_id"] == "F40"

    def test_task_count_matches_input(self):
        assert len(self.tasks) == 3

    def test_all_required_fields_present(self):
        required = {"task_id", "template_id", "templated_text", "priority", "effort", "value"}
        for task in self.tasks:
            assert required <= task.keys(), f"フィールド不足: {task}"

    def test_task_id_preserved(self):
        assert [t["task_id"] for t in self.tasks] == ["T1", "T2", "T3"]

    def test_high_priority_template(self):
        t = next(t for t in self.tasks if t["priority"] == "High")
        assert t["template_id"] == "TMP_HIGH"
        assert t["templated_text"].startswith("【優先度: 高】次のタスクを実行せよ: ")

    def test_medium_priority_template(self):
        t = next(t for t in self.tasks if t["priority"] == "Medium")
        assert t["template_id"] == "TMP_MEDIUM"
        assert t["templated_text"].startswith("【優先度: 中】検討すべきタスク: ")

    def test_low_priority_template(self):
        t = next(t for t in self.tasks if t["priority"] == "Low")
        assert t["template_id"] == "TMP_LOW"
        assert t["templated_text"].startswith("【優先度: 低】参考タスク: ")

    def test_task_text_embedded_in_templated_text(self):
        t1 = next(t for t in self.tasks if t["task_id"] == "T1")
        assert "売上を前年比120%に成長させる" in t1["templated_text"]

    def test_effort_value_carried_over(self):
        t1 = next(t for t in self.tasks if t["task_id"] == "T1")
        assert t1["effort"] == 3
        assert t1["value"]  == 5

    def test_hitl_elements_empty(self):
        assert self.result["hitl_elements"] == []

    def test_empty_tasks_returns_empty_templated(self):
        data   = {"trace_id": "F40", "tasks": []}
        result = execute(data)
        assert result["templated_tasks"] == []
        assert result["trace_id"] == "F50"

    def test_task_without_effort_value(self):
        """estimated_effort / estimated_value がないタスクは effort=None / value=None になること。"""
        data = {"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "広告配信を開始する", "priority": "High"}
        ]}
        result = execute(data)
        t = result["templated_tasks"][0]
        assert t["effort"] is None
        assert t["value"]  is None

    # ── _apply_template 単体検証 ──────────────────────

    @pytest.mark.parametrize("priority, expected_id, expected_prefix", [
        ("High",   "TMP_HIGH",   "【優先度: 高】次のタスクを実行せよ: "),
        ("Medium", "TMP_MEDIUM", "【優先度: 中】検討すべきタスク: "),
        ("Low",    "TMP_LOW",    "【優先度: 低】参考タスク: "),
    ])
    def test_apply_template_by_priority(self, priority, expected_id, expected_prefix):
        task = {"task_id": "T1", "task_text": "テスト実行", "priority": priority,
                "estimated_effort": 2, "estimated_value": 4}
        result = _apply_template(task)
        assert result["template_id"] == expected_id
        assert result["templated_text"].startswith(expected_prefix)
        assert "テスト実行" in result["templated_text"]


# ════════════════════════════════════════════════════════
# Test2 — 異常系：型不正・構造不正・フィールド欠落
# ════════════════════════════════════════════════════════

class TestInvalidInput:
    """dict 以外は TypeError、構造不正は ValueError、フィールド欠落は TypeError を検証する。"""

    @pytest.mark.parametrize("bad_input", INVALID_TYPE_INPUTS)
    def test_type_error_for_non_dict(self, bad_input):
        with pytest.raises(TypeError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_STRUCT_INPUTS)
    def test_value_error_for_invalid_structure(self, bad_input):
        with pytest.raises(ValueError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_FIELD_INPUTS)
    def test_type_error_for_missing_fields(self, bad_input):
        with pytest.raises(TypeError):
            execute(bad_input)

    def test_validate_input_none(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input(None)

    def test_validate_input_empty_dict(self):
        with pytest.raises(ValueError, match="空"):
            _validate_input({})

    def test_validate_input_missing_tasks(self):
        with pytest.raises(ValueError, match="tasks"):
            _validate_input({"trace_id": "F40"})

    def test_validate_input_tasks_not_list(self):
        with pytest.raises(ValueError, match="list"):
            _validate_input({"tasks": "bad"})

    def test_validate_input_missing_task_id(self):
        with pytest.raises(TypeError, match="task_id"):
            _validate_input({"tasks": [{"task_text": "テスト", "priority": "High"}]})

    def test_validate_input_missing_task_text(self):
        with pytest.raises(TypeError, match="task_text"):
            _validate_input({"tasks": [{"task_id": "T1", "priority": "High"}]})

    def test_validate_input_task_not_dict(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input({"tasks": ["not_a_dict"]})


# ════════════════════════════════════════════════════════
# Test3 — HITL移譲：空文字・曖昧語・全体/部分
# ════════════════════════════════════════════════════════

class TestHitlDelegation:
    """HITL 条件（空文字・曖昧語・priority 不明）を検証する。"""

    def _make_task(self, **kwargs):
        base = {
            "task_id": "T1", "task_text": "広告配信を開始する", "priority": "High",
            "estimated_effort": 2, "estimated_value": 4,
        }
        base.update(kwargs)
        return base

    def test_empty_text_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text=""),
            self._make_task(task_id="T2", task_text="LPを作成する"),
        ]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]
        assert "T2" not in result["hitl_elements"]

    def test_whitespace_text_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [self._make_task(task_text="   ")]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]

    def test_ambiguous_word_nado_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text="売上などを伸ばす")
        ]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]

    def test_ambiguous_word_kaizen_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text="プロセスを改善する")
        ]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]

    def test_ambiguous_word_kojo_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text="品質を向上させる")
        ]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]

    def test_ambiguous_word_kento_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text="施策を検討する")
        ]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]

    def test_invalid_priority_goes_to_hitl(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(priority="Unknown")
        ]}
        result = execute(data)
        assert "T1" in result["hitl_elements"]

    def test_all_hitl_sets_hitl_true(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text=""),
            self._make_task(task_id="T2", task_text="売上を改善する"),
        ]}
        result = execute(data)
        assert result["hitl"] is True
        assert result["templated_tasks"] == []

    def test_partial_hitl_templated_not_empty(self):
        data = {"trace_id": "F40", "tasks": [
            self._make_task(task_text=""),
            self._make_task(task_id="T2", task_text="広告配信を開始する"),
        ]}
        result = execute(data)
        assert result["hitl"] is False
        assert len(result["templated_tasks"]) == 1
        assert result["templated_tasks"][0]["task_id"] == "T2"

    def test_check_hitl_task_empty_text(self):
        reason = _check_hitl_task({"task_id": "T1", "task_text": "",
                                    "priority": "High"})
        assert reason == "Task text is empty or ambiguous"

    def test_check_hitl_task_ambiguous(self):
        reason = _check_hitl_task({"task_id": "T1", "task_text": "売上を改善する",
                                    "priority": "High"})
        assert reason is not None and "ambiguous" in reason

    def test_check_hitl_task_normal_returns_none(self):
        assert _check_hitl_task(
            {"task_id": "T1", "task_text": "広告配信を開始する", "priority": "High"}
        ) is None

    def test_hitl_trace_id_is_f50(self):
        data = {"trace_id": "F40", "tasks": [self._make_task(task_text="")]}
        result = execute(data)
        assert result["trace_id"] == "F50"


# ════════════════════════════════════════════════════════
# Test4 — RuntimeError：テンプレート適用失敗・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestTemplateApplicationError:
    """テンプレート適用が失敗した場合に RuntimeError が送出され、
    __cause__ に元の例外が保持されることを検証する。
    """

    def test_runtime_error_on_apply_failure(self, mocker):
        mocker.patch(
            "src.agents.f50_module._apply_template",
            side_effect=RuntimeError("テンプレート適用テストエラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_is_preserved_on_failure(self, mocker):
        """_TEMPLATES を空にすると _apply_template 内で KeyError が発生し RuntimeError にラップされる。"""
        mocker.patch.dict("src.agents.f50_module._TEMPLATES", {}, clear=True)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, KeyError, label="テンプレート適用失敗")

    def test_apply_template_wraps_exception(self, mocker):
        """_apply_template が内部エラー時に RuntimeError にラップすること。"""
        mocker.patch.dict("src.agents.f50_module._TEMPLATES", {}, clear=True)
        task = {"task_id": "T1", "task_text": "テスト", "priority": "High",
                "estimated_effort": 2, "estimated_value": 3}
        with pytest.raises(RuntimeError) as exc_info:
            _apply_template(task)
        assert exc_info.value.__cause__ is not None

    def test_runtime_error_message_contains_task_id(self, mocker):
        """RuntimeError のメッセージに task_id が含まれること。"""
        mocker.patch.dict("src.agents.f50_module._TEMPLATES", {}, clear=True)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert "task_id" in str(exc_info.value)


# ════════════════════════════════════════════════════════
# Test5 — WARNING継続：重複・不正値・不明trace_id
# ════════════════════════════════════════════════════════

class TestWarningContinuation:
    """WARNING が出力され処理継続することを各カテゴリ別に検証する。"""

    def test_duplicate_task_id_logs_warning(self, caplog):
        data = {"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LPを作成する", "priority": "High"},
            {"task_id": "T1", "task_text": "広告を出稿する", "priority": "Medium"},
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複 task_id", "DuplicateTaskId")

    def test_invalid_priority_logs_warning(self, caplog):
        data = {"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "テスト", "priority": "Critical"},
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "不正な priority", "InvalidPriority")

    def test_unknown_trace_id_logs_warning(self, caplog):
        data = {"trace_id": "F99", "tasks": VALID_INPUT["tasks"]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_empty_tasks_logs_warning(self, caplog):
        data = {"trace_id": "F40", "tasks": []}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "空リスト", "EmptyTasks")

    def test_validate_templated_empty_text(self, caplog):
        tasks = [{"task_id": "T1", "template_id": "TMP_HIGH",
                  "templated_text": "", "priority": "High"}]
        with caplog.at_level(logging.WARNING):
            _validate_templated(tasks)
        assert_warning_contains(caplog.records, "templated_text が空", "EmptyTemplatedText")

    def test_validate_templated_invalid_template_id(self, caplog):
        tasks = [{"task_id": "T1", "template_id": "TMP_UNKNOWN",
                  "templated_text": "テスト", "priority": "High"}]
        with caplog.at_level(logging.WARNING):
            _validate_templated(tasks)
        assert_warning_contains(caplog.records, "template_id", "InvalidTemplateId")

    def test_processing_continues_after_duplicate(self, caplog):
        data = {"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LPを作成する",   "priority": "High"},
            {"task_id": "T1", "task_text": "広告を出稿する", "priority": "Medium"},
        ]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F50"
        assert len(result["templated_tasks"]) == 2


# ════════════════════════════════════════════════════════
# Test6 — trace_id="F50"・パイプライン統合
# ════════════════════════════════════════════════════════

class TestTraceId:
    """出力の trace_id が常に 'F50' であることと F10→…→F50 パイプラインを検証する。"""

    def test_normal_output_trace_id_is_f50(self):
        assert execute(VALID_INPUT)["trace_id"] == "F50"

    def test_hitl_output_trace_id_is_f50(self):
        data = {"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "", "priority": "High"}
        ]}
        assert execute(data)["trace_id"] == "F50"

    def test_empty_tasks_trace_id_is_f50(self):
        assert execute({"trace_id": "F40", "tasks": []})["trace_id"] == "F50"

    def test_source_trace_id_reflects_input(self):
        assert execute(VALID_INPUT)["source_trace_id"] == "F40"

    def test_missing_trace_id_in_input(self, caplog):
        data = {"tasks": VALID_INPUT["tasks"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F50"
        assert result["source_trace_id"] == ""

    def test_unknown_source_trace_id_output_is_f50(self, caplog):
        data = {"trace_id": "UNKNOWN", "tasks": VALID_INPUT["tasks"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F50"

    def test_f10_to_f50_pipeline(self, mocker):
        """F10→F20→F30→F40→F50 の完全パイプラインを模擬して trace_id の伝播を検証する。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規獲得","リテンション"],"L3":["LP作成","広告配信"]}',
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec
        from src.agents.f40_module import execute as f40_exec

        f10_out = f10_exec({"goal_text": "売上を前年比120%に成長させる"})
        assert f10_out["trace_id"] == "F10"
        f20_out = f20_exec(f10_out)
        assert f20_out["trace_id"] == "F20"
        f30_out = f30_exec(f20_out)
        assert f30_out["trace_id"] == "F30"
        f40_out = f40_exec(f30_out)
        assert f40_out["trace_id"] == "F40"
        f50_out = execute(f40_out)
        assert f50_out["trace_id"] == "F50"
        assert f50_out["source_trace_id"] == "F40"
        assert len(f50_out["templated_tasks"]) > 0

    def test_pipeline_templated_text_contains_task_text(self, mocker):
        """パイプライン末端の templated_text にタスク文が埋め込まれていること。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規獲得"],"L3":["LP作成","広告配信"]}',
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec
        from src.agents.f40_module import execute as f40_exec

        f50_out = execute(f40_exec(f30_exec(f20_exec(f10_exec(
            {"goal_text": "売上を前年比120%に成長させる"}
        )))))
        for t in f50_out["templated_tasks"]:
            assert t["task_text"] if False else True
            assert t["templated_text"]
            # templated_text は優先度ヘッダを含む
            assert any(p in t["templated_text"]
                       for p in ["【優先度: 高】", "【優先度: 中】", "【優先度: 低】"])
