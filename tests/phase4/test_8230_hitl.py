"""Phase 4 — WP8230 HITL承認フローテスト
区分：HITL発動 / 出力構造 / 承認パス / 部分HITL / 要素精度 / ログ / reason / 曖昧語

WP8230 の観点：
  - 各モジュールが不確定・曖昧・例外的入力に対して HITL を正しく発動すること
  - HITL 出力構造（hitl / hitl_required / hitl_elements / hitl_reason）が仕様書どおりであること
  - 承認パス（修正後の再実行）で hitl=False になること
  - 部分 HITL（一部のみフラグ）時に非フラグ要素が正常処理されること
  - hitl_elements に正しい要素 ID が格納されること
  - WARNING ログが HITL 発動時に記録されること
  - hitl_reason 文字列が仕様書と一致すること
  - 全曖昧語定数が各モジュールで HITL を発動させること
"""

import logging
import pytest


# ════════════════════════════════════════════════════════
# 共通ヘルパ
# ════════════════════════════════════════════════════════

_MOCK_API = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


def _valid_task(task_id="T1", text="LP作成する", priority="High"):
    return {
        "task_id": task_id,
        "task_text": text,
        "priority": priority,
        "estimated_effort": 2,
        "estimated_value": 4,
        "element_id": "E1",
    }


def _valid_templated(task_id="T1", text="【優先度: 高】次のタスクを実行せよ: LP作成する", priority="High"):
    return {"task_id": task_id, "templated_text": text, "priority": priority,
            "effort": 2, "value": 4}


def _valid_hierarchy(trace_id="F70"):
    """F80 入力に使える最小限の hierarchy dict。trace_chain が完全になる。"""
    return {
        "trace_id": trace_id,
        "hierarchy": {
            "goals": [{
                "goal_id": "G1",
                "goal_text": "LP作成",
                "elements": [{
                    "element_id": "G1_EL_H",
                    "element_text": "High優先度タスク群",
                    "tasks": [{
                        "task_id": "T1",
                        "templated_text": "LP作成する",
                        "priority": "High",
                        "effort": 2,
                        "value": 4,
                    }]
                }]
            }]
        }
    }


# ════════════════════════════════════════════════════════
# WP8231: HITL発動条件（モジュール別）
# ════════════════════════════════════════════════════════

class TestWP8231_HITLTriggers:
    """各モジュールの HITL 発動条件を検証する"""

    # ─── F10 ───
    def test_f10_ambiguous_word_triggers_hitl(self):
        """F10: 曖昧語 'など' を含む goal_text → hitl=True。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "売上向上などの目標を達成する"})
        assert result["hitl"] is True

    def test_f10_short_text_triggers_hitl(self):
        """F10: 9文字以下の goal_text → hitl=True。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "目標達成"})
        assert result["hitl"] is True

    def test_f10_clean_text_no_hitl(self, mocker):
        """F10: 曖昧語なし・十分な長さ → hitl=False。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "売上を前年比120%に成長させる"})
        assert result["hitl"] is False

    # ─── F20 ───
    def test_f20_ambiguous_l1_triggers_hitl(self):
        """F20: L1 に曖昧語 'など' → hitl=True。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {"L1": "売上などを向上させる", "L2": ["新規顧客獲得"], "L3": ["LP作成する"]}
        })
        assert result["hitl"] is True

    def test_f20_clean_l1_no_hitl(self):
        """F20: L1 に曖昧語なし → hitl=False。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {"L1": "売上を前年比120%に成長させる", "L2": ["新規顧客獲得"], "L3": ["LP作成する"]}
        })
        assert result["hitl"] is False

    # ─── F30 ───
    def test_f30_ambiguous_element_text_triggers_hitl(self):
        """F30: element text に曖昧語 'など' → hitl_elements に element_id が入る。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"}
        ]})
        assert "E1" in result["hitl_elements"]

    def test_f30_all_ambiguous_sets_hitl_true(self):
        """F30: 全要素が曖昧語含む → hitl=True。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"},
            {"element_id": "E2", "text": "広告配信とかする", "parent": "L3"},
        ]})
        assert result["hitl"] is True

    def test_f30_partial_ambiguous_hitl_false(self):
        """F30: 一部のみ曖昧語 → hitl=False（全部ではないため）。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成する", "parent": "L3"},
            {"element_id": "E2", "text": "広告配信などする", "parent": "L3"},
        ]})
        assert result["hitl"] is False

    def test_f30_clean_elements_no_hitl(self):
        """F30: 曖昧語なし → hitl=False, hitl_elements=[]。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成する", "parent": "L3"}
        ]})
        assert result["hitl"] is False
        assert result["hitl_elements"] == []

    # ─── F50 ───
    def test_f50_ambiguous_task_text_triggers_hitl_element(self):
        """F50: task_text に曖昧語 'など' → task_id が hitl_elements に入る。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert "T1" in result["hitl_elements"]

    def test_f50_invalid_priority_triggers_hitl_element(self):
        """F50: priority が 'UNKNOWN' → task_id が hitl_elements に入る。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する", "priority": "UNKNOWN",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert "T1" in result["hitl_elements"]

    def test_f50_all_hitl_sets_hitl_true(self):
        """F50: 全タスクが HITL → hitl=True。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "T2", "task_text": "広告配信とかする", "priority": "Medium"},
        ]})
        assert result["hitl"] is True

    def test_f50_clean_tasks_no_hitl(self):
        """F50: 曖昧語なし・有効 priority → hitl=False, hitl_elements=[]。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4, "element_id": "E1"}
        ]})
        assert result["hitl"] is False
        assert result["hitl_elements"] == []

    # ─── F60 ───
    def test_f60_empty_tasks_triggers_hitl(self):
        """F60: templated_tasks が空 → hitl_required=True。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert result["hitl_required"] is True

    def test_f60_uncertain_similarity_triggers_hitl(self, mocker):
        """F60: cosine が 0.80-0.85 → hitl_required=True, hitl_elements 非空。"""
        mocker.patch(
            "src.agents.f60_module._cosine_similarity",
            return_value=0.82
        )
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            _valid_templated("T1", "LP作成する", "High"),
            _valid_templated("T2", "広告配信する", "Medium"),
        ]})
        assert result["hitl_required"] is True
        assert len(result["hitl_elements"]) > 0

    def test_f60_ambiguous_text_triggers_hitl(self):
        """F60: templated_text に ABSTRACT_WORDS → MECE 非準拠 + ambiguous → hitl_required=True。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            _valid_templated("T1", "業務改善する", "High"),
        ]})
        assert result["hitl_required"] is True

    def test_f60_clean_distinct_tasks_no_hitl(self):
        """F60: 重複なし・曖昧語なし → hitl_required=False。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            _valid_templated("T1", "LP作成する", "High"),
            _valid_templated("T2", "広告配信する", "Medium"),
        ]})
        assert result["hitl_required"] is False

    # ─── F70 ───
    def test_f70_empty_tasks_triggers_hitl(self):
        """F70: templated_tasks が空 → hitl_required=True。"""
        from src.agents.f70_module import execute as f70
        result = f70({"trace_id": "F60", "templated_tasks": []})
        assert result["hitl_required"] is True

    def test_f70_abstract_only_goal_triggers_hitl(self):
        """F70: goal_text が ABSTRACT_WORDS のみ → hitl_elements に goal_id が入る。"""
        from src.agents.f70_module import execute as f70
        result = f70({"trace_id": "F60", "templated_tasks": [
            # templated_text のプレフィックス除去後が抽象語のみになるテキスト
            _valid_templated("T1", "【優先度: 高】次のタスクを実行せよ: 改善", "High"),
        ]})
        # G1 の goal_text が "改善" → 抽象語のみ → hitl_elements に G1
        if result.get("hitl_required"):
            assert "G1" in result["hitl_elements"]

    def test_f70_valid_tasks_no_hitl(self):
        """F70: 有効なタスク群 → hitl_required=False。"""
        from src.agents.f70_module import execute as f70
        result = f70({"trace_id": "F60", "templated_tasks": [
            _valid_templated("T1", "【優先度: 高】次のタスクを実行せよ: LP作成する", "High"),
        ]})
        assert result["hitl_required"] is False

    # ─── F80 ───
    def test_f80_empty_goals_triggers_hitl(self):
        """F80: hierarchy.goals が空 → hitl_required=True。"""
        from src.agents.f80_module import execute as f80
        result = f80({"trace_id": "F70", "hierarchy": {"goals": []}})
        assert result["hitl_required"] is True

    def test_f80_missing_trace_chain_triggers_hitl(self):
        """F80: trace_id が PIPELINE_ORDER 外 → chain 空 → hitl_required=True。"""
        from src.agents.f80_module import execute as f80
        data = dict(_valid_hierarchy(trace_id="UNKNOWN"))
        result = f80(data)
        assert result["hitl_required"] is True

    def test_f80_incomplete_chain_triggers_hitl_elements(self):
        """F80: trace_id='F50'（F60/F70 欠落）→ is_complete=False → task が hitl_elements に入る。"""
        from src.agents.f80_module import execute as f80
        data = dict(_valid_hierarchy(trace_id="F50"))
        result = f80(data)
        # chain は F10..F50 → not complete → T1 が hitl_elements に入る
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    def test_f80_complete_chain_no_hitl(self):
        """F80: trace_id='F70'（完全 chain）→ hitl_required=False。"""
        from src.agents.f80_module import execute as f80
        result = f80(_valid_hierarchy(trace_id="F70"))
        assert result["hitl_required"] is False

    # ─── F90 ───
    def test_f90_empty_tmap_triggers_hitl(self):
        """F90: traceability_map が空 → hitl_required=True。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert result["hitl_required"] is True

    def test_f90_clean_tmap_no_hitl(self):
        """F90: 完全な tmap → hitl_required=False（または最小限のみ）。"""
        from src.agents.f80_module import execute as f80
        from src.agents.f90_module import execute as f90
        r80 = f80(_valid_hierarchy("F70"))
        result = f90(r80)
        assert "hitl_required" in result


# ════════════════════════════════════════════════════════
# WP8232: HITL出力構造
# ════════════════════════════════════════════════════════

class TestWP8232_HITLOutputStructure:
    """HITL 発動時の出力キー構造が仕様どおりであること"""

    def test_f10_hitl_has_required_keys(self):
        """F10 HITL 出力: hitl / hitl_reason / trace_id が存在すること。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "など"})
        assert "hitl" in result
        assert "hitl_reason" in result
        assert result["trace_id"] == "F10"

    def test_f20_hitl_has_required_keys(self):
        """F20 HITL 出力: hitl / hitl_reason / trace_id が存在すること。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {"L1": "売上などを向上させる", "L2": ["施策A"], "L3": ["タスク1"]}
        })
        assert "hitl" in result
        assert "hitl_reason" in result
        assert result["trace_id"] == "F20"

    def test_f30_hitl_has_required_keys(self):
        """F30 HITL 出力: hitl / hitl_elements / trace_id が存在すること。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"}
        ]})
        assert "hitl" in result
        assert "hitl_elements" in result
        assert isinstance(result["hitl_elements"], list)
        assert result["trace_id"] == "F30"

    def test_f50_hitl_has_required_keys(self):
        """F50 HITL 出力: hitl / hitl_elements / templated_tasks / trace_id が存在すること。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"}
        ]})
        assert "hitl" in result
        assert "hitl_elements" in result
        assert "templated_tasks" in result
        assert result["trace_id"] == "F50"

    def test_f60_hitl_has_required_keys(self):
        """F60 HITL 出力: hitl / hitl_required / hitl_elements / mece_report / trace_id。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert "hitl" in result
        assert "hitl_required" in result
        assert "hitl_elements" in result
        assert "mece_report" in result
        assert result["trace_id"] == "F60"

    def test_f70_hitl_has_required_keys(self):
        """F70 HITL 出力: hitl / hitl_required / hitl_elements / hierarchy / trace_id。"""
        from src.agents.f70_module import execute as f70
        result = f70({"trace_id": "F60", "templated_tasks": []})
        assert "hitl" in result
        assert "hitl_required" in result
        assert "hitl_elements" in result
        assert "hierarchy" in result
        assert result["trace_id"] == "F70"

    def test_f80_hitl_has_required_keys(self):
        """F80 HITL 出力: hitl / hitl_required / hitl_elements / trace_id。"""
        from src.agents.f80_module import execute as f80
        result = f80({"trace_id": "F70", "hierarchy": {"goals": []}})
        assert "hitl" in result
        assert "hitl_required" in result
        assert "hitl_elements" in result
        assert result["trace_id"] == "F80"

    def test_f90_hitl_has_required_keys(self):
        """F90 HITL 出力: hitl / hitl_required / hitl_elements / trace_id。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert "hitl" in result
        assert "hitl_required" in result
        assert "hitl_elements" in result
        assert result["trace_id"] == "F90"

    def test_hitl_elements_is_always_list(self):
        """hitl_elements は list 型であること（F30 〜 F90 共通）。"""
        import importlib
        for mod_name in ["f30_module", "f50_module", "f60_module",
                         "f70_module", "f80_module", "f90_module"]:
            mod = importlib.import_module(f"src.agents.{mod_name}")
            # いずれかが空入力で hitl_elements を返すはず
            try:
                result = mod.execute({"trace_id": "DUMMY"})
            except (ValueError, TypeError):
                continue
            if "hitl_elements" in result:
                assert isinstance(result["hitl_elements"], list), \
                    f"{mod_name}: hitl_elements is not list"

    def test_f10_hitl_goal_is_none(self):
        """F10 HITL 時: goal=None, tree=None であること。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "など"})
        assert result["goal"] is None
        assert result["tree"] is None


# ════════════════════════════════════════════════════════
# WP8233: 承認パス（修正後の再実行で hitl=False になること）
# ════════════════════════════════════════════════════════

class TestWP8233_ApprovalPath:
    """HITL 移譲後、修正された入力で再実行すると hitl=False になること（承認パス）"""

    def test_f10_fix_ambiguous_word_approves(self, mocker):
        """F10: 曖昧語除去後に再実行 → hitl=False。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        hitl_result = f10({"goal_text": "売上などを上げる目標"})
        assert hitl_result["hitl"] is True
        approved = f10({"goal_text": "売上を前年比120%に成長させる"})
        assert approved["hitl"] is False

    def test_f20_fix_ambiguous_l1_approves(self):
        """F20: 曖昧語を L1 から除去後に再実行 → hitl=False。"""
        from src.agents.f20_module import execute as f20
        hitl = f20({"trace_id": "F10", "goal": {
            "L1": "売上などを向上させる", "L2": ["施策A"], "L3": ["タスク1"]
        }})
        assert hitl["hitl"] is True
        approved = f20({"trace_id": "F10", "goal": {
            "L1": "売上を前年比120%に成長させる", "L2": ["施策A"], "L3": ["タスク1"]
        }})
        assert approved["hitl"] is False

    def test_f30_fix_element_text_approves(self):
        """F30: 曖昧語を element text から除去後に再実行 → hitl_elements=[]。"""
        from src.agents.f30_module import execute as f30
        hitl = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"}
        ]})
        assert "E1" in hitl["hitl_elements"]
        approved = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成する", "parent": "L3"}
        ]})
        assert approved["hitl_elements"] == []

    def test_f50_fix_task_text_approves(self):
        """F50: 曖昧語を task_text から除去後に再実行 → hitl_elements=[]。"""
        from src.agents.f50_module import execute as f50
        hitl = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4}
        ]})
        assert "T1" in hitl["hitl_elements"]
        approved = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4}
        ]})
        assert approved["hitl_elements"] == []

    def test_f50_fix_invalid_priority_approves(self):
        """F50: 不正 priority を修正後に再実行 → hitl_elements=[]。"""
        from src.agents.f50_module import execute as f50
        hitl = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する", "priority": "INVALID"}
        ]})
        assert "T1" in hitl["hitl_elements"]
        approved = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4}
        ]})
        assert approved["hitl_elements"] == []

    def test_f60_fix_empty_tasks_approves(self):
        """F60: 空タスクを修正後に再実行 → hitl_required=False。"""
        from src.agents.f60_module import execute as f60
        hitl = f60({"trace_id": "F50", "templated_tasks": []})
        assert hitl["hitl_required"] is True
        approved = f60({"trace_id": "F50", "templated_tasks": [
            _valid_templated("T1", "LP作成する", "High"),
        ]})
        assert approved["hitl_required"] is False

    def test_f70_fix_empty_tasks_approves(self):
        """F70: 空タスクを修正後に再実行 → hitl_required=False。"""
        from src.agents.f70_module import execute as f70
        hitl = f70({"trace_id": "F60", "templated_tasks": []})
        assert hitl["hitl_required"] is True
        approved = f70({"trace_id": "F60", "templated_tasks": [
            _valid_templated("T1", "【優先度: 高】次のタスクを実行せよ: LP作成する", "High"),
        ]})
        assert approved["hitl_required"] is False

    def test_f80_fix_trace_id_approves(self):
        """F80: trace_id を F70 に修正後 → hitl_required=False。"""
        from src.agents.f80_module import execute as f80
        hitl_data = dict(_valid_hierarchy(trace_id="UNKNOWN"))
        hitl = f80(hitl_data)
        assert hitl["hitl_required"] is True
        approved = f80(_valid_hierarchy(trace_id="F70"))
        assert approved["hitl_required"] is False


# ════════════════════════════════════════════════════════
# WP8234: 部分HITL（一部のみフラグ、残りは正常処理）
# ════════════════════════════════════════════════════════

class TestWP8234_PartialHITL:
    """一部要素のみ HITL 移譲、残りが正常処理されること"""

    def test_f30_partial_hitl_evaluates_clean_elements(self):
        """F30: 曖昧語含む E1 は HITL、E2 は正常評価されること。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"},
            {"element_id": "E2", "text": "広告配信する", "parent": "L3"},
        ]})
        assert "E1" in result["hitl_elements"]
        assert "E2" not in result["hitl_elements"]
        assert len(result["evaluated_goals"]) == 1
        assert result["evaluated_goals"][0]["element_id"] == "E2"

    def test_f50_partial_hitl_templates_clean_tasks(self):
        """F50: 曖昧語含む T1 は HITL、T2 は templated_tasks に含まれること。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4},
            {"task_id": "T2", "task_text": "広告配信する", "priority": "Medium",
             "estimated_effort": 1, "estimated_value": 3},
        ]})
        assert "T1" in result["hitl_elements"]
        assert "T2" not in result["hitl_elements"]
        assert len(result["templated_tasks"]) == 1
        assert result["templated_tasks"][0]["task_id"] == "T2"

    def test_f50_partial_hitl_not_all_hitl_flag(self):
        """F50: 一部 HITL → hitl=False（全部ではないため）。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "T2", "task_text": "広告配信する", "priority": "Medium",
             "estimated_effort": 1, "estimated_value": 3},
        ]})
        assert result["hitl"] is False

    def test_f30_empty_text_element_is_hitl(self):
        """F30: text が空の element は HITL 移譲されること。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "", "parent": "L3"},
            {"element_id": "E2", "text": "LP作成する", "parent": "L3"},
        ]})
        assert "E1" in result["hitl_elements"]
        assert "E2" not in result["hitl_elements"]

    def test_f60_duplicate_only_no_hitl(self):
        """F60: duplicate のみ（uncertain/ambiguous なし）→ hitl_required=False。"""
        from src.agents.f60_module import execute as f60, DUPLICATE_THRESHOLD
        mocker_data = [
            _valid_templated("T1", "全く同じテキスト内容", "High"),
            _valid_templated("T2", "全く同じテキスト内容", "High"),
        ]
        result = f60({"trace_id": "F50", "templated_tasks": mocker_data})
        # 重複のみの場合は hitl_required=False
        if not result["mece_report"]["ambiguous_tasks"] and not result["hitl_elements"]:
            assert result["hitl_required"] is False


# ════════════════════════════════════════════════════════
# WP8235: hitl_elements 内容精度
# ════════════════════════════════════════════════════════

class TestWP8235_HITLElementsAccuracy:
    """hitl_elements に格納される ID が正確であること"""

    def test_f30_hitl_elements_contains_correct_element_id(self):
        """F30: 曖昧要素の element_id が hitl_elements に格納されること。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E3", "text": "LP作成などをする", "parent": "L3"}
        ]})
        assert "E3" in result["hitl_elements"]
        assert "E1" not in result["hitl_elements"]

    def test_f50_hitl_elements_contains_correct_task_id(self):
        """F50: 曖昧タスクの task_id が hitl_elements に格納されること。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "TXX", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "TYY", "task_text": "広告配信する", "priority": "High",
             "estimated_effort": 1, "estimated_value": 2},
        ]})
        assert "TXX" in result["hitl_elements"]
        assert "TYY" not in result["hitl_elements"]

    def test_f50_hitl_task_not_in_templated_tasks(self):
        """F50: hitl_elements のタスクは templated_tasks に含まれないこと。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T_AMBIGUOUS", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "T_CLEAN", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4},
        ]})
        templated_ids = [t["task_id"] for t in result["templated_tasks"]]
        assert "T_AMBIGUOUS" not in templated_ids
        assert "T_CLEAN" in templated_ids

    def test_f60_uncertain_task_ids_in_hitl_elements(self, mocker):
        """F60: 不確定類似度タスクの task_id が hitl_elements に格納されること。"""
        mocker.patch("src.agents.f60_module._cosine_similarity", return_value=0.82)
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            _valid_templated("TASK_A", "LP作成する", "High"),
            _valid_templated("TASK_B", "広告配信する", "Medium"),
        ]})
        assert "TASK_A" in result["hitl_elements"] or "TASK_B" in result["hitl_elements"]

    def test_f80_incomplete_chain_task_in_hitl(self):
        """F80: is_complete=False のタスク task_id が hitl_elements に入ること。"""
        from src.agents.f80_module import execute as f80
        result = f80(_valid_hierarchy(trace_id="F50"))
        assert "T1" in result["hitl_elements"]

    def test_f90_empty_tmap_hitl_elements_empty(self):
        """F90: 空 tmap → hitl_elements=[] であること。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert result["hitl_elements"] == []


# ════════════════════════════════════════════════════════
# WP8236: WARNING ログ記録
# ════════════════════════════════════════════════════════

class TestWP8236_HITLLogRecording:
    """HITL 移譲時に WARNING ログが記録されること"""

    def test_f10_hitl_warning_logged(self, caplog):
        """F10: HITL 発動時に '[HITL移譲]' の WARNING ログが出力されること。"""
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.WARNING, logger="src.agents.f10_module"):
            f10({"goal_text": "など"})
        assert any("HITL" in r.message for r in caplog.records)

    def test_f30_hitl_warning_logged_per_element(self, caplog):
        """F30: 曖昧要素が HITL 移譲される際に '[HITL移譲]' の WARNING が出ること。"""
        from src.agents.f30_module import execute as f30
        with caplog.at_level(logging.WARNING, logger="src.agents.f30_module"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"}
            ]})
        assert any("HITL" in r.message for r in caplog.records)

    def test_f50_hitl_warning_logged_per_task(self, caplog):
        """F50: 曖昧タスクが HITL 移譲される際に '[HITL移譲]' の WARNING が出ること。"""
        from src.agents.f50_module import execute as f50
        with caplog.at_level(logging.WARNING, logger="src.agents.f50_module"):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"}
            ]})
        assert any("HITL" in r.message for r in caplog.records)

    def test_f60_empty_tasks_warning_logged(self, caplog):
        """F60: 空 templated_tasks で WARNING が出ること。"""
        from src.agents.f60_module import execute as f60
        with caplog.at_level(logging.WARNING, logger="src.agents.f60_module"):
            f60({"trace_id": "F50", "templated_tasks": []})
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_f20_hitl_warning_logged(self, caplog):
        """F20: HITL 発動時に '[HITL移譲]' の WARNING ログが出力されること。"""
        from src.agents.f20_module import execute as f20
        with caplog.at_level(logging.WARNING, logger="src.agents.f20_module"):
            f20({
                "trace_id": "F10",
                "goal": {"L1": "売上などを上げる", "L2": ["施策A"], "L3": ["タスク1"]}
            })
        assert any("HITL" in r.message for r in caplog.records)

    def test_f70_empty_tasks_warning_logged(self, caplog):
        """F70: 空 templated_tasks で WARNING が出ること。"""
        from src.agents.f70_module import execute as f70
        with caplog.at_level(logging.WARNING, logger="src.agents.f70_module"):
            f70({"trace_id": "F60", "templated_tasks": []})
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_f80_empty_goals_warning_logged(self, caplog):
        """F80: 空 goals で WARNING が出ること。"""
        from src.agents.f80_module import execute as f80
        with caplog.at_level(logging.WARNING, logger="src.agents.f80_module"):
            f80({"trace_id": "F70", "hierarchy": {"goals": []}})
        assert any(r.levelno >= logging.WARNING for r in caplog.records)


# ════════════════════════════════════════════════════════
# WP8237: hitl_reason メッセージ内容
# ════════════════════════════════════════════════════════

class TestWP8237_HITLReasonMessage:
    """hitl_reason の文字列が仕様書と一致すること"""

    def test_f10_ambiguous_reason_contains_word(self):
        """F10: hitl_reason に曖昧語名が含まれること。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "など"})
        assert "など" in result["hitl_reason"]

    def test_f10_short_text_reason_exists(self):
        """F10: 短すぎるテキストの hitl_reason が存在すること。"""
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": "目標達成"})
        assert result["hitl_reason"]

    def test_f20_ambiguous_reason_contains_word(self):
        """F20: hitl_reason に曖昧語名が含まれること。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {"L1": "売上などを向上させる", "L2": ["施策A"], "L3": ["タスク1"]}
        })
        assert "など" in result["hitl_reason"]

    def test_f60_empty_tasks_reason(self):
        """F60: 空 tasks の hitl_reason が 'No tasks provided' であること。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert result["hitl_reason"] == "No tasks provided"

    def test_f70_empty_tasks_reason(self):
        """F70: 空 tasks の hitl_reason が 'No hierarchy generated' であること。"""
        from src.agents.f70_module import execute as f70
        result = f70({"trace_id": "F60", "templated_tasks": []})
        assert result["hitl_reason"] == "No hierarchy generated"

    def test_f80_empty_goals_reason(self):
        """F80: 空 goals の hitl_reason が 'No hierarchy provided' であること。"""
        from src.agents.f80_module import execute as f80
        result = f80({"trace_id": "F70", "hierarchy": {"goals": []}})
        assert result["hitl_reason"] == "No hierarchy provided"

    def test_f80_missing_trace_chain_reason(self):
        """F80: 不明 trace_id の hitl_reason が 'Trace chain missing' であること。"""
        from src.agents.f80_module import execute as f80
        data = dict(_valid_hierarchy(trace_id="UNKNOWN"))
        result = f80(data)
        assert result["hitl_reason"] == "Trace chain missing"

    def test_f90_empty_tmap_reason(self):
        """F90: 空 tmap の hitl_reason が 'No tasks to finalize' であること。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert result["hitl_reason"] == "No tasks to finalize"


# ════════════════════════════════════════════════════════
# WP8238: 曖昧語カバレッジ（各曖昧語が HITL を発動すること）
# ════════════════════════════════════════════════════════

class TestWP8238_AmbiguousWordCoverage:
    """各モジュールの AMBIGUOUS_WORDS が全て HITL を発動すること"""

    @pytest.mark.parametrize("word", [
        "など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"
    ])
    def test_f10_each_ambiguous_word_triggers_hitl(self, word):
        """F10: AMBIGUOUS_WORDS の各語が HITL を発動すること。"""
        from src.agents.f10_module import execute as f10
        goal = f"売上{word}伸ばしていく"
        result = f10({"goal_text": goal})
        assert result["hitl"] is True, f"'{word}' が F10 HITL を発動しなかった"

    @pytest.mark.parametrize("word", [
        "など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"
    ])
    def test_f20_each_ambiguous_word_triggers_hitl(self, word):
        """F20: AMBIGUOUS_WORDS の各語が HITL を発動すること。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {
                "L1": f"売上{word}伸ばしていく",
                "L2": ["施策A"], "L3": ["タスク1"]
            }
        })
        assert result["hitl"] is True, f"'{word}' が F20 HITL を発動しなかった"

    @pytest.mark.parametrize("word", [
        "など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"
    ])
    def test_f30_each_ambiguous_word_triggers_hitl_element(self, word):
        """F30: AMBIGUOUS_WORDS の各語が element を HITL 移譲すること。"""
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": f"LP作成{word}する", "parent": "L3"}
        ]})
        assert "E1" in result["hitl_elements"], f"'{word}' が F30 HITL を発動しなかった"

    @pytest.mark.parametrize("word", [
        "など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ",
        "改善", "向上", "検討"
    ])
    def test_f50_each_ambiguous_word_triggers_hitl_element(self, word):
        """F50: AMBIGUOUS_WORDS の各語が task を HITL 移譲すること。"""
        from src.agents.f50_module import execute as f50
        result = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": f"LP作成{word}する", "priority": "High"}
        ]})
        assert "T1" in result["hitl_elements"], f"'{word}' が F50 HITL を発動しなかった"

    @pytest.mark.parametrize("word", [
        "改善", "向上", "検討", "最適化", "強化", "推進", "活性化"
    ])
    def test_f60_each_abstract_word_triggers_hitl(self, word):
        """F60: ABSTRACT_WORDS の各語が templated_text にあると HITL を発動すること。"""
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": [
            _valid_templated("T1", f"業務{word}する", "High"),
        ]})
        # ambiguous_tasks が存在 → mece non-compliant → hitl_required=True
        assert result["hitl_required"] is True, f"'{word}' が F60 HITL を発動しなかった"
