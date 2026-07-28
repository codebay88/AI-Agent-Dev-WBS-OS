# F10 目的構造化モジュール仕様

## 1. Module（概要）

- **Module Name:** F10_Objective_Structuring_Module
- **Purpose（目的）:** 自然言語で記述された目的文を受け取り、L1/L2/L3 の階層構造に分解・構造化する
- **Responsibility（責務）:** 入力された目的文を解析し、階層的に整合した目的ツリーを生成して後続モジュールへ引き渡す
- **Traceability ID:** WP7000 / WP7100 / WP7200

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** 目的文を含む dict 形式のデータ
- **必須項目:** `goal_text`（目的文）
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（`None` および空 `{}` は `ValueError`）
  - `goal_text` は空文字列不可（`ValueError`）
  - 以下の条件を満たす場合は処理を中断し HITL へ移譲する：
    - **曖昧語判定:** 「など」「いろいろ」「何か」等の不確定表現が含まれ、構造化が困難と判断された場合
    - **粒度不足判定:** 目的文が抽象的すぎて L2/L3 への分解が不可能と判断された場合

```python
# 正常な入力例
input_data = {
    "goal_text": "新規顧客獲得を強化し、売上を前年比120%に成長させる"
}
```

### Output

- **出力データの構造:** 構造化済み目的階層と処理トレース情報
- **必須項目:** `goal`（L1/L2/L3 の階層構造）、`trace_id`
- **型（Type）:** `dict`
- **粒度（L1/L2/L3）:** L1=大目的（全体方針）、L2=中目的（施策単位）、L3=小目的（タスク単位）

```python
# 出力例
output_data = {
    "trace_id": "F10",
    "goal": {
        "L1": "売上を前年比120%に成長させる",
        "L2": ["新規顧客獲得施策を推進する", "既存顧客のリテンションを強化する"],
        "L3": ["LP を作成する", "広告配信を開始する", "フォローアップメールを設計する"]
    }
}
```

> **注意:** `goal` の内部ツリー構造（`parent_id` / `children` の付与）は Logic セクション（Step4・Step7）で処理する。Interface では入出力の外形のみを定義する。

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F10 モジュールの統一インターフェース

    目的文（goal_text）を受け取り、L1/L2/L3 に構造化した
    目的階層と trace_id を返す。

    Args:
        input_data (dict): {"goal_text": str}

    Returns:
        dict: {
            "trace_id": "F10",
            "goal": {
                "L1": str,
                "L2": list[str],
                "L3": list[str]
            }
        }

    Raises:
        ValueError: input_data が None / {} / goal_text が空文字列
        RuntimeError: API 呼び出しが3回失敗、または JSON パース失敗
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が `None` または空 `{}` の場合、`ValueError("input_data は dict 形式必須")` を送出
  - `goal_text` キーが存在しない、または空文字列の場合、`ValueError("goal_text は必須かつ空文字列不可")` を送出

- **Step2 — HITL移譲判定**
  - `goal_text` に曖昧語（「など」「いろいろ」「何か」等）が含まれる場合、WARNING ログを出力して処理を中断し HITL へ移譲
  - 粒度不足（単語1語・極端に短い文等）と判定された場合も同様に HITL へ移譲

- **Step3 — プロンプト生成**
  - `src/prompts/f10_system.txt`（WP7000 目的構造化プロンプト）を読み込む
  - `goal_text` を埋め込み、Claude API へ渡すリクエストテキストを生成
  - プロンプトファイルが存在しない場合は `FileNotFoundError` を送出

- **Step4 — API呼出・パース・ツリー構築**
  - `anthropic.Anthropic` クライアントで `messages.create()` を呼び出す
  - レスポンスを `json.loads()` で解析し、`L1` / `L2` / `L3` キーの存在を確認
  - `L2` の各項目を L1 に従属、`L3` の各項目を対応する `L2` に従属させ、`parent_id` と `children` を付与したツリー構造を生成
  - API エラー・JSON パースエラーは Step5（リトライ）へ移行

- **Step5 — 整合性検証**
  - L2 の各ノードの `parent_id` が L1 の ID と一致するか確認
  - L3 の各ノードの `parent_id` が L2 の ID と一致するか確認
  - 重複 `objective_id`・親子不整合・孤立ノードが存在する場合は WARNING ログを出力し処理継続

- **Step6 — リトライ処理**
  - `anthropic.APIError` または `json.JSONDecodeError` 発生時、指数バックオフ（1秒→2秒）で最大 **3回**（初回＋再試行2回）実行
  - 3回すべて失敗した場合は `RuntimeError("API呼び出しが3回失敗")` を送出
  - `JSONDecodeError` は `RuntimeError` にラップし、`__cause__` に元の例外を保持する

- **Step7 — 整形・返却**
  - 構造化済みデータを出力形式（`trace_id="F10"`、`goal.L1/L2/L3`）に整形
  - `data/output/f10_result_{timestamp}.json` に UTF-8 で保存
  - 処理日時・入力文字数・L1/L2/L3 件数を INFO ログに記録（WP3300 準拠）
  - `output_data` として呼び出し元へ返却

- **例外処理:** 各 Step で発生した例外はログ記録後に上位へ送出。HITL 移譲が必要な場合は移譲理由を WARNING ログに明記
- **フェイルセーフ:** Step6 リトライ上限到達時は、それまでの部分結果を `data/output/` に保存してから `RuntimeError` を送出

---

## 4. Error Handling（例外処理）

| 例外 | 発生条件 | 処理 |
|---|---|---|
| `ValueError` | `input_data` が `None` / `{}` / `goal_text` が空文字列 | 即時送出、ログ記録 |
| `FileNotFoundError` | プロンプトファイルが存在しない | 即時送出、ログ記録 |
| `anthropic.APIError` | API接続エラー・タイムアウト | 最大3回リトライ（初回＋再試行2回）→ `RuntimeError` |
| `json.JSONDecodeError` | API応答が不正 JSON | `RuntimeError` にラップ（`__cause__` に保持）、最大3回リトライ後に送出 |
| `RuntimeError` | 3回リトライ失敗 / JSON パース失敗のラップ | 上位へ送出、部分結果を保存 |
| WARNING（処理継続） | 重複 `objective_id` / 階層矛盾 / 親子不整合 / 孤立ノード | WARNING ログ出力、処理継続 |

- **リトライ条件:** `anthropic.APIError` / `json.JSONDecodeError` の発生時。最大3回（初回＋再試行2回）、指数バックオフ（1秒→2秒）
- **HITL移譲条件:** 曖昧語・粒度不足判定時、またはリトライ上限到達時

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f10_module.py` / 実行: `pytest tests/test_f10_module.py -v`（WP5100準拠）

---

### Test1 — 正常系：階層構造化の検証

- **入力:** 正しい `goal_text` を含む dict
- **確認内容:**
  - `execute()` がエラーなく `dict` を返すこと
  - `trace_id` が `"F10"` であること
  - `goal.L1` が `str`、`goal.L2` / `goal.L3` が `list[str]` であること
  - `parent_id` と `children` が正しく付与されていること

```python
def test_normal_structuring():
    input_data = {"goal_text": "新規顧客獲得を強化し、売上を前年比120%に成長させる"}
    result = execute(input_data)
    assert result["trace_id"] == "F10"
    assert isinstance(result["goal"]["L1"], str)
    assert isinstance(result["goal"]["L2"], list)
    assert isinstance(result["goal"]["L3"], list)
```

---

### Test2 — 異常系：空入力・型不正・必須項目欠落

- **ケース A:** `input_data` が `None` → `ValueError`
- **ケース B:** `input_data` が `{}` → `ValueError`
- **ケース C:** `goal_text` が空文字列 `""` → `ValueError`
- **ケース D:** `goal_text` キーが存在しない → `ValueError`
- **ケース E:** `input_data` が `str` 型（dict 以外）→ `ValueError`

```python
@pytest.mark.parametrize("bad_input", [
    None,
    {},
    {"goal_text": ""},
    {"other_key": "value"},
    "not a dict",
])
def test_invalid_input(bad_input):
    with pytest.raises(ValueError):
        execute(bad_input)
```

---

### Test3 — 異常系：階層不整合・重複・親子不整合の WARNING

- **ケース A:** 重複した `objective_id` が存在する → WARNING ログ出力、処理継続
- **ケース B:** L3 が対応する L2 を持たない（孤立ノード）→ WARNING ログ出力、処理継続
- **ケース C:** L2 が対応する L1 を持たない（親子不整合）→ WARNING ログ出力、処理継続
- **確認内容:** いずれも `ValueError` / `RuntimeError` を送出せず、WARNING ログが記録されること

```python
def test_duplicate_id_warning(caplog):
    # 重複 ID を含む入力をモックで返す想定
    with caplog.at_level(logging.WARNING):
        execute({"goal_text": "重複IDを含む目的文"})
    assert any("重複" in r.message or "duplicate" in r.message.lower() for r in caplog.records)
```

---

### Test4 — APIエラー：タイムアウト・3回リトライ検証

- **前提:** `anthropic.Anthropic.messages.create` を `mocker.patch` で `anthropic.APIError` を送出するよう設定
- **確認内容:**
  - `messages.create` がちょうど **3回** 呼び出されること
  - 3回失敗後に `RuntimeError` が送出されること

```python
def test_api_retry_exhausted(mocker):
    mock_create = mocker.patch(
        "anthropic.resources.messages.Messages.create",
        side_effect=anthropic.APIError("timeout")
    )
    with pytest.raises(RuntimeError):
        execute({"goal_text": "売上を拡大する"})
    assert mock_create.call_count == 3
```

---

### Test5 — JSONパースエラー：RuntimeError へのラップ検証

- **前提:** `messages.create` をモック化し、不正な JSON 文字列（例: `"not a json {{{"` ）を返すよう設定
- **確認内容:**
  - `RuntimeError` が送出されること
  - `RuntimeError.__cause__` が `json.JSONDecodeError` であること

```python
def test_json_decode_error_wrapped(mocker):
    mock_response = mocker.MagicMock()
    mock_response.content[0].text = "not a json {{{"
    mocker.patch(
        "anthropic.resources.messages.Messages.create",
        return_value=mock_response
    )
    with pytest.raises(RuntimeError) as exc_info:
        execute({"goal_text": "売上を拡大する"})
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)
```

---

### Test6 — 整形処理：ツリー変換の検証

- **入力:** L1×1・L2×2・L3×3 の正しい目的リストが API から返される想定（モック）
- **確認内容:**
  - 出力が `children` ネスト構造になっていること
  - L1 → L2 → L3 の順で正しくネストされていること
  - 末端ノード（L3）の `children` が空リスト `[]` であること
  - 全ノードに `objective_id`・`objective_text`・`level`・`parent_id`・`children` が存在すること

```python
def test_tree_nesting(mocker):
    # API が正常な構造化結果を返すモック
    mock_response = mocker.MagicMock()
    mock_response.content[0].text = json.dumps({
        "L1": "大目的",
        "L2": ["中目的A", "中目的B"],
        "L3": ["小目的A-1", "小目的A-2", "小目的B-1"]
    })
    mocker.patch("anthropic.resources.messages.Messages.create", return_value=mock_response)

    result = execute({"goal_text": "大目的を達成する"})
    assert result["trace_id"] == "F10"
    assert len(result["goal"]["L2"]) == 2
    assert len(result["goal"]["L3"]) == 3
```
