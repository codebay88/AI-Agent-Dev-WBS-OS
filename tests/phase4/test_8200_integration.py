"""Phase 4 — WP8200 連携テスト
区分：I/O連携 / 例外処理連鎖 / HITL フロー

WP8200 の観点：
  - モジュール間の I/O が正しく連鎖すること
  - 例外が発生したモジュールで連鎖が止まること
  - HITL フラグが正しく発動・伝播されること
"""

import pytest


# ════════════════════════════════════════════════════════
# WP8210: I/O 連携（各隣接モジュール間の受け渡し）
# ════════════════════════════════════════════════════════

class TestWP8210_IOChain:
    """隣接モジュール間で必要なキーが正しく渡されること。"""

    @pytest.fixture(autouse=True)
    def mock_api(self, mocker):
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規顧客獲得","既存顧客維持"],"L3":["LP作成","広告配信"]}',
        )

    def _chain(self, up_to):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        from src.agents.f90_module import execute as f90

        r = f10({"goal_text": "売上を前年比120%に成長させる"})
        funcs = [("F20", f20), ("F30", f30), ("F40", f40), ("F50", f50),
                 ("F60", f60), ("F70", f70), ("F80", f80), ("F90", f90)]
        for name, fn in funcs:
            r = fn(r)
            if name == up_to:
                return r
        return r

    def test_f10_output_has_trace_id(self):
        from src.agents.f10_module import execute as f10
        out = f10({"goal_text": "売上を前年比120%に成長させる"})
        assert out["trace_id"] == "F10"

    def test_f10_output_has_goal_key(self):
        from src.agents.f10_module import execute as f10
        out = f10({"goal_text": "売上を前年比120%に成長させる"})
        assert "goal" in out

    def test_f10_output_has_tree_key(self):
        from src.agents.f10_module import execute as f10
        out = f10({"goal_text": "売上を前年比120%に成長させる"})
        assert "tree" in out

    def test_f20_accepts_f10_output(self):
        assert self._chain("F20")["trace_id"] == "F20"

    def test_f20_output_has_expanded_goals(self):
        out = self._chain("F20")
        assert "expanded_goals" in out

    def test_f30_accepts_f20_output(self):
        assert self._chain("F30")["trace_id"] == "F30"

    def test_f40_accepts_f30_output(self):
        assert self._chain("F40")["trace_id"] == "F40"

    def test_f50_accepts_f40_output(self):
        assert self._chain("F50")["trace_id"] == "F50"

    def test_f50_output_has_templated_tasks(self):
        out = self._chain("F50")
        assert "templated_tasks" in out

    def test_f60_accepts_f50_output(self):
        assert self._chain("F60")["trace_id"] == "F60"

    def test_f60_output_has_templated_tasks_passthrough(self):
        """F60 出力が templated_tasks パススルーを含むこと（F70 のため）。"""
        out = self._chain("F60")
        assert "templated_tasks" in out

    def test_f70_accepts_f60_output(self):
        assert self._chain("F70")["trace_id"] == "F70"

    def test_f70_output_has_hierarchy(self):
        out = self._chain("F70")
        assert "hierarchy" in out

    def test_f80_accepts_f70_output(self):
        assert self._chain("F80")["trace_id"] == "F80"

    def test_f80_output_has_traceability_map(self):
        out = self._chain("F80")
        assert "traceability_map" in out

    def test_f80_output_has_hierarchy_passthrough(self):
        """F80 出力が hierarchy パススルーを含むこと（F90 のため）。"""
        out = self._chain("F80")
        assert "hierarchy" in out

    def test_f90_accepts_f80_output(self):
        assert self._chain("F90")["trace_id"] == "F90"

    def test_source_trace_id_chain_f10_f20(self):
        """F20 の source_trace_id が F10 の trace_id と一致すること。"""
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        r10 = f10({"goal_text": "売上を前年比120%に成長させる"})
        r20 = f20(r10)
        assert r20["source_trace_id"] == r10["trace_id"]

    def test_source_trace_id_chain_f80_f90(self):
        """F90 の source_trace_id が 'F80' であること。"""
        out = self._chain("F90")
        assert out["source_trace_id"] == "F80"

    def test_full_pipeline_final_output_not_empty(self):
        out = self._chain("F90")
        assert out["final_output"]["summary"]["total_tasks"] > 0


# ════════════════════════════════════════════════════════
# WP8220: 例外処理連鎖
# ════════════════════════════════════════════════════════

class TestWP8220_ExceptionPropagation:
    """例外発生時にパイプラインが適切に停止すること。"""

    @pytest.mark.parametrize("mod_name", [
        "f20_module", "f30_module", "f40_module", "f50_module",
        "f60_module", "f70_module", "f80_module", "f90_module",
    ])
    def test_type_error_on_none(self, mod_name):
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises(TypeError):
            mod.execute(None)

    @pytest.mark.parametrize("mod_name", [
        "f20_module", "f30_module", "f40_module", "f50_module",
        "f60_module", "f70_module", "f80_module",
    ])
    def test_error_on_empty_dict(self, mod_name):
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises((TypeError, ValueError)):
            mod.execute({})

    def test_f90_value_error_no_traceability_map(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError, match="traceability_map"):
            f90({"hierarchy": {"goals": []}, "trace_id": "F80"})

    def test_f90_type_error_no_hierarchy(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError, match="hierarchy"):
            f90({"traceability_map": [], "trace_id": "F80"})

    def test_runtime_error_has_cause_from_f90(self, mocker):
        """RuntimeError の __cause__ が保持されること（F90 ゼロ除算）。"""
        mocker.patch(
            "src.agents.f90_module._compute_evaluation",
            side_effect=RuntimeError("集計失敗テスト")
        )
        data = {
            "trace_id": "F80",
            "traceability_map": [
                {"goal_id": "G1", "element_id": "G1_EL_H", "task_id": "T1",
                 "trace_chain": ["F10","F20","F30","F40","F50","F60","F70"],
                 "origin_module": "F10", "latest_module": "F70", "is_complete": True}
            ],
            "hierarchy": {"goals": [{"goal_id": "G1", "goal_text": "テスト", "elements": [
                {"element_id": "G1_EL_H", "element_text": "要素", "tasks": [
                    {"task_id": "T1", "templated_text": "テスト", "priority": "High",
                     "effort": 3, "value": 5}
                ]}
            ]}]},
        }
        from src.agents.f90_module import execute as f90
        with pytest.raises(RuntimeError):
            f90(data)

    def test_runtime_error_cause_is_zero_division(self):
        """F90 _compute_evaluation の RuntimeError.__cause__ が ZeroDivisionError であること。"""
        from src.agents.f90_module import _compute_evaluation
        hw = [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "x", "priority": "High",
             "effort": None, "value": None}
        ]}]}]
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation(hw)
        assert isinstance(exc_info.value.__cause__, ZeroDivisionError)

    def test_f50_runtime_error_has_cause(self, mocker):
        """F50 で KeyError が RuntimeError にラップされること。"""
        mocker.patch.dict("src.agents.f50_module._TEMPLATES", {}, clear=True)
        from src.agents.f50_module import execute as f50
        tasks = [{"task_id": "T1", "task_text": "LP作成", "priority": "High",
                  "effort": 2, "value": 4, "element_id": "E1"}]
        with pytest.raises(RuntimeError) as exc_info:
            f50({"trace_id": "F40", "tasks": tasks})
        assert exc_info.value.__cause__ is not None


# ════════════════════════════════════════════════════════
# WP8230: HITL フロー
# ════════════════════════════════════════════════════════

class TestWP8230_HITLFlow:
    """HITL フラグが正しく発動し、最終出力まで伝播すること。"""

    @pytest.fixture(autouse=True)
    def mock_api(self, mocker):
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規顧客獲得"],"L3":["LP作成","広告配信"]}',
        )

    def test_ambiguous_word_in_f50_triggers_hitl(self):
        """F50 で曖昧語が含まれる場合に hitl=True になること。"""
        from src.agents.f50_module import execute as f50, AMBIGUOUS_WORDS
        word = AMBIGUOUS_WORDS[0]
        tasks = [{"task_id": "T1", "task_text": f"{word}を実施する",
                  "priority": "High", "effort": 2, "value": 4, "element_id": "E1"}]
        result = f50({"trace_id": "F40", "tasks": tasks})
        assert result["hitl"] is True
        assert len(result["hitl_elements"]) > 0

    def test_hitl_false_when_no_ambiguous_words(self):
        from src.agents.f50_module import execute as f50
        tasks = [{"task_id": "T1", "task_text": "LP作成する",
                  "priority": "High", "effort": 2, "value": 4, "element_id": "E1"}]
        result = f50({"trace_id": "F40", "tasks": tasks})
        assert result["hitl"] is False

    def test_empty_tmap_triggers_f90_hitl(self):
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [],
            "hierarchy": {"goals": []},
        })
        assert result["hitl_required"] is True
        assert result.get("hitl_reason") == "No tasks to finalize"

    def test_incomplete_chain_triggers_f90_hitl(self):
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

    def test_hitl_elements_is_list(self, mocker):
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規顧客獲得"],"L3":["LP作成","広告配信"]}',
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
        r = f90(f80(f70(f60(f50(f40(f30(f20(f10(
            {"goal_text": "売上を前年比120%に成長させる"}
        )))))))))
        assert isinstance(r["hitl_elements"], list)

    def test_hitl_required_is_bool(self, mocker):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        from src.agents.f90_module import execute as f90
        r = f90(f80(f70(f60(f50(f40(f30(f20(f10(
            {"goal_text": "売上を前年比120%に成長させる"}
        )))))))))
        assert isinstance(r["hitl_required"], bool)

    def test_uncertain_similarity_triggers_f60_hitl(self):
        """F60 でコサイン類似度 0.80〜0.85 のペアが uncertain → hitl=True になること。"""
        from src.agents.f60_module import execute as f60, UNCERTAIN_LOW, UNCERTAIN_HIGH
        # 類似度が uncertain 範囲（0.80〜0.85）になるよう設計
        # 3/4 トークン一致 → cos ≈ 0.866 だと duplicate → uncertain 範囲を
        # モックで直接制御する
        from unittest.mock import patch
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.82):
            tasks = [
                {"task_id": "T1", "templated_text": "LP作成 広告配信", "priority": "High"},
                {"task_id": "T2", "templated_text": "LP作成 販促施策", "priority": "High"},
            ]
            result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["hitl"] is True
        assert len(result["hitl_elements"]) > 0

    def test_f80_empty_goals_triggers_hitl(self):
        """F80 に空の goals を渡した場合に hitl_required=True になること。"""
        from src.agents.f80_module import execute as f80
        result = f80({
            "trace_id": "F70",
            "hierarchy": {"goals": []},
        })
        assert result["hitl_required"] is True
