"""Unit tests for F60_MECE_Validation_Module (WP5100準拠)

F_series_overview.md の Unit Test 方針を継承し、
F10〜F50 と共通の assert_warning_contains / assert_wrapped_cause を再利用する。
"""

import logging
import math

import pytest

from src.agents.f60_module import (
    DUPLICATE_THRESHOLD,
    UNCERTAIN_HIGH,
    UNCERTAIN_LOW,
    _build_mece_report,
    _cosine_similarity,
    _detect_ambiguous,
    _detect_duplicates,
    _detect_missing,
    _validate_input,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数・ヘルパー
# ════════════════════════════════════════════════════════

def _task(task_id, text, priority="High", **kwargs):
    t = {"task_id": task_id, "templated_text": text, "priority": priority}
    t.update(kwargs)
    return t


VALID_INPUT = {
    "trace_id": "F50",
    "templated_tasks": [
        _task("T1", "【優先度: 高】次のタスクを実行せよ: LPを作成する"),
        _task("T2", "【優先度: 中】次のタスクを実行せよ: 新規顧客を獲得する", priority="Medium"),
        _task("T3", "【優先度: 低】参考タスク: 広告配信を開始する",          priority="Low"),
    ],
}

# テキストが完全一致 → cosine=1.0 > 0.85 → duplicate
DUPLICATE_TEXT = "【優先度: 高】次のタスクを実行せよ: LPを作成する"

INVALID_TYPE_INPUTS = [
    pytest.param(None,     id="none"),
    pytest.param("string", id="string"),
    pytest.param(42,       id="int"),
    pytest.param([],       id="list"),
]

INVALID_STRUCT_INPUTS = [
    pytest.param({},                                              id="empty_dict"),
    pytest.param({"trace_id": "F50"},                            id="missing_templated_tasks"),
    pytest.param({"templated_tasks": "not_a_list",
                  "trace_id": "F50"},                            id="tasks_not_list"),
]

INVALID_FIELD_INPUTS = [
    pytest.param(
        {"templated_tasks": [{"templated_text": "テスト", "priority": "High"}],
         "trace_id": "F50"},
        id="missing_task_id",
    ),
    pytest.param(
        {"templated_tasks": [{"task_id": "T1", "priority": "High"}],
         "trace_id": "F50"},
        id="missing_templated_text",
    ),
    pytest.param(
        {"templated_tasks": [{"task_id": "T1", "templated_text": "テスト"}],
         "trace_id": "F50"},
        id="missing_priority",
    ),
    pytest.param(
        {"templated_tasks": ["not_a_dict"], "trace_id": "F50"},
        id="task_not_dict",
    ),
]


def assert_warning_contains(caplog_records, keyword: str, category: str) -> None:
    matched = [r for r in caplog_records if keyword in r.message and r.levelno == logging.WARNING]
    assert matched, (
        f"WARNING [{category}] が見つかりません（keyword='{keyword}'）\n"
        f"実際の WARNING: {[r.message for r in caplog_records if r.levelno == logging.WARNING]}"
    )


def assert_wrapped_cause(exc_info, expected_cause_type, label: str = "") -> None:
    cause = exc_info.value.__cause__
    assert cause is not None, f"[{label}] __cause__ が None です"
    assert isinstance(cause, expected_cause_type), (
        f"[{label}] __cause__ の型: expected={expected_cause_type.__name__}, "
        f"actual={type(cause).__name__}"
    )


# ════════════════════════════════════════════════════════
# Test1 — 正常系：MECE準拠・レポート構造
# ════════════════════════════════════════════════════════

class TestNormalMeceCompliant:
    """重複・欠落・曖昧が存在しない場合に is_mece_compliant=True を返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def run(self):
        self.result = execute(VALID_INPUT)
        self.report = self.result["mece_report"]

    def test_trace_id_is_f60(self):
        assert self.result["trace_id"] == "F60"

    def test_source_trace_id_is_f50(self):
        assert self.result["source_trace_id"] == "F50"

    def test_mece_report_present(self):
        assert "mece_report" in self.result

    def test_mece_report_has_required_keys(self):
        required = {"duplicate_tasks", "missing_elements", "ambiguous_tasks", "is_mece_compliant"}
        assert required <= self.report.keys()

    def test_is_mece_compliant_true(self):
        assert self.report["is_mece_compliant"] is True

    def test_no_duplicates(self):
        assert self.report["duplicate_tasks"] == []

    def test_no_missing(self):
        assert self.report["missing_elements"] == []

    def test_no_ambiguous(self):
        assert self.report["ambiguous_tasks"] == []

    def test_hitl_false_when_compliant(self):
        assert self.result["hitl"] is False
        assert self.result["hitl_required"] is False

    def test_hitl_elements_empty(self):
        assert self.result["hitl_elements"] == []

    # ── cosine 類似度単体検証 ──────────────────────────

    def test_cosine_identical_texts(self):
        text = "LPを作成する"
        assert _cosine_similarity(text, text) == pytest.approx(1.0)

    def test_cosine_completely_different_texts(self):
        sim = _cosine_similarity("りんご", "自動車")
        assert sim == pytest.approx(0.0)

    def test_cosine_partial_overlap(self):
        # スペース区切りで共通トークン "LP作成" を持つテキスト
        a = "LP作成 売上拡大"
        b = "LP作成 広告出稿"
        sim = _cosine_similarity(a, b)
        assert 0.0 < sim < 1.0

    def test_cosine_empty_text_returns_zero(self):
        assert _cosine_similarity("", "テスト") == pytest.approx(0.0)
        assert _cosine_similarity("テスト", "") == pytest.approx(0.0)

    def test_cosine_symmetry(self):
        a = "LPを作成する"
        b = "広告を配信する"
        assert _cosine_similarity(a, b) == pytest.approx(_cosine_similarity(b, a))

    # ── _build_mece_report 単体検証 ─────────────────────

    def test_build_mece_report_compliant(self):
        report = _build_mece_report([], [], [])
        assert report["is_mece_compliant"] is True

    def test_build_mece_report_non_compliant(self):
        report = _build_mece_report(["T1"], [], [])
        assert report["is_mece_compliant"] is False

    def test_build_mece_report_any_non_empty(self):
        for args in [
            (["T1"], [], []),
            ([], ["E2"], []),
            ([], [], ["T3"]),
        ]:
            assert _build_mece_report(*args)["is_mece_compliant"] is False


# ════════════════════════════════════════════════════════
# Test2 — 異常系：型不正・構造不正・フィールド欠落
# ════════════════════════════════════════════════════════

class TestInvalidInput:

    @pytest.mark.parametrize("bad_input", INVALID_TYPE_INPUTS)
    def test_type_error_for_non_dict(self, bad_input):
        with pytest.raises(TypeError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_STRUCT_INPUTS)
    def test_value_error_for_invalid_structure(self, bad_input):
        with pytest.raises(ValueError):
            execute(bad_input)

    @pytest.mark.parametrize("bad_input", INVALID_FIELD_INPUTS)
    def test_type_error_for_missing_fields(self, bad_input):
        with pytest.raises(TypeError):
            execute(bad_input)

    def test_validate_input_none(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input(None)

    def test_validate_input_empty_dict(self):
        with pytest.raises(ValueError, match="空"):
            _validate_input({})

    def test_validate_input_missing_templated_tasks(self):
        with pytest.raises(ValueError, match="templated_tasks"):
            _validate_input({"trace_id": "F50"})

    def test_validate_input_tasks_not_list(self):
        with pytest.raises(ValueError, match="list"):
            _validate_input({"templated_tasks": "bad"})

    def test_validate_input_task_not_dict(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_input({"templated_tasks": ["not_a_dict"]})


# ════════════════════════════════════════════════════════
# Test3 — MECE非準拠：各検出ロジック
# ════════════════════════════════════════════════════════

class TestMeceNonCompliant:
    """duplicate / missing / ambiguous の各検出を独立して検証する。"""

    # ── 重複検出 ────────────────────────────────────────

    def test_duplicate_by_identical_text(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", DUPLICATE_TEXT),
            _task("T2", DUPLICATE_TEXT),
            _task("T3", "【優先度: 低】参考タスク: 広告配信"),
        ]}
        result = execute(data)
        assert "T1" in result["mece_report"]["duplicate_tasks"]
        assert "T2" in result["mece_report"]["duplicate_tasks"]
        assert result["mece_report"]["is_mece_compliant"] is False

    def test_duplicate_by_same_element_id(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する",   element_id="E1"),
            _task("T2", "広告を配信する", element_id="E1"),
        ]}
        result = execute(data)
        dups = result["mece_report"]["duplicate_tasks"]
        assert "T1" in dups and "T2" in dups

    def test_no_duplicate_for_different_texts(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "【優先度: 高】次のタスクを実行せよ: LP作成"),
            _task("T2", "【優先度: 低】参考タスク: 競合調査"),
        ]}
        result = execute(data)
        assert result["mece_report"]["duplicate_tasks"] == []

    def test_detect_duplicates_returns_sorted(self):
        tasks = [
            _task("T2", DUPLICATE_TEXT),
            _task("T1", DUPLICATE_TEXT),
        ]
        dups, _ = _detect_duplicates(tasks)
        assert dups == sorted(dups)

    # ── 抜け漏れ検出 ────────────────────────────────────

    def test_missing_element_id_detected(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する",   element_id="E1"),
            _task("T3", "広告を配信する", element_id="E3"),
        ]}
        result = execute(data)
        assert "E2" in result["mece_report"]["missing_elements"]

    def test_no_missing_when_sequential(self):
        tasks = [
            _task("T1", "LP作成", element_id="E1"),
            _task("T2", "広告配信", element_id="E2"),
            _task("T3", "SNS投稿", element_id="E3"),
        ]
        assert _detect_missing(tasks) == []

    def test_no_missing_without_element_id(self):
        tasks = [_task("T1", "LP作成"), _task("T2", "広告配信")]
        assert _detect_missing(tasks) == []

    def test_missing_multiple_gaps(self):
        tasks = [
            _task("T1", "LP作成",  element_id="E1"),
            _task("T4", "SNS投稿", element_id="E4"),
        ]
        missing = _detect_missing(tasks)
        assert "E2" in missing
        assert "E3" in missing

    # ── 曖昧検出 ────────────────────────────────────────

    def test_ambiguous_kaizen_detected(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "【優先度: 高】次のタスクを実行せよ: プロセスを改善する"),
        ]}
        result = execute(data)
        assert "T1" in result["mece_report"]["ambiguous_tasks"]

    def test_ambiguous_kojo_detected(self):
        assert _detect_ambiguous([_task("T1", "品質を向上させる")]) == ["T1"]

    def test_ambiguous_kento_detected(self):
        assert _detect_ambiguous([_task("T1", "施策を検討する")]) == ["T1"]

    def test_ambiguous_saitekika_detected(self):
        assert _detect_ambiguous([_task("T1", "プロセスを最適化する")]) == ["T1"]

    def test_no_ambiguous_for_concrete_text(self):
        assert _detect_ambiguous([_task("T1", "【優先度: 高】次のタスクを実行せよ: LPを作成する")]) == []

    def test_detect_ambiguous_skips_duplicates_in_one_task(self):
        """1タスクに複数の抽象語がある場合でも task_id は1回だけ登録されること。"""
        tasks = [_task("T1", "売上を改善して品質も向上させる")]
        result = _detect_ambiguous(tasks)
        assert result.count("T1") == 1

    # ── is_mece_compliant ─────────────────────────────

    def test_is_mece_compliant_false_when_duplicates(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", DUPLICATE_TEXT),
            _task("T2", DUPLICATE_TEXT),
        ]}
        assert execute(data)["mece_report"]["is_mece_compliant"] is False

    def test_is_mece_compliant_false_when_ambiguous(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "プロセスを改善する"),
        ]}
        assert execute(data)["mece_report"]["is_mece_compliant"] is False


# ════════════════════════════════════════════════════════
# Test4 — HITL移譲：空リスト・曖昧タスク・不確定類似度
# ════════════════════════════════════════════════════════

class TestHitlDelegation:

    def test_empty_tasks_hitl_required(self):
        data = {"trace_id": "F50", "templated_tasks": []}
        result = execute(data)
        assert result["hitl_required"] is True
        assert result["hitl"] is True
        assert result.get("hitl_reason") == "No tasks provided"

    def test_empty_tasks_trace_id_is_f60(self):
        data = {"trace_id": "F50", "templated_tasks": []}
        assert execute(data)["trace_id"] == "F60"

    def test_empty_tasks_mece_not_compliant(self):
        data = {"trace_id": "F50", "templated_tasks": []}
        assert execute(data)["mece_report"]["is_mece_compliant"] is False

    def test_ambiguous_tasks_trigger_hitl(self):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "売上を改善する"),
        ]}
        result = execute(data)
        assert result["hitl_required"] is True

    def test_uncertain_similarity_triggers_hitl(self, mocker):
        """cosine 類似度が 0.82（不確定域）の場合に hitl_required=True になること。"""
        mocker.patch(
            "src.agents.f60_module._cosine_similarity",
            return_value=0.82,
        )
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T2", "LPを設計する"),
        ]}
        result = execute(data)
        assert result["hitl_required"] is True
        assert len(result["hitl_elements"]) > 0

    def test_uncertain_ids_not_in_duplicates(self, mocker):
        """不確定域のタスクは duplicate_tasks には入らないこと。"""
        mocker.patch("src.agents.f60_module._cosine_similarity", return_value=0.82)
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T2", "LPを設計する"),
        ]}
        result = execute(data)
        assert "T1" not in result["mece_report"]["duplicate_tasks"]
        assert "T2" not in result["mece_report"]["duplicate_tasks"]

    def test_high_similarity_goes_to_duplicates_not_hitl(self, mocker):
        """cosine > 0.85 の場合は duplicate_tasks に入り hitl_elements には入らないこと。"""
        mocker.patch("src.agents.f60_module._cosine_similarity", return_value=0.90)
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T2", "LPを設計する"),
        ]}
        result = execute(data)
        dups = result["mece_report"]["duplicate_tasks"]
        assert "T1" in dups or "T2" in dups
        assert "T1" not in result["hitl_elements"]
        assert "T2" not in result["hitl_elements"]

    def test_no_hitl_when_fully_compliant(self):
        result = execute(VALID_INPUT)
        assert result["hitl_required"] is False
        assert result["hitl"] is False


# ════════════════════════════════════════════════════════
# Test5 — RuntimeError：類似度計算失敗・__cause__ 保持
# ════════════════════════════════════════════════════════

class TestRuntimeError:

    def test_runtime_error_on_cosine_failure(self, mocker):
        mocker.patch(
            "src.agents.f60_module._cosine_similarity",
            side_effect=RuntimeError("cosine 計算テストエラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)

    def test_cause_preserved_on_cosine_failure(self, mocker):
        """_detect_duplicates 内で RuntimeError にラップされること。"""
        original = ZeroDivisionError("test")
        mocker.patch("src.agents.f60_module._cosine_similarity", side_effect=original)
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        # _detect_duplicates が非 RuntimeError をラップして送出する
        assert_wrapped_cause(exc_info, ZeroDivisionError, label="cosine 計算失敗")

    def test_cosine_wraps_math_error(self, mocker):
        """_cosine_similarity 内で math エラー発生時に RuntimeError にラップされること。"""
        mocker.patch("src.agents.f60_module.math.sqrt", side_effect=ValueError("math error"))
        with pytest.raises(RuntimeError) as exc_info:
            _cosine_similarity("テスト", "テスト")
        assert_wrapped_cause(exc_info, ValueError, label="_cosine_similarity ラップ")

    def test_runtime_error_from_detect_duplicates_propagates(self, mocker):
        mocker.patch(
            "src.agents.f60_module._detect_duplicates",
            side_effect=RuntimeError("重複検出エラー"),
        )
        with pytest.raises(RuntimeError):
            execute(VALID_INPUT)


# ════════════════════════════════════════════════════════
# Test6 — WARNING継続：重複task_id・不正priority・不明trace_id
# ════════════════════════════════════════════════════════

class TestWarningContinuation:

    def test_duplicate_task_id_logs_warning(self, caplog):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T1", "広告を配信する"),
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "重複 task_id", "DuplicateTaskId")

    def test_invalid_priority_logs_warning(self, caplog):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する", priority="Critical"),
        ]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "不正な priority", "InvalidPriority")

    def test_unknown_trace_id_logs_warning(self, caplog):
        data = {"trace_id": "F99", "templated_tasks": VALID_INPUT["templated_tasks"]}
        with caplog.at_level(logging.WARNING):
            execute(data)
        assert_warning_contains(caplog.records, "F99", "UnknownTraceId")

    def test_processing_continues_after_duplicate_task_id(self, caplog):
        data = {"trace_id": "F50", "templated_tasks": [
            _task("T1", "LPを作成する"),
            _task("T1", "広告を配信する"),
        ]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F60"


# ════════════════════════════════════════════════════════
# Test7 — trace_id="F60"・パイプライン統合
# ════════════════════════════════════════════════════════

class TestTraceId:

    def test_normal_trace_id_is_f60(self):
        assert execute(VALID_INPUT)["trace_id"] == "F60"

    def test_empty_input_trace_id_is_f60(self):
        assert execute({"trace_id": "F50", "templated_tasks": []})["trace_id"] == "F60"

    def test_source_trace_id_reflects_input(self):
        assert execute(VALID_INPUT)["source_trace_id"] == "F50"

    def test_missing_trace_id_in_input(self, caplog):
        data = {"templated_tasks": VALID_INPUT["templated_tasks"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F60"
        assert result["source_trace_id"] == ""

    def test_unknown_source_trace_id_output_is_f60(self, caplog):
        data = {"trace_id": "UNKNOWN", "templated_tasks": VALID_INPUT["templated_tasks"]}
        with caplog.at_level(logging.WARNING):
            result = execute(data)
        assert result["trace_id"] == "F60"

    def test_f10_to_f60_pipeline(self, mocker):
        """F10→F20→F30→F40→F50→F60 の完全パイプラインを模擬して trace_id の伝播を検証する。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value=(
                '{"L1":"売上を伸ばす","L2":["新規獲得","リテンション"],'
                '"L3":["LP作成","広告配信"]}'
            ),
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec
        from src.agents.f40_module import execute as f40_exec
        from src.agents.f50_module import execute as f50_exec

        f10_out = f10_exec({"goal_text": "売上を前年比120%に成長させる"})
        f20_out = f20_exec(f10_out)
        f30_out = f30_exec(f20_out)
        f40_out = f40_exec(f30_out)
        f50_out = f50_exec(f40_out)
        f60_out = execute(f50_out)

        assert f60_out["trace_id"] == "F60"
        assert f60_out["source_trace_id"] == "F50"
        assert "mece_report" in f60_out

    def test_pipeline_mece_report_structure(self, mocker):
        """パイプライン末端の mece_report に必須キーが揃っていること。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value='{"L1":"売上を伸ばす","L2":["新規獲得"],"L3":["LP作成","広告配信"]}',
        )
        from src.agents.f10_module import execute as f10_exec
        from src.agents.f20_module import execute as f20_exec
        from src.agents.f30_module import execute as f30_exec
        from src.agents.f40_module import execute as f40_exec
        from src.agents.f50_module import execute as f50_exec

        f60_out = execute(f50_exec(f40_exec(f30_exec(f20_exec(f10_exec(
            {"goal_text": "売上を前年比120%に成長させる"}
        ))))))
        required = {"duplicate_tasks", "missing_elements", "ambiguous_tasks", "is_mece_compliant"}
        assert required <= f60_out["mece_report"].keys()

    def test_threshold_constants(self):
        """閾値定数が設計値であること（0.80 / 0.85）。"""
        assert UNCERTAIN_LOW    == pytest.approx(0.80)
        assert UNCERTAIN_HIGH   == pytest.approx(0.85)
        assert DUPLICATE_THRESHOLD == pytest.approx(0.85)
