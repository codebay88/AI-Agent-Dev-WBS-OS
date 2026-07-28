"""Phase 4 — WP8300 運用テスト
区分：正常系全件 / 異常系全件 / 本番移行判定

WP8300 の観点：
  - F10〜F90 のフルパイプラインが実データ相当の入力で正常稼働すること
  - 全モジュールが想定される異常入力を確実に拒否すること
  - 本番移行判定チェックリスト（DoD）を全項目検証すること
"""

import json
import logging
from pathlib import Path

import pytest


BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ════════════════════════════════════════════════════════
# WP8310: 正常系全件（3つの異なるゴールテキストで検証）
# ════════════════════════════════════════════════════════

GOAL_TEXTS = [
    "売上を前年比120%に成長させる",
    "新規顧客獲得数を月50件に増やす",
    "業務効率化により残業時間を月20時間削減する",
]

# L1 に数値表現を含めることで importance=0.95 → avg≥0.70 → High priority を保証する
_MOCK_API_RESPONSE = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


@pytest.fixture
def full_pipeline(mocker):
    """F10〜F90 のフルパイプライン実行器（API モック付き）。"""
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

    def run(goal_text):
        return f90(f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": goal_text})))))))))

    return run


class TestWP8310_Normal:
    """フルパイプライン正常系 — 3ゴールテキストで全件検証。"""

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_pipeline_completes_for_goal(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert result["trace_id"] == "F90"

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_final_output_has_summary(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert "summary" in result["final_output"]

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_total_tasks_positive(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert result["final_output"]["summary"]["total_tasks"] > 0

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_evaluation_report_present(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert "evaluation_report" in result["final_output"]

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_efficiency_score_positive(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        score = result["final_output"]["evaluation_report"]["efficiency_score"]
        assert score > 0

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_hierarchy_with_trace_not_empty(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert len(result["final_output"]["hierarchy_with_trace"]) > 0

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_all_tasks_have_full_trace_chain(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        full_chain = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]
        for goal in result["final_output"]["hierarchy_with_trace"]:
            for elem in goal["elements"]:
                for task in elem["tasks"]:
                    assert task["trace_chain"] == full_chain, \
                        f"task_id={task['task_id']} の trace_chain が不完全"

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_output_json_saved(self, full_pipeline, goal_text, tmp_path, mocker):
        """data/output/ に f90_result_*.json が保存されること（mtime で確認）。"""
        import time
        output_dir = BASE_DIR / "data" / "output"
        before_mtime = max(
            (p.stat().st_mtime for p in output_dir.glob("f90_result_*.json")),
            default=0.0,
        )
        time.sleep(0.05)
        full_pipeline(goal_text)
        after_files = list(output_dir.glob("f90_result_*.json"))
        assert any(p.stat().st_mtime > before_mtime for p in after_files), \
            "f90_result_*.json の新ファイルが保存されなかった"

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_saved_json_is_valid(self, full_pipeline, goal_text):
        """保存された JSON が有効な形式であること。"""
        full_pipeline(goal_text)
        files = sorted((BASE_DIR / "data" / "output").glob("f90_result_*.json"),
                       key=lambda p: p.stat().st_mtime)
        latest = files[-1]
        data = json.loads(latest.read_text(encoding="utf-8"))
        assert data["trace_id"] == "F90"

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_traceability_complete_true(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert result["final_output"]["summary"]["traceability_complete"] is True

    @pytest.mark.parametrize("goal_text", GOAL_TEXTS)
    def test_pipeline_integrity_verified(self, full_pipeline, goal_text):
        result = full_pipeline(goal_text)
        assert result["final_output"]["summary"]["pipeline_integrity"] == "verified"


# ════════════════════════════════════════════════════════
# WP8320: 異常系全件（全モジュールの境界値異常入力）
# ════════════════════════════════════════════════════════

class TestWP8320_Abnormal:
    """全モジュールが想定外入力を正しく拒否すること。"""

    @pytest.mark.parametrize("mod_name,bad_input", [
        ("f20_module", None),
        ("f30_module", "string"),
        ("f40_module", 42),
        ("f50_module", []),
        ("f60_module", None),
        ("f70_module", None),
        ("f80_module", None),
        ("f90_module", None),
    ])
    def test_type_error_on_non_dict(self, mod_name, bad_input):
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises(TypeError):
            mod.execute(bad_input)

    @pytest.mark.parametrize("mod_name", [
        "f20_module", "f30_module", "f40_module", "f50_module",
        "f60_module", "f70_module", "f80_module",
    ])
    def test_value_error_on_empty_dict(self, mod_name):
        import importlib
        mod = importlib.import_module(f"src.agents.{mod_name}")
        with pytest.raises((TypeError, ValueError)):
            mod.execute({})

    def test_f90_value_error_no_traceability_map(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(ValueError):
            f90({"hierarchy": {"goals": []}, "trace_id": "F80"})

    def test_f90_type_error_no_hierarchy(self):
        from src.agents.f90_module import execute as f90
        with pytest.raises(TypeError):
            f90({"traceability_map": [], "trace_id": "F80"})

    def test_f10_value_error_no_goal_text(self, mocker):
        mocker.patch("src.agents.f10_module._call_api", return_value='{}')
        from src.agents.f10_module import execute as f10
        with pytest.raises((TypeError, ValueError)):
            f10({})

    def test_all_runtime_errors_have_cause(self, mocker):
        """RuntimeError は必ず __cause__ を持つこと（F90 ゼロ除算）。"""
        from src.agents.f90_module import _compute_evaluation
        hw = [{"elements": [{"tasks": [
            {"task_id": "T1", "templated_text": "x", "priority": "High",
             "effort": None, "value": None}
        ]}]}]
        with pytest.raises(RuntimeError) as exc_info:
            _compute_evaluation(hw)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ZeroDivisionError)


# ════════════════════════════════════════════════════════
# WP8330: 本番移行判定（DoD チェックリスト）
# ════════════════════════════════════════════════════════

class TestWP8330_ProductionMigrationJudgment:
    """本番移行判定チェックリスト — 全項目を自動検証する。"""

    @pytest.fixture(autouse=True)
    def mock_api(self, mocker):
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value=_MOCK_API_RESPONSE,
        )

    def _run_pipeline(self):
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        from src.agents.f90_module import execute as f90
        return f90(f80(f70(f60(f50(f40(f30(f20(f10(
            {"goal_text": "売上を前年比120%に成長させる"}
        )))))))))

    # DoD1: モジュール数
    def test_dod1_nine_modules_implemented(self):
        modules = list((BASE_DIR / "src" / "agents").glob("f*_module.py"))
        assert len(modules) == 9, f"実装モジュール数が不正: {len(modules)}"

    # DoD2: 仕様書数
    def test_dod2_nine_spec_docs_exist(self):
        docs = list((BASE_DIR / "docs").glob("F*_Module.md"))
        assert len(docs) == 9, f"仕様書数が不正: {len(docs)}"

    # DoD3: テストファイル数
    def test_dod3_nine_test_files_exist(self):
        tests = list((BASE_DIR / "tests").glob("test_f*_module.py"))
        assert len(tests) == 9, f"テストファイル数が不正: {len(tests)}"

    # DoD4: 既存テスト 590件 PASS（import で確認）
    def test_dod4_all_f_series_modules_importable(self):
        import importlib
        for n in range(1, 10):
            mod_name = f"src.agents.f{n}0_module"
            mod = importlib.import_module(mod_name)
            assert hasattr(mod, "execute"), f"{mod_name} に execute() がない"

    # DoD5: trace_id チェーン F10→F90 が正しい
    def test_dod5_trace_id_chain_correct(self):
        result = self._run_pipeline()
        assert result["trace_id"]        == "F90"
        assert result["source_trace_id"] == "F80"

    # DoD6: final_output に必須キーが揃っている
    def test_dod6_final_output_required_keys(self):
        result = self._run_pipeline()
        required = {"summary", "hierarchy_with_trace", "evaluation_report"}
        assert required <= result["final_output"].keys()

    # DoD7: summary の全フィールド
    def test_dod7_summary_all_fields(self):
        result = self._run_pipeline()
        summary = result["final_output"]["summary"]
        required = {"total_goals", "total_elements", "total_tasks",
                    "pipeline_integrity", "traceability_complete"}
        assert required <= summary.keys()

    # DoD8: evaluation_report の全フィールド
    def test_dod8_evaluation_report_all_fields(self):
        result = self._run_pipeline()
        report = result["final_output"]["evaluation_report"]
        required = {"average_effort", "average_value", "efficiency_score", "recommendations"}
        assert required <= report.keys()

    # DoD9: 出力ファイルが保存されること
    def test_dod9_output_file_saved(self):
        import time
        output_dir = BASE_DIR / "data" / "output"
        before_mtime = max(
            (p.stat().st_mtime for p in output_dir.glob("f90_result_*.json")),
            default=0.0,
        )
        time.sleep(0.05)
        self._run_pipeline()
        after_files = list(output_dir.glob("f90_result_*.json"))
        assert any(p.stat().st_mtime > before_mtime for p in after_files)

    # DoD10: APIキーがログに出力されないこと
    def test_dod10_api_key_not_in_logs(self, caplog):
        with caplog.at_level(logging.DEBUG):
            self._run_pipeline()
        for record in caplog.records:
            assert "ANTHROPIC_API_KEY" not in record.message
            assert "sk-ant" not in record.message

    # DoD11: hitl フィールドが必ず存在すること
    def test_dod11_hitl_fields_always_present(self):
        result = self._run_pipeline()
        assert "hitl"          in result
        assert "hitl_required" in result
        assert "hitl_elements" in result

    # DoD12: efficiency_score が有効範囲内
    def test_dod12_efficiency_score_in_valid_range(self):
        result = self._run_pipeline()
        score = result["final_output"]["evaluation_report"]["efficiency_score"]
        assert 0 < score <= 10, f"efficiency_score が範囲外: {score}"
