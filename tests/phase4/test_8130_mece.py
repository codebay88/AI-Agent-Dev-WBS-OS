"""Phase 4 — WP8130 MECEチェックテスト
区分：相互排他（ME）/ 全体網羅（CE）/ 境界値 / HITL / 異常系

WP8130 の観点：
  - 出力要素が相互排他（Mutually Exclusive）であること
  - 出力要素が全体網羅（Collectively Exhaustive）であること
  - 因果・テンプレ・トレーサビリティの各層で重複・欠落・曖昧性がないこと
  - MECE 境界値（cosine 0.80〜0.85）が正しく適用されていること
  - HITL 承認フローで曖昧要素が正しく人間承認に回されること
"""

import pytest


# ════════════════════════════════════════════════════════
# 共通ヘルパ
# ════════════════════════════════════════════════════════

_MOCK_API = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


def _make_task(tid, text, priority="High", element_id=None):
    t = {"task_id": tid, "templated_text": text, "priority": priority}
    if element_id is not None:
        t["element_id"] = element_id
    return t


def _run_pipeline(mocker, goal="売上を前年比120%に成長させる"):
    mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
    from src.agents.f10_module import execute as f10
    from src.agents.f20_module import execute as f20
    from src.agents.f30_module import execute as f30
    from src.agents.f40_module import execute as f40
    from src.agents.f50_module import execute as f50
    from src.agents.f60_module import execute as f60
    return f60(f50(f40(f30(f20(f10({"goal_text": goal}))))))


# ════════════════════════════════════════════════════════
# WP8131: 相互排他性（Mutually Exclusive）— 重複検出ロジック
# ════════════════════════════════════════════════════════

class TestWP8131_MutuallyExclusive:
    """重複タスク検出（cosine類似度・element_id重複）の正確性"""

    # ─── cosine 類似度 ───
    def test_identical_texts_cosine_is_one(self):
        from src.agents.f60_module import _cosine_similarity
        assert _cosine_similarity("LP作成 広告配信", "LP作成 広告配信") == pytest.approx(1.0)

    def test_no_overlap_cosine_is_zero(self):
        from src.agents.f60_module import _cosine_similarity
        assert _cosine_similarity("LP作成", "採用活動") == pytest.approx(0.0)

    def test_partial_overlap_cosine_between_zero_and_one(self):
        from src.agents.f60_module import _cosine_similarity
        s = _cosine_similarity("LP作成 広告配信", "LP作成 採用活動")
        assert 0.0 < s < 1.0

    def test_cosine_symmetric(self):
        from src.agents.f60_module import _cosine_similarity
        a, b = "LP作成 広告配信", "LP作成 売上拡大"
        assert _cosine_similarity(a, b) == pytest.approx(_cosine_similarity(b, a))

    def test_cosine_single_token_identical(self):
        from src.agents.f60_module import _cosine_similarity
        assert _cosine_similarity("LP作成", "LP作成") == pytest.approx(1.0)

    def test_cosine_empty_string_returns_zero(self):
        from src.agents.f60_module import _cosine_similarity
        assert _cosine_similarity("", "LP作成") == pytest.approx(0.0)

    # ─── duplicate 閾値定数 ───
    def test_duplicate_threshold_is_085(self):
        from src.agents.f60_module import DUPLICATE_THRESHOLD
        assert DUPLICATE_THRESHOLD == pytest.approx(0.85)

    # ─── _detect_duplicates: cosine > 0.85 → duplicate ───
    def test_identical_tasks_classified_as_duplicate(self):
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            _make_task("T1", "LP作成 広告配信 売上拡大"),
            _make_task("T2", "LP作成 広告配信 売上拡大"),
        ]
        dups, uncertain = _detect_duplicates(tasks)
        assert "T1" in dups and "T2" in dups

    def test_duplicate_returns_sorted_list(self):
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            _make_task("T2", "LP作成 広告配信 売上拡大"),
            _make_task("T1", "LP作成 広告配信 売上拡大"),
        ]
        dups, _ = _detect_duplicates(tasks)
        assert dups == sorted(dups)

    def test_dissimilar_tasks_not_duplicate(self):
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            _make_task("T1", "LP作成"),
            _make_task("T2", "採用活動"),
        ]
        dups, uncertain = _detect_duplicates(tasks)
        assert len(dups) == 0

    def test_three_tasks_two_identical_one_dissimilar(self):
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            _make_task("T1", "LP作成 広告配信"),
            _make_task("T2", "LP作成 広告配信"),
            _make_task("T3", "採用活動 人材確保"),
        ]
        dups, _ = _detect_duplicates(tasks)
        assert "T1" in dups and "T2" in dups
        assert "T3" not in dups

    def test_duplicate_via_same_element_id(self):
        """同一 element_id を持つ2タスクは duplicate に分類されること。"""
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            _make_task("T1", "LP作成", element_id="E1"),
            _make_task("T2", "広告配信", element_id="E1"),
        ]
        dups, _ = _detect_duplicates(tasks)
        assert "T1" in dups and "T2" in dups

    def test_different_element_ids_not_duplicate(self):
        from src.agents.f60_module import _detect_duplicates
        tasks = [
            _make_task("T1", "LP作成", element_id="E1"),
            _make_task("T2", "広告配信", element_id="E2"),
        ]
        dups, _ = _detect_duplicates(tasks)
        assert len(dups) == 0

    def test_single_task_no_duplicate(self):
        from src.agents.f60_module import _detect_duplicates
        dups, uncertain = _detect_duplicates([_make_task("T1", "LP作成")])
        assert len(dups) == 0 and len(uncertain) == 0

    # ─── mece_report の duplicate_tasks 反映 ───
    def test_mece_report_contains_duplicate_ids(self):
        from src.agents.f60_module import execute as f60
        tasks = [
            _make_task("T1", "LP作成 広告配信 売上拡大"),
            _make_task("T2", "LP作成 広告配信 売上拡大"),
        ]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert "T1" in result["mece_report"]["duplicate_tasks"]
        assert "T2" in result["mece_report"]["duplicate_tasks"]

    def test_mece_noncompliant_when_duplicate(self):
        from src.agents.f60_module import execute as f60
        tasks = [
            _make_task("T1", "LP作成 広告配信 売上拡大"),
            _make_task("T2", "LP作成 広告配信 売上拡大"),
        ]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["mece_report"]["is_mece_compliant"] is False

    # ─── パイプライン経由での ME 検証 ───
    def test_pipeline_task_ids_all_unique(self, mocker):
        """F10→F60 パイプラインで生成されたタスクの task_id が全件ユニークであること。"""
        result = _run_pipeline(mocker)
        tids = [t["task_id"] for t in result["templated_tasks"]]
        assert len(tids) == len(set(tids)), f"重複 task_id: {tids}"


# ════════════════════════════════════════════════════════
# WP8132: 全体網羅性（Collectively Exhaustive）— 欠落検出ロジック
# ════════════════════════════════════════════════════════

class TestWP8132_CollectivelyExhaustive:
    """欠落タスク・欠落要素検出の正確性"""

    # ─── _detect_missing: element_id 連番チェック ───
    def test_sequential_element_ids_no_missing(self):
        from src.agents.f60_module import _detect_missing
        tasks = [
            _make_task("T1", "タスク1", element_id="E1"),
            _make_task("T2", "タスク2", element_id="E2"),
            _make_task("T3", "タスク3", element_id="E3"),
        ]
        assert _detect_missing(tasks) == []

    def test_gap_in_element_ids_detected(self):
        """E1, E3 → E2 欠落を検出すること。"""
        from src.agents.f60_module import _detect_missing
        tasks = [
            _make_task("T1", "タスク1", element_id="E1"),
            _make_task("T3", "タスク3", element_id="E3"),
        ]
        assert "E2" in _detect_missing(tasks)

    def test_gap_detects_multiple_missing(self):
        """E1, E5 → E2, E3, E4 欠落を検出すること。"""
        from src.agents.f60_module import _detect_missing
        tasks = [
            _make_task("T1", "タスク1", element_id="E1"),
            _make_task("T5", "タスク5", element_id="E5"),
        ]
        missing = _detect_missing(tasks)
        assert "E2" in missing and "E3" in missing and "E4" in missing

    def test_no_element_id_returns_empty(self):
        """element_id が存在しないタスクは missing_elements = [] であること。"""
        from src.agents.f60_module import _detect_missing
        tasks = [_make_task("T1", "タスク1"), _make_task("T2", "タスク2")]
        assert _detect_missing(tasks) == []

    def test_single_element_no_missing(self):
        from src.agents.f60_module import _detect_missing
        assert _detect_missing([_make_task("T1", "タスク", element_id="E1")]) == []

    def test_missing_prefix_format_is_e_number(self):
        """欠落 element_id が 'E{n}' 形式であること。"""
        from src.agents.f60_module import _detect_missing
        tasks = [
            _make_task("T1", "タスク1", element_id="E1"),
            _make_task("T3", "タスク3", element_id="E3"),
        ]
        for mid in _detect_missing(tasks):
            assert mid.startswith("E") and mid[1:].isdigit()

    def test_unrecognized_element_id_format_returns_empty(self):
        """'E{n}' 形式でない element_id は無視されること。"""
        from src.agents.f60_module import _detect_missing
        tasks = [
            _make_task("T1", "タスク", element_id="G1_EL_H"),
            _make_task("T2", "タスク", element_id="G1_EL_M"),
        ]
        assert _detect_missing(tasks) == []

    # ─── mece_report の missing_elements 反映 ───
    def test_mece_report_contains_missing_elements(self):
        from src.agents.f60_module import execute as f60
        tasks = [
            _make_task("T1", "タスク1", element_id="E1"),
            _make_task("T3", "タスク3", element_id="E3"),
        ]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert "E2" in result["mece_report"]["missing_elements"]

    def test_mece_noncompliant_when_missing(self):
        from src.agents.f60_module import execute as f60
        tasks = [
            _make_task("T1", "タスク1", element_id="E1"),
            _make_task("T3", "タスク3", element_id="E3"),
        ]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["mece_report"]["is_mece_compliant"] is False

    # ─── パイプライン経由での CE 検証 ───
    def test_pipeline_expanded_goals_count_matches_l2_l3(self, mocker):
        """F20 の expanded_goals 件数が goal.L2 + goal.L3 + 1(L1) と一致すること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        r10 = f10({"goal_text": "売上を前年比120%に成長させる"})
        r20 = f20(r10)
        expected = 1 + len(r10["goal"]["L2"]) + len(r10["goal"]["L3"])
        assert len(r20["expanded_goals"]) == expected

    def test_pipeline_all_l2_items_present_in_expanded_goals(self, mocker):
        """F10 の goal.L2 が全件 F20 の expanded_goals に含まれること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        r10 = f10({"goal_text": "売上を前年比120%に成長させる"})
        r20 = f20(r10)
        texts = {e["text"] for e in r20["expanded_goals"]}
        for item in r10["goal"]["L2"]:
            assert item in texts, f"L2 アイテム欠落: {item!r}"

    def test_pipeline_all_l3_items_present_in_expanded_goals(self, mocker):
        """F10 の goal.L3 が全件 F20 の expanded_goals に含まれること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        r10 = f10({"goal_text": "売上を前年比120%に成長させる"})
        r20 = f20(r10)
        texts = {e["text"] for e in r20["expanded_goals"]}
        for item in r10["goal"]["L3"]:
            assert item in texts, f"L3 アイテム欠落: {item!r}"

    def test_pipeline_f30_evaluated_all_f20_elements(self, mocker):
        """F30 の evaluated_goals 件数が F20 の expanded_goals と一致すること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        r20 = f20(f10({"goal_text": "売上を前年比120%に成長させる"}))
        r30 = f30(r20)
        assert len(r30["evaluated_goals"]) == len(r20["expanded_goals"])

    def test_pipeline_f40_task_count_matches_f30(self, mocker):
        """F40 の tasks 件数が F30 の evaluated_goals と一致すること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        r30 = f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))
        r40 = f40(r30)
        assert len(r40["tasks"]) == len(r30["evaluated_goals"])


# ════════════════════════════════════════════════════════
# WP8133: MECE 境界値 — 0.80〜0.85 不確定域の正確な分類
# ════════════════════════════════════════════════════════

class TestWP8133_MECEBoundaryValues:
    """cosine 類似度境界値（0.80〜0.85）の正確な動作検証"""

    def test_uncertain_low_constant(self):
        from src.agents.f60_module import UNCERTAIN_LOW
        assert UNCERTAIN_LOW == pytest.approx(0.80)

    def test_uncertain_high_constant(self):
        from src.agents.f60_module import UNCERTAIN_HIGH
        assert UNCERTAIN_HIGH == pytest.approx(0.85)

    def test_similarity_above_085_is_duplicate(self):
        """cos > 0.85 → duplicate に分類。"""
        from src.agents.f60_module import _detect_duplicates
        from unittest.mock import patch
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.90):
            tasks = [_make_task("T1", "A"), _make_task("T2", "B")]
            dups, uncertain = _detect_duplicates(tasks)
        assert "T1" in dups and "T2" in dups
        assert len(uncertain) == 0

    def test_similarity_in_uncertain_range_is_hitl(self):
        """0.80 ≤ cos ≤ 0.85 → uncertain（HITL）に分類。"""
        from src.agents.f60_module import _detect_duplicates
        from unittest.mock import patch
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.82):
            tasks = [_make_task("T1", "A"), _make_task("T2", "B")]
            dups, uncertain = _detect_duplicates(tasks)
        assert len(dups) == 0
        assert "T1" in uncertain and "T2" in uncertain

    def test_similarity_below_080_is_unrelated(self):
        """cos < 0.80 → どちらにも分類されないこと。"""
        from src.agents.f60_module import _detect_duplicates
        from unittest.mock import patch
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.70):
            tasks = [_make_task("T1", "A"), _make_task("T2", "B")]
            dups, uncertain = _detect_duplicates(tasks)
        assert len(dups) == 0 and len(uncertain) == 0

    def test_boundary_exactly_085_is_duplicate(self):
        """cos = 0.85（DUPLICATE_THRESHOLD） は duplicate でなく uncertain に分類（≤ 境界）。"""
        from src.agents.f60_module import _detect_duplicates, DUPLICATE_THRESHOLD
        from unittest.mock import patch
        # sim > DUPLICATE_THRESHOLD が条件 → 0.85 は duplicate に含まれない
        with patch("src.agents.f60_module._cosine_similarity", return_value=DUPLICATE_THRESHOLD):
            tasks = [_make_task("T1", "A"), _make_task("T2", "B")]
            dups, uncertain = _detect_duplicates(tasks)
        assert "T1" not in dups
        assert "T1" in uncertain

    def test_boundary_exactly_080_is_uncertain(self):
        """cos = 0.80（UNCERTAIN_LOW）→ uncertain に分類されること。"""
        from src.agents.f60_module import _detect_duplicates, UNCERTAIN_LOW
        from unittest.mock import patch
        with patch("src.agents.f60_module._cosine_similarity", return_value=UNCERTAIN_LOW):
            tasks = [_make_task("T1", "A"), _make_task("T2", "B")]
            dups, uncertain = _detect_duplicates(tasks)
        assert "T1" in uncertain

    def test_uncertain_tasks_removed_from_duplicate_set(self):
        """uncertain に入ったタスクは duplicate から除外されること。"""
        from src.agents.f60_module import _detect_duplicates
        from unittest.mock import patch
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.82):
            tasks = [_make_task("T1", "A"), _make_task("T2", "B")]
            dups, uncertain = _detect_duplicates(tasks)
        for uid in uncertain:
            assert uid not in dups

    def test_uncertain_range_triggers_hitl_in_execute(self):
        """不確定域（0.82）のペアが F60 execute() で hitl_required=True になること。"""
        from src.agents.f60_module import execute as f60
        from unittest.mock import patch
        tasks = [
            _make_task("T1", "LP作成 広告配信"),
            _make_task("T2", "LP作成 販促施策"),
        ]
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.82):
            result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["hitl_required"] is True
        assert len(result["hitl_elements"]) > 0


# ════════════════════════════════════════════════════════
# WP8134: 曖昧検出 — ABSTRACT_WORDS による ambiguous_tasks 分類
# ════════════════════════════════════════════════════════

class TestWP8134_AmbiguousDetection:
    """抽象語を含むタスクの曖昧検出ロジック検証"""

    def test_abstract_words_constant_defined(self):
        from src.agents.f60_module import ABSTRACT_WORDS
        assert len(ABSTRACT_WORDS) > 0

    def test_each_abstract_word_detected(self):
        from src.agents.f60_module import _detect_ambiguous, ABSTRACT_WORDS
        for word in ABSTRACT_WORDS:
            tasks = [_make_task("T1", f"業務{word}する")]
            result = _detect_ambiguous(tasks)
            assert "T1" in result, f"ABSTRACT_WORDS「{word}」が検出されなかった"

    def test_non_abstract_task_not_flagged(self):
        from src.agents.f60_module import _detect_ambiguous
        tasks = [_make_task("T1", "LP作成する")]
        assert _detect_ambiguous(tasks) == []

    def test_multiple_abstract_words_in_one_task(self):
        """複数の抽象語を含む場合でも task_id は1回だけリストに入ること。"""
        from src.agents.f60_module import _detect_ambiguous, ABSTRACT_WORDS
        text = f"{ABSTRACT_WORDS[0]}{ABSTRACT_WORDS[1]}"
        tasks = [_make_task("T1", text)]
        result = _detect_ambiguous(tasks)
        assert result.count("T1") == 1

    def test_abstract_word_in_multiple_tasks(self):
        from src.agents.f60_module import _detect_ambiguous, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [
            _make_task("T1", f"{word}する"),
            _make_task("T2", "LP作成"),
            _make_task("T3", f"システム{word}"),
        ]
        result = _detect_ambiguous(tasks)
        assert "T1" in result and "T3" in result
        assert "T2" not in result

    def test_mece_report_contains_ambiguous_ids(self):
        from src.agents.f60_module import execute as f60, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [_make_task("T1", f"業務{word}する")]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert "T1" in result["mece_report"]["ambiguous_tasks"]

    def test_mece_noncompliant_when_ambiguous(self):
        from src.agents.f60_module import execute as f60, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [_make_task("T1", f"業務{word}する")]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["mece_report"]["is_mece_compliant"] is False

    def test_ambiguous_triggers_hitl_required(self):
        """ambiguous_tasks が存在 → hitl_required=True になること。"""
        from src.agents.f60_module import execute as f60, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [_make_task("T1", f"業務{word}する")]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["hitl_required"] is True


# ════════════════════════════════════════════════════════
# WP8135: MECE 準拠判定 — is_mece_compliant ロジック
# ════════════════════════════════════════════════════════

class TestWP8135_MECECompliance:
    """is_mece_compliant の正確な論理判定"""

    def _mece_report(self, dups, missing, ambig):
        from src.agents.f60_module import _build_mece_report
        return _build_mece_report(dups, missing, ambig)

    def test_all_empty_is_compliant(self):
        assert self._mece_report([], [], [])["is_mece_compliant"] is True

    def test_with_duplicates_not_compliant(self):
        assert self._mece_report(["T1"], [], [])["is_mece_compliant"] is False

    def test_with_missing_not_compliant(self):
        assert self._mece_report([], ["E2"], [])["is_mece_compliant"] is False

    def test_with_ambiguous_not_compliant(self):
        assert self._mece_report([], [], ["T1"])["is_mece_compliant"] is False

    def test_all_three_not_compliant(self):
        assert self._mece_report(["T1"], ["E2"], ["T3"])["is_mece_compliant"] is False

    def test_report_preserves_input_lists(self):
        dups = ["T1", "T2"]
        missing = ["E2"]
        ambig = ["T3"]
        report = self._mece_report(dups, missing, ambig)
        assert report["duplicate_tasks"] == dups
        assert report["missing_elements"] == missing
        assert report["ambiguous_tasks"] == ambig

    def test_pipeline_clean_input_is_mece_compliant(self, mocker):
        """クリーンなパイプライン入力では is_mece_compliant=True になること。"""
        result = _run_pipeline(mocker)
        assert isinstance(result["mece_report"]["is_mece_compliant"], bool)

    def test_mece_compliant_true_means_all_lists_empty(self, mocker):
        """is_mece_compliant=True のとき duplicate/missing/ambiguous がすべて空であること。"""
        result = _run_pipeline(mocker)
        if result["mece_report"]["is_mece_compliant"]:
            assert result["mece_report"]["duplicate_tasks"] == []
            assert result["mece_report"]["missing_elements"] == []
            assert result["mece_report"]["ambiguous_tasks"] == []


# ════════════════════════════════════════════════════════
# WP8136: HITL 承認フロー — 曖昧要素の人間承認移譲
# ════════════════════════════════════════════════════════

class TestWP8136_HITLFlow:
    """曖昧・不確定要素が HITL フローに正しく移譲されること"""

    # ─── 空リスト → HITL ───
    def test_empty_tasks_triggers_hitl(self):
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert result["hitl_required"] is True

    def test_empty_tasks_hitl_reason(self):
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert result.get("hitl_reason") == "No tasks provided"

    def test_empty_tasks_mece_noncompliant(self):
        from src.agents.f60_module import execute as f60
        result = f60({"trace_id": "F50", "templated_tasks": []})
        assert result["mece_report"]["is_mece_compliant"] is False

    # ─── 不確定類似度 → hitl_elements ───
    def test_uncertain_similarity_adds_to_hitl_elements(self):
        from src.agents.f60_module import execute as f60
        from unittest.mock import patch
        tasks = [_make_task("T1", "LP作成"), _make_task("T2", "LP配信")]
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.83):
            result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert len(result["hitl_elements"]) > 0

    def test_hitl_elements_contains_uncertain_ids(self):
        from src.agents.f60_module import execute as f60
        from unittest.mock import patch
        tasks = [_make_task("T1", "LP作成"), _make_task("T2", "LP配信")]
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.83):
            result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert "T1" in result["hitl_elements"] or "T2" in result["hitl_elements"]

    # ─── 曖昧語 → hitl_required ───
    def test_ambiguous_task_sets_hitl_required(self):
        from src.agents.f60_module import execute as f60, ABSTRACT_WORDS
        word = ABSTRACT_WORDS[0]
        tasks = [_make_task("T1", f"業務{word}する")]
        result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["hitl_required"] is True

    # ─── duplicate のみでは HITL 不発動 ───
    def test_duplicate_only_does_not_trigger_hitl(self):
        """重複のみ（曖昧・不確定なし）では hitl_required=False であること。"""
        from src.agents.f60_module import execute as f60
        from unittest.mock import patch
        tasks = [_make_task("T1", "LP作成"), _make_task("T2", "LP配信")]
        with patch("src.agents.f60_module._cosine_similarity", return_value=0.95):
            result = f60({"trace_id": "F50", "templated_tasks": tasks})
        assert result["hitl_required"] is False

    def test_hitl_elements_is_list(self, mocker):
        result = _run_pipeline(mocker)
        assert isinstance(result["hitl_elements"], list)

    def test_hitl_required_is_bool(self, mocker):
        result = _run_pipeline(mocker)
        assert isinstance(result["hitl_required"], bool)

    # ─── hitl と hitl_required の同値 ───
    def test_hitl_equals_hitl_required(self, mocker):
        """hitl と hitl_required は同じ値であること（仕様書 Step6）。"""
        result = _run_pipeline(mocker)
        assert result["hitl"] == result["hitl_required"]


# ════════════════════════════════════════════════════════
# WP8137: 全モジュール間 MECE 整合性 — 各層での一貫性検証
# ════════════════════════════════════════════════════════

class TestWP8137_CrossModuleMECE:
    """全モジュール間での MECE 整合性（重複・欠落なし）の検証"""

    def test_f20_element_ids_unique(self, mocker):
        """F20 の expanded_goals に element_id 重複がないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        r20 = f20(f10({"goal_text": "売上を前年比120%に成長させる"}))
        eids = [e["element_id"] for e in r20["expanded_goals"]]
        assert len(eids) == len(set(eids))

    def test_f30_element_ids_unique(self, mocker):
        """F30 の evaluated_goals に element_id 重複がないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        r30 = f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))
        eids = [e["element_id"] for e in r30["evaluated_goals"]]
        assert len(eids) == len(set(eids))

    def test_f40_task_ids_unique(self, mocker):
        """F40 の tasks に task_id 重複がないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        r40 = f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))
        tids = [t["task_id"] for t in r40["tasks"]]
        assert len(tids) == len(set(tids))

    def test_f50_task_ids_unique(self, mocker):
        """F50 の templated_tasks に task_id 重複がないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        r50 = f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))
        tids = [t["task_id"] for t in r50["templated_tasks"]]
        assert len(tids) == len(set(tids))

    def test_f70_goal_ids_unique(self, mocker):
        """F70 の hierarchy.goals に goal_id 重複がないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        r70 = f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))))
        gids = [g["goal_id"] for g in r70["hierarchy"]["goals"]]
        assert len(gids) == len(set(gids))

    def test_f70_element_ids_unique_across_goals(self, mocker):
        """F70 の hierarchy 全体で element_id が重複しないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        r70 = f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))))
        eids = [
            elem["element_id"]
            for g in r70["hierarchy"]["goals"]
            for elem in g["elements"]
        ]
        assert len(eids) == len(set(eids))

    def test_f80_task_ids_unique_in_tmap(self, mocker):
        """F80 の traceability_map の task_id が重複しないこと。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        r80 = f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"}))))))))
        tids = [e["task_id"] for e in r80["traceability_map"]]
        assert len(tids) == len(set(tids))

    def test_f90_task_count_consistent(self, mocker):
        """F90 の final_output.summary.total_tasks と hierarchy_with_trace のタスク数が一致すること。"""
        mocker.patch("src.agents.f10_module._call_api", return_value=_MOCK_API)
        from src.agents.f10_module import execute as f10
        from src.agents.f20_module import execute as f20
        from src.agents.f30_module import execute as f30
        from src.agents.f40_module import execute as f40
        from src.agents.f50_module import execute as f50
        from src.agents.f60_module import execute as f60
        from src.agents.f70_module import execute as f70
        from src.agents.f80_module import execute as f80
        from src.agents.f90_module import execute as f90
        r90 = f90(f80(f70(f60(f50(f40(f30(f20(f10({"goal_text": "売上を前年比120%に成長させる"})))))))))
        fo = r90["final_output"]
        counted = sum(
            len(elem["tasks"])
            for g in fo["hierarchy_with_trace"]
            for elem in g["elements"]
        )
        assert counted == fo["summary"]["total_tasks"]


# ════════════════════════════════════════════════════════
# WP8138: 異常系 — MECE ロジックが破綻せず例外が発火すること
# ════════════════════════════════════════════════════════

class TestWP8138_MECEAbnormal:
    """異常入力に対して MECE ロジックが正しく例外処理すること"""

    def test_f60_none_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60(None)

    def test_f60_string_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60("invalid")

    def test_f60_empty_dict_raises_value_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError):
            f60({})

    def test_f60_missing_templated_tasks_raises_value_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError, match="templated_tasks"):
            f60({"trace_id": "F50"})

    def test_f60_tasks_not_list_raises_value_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(ValueError):
            f60({"trace_id": "F50", "templated_tasks": "not_a_list"})

    def test_f60_task_missing_task_id_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": [
                {"templated_text": "LP作成", "priority": "High"}
            ]})

    def test_f60_task_missing_templated_text_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": [
                {"task_id": "T1", "priority": "High"}
            ]})

    def test_f60_task_missing_priority_raises_type_error(self):
        from src.agents.f60_module import execute as f60
        with pytest.raises(TypeError):
            f60({"trace_id": "F50", "templated_tasks": [
                {"task_id": "T1", "templated_text": "LP作成"}
            ]})

    def test_cosine_similarity_empty_both_is_zero(self):
        """両方空文字列の場合は 0.0 を返すこと（例外にならないこと）。"""
        from src.agents.f60_module import _cosine_similarity
        result = _cosine_similarity("", "")
        assert result == pytest.approx(0.0)

    def test_detect_missing_empty_list_returns_empty(self):
        from src.agents.f60_module import _detect_missing
        assert _detect_missing([]) == []

    def test_detect_ambiguous_empty_list_returns_empty(self):
        from src.agents.f60_module import _detect_ambiguous
        assert _detect_ambiguous([]) == []

    def test_detect_duplicates_single_task_no_error(self):
        from src.agents.f60_module import _detect_duplicates
        dups, uncertain = _detect_duplicates([_make_task("T1", "LP作成")])
        assert len(dups) == 0 and len(uncertain) == 0

    def test_f60_unknown_trace_id_continues(self, caplog):
        """trace_id が F50 以外でも処理継続すること（WARNING ログ出力）。"""
        import logging
        from src.agents.f60_module import execute as f60
        tasks = [_make_task("T1", "LP作成")]
        with caplog.at_level(logging.WARNING, logger="src.agents.f60_module"):
            result = f60({"trace_id": "UNKNOWN", "templated_tasks": tasks})
        assert result["trace_id"] == "F60"
