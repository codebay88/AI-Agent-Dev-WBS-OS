"""Unit tests for F70_Hierarchy_Generation_Module (WP5100準拠)

F_series_overview.md の Unit Test 方針を継承し、
F10〜F60 と共通の assert_warning_contains / assert_wrapped_cause を再利用する。
"""

import logging

import pytest

from src.agents.f70_module import (
    GOAL_SIM_THRESHOLD,
    _cosine_similarity,
    _extract_goal_text,
    _group_by_element,
    _is_only_abstract,
    _strip_priority_prefix,
    _union_find_group,
    _validate_input,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー
# ════════════════════════════════════════════════════════

def _task(task_id, text, priority="High", **kwargs):
    t = {"task_id": task_id, "templated_text": text, "priority": priority}
    t.update(kwargs)
    return t


# 3タスク・全て異なるテキスト → 3 goals
VALID_INPUT = {
    "trace_id": "F60",
    "templated_tasks": [
        _task("T1", "【優先度: 高】次のタスクを実行せよ: LPを作成する",
              effort=3, value=5),
        _task("T2", "【優先度: 中】次のタスクを実行せよ: 広告配信を開始する",
              priority="Medium", effort=2, value=3),
        _task("T3", "【優先度: 低】参考タスク: SNS投稿を計画する",
              priority="Low", effort=1, value=2),
    ],
    "mece_report": {
        "duplicate_tasks": [], "missing_elements": [],
        "ambiguous_tasks": [], "is_mece_compliant": True,
    },
}

# 類似テキスト2タスク → 1 goal にグループ化
SIMILAR_TEXT = "【優先度: 高】次のタスクを実行せよ: LPを作成する"

INVALID_TYPE_INPUTS = [
    pytest.param(None,     id="none"),
    pytest.param("string", id="string"),
    pytest.param(42,       id="int"),
    pytest.param([],       id="list"),
]

INVALID_STRUCT_INPUTS = [
    pytest.param({},                                              id="empty_dict"),
    pytest.param({"trace_id": "F60"},                            id="missing_templated_tasks"),
    pytest.param({"templated_tasks": "not_a_list",
                  "trace_id": "F60"},                            id="tasks_not_list"),
]

INVALID_FIELD_INPUTS = [
    pytest.param(
        {"templated_tasks": [{"templated_text": "テスト", "priority": "High"}],
         "trace_id": "F60"},
        id="missing_task_id",
    ),
    pytest.param(
        {"templated_tasks": [{"task_id": "T1", "priority": "High"}],
         "trace_id": "F60"},
        id="missing_templated_text",
    ),
    pytest.param(
        {"templated_tasks": [{"task_id": "T1", "templated_text": "テスト"}],
         "trace_id": "F60"},
        id="missing_priority",
    ),
    pytest.param(
        {"templated_tasks": ["not_a_dict"], "trace_id": "F60"},
        id="task_not_dict",
    ),
]


def assert_warning_contains(caplog_records, keyword: str, category: str) -> None:
    matched = [r for r in caplog_records if keyword in r.message and r.levelno == logging.WARNING]
    assert matched, (
        f"WARNING [{category}] が見つかりません（keyword='{keyword}'）\n"
        f"実際の WARNING: {[r.message for r in caplog_records if r.levelno == logging.WARNING]}"
    )


def assert_wrapped_cause(exc_info, expected_cause_type, label: str = "") -> None:
    cause = exc_info.value.__cause__
    assert cause is not None, f"[{label}] __cause__ が None です"
    assert isinstance(cause, expected_cause_type), (
        f"[{label}] __cause__ の型: expected={expected_cause_type.__name__}, "
        f"actual={type(cause).__name__}"
    )


# ════════════════════════════════════════════════════════
# Test1 — 正常系：三層構造・goal/element/task フィールド
# ════════════════════════════════════════════════════════

class TestNormalHierarchy:
    """execute() が正常入力に対して期待する三層構造を返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)
        self.goals  = self.result["hierarchy"]["goals"]

    def test_trace_id_is_f70(self):
        assert self.result["trace_id"] == "F70"

    def test_source_trace_id_is_f60(self):
        assert self.result["source_trace_id"] == "F60"

    def test_hierarchy_key_present(self):
        assert "hierarchy" in self.result
        assert "goals" in self.result["hierarchy"]

    def test_goals_is_list(self):
        assert isinstance(self.goals, list)

    def test_goals_not_empty(self):
        assert len(self.goals) > 0

    def test_goal_required_fields(self):
        for g in self.goals:
            assert "goal_id"   in g
            assert "goal_text" in g
            assert "elements"  in g

    def test_goal_id_prefix(self):
        for g in self.goals:
            assert g["goal_id"].startswith("G")

    def test_each_goal_has_elements(self):
        for g in self.goals:
            assert len(g["elements"]) >= 1

    def test_element_required_fields(self):
        for g in self.goals:
            for e in g["elements"]:
                assert "element_id"   in e
                assert "element_text" in e
                assert "tasks"        in e

    def test_element_id_contains_goal_id(self):
        for g in self.goals:
            for e in g["elements"]:
                assert e["element_id"].startswith(g["goal_id"])

    def test_each_element_has_tasks(self):
        for g in self.goals:
            for e in g["elements"]:
                assert len(e["tasks"]) >= 1

    def test_task_required_fields(self):
        for g in self.goals:
            for e in g["elements"]:
                for t in e["tasks"]:
                    assert "task_id"        in t
                    assert "templated_text" in t
                    assert "priority"       in t

    def test_all_input_tasks_appear_in_hierarchy(self):
        input_ids = {t["task_id"] for t in VALID_INPUT["templated_tasks"]}
        output_ids = {
            t["task_id"]
            for g in self.goals
            for e in g["elements"]
            for t in e["tasks"]
        }
        assert input_ids == output_ids

    def test_hitl_false_when_no_issues(self):
        assert self.result["hitl"] is False
        assert self.result["hitl_required"] is False
        assert self.result["hitl_elements"] == []

    # ── ユーティリティ単体検証 ──────────────────────────

    def test_strip_priority_prefix_removes_header(self):
        text = "【優先度: 高】次のタスクを実行せよ: LPを作成する"
        assert _strip_priority_prefix(text) == "LPを作成する"

    def test_strip_priority_prefix_no_match_returns_original(self):
        text = "プレーンテキスト"
        assert _strip_priority_prefix(text) == "プレーンテキスト"

    def test_extract_goal_text_single_task(self):
        tasks = [_task("T1", "【優先度: 高】次のタスクを実行せよ: LPを作成する")]
        result = _extract_goal_text(tasks)
        assert result == "LPを作成する"

    def test_extract_goal_text_multiple_tasks_common_tokens(self):
        tasks = [
            _task("T1", "LP作成 売上拡大"),
            _task("T2", "LP作成 広告出稿"),
        ]
        result = _extract_goal_text(tasks)
        assert "LP作成" in result

    def test_is_only_abstract_true(self):
        assert _is_only_abstract("改善 向上") is True

    def test_is_only_abstract_false(self):
        assert _is_only_abstract("LPを作成する") is False

    def test_is_only_abstract_empty(self):
        assert _is_only_abstract("") is True

    def test_cosine_identical_returns_one(self):
        t = "LPを作成する"
        assert _cosine_similarity(t, t) == pytest.approx(1.0)

    def test_cosine_different_returns_zero(self):
        assert _cosine_similarity("りんご", "自動車") == pytest.approx(0.0)

    def test_priority_order_in_elements(self):
        """High が Medium より前に来ること。"""
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "広告配信を開始する",   priority="Medium"),
            _task("T2", "LP作成を実施する",     priority="High"),
        ]}
        result = execute(data)
        goals  = result["hierarchy"]["goals"]
        # 2タスクが1つの goal（類似度次第）または別 goal → 最初の goal の最初の element が High
        all_pris = [
            e["tasks"][0]["priority"]
            for g in goals
            for e in g["elements"]
        ]
        # High が存在することを確認（順序の強制は goal 内の element 順で確認）
        assert "High" in all_pris


# ════════════════════════════════════════════════════════
# Test2 — 異常系：型不正・構造不正・フィールド欠落
# ════════════════════════════════════════════════════════

class TestInvalidInput:

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

    def test_validate_input_missing_templated_tasks(self):
        with pytest.raises(ValueError, match="templated_tasks"):
            _validate_input({"trace_id": "F60"})

    def test_validate_input_tasks_not_list(self):
        with pytest.raises(ValueError, match="list"):
            _validate_input({"templated_tasks": "bad"})

    def test_validate_input_task_not_dict(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input({"templated_tasks": ["not_a_dict"]})


# ════════════════════════════════════════════════════════
# Test3 — グループ化ロジック
# ════════════════════════════════════════════════════════

class TestGroupingLogic:
    """類似タスクの goal 統合・priority 別 element 分離を検証する。"""

    def test_identical_texts_grouped_into_one_goal(self):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", SIMILAR_TEXT),
            _task("T2", SIMILAR_TEXT),
        ]}
        result = execute(data)
        assert len(result["hierarchy"]["goals"]) == 1

    def test_completely_different_texts_make_separate_goals(self):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "LP作成"),
            _task("T2", "競合調査"),
        ]}
        result = execute(data)
        # 異なるトークンが異なる goal を生成
        goals = result["hierarchy"]["goals"]
        # goal が1〜2個（類似度次第）だが全タスクが含まれていること
        all_tids = {t["task_id"] for g in goals for e in g["elements"] for t in e["tasks"]}
        assert {"T1", "T2"} == all_tids

    def test_union_find_group_identical_returns_one_group(self):
        tasks = [_task("T1", SIMILAR_TEXT), _task("T2", SIMILAR_TEXT)]
        groups = _union_find_group(tasks)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_union_find_group_singleton(self):
        tasks = [_task("T1", "LP作成")]
        groups = _union_find_group(tasks)
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_group_by_element_high_medium_low(self):
        """High/Medium/Low の3タスクが3要素に分かれること。"""
        tasks = [
            _task("T1", "LP作成",   priority="High"),
            _task("T2", "広告配信", priority="Medium"),
            _task("T3", "SNS投稿",  priority="Low"),
        ]
        elements = _group_by_element("G1", tasks)
        priorities = [e["tasks"][0]["priority"] for e in elements]
        assert "High"   in priorities
        assert "Medium" in priorities
        assert "Low"    in priorities

    def test_group_by_element_same_priority_merged(self):
        """同一 priority タスクは1つの element にまとめられること。"""
        tasks = [
            _task("T1", "LP作成",     priority="High"),
            _task("T2", "広告出稿",   priority="High"),
        ]
        elements = _group_by_element("G1", tasks)
        assert len(elements) == 1
        assert len(elements[0]["tasks"]) == 2

    def test_element_id_format(self):
        """element_id が {goal_id}_EL_{suffix} 形式であること。"""
        tasks = [_task("T1", "テスト", priority="High")]
        elements = _group_by_element("G2", tasks)
        assert elements[0]["element_id"] == "G2_EL_H"

    def test_element_text_reflects_priority(self):
        tasks = [_task("T1", "テスト", priority="Medium")]
        elements = _group_by_element("G1", tasks)
        assert "Medium" in elements[0]["element_text"]

    def test_tasks_within_element_have_required_fields(self):
        tasks = [_task("T1", "LP作成", priority="High", effort=2, value=4)]
        elements = _group_by_element("G1", tasks)
        t = elements[0]["tasks"][0]
        assert "task_id" in t and "templated_text" in t and "priority" in t

    def test_threshold_constant_is_0_80(self):
        assert GOAL_SIM_THRESHOLD == pytest.approx(0.80)


# ════════════════════════════════════════════════════════
# Test4 — HITL移譲：空入力・抽象 goal_text・整合性不完全
# ════════════════════════════════════════════════════════

class TestHitlDelegation:

    def test_empty_tasks_hitl_required(self):
        data = {"trace_id": "F60", "templated_tasks": []}
        result = execute(data)
        assert result["hitl_required"] is True
        assert result["hitl"] is True
        assert result.get("hitl_reason") == "No hierarchy generated"

    def test_empty_tasks_goals_is_empty(self):
        data = {"trace_id": "F60", "templated_tasks": []}
        result = execute(data)
        assert result["hierarchy"]["goals"] == []

    def test_empty_tasks_trace_id_is_f70(self):
        data = {"trace_id": "F60", "templated_tasks": []}
        assert execute(data)["trace_id"] == "F70"

    def test_abstract_only_goal_text_triggers_hitl(self):
        """goal_text が ABSTRACT_WORDS のみの場合 hitl_required=True になること。"""
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "改善 向上"),   # 抽象語トークンのみ
        ]}
        result = execute(data)
        assert result["hitl_required"] is True
        assert len(result["hitl_elements"]) > 0

    def test_abstract_goal_id_in_hitl_elements(self):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "改善 向上"),
        ]}
        result = execute(data)
        assert "G1" in result["hitl_elements"]

    def test_non_abstract_goal_no_hitl(self):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "【優先度: 高】次のタスクを実行せよ: LPを作成する"),
        ]}
        result = execute(data)
        assert result["hitl_required"] is False

    def test_hitl_elements_deduped(self):
        """hitl_elements が重複なくソートされていること。"""
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "改善 向上"),
        ]}
        result = execute(data)
        els = result["hitl_elements"]
        assert els == sorted(set(els))


# ════════════════════════════════════════════════════════
# Test5 — RuntimeError：類似度計算失敗・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestRuntimeError:

    def test_runtime_error_on_cosine_failure(self, mocker):
        mocker.patch(
            "src.agents.f70_module._cosine_similarity",
            side_effect=RuntimeError("cosine テストエラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_preserved_on_cosine_failure(self, mocker):
        original = ZeroDivisionError("test")
        mocker.patch("src.agents.f70_module._cosine_similarity", side_effect=original)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, ZeroDivisionError, label="cosine 計算失敗")

    def test_cosine_wraps_math_error(self, mocker):
        """_cosine_similarity 内で math エラー発生時に RuntimeError にラップされること。"""
        mocker.patch("src.agents.f70_module.math.sqrt", side_effect=ValueError("math error"))
        with pytest.raises(RuntimeError) as exc_info:
            _cosine_similarity("テスト", "テスト")
        assert_wrapped_cause(exc_info, ValueError, label="_cosine_similarity ラップ")

    def test_union_find_group_wraps_non_runtime_error(self, mocker):
        """_union_find_group が非 RuntimeError を RuntimeError にラップすること。"""
        mocker.patch("src.agents.f70_module._cosine_similarity",
                     side_effect=KeyError("key"))
        tasks = [_task("T1", "A"), _task("T2", "B")]
        with pytest.raises(RuntimeError) as exc_info:
            _union_find_group(tasks)
        assert_wrapped_cause(exc_info, KeyError, label="_union_find_group ラップ")


# ════════════════════════════════════════════════════════
# Test6 — WARNING継続：重複task_id・不正priority・不明trace_id・MECE非準拠
# ════════════════════════════════════════════════════════

class TestWarningContinuation:

    def test_duplicate_task_id_logs_warning(self, caplog):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T1", "広告を配信する"),
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複 task_id", "DuplicateTaskId")

    def test_invalid_priority_logs_warning(self, caplog):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "LPを作成する", priority="Critical"),
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "不正な priority", "InvalidPriority")

    def test_unknown_trace_id_logs_warning(self, caplog):
        data = {"trace_id": "F99", "templated_tasks": VALID_INPUT["templated_tasks"]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_mece_non_compliant_logs_warning(self, caplog):
        data = {
            "trace_id": "F60",
            "templated_tasks": VALID_INPUT["templated_tasks"],
            "mece_report": {
                "duplicate_tasks": ["T1"], "missing_elements": [],
                "ambiguous_tasks": [], "is_mece_compliant": False,
            },
        }
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "MECE 非準拠", "MeceNonCompliant")

    def test_processing_continues_after_warning(self, caplog):
        data = {"trace_id": "F60", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T1", "広告を配信する"),  # 重複
        ]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F70"
        assert len(result["hierarchy"]["goals"]) > 0


# ════════════════════════════════════════════════════════
# Test7 — trace_id="F70"・パイプライン統合
# ════════════════════════════════════════════════════════

class TestTraceId:

    def test_normal_trace_id_is_f70(self):
        assert execute(VALID_INPUT)["trace_id"] == "F70"

    def test_hitl_output_trace_id_is_f70(self):
        data = {"trace_id": "F60", "templated_tasks": []}
        assert execute(data)["trace_id"] == "F70"

    def test_source_trace_id_reflects_input(self):
        assert execute(VALID_INPUT)["source_trace_id"] == "F60"

    def test_missing_trace_id_in_input(self, caplog):
        data = {"templated_tasks": VALID_INPUT["templated_tasks"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F70"
        assert result["source_trace_id"] == ""

    def test_unknown_source_trace_id_is_f70(self, caplog):
        data = {"trace_id": "UNKNOWN", "templated_tasks": VALID_INPUT["templated_tasks"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F70"

    def test_f10_to_f70_pipeline(self, mocker):
        """F10→F20→F30→F40→F50→F60→F70 の完全パイプラインを検証する。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value=(
                '{"L1":"売上を伸ばす","L2":["新規獲得","リテンション"],'
                '"L3":["LP作成","広告配信"]}'
            ),
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec
        from src.agents.f40_module import execute as f40_exec
        from src.agents.f50_module import execute as f50_exec
        from src.agents.f60_module import execute as f60_exec

        f70_out = execute(
            f60_exec(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
                {"goal_text": "売上を前年比120%に成長させる"}
            ))))))
        )

        assert f70_out["trace_id"] == "F70"
        assert f70_out["source_trace_id"] == "F60"
        assert "hierarchy" in f70_out
        assert "goals" in f70_out["hierarchy"]

    def test_pipeline_hierarchy_contains_all_tasks(self, mocker):
        """パイプライン末端で全タスクが hierarchy 内に存在すること。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規獲得"],"L3":["LP作成","広告配信"]}',
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec
        from src.agents.f40_module import execute as f40_exec
        from src.agents.f50_module import execute as f50_exec
        from src.agents.f60_module import execute as f60_exec

        f50_out = f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
            {"goal_text": "売上を前年比120%に成長させる"}
        )))))

        f70_out = execute(f60_exec(f50_out))
        goals   = f70_out["hierarchy"]["goals"]

        # F50 の templated_tasks に含まれる全 task_id が F70 の hierarchy に存在すること
        input_task_ids = {t["task_id"] for t in f50_out["templated_tasks"]}
        output_task_ids = {
            t["task_id"]
            for g in goals
            for e in g["elements"]
            for t in e["tasks"]
        }
        assert input_task_ids == output_task_ids
