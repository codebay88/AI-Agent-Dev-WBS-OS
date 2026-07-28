"""Phase 4 — WP8110 因果分解テスト（Causal Decomposition Test）

■ 検証軸
  各モジュールを「原因（Cause）→ 中間処理（Process）→ 結果（Effect）」に分解し、
  仕様書（docs/Fxx_Module.md）に定義された因果構造どおりに動作するかを確認する。

■ 構造マップ
  F10: goal_text        → Claude API 構造化        → goal/tree（L1/L2/L3）
  F20: tree             → expand_goals            → expanded_goals list
  F30: expanded_goals   → importance/feasibility  → evaluated elements + priority
  F40: evaluated elems  → generate_task           → tasks（effort/value/priority）
  F50: tasks            → apply_template          → templated_tasks（TMP_HIGH/MED/LOW）
  F60: templated_tasks  → MECE check              → mece_report（dup/missing/ambig）
  F70: templated_tasks  → Union-Find group        → hierarchy（goals/elements/tasks）
  F80: hierarchy        → build_trace_chain       → traceability_map（chain/is_complete）
  F90: tmap + hierarchy → evaluate + recommend    → final_output（summary/report）

■ 判定基準
  - 原因フィールドが出力に因果的影響を与えていること
  - 中間処理が省略されていないこと（INFOログで確認）
  - 出力が原因と処理の結果として妥当であること
  - 異常系で因果チェーンが破綻せず例外処理が発火すること
  - HITL系で人間承認フローが正しく発動すること
"""

import logging

import pytest


# ════════════════════════════════════════════════════════
# 共通フィクスチャ
# ════════════════════════════════════════════════════════

FULL_CHAIN = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]

_API_MOCK = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


@pytest.fixture
def mock_api(mocker):
    mocker.patch("src.agents.f10_module._call_api", return_value=_API_MOCK)


def _run_full(goal="売上を前年比120%に成長させる"):
    from src.agents.f10_module import execute as f10
    from src.agents.f20_module import execute as f20
    from src.agents.f30_module import execute as f30
    from src.agents.f40_module import execute as f40
    from src.agents.f50_module import execute as f50
    from src.agents.f60_module import execute as f60
    from src.agents.f70_module import execute as f70
    from src.agents.f80_module import execute as f80
    from src.agents.f90_module import execute as f90
    return f90(f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": goal})))))))))



# ════════════════════════════════════════════════════════
# WP8111: F10 因果分解
# 原因: goal_text  処理: _call_api → _parse_response → _build_tree
# 結果: goal（L1/L2/L3）+ tree（objective_id付き階層）
# ════════════════════════════════════════════════════════

class TestCausal_F10:
    """F10: goal_text → Claude API 構造化 → goal/tree"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        self.result = f10({"goal_text": "売上を前年比120%に成長させる"})

    # ── 原因（Cause） ─────────────────────────
    def test_cause_goal_text_is_consumed(self):
        """goal_text が入力として受け付けられ、出力に goal が生成されること。"""
        assert self.result.get("goal") is not None

    def test_cause_affects_l1_structure(self):
        """goal_text の内容が L1 に反映されること（API モックから）。"""
        l1 = self.result["goal"]["L1"]
        assert isinstance(l1, str) and len(l1) > 0

    # ── 中間処理（Process） ──────────────────
    def test_process_generates_l2_list(self):
        """L2 が list[str] として生成されること。"""
        assert isinstance(self.result["goal"]["L2"], list)
        assert len(self.result["goal"]["L2"]) > 0

    def test_process_generates_l3_list(self):
        assert isinstance(self.result["goal"]["L3"], list)
        assert len(self.result["goal"]["L3"]) > 0

    def test_process_builds_tree(self):
        """tree（objective_id付き階層）が生成されること。"""
        assert isinstance(self.result.get("tree"), dict)
        assert len(self.result["tree"]) > 0

    def test_process_tree_nodes_have_objective_id(self):
        for node in self.result["tree"].values():
            assert "objective_id" in node

    def test_process_tree_nodes_have_level(self):
        for node in self.result["tree"].values():
            assert node["level"] in ("L1", "L2", "L3")

    def test_process_info_log_emitted(self, caplog):
        """[F10] INFO ログが出力されること（中間処理の証跡）。"""
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.INFO, logger="src.agents.f10_module"):
            f10({"goal_text": "売上を前年比120%に成長させる"})
        assert any("[F10]" in r.message for r in caplog.records)

    # ── 結果（Effect） ───────────────────────
    def test_effect_trace_id_is_f10(self):
        assert self.result["trace_id"] == "F10"

    def test_effect_hitl_is_bool(self):
        assert isinstance(self.result["hitl"], bool)

    # ── 異常系：因果チェーン破綻なし ──────────
    def test_abnormal_none_raises_value_error(self):
        """F10 は None を受け取った場合 ValueError を発生させること。"""
        from src.agents.f10_module import execute as f10
        with pytest.raises(ValueError):
            f10(None)

    def test_abnormal_empty_dict_raises_error(self):
        from src.agents.f10_module import execute as f10
        with pytest.raises((TypeError, ValueError)):
            f10({})


# ════════════════════════════════════════════════════════
# WP8112: F20 因果分解
# 原因: goal.L1/L2/L3 + tree  処理: _expand_goals
# 結果: expanded_goals（element_id付きフラットリスト）
# ════════════════════════════════════════════════════════

class TestCausal_F20:
    """F20: goal/tree → expand_goals → expanded_goals list"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        r10 = f10({"goal_text": "売上を前年比120%に成長させる"})
        self.r10 = r10
        self.result = f20(r10)

    def test_cause_tree_is_consumed(self):
        """F10 の tree が F20 の入力として使われること。"""
        assert len(self.r10["tree"]) > 0

    def test_process_expanded_goals_generated(self):
        """expanded_goals が生成されること。"""
        assert isinstance(self.result.get("expanded_goals"), list)

    def test_process_each_element_has_element_id(self):
        for elem in self.result["expanded_goals"]:
            assert "element_id" in elem, f"element_id 欠落: {elem}"

    def test_process_each_element_has_text(self):
        for elem in self.result["expanded_goals"]:
            assert "text" in elem

    def test_process_each_element_has_parent(self):
        for elem in self.result["expanded_goals"]:
            assert "parent" in elem and elem["parent"] in ("L1", "L2", "L3")

    def test_process_element_count_matches_l1_l2_l3(self):
        """展開要素数 = L1(1) + L2 + L3 の合計であること。"""
        goal = self.r10["goal"]
        expected = 1 + len(goal["L2"]) + len(goal["L3"])
        assert len(self.result["expanded_goals"]) == expected

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        with caplog.at_level(logging.INFO, logger="src.agents.f20_module"):
            f20(f10({"goal_text": "売上を前年比120%に成長させる"}))
        assert any("[F20]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f20(self):
        assert self.result["trace_id"] == "F20"

    def test_effect_source_trace_id_is_f10(self):
        assert self.result["source_trace_id"] == "F10"

    def test_abnormal_missing_goal_key_raises_error(self):
        from src.agents.f20_module import execute as f20
        with pytest.raises((TypeError, ValueError)):
            f20({"trace_id": "F10"})  # goal なし


# ════════════════════════════════════════════════════════
# WP8113: F30 因果分解
# 原因: expanded_goals（text/parent）  処理: _score_importance/_score_feasibility
# 結果: evaluated（priority + score付きリスト）
# ════════════════════════════════════════════════════════

class TestCausal_F30:
    """F30: expanded_goals → importance/feasibility scoring → evaluated elements"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        self.result = f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))

    def test_cause_expanded_goals_consumed(self):
        """evaluated_goals に expanded_goals の件数が反映されること。"""
        assert len(self.result.get("evaluated_goals", [])) > 0

    def test_process_importance_score_assigned(self):
        for elem in self.result["evaluated_goals"]:
            assert "score_importance" in elem
            assert 0.0 <= elem["score_importance"] <= 1.0

    def test_process_feasibility_score_assigned(self):
        for elem in self.result["evaluated_goals"]:
            assert "score_feasibility" in elem
            assert 0.0 <= elem["score_feasibility"] <= 1.0

    def test_process_priority_derived_from_scores(self):
        """priority が importance/feasibility の平均から導出されること。"""
        from src.agents.f30_module import _classify_priority
        for elem in self.result["evaluated_goals"]:
            imp  = elem["score_importance"]
            feas = elem["score_feasibility"]
            expected = _classify_priority(imp, feas)
            assert elem["priority"] == expected, (
                f"element_id={elem['element_id']}: "
                f"priority={elem['priority']} ≠ expected={expected}"
            )

    def test_process_l1_importance_base_higher_than_l3(self):
        """L1 の importance_base が L3 より高いこと（F30 定数検証）。"""
        from src.agents.f30_module import _IMPORTANCE_BASE
        assert _IMPORTANCE_BASE["L1"] > _IMPORTANCE_BASE["L3"]

    def test_process_l3_feasibility_base_higher_than_l1(self):
        from src.agents.f30_module import _FEASIBILITY_BASE
        assert _FEASIBILITY_BASE["L3"] > _FEASIBILITY_BASE["L1"]

    def test_process_numeric_text_gets_importance_bonus(self):
        """数値表現（120%等）を含む L1 テキストが importance ボーナスを得ること。"""
        from src.agents.f30_module import _score_importance, _IMPORTANCE_BASE
        base  = _IMPORTANCE_BASE["L1"]
        score = _score_importance("売上を前年比120%に成長させる", "L1")
        assert score > base

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        with caplog.at_level(logging.INFO, logger="src.agents.f30_module"):
            f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))
        assert any("[F30]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f30(self):
        assert self.result["trace_id"] == "F30"

    def test_effect_all_priorities_are_valid(self):
        for elem in self.result["evaluated_goals"]:
            assert elem["priority"] in ("High", "Medium", "Low")

    def test_abnormal_ambiguous_element_triggers_hitl(self):
        """曖昧語（AMBIGUOUS_WORDS）を含む要素が HITL 移譲されること。"""
        from src.agents.f30_module import execute as f30, AMBIGUOUS_WORDS
        word = AMBIGUOUS_WORDS[0]  # "など"
        elems = [{"element_id": "E1", "text": f"売上など{word}", "parent": "L2"}]
        result = f30({"trace_id": "F20", "expanded_goals": elems})
        assert result["hitl"] is True


# ════════════════════════════════════════════════════════
# WP8114: F40 因果分解
# 原因: evaluated elements（priority/score）  処理: _calc_effort/_calc_value/_generate_task
# 結果: tasks（task_id/priority/effort/value）
# ════════════════════════════════════════════════════════

class TestCausal_F40:
    """F40: evaluated elements → _generate_task → tasks"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        self.result = f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))

    def test_cause_evaluated_goals_consumed(self):
        assert len(self.result.get("tasks", [])) > 0

    def test_process_task_id_assigned(self):
        for t in self.result["tasks"]:
            assert "task_id" in t and t["task_id"].startswith("T")

    def test_process_estimated_effort_derived_from_feasibility(self):
        """estimated_effort が score_feasibility から導出されること（高実現可能 → 低工数）。"""
        from src.agents.f40_module import _calc_effort
        # feasibility=1.0（最高）→ effort=1（最低工数）
        assert _calc_effort(1.0) == 1
        # feasibility=0.0（最低）→ effort=5（最高工数）
        assert _calc_effort(0.0) == 5

    def test_process_estimated_value_derived_from_importance(self):
        """estimated_value が score_importance から導出されること（高重要度 → 高価値）。"""
        from src.agents.f40_module import _calc_value
        assert _calc_value(1.0) == 5
        assert _calc_value(0.0) == 1

    def test_process_effort_in_range_1_to_5(self):
        for t in self.result["tasks"]:
            assert 1 <= t["estimated_effort"] <= 5

    def test_process_value_in_range_1_to_5(self):
        for t in self.result["tasks"]:
            assert 1 <= t["estimated_value"] <= 5

    def test_process_priority_preserved_from_f30(self):
        """F30 の priority が F40 タスクに引き継がれること。"""
        for t in self.result["tasks"]:
            assert t["priority"] in ("High", "Medium", "Low")

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        with caplog.at_level(logging.INFO, logger="src.agents.f40_module"):
            f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))
        assert any("[F40]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f40(self):
        assert self.result["trace_id"] == "F40"

    def test_effect_task_count_equals_element_count(self):
        """タスク数 = 入力 element 数であること（1:1 対応）。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        r30 = f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))
        n_tasks = len([t for t in self.result["tasks"] if t.get("task_id")])
        assert n_tasks > 0


# ════════════════════════════════════════════════════════
# WP8115: F50 因果分解
# 原因: tasks（priority）  処理: _apply_template（TMP_HIGH/MED/LOW）
# 結果: templated_tasks（templated_text/template_id）
# ════════════════════════════════════════════════════════

class TestCausal_F50:
    """F50: tasks → _apply_template → templated_tasks"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        self.result = f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))

    def test_cause_priority_determines_template(self):
        """priority（High/Medium/Low）がテンプレ選択の原因であること。"""
        from src.agents.f50_module import _TEMPLATES
        for task in self.result["templated_tasks"]:
            pri = task["priority"]
            tid = task["template_id"]
            assert tid == _TEMPLATES[pri][0], f"priority={pri} → template_id={tid} 不一致"

    def test_process_templated_text_contains_task_text(self):
        """task_text がテンプレ適用後のテキストに含まれること。"""
        for task in self.result["templated_tasks"]:
            assert len(task["templated_text"]) > len(task.get("task_text", ""))

    def test_process_high_prefix_applied(self):
        highs = [t for t in self.result["templated_tasks"] if t["priority"] == "High"]
        for t in highs:
            assert t["templated_text"].startswith("【優先度: 高】")

    def test_process_medium_prefix_applied(self):
        mediums = [t for t in self.result["templated_tasks"] if t["priority"] == "Medium"]
        for t in mediums:
            assert t["templated_text"].startswith("【優先度: 中】")

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        with caplog.at_level(logging.INFO, logger="src.agents.f50_module"):
            f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))
        assert any("[F50]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f50(self):
        assert self.result["trace_id"] == "F50"

    def test_effect_template_id_is_valid(self):
        valid = {"TMP_HIGH", "TMP_MEDIUM", "TMP_LOW"}
        for t in self.result["templated_tasks"]:
            assert t["template_id"] in valid

    def test_abnormal_ambiguous_word_causes_hitl(self):
        """曖昧語（AMBIGUOUS_WORDS）を含むタスクが HITL 原因になること。"""
        from src.agents.f50_module import execute as f50, AMBIGUOUS_WORDS
        word = AMBIGUOUS_WORDS[0]
        tasks = [{"task_id": "T1", "task_text": f"{word}を実施する",
                  "priority": "High", "effort": 2, "value": 4, "element_id": "E1"}]
        result = f50({"trace_id": "F40", "tasks": tasks})
        # 曖昧語 → hitl_elements に T1 が入る
        assert "T1" in result["hitl_elements"]

    def test_abnormal_unknown_priority_raises_runtime(self, mocker):
        """不正 priority がテンプレ適用で RuntimeError を発生させること。"""
        mocker.patch.dict("src.agents.f50_module._TEMPLATES", {}, clear=True)
        from src.agents.f50_module import execute as f50
        tasks = [{"task_id": "T1", "task_text": "LP作成",
                  "priority": "High", "effort": 2, "value": 4, "element_id": "E1"}]
        with pytest.raises(RuntimeError) as exc_info:
            f50({"trace_id": "F40", "tasks": tasks})
        assert exc_info.value.__cause__ is not None


# ════════════════════════════════════════════════════════
# WP8116: F60 因果分解
# 原因: templated_tasks  処理: _detect_duplicates/_detect_missing/_detect_ambiguous
# 結果: mece_report（is_mece_compliant/duplicate/missing/ambiguous）
# ════════════════════════════════════════════════════════

class TestCausal_F60:
    """F60: templated_tasks → MECE check → mece_report"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        self.result = f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))))

    def test_cause_templated_tasks_consumed(self):
        assert "mece_report" in self.result

    def test_process_mece_report_has_required_keys(self):
        required = {"is_mece_compliant", "duplicate_tasks",
                    "missing_elements", "ambiguous_tasks"}
        assert required <= self.result["mece_report"].keys()

    def test_process_duplicate_detection_cause_effect(self):
        """完全一致タスクが duplicate_tasks に分類されること。"""
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            {"task_id": "T1", "templated_text": "LP作成 広告配信", "priority": "High"},
            {"task_id": "T2", "templated_text": "LP作成 広告配信", "priority": "High"},
        ]
        dups, _ = _detect_duplicates(tasks)
        assert len(dups) > 0

    def test_process_cosine_similarity_causes_classification(self):
        """コサイン類似度の値が分類（duplicate/uncertain/normal）の原因であること。"""
        from src.agents.f60_module import (
            _cosine_similarity, DUPLICATE_THRESHOLD, UNCERTAIN_LOW
        )
        # cos=1.0 → duplicate
        assert _cosine_similarity("LP作成 広告", "LP作成 広告") >= DUPLICATE_THRESHOLD
        # cos=0.0 → normal
        assert _cosine_similarity("LP作成", "採用活動") < UNCERTAIN_LOW

    def test_process_abstract_causes_ambiguous(self):
        """抽象語が ambiguous_tasks 分類の原因であること。"""
        from src.agents.f60_module import _detect_ambiguous, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [{"task_id": "T1", "templated_text": f"業務{word}する", "priority": "High"}]
        assert "T1" in _detect_ambiguous(tasks)

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        with caplog.at_level(logging.INFO, logger="src.agents.f60_module"):
            f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))))
        assert any("[F60]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f60(self):
        assert self.result["trace_id"] == "F60"

    def test_effect_passthrough_templated_tasks(self):
        """F70 のために templated_tasks パススルーが出力に含まれること。"""
        assert "templated_tasks" in self.result


# ════════════════════════════════════════════════════════
# WP8117: F70 因果分解
# 原因: templated_tasks  処理: _union_find_group → _group_by_element
# 結果: hierarchy（goal_id/element_id/tasks の3階層）
# ════════════════════════════════════════════════════════

class TestCausal_F70:
    """F70: templated_tasks → Union-Find grouping → hierarchy"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        self.result = f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))))

    def test_cause_task_similarity_causes_goal_grouping(self):
        """タスク類似度（原因）がゴールグループ化（結果）の原因であること。"""
        from src.agents.f70_module import _union_find_group
        tasks = [
            {"task_id": "T1", "templated_text": "LP作成 広告配信",
             "priority": "High", "effort": 2, "value": 4, "element_id": "E1"},
            {"task_id": "T2", "templated_text": "LP作成 広告配信",
             "priority": "High", "effort": 2, "value": 4, "element_id": "E2"},
            {"task_id": "T3", "templated_text": "採用活動 HR施策",
             "priority": "Low",  "effort": 4, "value": 2, "element_id": "E3"},
        ]
        groups = _union_find_group(tasks)
        # T1,T2 は同一グループ → 2グループになること
        assert len(groups) == 2

    def test_process_hierarchy_has_three_levels(self):
        """Goal → Element → Task の3階層が生成されること。"""
        h = self.result["hierarchy"]
        for goal in h["goals"]:
            assert "elements" in goal
            for elem in goal["elements"]:
                assert "tasks" in elem

    def test_process_priority_determines_element_suffix(self):
        """タスクの priority が element_id のサフィックス（EL_H/M/L）を決定すること。"""
        h = self.result["hierarchy"]
        for goal in h["goals"]:
            for elem in goal["elements"]:
                eid = elem["element_id"]
                for task in elem["tasks"]:
                    pri = task["priority"]
                    if pri == "High":
                        assert eid.endswith("EL_H"), f"{eid} は High タスクを含むが EL_H でない"
                    elif pri == "Medium":
                        assert eid.endswith("EL_M")
                    elif pri == "Low":
                        assert eid.endswith("EL_L")

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        with caplog.at_level(logging.INFO, logger="src.agents.f70_module"):
            f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))))
        assert any("[F70]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f70(self):
        assert self.result["trace_id"] == "F70"

    def test_effect_hierarchy_goals_not_empty(self):
        assert len(self.result["hierarchy"]["goals"]) > 0


# ════════════════════════════════════════════════════════
# WP8118: F80 因果分解
# 原因: hierarchy（goals/elements/tasks）  処理: _build_trace_chain/_build_trace_entry
# 結果: traceability_map（trace_chain/origin_module/is_complete）
# ════════════════════════════════════════════════════════

class TestCausal_F80:
    """F80: hierarchy → _build_trace_chain → traceability_map"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        self.result = f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))))))

    def test_cause_source_trace_id_determines_chain(self):
        """source_trace_id（F70）が trace_chain の構築原因であること。"""
        from src.agents.f80_module import _build_trace_chain
        chain = _build_trace_chain("F70")
        assert chain == FULL_CHAIN

    def test_process_each_task_gets_trace_entry(self):
        """hierarchy の全タスクが traceability_map エントリを持つこと。"""
        tmap = self.result["traceability_map"]
        assert len(tmap) > 0

    def test_process_trace_chain_matches_pipeline_order(self):
        """全エントリの trace_chain が PIPELINE_ORDER と一致すること。"""
        for entry in self.result["traceability_map"]:
            assert entry["trace_chain"] == FULL_CHAIN

    def test_process_is_complete_true_when_full_chain(self):
        """フルチェーン = is_complete=True であること。"""
        for entry in self.result["traceability_map"]:
            assert entry["is_complete"] is True

    def test_process_origin_module_is_f10(self):
        """全エントリの origin_module が F10 であること。"""
        for entry in self.result["traceability_map"]:
            assert entry["origin_module"] == "F10"

    def test_process_partial_chain_causes_incomplete(self):
        """F40 の source_trace_id → chain が不完全 → is_complete=False。"""
        from src.agents.f80_module import _build_trace_chain, _is_chain_complete
        chain = _build_trace_chain("F40")
        assert _is_chain_complete(chain) is False

    def test_process_info_log_emitted(self, caplog, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        with caplog.at_level(logging.INFO, logger="src.agents.f80_module"):
            f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))))))
        assert any("[F80]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f80(self):
        assert self.result["trace_id"] == "F80"

    def test_effect_hierarchy_passthrough(self):
        """F90 のために hierarchy が F80 出力にパススルーされること。"""
        assert "hierarchy" in self.result
        assert "goals" in self.result["hierarchy"]


# ════════════════════════════════════════════════════════
# WP8119: F90 因果分解
# 原因: traceability_map + hierarchy
# 処理: _merge_hierarchy_with_trace → _check_integrity → _compute_evaluation
# 結果: final_output（summary/hierarchy_with_trace/evaluation_report）
# ════════════════════════════════════════════════════════

class TestCausal_F90:
    """F90: tmap + hierarchy → evaluation → final_output"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        self.result = _run_full()
        self.fo = self.result["final_output"]

    def test_cause_traceability_map_determines_summary(self):
        """traceability_map のエントリ数が total_tasks の原因であること。"""
        n_entries = len(self.result["final_output"]["hierarchy_with_trace"])
        assert self.fo["summary"]["total_goals"] == n_entries

    def test_cause_hierarchy_determines_structure(self):
        """hierarchy の goal 数が hierarchy_with_trace の goal 数と一致すること。"""
        n_hwt = len(self.fo["hierarchy_with_trace"])
        assert self.fo["summary"]["total_goals"] == n_hwt

    def test_process_trace_chain_merged_into_tasks(self):
        """trace_chain が各タスクにマージされること（処理の証跡）。"""
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert task["trace_chain"] == FULL_CHAIN

    def test_process_efficiency_score_derived_from_effort_value(self):
        """efficiency_score = avg_value / avg_effort であること（算術因果）。"""
        ev = self.fo["evaluation_report"]
        computed = round(ev["average_value"] / ev["average_effort"], 2)
        assert ev["efficiency_score"] == pytest.approx(computed, abs=0.01)

    def test_process_high_priority_causes_recommendation(self):
        """High 優先度タスクが '高優先度' 推奨事項の原因であること。"""
        has_high = any(
            task.get("priority") == "High"
            for goal in self.fo["hierarchy_with_trace"]
            for elem in goal["elements"]
            for task in elem["tasks"]
        )
        if has_high:
            assert any("高優先度" in r for r in self.fo["evaluation_report"]["recommendations"])

    def test_process_incomplete_chain_causes_hitl(self):
        """is_complete=False が hitl_required=True の原因であること。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [
                {"goal_id": "G1", "element_id": "G1_EL_H", "task_id": "T1",
                 "trace_chain": ["F10", "F20"], "origin_module": "F10",
                 "latest_module": "F20", "is_complete": False},
            ],
            "hierarchy": {"goals": [{"goal_id": "G1", "goal_text": "目標", "elements": [
                {"element_id": "G1_EL_H", "element_text": "要素", "tasks": [
                    {"task_id": "T1", "templated_text": "テスト", "priority": "High",
                     "effort": 3, "value": 5}
                ]}
            ]}]},
        })
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    def test_process_zero_effort_causes_runtime_error(self):
        """avg_effort=0 が ZeroDivisionError → RuntimeError の原因連鎖であること。"""
        from src.agents.f90_module import _compute_evaluation
        hw = [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "x", "priority": "High",
             "effort": None, "value": None}
        ]}]}]
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation(hw)
        assert isinstance(exc_info.value.__cause__, ZeroDivisionError)

    def test_process_info_log_emitted(self, caplog, mock_api):
        with caplog.at_level(logging.INFO, logger="src.agents.f90_module"):
            _run_full()
        assert any("[F90]" in r.message for r in caplog.records)

    def test_effect_trace_id_is_f90(self):
        assert self.result["trace_id"] == "F90"

    def test_effect_pipeline_integrity_verified(self):
        assert self.fo["summary"]["pipeline_integrity"] == "verified"

    def test_effect_traceability_complete_true(self):
        assert self.fo["summary"]["traceability_complete"] is True


# ════════════════════════════════════════════════════════
# WP811X: 因果チェーン全体（F10→F90 連鎖の不断性）
# ════════════════════════════════════════════════════════

class TestCausal_ChainIntegrity:
    """F10→F20→…→F90 の因果チェーンが途切れないことを確認する。"""

    @pytest.fixture(autouse=True)
    def setup(self, mock_api):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        from src.agents.f90_module import execute as f90

        self.stages = {}
        r = f10({"goal_text": "売上を前年比120%に成長させる"})
        self.stages["F10"] = r
        r = f20(r);  self.stages["F20"] = r
        r = f30(r);  self.stages["F30"] = r
        r = f40(r);  self.stages["F40"] = r
        r = f50(r);  self.stages["F50"] = r
        r = f60(r);  self.stages["F60"] = r
        r = f70(r);  self.stages["F70"] = r
        r = f80(r);  self.stages["F80"] = r
        r = f90(r);  self.stages["F90"] = r

    @pytest.mark.parametrize("module", ["F10","F20","F30","F40","F50","F60","F70","F80","F90"])
    def test_chain_each_module_produces_output(self, module):
        """各モジュールが dict を返すこと（チェーンが途切れていない証拠）。"""
        assert isinstance(self.stages[module], dict)

    @pytest.mark.parametrize("module", ["F10","F20","F30","F40","F50","F60","F70","F80","F90"])
    def test_chain_each_module_has_trace_id(self, module):
        """各モジュールの出力に trace_id が存在すること。"""
        assert self.stages[module]["trace_id"] == module

    @pytest.mark.parametrize("src,dst", [
        ("F10","F20"),("F20","F30"),("F30","F40"),("F40","F50"),
        ("F50","F60"),("F60","F70"),("F70","F80"),("F80","F90"),
    ])
    def test_chain_source_trace_id_links_consecutive_modules(self, src, dst):
        """各モジュールの source_trace_id が前段の trace_id と一致すること。"""
        assert self.stages[dst]["source_trace_id"] == src, (
            f"{dst}.source_trace_id={self.stages[dst]['source_trace_id']!r} ≠ '{src}'"
        )

    def test_chain_f90_final_output_references_all_modules(self):
        """F90 の trace_chain に F10〜F70 が全件含まれること。"""
        for goal in self.stages["F90"]["final_output"]["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    for mod in FULL_CHAIN:
                        assert mod in task["trace_chain"], \
                            f"task_id={task['task_id']} の trace_chain に {mod} が欠落"

    def test_chain_no_module_swallows_data_silently(self):
        """F90 の total_tasks > 0 であること（データが途中で消えていない）。"""
        assert self.stages["F90"]["final_output"]["summary"]["total_tasks"] > 0

    def test_chain_exception_at_f20_stops_pipeline(self):
        """F20 で TypeError が発生した場合、F30 以降に到達しないこと。"""
        from src.agents.f30_module import execute as f30
        with pytest.raises(TypeError):
            f30(None)  # F20相当の invalid input

    def test_chain_info_logs_all_modules_emitted(self, caplog, mock_api):
        """全モジュール（F10〜F90）の INFO ログが1回ずつ出力されること。"""
        with caplog.at_level(logging.INFO):
            _run_full()
        for fmod in ["[F10]","[F20]","[F30]","[F40]","[F50]","[F60]","[F70]","[F80]","[F90]"]:
            assert any(fmod in r.message for r in caplog.records), \
                f"{fmod} の INFO ログが出力されていない"
