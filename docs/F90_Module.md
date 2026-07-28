# F90 最終出力生成モジュール仕様

## 1. Module（概要）

- **Module Name:** F90_Final_Output_Generation_Module
- **Purpose（目的）:** F80 の traceability_map と F70 の hierarchy（F80 パススルー）を統合し、全タスクの履歴・階層・評価を一体化した最終成果物を生成する
- **Responsibility（責務）:** 階層統合・評価集計・整合性検証・レポート生成・HITL 判定を行い、F シリーズ全体の完了を示す最終出力を返す
- **Traceability ID:** WP7700
- **前提モジュール:** F80_Traceability_Generation_Module
- **参照仕様:** `docs/F_series_overview.md`, `docs/F80_Module.md`
- **外部ライブラリ:** なし（stdlib のみ）

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F80 の出力（traceability_map + hierarchy パススルー + trace_id）を含む dict
- **必須項目:** `traceability_map`（list）、`hierarchy`（dict）
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `traceability_map` キーが存在しない場合は `ValueError`
  - `hierarchy` キーが存在しない場合は `TypeError`（F80 のパススルー欠落を示す）

```python
# 正常な入力例（F80 の出力をそのまま渡す）
input_data = {
    "trace_id": "F80",
    "source_trace_id": "F70",
    "traceability_map": [
        {
            "goal_id":       "G1",
            "element_id":    "G1_EL_H",
            "task_id":       "T1",
            "trace_chain":   ["F10","F20","F30","F40","F50","F60","F70"],
            "origin_module": "F10",
            "latest_module": "F70",
            "is_complete":   True
        }
    ],
    "hierarchy": {
        "goals": [
            {
                "goal_id":   "G1",
                "goal_text": "LPを作成する",
                "elements": [
                    {
                        "element_id":   "G1_EL_H",
                        "element_text": "High優先度タスク群",
                        "tasks": [
                            {
                                "task_id":        "T1",
                                "templated_text": "【優先度: 高】次のタスクを実行せよ: LPを作成する",
                                "priority":       "High",
                                "effort":         3,
                                "value":          5
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

- **出力データの構造:** 最終統合成果物
- **必須項目:** `final_output`（dict）、`trace_id`
- **型（Type）:** `dict`

```python
# 出力例
output_data = {
    "trace_id":        "F90",
    "source_trace_id": "F80",
    "final_output": {
        "summary": {
            "total_goals":         1,
            "total_elements":      1,
            "total_tasks":         1,
            "pipeline_integrity":  "verified",
            "traceability_complete": True
        },
        "hierarchy_with_trace": [...],
        "evaluation_report": {
            "average_effort":   3.0,
            "average_value":    5.0,
            "efficiency_score": 1.67,
            "recommendations":  ["高優先度タスクの実行を最優先とする"]
        }
    },
    "hitl":          False,
    "hitl_required": False,
    "hitl_elements": []
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F90 モジュールの統一インターフェース。

    Returns:
        dict: {
            "trace_id": "F90",
            "source_trace_id": str,
            "final_output": {
                "summary": dict,
                "hierarchy_with_trace": list[dict],
                "evaluation_report": dict
            },
            "hitl": bool,
            "hitl_required": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または hierarchy 欠落
        ValueError:   traceability_map の欠落・型不正
        RuntimeError: 集計処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が空 `{}` → `ValueError`
  - `"traceability_map"` キーが存在しない → `ValueError`
  - `traceability_map` が list 以外 → `ValueError`
  - `"hierarchy"` キーが存在しない → `TypeError`
  - `hierarchy` が dict 以外 → `TypeError`

- **Step2 — 前処理**
  - `trace_id` が `"F80"` 以外 → WARNING ログ出力（処理継続）
  - `traceability_map` が空リスト → HITL 移譲（`hitl_reason: "No tasks to finalize"`）
  - `hierarchy.goals` が空リスト → HITL 移譲（同上）

- **Step3 — 階層統合（hierarchy_with_trace 生成）**
  - `traceability_map` から `task_id → trace_chain` のルックアップテーブルを構築
  - `hierarchy.goals` の各タスクに `trace_chain` を付与

- **Step4 — 整合性検証**
  - `traceability_map` の全エントリで `is_complete` が `True` → `traceability_complete = True`
  - いずれか `False` → `is_complete = False` の task_id を `hitl_elements` に追加
  - `trace_chain` が空のエントリ → `hitl_elements` に追加、`hitl_reason: "Trace chain missing"`

- **Step5 — 評価集計**
  - `hierarchy_with_trace` の全タスクから `effort` / `value` を収集（None は除外）
  - `average_effort = sum(efforts) / len(efforts)`
  - `average_value  = sum(values)  / len(values)`
  - `efficiency_score = round(average_value / average_effort, 2)`
  - `average_effort == 0` → ZeroDivisionError → RuntimeError（`__cause__` 保持）

- **Step6 — レポート・推奨事項生成**
  - `recommendations` を自動生成:
    - High priority タスクが存在 → "高優先度タスクの実行を最優先とする"
    - 不完全 trace_chain 存在 → "曖昧語を含むタスクは HITL で再確認する"
    - `efficiency_score > 3.0` → "工数対比で高価値なタスクを優先的に実行する"
  - `recommendations` 自身が ABSTRACT_WORDS を含む → `hitl_elements` に "recommendations" を追加

- **Step7 — HITL 判定・保存・返却**
  - `efficiency_score == 0 または > 10` → `hitl_elements` に "efficiency_score" を追加
  - `hitl_elements` が存在 → `hitl_required = True`
  - 結果を `data/output/f90_result_{timestamp}.json` に UTF-8 で保存
  - INFO ログに集計結果を記録（WP3300 準拠）

---

## 4. Error Handling（例外処理）

| 例外 / 状態 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外 / `hierarchy` 欠落・型不正 | 即時送出 |
| `ValueError` | 空 dict / `traceability_map` 欠落・型不正 | 即時送出 |
| HITL 移譲（空） | `traceability_map` または `goals` が空 | `hitl_required: True, hitl_reason: "No tasks to finalize"` |
| HITL 移譲（不完全） | `is_complete=False` の trace_chain / efficiency_score 異常 | `hitl_elements` に追加 |
| `RuntimeError` | 集計処理失敗（ZeroDivisionError 等） | `__cause__` 保持して送出 |
| WARNING（処理継続） | 重複 task_id / 不正 trace_id | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f90_module.py` / 実行: `pytest tests/test_f90_module.py -v`

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | final_output 構造・summary・hierarchy_with_trace・evaluation_report |
| Test2 | 異常系 | TypeError（dict 以外・hierarchy 欠落）/ ValueError（traceability_map 欠落）の分離 |
| Test3 | 統合ロジック | 階層統合・trace_chain 付与・評価集計・efficiency_score 算出 |
| Test4 | HITL移譲 | 空入力・不完全 chain・efficiency_score 異常 |
| Test5 | RuntimeError | ZeroDivisionError ラップ・`__cause__` 保持 |
| Test6 | WARNING継続 | 重複 task_id・不正 trace_id |
| Test7 | trace_id | "F90" 固定・source_trace_id・F10→…→F90 完全パイプライン統合 |
