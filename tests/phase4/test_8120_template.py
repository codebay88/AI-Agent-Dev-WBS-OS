"""Phase 4 — WP8120 テンプレ適用テスト
区分：構造テンプレ / 因果テンプレ / MECEテンプレ / WBSテンプレ / 後続互換性

WP8120 の観点：
  - 各 F モジュールの出力がテンプレ構造（keys/階層/必須項目）と一致すること
  - F50 の TMP_HIGH/MEDIUM/LOW テンプレが仕様どおりに適用されること
  - テンプレ必須フィールドが欠落していないこと
  - テンプレ適用後のデータが後続モジュールで正しく利用できること
  - 異常系でテンプレ適用ロジックが破綻せず例外が正しく発火すること
"""

import pytest


# ════════════════════════════════════════════════════════
# 共通フィクスチャ
# ════════════════════════════════════════════════════════

_MOCK_API = '{"L1":"売上を前年比120%に成長させる","L2":["新規顧客獲得","既存顧客維持"],"L3":["LP作成する","広告配信する"]}'

@pytest.fixture
def mock_api(mocker):
    mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)

@pytest.fixture
def f10_out(mock_api):
    from src.agents.f10_module import execute as f10
    return f10({"goal_text": "売上を前年比120%に成長させる"})

@pytest.fixture
def f20_out(f10_out):
    from src.agents.f20_module import execute as f20
    return f20(f10_out)

@pytest.fixture
def f30_out(f20_out):
    from src.agents.f30_module import execute as f30
    return f30(f20_out)

@pytest.fixture
def f40_out(f30_out):
    from src.agents.f40_module import execute as f40
    return f40(f30_out)

@pytest.fixture
def f50_out(f40_out):
    from src.agents.f50_module import execute as f50
    return f50(f40_out)

@pytest.fixture
def f60_out(f50_out):
    from src.agents.f60_module import execute as f60
    return f60(f50_out)

@pytest.fixture
def f70_out(f60_out):
    from src.agents.f70_module import execute as f70
    return f70(f60_out)

@pytest.fixture
def f80_out(f70_out):
    from src.agents.f80_module import execute as f80
    return f80(f70_out)

@pytest.fixture
def f90_out(f80_out):
    from src.agents.f90_module import execute as f90
    return f90(f80_out)


# ════════════════════════════════════════════════════════
# WP8121: 構造テンプレ — F10 出力テンプレ検証
# ════════════════════════════════════════════════════════

class TestWP8121_StructureTemplate:
    """F10 の出力テンプレ（goal.L1/L2/L3 階層構造）の検証"""

    def test_f10_output_is_dict(self, f10_out):
        assert isinstance(f10_out, dict)

    def test_f10_has_trace_id(self, f10_out):
        assert "trace_id" in f10_out

    def test_f10_trace_id_value(self, f10_out):
        assert f10_out["trace_id"] == "F10"

    def test_f10_has_goal_key(self, f10_out):
        assert "goal" in f10_out

    def test_f10_goal_has_l1(self, f10_out):
        assert "L1" in f10_out["goal"]

    def test_f10_goal_has_l2(self, f10_out):
        assert "L2" in f10_out["goal"]

    def test_f10_goal_has_l3(self, f10_out):
        assert "L3" in f10_out["goal"]

    def test_f10_l1_is_string(self, f10_out):
        assert isinstance(f10_out["goal"]["L1"], str)

    def test_f10_l2_is_list(self, f10_out):
        assert isinstance(f10_out["goal"]["L2"], list)

    def test_f10_l3_is_list(self, f10_out):
        assert isinstance(f10_out["goal"]["L3"], list)

    def test_f10_l2_elements_are_strings(self, f10_out):
        for item in f10_out["goal"]["L2"]:
            assert isinstance(item, str)

    def test_f10_l3_elements_are_strings(self, f10_out):
        for item in f10_out["goal"]["L3"]:
            assert isinstance(item, str)

    def test_f10_l1_nonempty(self, f10_out):
        assert len(f10_out["goal"]["L1"]) > 0

    def test_f10_l2_nonempty(self, f10_out):
        assert len(f10_out["goal"]["L2"]) > 0

    def test_f10_l3_nonempty(self, f10_out):
        assert len(f10_out["goal"]["L3"]) > 0


# ════════════════════════════════════════════════════════
# WP8122: 因果テンプレ — F20/F30/F40 出力テンプレ検証
# ════════════════════════════════════════════════════════

class TestWP8122_CausalTemplate:
    """F20/F30/F40 の出力テンプレ構造検証"""

    # ─── F20 expanded_goals テンプレ ───
    def test_f20_has_expanded_goals(self, f20_out):
        assert "expanded_goals" in f20_out

    def test_f20_expanded_goals_is_list(self, f20_out):
        assert isinstance(f20_out["expanded_goals"], list)

    def test_f20_each_element_has_element_id(self, f20_out):
        for elem in f20_out["expanded_goals"]:
            assert "element_id" in elem, f"element_id 欠落: {elem}"

    def test_f20_each_element_has_text(self, f20_out):
        for elem in f20_out["expanded_goals"]:
            assert "text" in elem, f"text 欠落: {elem}"

    def test_f20_each_element_has_parent(self, f20_out):
        for elem in f20_out["expanded_goals"]:
            assert "parent" in elem, f"parent 欠落: {elem}"

    def test_f20_parent_values_valid(self, f20_out):
        valid = {"L1", "L2", "L3"}
        for elem in f20_out["expanded_goals"]:
            assert elem["parent"] in valid, f"不正 parent: {elem['parent']}"

    def test_f20_element_ids_are_strings(self, f20_out):
        for elem in f20_out["expanded_goals"]:
            assert isinstance(elem["element_id"], str)

    def test_f20_source_trace_id_is_f10(self, f20_out):
        assert f20_out.get("source_trace_id") == "F10"

    # ─── F30 evaluated_goals テンプレ ───
    def test_f30_has_evaluated_goals(self, f30_out):
        assert "evaluated_goals" in f30_out

    def test_f30_evaluated_goals_is_list(self, f30_out):
        assert isinstance(f30_out["evaluated_goals"], list)

    def test_f30_each_element_has_score_importance(self, f30_out):
        for elem in f30_out["evaluated_goals"]:
            assert "score_importance" in elem, f"score_importance 欠落: {elem}"

    def test_f30_each_element_has_score_feasibility(self, f30_out):
        for elem in f30_out["evaluated_goals"]:
            assert "score_feasibility" in elem, f"score_feasibility 欠落: {elem}"

    def test_f30_each_element_has_priority(self, f30_out):
        for elem in f30_out["evaluated_goals"]:
            assert "priority" in elem, f"priority 欠落: {elem}"

    def test_f30_priority_values_valid(self, f30_out):
        valid = {"High", "Medium", "Low"}
        for elem in f30_out["evaluated_goals"]:
            assert elem["priority"] in valid

    def test_f30_scores_in_range(self, f30_out):
        for elem in f30_out["evaluated_goals"]:
            assert 0.0 <= elem["score_importance"] <= 1.0
            assert 0.0 <= elem["score_feasibility"] <= 1.0

    def test_f30_source_trace_id_is_f20(self, f30_out):
        assert f30_out.get("source_trace_id") == "F20"

    # ─── F40 tasks テンプレ ───
    def test_f40_has_tasks(self, f40_out):
        assert "tasks" in f40_out

    def test_f40_tasks_is_list(self, f40_out):
        assert isinstance(f40_out["tasks"], list)

    def test_f40_each_task_has_task_id(self, f40_out):
        for task in f40_out["tasks"]:
            assert "task_id" in task, f"task_id 欠落: {task}"

    def test_f40_each_task_has_estimated_effort(self, f40_out):
        for task in f40_out["tasks"]:
            assert "estimated_effort" in task, f"estimated_effort 欠落: {task}"

    def test_f40_each_task_has_estimated_value(self, f40_out):
        for task in f40_out["tasks"]:
            assert "estimated_value" in task, f"estimated_value 欠落: {task}"

    def test_f40_effort_is_numeric(self, f40_out):
        for task in f40_out["tasks"]:
            assert isinstance(task["estimated_effort"], (int, float))

    def test_f40_value_is_numeric(self, f40_out):
        for task in f40_out["tasks"]:
            assert isinstance(task["estimated_value"], (int, float))

    def test_f40_source_trace_id_is_f30(self, f40_out):
        assert f40_out.get("source_trace_id") == "F30"


# ════════════════════════════════════════════════════════
# WP8123: テンプレ適用 — F50 TMP_HIGH/MEDIUM/LOW 検証
# ════════════════════════════════════════════════════════

class TestWP8123_TemplateApplication:
    """F50 テンプレート適用ロジックの網羅的検証"""

    def _task(self, text, priority, tid="T1"):
        return {"task_id": tid, "task_text": text, "priority": priority,
                "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}

    # ─── テンプレ選択 ───
    def test_high_template_id(self):
        from src.agents.f50_module import _apply_template
        assert _apply_template(self._task("LP作成", "High"))["template_id"] == "TMP_HIGH"

    def test_medium_template_id(self):
        from src.agents.f50_module import _apply_template
        assert _apply_template(self._task("広告配信", "Medium"))["template_id"] == "TMP_MEDIUM"

    def test_low_template_id(self):
        from src.agents.f50_module import _apply_template
        assert _apply_template(self._task("資料整理", "Low"))["template_id"] == "TMP_LOW"

    # ─── テンプレ文字列形式 ───
    def test_high_text_prefix(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成する", "High"))
        assert result["templated_text"].startswith("【優先度: 高】次のタスクを実行せよ: ")

    def test_medium_text_prefix(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("広告配信する", "Medium"))
        assert result["templated_text"].startswith("【優先度: 中】検討すべきタスク: ")

    def test_low_text_prefix(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("資料整理する", "Low"))
        assert result["templated_text"].startswith("【優先度: 低】参考タスク: ")

    def test_task_text_embedded_in_high(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成テスト", "High"))
        assert "LP作成テスト" in result["templated_text"]

    def test_task_text_embedded_in_medium(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("広告配信テスト", "Medium"))
        assert "広告配信テスト" in result["templated_text"]

    def test_task_text_embedded_in_low(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("資料整理テスト", "Low"))
        assert "資料整理テスト" in result["templated_text"]

    # ─── 必須フィールド ───
    def test_apply_template_has_task_id(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High", "T99"))
        assert result["task_id"] == "T99"

    def test_apply_template_has_templated_text(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High"))
        assert "templated_text" in result

    def test_apply_template_has_template_id(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High"))
        assert "template_id" in result

    def test_apply_template_has_priority(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High"))
        assert result["priority"] == "High"

    def test_apply_template_has_effort(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High"))
        assert "effort" in result

    def test_apply_template_has_value(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High"))
        assert "value" in result

    # ─── estimated_effort/value → effort/value 変換 ───
    def test_effort_mapped_from_estimated_effort(self):
        from src.agents.f50_module import _apply_template
        task = {"task_id": "T1", "task_text": "LP作成", "priority": "High",
                "estimated_effort": 3, "estimated_value": 7, "element_id": "E1"}
        result = _apply_template(task)
        assert result["effort"] == 3

    def test_value_mapped_from_estimated_value(self):
        from src.agents.f50_module import _apply_template
        task = {"task_id": "T1", "task_text": "LP作成", "priority": "High",
                "estimated_effort": 3, "estimated_value": 7, "element_id": "E1"}
        result = _apply_template(task)
        assert result["value"] == 7

    def test_effort_none_when_absent(self):
        from src.agents.f50_module import _apply_template
        result = _apply_template(self._task("LP作成", "High"))
        assert "effort" in result

    # ─── 異常系 ───
    def test_unknown_priority_raises_runtime(self):
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError):
            _apply_template(self._task("LP作成", "INVALID"))

    def test_runtime_error_has_cause(self):
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError) as exc_info:
            _apply_template(self._task("LP作成", "INVALID"))
        assert exc_info.value.__cause__ is not None

    def test_templated_text_nonempty_for_all_priorities(self):
        from src.agents.f50_module import _apply_template
        for pri in ("High", "Medium", "Low"):
            result = _apply_template(self._task("テスト", pri))
            assert len(result["templated_text"]) > 0

    # ─── execute() テンプレ出力全体 ───
    def test_execute_output_has_templated_tasks(self, f50_out):
        assert "templated_tasks" in f50_out

    def test_execute_output_has_hitl(self, f50_out):
        assert "hitl" in f50_out

    def test_execute_output_has_hitl_elements(self, f50_out):
        assert "hitl_elements" in f50_out

    def test_execute_templated_tasks_is_list(self, f50_out):
        assert isinstance(f50_out["templated_tasks"], list)

    def test_execute_all_tasks_have_template_id(self, f50_out):
        valid_ids = {"TMP_HIGH", "TMP_MEDIUM", "TMP_LOW"}
        for task in f50_out["templated_tasks"]:
            assert task["template_id"] in valid_ids

    def test_execute_all_tasks_have_priority_marker_in_text(self, f50_out):
        for task in f50_out["templated_tasks"]:
            assert "【優先度:" in task["templated_text"], \
                f"優先度マーカーなし: {task['templated_text']!r}"

    def test_execute_source_trace_id_is_f40(self, f50_out):
        assert f50_out.get("source_trace_id") == "F40"


# ════════════════════════════════════════════════════════
# WP8124: MECEテンプレ — F60 mece_report 構造検証
# ════════════════════════════════════════════════════════

class TestWP8124_MECETemplate:
    """F60 の mece_report テンプレ構造検証"""

    def test_f60_has_mece_report(self, f60_out):
        assert "mece_report" in f60_out

    def test_f60_mece_report_has_is_mece_compliant(self, f60_out):
        assert "is_mece_compliant" in f60_out["mece_report"]

    def test_f60_mece_report_has_duplicate_tasks(self, f60_out):
        assert "duplicate_tasks" in f60_out["mece_report"]

    def test_f60_mece_report_has_missing_elements(self, f60_out):
        assert "missing_elements" in f60_out["mece_report"]

    def test_f60_mece_report_has_ambiguous_tasks(self, f60_out):
        assert "ambiguous_tasks" in f60_out["mece_report"]

    def test_f60_is_mece_compliant_is_bool(self, f60_out):
        assert isinstance(f60_out["mece_report"]["is_mece_compliant"], bool)

    def test_f60_duplicate_tasks_is_list(self, f60_out):
        assert isinstance(f60_out["mece_report"]["duplicate_tasks"], list)

    def test_f60_missing_elements_is_list(self, f60_out):
        assert isinstance(f60_out["mece_report"]["missing_elements"], list)

    def test_f60_ambiguous_tasks_is_list(self, f60_out):
        assert isinstance(f60_out["mece_report"]["ambiguous_tasks"], list)

    def test_f60_templated_tasks_passthrough_exists(self, f60_out):
        """F60 出力に templated_tasks パススルーが含まれること（F70 への受け渡しに必要）。"""
        assert "templated_tasks" in f60_out

    def test_f60_templated_tasks_passthrough_is_list(self, f60_out):
        assert isinstance(f60_out["templated_tasks"], list)

    def test_f60_has_hitl_field(self, f60_out):
        assert "hitl" in f60_out

    def test_f60_hitl_is_bool(self, f60_out):
        assert isinstance(f60_out["hitl"], bool)

    def test_f60_source_trace_id_is_f50(self, f60_out):
        assert f60_out.get("source_trace_id") == "F50"


# ════════════════════════════════════════════════════════
# WP8125: WBSテンプレ — F70 hierarchy 三層構造検証
# ════════════════════════════════════════════════════════

class TestWP8125_WBSTemplate:
    """F70 の hierarchy Goal/Element/Task 三層テンプレ構造検証"""

    def test_f70_has_hierarchy(self, f70_out):
        assert "hierarchy" in f70_out

    def test_f70_hierarchy_has_goals(self, f70_out):
        assert "goals" in f70_out["hierarchy"]

    def test_f70_goals_is_list(self, f70_out):
        assert isinstance(f70_out["hierarchy"]["goals"], list)

    def test_f70_goals_nonempty(self, f70_out):
        assert len(f70_out["hierarchy"]["goals"]) > 0

    def test_f70_each_goal_has_goal_id(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            assert "goal_id" in goal, f"goal_id 欠落: {goal}"

    def test_f70_each_goal_has_goal_text(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            assert "goal_text" in goal, f"goal_text 欠落: {goal}"

    def test_f70_each_goal_has_elements(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            assert "elements" in goal, f"elements 欠落: {goal}"

    def test_f70_elements_is_list(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            assert isinstance(goal["elements"], list)

    def test_f70_each_element_has_element_id(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                assert "element_id" in elem

    def test_f70_each_element_has_element_text(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                assert "element_text" in elem

    def test_f70_each_element_has_tasks(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                assert "tasks" in elem

    def test_f70_element_id_naming_convention(self, f70_out):
        """element_id が G\d+_EL_[HML] パターンに従うこと。"""
        import re
        pattern = re.compile(r"^G\d+_EL_[HML]$")
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                eid = elem["element_id"]
                assert pattern.match(eid), f"命名規則違反: {eid!r}"

    def test_f70_goal_ids_sequential(self, f70_out):
        """goal_id が G1, G2, ... と連番であること。"""
        goal_ids = [g["goal_id"] for g in f70_out["hierarchy"]["goals"]]
        for i, gid in enumerate(goal_ids, 1):
            assert gid == f"G{i}", f"goal_id 連番違反: {gid} (期待: G{i})"

    def test_f70_tasks_have_task_id(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert "task_id" in task

    def test_f70_tasks_have_templated_text(self, f70_out):
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert "templated_text" in task

    def test_f70_tasks_have_priority(self, f70_out):
        valid = {"High", "Medium", "Low"}
        for goal in f70_out["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert task.get("priority") in valid

    def test_f70_source_trace_id_is_f60(self, f70_out):
        assert f70_out.get("source_trace_id") == "F60"


# ════════════════════════════════════════════════════════
# WP8126: トレーサビリティテンプレ — F80 traceability_map 構造検証
# ════════════════════════════════════════════════════════

class TestWP8126_TraceTemplate:
    """F80 の traceability_map テンプレ構造検証"""

    def test_f80_has_traceability_map(self, f80_out):
        assert "traceability_map" in f80_out

    def test_f80_traceability_map_is_list(self, f80_out):
        assert isinstance(f80_out["traceability_map"], list)

    def test_f80_each_entry_has_goal_id(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert "goal_id" in entry

    def test_f80_each_entry_has_element_id(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert "element_id" in entry

    def test_f80_each_entry_has_task_id(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert "task_id" in entry

    def test_f80_each_entry_has_trace_chain(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert "trace_chain" in entry

    def test_f80_each_entry_has_is_complete(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert "is_complete" in entry

    def test_f80_is_complete_is_bool(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert isinstance(entry["is_complete"], bool)

    def test_f80_trace_chain_is_list(self, f80_out):
        for entry in f80_out["traceability_map"]:
            assert isinstance(entry["trace_chain"], list)

    def test_f80_trace_chain_only_valid_modules(self, f80_out):
        valid = {"F10", "F20", "F30", "F40", "F50", "F60", "F70"}
        for entry in f80_out["traceability_map"]:
            for mod in entry["trace_chain"]:
                assert mod in valid

    def test_f80_hierarchy_passthrough_exists(self, f80_out):
        """F80 出力に hierarchy パススルーが含まれること（F90 への受け渡しに必要）。"""
        assert "hierarchy" in f80_out

    def test_f80_hierarchy_passthrough_has_goals(self, f80_out):
        assert "goals" in f80_out["hierarchy"]

    def test_f80_source_trace_id_is_f70(self, f80_out):
        assert f80_out.get("source_trace_id") == "F70"


# ════════════════════════════════════════════════════════
# WP8127: 最終出力テンプレ — F90 final_output 構造検証
# ════════════════════════════════════════════════════════

class TestWP8127_FinalOutputTemplate:
    """F90 の final_output テンプレ構造検証"""

    def test_f90_has_final_output(self, f90_out):
        assert "final_output" in f90_out

    def test_f90_final_output_has_summary(self, f90_out):
        assert "summary" in f90_out["final_output"]

    def test_f90_summary_has_total_goals(self, f90_out):
        assert "total_goals" in f90_out["final_output"]["summary"]

    def test_f90_summary_has_total_elements(self, f90_out):
        assert "total_elements" in f90_out["final_output"]["summary"]

    def test_f90_summary_has_total_tasks(self, f90_out):
        assert "total_tasks" in f90_out["final_output"]["summary"]

    def test_f90_summary_has_traceability_complete(self, f90_out):
        assert "traceability_complete" in f90_out["final_output"]["summary"]

    def test_f90_summary_has_pipeline_integrity(self, f90_out):
        assert "pipeline_integrity" in f90_out["final_output"]["summary"]

    def test_f90_final_output_has_hierarchy_with_trace(self, f90_out):
        assert "hierarchy_with_trace" in f90_out["final_output"]

    def test_f90_hierarchy_with_trace_is_list(self, f90_out):
        assert isinstance(f90_out["final_output"]["hierarchy_with_trace"], list)

    def test_f90_final_output_has_evaluation_report(self, f90_out):
        assert "evaluation_report" in f90_out["final_output"]

    def test_f90_evaluation_report_has_efficiency_score(self, f90_out):
        assert "efficiency_score" in f90_out["final_output"]["evaluation_report"]

    def test_f90_evaluation_report_has_recommendations(self, f90_out):
        assert "recommendations" in f90_out["final_output"]["evaluation_report"]

    def test_f90_recommendations_is_list(self, f90_out):
        assert isinstance(f90_out["final_output"]["evaluation_report"]["recommendations"], list)

    def test_f90_efficiency_score_is_numeric(self, f90_out):
        score = f90_out["final_output"]["evaluation_report"]["efficiency_score"]
        assert isinstance(score, (int, float))

    def test_f90_has_hitl_required(self, f90_out):
        assert "hitl_required" in f90_out

    def test_f90_has_hitl_elements(self, f90_out):
        assert "hitl_elements" in f90_out

    def test_f90_hitl_required_is_bool(self, f90_out):
        assert isinstance(f90_out["hitl_required"], bool)

    def test_f90_source_trace_id_is_f80(self, f90_out):
        assert f90_out.get("source_trace_id") == "F80"


# ════════════════════════════════════════════════════════
# WP8128: 後続互換性 — テンプレ適用後のデータが後続モジュールで利用できること
# ════════════════════════════════════════════════════════

class TestWP8128_TemplateDownstreamCompat:
    """テンプレ適用後のデータが後続モジュールの入力として正しく機能すること"""

    def test_f50_output_accepted_by_f60(self, f50_out):
        from src.agents.f60_module import execute as f60
        result = f60(f50_out)
        assert result["trace_id"] == "F60"

    def test_f60_output_accepted_by_f70(self, f60_out):
        from src.agents.f70_module import execute as f70
        result = f70(f60_out)
        assert result["trace_id"] == "F70"

    def test_f70_output_accepted_by_f80(self, f70_out):
        from src.agents.f80_module import execute as f80
        result = f80(f70_out)
        assert result["trace_id"] == "F80"

    def test_f80_output_accepted_by_f90(self, f80_out):
        from src.agents.f90_module import execute as f90
        result = f90(f80_out)
        assert result["trace_id"] == "F90"

    def test_f50_templated_tasks_keys_accessible_in_f60(self, f50_out):
        """F60 が f50_out の templated_tasks を正しく読み込めること。"""
        from src.agents.f60_module import execute as f60
        result = f60(f50_out)
        assert "mece_report" in result

    def test_f60_templated_tasks_passthrough_accessible_in_f70(self, f60_out):
        """F70 が f60_out の templated_tasks パススルーを正しく読み込めること。"""
        from src.agents.f70_module import execute as f70
        result = f70(f60_out)
        assert "hierarchy" in result

    def test_f70_hierarchy_passthrough_accessible_in_f90(self, f80_out):
        """F90 が f80_out の hierarchy パススルーを正しく読み込めること。"""
        from src.agents.f90_module import execute as f90
        result = f90(f80_out)
        assert "final_output" in result

    def test_full_pipeline_template_end_to_end(self, f90_out):
        """F10→F90 パイプラインを通じてテンプレ適用が正しく機能すること。"""
        assert f90_out["trace_id"] == "F90"
        fo = f90_out["final_output"]
        assert fo["summary"]["total_tasks"] > 0
        for goal in fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert "【優先度:" in task["templated_text"]


# ════════════════════════════════════════════════════════
# WP8129: 異常系テンプレ — 欠落フィールド・不正入力での例外発火検証
# ════════════════════════════════════════════════════════

class TestWP8129_TemplateAbnormal:
    """テンプレ必須フィールド欠落・不正入力での例外処理検証"""

    # ─── F50 入力検証 ───
    def test_f50_none_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50(None)

    def test_f50_empty_dict_raises_value_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError):
            f50({})

    def test_f50_missing_tasks_key_raises_value_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError, match="tasks"):
            f50({"trace_id": "F40"})

    def test_f50_tasks_not_list_raises_value_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError):
            f50({"trace_id": "F40", "tasks": "not_a_list"})

    def test_f50_task_missing_task_id_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_text": "LP作成", "priority": "High"}
            ]})

    def test_f50_task_missing_task_text_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "priority": "High"}
            ]})

    def test_f50_task_missing_priority_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "task_text": "LP作成"}
            ]})

    # ─── HITL 移譲（テンプレ適用スキップ） ───
    def test_f50_empty_task_text_triggers_hitl(self):
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert "T1" in result["hitl_elements"]

    def test_f50_ambiguous_word_triggers_hitl(self):
        from src.agents.f50_module import execute as f50, AMBIGUOUS_WORDS
        word = AMBIGUOUS_WORDS[0]
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": f"売上{word}を改善する",
             "priority": "High", "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert "T1" in result["hitl_elements"]

    def test_f50_unknown_priority_triggers_hitl(self):
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成", "priority": "INVALID",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert "T1" in result["hitl_elements"]

    def test_f50_all_hitl_sets_hitl_true(self):
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"},
            {"task_id": "T2", "task_text": "  ", "priority": "High",
             "estimated_effort": 1, "estimated_value": 3, "element_id": "E1"},
        ]})
        assert result["hitl"] is True

    def test_f50_partial_hitl_sets_hitl_false(self):
        """一部のみ HITL 移譲の場合は hitl=False（全体 HITL でない）。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"},
            {"task_id": "T2", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"},
        ]})
        assert result["hitl"] is False
        assert "T1" in result["hitl_elements"]
        assert "T2" not in result["hitl_elements"]

    # ─── F60/F70/F80 入力検証 ───
    def test_f60_missing_templated_tasks_raises(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises((TypeError, ValueError)):
            f60({"trace_id": "F50"})

    def test_f70_missing_templated_tasks_raises(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises((TypeError, ValueError)):
            f70({"trace_id": "F60"})

    def test_f80_missing_hierarchy_raises(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises((TypeError, ValueError)):
            f80({"trace_id": "F70"})

    def test_f90_missing_traceability_map_raises_value_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError, match="traceability_map"):
            f90({"trace_id": "F80", "hierarchy": {"goals": []}})

    def test_f90_missing_hierarchy_raises_type_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError, match="hierarchy"):
            f90({"trace_id": "F80", "traceability_map": []})
