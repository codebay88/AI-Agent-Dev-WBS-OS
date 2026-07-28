# F60 MECEチェックモジュール仕様

## 1. Module（概要）

- **Module Name:** F60_MECE_Validation_Module
- **Purpose（目的）:** F50 の templated_tasks を受け取り、タスク群が MECE 原則に従っているかを検証する
- **Responsibility（責務）:** 重複・抜け漏れ・曖昧タスクを検出し、MECE準拠レポートを生成する
- **Traceability ID:** WP7400
- **前提モジュール:** F50_Template_Application_Module
- **参照仕様:** `docs/F_series_overview.md`, `docs/F50_Module.md`
- **外部ライブラリ:** なし（純粋 Python 実装。単語ベクトルによる cosine 類似度を stdlib のみで実装）

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F50 の出力（templated_tasks + trace_id）を含む dict
- **必須項目:** `templated_tasks`（list）、各要素の `task_id` / `templated_text` / `priority`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `templated_tasks` キーが存在しない場合は `ValueError`
  - 各要素に必須フィールドが欠落している場合は `TypeError`
  - 空リスト入力 → HITL 移譲（`hitl_required: true`, `hitl_reason: "No tasks provided"`）

```python
# 正常な入力例（F50 の出力をそのまま渡す）
input_data = {
    "trace_id": "F50",
    "templated_tasks": [
        {
            "task_id": "T1",
            "template_id": "TMP_HIGH",
            "templated_text": "【優先度: 高】次のタスクを実行せよ: LPを作成する",
            "priority": "High",
            "effort": 3,
            "value": 5
        }
    ]
}
```

### Output

- **出力データの構造:** MECE 検証レポートとトレース情報
- **必須項目:** `mece_report`（dict）、`trace_id`
- **型（Type）:** `dict`
- **mece_report の構造:**
  - `duplicate_tasks`: 重複と判定されたタスクの task_id リスト
  - `missing_elements`: 欠落と判定された element_id リスト（element_id が存在する場合のみ）
  - `ambiguous_tasks`: 曖昧と判定されたタスクの task_id リスト
  - `is_mece_compliant`: すべてのリストが空の場合 `true`、それ以外 `false`

```python
# 出力例
output_data = {
    "trace_id": "F60",
    "source_trace_id": "F50",
    "mece_report": {
        "duplicate_tasks": ["T3"],
        "missing_elements": [],
        "ambiguous_tasks": ["T1"],
        "is_mece_compliant": False
    },
    "hitl": False,
    "hitl_required": False,
    "hitl_elements": []
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F60 モジュールの統一インターフェース。

    Args:
        input_data (dict): F50 の出力形式（templated_tasks + trace_id）

    Returns:
        dict: {
            "trace_id": "F60",
            "source_trace_id": str,
            "mece_report": {
                "duplicate_tasks": list[str],
                "missing_elements": list[str],
                "ambiguous_tasks": list[str],
                "is_mece_compliant": bool
            },
            "hitl": bool,
            "hitl_required": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または各要素の必須フィールド欠落
        ValueError:   templated_tasks の欠落・型不正
        RuntimeError: 類似度計算処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が空 `{}` → `ValueError`
  - `"templated_tasks"` キーが存在しない → `ValueError`
  - `templated_tasks` が list 以外 → `ValueError`
  - 各要素に `task_id` / `templated_text` / `priority` が存在しない → `TypeError`

- **Step2 — 前処理**
  - `trace_id` が `"F50"` 以外 → WARNING ログ出力（処理継続）
  - `templated_tasks` が空リスト → HITL 移譲（`hitl_required: true, hitl_reason: "No tasks provided"`）
  - 重複 `task_id` → WARNING ログ出力（処理継続）
  - `priority` が "High"/"Medium"/"Low" 以外 → WARNING ログ出力（処理継続）

- **Step3 — 重複検出**
  - 同一 `element_id`（存在する場合）を持つタスク → `duplicate_tasks` に追加
  - 全タスクペアの `templated_text` 間 cosine 類似度を計算
    - `similarity > 0.85` → `duplicate_tasks` に追加（未登録の場合のみ）
    - `0.80 ≤ similarity ≤ 0.85`（不確定域）→ `hitl_elements` に追加してスキップ
  - cosine 類似度実装: stdlib のみ（`math.sqrt`、単語 Counter ベクトル）

- **Step4 — 抜け漏れ検出**
  - タスクに `element_id` フィールドが存在する場合のみ実施
  - `element_id` の連番（E1, E2, …）に欠番があれば → `missing_elements` に追加
  - `element_id` が存在しない場合は `missing_elements = []`

- **Step5 — 曖昧検出**
  - `templated_text` に抽象語（`ABSTRACT_WORDS`）が含まれる → `ambiguous_tasks` に追加
  - `ABSTRACT_WORDS = ["改善", "向上", "検討", "最適化", "強化", "推進", "活性化"]`

- **Step6 — MECE 判定**
  - `duplicate_tasks`・`missing_elements`・`ambiguous_tasks` がすべて空 → `is_mece_compliant = True`
  - いずれか存在 → `is_mece_compliant = False`
  - HITL 移譲条件:
    - `is_mece_compliant = False` かつ `ambiguous_tasks` が存在 → `hitl_required = True`
    - `hitl_elements` が存在する（不確定域の類似度ペア）→ `hitl_required = True`

- **Step7 — 保存・返却**
  - 結果を `data/output/f60_result_{timestamp}.json` に UTF-8 で保存
  - INFO ログに検証結果サマリを記録（WP3300 準拠）

---

## 4. Error Handling（例外処理）

`docs/F_series_overview.md` の Error Handling ルールを継承し、以下を追加：

| 例外 / 状態 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外、または各要素の必須フィールド欠落 | 即時送出 |
| `ValueError` | 空 dict / `templated_tasks` 欠落・型不正 | 即時送出 |
| HITL 移譲（空リスト） | `templated_tasks` が空 | `hitl_required: True, hitl_reason: "No tasks provided"` |
| HITL 移譲（曖昧判定） | MECE 非準拠 + ambiguous_tasks 存在、または不確定類似度ペア存在 | `hitl_required: True` |
| `RuntimeError` | 類似度計算ロジック失敗 | `__cause__` に元の例外を保持して送出 |
| WARNING（処理継続） | 重複 task_id / 不正 priority / 不明 trace_id | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f60_module.py` / 実行: `pytest tests/test_f60_module.py -v`

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | MECE準拠・mece_report 構造・is_mece_compliant=true |
| Test2 | 異常系 | TypeError（dict 以外・フィールド欠落）/ ValueError（templated_tasks 欠落）の分離 |
| Test3 | MECE非準拠 | duplicate_tasks / missing_elements / ambiguous_tasks の各検出 |
| Test4 | HITL移譲 | 空リスト・曖昧タスク・不確定類似度 → hitl_required=true |
| Test5 | RuntimeError | 類似度計算失敗・`__cause__` 保持 |
| Test6 | WARNING継続 | 重複 task_id・不正 priority・不明 trace_id |
| Test7 | trace_id | "F60" 固定・source_trace_id・F10→F20→F30→F40→F50→F60 パイプライン統合 |
