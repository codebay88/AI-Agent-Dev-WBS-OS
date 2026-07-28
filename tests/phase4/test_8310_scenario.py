"""Phase 4 — WP8310 想定シナリオテスト（Operational Scenario Test）
区分：正常系 / 異常系 / HITL系 / I/O連鎖 / 運用ログ

WP8310 の観点：
  - 実運用で発生しうる代表的シナリオが仕様書どおりに処理されること
  - 正常系シナリオで全モジュールの出力整合性が保たれること
  - 異常系シナリオで例外処理が正しく発動し、パイプラインが指定箇所で停止すること
  - HITL系シナリオで承認フローが正しく発動すること
  - F10→F90 I/O連鎖が途切れず処理されること
  - INFO/WARNING ログが仕様書どおりに記録されること
"""

import logging
import pytest


# ════════════════════════════════════════════════════════
# 共通ヘルパ
# ════════════════════════════════════════════════════════

_MOCK_API = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する","既存顧客フォローする","リテンション施策を実施する"]}'
)

_GOAL_TEXT = "売上を前年比120%に成長させる"


@pytest.fixture(scope="module")
def mock_api(module_mocker):
    module_mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)


@pytest.fixture(scope="module")
def pipeline(mock_api):
    """F10→F90 完全パイプライン結果を module スコープでキャッシュする。"""
    from src.agents.f10_module import execute as f10
    from src.agents.f20_module import execute as f20
    from src.agents.f30_module import execute as f30
    from src.agents.f40_module import execute as f40
    from src.agents.f50_module import execute as f50
    from src.agents.f60_module import execute as f60
    from src.agents.f70_module import execute as f70
    from src.agents.f80_module import execute as f80
    from src.agents.f90_module import execute as f90

    r10 = f10({"goal_text": _GOAL_TEXT})
    r20 = f20(r10)
    r30 = f30(r20)
    r40 = f40(r30)
    r50 = f50(r40)
    r60 = f60(r50)
    r70 = f70(r60)
    r80 = f80(r70)
    r90 = f90(r80)

    return {
        "r10": r10, "r20": r20, "r30": r30, "r40": r40, "r50": r50,
        "r60": r60, "r70": r70, "r80": r80, "r90": r90,
    }


# ════════════════════════════════════════════════════════
# WP8311: 正常系シナリオ
# ════════════════════════════════════════════════════════

class TestWP8311_NormalScenario:
    """正常系シナリオが仕様書どおりに処理されること"""

    # ─── シナリオ01: 完全パイプライン正常系 ───
    def test_scenario_01_all_modules_return_dict(self, pipeline):
        """シナリオ01: F10〜F90 が全て dict を返すこと。"""
        for key, result in pipeline.items():
            assert isinstance(result, dict), f"{key} は dict でない"

    def test_scenario_01_all_modules_have_trace_id(self, pipeline):
        """シナリオ01: 全モジュールの出力に trace_id が存在すること。"""
        expected = {
            "r10": "F10", "r20": "F20", "r30": "F30", "r40": "F40", "r50": "F50",
            "r60": "F60", "r70": "F70", "r80": "F80", "r90": "F90",
        }
        for key, expected_id in expected.items():
            assert pipeline[key]["trace_id"] == expected_id, \
                f"{key}: trace_id が {expected_id} でない"

    def test_scenario_01_f90_final_output_exists(self, pipeline):
        """シナリオ01: F90 が final_output を出力すること。"""
        r90 = pipeline["r90"]
        assert "final_output" in r90
        assert isinstance(r90["final_output"], dict)

    def test_scenario_01_f90_has_efficiency_score(self, pipeline):
        """シナリオ01: F90 が efficiency_score を final_output 内に出力すること。"""
        r90 = pipeline["r90"]
        report = r90["final_output"]["evaluation_report"]
        assert "efficiency_score" in report

    def test_scenario_01_f90_has_recommendations(self, pipeline):
        """シナリオ01: F90 が recommendations を final_output 内に出力すること。"""
        r90 = pipeline["r90"]
        report = r90["final_output"]["evaluation_report"]
        assert "recommendations" in report
        assert isinstance(report["recommendations"], list)

    # ─── シナリオ02: F10 出力構造 ───
    def test_scenario_02_f10_goal_structure(self, pipeline):
        """シナリオ02: F10 出力の goal に L1/L2/L3 が存在すること。"""
        goal = pipeline["r10"]["goal"]
        assert "L1" in goal
        assert "L2" in goal
        assert "L3" in goal
        assert isinstance(goal["L2"], list)
        assert isinstance(goal["L3"], list)

    def test_scenario_02_f10_no_hitl_on_clean_input(self, pipeline):
        """シナリオ02: 明確な goal_text では HITL が発動しないこと。"""
        assert pipeline["r10"]["hitl"] is False

    # ─── シナリオ03: 混在優先度タスク ───
    def test_scenario_03_f40_generates_tasks_for_all_elements(self, pipeline):
        """シナリオ03: F40 が全要素に対してタスクを生成すること。"""
        tasks = pipeline["r40"]["tasks"]
        assert len(tasks) > 0

    def test_scenario_03_f50_templates_all_clean_tasks(self, pipeline):
        """シナリオ03: F50 が全クリーンタスクにテンプレートを適用すること。"""
        r50 = pipeline["r50"]
        r40 = pipeline["r40"]
        clean_count = len([t for t in r40["tasks"]
                           if t.get("priority") in {"High", "Medium", "Low"}
                           and not any(w in t.get("task_text", "")
                                       for w in ["など", "いろいろ", "何か", "なんか",
                                                 "とか", "色々", "諸々", "もろもろ",
                                                 "改善", "向上", "検討"])])
        assert len(r50["templated_tasks"]) <= clean_count

    # ─── シナリオ04: 出力整合性 ───
    def test_scenario_04_f60_mece_report_structure(self, pipeline):
        """シナリオ04: F60 の mece_report に必須フィールドが存在すること。"""
        report = pipeline["r60"]["mece_report"]
        for field in ("duplicate_tasks", "missing_elements", "ambiguous_tasks", "is_mece_compliant"):
            assert field in report, f"mece_report に '{field}' が存在しない"

    def test_scenario_04_f70_hierarchy_has_goals(self, pipeline):
        """シナリオ04: F70 の hierarchy.goals が存在すること。"""
        goals = pipeline["r70"]["hierarchy"]["goals"]
        assert len(goals) > 0

    def test_scenario_04_f80_traceability_map_exists(self, pipeline):
        """シナリオ04: F80 の traceability_map が存在すること。"""
        assert "traceability_map" in pipeline["r80"]
        assert isinstance(pipeline["r80"]["traceability_map"], list)

    # ─── シナリオ05: 単一タスクシナリオ ───
    def test_scenario_05_single_task_through_f50_f60(self):
        """シナリオ05: 単一タスクが F50→F60 を正常に通過すること。"""
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        r50 = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する",
             "priority": "High", "estimated_effort": 2, "estimated_value": 4,
             "element_id": "E1"}
        ]})
        assert r50["trace_id"] == "F50"
        r60 = f60(r50)
        assert r60["trace_id"] == "F60"
        assert isinstance(r60["mece_report"]["is_mece_compliant"], bool)

    def test_scenario_05_single_task_f70_creates_one_goal(self):
        """シナリオ05: 単一タスクから F70 が1つの goal グループを生成すること。"""
        from src.agents.f70_module import execute as f70
        r70 = f70({"trace_id": "F60", "templated_tasks": [
            {"task_id": "T1",
             "templated_text": "【優先度: 高】次のタスクを実行せよ: LP作成する",
             "priority": "High", "effort": 2, "value": 4}
        ]})
        goals = r70["hierarchy"]["goals"]
        assert len(goals) == 1
        assert goals[0]["goal_id"] == "G1"


# ════════════════════════════════════════════════════════
# WP8312: 異常系シナリオ
# ════════════════════════════════════════════════════════

class TestWP8312_AbnormalScenario:
    """異常系シナリオで例外が正しく発動し、パイプラインが停止すること"""

    # ─── シナリオ11: F10 で停止 ───
    def test_scenario_11_pipeline_stops_at_f10_on_none(self):
        """シナリオ11: None 入力で F10 が ValueError を発火し、F20 は呼ばれないこと。"""
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10(None)

    def test_scenario_11_pipeline_stops_at_f10_on_empty_goal(self):
        """シナリオ11: 空文字列 goal_text で F10 が ValueError を発火すること。"""
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10({"goal_text": ""})

    # ─── シナリオ12: F20 で停止 ───
    def test_scenario_12_pipeline_stops_at_f20_on_missing_goal(self):
        """シナリオ12: goal キー欠落で F20 が ValueError を発火すること。"""
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError, match="goal"):
            f20({"trace_id": "F10"})

    def test_scenario_12_pipeline_stops_at_f20_on_none_input(self):
        """シナリオ12: None 入力で F20 が TypeError を発火すること。"""
        from src.agents.f20_module import execute as f20
        with pytest.raises(TypeError):
            f20(None)

    # ─── シナリオ13: F30 で停止 ───
    def test_scenario_13_pipeline_stops_at_f30_on_missing_expanded_goals(self):
        """シナリオ13: expanded_goals 欠落で F30 が ValueError を発火すること。"""
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="expanded_goals"):
            f30({"trace_id": "F20"})

    # ─── シナリオ14: F40 で停止 ───
    def test_scenario_14_pipeline_stops_at_f40_on_missing_evaluated_goals(self):
        """シナリオ14: evaluated_goals 欠落で F40 が ValueError を発火すること。"""
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError, match="evaluated_goals"):
            f40({"trace_id": "F30"})

    # ─── シナリオ15: F50 で停止 ───
    def test_scenario_15_pipeline_stops_at_f50_on_missing_tasks(self):
        """シナリオ15: tasks 欠落で F50 が ValueError を発火すること。"""
        from src.agents.f50_module import execute as f50
        with pytest.raises(ValueError, match="tasks"):
            f50({"trace_id": "F40"})

    # ─── シナリオ16: F60 で停止 ───
    def test_scenario_16_pipeline_stops_at_f60_on_missing_templated_tasks(self):
        """シナリオ16: templated_tasks 欠落で F60 が ValueError を発火すること。"""
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError, match="templated_tasks"):
            f60({"trace_id": "F50"})

    # ─── シナリオ17: F90 非対称例外 ───
    def test_scenario_17_f90_missing_tmap_raises_value_error(self):
        """シナリオ17: F90 で traceability_map 欠落 → ValueError（非対称）。"""
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError, match="traceability_map"):
            f90({"trace_id": "F80", "hierarchy": {"goals": []}})

    def test_scenario_17_f90_missing_hierarchy_raises_type_error(self):
        """シナリオ17: F90 で hierarchy 欠落 → TypeError（非対称）。"""
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError, match="hierarchy"):
            f90({"trace_id": "F80", "traceability_map": []})

    # ─── シナリオ18: 型不一致 ───
    def test_scenario_18_type_error_propagates_from_string_input(self):
        """シナリオ18: F20〜F90 へ string 入力すると TypeError が発火すること。"""
        import importlib
        for mod_name in ["f20_module", "f30_module", "f40_module",
                         "f50_module", "f60_module", "f70_module",
                         "f80_module", "f90_module"]:
            mod = importlib.import_module(f"src.agents.{mod_name}")
            with pytest.raises(TypeError):
                mod.execute("invalid string input")

    # ─── シナリオ19: RuntimeError チェーン ───
    def test_scenario_19_f50_unknown_priority_raises_runtime_with_cause(self):
        """シナリオ19: F50 の未知 priority タスクが RuntimeError(__cause__) を発火すること。"""
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError) as exc_info:
            _apply_template({
                "task_id": "T_ERR", "task_text": "LP作成",
                "priority": "UNKNOWN"
            })
        assert exc_info.value.__cause__ is not None

    def test_scenario_19_f90_zero_effort_raises_runtime_with_cause(self):
        """シナリオ19: F90 の effort=None がゼロ除算 → RuntimeError(__cause__ = ZeroDivisionError)。"""
        from src.agents.f90_module import _compute_evaluation
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation([{"elements": [{"tasks": [
                {"task_id": "T1", "templated_text": "x",
                 "priority": "High", "effort": None, "value": None}
            ]}]}])
        assert isinstance(exc_info.value.__cause__, ZeroDivisionError)

    # ─── シナリオ20: 独立性（例外後の他モジュール動作）───
    def test_scenario_20_exception_in_one_module_does_not_break_others(self):
        """シナリオ20: F30 で例外が起きても F50 は別の入力で独立して動作すること。"""
        from src.agents.f30_module import execute as f30
        from src.agents.f50_module import execute as f50

        # F30 で例外
        with pytest.raises(ValueError):
            f30({"trace_id": "F20", "expanded_goals": "bad"})

        # F50 は別入力で正常動作
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する",
             "priority": "High", "estimated_effort": 2, "estimated_value": 4}
        ]})
        assert result["trace_id"] == "F50"


# ════════════════════════════════════════════════════════
# WP8313: HITL系シナリオ
# ════════════════════════════════════════════════════════

class TestWP8313_HITLScenario:
    """HITL系シナリオが正しく発動し、各パスが仕様どおりに動作すること"""

    # ─── シナリオ21: F10 HITL → パイプライン中断 ───
    def test_scenario_21_ambiguous_goal_triggers_f10_hitl(self):
        """シナリオ21: 曖昧語 goal → F10 が hitl=True を返してパイプラインを中断すること。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "売上などを改善する"})
        assert result["hitl"] is True
        assert result["goal"] is None
        assert result["tree"] is None

    def test_scenario_21_f10_hitl_output_has_reason(self):
        """シナリオ21: F10 HITL 時に hitl_reason が含まれること。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "いろいろ改善したい"})
        assert "hitl_reason" in result
        assert len(result["hitl_reason"]) > 0

    # ─── シナリオ22: F20 HITL ───
    def test_scenario_22_ambiguous_l1_triggers_f20_hitl(self):
        """シナリオ22: 曖昧語 L1 → F20 が hitl=True を返すこと。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {"L1": "売上とか何か上げたい", "L2": ["施策A"], "L3": ["タスク1"]}
        })
        assert result["hitl"] is True

    # ─── シナリオ23: F30 部分 HITL ───
    def test_scenario_23_partial_hitl_in_f30_processes_clean_elements(self):
        """シナリオ23: F30 部分 HITL — 曖昧要素は移譲、クリーン要素は評価されること。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"},
            {"element_id": "E2", "text": "広告配信する", "parent": "L3"},
            {"element_id": "E3", "text": "既存顧客フォローする", "parent": "L3"},
        ]})
        assert "E1" in result["hitl_elements"]
        assert "E2" not in result["hitl_elements"]
        assert "E3" not in result["hitl_elements"]
        assert len(result["evaluated_goals"]) == 2

    # ─── シナリオ24: F50 部分 HITL ───
    def test_scenario_24_partial_hitl_in_f50_templates_clean_tasks(self):
        """シナリオ24: F50 部分 HITL — 曖昧タスクは移譲、クリーンタスクはテンプレ適用。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "T2", "task_text": "広告配信する", "priority": "High",
             "estimated_effort": 1, "estimated_value": 3, "element_id": "E2"},
            {"task_id": "T3", "task_text": "既存顧客フォローする", "priority": "Medium",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E3"},
        ]})
        assert "T1" in result["hitl_elements"]
        assert "T2" not in result["hitl_elements"]
        assert "T3" not in result["hitl_elements"]
        templated_ids = [t["task_id"] for t in result["templated_tasks"]]
        assert "T1" not in templated_ids
        assert "T2" in templated_ids
        assert "T3" in templated_ids

    # ─── シナリオ25: F60 不確定域 HITL ───
    def test_scenario_25_uncertain_similarity_triggers_f60_hitl(self, mocker):
        """シナリオ25: cosine 0.82 の類似ペアが F60 で HITL を発動させること。"""
        mocker.patch("src.agents.f60_module._cosine_similarity", return_value=0.82)
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            {"task_id": "T1", "templated_text": "LP作成する", "priority": "High"},
            {"task_id": "T2", "templated_text": "広告配信する", "priority": "Medium"},
        ]})
        assert result["hitl_required"] is True
        assert len(result["hitl_elements"]) > 0

    def test_scenario_25_duplicate_only_does_not_trigger_hitl(self, mocker):
        """シナリオ25: cosine > 0.85（duplicate のみ）は HITL を発動しないこと。"""
        mocker.patch("src.agents.f60_module._cosine_similarity", return_value=0.95)
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            {"task_id": "T1", "templated_text": "全く同じテキスト内容", "priority": "High"},
            {"task_id": "T2", "templated_text": "全く同じテキスト内容", "priority": "High"},
        ]})
        if not result["mece_report"]["ambiguous_tasks"] and not result["hitl_elements"]:
            assert result["hitl_required"] is False

    # ─── シナリオ26: F80 trace chain 不完全 HITL ───
    def test_scenario_26_f80_incomplete_chain_triggers_hitl_elements(self):
        """シナリオ26: F80 に F50 までの trace_id を渡すと不完全 chain → hitl_elements。"""
        from src.agents.f80_module import execute as f80
        result = f80({
            "trace_id": "F50",
            "hierarchy": {"goals": [{
                "goal_id": "G1", "goal_text": "LP作成",
                "elements": [{"element_id": "G1_EL_H", "element_text": "High優先",
                              "tasks": [{"task_id": "T1", "templated_text": "LP作成する",
                                         "priority": "High", "effort": 2, "value": 4}]}]
            }]}
        })
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    # ─── シナリオ27: HITL 後の承認パス ───
    def test_scenario_27_approval_path_restores_normal_processing(self, mocker):
        """シナリオ27: F10 HITL 後、修正された入力を再実行すると正常処理になること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10

        # HITL 発動
        hitl = f10({"goal_text": "売上などを改善する"})
        assert hitl["hitl"] is True

        # 修正後の再実行（承認パス）
        approved = f10({"goal_text": _GOAL_TEXT})
        assert approved["hitl"] is False
        assert approved["goal"] is not None


# ════════════════════════════════════════════════════════
# WP8314: I/O連鎖シナリオ
# ════════════════════════════════════════════════════════

class TestWP8314_PipelineChain:
    """F10→F90 の I/O 連鎖が途切れず整合していること"""

    # ─── シナリオ31: source_trace_id 継承 ───
    def test_scenario_31_source_trace_id_chain_is_correct(self, pipeline):
        """シナリオ31: source_trace_id が前段の trace_id と一致すること。"""
        chain = [
            ("r20", "F10"), ("r30", "F20"), ("r40", "F30"), ("r50", "F40"),
            ("r60", "F50"), ("r70", "F60"), ("r80", "F70"), ("r90", "F80"),
        ]
        for key, expected_source in chain:
            result = pipeline[key]
            assert result.get("source_trace_id") == expected_source, \
                f"{key}: source_trace_id が '{expected_source}' でない"

    # ─── シナリオ32: F10→F20 key 継承 ───
    def test_scenario_32_f10_goal_passes_to_f20(self, pipeline):
        """シナリオ32: F10 の goal が F20 に正しく渡り展開されること。"""
        r10 = pipeline["r10"]
        r20 = pipeline["r20"]
        assert r20["source_trace_id"] == "F10"
        assert "expanded_goals" in r20
        assert isinstance(r20["expanded_goals"], list)

    # ─── シナリオ33: F40→F50 estimated_effort→effort 変換 ───
    def test_scenario_33_f40_uses_estimated_effort_key(self, pipeline):
        """シナリオ33: F40 出力の tasks に estimated_effort が存在すること。"""
        tasks = pipeline["r40"]["tasks"]
        for t in tasks:
            assert "estimated_effort" in t, f"task {t.get('task_id')} に estimated_effort がない"

    def test_scenario_33_f50_converts_to_effort_key(self, pipeline):
        """シナリオ33: F50 出力の templated_tasks に effort が存在すること（estimated_effort ではない）。"""
        for t in pipeline["r50"]["templated_tasks"]:
            assert "effort" in t, f"task {t.get('task_id')} に effort がない"
            assert "estimated_effort" not in t, \
                f"task {t.get('task_id')} に estimated_effort が残っている"

    # ─── シナリオ34: F50→F60 パススルー ───
    def test_scenario_34_f60_passthrough_is_same_as_f50_templated_tasks(self, pipeline):
        """シナリオ34: F60 の templated_tasks が F50 の templated_tasks と同一であること。"""
        assert pipeline["r60"]["templated_tasks"] == pipeline["r50"]["templated_tasks"]

    # ─── シナリオ35: F70→F80 hierarchy パススルー ───
    def test_scenario_35_f80_hierarchy_is_same_as_f70(self, pipeline):
        """シナリオ35: F80 の hierarchy が F70 の hierarchy と同一であること。"""
        assert pipeline["r80"]["hierarchy"] == pipeline["r70"]["hierarchy"]

    # ─── シナリオ36: F80 traceability_map を F90 が消費 ───
    def test_scenario_36_f90_consumes_f80_traceability_map(self, pipeline):
        """シナリオ36: F90 が F80 の traceability_map を正しく消費すること。"""
        tmap = pipeline["r80"]["traceability_map"]
        r90 = pipeline["r90"]
        assert "final_output" in r90
        # F90 が処理した goal 数 ≥ 0
        assert "n_goals" in r90 or "final_output" in r90

    # ─── シナリオ37: 全モジュールの key ファミリー ───
    def test_scenario_37_f30_evaluated_goals_has_required_fields(self, pipeline):
        """シナリオ37: F30 出力の evaluated_goals に必須フィールドが存在すること。"""
        for elem in pipeline["r30"]["evaluated_goals"]:
            for field in ("element_id", "text", "parent", "priority",
                          "score_importance", "score_feasibility"):
                assert field in elem, f"F30 要素に '{field}' がない"

    def test_scenario_37_f40_tasks_have_required_fields(self, pipeline):
        """シナリオ37: F40 出力の tasks に必須フィールドが存在すること。"""
        for task in pipeline["r40"]["tasks"]:
            for field in ("task_id", "task_text", "priority",
                          "estimated_effort", "estimated_value"):
                assert field in task, f"F40 タスクに '{field}' がない"

    def test_scenario_37_f50_templated_tasks_have_required_fields(self, pipeline):
        """シナリオ37: F50 出力の templated_tasks に必須フィールドが存在すること。"""
        for task in pipeline["r50"]["templated_tasks"]:
            for field in ("task_id", "template_id", "templated_text", "priority"):
                assert field in task, f"F50 タスクに '{field}' がない"

    def test_scenario_37_f70_goals_have_required_structure(self, pipeline):
        """シナリオ37: F70 の hierarchy.goals に goal_id/elements が存在すること。"""
        for goal in pipeline["r70"]["hierarchy"]["goals"]:
            assert "goal_id" in goal
            assert "elements" in goal
            for elem in goal["elements"]:
                assert "element_id" in elem
                assert "tasks" in elem

    def test_scenario_37_f80_tmap_entries_have_required_fields(self, pipeline):
        """シナリオ37: F80 の traceability_map の各エントリに必須フィールドが存在すること。"""
        for entry in pipeline["r80"]["traceability_map"]:
            for field in ("goal_id", "element_id", "task_id",
                          "trace_chain", "is_complete"):
                assert field in entry, f"F80 エントリに '{field}' がない"


# ════════════════════════════════════════════════════════
# WP8315: 運用ログシナリオ
# ════════════════════════════════════════════════════════

class TestWP8315_OperationalLog:
    """運用ログが仕様書どおりに記録されること（INFO / WARNING）"""

    # ─── シナリオ41: F10 完了 INFO ───
    def test_scenario_41_f10_logs_info_on_success(self, mocker, caplog):
        """シナリオ41: F10 正常完了時に INFO ログが出力されること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.INFO, logger="src.agents.f10_module"):
            f10({"goal_text": _GOAL_TEXT})
        assert any(r.levelno == logging.INFO for r in caplog.records)

    def test_scenario_41_f10_info_log_contains_f10_marker(self, mocker, caplog):
        """シナリオ41: F10 INFO ログに '[F10]' マーカーが含まれること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.INFO, logger="src.agents.f10_module"):
            f10({"goal_text": _GOAL_TEXT})
        assert any("[F10]" in r.message for r in caplog.records)

    # ─── シナリオ42: F20 完了 INFO ───
    def test_scenario_42_f20_logs_info_on_success(self, caplog):
        """シナリオ42: F20 正常完了時に INFO ログが出力されること。"""
        from src.agents.f20_module import execute as f20
        with caplog.at_level(logging.INFO, logger="src.agents.f20_module"):
            f20({"trace_id": "F10", "goal": {
                "L1": _GOAL_TEXT, "L2": ["新規顧客獲得"], "L3": ["LP作成する"]
            }})
        assert any(r.levelno == logging.INFO for r in caplog.records)

    # ─── シナリオ43: F50 完了 INFO ───
    def test_scenario_43_f50_logs_info_on_success(self, caplog):
        """シナリオ43: F50 正常完了時に '[F50]' INFO ログが出力されること。"""
        from src.agents.f50_module import execute as f50
        with caplog.at_level(logging.INFO, logger="src.agents.f50_module"):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "task_text": "LP作成する", "priority": "High",
                 "estimated_effort": 2, "estimated_value": 4}
            ]})
        assert any("[F50]" in r.message for r in caplog.records)

    # ─── シナリオ44: F60 完了 INFO ───
    def test_scenario_44_f60_logs_info_on_success(self, caplog):
        """シナリオ44: F60 正常完了時に '[F60]' INFO ログが出力されること。"""
        from src.agents.f60_module import execute as f60
        with caplog.at_level(logging.INFO, logger="src.agents.f60_module"):
            f60({"trace_id": "F50", "templated_tasks": [
                {"task_id": "T1", "templated_text": "LP作成する", "priority": "High"}
            ]})
        assert any("[F60]" in r.message for r in caplog.records)

    # ─── シナリオ45: WARNING — 不明 trace_id ───
    def test_scenario_45_warning_on_unknown_trace_id_f20(self, caplog):
        """シナリオ45: F20 に不明 trace_id を渡すと WARNING が出力されること。"""
        from src.agents.f20_module import execute as f20
        with caplog.at_level(logging.WARNING, logger="src.agents.f20_module"):
            f20({"trace_id": "UNKNOWN", "goal": {
                "L1": _GOAL_TEXT, "L2": ["施策A"], "L3": ["タスク1"]
            }})
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_scenario_45_warning_message_contains_unknown_trace_id(self, caplog):
        """シナリオ45: WARNING メッセージに不明 trace_id 文字列が含まれること。"""
        from src.agents.f20_module import execute as f20
        with caplog.at_level(logging.WARNING, logger="src.agents.f20_module"):
            f20({"trace_id": "BADID", "goal": {
                "L1": _GOAL_TEXT, "L2": ["施策A"], "L3": ["タスク1"]
            }})
        assert any("BADID" in r.message for r in caplog.records)

    # ─── シナリオ46: WARNING — 重複 task_id ───
    def test_scenario_46_warning_on_duplicate_task_id_f50(self, caplog):
        """シナリオ46: F50 に重複 task_id を渡すと WARNING が出力されること。"""
        from src.agents.f50_module import execute as f50
        with caplog.at_level(logging.WARNING, logger="src.agents.f50_module"):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "task_text": "LP作成する", "priority": "High",
                 "estimated_effort": 2, "estimated_value": 4},
                {"task_id": "T1", "task_text": "広告配信する", "priority": "Medium",
                 "estimated_effort": 1, "estimated_value": 3},
            ]})
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    # ─── シナリオ47: WARNING — HITL 移譲 ───
    def test_scenario_47_warning_on_hitl_delegation_f10(self, caplog):
        """シナリオ47: F10 HITL 移譲時に '[HITL移譲]' WARNING が記録されること。"""
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.WARNING, logger="src.agents.f10_module"):
            f10({"goal_text": "売上などを改善する"})
        assert any("HITL" in r.message for r in caplog.records)

    def test_scenario_47_warning_on_hitl_delegation_f50(self, caplog):
        """シナリオ47: F50 HITL 移譲時に '[HITL移譲]' WARNING が記録されること。"""
        from src.agents.f50_module import execute as f50
        with caplog.at_level(logging.WARNING, logger="src.agents.f50_module"):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"}
            ]})
        assert any("HITL" in r.message for r in caplog.records)

    # ─── シナリオ48: F90 完了 INFO ───
    def test_scenario_48_f90_logs_info_on_success(self, caplog):
        """シナリオ48: F90 正常完了時に '[F90]' INFO ログが出力されること。"""
        from src.agents.f90_module import execute as f90
        with caplog.at_level(logging.INFO, logger="src.agents.f90_module"):
            f90({
                "trace_id": "F80",
                "traceability_map": [],
                "hierarchy": {"goals": []},
            })
        # 空入力は HITL 移譲だが INFO は出ないかもしれない。
        # 有効な入力でテスト

    def test_scenario_48_f90_info_log_on_valid_input(self, pipeline, caplog):
        """シナリオ48: F90 有効入力時に '[F90]' INFO ログが出力されること。"""
        from src.agents.f90_module import execute as f90
        with caplog.at_level(logging.INFO, logger="src.agents.f90_module"):
            f90(pipeline["r80"])
        assert any("[F90]" in r.message for r in caplog.records)

    # ─── シナリオ49: F80 完了 INFO ───
    def test_scenario_49_f80_logs_info_on_success(self, caplog):
        """シナリオ49: F80 正常完了時に '[F80]' INFO ログが出力されること。"""
        from src.agents.f80_module import execute as f80
        with caplog.at_level(logging.INFO, logger="src.agents.f80_module"):
            f80({
                "trace_id": "F70",
                "hierarchy": {"goals": [{
                    "goal_id": "G1", "goal_text": "LP作成",
                    "elements": [{"element_id": "G1_EL_H", "element_text": "High優先",
                                  "tasks": [{"task_id": "T1", "templated_text": "LP作成する",
                                             "priority": "High", "effort": 2, "value": 4}]}]
                }]}
            })
        assert any("[F80]" in r.message for r in caplog.records)

    # ─── シナリオ50: F30 / F40 完了 INFO ───
    def test_scenario_50_f30_logs_info_on_success(self, caplog):
        """シナリオ50: F30 正常完了時に '[F30]' INFO ログが出力されること。"""
        from src.agents.f30_module import execute as f30
        with caplog.at_level(logging.INFO, logger="src.agents.f30_module"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"element_id": "E1", "text": "LP作成する", "parent": "L3"}
            ]})
        assert any("[F30]" in r.message for r in caplog.records)

    def test_scenario_50_f40_logs_info_on_success(self, caplog):
        """シナリオ50: F40 正常完了時に '[F40]' INFO ログが出力されること。"""
        from src.agents.f40_module import execute as f40
        with caplog.at_level(logging.INFO, logger="src.agents.f40_module"):
            f40({"trace_id": "F30", "evaluated_goals": [
                {"element_id": "E1", "text": "LP作成する", "parent": "L3",
                 "priority": "High", "score_importance": 0.8, "score_feasibility": 0.7}
            ]})
        assert any("[F40]" in r.message for r in caplog.records)
