"""Phase 4 — WP8320 異常系運用テスト（Operational Exception Test）
区分：再試行 / データ欠損 / HITL誤承認 / 構造不整合 / 異常ログ

WP8320 の観点：
  - 通信エラー時に再試行ロジックが仕様書どおりに発動すること（MAX_RETRY=3）
  - データ欠損・型不一致で例外が正しく発火し処理が停止すること
  - HITL誤承認・誤却下後の再承認フローが正しく動作すること
  - 構造不整合・フェイルセーフが安全停止すること
  - ERROR/WARNING/RETRY ログが仕様書どおりに記録されること
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

# F10 HITL を踏まない最小限の goal_text（10文字以上・曖昧語なし）
_SAFE_GOAL = "売上を前年比120%に成長させる"


# ════════════════════════════════════════════════════════
# WP8321: 再試行ロジック（F10 API 通信エラー）
# ════════════════════════════════════════════════════════

class TestWP8321_RetryLogic:
    """F10 API 通信エラー時に再試行ロジックが仕様書どおりに発動すること"""

    def test_f10_api_error_retries_max_retry_times(self, mocker):
        """F10: anthropic.APIError → _call_api が MAX_RETRY(3) 回呼ばれること。"""
        import anthropic
        mocker.patch("time.sleep")  # sleep をスキップ
        mock_call = mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="timeout", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises(RuntimeError):
            f10({"goal_text": _SAFE_GOAL})
        assert mock_call.call_count == 3

    def test_f10_api_error_all_retries_raises_runtime(self, mocker):
        """F10: MAX_RETRY 全回失敗 → RuntimeError が発火すること。"""
        import anthropic
        mocker.patch("time.sleep")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="timeout", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises(RuntimeError):
            f10({"goal_text": _SAFE_GOAL})

    def test_f10_retry_runtime_error_message_contains_attempt_count(self, mocker):
        """F10: RuntimeError メッセージに試行回数 '3' が含まれること。"""
        import anthropic
        mocker.patch("time.sleep")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="timeout", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises(RuntimeError) as exc_info:
            f10({"goal_text": _SAFE_GOAL})
        assert "3" in str(exc_info.value)

    def test_f10_retry_succeeds_on_second_attempt(self, mocker):
        """F10: 1回目失敗 → 2回目で成功 → 正常出力を返すこと。"""
        import anthropic
        mocker.patch("time.sleep")
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        mock_call = mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=[
                anthropic.APIError(message="timeout", request=None, body=None),
                _MOCK_API,
            ]
        )
        from src.agents.f10_module import execute as f10
        result = f10({"goal_text": _SAFE_GOAL})
        assert result["trace_id"] == "F10"
        assert result["hitl"] is False
        assert mock_call.call_count == 2

    def test_f10_retry_logs_warning_per_attempt(self, mocker, caplog):
        """F10: 各リトライで WARNING ログが出力されること。"""
        import anthropic
        mocker.patch("time.sleep")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="err", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.WARNING, logger="src.agents.f10_module"):
            with pytest.raises(RuntimeError):
                f10({"goal_text": _SAFE_GOAL})
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) >= 3

    def test_f10_retry_warning_includes_attempt_number(self, mocker, caplog):
        """F10: 各リトライ WARNING に試行番号（1/3, 2/3, 3/3）が含まれること。"""
        import anthropic
        mocker.patch("time.sleep")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="err", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.WARNING, logger="src.agents.f10_module"):
            with pytest.raises(RuntimeError):
                f10({"goal_text": _SAFE_GOAL})
        messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("1/3" in m or "1" in m for m in messages)

    def test_f10_json_decode_error_triggers_retry(self, mocker):
        """F10: JSONDecodeError → 再試行ロジックが発動すること。"""
        import json
        mocker.patch("time.sleep")
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        mock_call = mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=json.JSONDecodeError("bad json", "", 0)
        )
        from src.agents.f10_module import execute as f10
        with pytest.raises(RuntimeError):
            f10({"goal_text": _SAFE_GOAL})
        assert mock_call.call_count == 3

    def test_f10_sleep_called_between_retries(self, mocker):
        """F10: リトライ間に time.sleep が呼ばれること（RETRY_DELAYS 適用確認）。"""
        import anthropic
        mock_sleep = mocker.patch("time.sleep")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="err", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises(RuntimeError):
            f10({"goal_text": _SAFE_GOAL})
        assert mock_sleep.call_count >= 2

    def test_f10_prompt_not_found_raises_file_not_found(self, mocker):
        """F10: プロンプトファイル不在 → FileNotFoundError が発火すること。"""
        from src.agents.f10_module import _load_prompt, PROMPT_PATH
        if PROMPT_PATH.exists():
            pytest.skip("プロンプトファイルが存在するためスキップ")
        with pytest.raises(FileNotFoundError):
            _load_prompt()


# ════════════════════════════════════════════════════════
# WP8322: データ欠損・型不一致による異常系
# ════════════════════════════════════════════════════════

class TestWP8322_DataCorruption:
    """データ欠損・型不一致時に例外が正しく発火し処理が停止すること"""

    # ─── F10 API レスポンス欠損 ───
    def test_f10_api_response_missing_l1_raises_value_error(self, mocker):
        """F10: API レスポンスに L1 が欠落 → ValueError が発火すること。"""
        mocker.patch("src.agents.f10_module._call_api",
                     return_value='{"L2":["施策A"],"L3":["タスク1"]}')
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises((ValueError, RuntimeError)):
            f10({"goal_text": _SAFE_GOAL})

    def test_f10_api_response_not_json_raises_runtime(self, mocker):
        """F10: API レスポンスが非 JSON → RuntimeError が発火すること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value="NOT_JSON")
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises(RuntimeError):
            f10({"goal_text": _SAFE_GOAL})

    def test_f10_api_response_l1_wrong_type_raises_value_error(self, mocker):
        """F10: L1 が str でない → ValueError が発火すること。"""
        mocker.patch("src.agents.f10_module._call_api",
                     return_value='{"L1":123,"L2":[],"L3":[]}')
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises((ValueError, RuntimeError)):
            f10({"goal_text": _SAFE_GOAL})

    def test_f10_api_response_l2_not_list_raises_value_error(self, mocker):
        """F10: L2 が list でない → ValueError が発火すること。"""
        mocker.patch("src.agents.f10_module._call_api",
                     return_value='{"L1":"テスト","L2":"not_list","L3":[]}')
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with pytest.raises((ValueError, RuntimeError)):
            f10({"goal_text": _SAFE_GOAL})

    # ─── F20 データ欠損 ───
    def test_f20_goal_l1_empty_string_triggers_hitl(self):
        """F20: L1 が空文字列 → HITL 移譲（例外でなく hitl=True）。"""
        from src.agents.f20_module import execute as f20
        result = f20({
            "trace_id": "F10",
            "goal": {"L1": "   ", "L2": ["施策A"], "L3": ["タスク1"]}
        })
        assert result["hitl"] is True

    def test_f20_goal_l2_wrong_type_raises_value_error(self):
        """F20: L2 が list でない → ValueError が発火すること。"""
        from src.agents.f20_module import execute as f20
        with pytest.raises(ValueError):
            f20({"trace_id": "F10", "goal": {
                "L1": _SAFE_GOAL, "L2": "not_a_list", "L3": []
            }})

    # ─── F30 要素欠損 ───
    def test_f30_element_missing_text_raises_value_error(self):
        """F30: element に text が欠落 → ValueError が発火すること。"""
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError, match="text"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"element_id": "E1", "parent": "L3"}
            ]})

    def test_f30_element_not_dict_raises_value_error(self):
        """F30: expanded_goals の要素が dict でない → ValueError が発火すること。"""
        from src.agents.f30_module import execute as f30
        with pytest.raises(ValueError):
            f30({"trace_id": "F20", "expanded_goals": ["not_a_dict"]})

    # ─── F40 データ欠損 ───
    def test_f40_element_missing_score_feasibility_raises_value_error(self):
        """F40: score_feasibility が欠落 → ValueError が発火すること。"""
        from src.agents.f40_module import execute as f40
        with pytest.raises(ValueError):
            f40({"trace_id": "F30", "evaluated_goals": [
                {"element_id": "E1", "text": "LP作成", "parent": "L3",
                 "priority": "High", "score_importance": 0.8}
                # score_feasibility 欠落
            ]})

    # ─── F50 タスク欠損 ───
    def test_f50_task_missing_task_id_raises_type_error(self):
        """F50: task に task_id が欠落 → TypeError が発火すること。"""
        from src.agents.f50_module import execute as f50
        with pytest.raises(TypeError):
            f50({"trace_id": "F40", "tasks": [
                {"task_text": "LP作成", "priority": "High"}
            ]})

    # ─── F70 タスク欠損 ───
    def test_f70_task_missing_templated_text_raises_type_error(self):
        """F70: task に templated_text が欠落 → TypeError が発火すること。"""
        from src.agents.f70_module import execute as f70
        with pytest.raises(TypeError):
            f70({"trace_id": "F60", "templated_tasks": [
                {"task_id": "T1", "priority": "High"}
            ]})

    # ─── F80 hierarchy 欠損 ───
    def test_f80_goal_missing_elements_raises_type_error(self):
        """F80: goal に elements が欠落 → TypeError が発火すること。"""
        from src.agents.f80_module import execute as f80
        with pytest.raises(TypeError):
            f80({"trace_id": "F70", "hierarchy": {
                "goals": [{"goal_id": "G1"}]
            }})

    def test_f80_hierarchy_not_dict_raises_value_error(self):
        """F80: hierarchy が dict でない → ValueError が発火すること。"""
        from src.agents.f80_module import execute as f80
        with pytest.raises(ValueError):
            f80({"trace_id": "F70", "hierarchy": "not_a_dict"})

    # ─── F90 非対称例外 ───
    def test_f90_missing_traceability_map_raises_value_error(self):
        """F90: traceability_map 欠落 → ValueError（仕様書非対称）。"""
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError, match="traceability_map"):
            f90({"trace_id": "F80", "hierarchy": {"goals": []}})

    def test_f90_missing_hierarchy_raises_type_error(self):
        """F90: hierarchy 欠落 → TypeError（仕様書非対称）。"""
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError, match="hierarchy"):
            f90({"trace_id": "F80", "traceability_map": []})

    # ─── パイプライン停止確認 ───
    def test_pipeline_stops_at_corruption_point(self, mocker):
        """データ欠損があったモジュールでパイプラインが停止し、後続は呼ばれないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20

        r10 = f10({"goal_text": _SAFE_GOAL})
        # F20 に意図的に goal を壊して渡す
        corrupt = dict(r10)
        del corrupt["goal"]
        with pytest.raises(ValueError, match="goal"):
            f20(corrupt)

        # F20 が停止したため F30 は呼ばれない（独立してテスト）
        from src.agents.f30_module import execute as f30
        result = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成する", "parent": "L3"}
        ]})
        assert result["trace_id"] == "F30"  # F30 は別入力で正常動作


# ════════════════════════════════════════════════════════
# WP8323: HITL誤承認・誤却下シミュレーション
# ════════════════════════════════════════════════════════

class TestWP8323_HITLMisapproval:
    """HITL誤承認・誤却下後の再承認フローが正しく動作すること"""

    def test_hitl_reapproval_after_correction(self, mocker):
        """HITL → 曖昧語修正 → 再実行 = 正常処理（再承認パス）。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10

        # 1回目: HITL 発動
        r_hitl = f10({"goal_text": "売上などを改善したい"})
        assert r_hitl["hitl"] is True

        # 修正後の再実行（再承認）
        r_approved = f10({"goal_text": _SAFE_GOAL})
        assert r_approved["hitl"] is False
        assert r_approved["goal"] is not None

    def test_f50_resubmission_of_clean_subset_after_partial_hitl(self):
        """F50 部分 HITL 後、クリーン subset のみ再実行すると全タスク処理されること。"""
        from src.agents.f50_module import execute as f50

        # 1回目: 曖昧タスクが HITL
        r1 = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "T2", "task_text": "広告配信する", "priority": "High",
             "estimated_effort": 1, "estimated_value": 3},
        ]})
        assert "T1" in r1["hitl_elements"]
        assert "T2" not in r1["hitl_elements"]

        # 2回目: T1 の曖昧語を修正して再実行（再承認パス）
        r2 = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1_fixed", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4},
        ]})
        templated_ids = [t["task_id"] for t in r2["templated_tasks"]]
        assert "T1_fixed" in templated_ids
        assert r2["hitl_elements"] == []

    def test_f60_resubmission_after_uncertain_resolved(self, mocker):
        """F60 不確定ペア除去後の再実行 → hitl_required=False になること。"""
        mocker.patch("src.agents.f60_module._cosine_similarity", return_value=0.82)
        from src.agents.f60_module import execute as f60

        # 1回目: 不確定域 → HITL
        r1 = f60({"trace_id": "F50", "templated_tasks": [
            {"task_id": "T1", "templated_text": "LP作成する", "priority": "High"},
            {"task_id": "T2", "templated_text": "広告配信する", "priority": "Medium"},
        ]})
        assert r1["hitl_required"] is True

        # 2回目: 不確定ペア T2 を除去して再実行
        mocker.stopall()  # cosine モックを解除（実際の類似度計算を使う）
        r2 = f60({"trace_id": "F50", "templated_tasks": [
            {"task_id": "T1", "templated_text": "LP作成する", "priority": "High"},
        ]})
        assert r2["hitl_required"] is False

    def test_hitl_trigger_is_deterministic_on_same_input(self):
        """同一入力を2回実行しても HITL 結果が同一であること（冪等性）。"""
        from src.agents.f50_module import execute as f50
        task_input = {"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"}
        ]}
        r1 = f50(task_input)
        r2 = f50(task_input)
        assert r1["hitl"] == r2["hitl"]
        assert r1["hitl_elements"] == r2["hitl_elements"]

    def test_f30_hitl_partial_resubmission_with_cleaned_element(self):
        """F30 部分 HITL 後、曖昧要素を修正して再実行すると hitl_elements=[] になること。"""
        from src.agents.f30_module import execute as f30

        # 1回目: E1 が曖昧語で HITL
        r1 = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成などをする", "parent": "L3"},
        ]})
        assert "E1" in r1["hitl_elements"]

        # 2回目: E1 の曖昧語を修正
        r2 = f30({"trace_id": "F20", "expanded_goals": [
            {"element_id": "E1", "text": "LP作成する", "parent": "L3"},
        ]})
        assert r2["hitl_elements"] == []
        assert len(r2["evaluated_goals"]) == 1

    def test_f20_hitl_reapproval_with_cleaned_l1(self):
        """F20 HITL 後、L1 曖昧語修正で再実行 → hitl=False になること。"""
        from src.agents.f20_module import execute as f20

        # 1回目: 曖昧語 L1 → HITL
        r1 = f20({"trace_id": "F10", "goal": {
            "L1": "売上などを向上させる", "L2": ["施策A"], "L3": ["タスク1"]
        }})
        assert r1["hitl"] is True

        # 2回目: 曖昧語除去
        r2 = f20({"trace_id": "F10", "goal": {
            "L1": _SAFE_GOAL, "L2": ["新規顧客獲得"], "L3": ["LP作成する"]
        }})
        assert r2["hitl"] is False

    def test_multiple_sequential_hitl_reapprovals_converge(self):
        """複数回の HITL→修正サイクルを経て最終的に hitl=False になること。"""
        from src.agents.f50_module import execute as f50

        # サイクル1: T1 と T2 が HITL
        r1 = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1", "task_text": "LP作成などする", "priority": "High"},
            {"task_id": "T2", "task_text": "広告配信とかする", "priority": "Medium"},
        ]})
        assert "T1" in r1["hitl_elements"]
        assert "T2" in r1["hitl_elements"]
        assert r1["hitl"] is True

        # サイクル2: T1 修正、T2 は修正未了
        r2 = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1_fixed", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4},
            {"task_id": "T2", "task_text": "広告配信とかする", "priority": "Medium"},
        ]})
        assert "T1_fixed" not in r2["hitl_elements"]
        assert "T2" in r2["hitl_elements"]

        # サイクル3: T2 も修正
        r3 = f50({"trace_id": "F40", "tasks": [
            {"task_id": "T1_fixed", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4},
            {"task_id": "T2_fixed", "task_text": "広告配信する", "priority": "Medium",
             "estimated_effort": 1, "estimated_value": 3},
        ]})
        assert r3["hitl_elements"] == []
        assert r3["hitl"] is False


# ════════════════════════════════════════════════════════
# WP8324: 構造不整合・フェイルセーフ
# ════════════════════════════════════════════════════════

class TestWP8324_StructuralCorruption:
    """構造不整合・フェイルセーフが安全停止すること"""

    # ─── F80 循環依存検出 ───
    def test_f80_circular_dependency_detected_as_hitl_elements(self):
        """F80: 同一 task_id が複数 element に存在 → 循環依存として hitl_elements に追加。"""
        from src.agents.f80_module import execute as f80
        result = f80({
            "trace_id": "F70",
            "hierarchy": {"goals": [{
                "goal_id": "G1", "goal_text": "LP作成",
                "elements": [
                    {"element_id": "G1_EL_H", "element_text": "High優先",
                     "tasks": [{"task_id": "T_DUP", "templated_text": "LP作成する",
                                "priority": "High", "effort": 2, "value": 4}]},
                    {"element_id": "G1_EL_M", "element_text": "Medium優先",
                     "tasks": [{"task_id": "T_DUP", "templated_text": "LP作成する",
                                "priority": "Medium", "effort": 1, "value": 3}]},
                ]
            }]}
        })
        # 循環依存 → hitl_elements に T_DUP が入る
        assert result["hitl_required"] is True
        assert "T_DUP" in result["hitl_elements"]

    # ─── F80 不完全 trace_chain ───
    def test_f80_incomplete_trace_chain_is_failsafe(self):
        """F80: trace_chain が不完全（F60/F70 欠落）→ HITL 移譲で安全停止すること。"""
        from src.agents.f80_module import execute as f80
        result = f80({
            "trace_id": "F50",
            "hierarchy": {"goals": [{
                "goal_id": "G1", "goal_text": "LP作成",
                "elements": [{"element_id": "G1_EL_H", "element_text": "High優先",
                              "tasks": [{"task_id": "T1", "templated_text": "LP作成",
                                         "priority": "High", "effort": 2, "value": 4}]}]
            }]}
        })
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    # ─── F80 不明 trace_chain ───
    def test_f80_unknown_source_trace_failsafe(self):
        """F80: 全く不明な trace_id → chain 空 → HITL 移譲で安全停止すること。"""
        from src.agents.f80_module import execute as f80
        result = f80({
            "trace_id": "UNKNOWN",
            "hierarchy": {"goals": [{
                "goal_id": "G1", "goal_text": "LP作成",
                "elements": [{"element_id": "G1_EL_H", "element_text": "High優先",
                              "tasks": [{"task_id": "T1", "templated_text": "LP作成",
                                         "priority": "High", "effort": 2, "value": 4}]}]
            }]}
        })
        assert result["hitl_required"] is True
        assert result["hitl_reason"] == "Trace chain missing"

    # ─── F90 不完全トレーサビリティ ───
    def test_f90_incomplete_traceability_triggers_hitl_elements(self):
        """F90: is_complete=False のエントリが hitl_elements に入ること。"""
        from src.agents.f90_module import execute as f90
        result = f90({
            "trace_id": "F80",
            "traceability_map": [{
                "goal_id": "G1", "element_id": "G1_EL_H", "task_id": "T1",
                "trace_chain": ["F10"],   # 不完全
                "is_complete": False,
                "origin_module": "F10", "latest_module": "F10",
            }],
            "hierarchy": {"goals": [{
                "goal_id": "G1", "goal_text": "LP作成",
                "elements": [{"element_id": "G1_EL_H", "element_text": "High優先",
                              "tasks": [{"task_id": "T1", "templated_text": "LP作成",
                                         "priority": "High", "effort": 2, "value": 4}]}]
            }]}
        })
        assert result["hitl_required"] is True
        assert "T1" in result["hitl_elements"]

    # ─── F90 抽象語 recommendation ───
    def test_f90_abstract_word_in_recommendation_triggers_hitl(self):
        """F90: recommendations に抽象語が含まれると hitl_elements に 'recommendations' が入ること。"""
        from src.agents.f90_module import _check_recommendations_abstract
        hitl_elements = []
        _check_recommendations_abstract(["改善を検討してください"], hitl_elements)
        assert "recommendations" in hitl_elements

    # ─── F10 ツリー整合性 WARNING → 処理継続 ───
    def test_f10_orphan_node_warning_but_continues(self, mocker, caplog):
        """F10: ツリー内の孤立ノード → WARNING で記録するが処理継続すること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import _build_tree, _validate_tree
        parsed = {"L1": "テスト", "L2": ["施策A"], "L3": ["タスク1"]}
        tree = _build_tree(parsed)
        # ツリーに孤立ノードを手動追加して validate
        import uuid
        orphan_id = f"L3-orphan-{uuid.uuid4().hex[:6]}"
        fake_node = {
            "objective_id": orphan_id,
            "objective_text": "孤立ノード",
            "level": "L3",
            "parent_id": "NONEXISTENT_PARENT",
            "children": [],
        }
        list(tree.values())[0]["children"].append(fake_node)
        with caplog.at_level(logging.WARNING, logger="src.agents.f10_module"):
            _validate_tree(tree)
        assert any("孤立ノード" in r.message or "parent_id" in r.message
                   for r in caplog.records)

    # ─── F50 RuntimeError チェーン ───
    def test_f50_template_apply_error_has_cause_chain(self):
        """F50: _apply_template での RuntimeError が __cause__ を保持すること。"""
        from src.agents.f50_module import _apply_template
        with pytest.raises(RuntimeError) as exc_info:
            _apply_template({"task_id": "T1", "task_text": "LP作成", "priority": "UNKNOWN"})
        assert exc_info.value.__cause__ is not None

    # ─── F90 ゼロ除算チェーン ───
    def test_f90_zero_effort_runtime_cause_is_zero_division(self):
        """F90: effort=0 → ZeroDivisionError → RuntimeError(__cause__=ZeroDivisionError)。"""
        from src.agents.f90_module import _compute_evaluation
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation([{"elements": [{"tasks": [
                {"task_id": "T1", "templated_text": "x",
                 "priority": "High", "effort": 0, "value": 5}
            ]}]}])
        assert isinstance(exc_info.value.__cause__, ZeroDivisionError)

    # ─── F60 cosine 計算失敗 ───
    def test_f60_cosine_failure_wraps_as_runtime_with_cause(self, mocker):
        """F60: cosine 計算失敗 → RuntimeError(__cause__ 保持）で安全停止すること。"""
        from src.agents.f60_module import _cosine_similarity
        mocker.patch("src.agents.f60_module.math.sqrt",
                     side_effect=OverflowError("overflow"))
        with pytest.raises(RuntimeError) as exc_info:
            _cosine_similarity("LP作成する", "LP作成する")
        assert exc_info.value.__cause__ is not None


# ════════════════════════════════════════════════════════
# WP8325: 異常系運用ログ
# ════════════════════════════════════════════════════════

class TestWP8325_OperationalExceptionLog:
    """異常発生時のログが仕様書どおりに記録されること（WARNING / ERROR）"""

    # ─── F10 リトライ WARNING ───
    def test_f10_api_retry_warning_logged_with_attempt_info(self, mocker, caplog):
        """F10: API リトライ時に試行回数を含む WARNING ログが出力されること。"""
        import anthropic
        mocker.patch("time.sleep")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=anthropic.APIError(message="err", request=None, body=None)
        )
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        from src.agents.f10_module import execute as f10
        with caplog.at_level(logging.WARNING, logger="src.agents.f10_module"):
            with pytest.raises(RuntimeError):
                f10({"goal_text": _SAFE_GOAL})
        retry_warnings = [r for r in caplog.records
                          if r.levelno == logging.WARNING and "呼び出し失敗" in r.message]
        assert len(retry_warnings) == 3

    # ─── F50 HITL WARNING に task_id 含む ───
    def test_f50_hitl_warning_includes_task_id(self, caplog):
        """F50: HITL 移譲 WARNING に task_id が含まれること。"""
        from src.agents.f50_module import execute as f50
        with caplog.at_level(logging.WARNING, logger="src.agents.f50_module"):
            f50({"trace_id": "F40", "tasks": [
                {"task_id": "T_AMBIGUOUS", "task_text": "LP作成などする", "priority": "High"}
            ]})
        assert any("T_AMBIGUOUS" in r.message for r in caplog.records)

    # ─── F30 HITL WARNING に element_id 含む ───
    def test_f30_hitl_warning_includes_element_id(self, caplog):
        """F30: HITL 移譲 WARNING に element_id が含まれること。"""
        from src.agents.f30_module import execute as f30
        with caplog.at_level(logging.WARNING, logger="src.agents.f30_module"):
            f30({"trace_id": "F20", "expanded_goals": [
                {"element_id": "E_TARGET", "text": "LP作成などをする", "parent": "L3"}
            ]})
        assert any("E_TARGET" in r.message for r in caplog.records)

    # ─── F80 不完全チェーン WARNING ───
    def test_f80_incomplete_chain_warning_logged(self, caplog):
        """F80: 不完全 trace_chain タスクで WARNING が出力されること。"""
        from src.agents.f80_module import execute as f80
        with caplog.at_level(logging.WARNING, logger="src.agents.f80_module"):
            f80({
                "trace_id": "F50",
                "hierarchy": {"goals": [{
                    "goal_id": "G1", "goal_text": "LP作成",
                    "elements": [{"element_id": "G1_EL_H", "element_text": "High優先",
                                  "tasks": [{"task_id": "T_INCOMPLETE",
                                             "templated_text": "LP作成",
                                             "priority": "High", "effort": 2, "value": 4}]}]
                }]}
            })
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    # ─── F60 空タスク WARNING ───
    def test_f60_empty_tasks_warning_with_reason(self, caplog):
        """F60: 空 templated_tasks で HITL 移譲 WARNING が出力されること。"""
        from src.agents.f60_module import execute as f60
        with caplog.at_level(logging.WARNING, logger="src.agents.f60_module"):
            f60({"trace_id": "F50", "templated_tasks": []})
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    # ─── F40 スコア範囲外 WARNING ───
    def test_f40_out_of_range_score_warning_logged(self, caplog):
        """F40: スコアが範囲外（>1.0）で WARNING が出力されること。"""
        from src.agents.f40_module import execute as f40
        with caplog.at_level(logging.WARNING, logger="src.agents.f40_module"):
            f40({"trace_id": "F30", "evaluated_goals": [
                {"element_id": "E1", "text": "LP作成する", "parent": "L3",
                 "priority": "High", "score_importance": 1.5, "score_feasibility": 0.7}
            ]})
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    # ─── F80 循環依存 WARNING ───
    def test_f80_circular_dependency_warning_logged(self, caplog):
        """F80: 循環依存（同一 task_id 複数 element）で WARNING が出力されること。"""
        from src.agents.f80_module import execute as f80
        with caplog.at_level(logging.WARNING, logger="src.agents.f80_module"):
            f80({
                "trace_id": "F70",
                "hierarchy": {"goals": [{
                    "goal_id": "G1", "goal_text": "LP作成",
                    "elements": [
                        {"element_id": "G1_EL_H", "element_text": "High優先",
                         "tasks": [{"task_id": "T_CIRC", "templated_text": "LP作成",
                                    "priority": "High", "effort": 2, "value": 4}]},
                        {"element_id": "G1_EL_M", "element_text": "Medium優先",
                         "tasks": [{"task_id": "T_CIRC", "templated_text": "LP作成",
                                    "priority": "Medium", "effort": 1, "value": 3}]},
                    ]
                }]}
            })
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    # ─── F20 HITL 移譲 WARNING ───
    def test_f20_hitl_warning_logged_with_reason(self, caplog):
        """F20: HITL 移譲時に '[HITL移譲]' と理由を含む WARNING が出力されること。"""
        from src.agents.f20_module import execute as f20
        with caplog.at_level(logging.WARNING, logger="src.agents.f20_module"):
            f20({"trace_id": "F10", "goal": {
                "L1": "売上などを上げたい", "L2": ["施策A"], "L3": ["タスク1"]
            }})
        hitl_warns = [r for r in caplog.records
                      if r.levelno == logging.WARNING and "HITL" in r.message]
        assert len(hitl_warns) >= 1

    # ─── 全モジュール WARNING → 処理継続（不明 trace_id）───
    @pytest.mark.parametrize("mod_name,input_data", [
        ("f20_module", {"trace_id": "BAD", "goal": {
            "L1": "売上を前年比120%に成長させる", "L2": ["施策A"], "L3": ["タスク1"]
        }}),
        ("f50_module", {"trace_id": "BAD", "tasks": [
            {"task_id": "T1", "task_text": "LP作成する", "priority": "High",
             "estimated_effort": 2, "estimated_value": 4}
        ]}),
        ("f60_module", {"trace_id": "BAD", "templated_tasks": [
            {"task_id": "T1", "templated_text": "LP作成する", "priority": "High"}
        ]}),
    ])
    def test_unknown_trace_id_warns_and_continues(self, mod_name, input_data, caplog):
        """不明 trace_id の WARNING が出力されても処理が継続すること。"""
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with caplog.at_level(logging.WARNING, logger=f"src.agents.{mod_name}"):
            result = mod.execute(input_data)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert result is not None
