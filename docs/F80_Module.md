# F80 トレーサビリティ生成モジュール仕様

## 1. Module（概要）

- **Module Name:** F80_Traceability_Generation_Module
- **Purpose（目的）:** F70 の hierarchy を受け取り、各 goal・element・task に F10〜F70 の trace_chain を付与してトレーサビリティマップを生成する
- **Responsibility（責務）:** trace_chain 構築・完全性検証・循環依存 Union-Find 検出・HITL 判定を行い、後続モジュールへ引き渡す
- **Traceability ID:** WP7600
- **前提モジュール:** F70_Hierarchy_Generation_Module
- **参照仕様:** `docs/F_series_overview.md`, `docs/F70_Module.md`
- **外部ライブラリ:** なし（stdlib のみ）

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F70 の出力（hierarchy + trace_id）を含む dict
- **必須項目:** `hierarchy`（dict）、`hierarchy.goals`（list）
- **各 goal の必須項目:** `goal_id`、`elements`（list）
- **各 element の必須項目:** `element_id`、`tasks`（list）
- **各 task の必須項目:** `task_id`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `hierarchy` キーが存在しない場合は `ValueError`
  - 必須フィールド欠落 → `TypeError`

```python
# 正常な入力例（F70 の出力をそのまま渡す）
input_data = {
    "trace_id": "F70",
    "source_trace_id": "F60",
    "hierarchy": {
        "goals": [
            {
                "goal_id": "G1",
                "goal_text": "LPを作成する",
                "elements": [
                    {
                        "element_id": "G1_EL_H",
                        "element_text": "High優先度タスク群",
                        "tasks": [
                            {
                                "task_id": "T1",
                                "templated_text": "【優先度: 高】次のタスクを実行せよ: LPを作成する",
                                "priority": "High",
                                "effort": 3,
                                "value": 5
                            }
                        ]
                    }
                ]
            }
        ]
    }
}
```

### Output

- **出力データの構造:** トレーサビリティマップとトレース情報
- **必須項目:** `traceability_map`（list）、`trace_id`
- **型（Type）:** `dict`
- **各エントリの構造:**
  - `goal_id`: 所属 goal の ID
  - `element_id`: 所属 element の ID
  - `task_id`: タスクの ID
  - `trace_chain`: `["F10", "F20", "F30", "F40", "F50", "F60", "F70"]`（source_trace_id 解決済み）
  - `origin_module`: chain の最初のモジュール（通常 "F10"）
  - `latest_module`: chain の最後のモジュール
  - `is_complete`: F10〜F70 がすべて chain に含まれる場合 `true`

```python
# 出力例
output_data = {
    "trace_id": "F80",
    "source_trace_id": "F70",
    "traceability_map": [
        {
            "goal_id":       "G1",
            "element_id":    "G1_EL_H",
            "task_id":       "T1",
            "trace_chain":   ["F10", "F20", "F30", "F40", "F50", "F60", "F70"],
            "origin_module": "F10",
            "latest_module": "F70",
            "is_complete":   True
        }
    ],
    "hitl":          False,
    "hitl_required": False,
    "hitl_elements": []
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F80 モジュールの統一インターフェース。

    Returns:
        dict: {
            "trace_id": "F80",
            "source_trace_id": str,
            "traceability_map": list[dict],
            "hitl": bool,
            "hitl_required": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または必須フィールド欠落
        ValueError:   hierarchy の欠落・型不正
        RuntimeError: trace_chain 構築処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が空 `{}` → `ValueError`
  - `"hierarchy"` キーが存在しない → `ValueError`
  - `hierarchy` が dict 以外 → `ValueError`
  - `hierarchy.goals` が list 以外 → `ValueError`
  - goal に `goal_id` または `elements` が欠落 → `TypeError`
  - element に `element_id` または `tasks` が欠落 → `TypeError`
  - task に `task_id` が欠落 → `TypeError`

- **Step2 — 前処理**
  - `trace_id` が `"F70"` 以外 → WARNING ログ出力（処理継続）
  - `goals` が空リスト → HITL 移譲（`hitl_required: true, hitl_reason: "No hierarchy provided"`）
  - 重複 `task_id`（全 goal を横断）→ WARNING ログ出力（処理継続）

- **Step3 — trace_chain 構築**
  - `PIPELINE_ORDER = ["F10","F20","F30","F40","F50","F60","F70"]`
  - `source_trace_id`（input の trace_id）から chain を構築
    - `source_trace_id` が `PIPELINE_ORDER` に含まれる場合: `PIPELINE_ORDER[:idx+1]`
    - 含まれない場合: 空リスト → HITL 移譲（`hitl_reason: "Trace chain missing"`）
  - 各タスクに対してエントリを生成
  - chain が空のタスク → `hitl_elements` に `task_id` を追加

- **Step4 — 完全性チェック**
  - chain に F10〜F70 がすべて含まれる → `is_complete = True`
  - 欠落がある → `is_complete = False`、`hitl_elements` に `task_id` を追加

- **Step5 — origin_module / latest_module 判定**
  - `origin_module = chain[0]`（通常 "F10"）
  - `latest_module = chain[-1]`（通常 "F70"）
  - `origin_module != "F10"` → WARNING ログ + `hitl_elements` に追加

- **Step6 — 循環依存 Union-Find 検出**
  - 全 goal の全 element を走査し、task_id → element_id のマッピングを作成
  - 同一 `task_id` が複数の `element_id` に存在 → 循環依存と判定
  - 検出された task_id を `hitl_elements` に追加し WARNING ログ出力

- **Step7 — HITL 判定・保存・返却**
  - `hitl_elements` が存在 → `hitl_required = True`
  - 結果を `data/output/f80_result_{timestamp}.json` に UTF-8 で保存
  - INFO ログに chain 数・HITL 数を記録

---

## 4. Error Handling（例外処理）

| 例外 / 状態 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外 / 必須フィールド欠落 | 即時送出 |
| `ValueError` | 空 dict / `hierarchy` 欠落・型不正 / `goals` 型不正 | 即時送出 |
| HITL 移譲（空） | `goals` が空、または chain が空 | `hitl_required: True` |
| HITL 移譲（不完全） | `is_complete = False` | `hitl_elements` に task_id 追加 |
| HITL 移譲（循環） | task_id が複数 element に存在 | `hitl_elements` に task_id 追加 |
| `RuntimeError` | chain 構築ロジック失敗 | `__cause__` 保持して送出 |
| WARNING（処理継続） | 重複 task_id / 不正 trace_id / origin_module 不一致 | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f80_module.py` / 実行: `pytest tests/test_f80_module.py -v`

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | traceability_map 構造・trace_chain・is_complete=true・origin/latest |
| Test2 | 異常系 | TypeError（dict 以外・フィールド欠落）/ ValueError（hierarchy 欠落）の分離 |
| Test3 | trace_chain | 完全 chain・部分 chain・source_trace_id 解決 |
| Test4 | HITL移譲 | 空 goals・chain 欠落・不完全 chain・循環依存 |
| Test5 | RuntimeError | chain 構築失敗・`__cause__` 保持 |
| Test6 | WARNING継続 | 重複 task_id・不正 trace_id・origin_module 不一致 |
| Test7 | trace_id | "F80" 固定・source_trace_id・F10→…→F80 パイプライン統合 |
