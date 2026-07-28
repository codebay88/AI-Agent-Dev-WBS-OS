"""Phase 4 — WP8220 例外処理テスト
区分：例外クラス / メッセージ / 伝播 / ログ / HITL / 処理継続

WP8220 の観点：
  - 全 F モジュールで異常系入力に対して仕様書どおりの例外クラスが発火すること
  - 例外メッセージに原因情報が含まれること
  - RuntimeError の __cause__ チェーンが保持されること
  - HITL 承認フローが例外境界で正しく発動すること
  - 例外発生後も他のモジュールが独立して正常動作すること
  - WARNING ログが処理継続ケースで正しく出力されること
"""

import pytest
import logging


# ════════════════════════════════════════════════════════
# 共通ヘルパ
# ════════════════════════════════════════════════════════

_MOCK_API = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


def _f10_out(mocker):
    mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
    from src.agents.f10_module import execute as f10
    return f10({"goal_text": "売上を前年比120%に成長させる"})


# ════════════════════════════════════════════════════════
# WP8221: F10 例外処理
# ════════════════════════════════════════════════════════

class TestWP8221_F10Exceptions:
    """F10 の例外処理仕様検証"""

    # ─── TypeError / ValueError 発火条件 ───
    def test_none_raises_value_error(self):
        """F10 仕様: None → ValueError（dict 形式必須チェックで先に検出）。"""
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10(None)

    def test_string_raises_value_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10("goal_text")

    def test_list_raises_value_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10(["goal_text"])

    def test_empty_dict_raises_value_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10({})

    def test_missing_goal_text_raises_value_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError, match="goal_text"):
            f10({"not_goal_text": "テスト"})

    def test_empty_goal_text_raises_value_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10({"goal_text": ""})

    def test_goal_text_not_string_raises_value_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises((ValueError, TypeError)):
            f10({"goal_text": 123})

    # ─── API 失敗 → HITL 移譲（F10 は RuntimeError を上位に伝播せず HITL に変換する）───
    def test_api_failure_returns_hitl(self, mocker):
        """F10 仕様: API 失敗は RuntimeError ではなく HITL 移譲として返ること。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=RuntimeError("API 呼び出し失敗")
        )
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "テスト目標"})
        assert result["hitl"] is True

    def test_invalid_json_from_api_returns_hitl(self, mocker):
        """F10 仕様: 不正 JSON 応答は RuntimeError ではなく HITL 移譲として返ること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value="NOT_JSON")
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "テスト目標"})
        assert result["hitl"] is True


# ════════════════════════════════════════════════════════
# WP8222: F20 例外処理
# ════════════════════════════════════════════════════════

class TestWP8222_F20Exceptions:
    """F20 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(TypeError):
            f20(None)

    def test_string_raises_type_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(TypeError):
            f20("invalid")

    def test_empty_dict_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError):
            f20({})

    def test_missing_goal_key_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError, match="goal"):
            f20({"trace_id": "F10"})

    def test_missing_goal_l1_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError, match="L1"):
            f20({"trace_id": "F10", "goal": {"L2": [], "L3": []}})

    def test_missing_goal_l2_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError, match="L2"):
            f20({"trace_id": "F10", "goal": {"L1": "テスト", "L3": []}})

    def test_missing_goal_l3_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError, match="L3"):
            f20({"trace_id": "F10", "goal": {"L1": "テスト", "L2": []}})

    def test_goal_l1_not_string_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError):
            f20({"trace_id": "F10", "goal": {"L1": 123, "L2": [], "L3": []}})

    def test_goal_l2_not_list_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError):
            f20({"trace_id": "F10", "goal": {"L1": "テスト", "L2": "not_list", "L3": []}})

    def test_goal_l3_not_list_raises_value_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError):
            f20({"trace_id": "F10", "goal": {"L1": "テスト", "L2": [], "L3": "not_list"}})

    def test_unknown_trace_id_continues_with_warning(self, caplog):
        """trace_id が F10 以外でも処理継続すること。"""
        from src.agents.f20_module import execute as f20
        data = {"trace_id": "UNKNOWN", "goal": {
            "L1": "テスト目標", "L2": ["施策A"], "L3": ["タスク1"]
        }}
        with caplog.at_level(logging.WARNING, logger="src.agents.f20_module"):
            result = f20(data)
        assert result["trace_id"] == "F20"


# ════════════════════════════════════════════════════════
# WP8223: F30 例外処理
# ════════════════════════════════════════════════════════

class TestWP8223_F30Exceptions:
    """F30 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(TypeError):
            f30(None)

    def test_empty_dict_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError):
            f30({})

    def test_missing_expanded_goals_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="expanded_goals"):
            f30({"trace_id": "F20"})

    def test_expanded_goals_not_list_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError):
            f30({"trace_id": "F20", "expanded_goals": "not_list"})

    def test_element_missing_text_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="text"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"element_id": "E1", "parent": "L1"}  # text 欠落
            ]})

    def test_element_missing_parent_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="parent"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"element_id": "E1", "text": "テスト"}  # parent 欠落
            ]})

    def test_element_missing_element_id_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="element_id"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"text": "テスト", "parent": "L1"}  # element_id 欠落
            ]})

    def test_element_not_dict_raises_value_error(self):
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError):
            f30({"trace_id": "F20", "expanded_goals": ["not_a_dict"]})

    def test_empty_goals_returns_empty_evaluated(self):
        """expanded_goals が空でも例外にならないこと（空出力を返す）。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": []})
        assert result["evaluated_goals"] == []


# ════════════════════════════════════════════════════════
# WP8224: F40 例外処理
# ════════════════════════════════════════════════════════

class TestWP8224_F40Exceptions:
    """F40 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(TypeError):
            f40(None)

    def test_empty_dict_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({})

    def test_missing_evaluated_goals_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError, match="evaluated_goals"):
            f40({"trace_id": "F30"})

    def test_evaluated_goals_not_list_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({"trace_id": "F30", "evaluated_goals": {}})

    def test_element_missing_element_id_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({"trace_id": "F30", "evaluated_goals": [
                {"priority": "High", "score_importance": 0.8, "score_feasibility": 0.7}
            ]})

    def test_element_missing_priority_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({"trace_id": "F30", "evaluated_goals": [
                {"element_id": "E1", "score_importance": 0.8, "score_feasibility": 0.7}
            ]})

    def test_element_missing_score_importance_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({"trace_id": "F30", "evaluated_goals": [
                {"element_id": "E1", "priority": "High", "score_feasibility": 0.7}
            ]})

    def test_element_not_dict_raises_value_error(self):
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({"trace_id": "F30", "evaluated_goals": ["not_a_dict"]})

    def test_empty_goals_returns_empty_tasks(self):
        """evaluated_goals が空でも例外にならないこと。"""
        from src.agents.f40_module import execute as f40
        result = f40({"trace_id": "F30", "evaluated_goals": []})
        assert result["tasks"] == []


# ════════════════════════════════════════════════════════
# WP8225: F50 例外処理
# ════════════════════════════════════════════════════════

class TestWP8225_F50Exceptions:
    """F50 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50(None)

    def test_list_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50([{"task_id": "T1"}])

    def test_empty_dict_raises_value_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError):
            f50({})

    def test_missing_tasks_raises_value_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError, match="tasks"):
            f50({"trace_id": "F40"})

    def test_tasks_not_list_raises_value_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError):
            f50({"trace_id": "F40", "tasks": "not_list"})

    def test_task_missing_task_id_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_text": "LP作成", "priority": "High"}
            ]})

    def test_task_missing_task_text_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "priority": "High"}
            ]})

    def test_task_missing_priority_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "task_text": "LP作成"}
            ]})

    def test_task_not_dict_raises_type_error(self):
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": ["not_a_dict"]})

    # ─── RuntimeError + __cause__ 保持 ───
    def test_unknown_priority_raises_runtime_with_cause(self):
        """不正 priority でテンプレ適用が失敗 → RuntimeError(__cause__ 保持）。"""
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError) as exc_info:
            _apply_template({
                "task_id": "T1", "task_text": "LP作成",
                "priority": "INVALID", "estimated_effort": 2, "estimated_value": 4
            })
        assert exc_info.value.__cause__ is not None

    def test_runtime_error_message_contains_task_id(self):
        """RuntimeError メッセージに task_id が含まれること。"""
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError) as exc_info:
            _apply_template({
                "task_id": "T_ERROR", "task_text": "LP作成",
                "priority": "INVALID", "estimated_effort": 2, "estimated_value": 4
            })
        assert "T_ERROR" in str(exc_info.value)

    def test_empty_tasks_returns_empty_templated(self):
        """tasks が空でも例外にならないこと（WARNING のみ）。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": []})
        assert result["templated_tasks"] == []


# ════════════════════════════════════════════════════════
# WP8226: F60 例外処理
# ════════════════════════════════════════════════════════

class TestWP8226_F60Exceptions:
    """F60 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60(None)

    def test_integer_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60(42)

    def test_empty_dict_raises_value_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError):
            f60({})

    def test_missing_templated_tasks_raises_value_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError, match="templated_tasks"):
            f60({"trace_id": "F50"})

    def test_templated_tasks_not_list_raises_value_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError):
            f60({"trace_id": "F50", "templated_tasks": {}})

    def test_task_not_dict_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": ["not_a_dict"]})

    def test_task_missing_task_id_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": [
                {"templated_text": "LP作成", "priority": "High"}
            ]})

    def test_task_missing_templated_text_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": [
                {"task_id": "T1", "priority": "High"}
            ]})

    def test_task_missing_priority_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": [
                {"task_id": "T1", "templated_text": "LP作成"}
            ]})

    def test_empty_templated_tasks_returns_hitl(self):
        """templated_tasks が空 → HITL（例外ではなく hitl_required=True）。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert result["hitl_required"] is True
        assert result.get("hitl_reason") == "No tasks provided"

    def test_cosine_runtime_error_has_cause(self):
        """cosine 計算失敗時に RuntimeError(__cause__ 保持）が発火すること。"""
        from src.agents.f60_module import _cosine_similarity
        from unittest.mock import patch
        with patch("src.agents.f60_module.math.sqrt", side_effect=OverflowError("overflow")):
            with pytest.raises(RuntimeError) as exc_info:
                _cosine_similarity("LP作成 広告配信", "LP作成 広告配信")
        assert exc_info.value.__cause__ is not None


# ════════════════════════════════════════════════════════
# WP8227: F70 例外処理
# ════════════════════════════════════════════════════════

class TestWP8227_F70Exceptions:
    """F70 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(TypeError):
            f70(None)

    def test_empty_dict_raises_value_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(ValueError):
            f70({})

    def test_missing_templated_tasks_raises_value_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(ValueError, match="templated_tasks"):
            f70({"trace_id": "F60"})

    def test_templated_tasks_not_list_raises_value_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(ValueError):
            f70({"trace_id": "F60", "templated_tasks": "not_list"})

    def test_task_not_dict_raises_type_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(TypeError):
            f70({"trace_id": "F60", "templated_tasks": ["not_a_dict"]})

    def test_task_missing_task_id_raises_type_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(TypeError):
            f70({"trace_id": "F60", "templated_tasks": [
                {"templated_text": "LP作成", "priority": "High"}
            ]})

    def test_task_missing_priority_raises_type_error(self):
        from src.agents.f70_module import execute as f70
        with pytest.raises(TypeError):
            f70({"trace_id": "F60", "templated_tasks": [
                {"task_id": "T1", "templated_text": "LP作成"}
            ]})

    def test_empty_templated_tasks_returns_hitl(self):
        """templated_tasks が空 → HITL（例外ではなく hitl_required=True）。"""
        from src.agents.f70_module import execute as f70
        result = f70({"trace_id": "F60", "templated_tasks": []})
        assert result.get("hitl_required") is True


# ════════════════════════════════════════════════════════
# WP8228: F80 例外処理
# ════════════════════════════════════════════════════════

class TestWP8228_F80Exceptions:
    """F80 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(TypeError):
            f80(None)

    def test_empty_dict_raises_value_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError):
            f80({})

    def test_missing_hierarchy_raises_value_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError, match="hierarchy"):
            f80({"trace_id": "F70"})

    def test_hierarchy_not_dict_raises_value_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError):
            f80({"trace_id": "F70", "hierarchy": "not_dict"})

    def test_hierarchy_missing_goals_raises_value_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError, match="goals"):
            f80({"trace_id": "F70", "hierarchy": {}})

    def test_hierarchy_goals_not_list_raises_value_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError):
            f80({"trace_id": "F70", "hierarchy": {"goals": "not_list"}})

    def test_goal_not_dict_raises_type_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(TypeError):
            f80({"trace_id": "F70", "hierarchy": {"goals": ["not_a_dict"]}})

    def test_goal_missing_goal_id_raises_type_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(TypeError):
            f80({"trace_id": "F70", "hierarchy": {"goals": [
                {"elements": []}
            ]}})

    def test_goal_missing_elements_raises_type_error(self):
        from src.agents.f80_module import execute as f80
        with pytest.raises(TypeError):
            f80({"trace_id": "F70", "hierarchy": {"goals": [
                {"goal_id": "G1"}
            ]}})

    def test_empty_goals_returns_hitl(self):
        """hierarchy.goals が空 → HITL（例外ではなく hitl_required=True）。"""
        from src.agents.f80_module import execute as f80
        result = f80({"trace_id": "F70", "hierarchy": {"goals": []}})
        assert result.get("hitl_required") is True


# ════════════════════════════════════════════════════════
# WP8229: F90 例外処理
# ════════════════════════════════════════════════════════

class TestWP8229_F90Exceptions:
    """F90 の例外処理仕様検証"""

    def test_none_raises_type_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError):
            f90(None)

    def test_empty_dict_raises_value_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError):
            f90({})

    def test_missing_traceability_map_raises_value_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError, match="traceability_map"):
            f90({"trace_id": "F80", "hierarchy": {"goals": []}})

    def test_traceability_map_not_list_raises_value_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError):
            f90({"trace_id": "F80",
                 "traceability_map": "not_list",
                 "hierarchy": {"goals": []}})

    def test_missing_hierarchy_raises_type_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError, match="hierarchy"):
            f90({"trace_id": "F80", "traceability_map": []})

    def test_hierarchy_not_dict_raises_type_error(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError):
            f90({"trace_id": "F80",
                 "traceability_map": [],
                 "hierarchy": "not_dict"})

    def test_zero_effort_raises_runtime_with_cause(self):
        """effort=None → ZeroDivisionError → RuntimeError(__cause__ 保持）。"""
        from src.agents.f90_module import _compute_evaluation
        hw = [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "x",
             "priority": "High", "effort": None, "value": None}
        ]}]}]
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation(hw)
        assert isinstance(exc_info.value.__cause__, ZeroDivisionError)

    def test_compute_evaluation_runtime_cause_is_zero_division(self):
        """RuntimeError の __cause__ が ZeroDivisionError であること（型検証）。"""
        from src.agents.f90_module import _compute_evaluation
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation([{"elements": [{"tasks": [
                {"task_id": "T1", "templated_text": "x",
                 "priority": "High", "effort": 0, "value": 5}
            ]}]}])
        assert exc_info.value.__cause__ is not None

    def test_empty_tmap_returns_hitl(self):
        """traceability_map が空 → HITL（例外ではなく hitl_required=True）。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert result["hitl_required"] is True
        assert result.get("hitl_reason") == "No tasks to finalize"


# ════════════════════════════════════════════════════════
# WP822A: 例外伝播 — パイプライン内での例外連鎖
# ════════════════════════════════════════════════════════

class TestWP822A_ExceptionPropagation:
    """例外が上位モジュールに正しく伝播すること"""

    def test_f10_exception_propagates_without_swallowing(self, mocker):
        """F10 の ValueError が呼び出し元に正しく伝播すること。"""
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10({"goal_text": ""})

    def test_f20_exception_propagates_from_f10_output(self, mocker):
        """F10 出力を壊してから F20 に渡すと ValueError が発火すること。"""
        r10 = _f10_out(mocker)
        del r10["goal"]
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError, match="goal"):
            f20(r10)

    def test_f30_exception_propagates_from_f20_output(self, mocker):
        """F20 出力を壊してから F30 に渡すと ValueError が発火すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        r20 = f20(f10({"goal_text": "売上を前年比120%に成長させる"}))
        del r20["expanded_goals"]
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="expanded_goals"):
            f30(r20)

    def test_f40_exception_propagates_from_f30_output(self, mocker):
        """F30 出力を壊してから F40 に渡すと ValueError が発火すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        r30 = f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))
        del r30["evaluated_goals"]
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError, match="evaluated_goals"):
            f40(r30)

    def test_f50_exception_propagates_from_f40_output(self, mocker):
        """F40 出力を壊してから F50 に渡すと ValueError が発火すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        r40 = f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))
        del r40["tasks"]
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError, match="tasks"):
            f50(r40)

    def test_f60_exception_propagates_from_f50_output(self, mocker):
        """F50 出力を壊してから F60 に渡すと ValueError が発火すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        r50 = f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))
        del r50["templated_tasks"]
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError, match="templated_tasks"):
            f60(r50)

    def test_f80_exception_propagates_from_f70_output(self, mocker):
        """F70 出力を壊してから F80 に渡すと ValueError が発火すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        r70 = f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))))
        del r70["hierarchy"]
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError, match="hierarchy"):
            f80(r70)

    def test_f90_exception_propagates_from_f80_output(self, mocker):
        """F80 出力を壊してから F90 に渡すと ValueError が発火すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        r80 = f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))))))
        del r80["traceability_map"]
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError, match="traceability_map"):
            f90(r80)

    def test_exception_does_not_affect_independent_module(self, mocker):
        """F30 で例外が起きても、F50 は別の入力で正常動作すること。"""
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError):
            f30({"trace_id": "F20", "expanded_goals": "bad_input"})
        # F50 は独立して正常動作すること
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成",
             "priority": "High", "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert result["trace_id"] == "F50"


# ════════════════════════════════════════════════════════
# WP822B: 例外クラス別整合性 — TypeError/ValueError/RuntimeError の使い分け
# ════════════════════════════════════════════════════════

class TestWP822B_ExceptionClassConsistency:
    """例外クラスが仕様書どおりに使い分けられていること"""

    @pytest.mark.parametrize("mod_name,none_exc", [
        ("f20_module", TypeError),
        ("f30_module", TypeError),
        ("f40_module", TypeError),
        ("f50_module", TypeError),
        ("f60_module", TypeError),
        ("f70_module", TypeError),
        ("f80_module", TypeError),
        ("f90_module", TypeError),
    ])
    def test_none_input_exception_class(self, mod_name, none_exc):
        """None 入力で発火する例外クラスが仕様どおりであること。"""
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises(none_exc):
            mod.execute(None)

    @pytest.mark.parametrize("mod_name", [
        "f20_module", "f30_module", "f40_module", "f50_module",
        "f60_module", "f70_module", "f80_module", "f90_module",
    ])
    def test_empty_dict_raises_value_error(self, mod_name):
        """空 dict で発火する例外は ValueError であること。"""
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises(ValueError):
            mod.execute({})

    @pytest.mark.parametrize("mod_name", [
        "f20_module", "f30_module", "f40_module", "f50_module",
        "f60_module", "f70_module", "f80_module",
    ])
    def test_missing_primary_key_raises_value_error(self, mod_name):
        """必須キー欠落（trace_id のみの dict）で ValueError が発火すること。"""
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises((ValueError, TypeError)):
            mod.execute({"trace_id": "DUMMY"})

    def test_f50_apply_template_raises_runtime_not_key_error(self):
        """F50 _apply_template は KeyError を RuntimeError にラップすること。"""
        from src.agents.f50_module import _apply_template
        exc_type = None
        try:
            _apply_template({"task_id": "T1", "task_text": "x", "priority": "UNKNOWN"})
        except RuntimeError:
            exc_type = RuntimeError
        except KeyError:
            exc_type = KeyError
        assert exc_type is RuntimeError, "KeyError が RuntimeError にラップされていない"

    def test_f90_compute_evaluation_wraps_zero_div_as_runtime(self):
        """F90 _compute_evaluation は ZeroDivisionError を RuntimeError にラップすること。"""
        from src.agents.f90_module import _compute_evaluation
        exc_type = None
        try:
            _compute_evaluation([{"elements": [{"tasks": [
                {"task_id": "T1", "templated_text": "x",
                 "priority": "High", "effort": None, "value": None}
            ]}]}])
        except RuntimeError:
            exc_type = RuntimeError
        except ZeroDivisionError:
            exc_type = ZeroDivisionError
        assert exc_type is RuntimeError, "ZeroDivisionError が RuntimeError にラップされていない"


# ════════════════════════════════════════════════════════
# WP822C: WARNING 継続 — 例外にならず処理継続するケース
# ════════════════════════════════════════════════════════

class TestWP822C_WarningContinuation:
    """WARNING で処理継続するケース（例外にならないこと）の検証"""

    def test_f20_wrong_trace_id_continues(self, caplog):
        from src.agents.f20_module import execute as f20
        data = {"trace_id": "WRONG", "goal": {
            "L1": "テスト", "L2": ["施策A"], "L3": ["タスク1"]
        }}
        with caplog.at_level(logging.WARNING, logger="src.agents.f20_module"):
            result = f20(data)
        assert result["trace_id"] == "F20"
        assert any("WRONG" in r.message for r in caplog.records)

    def test_f30_wrong_trace_id_continues(self):
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "WRONG", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成", "parent": "L3"}
        ]})
        assert result["trace_id"] == "F30"

    def test_f40_wrong_trace_id_continues(self):
        from src.agents.f40_module import execute as f40
        result = f40({"trace_id": "WRONG", "evaluated_goals": [
            {"element_id": "E1", "text": "テスト", "parent": "L3",
             "priority": "High", "score_importance": 0.8, "score_feasibility": 0.7}
        ]})
        assert result["trace_id"] == "F40"

    def test_f50_wrong_trace_id_continues(self):
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "WRONG", "tasks": [
            {"task_id": "T1", "task_text": "LP作成", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert result["trace_id"] == "F50"

    def test_f50_duplicate_task_id_continues(self):
        """重複 task_id でも WARNING のみで処理継続すること。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"},
            {"task_id": "T1", "task_text": "広告配信", "priority": "Medium",
             "estimated_effort": 3, "estimated_value": 5, "element_id": "E2"},
        ]})
        assert result["trace_id"] == "F50"

    def test_f60_wrong_trace_id_continues(self):
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "WRONG", "templated_tasks": [
            {"task_id": "T1", "templated_text": "LP作成", "priority": "High"}
        ]})
        assert result["trace_id"] == "F60"

    def test_f60_duplicate_task_id_continues(self):
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            {"task_id": "T1", "templated_text": "LP作成 A", "priority": "High"},
            {"task_id": "T1", "templated_text": "LP作成 B", "priority": "High"},
        ]})
        assert result["trace_id"] == "F60"

    def test_f90_wrong_trace_id_continues(self):
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "WRONG",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert result["trace_id"] == "F90"

    def test_f50_invalid_priority_in_task_continues(self):
        """tasks に不正 priority があっても全体例外にならず処理継続すること
        （該当タスクは HITL 移譲）。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成", "priority": "INVALID",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"},
            {"task_id": "T2", "task_text": "広告配信", "priority": "High",
             "estimated_effort": 1, "estimated_value": 3, "element_id": "E2"},
        ]})
        assert result["trace_id"] == "F50"
        assert "T1" in result["hitl_elements"]
        assert len(result["templated_tasks"]) == 1
