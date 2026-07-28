# F20 目的展開モジュール仕様

## 1. Module（概要）

- **Module Name:** F20_Goal_Expansion_Module
- **Purpose（目的）:** F10 の出力（goal.L1/L2/L3）を受け取り、目的を要素単位に展開・分解する
- **Responsibility（責務）:** L1/L2/L3 の目的文をトークン化し、element_id 付きの展開要素リストを生成して後続モジュールへ引き渡す
- **Traceability ID:** WP7100 / WP7200
- **前提モジュール:** F10_Objective_Structuring_Module

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F10 の出力（goal.L1/L2/L3 と trace_id）を含む dict
- **必須項目:** `goal.L1`（str）、`goal.L2`（list[str]）、`goal.L3`（list[str]）、`trace_id`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `goal` キーが存在しない場合は `ValueError`
  - `goal.L1/L2/L3` が存在しない場合は `ValueError`
  - `goal.L1` が空文字列の場合は HITL 移譲
  - `trace_id` が `"F10"` であることを推奨（警告のみ、強制はしない）

```python
# 正常な入力例（F10 の出力をそのまま渡す）
input_data = {
    "goal": {
        "L1": "売上を前年比120%に成長させる",
        "L2": ["新規顧客獲得施策を推進する", "既存顧客リテンションを強化する"],
        "L3": ["LPを作成する", "広告配信を開始する", "フォローアップメールを設計する"]
    },
    "trace_id": "F10"
}
```

### Output

- **出力データの構造:** 展開済み目的要素リストとトレース情報
- **必須項目:** `expanded_goals`（list）、`trace_id`
- **型（Type）:** `dict`
- **各要素の構造:** `element_id`（"E1"〜）、`text`（展開テキスト）、`parent`（"L1"/"L2"/"L3"）

```python
# 出力例
output_data = {
    "trace_id": "F20",
    "source_trace_id": "F10",
    "expanded_goals": [
        {"element_id": "E1", "text": "売上を前年比120%に成長させる", "parent": "L1"},
        {"element_id": "E2", "text": "新規顧客獲得施策を推進する",   "parent": "L2"},
        {"element_id": "E3", "text": "既存顧客リテンションを強化する", "parent": "L2"},
        {"element_id": "E4", "text": "LPを作成する",                "parent": "L3"},
        {"element_id": "E5", "text": "広告配信を開始する",           "parent": "L3"},
        {"element_id": "E6", "text": "フォローアップメールを設計する", "parent": "L3"},
    ],
    "hitl": False
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F20 モジュールの統一インターフェース。

    F10 の出力（goal.L1/L2/L3）を受け取り、
    element_id 付きの展開要素リストを返す。

    Args:
        input_data (dict): F10 の出力形式（goal.L1/L2/L3 + trace_id）

    Returns:
        dict: {
            "trace_id": "F20",
            "source_trace_id": str,
            "expanded_goals": list[dict],
            "hitl": bool
        }

    Raises:
        TypeError:    input_data が dict 以外
        ValueError:   goal / goal.L1/L2/L3 の欠落
        RuntimeError: トークン化処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が `None` または `{}` → `ValueError`
  - `"goal"` キーが存在しない → `ValueError`
  - `goal.L1` が str でない、または `goal.L2` / `goal.L3` が list でない → `ValueError`

- **Step2 — HITL 移譲判定**
  - `goal.L1` が空文字列 → HITL 移譲（reason: "Goal text is empty"）
  - `goal.L1` に曖昧語（「など」「いろいろ」「何か」）が含まれる → HITL 移譲

- **Step3 — 前処理**
  - `trace_id` が `"F10"` 以外の場合は WARNING ログを出力（処理継続）
  - L2 / L3 リストの各要素の空文字列・重複を検出し WARNING ログ出力（処理継続）

- **Step4 — トークン化・展開**
  - L1 文字列を1要素として展開（`parent="L1"`）
  - L2 リストの各要素を展開（`parent="L2"`）
  - L3 リストの各要素を展開（`parent="L3"`）
  - 各要素に連番 `element_id`（"E1", "E2", ...）を付与
  - トークン化処理が失敗した場合は `RuntimeError`（`__cause__` に元の例外を保持）

- **Step5 — 整合性検証**
  - `element_id` の重複を検出 → WARNING ログ出力（処理継続）
  - `parent` 値が "L1"/"L2"/"L3" 以外のノードを検出 → WARNING ログ出力（処理継続）

- **Step6 — 保存・返却**
  - 結果を `data/output/f20_result_{timestamp}.json` に UTF-8 で保存
  - 処理日時・展開要素数を INFO ログに記録（WP3300 準拠）
  - `output_data` として呼び出し元へ返却

- **例外処理:** 各 Step で発生した例外はログ記録後に上位へ送出
- **フェイルセーフ:** RuntimeError 発生時は部分結果を `data/output/` に保存してから送出

---

## 4. Error Handling（例外処理）

| 例外 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外 | 即時送出、ログ記録 |
| `ValueError` | `None` / `{}` / 必須フィールド欠落 / L1/L2/L3 型不正 | 即時送出、ログ記録 |
| HITL 移譲 | `goal.L1` が空文字列・曖昧語 | WARNING ログ＋`hitl: True` で返却 |
| `RuntimeError` | トークン化処理失敗 | `__cause__` に元の例外を保持して送出 |
| WARNING（処理継続） | 重複 element_id / 親子不整合 / 空文字列要素 / 不明 trace_id | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f20_module.py` / 実行: `pytest tests/test_f20_module.py -v`（WP5100準拠）

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | L1/L2/L3 の展開・element_id 付与・parent 対応 |
| Test2 | 異常系 | None・{}・空文字・型不正・フィールド欠落 |
| Test3 | HITL移譲 | 空文字・曖昧語での hitl:True 返却 |
| Test4 | トークン化失敗 | RuntimeError・`__cause__` 保持 |
| Test5 | WARNING継続 | 重複要素・親子不整合の WARNING ログ |
| Test6 | trace_id | 出力の `trace_id=="F20"` 確認 |
