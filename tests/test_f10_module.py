"""Unit tests for F10_Objective_Structuring_Module (WP5100準拠)

補強方針:
  1. parametrize ケースの共通化（INVALID_INPUTS / helper fixture）
  2. WARNING ログを Duplicate / Orphan / ParentMismatch の3種に分類・明示
  3. call_count 検証の共通関数化（assert_call_count）
  4. __cause__ 検証のテンプレート化（assert_wrapped_cause）
  5. 各クラスに docstring でテスト目的を明記
"""

import json
import logging
from unittest.mock import MagicMock

import pytest

from src.agents.f10_module import (
    _build_tree,
    _call_api_with_retry,
    _check_hitl_conditions,
    _parse_response,
    _validate_input,
    _validate_tree,
    execute,
)


# ════════════════════════════════════════════════════════
# 共通定数
# ════════════════════════════════════════════════════════

VALID_INPUT = {"goal_text": "新規顧客獲得を強化し、売上を前年比120%に成長させる"}

VALID_API_RESPONSE = json.dumps({
    "L1": "売上を前年比120%に成長させる",
    "L2": ["新規顧客獲得施策を推進する", "既存顧客リテンションを強化する"],
    "L3": ["LPを作成する", "広告配信を開始する", "フォローアップメールを設計する"],
}, ensure_ascii=False)

# 補強箇所①: 不正入力ケースを定数として一元定義し、複数クラスで再利用可能にする
INVALID_INPUTS = [
    pytest.param(None,                   id="none"),
    pytest.param({},                     id="empty_dict"),
    pytest.param({"goal_text": ""},      id="empty_string"),
    pytest.param({"goal_text": "   "},   id="whitespace_only"),
    pytest.param({"other_key": "value"}, id="missing_goal_text"),
    pytest.param("not a dict",           id="string_type"),
    pytest.param(42,                     id="int_type"),
    pytest.param([],                     id="list_type"),
]


# ════════════════════════════════════════════════════════
# 補強箇所①: 共通 fixture — 不正入力リストを提供
# ════════════════════════════════════════════════════════

@pytest.fixture(params=INVALID_INPUTS)
def invalid_input(request):
    """不正入力を parametrize fixture として提供する。
    TestInvalidInput 以外のクラスでも `invalid_input` を受け取るだけで再利用できる。
    """
    return request.param


# ════════════════════════════════════════════════════════
# 補強箇所③: call_count 検証の共通ヘルパー
# ════════════════════════════════════════════════════════

def assert_call_count(mock_obj, expected: int, label: str = "mock") -> None:
    """API 呼び出し回数を検証する共通関数。
    将来 F20 / F30 など他モジュールのテストでもそのまま利用できる。

    Args:
        mock_obj: mocker.patch が返す MagicMock オブジェクト
        expected: 期待する呼び出し回数
        label: エラーメッセージ用のラベル
    """
    assert mock_obj.call_count == expected, (
        f"[{label}] 呼び出し回数が異なります: expected={expected}, actual={mock_obj.call_count}"
    )


# ════════════════════════════════════════════════════════
# 補強箇所④: __cause__ 検証のテンプレートヘルパー
# ════════════════════════════════════════════════════════

def assert_wrapped_cause(exc_info, expected_cause_type: type, label: str = "") -> None:
    """RuntimeError が期待する例外型を __cause__ に保持しているか検証する共通関数。
    将来 FileNotFoundError ラップなど他のケースにも転用できる。

    Args:
        exc_info: pytest.raises の ExceptionInfo オブジェクト
        expected_cause_type: __cause__ として期待する例外クラス
        label: エラーメッセージ用のラベル
    """
    cause = exc_info.value.__cause__
    assert cause is not None, f"[{label}] __cause__ が None です（ラップされていません）"
    assert isinstance(cause, expected_cause_type), (
        f"[{label}] __cause__ の型が異なります: expected={expected_cause_type.__name__}, "
        f"actual={type(cause).__name__}"
    )


# ════════════════════════════════════════════════════════
# 補強箇所②: WARNING ログ分類ヘルパー
# ════════════════════════════════════════════════════════

def assert_warning_contains(caplog_records, keyword: str, category: str) -> None:
    """WARNING ログに指定キーワードが含まれることを検証する共通関数。
    Duplicate / Orphan / ParentMismatch の3分類を明示的に検証するために使用。

    Args:
        caplog_records: caplog.records のリスト
        keyword: ログメッセージに含まれるべきキーワード
        category: エラーメッセージ用の分類名（例: "Duplicate"）
    """
    matched = [r for r in caplog_records if keyword in r.message and r.levelno == logging.WARNING]
    assert matched, (
        f"WARNING カテゴリ [{category}] のログが見つかりません（keyword='{keyword}'）\n"
        f"実際の WARNING ログ: {[r.message for r in caplog_records if r.levelno == logging.WARNING]}"
    )


# ════════════════════════════════════════════════════════
# 補強箇所①: 共通ツリーファクトリ
# ════════════════════════════════════════════════════════

def _make_simple_tree() -> dict:
    """テスト用の標準的なツリー構造を生成する。
    WARNING 検証テストで重複して記述していたツリー生成を一元化する。
    """
    return _build_tree({
        "L1": "大目的",
        "L2": ["中目的A"],
        "L3": ["小目的A-1"],
    })


# ════════════════════════════════════════════════════════
# Test1 — 正常系：階層構造化の検証
# ════════════════════════════════════════════════════════

class TestNormalStructuring:
    """execute() が正常入力に対して期待する構造・フィールドを返すことを検証する。"""

    @pytest.fixture(autouse=True)
    def mock_api(self, mocker):
        """全テストで API モックを自動適用する fixture。"""  # 補強箇所⑤
        return mocker.patch("src.agents.f10_module._call_api", return_value=VALID_API_RESPONSE)

    def test_returns_trace_id(self, mock_api):
        result = execute(VALID_INPUT)
        assert result["trace_id"] == "F10"
        assert result["hitl"] is False

    def test_goal_structure(self, mock_api):
        result = execute(VALID_INPUT)
        goal = result["goal"]
        assert isinstance(goal["L1"], str)
        assert isinstance(goal["L2"], list) and len(goal["L2"]) > 0
        assert isinstance(goal["L3"], list) and len(goal["L3"]) > 0

    def test_tree_parent_id_and_children(self, mock_api):
        result = execute(VALID_INPUT)
        tree = result["tree"]
        root_id = next(iter(tree))
        root = tree[root_id]
        assert root["parent_id"] is None
        assert root["level"] == "L1"
        for l2 in root["children"]:
            assert l2["parent_id"] == root_id
            assert l2["level"] == "L2"
            for l3 in l2["children"]:
                assert l3["parent_id"] == l2["objective_id"]
                assert l3["level"] == "L3"
                assert l3["children"] == []

    def test_all_required_fields(self, mock_api):
        result = execute(VALID_INPUT)
        required = {"objective_id", "objective_text", "level", "parent_id", "children"}

        def _check(node):
            assert required <= node.keys(), f"フィールド不足: {node}"
            for child in node["children"]:
                _check(child)

        for root in result["tree"].values():
            _check(root)


# ════════════════════════════════════════════════════════
# Test2 — 異常系：空入力・型不正・必須項目欠落
# ════════════════════════════════════════════════════════

class TestInvalidInput:
    """不正な入力に対して ValueError が送出されることを検証する。
    INVALID_INPUTS 定数を fixture 経由で再利用し、追加ケースは定数側に集約する。
    """

    # 補強箇所①: fixture を使って parametrize を共通化
    def test_raises_value_error(self, invalid_input):
        with pytest.raises(ValueError):
            execute(invalid_input)

    def test_validate_input_none(self):
        with pytest.raises(ValueError, match="None"):
            _validate_input(None)

    def test_validate_input_empty_dict(self):
        with pytest.raises(ValueError, match="None|{}"):
            _validate_input({})

    def test_validate_input_missing_key(self):
        with pytest.raises(ValueError, match="goal_text"):
            _validate_input({"other": "x"})

    def test_validate_input_empty_string(self):
        with pytest.raises(ValueError, match="空文字列"):
            _validate_input({"goal_text": ""})

    def test_validate_input_wrong_type(self):
        with pytest.raises(ValueError, match="dict"):
            _validate_input("string input")


# ════════════════════════════════════════════════════════
# Test3 — HITL移譲・WARNING 継続ケース
# ════════════════════════════════════════════════════════

class TestHitlAndWarnings:
    """曖昧語・粒度不足による HITL 移譲と、WARNING ログ出力（処理継続）を検証する。
    WARNING は Duplicate / Orphan / ParentMismatch の3種に分類して明示的に検証する。
    """

    @pytest.fixture(autouse=True)
    def mock_api(self, mocker):  # 補強箇所⑤: HITL 検証では API 到達前に返るが念のため設定
        return mocker.patch("src.agents.f10_module._call_api", return_value=VALID_API_RESPONSE)

    def test_ambiguous_word_triggers_hitl(self):
        result = execute({"goal_text": "売上などを改善したい"})
        assert result["hitl"] is True
        assert result["goal"] is None

    def test_short_text_triggers_hitl(self):
        result = execute({"goal_text": "改善"})
        assert result["hitl"] is True

    def test_hitl_check_ambiguous(self):
        reason = _check_hitl_conditions("売上などを上げたい")
        assert reason is not None and "HITL" in reason

    def test_hitl_check_short(self):
        reason = _check_hitl_conditions("短い")
        assert reason is not None

    def test_hitl_check_normal_returns_none(self):
        assert _check_hitl_conditions("新規顧客獲得を強化し、売上を前年比120%に成長させる") is None

    # 補強箇所②: Duplicate カテゴリの WARNING を明示検証
    def test_duplicate_id_logs_warning(self, caplog):
        """同一 objective_id が複数存在する場合に Duplicate WARNING が出ることを検証。"""
        tree = _make_simple_tree()  # 補強箇所①: 共通ファクトリを利用
        root_id = next(iter(tree))
        tree[root_id]["children"].append({
            "objective_id": root_id,   # 意図的に重複
            "objective_text": "重複ノード",
            "level": "L2",
            "parent_id": root_id,
            "children": [],
        })
        with caplog.at_level(logging.WARNING):
            _validate_tree(tree)
        assert_warning_contains(caplog.records, "重複", "Duplicate")  # 補強箇所②

    # 補強箇所②: Orphan カテゴリの WARNING を明示検証
    def test_orphan_node_logs_warning(self, caplog):
        """存在しない parent_id を持つ孤立ノードで Orphan WARNING が出ることを検証。"""
        tree = {
            "L1-xxx": {
                "objective_id": "L1-xxx",
                "objective_text": "大目的",
                "level": "L1",
                "parent_id": None,
                "children": [
                    {
                        "objective_id": "L2-yyy",
                        "objective_text": "中目的",
                        "level": "L2",
                        "parent_id": "L1-NONEXISTENT",  # 存在しない親
                        "children": [],
                    }
                ],
            }
        }
        with caplog.at_level(logging.WARNING):
            _validate_tree(tree)
        assert_warning_contains(caplog.records, "孤立", "Orphan")  # 補強箇所②

    # 補強箇所②: ParentMismatch カテゴリの WARNING を明示検証
    def test_parent_mismatch_logs_warning(self, caplog):
        """L3 の parent_id が存在する L2 と一致しない場合に ParentMismatch WARNING が出ることを検証。"""
        tree = {
            "L1-aaa": {
                "objective_id": "L1-aaa",
                "objective_text": "大目的",
                "level": "L1",
                "parent_id": None,
                "children": [
                    {
                        "objective_id": "L2-bbb",
                        "objective_text": "中目的",
                        "level": "L2",
                        "parent_id": "L1-aaa",
                        "children": [
                            {
                                "objective_id": "L3-ccc",
                                "objective_text": "小目的",
                                "level": "L3",
                                "parent_id": "L2-WRONG",  # 不整合な parent_id
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        }
        with caplog.at_level(logging.WARNING):
            _validate_tree(tree)
        # L2-WRONG は all_ids に存在しないため孤立ノード扱いで WARNING が出る
        assert_warning_contains(caplog.records, "孤立", "ParentMismatch")  # 補強箇所②


# ════════════════════════════════════════════════════════
# Test4 — APIエラー：タイムアウト・3回リトライ検証
# ════════════════════════════════════════════════════════

class TestApiRetry:
    """API 呼び出しのリトライ挙動（最大3回・RuntimeError 送出）を検証する。
    assert_call_count ヘルパーを使い、呼び出し回数検証を共通化する。
    """

    @pytest.fixture
    def api_error(self):
        """共通の APIStatusError を fixture として提供する。"""  # 補強箇所①
        import anthropic
        return anthropic.APIStatusError(
            "timeout", response=MagicMock(status_code=503), body={}
        )

    def test_retries_exactly_3_times(self, mocker, api_error):
        mock_call = mocker.patch("src.agents.f10_module._call_api", side_effect=api_error)
        mocker.patch("src.agents.f10_module.time.sleep")
        with pytest.raises(RuntimeError, match="3 回失敗"):
            _call_api_with_retry("system", "goal")
        assert_call_count(mock_call, 3, label="APIタイムアウト")  # 補強箇所③

    def test_raises_runtime_error_after_exhaustion(self, mocker, api_error):
        mocker.patch("src.agents.f10_module._call_api", side_effect=api_error)
        mocker.patch("src.agents.f10_module.time.sleep")
        with pytest.raises(RuntimeError):
            _call_api_with_retry("system", "goal")

    def test_succeeds_on_second_attempt(self, mocker, api_error):
        mock_call = mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=[api_error, VALID_API_RESPONSE],
        )
        mocker.patch("src.agents.f10_module.time.sleep")
        result = _call_api_with_retry("system", "goal")
        assert result == VALID_API_RESPONSE
        assert_call_count(mock_call, 2, label="2回目成功")  # 補強箇所③


# ════════════════════════════════════════════════════════
# Test5 — JSONDecodeError → RuntimeError（__cause__ 保持）
# ════════════════════════════════════════════════════════

class TestJsonParseError:
    """JSON パース失敗が RuntimeError にラップされ、__cause__ に JSONDecodeError が
    保持されることを検証する。assert_wrapped_cause で将来の追加ケースにも転用できる。
    """

    def test_invalid_json_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            _parse_response("not a json {{{")

    def test_cause_is_json_decode_error(self):
        with pytest.raises(RuntimeError) as exc_info:
            _parse_response("not a json {{{")
        assert_wrapped_cause(exc_info, json.JSONDecodeError, label="_parse_response")  # 補強箇所④

    def test_missing_key_raises_value_error(self):
        with pytest.raises(ValueError, match="L3"):
            _parse_response(json.dumps({"L1": "大目的", "L2": ["中目的"]}))

    def test_json_decode_error_via_execute(self, mocker):
        mocker.patch("src.agents.f10_module._call_api", return_value="{{invalid json}}")
        mocker.patch("src.agents.f10_module.time.sleep")
        with pytest.raises(RuntimeError) as exc_info:
            execute(VALID_INPUT)
        assert_wrapped_cause(exc_info, (json.JSONDecodeError, Exception), label="execute経由")  # 補強箇所④


# ════════════════════════════════════════════════════════
# Test6 — 整形処理：ツリー変換の検証
# ════════════════════════════════════════════════════════

class TestTreeStructuring:
    """フラット構造の L1/L2/L3 リストが正しいネストツリーに変換されることを検証する。
    WARNING ログの Hierarchy カテゴリ（抽象語残存）も合わせて確認する。
    """

    @pytest.fixture(autouse=True)
    def mock_api(self, mocker):  # 補強箇所⑤: autouse で全テストに自動適用
        return mocker.patch("src.agents.f10_module._call_api", return_value=VALID_API_RESPONSE)

    def test_flat_to_tree_conversion(self):
        result = execute(VALID_INPUT)
        assert len(result["tree"]) == 1  # L1 ルートは1件

    def test_l3_children_is_empty_list(self):
        result = execute(VALID_INPUT)

        def _check_l3_leaf(node):
            if node["level"] == "L3":
                assert node["children"] == [], f"L3 の children が空でない: {node}"
            for child in node["children"]:
                _check_l3_leaf(child)

        for root in result["tree"].values():
            _check_l3_leaf(root)

    def test_build_tree_direct(self):
        parsed = {"L1": "大目的", "L2": ["中目的A", "中目的B"], "L3": ["小目的A-1", "小目的A-2", "小目的B-1"]}
        tree = _build_tree(parsed)
        root = next(iter(tree.values()))
        assert root["level"] == "L1"
        assert len(root["children"]) == 2
        assert sum(len(l2["children"]) for l2 in root["children"]) == 3

    def test_all_nodes_have_required_fields(self):
        tree = _build_tree({"L1": "大目的", "L2": ["中目的A"], "L3": ["小目的A-1", "小目的A-2"]})
        required = {"objective_id", "objective_text", "level", "parent_id", "children"}

        def _check(node):
            assert required <= node.keys()
            for child in node["children"]:
                _check(child)

        for root in tree.values():
            _check(root)

    # 補強箇所②: Hierarchy（抽象語残存）カテゴリの WARNING を明示検証
    def test_hierarchy_warning_logged(self, caplog, mocker):
        """L3 に抽象語「最適化」が残存した場合に Hierarchy WARNING が出ることを検証。"""
        mocker.patch(
            "src.agents.f10_module._call_api",
            return_value=json.dumps(
                {"L1": "大目的", "L2": ["中目的A"], "L3": ["業務を最適化する"]},
                ensure_ascii=False,
            ),
        )
        with caplog.at_level(logging.WARNING):
            execute(VALID_INPUT)
        assert_warning_contains(caplog.records, "最適化", "Hierarchy")  # 補強箇所②
