"""Unit tests for F80_Traceability_Generation_Module (WP5100準拠)

F_series_overview.md の Unit Test 方針を継承し、
F10〜F70 と共通の assert_warning_contains / assert_wrapped_cause を再利用する。
"""

import logging

import pytest

from src.agents.f80_module import (
    EXPECTED_ORIGIN,
    PIPELINE_ORDER,
    _build_trace_chain,
    _build_trace_entry,
    _detect_circular_deps,
    _is_chain_complete,
    _validate_input,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー
# ════════════════════════════════════════════════════════

def _make_task(task_id, **kwargs):
    t = {"task_id": task_id, "templated_text": f"テスト: {task_id}",
         "priority": "High", "effort": 2, "value": 4}
    t.update(kwargs)
    return t


def _make_elem(element_id, task_ids):
    return {
        "element_id":   element_id,
        "element_text": f"{element_id}テキスト",
        "tasks":        [_make_task(tid) for tid in task_ids],
    }


def _make_goal(goal_id, elements):
    return {
        "goal_id":   goal_id,
        "goal_text": f"{goal_id}テキスト",
        "elements":  elements,
    }


FULL_CHAIN = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]

# 正常入力: F70 出力
VALID_INPUT = {
    "trace_id": "F70",
    "source_trace_id": "F60",
    "hierarchy": {
        "goals": [
            _make_goal("G1", [
                _make_elem("G1_EL_H", ["T1", "T2"]),
                _make_elem("G1_EL_M", ["T3"]),
            ]),
            _make_goal("G2", [
                _make_elem("G2_EL_L", ["T4"]),
            ]),
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
    pytest.param({},                             id="empty_dict"),
    pytest.param({"trace_id": "F70"},            id="missing_hierarchy"),
    pytest.param({"hierarchy": "not_a_dict",
                  "trace_id": "F70"},            id="hierarchy_not_dict"),
    pytest.param({"hierarchy": {},
                  "trace_id": "F70"},            id="missing_goals"),
    pytest.param({"hierarchy": {"goals": "bad"},
                  "trace_id": "F70"},            id="goals_not_list"),
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
# Test1 — 正常系：traceability_map 構造・trace_chain・is_complete
# ════════════════════════════════════════════════════════

class TestNormalTraceability:
    """execute() が正常入力に対して期待する traceability_map を返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)
        self.tmap   = self.result["traceability_map"]

    def test_trace_id_is_f80(self):
        assert self.result["trace_id"] == "F80"

    def test_source_trace_id_is_f70(self):
        assert self.result["source_trace_id"] == "F70"

    def test_traceability_map_is_list(self):
        assert isinstance(self.tmap, list)

    def test_entry_count_equals_total_tasks(self):
        """全 goal の全 element の全 task 数だけエントリが生成されること。"""
        expected = sum(
            len(elem["tasks"])
            for goal in VALID_INPUT["hierarchy"]["goals"]
            for elem in goal["elements"]
        )
        assert len(self.tmap) == expected

    def test_entry_required_fields(self):
        required = {"goal_id", "element_id", "task_id",
                    "trace_chain", "origin_module", "latest_module", "is_complete"}
        for entry in self.tmap:
            assert required <= entry.keys(), f"フィールド不足: {entry}"

    def test_trace_chain_is_full_pipeline(self):
        """trace_id="F70" の場合に全 chain が F10〜F70 であること。"""
        for entry in self.tmap:
            assert entry["trace_chain"] == FULL_CHAIN

    def test_origin_module_is_f10(self):
        for entry in self.tmap:
            assert entry["origin_module"] == "F10"

    def test_latest_module_is_f70(self):
        for entry in self.tmap:
            assert entry["latest_module"] == "F70"

    def test_is_complete_true_for_full_chain(self):
        for entry in self.tmap:
            assert entry["is_complete"] is True

    def test_hitl_false_when_complete(self):
        assert self.result["hitl"] is False
        assert self.result["hitl_required"] is False
        assert self.result["hitl_elements"] == []

    def test_goal_id_preserved(self):
        g1_entries = [e for e in self.tmap if e["goal_id"] == "G1"]
        assert len(g1_entries) > 0

    def test_element_id_preserved(self):
        el_entries = [e for e in self.tmap if e["element_id"] == "G1_EL_H"]
        assert len(el_entries) == 2  # T1, T2

    def test_task_id_preserved(self):
        all_task_ids = {e["task_id"] for e in self.tmap}
        assert {"T1", "T2", "T3", "T4"} == all_task_ids

    # ── ユーティリティ単体検証 ──────────────────────────

    def test_build_trace_chain_f70(self):
        assert _build_trace_chain("F70") == FULL_CHAIN

    def test_build_trace_chain_f10(self):
        assert _build_trace_chain("F10") == ["F10"]

    def test_build_trace_chain_f40(self):
        assert _build_trace_chain("F40") == ["F10", "F20", "F30", "F40"]

    def test_build_trace_chain_unknown_returns_empty(self):
        assert _build_trace_chain("F99") == []
        assert _build_trace_chain("") == []

    def test_is_chain_complete_full(self):
        assert _is_chain_complete(FULL_CHAIN) is True

    def test_is_chain_complete_partial(self):
        assert _is_chain_complete(["F10", "F20"]) is False

    def test_is_chain_complete_empty(self):
        assert _is_chain_complete([]) is False

    def test_pipeline_order_constant(self):
        assert PIPELINE_ORDER == ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]

    def test_expected_origin_constant(self):
        assert EXPECTED_ORIGIN == "F10"


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

    def test_type_error_missing_goal_id(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            {"elements": [_make_elem("E1", ["T1"])]}
        ]}}
        with pytest.raises(TypeError, match="goal_id"):
            execute(data)

    def test_type_error_missing_elements(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            {"goal_id": "G1"}
        ]}}
        with pytest.raises(TypeError, match="elements"):
            execute(data)

    def test_type_error_missing_element_id(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [{"tasks": [_make_task("T1")]}])
        ]}}
        with pytest.raises(TypeError, match="element_id"):
            execute(data)

    def test_type_error_missing_tasks(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [{"element_id": "E1"}])
        ]}}
        with pytest.raises(TypeError, match="tasks"):
            execute(data)

    def test_type_error_missing_task_id(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [{"element_id": "E1", "tasks": [{"priority": "High"}]}])
        ]}}
        with pytest.raises(TypeError, match="task_id"):
            execute(data)

    def test_type_error_goal_not_dict(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": ["not_a_dict"]}}
        with pytest.raises(TypeError, match="dict"):
            execute(data)

    def test_validate_input_none(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input(None)

    def test_validate_input_empty_dict(self):
        with pytest.raises(ValueError, match="空"):
            _validate_input({})

    def test_validate_input_missing_hierarchy(self):
        with pytest.raises(ValueError, match="hierarchy"):
            _validate_input({"trace_id": "F70"})


# ════════════════════════════════════════════════════════
# Test3 — trace_chain：完全/部分/source_trace_id 解決
# ════════════════════════════════════════════════════════

class TestTraceChain:

    def test_full_chain_from_f70_source(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [_make_elem("E1", ["T1"])])
        ]}}
        result = execute(data)
        entry  = result["traceability_map"][0]
        assert entry["trace_chain"] == FULL_CHAIN
        assert entry["is_complete"] is True

    def test_partial_chain_from_f40_source(self):
        """trace_id='F40' の場合に F10〜F40 の部分 chain になること。"""
        data = {"trace_id": "F40", "hierarchy": {"goals": [
            _make_goal("G1", [_make_elem("E1", ["T1"])])
        ]}}
        result = execute(data)
        entry  = result["traceability_map"][0]
        assert entry["trace_chain"] == ["F10", "F20", "F30", "F40"]
        assert entry["is_complete"] is False

    def test_incomplete_chain_sets_hitl_element(self):
        data = {"trace_id": "F40", "hierarchy": {"goals": [
            _make_goal("G1", [_make_elem("E1", ["T1"])])
        ]}}
        result = execute(data)
        assert "T1" in result["hitl_elements"]
        assert result["hitl_required"] is True

    def test_build_trace_entry_complete(self):
        hitl = []
        entry = _build_trace_entry("G1", "E1", "T1", FULL_CHAIN, hitl)
        assert entry["is_complete"] is True
        assert entry["origin_module"] == "F10"
        assert entry["latest_module"] == "F70"
        assert hitl == []

    def test_build_trace_entry_partial_adds_hitl(self):
        hitl = []
        entry = _build_trace_entry("G1", "E1", "T1", ["F10", "F20"], hitl)
        assert entry["is_complete"] is False
        assert "T1" in hitl

    def test_build_trace_entry_empty_chain_adds_hitl(self):
        hitl = []
        entry = _build_trace_entry("G1", "E1", "T1", [], hitl)
        assert entry["origin_module"] is None
        assert entry["latest_module"] is None
        assert "T1" in hitl

    def test_all_entries_share_same_chain(self):
        """同一入力の全エントリが同一 trace_chain を持つこと。"""
        result = execute(VALID_INPUT)
        chains = [e["trace_chain"] for e in result["traceability_map"]]
        assert all(c == FULL_CHAIN for c in chains)

    @pytest.mark.parametrize("module_id, expected_len", [
        ("F10", 1),
        ("F20", 2),
        ("F30", 3),
        ("F40", 4),
        ("F50", 5),
        ("F60", 6),
        ("F70", 7),
    ])
    def test_build_trace_chain_length(self, module_id, expected_len):
        chain = _build_trace_chain(module_id)
        assert len(chain) == expected_len
        assert chain[-1] == module_id


# ════════════════════════════════════════════════════════
# Test4 — HITL移譲：空 goals・chain 欠落・不完全・循環依存
# ════════════════════════════════════════════════════════

class TestHitlDelegation:

    def test_empty_goals_hitl_required(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": []}}
        result = execute(data)
        assert result["hitl_required"] is True
        assert result["hitl"] is True
        assert result.get("hitl_reason") == "No hierarchy provided"

    def test_empty_goals_trace_id_is_f80(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": []}}
        assert execute(data)["trace_id"] == "F80"

    def test_empty_goals_traceability_map_is_empty(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": []}}
        assert execute(data)["traceability_map"] == []

    def test_unknown_source_trace_id_hitl_chain_missing(self):
        """不明な source_trace_id の場合 chain が空になり HITL 移譲されること。"""
        data = {"trace_id": "F99", "hierarchy": {"goals": [
            _make_goal("G1", [_make_elem("E1", ["T1"])])
        ]}}
        result = execute(data)
        assert result["hitl_required"] is True
        assert result.get("hitl_reason") == "Trace chain missing"

    def test_partial_chain_triggers_hitl_for_all_tasks(self):
        data = {"trace_id": "F30", "hierarchy": {"goals": [
            _make_goal("G1", [_make_elem("E1", ["T1", "T2"])])
        ]}}
        result = execute(data)
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]
        assert "T2" in result["hitl_elements"]

    def test_circular_dependency_detected(self):
        """同一 task_id が複数 element に登場する場合 hitl_required=True になること。"""
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [
                _make_elem("E1", ["T1", "T2"]),
                _make_elem("E2", ["T1"]),    # T1 が E1 と E2 に重複
            ])
        ]}}
        result = execute(data)
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    def test_detect_circular_deps_returns_duplicates(self):
        goals = [_make_goal("G1", [
            _make_elem("E1", ["T1", "T2"]),
            _make_elem("E2", ["T1"]),
        ])]
        circular = _detect_circular_deps(goals)
        assert "T1" in circular

    def test_detect_circular_deps_no_issue(self):
        goals = [_make_goal("G1", [
            _make_elem("E1", ["T1"]),
            _make_elem("E2", ["T2"]),
        ])]
        assert _detect_circular_deps(goals) == []

    def test_hitl_elements_deduped_and_sorted(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [
                _make_elem("E1", ["T1"]),
                _make_elem("E2", ["T1"]),   # 循環
            ])
        ]}}
        result = execute(data)
        els = result["hitl_elements"]
        assert els == sorted(set(els))

    def test_full_chain_no_hitl(self):
        result = execute(VALID_INPUT)
        assert result["hitl_required"] is False


# ════════════════════════════════════════════════════════
# Test5 — RuntimeError：chain 構築失敗・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestRuntimeError:

    def test_runtime_error_on_build_entry_failure(self, mocker):
        mocker.patch(
            "src.agents.f80_module._build_trace_entry",
            side_effect=RuntimeError("entry 構築テストエラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_preserved_on_entry_failure(self, mocker):
        original = ZeroDivisionError("test")
        mocker.patch("src.agents.f80_module._is_chain_complete",
                     side_effect=original)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, ZeroDivisionError, label="entry 構築失敗")

    def test_build_trace_entry_wraps_exception(self, mocker):
        """_build_trace_entry が内部エラー時に RuntimeError にラップすること。"""
        mocker.patch("src.agents.f80_module._is_chain_complete",
                     side_effect=AttributeError("attr"))
        hitl = []
        with pytest.raises(RuntimeError) as exc_info:
            _build_trace_entry("G1", "E1", "T1", FULL_CHAIN, hitl)
        assert_wrapped_cause(exc_info, AttributeError, label="_build_trace_entry ラップ")

    def test_runtime_error_message_contains_task_id(self, mocker):
        mocker.patch("src.agents.f80_module._is_chain_complete",
                     side_effect=ValueError("err"))
        hitl = []
        with pytest.raises(RuntimeError) as exc_info:
            _build_trace_entry("G1", "E1", "TX99", FULL_CHAIN, hitl)
        assert "TX99" in str(exc_info.value)


# ════════════════════════════════════════════════════════
# Test6 — WARNING継続：重複task_id・不正trace_id・origin_module不一致
# ════════════════════════════════════════════════════════

class TestWarningContinuation:

    def test_duplicate_task_id_logs_warning(self, caplog):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [
                _make_elem("E1", ["T1"]),
                _make_elem("E2", ["T1"]),   # 重複
            ])
        ]}}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複 task_id", "DuplicateTaskId")

    def test_unknown_trace_id_logs_warning(self, caplog):
        data = {"trace_id": "F99", "hierarchy": {"goals": [
            _make_goal("G1", [_make_elem("E1", ["T1"])])
        ]}}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_origin_module_mismatch_logs_warning(self, mocker, caplog):
        """chain[0] が 'F10' 以外の場合に WARNING が出ること。"""
        mocker.patch("src.agents.f80_module._build_trace_chain",
                     return_value=["F20", "F30", "F40"])
        with caplog.at_level(logging.WARNING):
            execute(VALID_INPUT)
        assert_warning_contains(caplog.records, "origin_module が不正", "OriginMismatch")

    def test_circular_dependency_logs_warning(self, caplog):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [
                _make_elem("E1", ["T1"]),
                _make_elem("E2", ["T1"]),
            ])
        ]}}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "循環依存", "CircularDep")

    def test_processing_continues_after_warning(self, caplog):
        data = {"trace_id": "F70", "hierarchy": {"goals": [
            _make_goal("G1", [
                _make_elem("E1", ["T1"]),
                _make_elem("E2", ["T2"]),
            ])
        ]}}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F80"
        assert len(result["traceability_map"]) == 2


# ════════════════════════════════════════════════════════
# Test7 — trace_id="F80"・パイプライン統合
# ════════════════════════════════════════════════════════

class TestTraceId:

    def test_normal_trace_id_is_f80(self):
        assert execute(VALID_INPUT)["trace_id"] == "F80"

    def test_hitl_output_trace_id_is_f80(self):
        data = {"trace_id": "F70", "hierarchy": {"goals": []}}
        assert execute(data)["trace_id"] == "F80"

    def test_source_trace_id_reflects_input(self):
        assert execute(VALID_INPUT)["source_trace_id"] == "F70"

    def test_missing_trace_id_in_input(self, caplog):
        data = {"hierarchy": VALID_INPUT["hierarchy"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F80"
        assert result["source_trace_id"] == ""

    def test_f10_to_f80_pipeline(self, mocker):
        """F10→F20→F30→F40→F50→F60→F70→F80 の完全パイプラインを検証する。"""
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

        f80_out = execute(
            f70_exec(f60_exec(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
                {"goal_text": "売上を前年比120%に成長させる"}
            )))))))
        )

        assert f80_out["trace_id"] == "F80"
        assert f80_out["source_trace_id"] == "F70"
        assert isinstance(f80_out["traceability_map"], list)
        assert len(f80_out["traceability_map"]) > 0

    def test_pipeline_all_entries_complete(self, mocker):
        """フルパイプラインで全エントリが is_complete=True であること。"""
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

        f80_out = execute(
            f70_exec(f60_exec(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
                {"goal_text": "売上を前年比120%に成長させる"}
            )))))))
        )

        for entry in f80_out["traceability_map"]:
            assert entry["is_complete"] is True, f"is_complete=False: {entry}"
            assert entry["trace_chain"] == FULL_CHAIN
            assert entry["origin_module"] == "F10"
            assert entry["latest_module"] == "F70"
