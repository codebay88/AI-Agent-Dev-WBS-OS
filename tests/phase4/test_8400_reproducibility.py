"""Phase 4 — WP8400 再現性テスト
区分：同条件再実行 / 出力安定性 / WBS適用性

WP8400 の観点：
  - 同一入力に対して複数回実行しても出力が一貫していること
  - 構造的フィールド（task_id 命名規則・trace_chain 等）が安定していること
  - WBS としての適用性（ゴール→要素→タスクの階層完全性）を検証すること
"""

import pytest


# L1 に数値表現を含め importance=0.95 → High priority を保証する
_MOCK_API_RESPONSE = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


@pytest.fixture
def pipeline(mocker):
    """共通パイプライン実行フィクスチャ（API モック付き）。"""
    mocker.patch(
        "src.agents.f10_module._call_api",
        return_value=_MOCK_API_RESPONSE,
    )
    from src.agents.f10_module import execute as f10
    from src.agents.f20_module import execute as f20
    from src.agents.f30_module import execute as f30
    from src.agents.f40_module import execute as f40
    from src.agents.f50_module import execute as f50
    from src.agents.f60_module import execute as f60
    from src.agents.f70_module import execute as f70
    from src.agents.f80_module import execute as f80
    from src.agents.f90_module import execute as f90

    def run(goal="売上を前年比120%に成長させる"):
        return f90(f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": goal})))))))))

    return run


# ════════════════════════════════════════════════════════
# WP8410: 同条件再実行（3回連続で構造的に一致すること）
# ════════════════════════════════════════════════════════

class TestWP8410_SameConditionRerun:
    """同一入力で3回実行し、構造的フィールドが一致することを検証する。"""

    GOAL = "売上を前年比120%に成長させる"

    def test_trace_id_stable_across_runs(self, pipeline):
        results = [pipeline(self.GOAL) for _ in range(3)]
        assert all(r["trace_id"] == "F90" for r in results)

    def test_total_goals_stable_across_runs(self, pipeline):
        counts = [pipeline(self.GOAL)["final_output"]["summary"]["total_goals"]
                  for _ in range(3)]
        assert len(set(counts)) == 1, f"total_goals が不安定: {counts}"

    def test_total_tasks_stable_across_runs(self, pipeline):
        counts = [pipeline(self.GOAL)["final_output"]["summary"]["total_tasks"]
                  for _ in range(3)]
        assert len(set(counts)) == 1, f"total_tasks が不安定: {counts}"

    def test_traceability_complete_stable_across_runs(self, pipeline):
        flags = [pipeline(self.GOAL)["final_output"]["summary"]["traceability_complete"]
                 for _ in range(3)]
        assert all(flags), f"traceability_complete が不安定: {flags}"

    def test_efficiency_score_stable_across_runs(self, pipeline):
        scores = [pipeline(self.GOAL)["final_output"]["evaluation_report"]["efficiency_score"]
                  for _ in range(3)]
        assert len(set(scores)) == 1, f"efficiency_score が不安定: {scores}"

    def test_hitl_required_stable_across_runs(self, pipeline):
        flags = [pipeline(self.GOAL)["hitl_required"] for _ in range(3)]
        assert len(set(flags)) == 1, f"hitl_required が不安定: {flags}"

    def test_pipeline_integrity_stable_across_runs(self, pipeline):
        values = [pipeline(self.GOAL)["final_output"]["summary"]["pipeline_integrity"]
                  for _ in range(3)]
        assert all(v == "verified" for v in values)


# ════════════════════════════════════════════════════════
# WP8420: 出力安定性（命名規則・型・構造の安定性）
# ════════════════════════════════════════════════════════

class TestWP8420_OutputStability:
    """出力の命名規則・型・構造が仕様どおりに安定していること。"""

    @pytest.fixture(autouse=True)
    def run(self, pipeline):
        self.result = pipeline()
        self.fo = self.result["final_output"]

    def test_task_ids_are_strings(self):
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert isinstance(task["task_id"], str), \
                        f"task_id が str でない: {task['task_id']!r}"

    def test_goal_ids_are_strings(self):
        for goal in self.fo["hierarchy_with_trace"]:
            assert isinstance(goal["goal_id"], str)

    def test_element_ids_are_strings(self):
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                assert isinstance(elem["element_id"], str)

    def test_trace_chain_contains_only_valid_modules(self):
        valid = {"F10", "F20", "F30", "F40", "F50", "F60", "F70"}
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    for m in task["trace_chain"]:
                        assert m in valid, f"不正なモジュール名: {m}"

    def test_priority_values_are_valid(self):
        valid = {"High", "Medium", "Low"}
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert task.get("priority") in valid, \
                        f"不正 priority: {task.get('priority')}"

    def test_templated_text_contains_priority_marker(self):
        """templated_text が 【優先度: X】 で始まること。"""
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    txt = task.get("templated_text", "")
                    assert txt.startswith("【優先度:"), \
                        f"templated_text の書式が不正: {txt!r}"

    def test_effort_and_value_are_numeric(self):
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert isinstance(task.get("effort"), (int, float)), \
                        f"effort が数値でない: {task.get('effort')!r}"
                    assert isinstance(task.get("value"), (int, float)), \
                        f"value が数値でない: {task.get('value')!r}"

    def test_recommendations_are_strings(self):
        recs = self.fo["evaluation_report"]["recommendations"]
        for r in recs:
            assert isinstance(r, str), f"recommendation が str でない: {r!r}"

    def test_hitl_elements_contains_only_strings(self):
        for item in self.result["hitl_elements"]:
            assert isinstance(item, str), f"hitl_elements に str 以外: {item!r}"

    def test_summary_counts_are_non_negative_int(self):
        s = self.fo["summary"]
        for key in ("total_goals", "total_elements", "total_tasks"):
            assert isinstance(s[key], int) and s[key] >= 0, \
                f"{key} が非負整数でない: {s[key]}"


# ════════════════════════════════════════════════════════
# WP8430: WBS 適用性（階層完全性・トレーサビリティ完全性）
# ════════════════════════════════════════════════════════

class TestWP8430_WBSApplicability:
    """WBS としての適用性 — 階層の完全性とトレーサビリティを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self, pipeline):
        self.result = pipeline()
        self.fo = self.result["final_output"]

    def test_hierarchy_three_levels(self):
        """Goal → Element → Task の3階層が存在すること。"""
        for goal in self.fo["hierarchy_with_trace"]:
            assert "elements" in goal
            for elem in goal["elements"]:
                assert "tasks" in elem
                assert len(elem["tasks"]) > 0

    def test_all_goals_have_at_least_one_element(self):
        for goal in self.fo["hierarchy_with_trace"]:
            assert len(goal["elements"]) > 0, \
                f"goal_id={goal['goal_id']} に element がない"

    def test_all_elements_have_at_least_one_task(self):
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                assert len(elem["tasks"]) > 0, \
                    f"element_id={elem['element_id']} に task がない"

    def test_task_count_matches_summary(self):
        """hierarchy_with_trace のタスク総数が summary.total_tasks と一致すること。"""
        counted = sum(
            len(elem["tasks"])
            for goal in self.fo["hierarchy_with_trace"]
            for elem in goal["elements"]
        )
        assert counted == self.fo["summary"]["total_tasks"], \
            f"タスク数不一致: counted={counted}, summary={self.fo['summary']['total_tasks']}"

    def test_goal_count_matches_summary(self):
        counted = len(self.fo["hierarchy_with_trace"])
        assert counted == self.fo["summary"]["total_goals"]

    def test_element_count_matches_summary(self):
        counted = sum(
            len(goal["elements"]) for goal in self.fo["hierarchy_with_trace"]
        )
        assert counted == self.fo["summary"]["total_elements"]

    def test_all_task_ids_unique_in_hierarchy(self):
        task_ids = [
            task["task_id"]
            for goal in self.fo["hierarchy_with_trace"]
            for elem in goal["elements"]
            for task in elem["tasks"]
        ]
        assert len(task_ids) == len(set(task_ids)), \
            f"task_id に重複あり: {[t for t in task_ids if task_ids.count(t) > 1]}"

    def test_all_goal_ids_unique(self):
        goal_ids = [g["goal_id"] for g in self.fo["hierarchy_with_trace"]]
        assert len(goal_ids) == len(set(goal_ids))

    def test_traceability_covers_all_tasks(self):
        """traceability_complete=True のとき、全タスクが完全な trace_chain を持つこと。"""
        if not self.fo["summary"]["traceability_complete"]:
            pytest.skip("traceability_complete=False のため対象外")
        full_chain = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert task["trace_chain"] == full_chain, \
                        f"task_id={task['task_id']} の trace_chain が不完全"

    def test_wbs_element_ids_follow_naming_convention(self):
        """element_id が 'G\\d+_EL_[HML]' パターンに従うこと。"""
        import re
        pattern = re.compile(r"^G\d+_EL_[HML]$")
        for goal in self.fo["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                eid = elem["element_id"]
                assert pattern.match(eid), \
                    f"element_id の命名規則違反: {eid!r}"

    def test_high_priority_tasks_exist(self):
        """High 優先度タスクが少なくとも1件存在すること。"""
        has_high = any(
            task.get("priority") == "High"
            for goal in self.fo["hierarchy_with_trace"]
            for elem in goal["elements"]
            for task in elem["tasks"]
        )
        assert has_high, "High 優先度タスクが存在しない"

    def test_recommendations_reference_high_priority(self):
        """High タスクがある場合、recommendations に '高優先度' が含まれること。"""
        recs = self.fo["evaluation_report"]["recommendations"]
        assert any("高優先度" in r for r in recs), \
            f"'高優先度' の推奨事項がない: {recs}"
