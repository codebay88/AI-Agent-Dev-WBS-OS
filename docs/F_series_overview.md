# F シリーズ共通仕様（F_series_overview）

本ドキュメントは F10〜F40 以降の全モジュールが継承すべき共通ルールを定義する。

---

## 1. パイプライン概要

```
F10（目的構造化）
  └─ goal.L1/L2/L3
      ↓ trace_id="F10"
F20（目的展開）
  └─ expanded_goals[element_id, text, parent]
      ↓ trace_id="F20"
F30（目的要素評価）
  └─ evaluated_goals[element_id, score_importance, score_feasibility, priority]
      ↓ trace_id="F30"
F40（タスク生成）
  └─ tasks[task_id, element_id, task_text, priority, estimated_effort, estimated_value]
      ↓ trace_id="F40"
F50 以降…
```

---

## 2. trace_id ルール

| モジュール | 出力 trace_id | 受け取る source_trace_id |
|---|---|---|
| F10 | "F10" | なし（起点） |
| F20 | "F20" | "F10" |
| F30 | "F30" | "F20" |
| F40 | "F40" | "F30" |
| F50〜 | "F5x" | 前段モジュールの trace_id |

- 出力には必ず `trace_id`（自モジュール）と `source_trace_id`（前段モジュール）を含める
- 想定外の `source_trace_id` を受け取った場合は WARNING ログを出力し処理継続

---

## 3. 統一インターフェース

```python
def execute(input_data: dict) -> dict:
    """全 F シリーズモジュールの統一インターフェース。"""
```

Returns:
```python
{
    "trace_id": "Fxx",
    "source_trace_id": str,
    "<output_key>": list[dict] | dict,
    "hitl": bool,
    "hitl_elements": list[str]
}
```

---

## 4. 入力検証ルール（全モジュール共通）

| 条件 | 例外 |
|---|---|
| `input_data` が dict 以外 | `TypeError` |
| `input_data` が `None` または `{}` | `ValueError` |
| 必須キーが存在しない | `ValueError` |
| 各要素の必須フィールド欠落 | `ValueError` |

---

## 5. HITL 移譲ルール

### モジュール全体 HITL（hitl: True）
- すべての処理対象要素が HITL 移譲対象となった場合
- 入力テキストに曖昧語（「など」「いろいろ」「何か」）が含まれる場合
- テキストが空文字列または粒度不足の場合

### 要素単位 HITL（hitl_elements に追加、処理継続）
- 個々の要素で上記条件に該当した場合
- 当該要素をスキップし `hitl_elements` に `element_id` を記録

---

## 6. Error Handling ルール

| 例外 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | dict 以外の入力 | 即時送出 |
| `ValueError` | 空 dict / 必須キー欠落 / 型不正 | 即時送出 |
| `RuntimeError` | 処理ロジック失敗 | `__cause__` に元例外を保持して送出 |
| WARNING | 重複 ID / スコア範囲外 / 不正値 / 不明 trace_id | WARNING ログ出力、処理継続 |

---

## 7. ログ出力ルール（WP3300 準拠）

- INFO: 処理完了サマリ（件数・保存パス）
- WARNING: 異常検知（重複・範囲外・HITL移譲）
- ERROR: 処理中断レベル（RuntimeError 送出前）

---

## 8. Unit Test 方針（WP5100 準拠）

| テストクラス | 区分 |
|---|---|
| `TestNormalXxx` | 正常系（出力構造・フィールド・値域） |
| `TestInvalidInput` | TypeError / ValueError の分離検証 |
| `TestHitlDelegation` | 空文字・曖昧語・全体/部分 HITL |
| `TestProcessingError` | RuntimeError・`__cause__` 保持 |
| `TestWarningContinuation` | WARNING 継続（重複・範囲外・不正値） |
| `TestTraceId` | trace_id・source_trace_id・パイプライン統合 |

共通ヘルパー: `assert_warning_contains` / `assert_wrapped_cause`

---

## 9. 出力保存ルール

- 保存先: `data/output/fxx_result_{timestamp}.json`
- エンコード: UTF-8
- フォーマット: `json.dumps(..., ensure_ascii=False, indent=2)`
