# F50 テンプレ適用モジュール仕様

## 1. Module（概要）

- **Module Name:** F50_Template_Application_Module
- **Purpose（目的）:** F40 の tasks を受け取り、priority に応じた標準テンプレートを適用し、統一されたタスク文書（templated_tasks）を生成する
- **Responsibility（責務）:** 各タスクのテンプレート選択・文字列展開・HITL 判定・整合性検証を行い、後続モジュールへ引き渡す
- **Traceability ID:** WP7300
- **前提モジュール:** F40_Task_Generation_Module
- **参照仕様:** `docs/F_series_overview.md`, `docs/F40_Module.md`

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F40 の出力（tasks + trace_id）を含む dict
- **必須項目:** `tasks`（list）、各要素の `task_id` / `task_text` / `priority`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `tasks` キーが存在しない場合は `ValueError`
  - 各要素に必須フィールドが欠落している場合は `TypeError`
  - `priority` が "High"/"Medium"/"Low" 以外の場合は WARNING ログ出力（処理継続）
  - 重複 `task_id` → WARNING ログ出力（処理継続）

```python
# 正常な入力例（F40 の出力をそのまま渡す）
input_data = {
    "trace_id": "F40",
    "tasks": [
        {
            "task_id": "T1",
            "element_id": "E1",
            "task_text": "【即実行】売上を前年比120%に成長させる",
            "priority": "High",
            "estimated_effort": 3,
            "estimated_value": 5
        }
    ]
}
```

### Output

- **出力データの構造:** テンプレート適用済みタスクリストとトレース情報
- **必須項目:** `templated_tasks`（list）、`trace_id`
- **型（Type）:** `dict`
- **各タスクの構造:**
  - `task_id`: 入力の task_id を引き継ぐ
  - `template_id`: "TMP_HIGH" / "TMP_MEDIUM" / "TMP_LOW"
  - `templated_text`: テンプレート展開済みのタスク文
  - `priority`: "High" / "Medium" / "Low"
  - `effort`: estimated_effort をそのまま引き継ぐ
  - `value`: estimated_value をそのまま引き継ぐ

```python
# 出力例
output_data = {
    "trace_id": "F50",
    "source_trace_id": "F40",
    "templated_tasks": [
        {
            "task_id": "T1",
            "template_id": "TMP_HIGH",
            "templated_text": "【優先度: 高】次のタスクを実行せよ: 【即実行】売上を前年比120%に成長させる",
            "priority": "High",
            "effort": 3,
            "value": 5
        }
    ],
    "hitl": False,
    "hitl_elements": []
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F50 モジュールの統一インターフェース。

    Args:
        input_data (dict): F40 の出力形式（tasks + trace_id）

    Returns:
        dict: {
            "trace_id": "F50",
            "source_trace_id": str,
            "templated_tasks": list[dict],
            "hitl": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または各要素の必須フィールド欠落
        ValueError:   tasks の欠落・型不正
        RuntimeError: テンプレート適用処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が空 `{}` → `ValueError`
  - `"tasks"` キーが存在しない → `ValueError`
  - `tasks` が list 以外 → `ValueError`
  - 各要素に `task_id` / `task_text` / `priority` が存在しない → `TypeError`

- **Step2 — 前処理**
  - `trace_id` が `"F40"` 以外の場合は WARNING ログ出力（処理継続）
  - `tasks` が空リストの場合は WARNING ログ出力し、空の templated_tasks を返す
  - 重複 `task_id` を検出し WARNING ログ出力（処理継続）
  - `priority` が "High"/"Medium"/"Low" 以外の場合は WARNING ログ出力（処理継続）

- **Step3 — HITL 移譲判定（要素単位）**
  - `task_text` が空文字列または空白のみ → `hitl_elements` に追加してスキップ
  - `task_text` に曖昧語（「など」「いろいろ」「何か」「改善」「向上」「検討」）を含む → `hitl_elements` に追加してスキップ
  - `priority` が判定不能（"High"/"Medium"/"Low" 以外）→ `hitl_elements` に追加してスキップ
  - すべての要素が HITL 移譲対象の場合 → `hitl: True` で返却

- **Step4 — テンプレート適用**
  - **テンプレート選択（priority 別）:**
    - `"High"`   → `template_id = "TMP_HIGH"`,   `templated_text = "【優先度: 高】次のタスクを実行せよ: {task_text}"`
    - `"Medium"` → `template_id = "TMP_MEDIUM"`, `templated_text = "【優先度: 中】検討すべきタスク: {task_text}"`
    - `"Low"`    → `template_id = "TMP_LOW"`,    `templated_text = "【優先度: 低】参考タスク: {task_text}"`
  - `estimated_effort` → `effort`、`estimated_value` → `value` としてそのまま引き継ぐ（存在しない場合は None）
  - テンプレート適用中に例外が発生した場合は `RuntimeError`（`__cause__` に元の例外を保持）

- **Step5 — 整合性検証**
  - `template_id` が想定外の値 → WARNING ログ出力（処理継続）
  - `templated_text` が空文字列 → WARNING ログ出力（処理継続）

- **Step6 — 保存・返却**
  - 結果を `data/output/f50_result_{timestamp}.json` に UTF-8 で保存
  - 処理日時・生成タスク数・HITL 移譲数を INFO ログに記録（WP3300 準拠）
  - `output_data` として呼び出し元へ返却

---

## 4. Error Handling（例外処理）

`docs/F_series_overview.md` の Error Handling ルールを継承し、以下を追加：

| 例外 / 状態 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外、または各要素の必須フィールド欠落 | 即時送出 |
| `ValueError` | 空 dict / `tasks` 欠落・型不正 | 即時送出 |
| HITL 移譲（要素単位） | `task_text` 空文字列・曖昧語・priority 判定不能 | `hitl_elements` に記録してスキップ |
| HITL 移譲（全体） | 全要素が HITL 対象 | `hitl: True` で返却 |
| `RuntimeError` | テンプレート適用ロジック失敗 | `__cause__` に元の例外を保持して送出 |
| WARNING（処理継続） | 重複 task_id / 不正 priority / 不明 trace_id / 空 templated_text | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f50_module.py` / 実行: `pytest tests/test_f50_module.py -v`

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | テンプレート適用・template_id・templated_text・effort/value 引き継ぎ |
| Test2 | 異常系 | TypeError（dict 以外・フィールド欠落）/ ValueError（tasks 欠落・型不正）の分離 |
| Test3 | HITL移譲 | 空文字・曖昧語・priority 不明・全体/部分 HITL・hitl_elements |
| Test4 | RuntimeError | テンプレート適用失敗・`__cause__` 保持 |
| Test5 | WARNING継続 | 重複 task_id・不正 priority・不明 trace_id・空 templated_text |
| Test6 | trace_id | "F50" 固定・source_trace_id・F10→F20→F30→F40→F50 パイプライン統合 |
