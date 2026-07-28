"""Unit tests for F90_Final_Output_Generation_Module (WP5100準拠)

F_series_overview.md の Unit Test 方針を継承し、
F10〜F80 と共通の assert_warning_contains / assert_wrapped_cause を再利用する。
"""

import logging

import pytest

from src.agents.f90_module import (
    EFFICIENCY_MAX,
    EXPECTED_FULL_CHAIN,
    _build_trace_lookup,
    _check_integrity,
    _compute_evaluation,
    _generate_recommendations,
    _merge_hierarchy_with_trace,
    _validate_input,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー
# ════════════════════════════════════════════════════════

FULL_CHAIN = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]


def _trace_entry(task_id, goal_id="G1", element_id="G1_EL_H",
                 chain=None, is_complete=True):
    return {
        "goal_id":       goal_id,
        "element_id":    element_id,
        "task_id":       task_id,
        "trace_chain":   chain if chain is not None else FULL_CHAIN,
        "origin_module": (chain or FULL_CHAIN)[0],
        "latest_module": (chain or FULL_CHAIN)[-1],
        "is_complete":   is_complete,
    }


def _task(task_id, text="テスト", priority="High", effort=3, value=5):
    return {
        "task_id":        task_id,
        "templated_text": text,
        "priority":       priority,
        "effort":         effort,
        "value":          value,
    }


def _elem(element_id, task_ids, tasks_override=None):
    tasks = tasks_override or [_task(tid) for tid in task_ids]
    return {"element_id": element_id, "element_text": f"{element_id}テキスト", "tasks": tasks}


def _goal(goal_id, elements):
    return {"goal_id": goal_id, "goal_text": f"{goal_id}テキスト", "elements": elements}


VALID_INPUT = {
    "trace_id": "F80",
    "source_trace_id": "F70",
    "traceability_map": [
        _trace_entry("T1", goal_id="G1", element_id="G1_EL_H"),
        _trace_entry("T2", goal_id="G1", element_id="G1_EL_H"),
        _trace_entry("T3", goal_id="G2", element_id="G2_EL_M"),
    ],
    "hierarchy": {
        "goals": [
            _goal("G1", [_elem("G1_EL_H", ["T1", "T2"])]),
            _goal("G2", [_elem("G2_EL_M", ["T3"])]),
        ]
    },
}

INVALID_TYPE_INPUTS = [
    pytest.param(None,     id="none"),
    pytest.param("string", id="string"),
    pytest.param(42,       id="int"),
    pytest.param([],       id="list"),
]

INVALID_STRUCT_INPUTS = [
    pytest.param({},                          id="empty_dict"),
    pytest.param({"trace_id": "F80",
                  "hierarchy": {"goals": []}}, id="missing_traceability_map"),
    pytest.param({"traceability_map": "bad",
                  "hierarchy": {},
                  "trace_id": "F80"},         id="tmap_not_list"),
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
# Test1 — 正常系：final_output 構造・summary・評価レポート
# ════════════════════════════════════════════════════════

class TestNormalFinalOutput:
    """execute() が正常入力に対して期待する final_output を返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)
        self.fo     = self.result["final_output"]

    def test_trace_id_is_f90(self):
        assert self.result["trace_id"] == "F90"

    def test_source_trace_id_is_f80(self):
        assert self.result["source_trace_id"] == "F80"

    def test_final_output_key_present(self):
        assert "final_output" in self.result

    def test_summary_keys(self):
        required = {"total_goals","total_elements","total_tasks",
                    "pipeline_integrity","traceability_complete"}
        assert required <= self.fo["summary"].keys()

    def test_summary_total_goals(self):
        assert self.fo["summary"]["total_goals"] == 2

    def test_summary_total_elements(self):
        assert self.fo["summary"]["total_elements"] == 2

    def test_summary_total_tasks(self):
        assert self.fo["summary"]["total_tasks"] == 3

    def test_pipeline_integrity_verified(self):
        assert self.fo["summary"]["pipeline_integrity"] == "verified"

    def test_traceability_complete_true(self):
        assert self.fo["summary"]["traceability_complete"] is True

    def test_hierarchy_with_trace_is_list(self):
        assert isinstance(self.fo["hierarchy_with_trace"], list)

    def test_hierarchy_with_trace_has_goals(self):
        assert len(self.fo["hierarchy_with_trace"]) == 2

    def test_tasks_have_trace_chain(self):
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert "trace_chain" in task
                    assert task["trace_chain"] == FULL_CHAIN

    def test_evaluation_report_keys(self):
        required = {"average_effort","average_value","efficiency_score","recommendations"}
        assert required <= self.fo["evaluation_report"].keys()

    def test_average_effort_correct(self):
        assert self.fo["evaluation_report"]["average_effort"] == pytest.approx(3.0)

    def test_average_value_correct(self):
        assert self.fo["evaluation_report"]["average_value"] == pytest.approx(5.0)

    def test_efficiency_score_correct(self):
        # 5.0 / 3.0 = 1.67
        assert self.fo["evaluation_report"]["efficiency_score"] == pytest.approx(1.67, abs=0.01)

    def test_recommendations_is_list(self):
        assert isinstance(self.fo["evaluation_report"]["recommendations"], list)

    def test_high_priority_recommendation_present(self):
        recs = self.fo["evaluation_report"]["recommendations"]
        assert any("高優先度" in r for r in recs)

    def test_hitl_false_when_complete(self):
        assert self.result["hitl"] is False
        assert self.result["hitl_required"] is False
        assert self.result["hitl_elements"] == []

    # ── ユーティリティ単体検証 ──────────────────────────

    def test_build_trace_lookup(self):
        lookup = _build_trace_lookup([
            _trace_entry("T1"), _trace_entry("T2"),
        ])
        assert "T1" in lookup and "T2" in lookup
        assert lookup["T1"] == FULL_CHAIN

    def test_merge_hierarchy_with_trace_attaches_chain(self):
        hierarchy = {"goals": [_goal("G1", [_elem("E1", ["T1"])])]}
        lookup    = {"T1": FULL_CHAIN}
        merged    = _merge_hierarchy_with_trace(hierarchy, lookup)
        assert merged[0]["elements"][0]["tasks"][0]["trace_chain"] == FULL_CHAIN

    def test_merge_hierarchy_missing_task_in_lookup_gives_empty_chain(self):
        hierarchy = {"goals": [_goal("G1", [_elem("E1", ["T99"])])]}
        merged    = _merge_hierarchy_with_trace(hierarchy, {})
        assert merged[0]["elements"][0]["tasks"][0]["trace_chain"] == []

    def test_efficiency_max_constant(self):
        assert EFFICIENCY_MAX == pytest.approx(10.0)

    def test_expected_full_chain_constant(self):
        assert EXPECTED_FULL_CHAIN == FULL_CHAIN


# ════════════════════════════════════════════════════════
# Test2 — 異常系：型不正・traceability_map 欠落・hierarchy 欠落
# ════════════════════════════════════════════════════════

class TestInvalidInput:

    @pytest.mark.parametrize("bad_input", INVALID_TYPE_INPUTS)
    def test_type_error_for_non_dict(self, bad_input):
        with pytest.raises(TypeError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_STRUCT_INPUTS)
    def test_value_error_for_missing_traceability_map(self, bad_input):
        with pytest.raises(ValueError):
            execute(bad_input)

    def test_type_error_for_missing_hierarchy(self):
        """hierarchy 欠落は ValueError ではなく TypeError であること。"""
        data = {"traceability_map": [], "trace_id": "F80"}
        with pytest.raises(TypeError, match="hierarchy"):
            execute(data)

    def test_type_error_for_hierarchy_not_dict(self):
        data = {"traceability_map": [], "hierarchy": "not_a_dict", "trace_id": "F80"}
        with pytest.raises(TypeError, match="dict"):
            execute(data)

    def test_validate_input_none(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input(None)

    def test_validate_input_empty_dict(self):
        with pytest.raises(ValueError, match="空"):
            _validate_input({})

    def test_validate_input_missing_traceability_map(self):
        with pytest.raises(ValueError, match="traceability_map"):
            _validate_input({"hierarchy": {}, "trace_id": "F80"})

    def test_validate_input_tmap_not_list(self):
        with pytest.raises(ValueError, match="list"):
            _validate_input({"traceability_map": "bad", "hierarchy": {}})


# ════════════════════════════════════════════════════════
# Test3 — 統合ロジック：階層統合・評価集計・推奨事項
# ════════════════════════════════════════════════════════

class TestIntegrationLogic:

    def test_compute_evaluation_basic(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            _task("T1", effort=2, value=4),
            _task("T2", effort=4, value=6),
        ])])]
        result = _compute_evaluation(hw)
        assert result["average_effort"] == pytest.approx(3.0)
        assert result["average_value"]  == pytest.approx(5.0)
        assert result["efficiency_score"] == pytest.approx(1.67, abs=0.01)

    def test_compute_evaluation_single_task(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            _task("T1", effort=5, value=5),
        ])])]
        result = _compute_evaluation(hw)
        assert result["efficiency_score"] == pytest.approx(1.0)

    def test_compute_evaluation_skips_none_effort(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            _task("T1", effort=2, value=4),
            {"task_id": "T2", "templated_text": "テスト",
             "priority": "Low", "effort": None, "value": None},
        ])])]
        result = _compute_evaluation(hw)
        assert result["average_effort"] == pytest.approx(2.0)

    def test_check_integrity_all_complete(self):
        tmap = [_trace_entry("T1"), _trace_entry("T2")]
        hitl = []
        assert _check_integrity(tmap, hitl) is True
        assert hitl == []

    def test_check_integrity_incomplete(self):
        tmap = [
            _trace_entry("T1"),
            _trace_entry("T2", chain=["F10","F20"], is_complete=False),
        ]
        hitl = []
        result = _check_integrity(tmap, hitl)
        assert result is False
        assert "T2" in hitl

    def test_check_integrity_empty_chain(self):
        tmap = [_trace_entry("T1", chain=[])]
        hitl = []
        _check_integrity(tmap, hitl)
        assert "T1" in hitl

    def test_generate_recommendations_high_priority(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            _task("T1", priority="High"),
        ])])]
        recs = _generate_recommendations(hw, True, 2.0)
        assert any("高優先度" in r for r in recs)

    def test_generate_recommendations_incomplete_chain(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[_task("T1")])])]
        recs = _generate_recommendations(hw, False, 2.0)
        assert any("HITL" in r for r in recs)

    def test_generate_recommendations_high_efficiency(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[_task("T1")])])]
        recs = _generate_recommendations(hw, True, 4.0)
        assert any("高価値" in r for r in recs)

    def test_efficiency_score_rounding(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            _task("T1", effort=3, value=10),
        ])])]
        result = _compute_evaluation(hw)
        # 10/3 = 3.33
        assert result["efficiency_score"] == pytest.approx(3.33, abs=0.01)

    def test_hierarchy_with_trace_preserves_effort_value(self):
        result = execute(VALID_INPUT)
        for goal in result["final_output"]["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert "effort" in task
                    assert "value"  in task


# ════════════════════════════════════════════════════════
# Test4 — HITL移譲：空入力・不完全chain・efficiency_score異常
# ════════════════════════════════════════════════════════

class TestHitlDelegation:

    def test_empty_tmap_hitl_required(self):
        data = {"trace_id": "F80", "traceability_map": [],
                "hierarchy": {"goals": [_goal("G1", [_elem("E1", ["T1"])])]}}
        result = execute(data)
        assert result["hitl_required"] is True
        assert result.get("hitl_reason") == "No tasks to finalize"

    def test_empty_goals_hitl_required(self):
        data = {"trace_id": "F80",
                "traceability_map": [_trace_entry("T1")],
                "hierarchy": {"goals": []}}
        result = execute(data)
        assert result["hitl_required"] is True

    def test_empty_hitl_trace_id_is_f90(self):
        data = {"trace_id": "F80", "traceability_map": [],
                "hierarchy": {"goals": []}}
        assert execute(data)["trace_id"] == "F90"

    def test_incomplete_chain_triggers_hitl(self):
        data = {
            "trace_id": "F80",
            "traceability_map": [
                _trace_entry("T1", chain=["F10","F20"], is_complete=False),
            ],
            "hierarchy": {"goals": [_goal("G1", [_elem("G1_EL_H", ["T1"])])]},
        }
        result = execute(data)
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    def test_efficiency_score_zero_triggers_hitl(self, mocker):
        """efficiency_score=0 の場合に hitl_elements に追加されること。"""
        mocker.patch("src.agents.f90_module._compute_evaluation",
                     return_value={"average_effort": 3.0,
                                   "average_value":  0.0,
                                   "efficiency_score": 0.0})
        result = execute(VALID_INPUT)
        assert "efficiency_score" in result["hitl_elements"]

    def test_efficiency_score_over_max_triggers_hitl(self, mocker):
        """efficiency_score > 10 の場合に hitl_elements に追加されること。"""
        mocker.patch("src.agents.f90_module._compute_evaluation",
                     return_value={"average_effort": 1.0,
                                   "average_value":  12.0,
                                   "efficiency_score": 12.0})
        result = execute(VALID_INPUT)
        assert "efficiency_score" in result["hitl_elements"]

    def test_hitl_elements_sorted_and_deduped(self):
        data = {
            "trace_id": "F80",
            "traceability_map": [
                _trace_entry("T2", chain=["F10"], is_complete=False),
                _trace_entry("T1", chain=["F10"], is_complete=False),
            ],
            "hierarchy": {"goals": [_goal("G1", [
                _elem("G1_EL_H", [], tasks_override=[
                    _task("T1"), _task("T2")
                ])
            ])]},
        }
        result = execute(data)
        els = result["hitl_elements"]
        assert els == sorted(set(els))

    def test_full_pipeline_no_hitl(self):
        result = execute(VALID_INPUT)
        assert result["hitl_required"] is False


# ════════════════════════════════════════════════════════
# Test5 — RuntimeError：ZeroDivisionError ラップ・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestRuntimeError:

    def test_zero_average_effort_raises_runtime(self):
        """all effort=None → average_effort=0 → RuntimeError。"""
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            {"task_id": "T1", "templated_text": "テスト",
             "priority": "High", "effort": None, "value": None},
        ])])]
        with pytest.raises(RuntimeError):
            _compute_evaluation(hw)

    def test_zero_effort_cause_is_zero_division(self):
        hw = [_goal("G1", [_elem("E1", [], tasks_override=[
            {"task_id": "T1", "templated_text": "テスト",
             "priority": "High", "effort": None, "value": None},
        ])])]
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation(hw)
        assert_wrapped_cause(exc_info, ZeroDivisionError, label="ZeroDivision ラップ")

    def test_runtime_propagates_from_execute(self, mocker):
        """_compute_evaluation が RuntimeError を上げると execute() から伝播すること。"""
        mocker.patch("src.agents.f90_module._compute_evaluation",
                     side_effect=RuntimeError("集計テストエラー"))
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_preserved_from_compute(self, mocker):
        original = TypeError("type error")
        mocker.patch("src.agents.f90_module._compute_evaluation",
                     side_effect=original)
        with pytest.raises(TypeError):
            execute(VALID_INPUT)


# ════════════════════════════════════════════════════════
# Test6 — WARNING継続：重複task_id・不正trace_id
# ════════════════════════════════════════════════════════

class TestWarningContinuation:

    def test_duplicate_task_id_logs_warning(self, caplog):
        data = {
            "trace_id": "F80",
            "traceability_map": [
                _trace_entry("T1"),
                _trace_entry("T1"),   # 重複
            ],
            "hierarchy": {"goals": [_goal("G1", [_elem("G1_EL_H", ["T1"])])]},
        }
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複 task_id", "DuplicateTaskId")

    def test_unknown_trace_id_logs_warning(self, caplog):
        data = {**VALID_INPUT, "trace_id": "F99"}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_processing_continues_after_warning(self, caplog):
        data = {**VALID_INPUT, "trace_id": "F99"}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F90"
        assert result["final_output"]["summary"]["total_tasks"] > 0


# ════════════════════════════════════════════════════════
# Test7 — trace_id="F90"・F10→F90 完全パイプライン統合
# ════════════════════════════════════════════════════════

class TestTraceId:

    def test_normal_trace_id_is_f90(self):
        assert execute(VALID_INPUT)["trace_id"] == "F90"

    def test_empty_input_trace_id_is_f90(self):
        data = {"trace_id": "F80", "traceability_map": [],
                "hierarchy": {"goals": []}}
        assert execute(data)["trace_id"] == "F90"

    def test_source_trace_id_reflects_input(self):
        assert execute(VALID_INPUT)["source_trace_id"] == "F80"

    def test_missing_trace_id_in_input(self, caplog):
        data = {k: v for k, v in VALID_INPUT.items() if k != "trace_id"}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F90"
        assert result["source_trace_id"] == ""

    def test_f10_to_f90_full_pipeline(self, mocker):
        """F10→F20→F30→F40→F50→F60→F70→F80→F90 の完全パイプラインを検証する。"""
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
        from src.agents.f70_module import execute as f70_exec
        from src.agents.f80_module import execute as f80_exec

        f90_out = execute(
            f80_exec(f70_exec(f60_exec(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
                {"goal_text": "売上を前年比120%に成長させる"}
            ))))))))
        )

        assert f90_out["trace_id"] == "F90"
        assert f90_out["source_trace_id"] == "F80"
        fo = f90_out["final_output"]
        assert fo["summary"]["total_tasks"] > 0
        assert fo["summary"]["traceability_complete"] is True
        assert fo["summary"]["pipeline_integrity"] == "verified"

    def test_pipeline_efficiency_score_valid(self, mocker):
        """フルパイプラインで efficiency_score が有効範囲にあること。"""
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
        from src.agents.f70_module import execute as f70_exec
        from src.agents.f80_module import execute as f80_exec

        f90_out = execute(
            f80_exec(f70_exec(f60_exec(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
                {"goal_text": "売上を前年比120%に成長させる"}
            ))))))))
        )

        score = f90_out["final_output"]["evaluation_report"]["efficiency_score"]
        assert 0 < score <= 10, f"efficiency_score 異常値: {score}"

    def test_pipeline_all_tasks_have_trace_chain(self, mocker):
        """フルパイプラインで hierarchy_with_trace の全タスクが trace_chain を持つこと。"""
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
        from src.agents.f70_module import execute as f70_exec
        from src.agents.f80_module import execute as f80_exec

        f90_out = execute(
            f80_exec(f70_exec(f60_exec(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
                {"goal_text": "売上を前年比120%に成長させる"}
            ))))))))
        )

        for goal in f90_out["final_output"]["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert task["trace_chain"] == FULL_CHAIN, (
                        f"task_id='{task['task_id']}' の trace_chain が不完全: {task['trace_chain']}"
                    )
