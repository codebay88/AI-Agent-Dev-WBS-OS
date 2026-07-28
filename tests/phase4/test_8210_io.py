"""Phase 4 — WP8210 I/O連携テスト
区分：隣接モジュール間 I/O / データ型整合 / キー名整合 / 連鎖不断性 / パススルー

WP8210 の観点：
  - F10→F20→…→F90 の全隣接ペアで I/O キー・型・構造が整合すること
  - 各モジュールの出力が次モジュールの入力仕様と完全に一致すること
  - データ型・必須フィールド・階層構造が仕様書どおりであること
  - パススルーキー（templated_tasks, hierarchy）が正しく伝播すること
  - trace_id / source_trace_id の連鎖が F10→F90 を通じて途切れないこと
"""

import pytest


# ════════════════════════════════════════════════════════
# 共通フィクスチャ
# ════════════════════════════════════════════════════════

_MOCK_API = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)

_GOAL_TEXT = "売上を前年比120%に成長させる"


@pytest.fixture(autouse=True)
def mock_api(mocker):
    mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)


@pytest.fixture
def r10():
    from src.agents.f10_module import execute as f10
    return f10({"goal_text": _GOAL_TEXT})

@pytest.fixture
def r20(r10):
    from src.agents.f20_module import execute as f20
    return f20(r10)

@pytest.fixture
def r30(r20):
    from src.agents.f30_module import execute as f30
    return f30(r20)

@pytest.fixture
def r40(r30):
    from src.agents.f40_module import execute as f40
    return f40(r30)

@pytest.fixture
def r50(r40):
    from src.agents.f50_module import execute as f50
    return f50(r40)

@pytest.fixture
def r60(r50):
    from src.agents.f60_module import execute as f60
    return f60(r50)

@pytest.fixture
def r70(r60):
    from src.agents.f70_module import execute as f70
    return f70(r60)

@pytest.fixture
def r80(r70):
    from src.agents.f80_module import execute as f80
    return f80(r70)

@pytest.fixture
def r90(r80):
    from src.agents.f90_module import execute as f90
    return f90(r80)


# ════════════════════════════════════════════════════════
# WP8211: F10→F20 I/O 整合性
# ════════════════════════════════════════════════════════

class TestWP8211_F10toF20:
    """F10 出力 → F20 入力の I/O 整合性"""

    # F10 出力の必須キー確認
    def test_f10_produces_goal_key(self, r10):
        assert "goal" in r10

    def test_f10_produces_tree_key(self, r10):
        assert "tree" in r10

    def test_f10_produces_trace_id_f10(self, r10):
        assert r10["trace_id"] == "F10"

    # F20 が F10 出力を受け入れること
    def test_f20_accepts_f10_output_without_error(self, r10):
        from src.agents.f20_module import execute as f20
        result = f20(r10)
        assert result["trace_id"] == "F20"

    # F20 が要求する入力キーが F10 出力に存在すること
    def test_f10_output_has_goal_l1_required_by_f20(self, r10):
        assert "L1" in r10["goal"]

    def test_f10_output_has_goal_l2_required_by_f20(self, r10):
        assert "L2" in r10["goal"]

    def test_f10_output_has_goal_l3_required_by_f20(self, r10):
        assert "L3" in r10["goal"]

    def test_f10_l1_type_matches_f20_spec(self, r10):
        """F20 仕様: goal.L1 は str 型必須。"""
        assert isinstance(r10["goal"]["L1"], str)

    def test_f10_l2_type_matches_f20_spec(self, r10):
        """F20 仕様: goal.L2 は list[str] 型必須。"""
        assert isinstance(r10["goal"]["L2"], list)
        assert all(isinstance(x, str) for x in r10["goal"]["L2"])

    def test_f10_l3_type_matches_f20_spec(self, r10):
        """F20 仕様: goal.L3 は list[str] 型必須。"""
        assert isinstance(r10["goal"]["L3"], list)
        assert all(isinstance(x, str) for x in r10["goal"]["L3"])

    # F20 出力の source_trace_id が F10 を指すこと
    def test_f20_source_trace_id_points_to_f10(self, r10, r20):
        assert r20["source_trace_id"] == r10["trace_id"]

    # F20 が F10 出力の expanded_goals を正しく生成すること
    def test_f20_expanded_goals_count(self, r10, r20):
        expected = 1 + len(r10["goal"]["L2"]) + len(r10["goal"]["L3"])
        assert len(r20["expanded_goals"]) == expected


# ════════════════════════════════════════════════════════
# WP8212: F20→F30 I/O 整合性
# ════════════════════════════════════════════════════════

class TestWP8212_F20toF30:
    """F20 出力 → F30 入力の I/O 整合性"""

    def test_f20_produces_expanded_goals_key(self, r20):
        assert "expanded_goals" in r20

    def test_f20_produces_trace_id_f20(self, r20):
        assert r20["trace_id"] == "F20"

    def test_f30_accepts_f20_output_without_error(self, r20):
        from src.agents.f30_module import execute as f30
        result = f30(r20)
        assert result["trace_id"] == "F30"

    def test_f20_each_element_has_text_required_by_f30(self, r20):
        """F30 仕様: expanded_goals 各要素に 'text' が必要。"""
        for elem in r20["expanded_goals"]:
            assert "text" in elem, f"'text' 欠落: {elem}"

    def test_f20_each_element_has_parent_required_by_f30(self, r20):
        """F30 仕様: expanded_goals 各要素に 'parent' が必要。"""
        for elem in r20["expanded_goals"]:
            assert "parent" in elem, f"'parent' 欠落: {elem}"

    def test_f20_each_element_has_element_id(self, r20):
        for elem in r20["expanded_goals"]:
            assert "element_id" in elem

    def test_f20_parent_values_accepted_by_f30(self, r20):
        """F30 仕様: parent は L1/L2/L3 のいずれか。"""
        valid = {"L1", "L2", "L3"}
        for elem in r20["expanded_goals"]:
            assert elem["parent"] in valid

    def test_f30_source_trace_id_points_to_f20(self, r20, r30):
        assert r30["source_trace_id"] == r20["trace_id"]

    def test_f30_evaluated_goals_count_matches_f20(self, r20, r30):
        assert len(r30["evaluated_goals"]) == len(r20["expanded_goals"])


# ════════════════════════════════════════════════════════
# WP8213: F30→F40 I/O 整合性
# ════════════════════════════════════════════════════════

class TestWP8213_F30toF40:
    """F30 出力 → F40 入力の I/O 整合性"""

    def test_f30_produces_evaluated_goals_key(self, r30):
        assert "evaluated_goals" in r30

    def test_f30_produces_trace_id_f30(self, r30):
        assert r30["trace_id"] == "F30"

    def test_f40_accepts_f30_output_without_error(self, r30):
        from src.agents.f40_module import execute as f40
        result = f40(r30)
        assert result["trace_id"] == "F40"

    def test_f30_each_element_has_score_importance_for_f40(self, r30):
        for elem in r30["evaluated_goals"]:
            assert "score_importance" in elem

    def test_f30_each_element_has_score_feasibility_for_f40(self, r30):
        for elem in r30["evaluated_goals"]:
            assert "score_feasibility" in elem

    def test_f30_each_element_has_priority_for_f40(self, r30):
        for elem in r30["evaluated_goals"]:
            assert "priority" in elem

    def test_f30_each_element_has_element_id_for_f40(self, r30):
        for elem in r30["evaluated_goals"]:
            assert "element_id" in elem

    def test_f30_each_element_has_text_for_f40(self, r30):
        for elem in r30["evaluated_goals"]:
            assert "text" in elem

    def test_f30_priority_values_accepted_by_f40(self, r30):
        valid = {"High", "Medium", "Low"}
        for elem in r30["evaluated_goals"]:
            assert elem["priority"] in valid

    def test_f40_source_trace_id_points_to_f30(self, r30, r40):
        assert r40["source_trace_id"] == r30["trace_id"]

    def test_f40_task_count_matches_f30_evaluated(self, r30, r40):
        assert len(r40["tasks"]) == len(r30["evaluated_goals"])


# ════════════════════════════════════════════════════════
# WP8214: F40→F50 I/O 整合性
# ════════════════════════════════════════════════════════

class TestWP8214_F40toF50:
    """F40 出力 → F50 入力の I/O 整合性"""

    def test_f40_produces_tasks_key(self, r40):
        assert "tasks" in r40

    def test_f40_produces_trace_id_f40(self, r40):
        assert r40["trace_id"] == "F40"

    def test_f50_accepts_f40_output_without_error(self, r40):
        from src.agents.f50_module import execute as f50
        result = f50(r40)
        assert result["trace_id"] == "F50"

    def test_f40_each_task_has_task_id_required_by_f50(self, r40):
        """F50 仕様: 各タスクに task_id が必要。"""
        for task in r40["tasks"]:
            assert "task_id" in task

    def test_f40_each_task_has_task_text_required_by_f50(self, r40):
        """F50 仕様: 各タスクに task_text が必要。"""
        for task in r40["tasks"]:
            assert "task_text" in task

    def test_f40_each_task_has_priority_required_by_f50(self, r40):
        """F50 仕様: 各タスクに priority が必要。"""
        for task in r40["tasks"]:
            assert "priority" in task

    def test_f40_estimated_effort_key_exists(self, r40):
        """F40 は estimated_effort を出力する（F50 で effort に変換される）。"""
        for task in r40["tasks"]:
            assert "estimated_effort" in task

    def test_f40_estimated_value_key_exists(self, r40):
        """F40 は estimated_value を出力する（F50 で value に変換される）。"""
        for task in r40["tasks"]:
            assert "estimated_value" in task

    def test_f50_converts_estimated_effort_to_effort(self, r40, r50):
        """F50 は F40 の estimated_effort を effort に変換すること。"""
        for task in r50["templated_tasks"]:
            assert "effort" in task

    def test_f50_converts_estimated_value_to_value(self, r40, r50):
        """F50 は F40 の estimated_value を value に変換すること。"""
        for task in r50["templated_tasks"]:
            assert "value" in task

    def test_f50_source_trace_id_points_to_f40(self, r40, r50):
        assert r50["source_trace_id"] == r40["trace_id"]

    def test_f50_task_count_matches_f40(self, r40, r50):
        """HITL 移譲がなければ、タスク件数は F40 と一致すること。"""
        hitl_count = len(r50["hitl_elements"])
        assert len(r50["templated_tasks"]) + hitl_count == len(r40["tasks"])


# ════════════════════════════════════════════════════════
# WP8215: F50→F60 I/O 整合性
# ════════════════════════════════════════════════════════

class TestWP8215_F50toF60:
    """F50 出力 → F60 入力の I/O 整合性"""

    def test_f50_produces_templated_tasks_key(self, r50):
        assert "templated_tasks" in r50

    def test_f50_produces_trace_id_f50(self, r50):
        assert r50["trace_id"] == "F50"

    def test_f60_accepts_f50_output_without_error(self, r50):
        from src.agents.f60_module import execute as f60
        result = f60(r50)
        assert result["trace_id"] == "F60"

    def test_f50_each_task_has_task_id_required_by_f60(self, r50):
        """F60 仕様: 各タスクに task_id が必要。"""
        for task in r50["templated_tasks"]:
            assert "task_id" in task

    def test_f50_each_task_has_templated_text_required_by_f60(self, r50):
        """F60 仕様: 各タスクに templated_text が必要。"""
        for task in r50["templated_tasks"]:
            assert "templated_text" in task

    def test_f50_each_task_has_priority_required_by_f60(self, r50):
        """F60 仕様: 各タスクに priority が必要。"""
        for task in r50["templated_tasks"]:
            assert "priority" in task

    def test_f50_templated_text_format_valid_for_f60(self, r50):
        """F60 が受け取る templated_text が空でないこと。"""
        for task in r50["templated_tasks"]:
            assert len(task["templated_text"]) > 0

    def test_f60_source_trace_id_points_to_f50(self, r50, r60):
        assert r60["source_trace_id"] == r50["trace_id"]

    def test_f60_mece_report_generated_from_f50_tasks(self, r60):
        assert "mece_report" in r60


# ════════════════════════════════════════════════════════
# WP8216: F60→F70 I/O 整合性（パススルー検証含む）
# ════════════════════════════════════════════════════════

class TestWP8216_F60toF70:
    """F60 出力 → F70 入力の I/O 整合性（templated_tasks パススルー）"""

    def test_f60_produces_templated_tasks_passthrough(self, r60):
        """F60 は F70 のために templated_tasks をパススルーすること。"""
        assert "templated_tasks" in r60

    def test_f60_produces_trace_id_f60(self, r60):
        assert r60["trace_id"] == "F60"

    def test_f70_accepts_f60_output_without_error(self, r60):
        from src.agents.f70_module import execute as f70
        result = f70(r60)
        assert result["trace_id"] == "F70"

    def test_f60_passthrough_is_same_as_f50_output(self, r50, r60):
        """F60 のパススルー templated_tasks が F50 出力と同一であること。"""
        assert r60["templated_tasks"] == r50["templated_tasks"]

    def test_f60_each_passthrough_task_has_task_id(self, r60):
        """F70 仕様: 各タスクに task_id が必要。"""
        for task in r60["templated_tasks"]:
            assert "task_id" in task

    def test_f60_each_passthrough_task_has_templated_text(self, r60):
        """F70 仕様: 各タスクに templated_text が必要。"""
        for task in r60["templated_tasks"]:
            assert "templated_text" in task

    def test_f60_each_passthrough_task_has_priority(self, r60):
        """F70 仕様: 各タスクに priority が必要。"""
        for task in r60["templated_tasks"]:
            assert "priority" in task

    def test_f70_source_trace_id_points_to_f60(self, r60, r70):
        assert r70["source_trace_id"] == r60["trace_id"]

    def test_f70_hierarchy_generated_from_f60_tasks(self, r70):
        assert "hierarchy" in r70
        assert "goals" in r70["hierarchy"]

    def test_f60_mece_report_not_consumed_by_f70(self, r60, r70):
        """F70 出力に mece_report は含まれないこと（F70 は hierarchy を生成するのみ）。"""
        assert "mece_report" not in r70


# ════════════════════════════════════════════════════════
# WP8217: F70→F80 I/O 整合性
# ════════════════════════════════════════════════════════

class TestWP8217_F70toF80:
    """F70 出力 → F80 入力の I/O 整合性"""

    def test_f70_produces_hierarchy_key(self, r70):
        assert "hierarchy" in r70

    def test_f70_produces_trace_id_f70(self, r70):
        assert r70["trace_id"] == "F70"

    def test_f80_accepts_f70_output_without_error(self, r70):
        from src.agents.f80_module import execute as f80
        result = f80(r70)
        assert result["trace_id"] == "F80"

    def test_f70_hierarchy_has_goals_required_by_f80(self, r70):
        """F80 仕様: hierarchy.goals が必要。"""
        assert "goals" in r70["hierarchy"]

    def test_f70_each_goal_has_goal_id_required_by_f80(self, r70):
        """F80 仕様: 各 goal に goal_id が必要。"""
        for goal in r70["hierarchy"]["goals"]:
            assert "goal_id" in goal

    def test_f70_each_goal_has_elements_required_by_f80(self, r70):
        """F80 仕様: 各 goal に elements が必要。"""
        for goal in r70["hierarchy"]["goals"]:
            assert "elements" in goal

    def test_f70_each_element_has_element_id_required_by_f80(self, r70):
        for goal in r70["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                assert "element_id" in elem

    def test_f70_each_element_has_tasks_required_by_f80(self, r70):
        for goal in r70["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                assert "tasks" in elem

    def test_f70_each_task_has_task_id_required_by_f80(self, r70):
        for goal in r70["hierarchy"]["goals"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert "task_id" in task

    def test_f80_source_trace_id_points_to_f70(self, r70, r80):
        assert r80["source_trace_id"] == r70["trace_id"]

    def test_f80_traceability_map_generated_from_f70(self, r80):
        assert "traceability_map" in r80
        assert isinstance(r80["traceability_map"], list)


# ════════════════════════════════════════════════════════
# WP8218: F80→F90 I/O 整合性（hierarchy パススルー検証含む）
# ════════════════════════════════════════════════════════

class TestWP8218_F80toF90:
    """F80 出力 → F90 入力の I/O 整合性（hierarchy パススルー）"""

    def test_f80_produces_traceability_map_key(self, r80):
        assert "traceability_map" in r80

    def test_f80_produces_hierarchy_passthrough(self, r80):
        """F80 は F90 のために hierarchy をパススルーすること。"""
        assert "hierarchy" in r80

    def test_f80_produces_trace_id_f80(self, r80):
        assert r80["trace_id"] == "F80"

    def test_f90_accepts_f80_output_without_error(self, r80):
        from src.agents.f90_module import execute as f90
        result = f90(r80)
        assert result["trace_id"] == "F90"

    def test_f80_passthrough_hierarchy_same_as_f70(self, r70, r80):
        """F80 の hierarchy パススルーが F70 出力の hierarchy と同一であること。"""
        assert r80["hierarchy"] == r70["hierarchy"]

    def test_f80_traceability_map_type_accepted_by_f90(self, r80):
        """F90 仕様: traceability_map は list 型必須。"""
        assert isinstance(r80["traceability_map"], list)

    def test_f80_each_tmap_entry_has_task_id(self, r80):
        """F90 が tmap を参照する際に task_id が必要。"""
        for entry in r80["traceability_map"]:
            assert "task_id" in entry

    def test_f80_each_tmap_entry_has_trace_chain(self, r80):
        for entry in r80["traceability_map"]:
            assert "trace_chain" in entry

    def test_f80_each_tmap_entry_has_is_complete(self, r80):
        for entry in r80["traceability_map"]:
            assert "is_complete" in entry

    def test_f80_hierarchy_goals_structure_preserved_for_f90(self, r80):
        """F90 が参照する hierarchy.goals 構造が壊れていないこと。"""
        for goal in r80["hierarchy"]["goals"]:
            assert "goal_id" in goal
            assert "elements" in goal

    def test_f90_source_trace_id_points_to_f80(self, r80, r90):
        assert r90["source_trace_id"] == r80["trace_id"]

    def test_f90_final_output_generated_from_f80(self, r90):
        assert "final_output" in r90


# ════════════════════════════════════════════════════════
# WP8219: 連鎖不断性 — trace_id / source_trace_id の全ペア検証
# ════════════════════════════════════════════════════════

class TestWP8219_ChainContinuity:
    """F10→F90 全モジュール間の trace_id 連鎖が途切れないこと"""

    EXPECTED_CHAIN = [
        ("F10", None),
        ("F20", "F10"),
        ("F30", "F20"),
        ("F40", "F30"),
        ("F50", "F40"),
        ("F60", "F50"),
        ("F70", "F60"),
        ("F80", "F70"),
        ("F90", "F80"),
    ]

    @pytest.mark.parametrize("mod,expected_source", EXPECTED_CHAIN)
    def test_trace_id_value(self, request, mod, expected_source,
                            r10, r20, r30, r40, r50, r60, r70, r80, r90):
        outputs = {
            "F10": r10, "F20": r20, "F30": r30, "F40": r40, "F50": r50,
            "F60": r60, "F70": r70, "F80": r80, "F90": r90,
        }
        assert outputs[mod]["trace_id"] == mod

    @pytest.mark.parametrize("mod,expected_source", [
        ("F20", "F10"), ("F30", "F20"), ("F40", "F30"), ("F50", "F40"),
        ("F60", "F50"), ("F70", "F60"), ("F80", "F70"), ("F90", "F80"),
    ])
    def test_source_trace_id_links_to_previous(self, mod, expected_source,
                                               r20, r30, r40, r50, r60, r70, r80, r90):
        outputs = {
            "F20": r20, "F30": r30, "F40": r40, "F50": r50,
            "F60": r60, "F70": r70, "F80": r80, "F90": r90,
        }
        assert outputs[mod]["source_trace_id"] == expected_source, \
            f"{mod}.source_trace_id = {outputs[mod].get('source_trace_id')!r}（期待: {expected_source!r}）"

    def test_no_module_has_duplicate_trace_id(self, r10, r20, r30, r40, r50, r60, r70, r80, r90):
        """全モジュールの trace_id が異なること。"""
        ids = [r["trace_id"] for r in [r10, r20, r30, r40, r50, r60, r70, r80, r90]]
        assert len(ids) == len(set(ids))

    def test_full_pipeline_completes_without_error(self, r90):
        """F10→F90 の全パイプラインがエラーなく完了すること。"""
        assert r90["trace_id"] == "F90"
        assert r90["final_output"]["summary"]["total_tasks"] > 0

    def test_pipeline_integrity_verified(self, r90):
        assert r90["final_output"]["summary"]["pipeline_integrity"] == "verified"

    def test_traceability_complete_in_final_output(self, r90):
        """F90 の traceability_complete がブール型であること。"""
        assert isinstance(r90["final_output"]["summary"]["traceability_complete"], bool)

    def test_f90_trace_chain_in_tmap_covers_f10_to_f70(self, r80):
        """F80 の traceability_map エントリの trace_chain が F10〜F70 を網羅すること。"""
        expected_full = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]
        for entry in r80["traceability_map"]:
            if entry["is_complete"]:
                assert entry["trace_chain"] == expected_full, \
                    f"task_id={entry['task_id']} の trace_chain が不完全"


# ════════════════════════════════════════════════════════
# WP821A: データ型整合性 — 全モジュール出力の型検証
# ════════════════════════════════════════════════════════

class TestWP821A_DataTypeConsistency:
    """全モジュール出力の型・構造の整合性"""

    @pytest.mark.parametrize("mod,fixture_name", [
        ("F10", "r10"), ("F20", "r20"), ("F30", "r30"), ("F40", "r40"),
        ("F50", "r50"), ("F60", "r60"), ("F70", "r70"), ("F80", "r80"), ("F90", "r90"),
    ])
    def test_all_module_outputs_are_dicts(self, request, mod, fixture_name):
        result = request.getfixturevalue(fixture_name)
        assert isinstance(result, dict), f"{mod} output is not dict"

    @pytest.mark.parametrize("mod,fixture_name", [
        ("F10", "r10"), ("F20", "r20"), ("F30", "r30"), ("F40", "r40"),
        ("F50", "r50"), ("F60", "r60"), ("F70", "r70"), ("F80", "r80"), ("F90", "r90"),
    ])
    def test_all_module_trace_ids_are_strings(self, request, mod, fixture_name):
        result = request.getfixturevalue(fixture_name)
        assert isinstance(result["trace_id"], str)

    def test_f20_expanded_goals_element_id_sequential(self, r20):
        """F20 の element_id が E1, E2, E3... の連番であること。"""
        eids = [e["element_id"] for e in r20["expanded_goals"]]
        for i, eid in enumerate(eids, 1):
            assert eid == f"E{i}", f"element_id 連番違反: {eid} (期待: E{i})"

    def test_f30_scores_are_floats(self, r30):
        for elem in r30["evaluated_goals"]:
            assert isinstance(elem["score_importance"], float)
            assert isinstance(elem["score_feasibility"], float)

    def test_f40_effort_value_are_ints(self, r40):
        for task in r40["tasks"]:
            assert isinstance(task["estimated_effort"], int)
            assert isinstance(task["estimated_value"], int)

    def test_f50_effort_value_type_preserved(self, r50):
        for task in r50["templated_tasks"]:
            assert isinstance(task["effort"], (int, float))
            assert isinstance(task["value"], (int, float))

    def test_f60_mece_report_fields_types(self, r60):
        report = r60["mece_report"]
        assert isinstance(report["duplicate_tasks"], list)
        assert isinstance(report["missing_elements"], list)
        assert isinstance(report["ambiguous_tasks"], list)
        assert isinstance(report["is_mece_compliant"], bool)

    def test_f70_goal_ids_are_strings(self, r70):
        for goal in r70["hierarchy"]["goals"]:
            assert isinstance(goal["goal_id"], str)

    def test_f80_is_complete_flags_are_bool(self, r80):
        for entry in r80["traceability_map"]:
            assert isinstance(entry["is_complete"], bool)

    def test_f90_efficiency_score_is_float(self, r90):
        score = r90["final_output"]["evaluation_report"]["efficiency_score"]
        assert isinstance(score, float)

    def test_f90_total_counts_are_non_negative_ints(self, r90):
        s = r90["final_output"]["summary"]
        for key in ("total_goals", "total_elements", "total_tasks"):
            v = s[key]
            assert isinstance(v, int) and v >= 0, f"{key}={v} は非負整数でない"


# ════════════════════════════════════════════════════════
# WP821B: キー名整合性 — 仕様書定義のキー名と実装の一致
# ════════════════════════════════════════════════════════

class TestWP821B_KeyNameConsistency:
    """仕様書に定義されたキー名と実装出力の完全一致検証"""

    def test_f10_required_keys(self, r10):
        assert {"trace_id", "goal", "tree"} <= r10.keys()

    def test_f20_required_keys(self, r20):
        assert {"trace_id", "source_trace_id", "expanded_goals"} <= r20.keys()

    def test_f30_required_keys(self, r30):
        assert {"trace_id", "source_trace_id", "evaluated_goals"} <= r30.keys()

    def test_f40_required_keys(self, r40):
        assert {"trace_id", "source_trace_id", "tasks"} <= r40.keys()

    def test_f50_required_keys(self, r50):
        assert {"trace_id", "source_trace_id", "templated_tasks", "hitl", "hitl_elements"} <= r50.keys()

    def test_f60_required_keys(self, r60):
        assert {"trace_id", "source_trace_id", "mece_report", "hitl",
                "hitl_required", "hitl_elements", "templated_tasks"} <= r60.keys()

    def test_f70_required_keys(self, r70):
        assert {"trace_id", "source_trace_id", "hierarchy"} <= r70.keys()

    def test_f80_required_keys(self, r80):
        assert {"trace_id", "source_trace_id", "traceability_map",
                "hierarchy", "hitl_required"} <= r80.keys()

    def test_f90_required_keys(self, r90):
        assert {"trace_id", "source_trace_id", "final_output",
                "hitl_required", "hitl_elements"} <= r90.keys()

    def test_f40_uses_estimated_effort_not_effort(self, r40):
        """F40 は estimated_effort を使用し、effort ではないこと。"""
        for task in r40["tasks"]:
            assert "estimated_effort" in task
            assert "effort" not in task

    def test_f40_uses_estimated_value_not_value(self, r40):
        """F40 は estimated_value を使用し、value ではないこと。"""
        for task in r40["tasks"]:
            assert "estimated_value" in task
            assert "value" not in task

    def test_f50_converts_to_effort_not_estimated_effort(self, r50):
        """F50 は effort を使用し、estimated_effort ではないこと。"""
        for task in r50["templated_tasks"]:
            assert "effort" in task
            assert "estimated_effort" not in task

    def test_f60_mece_report_key_is_is_mece_compliant(self, r60):
        """F60 mece_report の判定キーは 'is_mece_compliant' であること（'compliant' ではない）。"""
        assert "is_mece_compliant" in r60["mece_report"]

    def test_f90_final_output_summary_uses_total_tasks(self, r90):
        """F90 summary のキーは 'total_tasks' であること。"""
        assert "total_tasks" in r90["final_output"]["summary"]

    def test_f90_evaluation_uses_efficiency_score(self, r90):
        """F90 evaluation_report のキーは 'efficiency_score' であること。"""
        assert "efficiency_score" in r90["final_output"]["evaluation_report"]
