# F40 タスク生成モジュール仕様

## 1. Module（概要）

- **Module Name:** F40_Task_Generation_Module
- **Purpose（目的）:** F30 の evaluated_goals を受け取り、importance・feasibility・priority をもとに実行可能なタスクを生成する
- **Responsibility（責務）:** 各評価済み要素からタスク文・優先度・工数・価値スコアを算出し、task_id 付きのタスクリストを生成して後続モジュールへ引き渡す
- **Traceability ID:** WP7200
- **前提モジュール:** F30_Goal_Element_Evaluator
- **参照仕様:** `docs/F_series_overview.md`

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F30 の出力（evaluated_goals + trace_id）を含む dict
- **必須項目:** `evaluated_goals`（list）、各要素の `element_id` / `priority` / `score_importance` / `score_feasibility`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `evaluated_goals` キーが存在しない場合は `ValueError`
  - 各要素に必須フィールドが欠落している場合は `ValueError`
  - スコアが 0.0〜1.0 範囲外の場合は WARNING ログ出力（処理継続）
  - `priority` が "High"/"Medium"/"Low" 以外の場合は WARNING ログ出力（処理継続）

```python
# 正常な入力例（F30 の出力をそのまま渡す）
input_data = {
    "trace_id": "F30",
    "evaluated_goals": [
        {
            "element_id": "E1",
            "text": "売上を前年比120%に成長させる",
            "parent": "L1",
            "score_importance": 0.85,
            "score_feasibility": 0.70,
            "priority": "High"
        }
    ]
}
```

### Output

- **出力データの構造:** 生成済みタスクリストとトレース情報
- **必須項目:** `tasks`（list）、`trace_id`
- **型（Type）:** `dict`
- **各タスクの構造:**
  - `task_id`: "T1", "T2", ... （連番）
  - `element_id`: 入力の element_id を引き継ぐ
  - `task_text`: 生成されたタスク文
  - `priority`: "High" / "Medium" / "Low"
  - `estimated_effort`: 工数スコア（1〜5、feasibility の反転）
  - `estimated_value`: 価値スコア（1〜5、importance の正規化）

```python
# 出力例
output_data = {
    "trace_id": "F40",
    "source_trace_id": "F30",
    "tasks": [
        {
            "task_id": "T1",
            "element_id": "E1",
            "task_text": "【即実行】売上を前年比120%に成長させる",
            "priority": "High",
            "estimated_effort": 2,
            "estimated_value": 5
        }
    ],
    "hitl": False,
    "hitl_elements": []
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F40 モジュールの統一インターフェース。

    Args:
        input_data (dict): F30 の出力形式（evaluated_goals + trace_id）

    Returns:
        dict: {
            "trace_id": "F40",
            "source_trace_id": str,
            "tasks": list[dict],
            "hitl": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外
        ValueError:   evaluated_goals の欠落 / 各要素の必須フィールド欠落
        RuntimeError: タスク生成処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が空 `{}` → `ValueError`
  - `"evaluated_goals"` キーが存在しない → `ValueError`
  - `evaluated_goals` が list 以外 → `ValueError`
  - 各要素に `element_id` / `priority` / `score_importance` / `score_feasibility` が存在しない → `ValueError`

- **Step2 — 前処理**
  - `trace_id` が `"F30"` 以外の場合は WARNING ログ出力（処理継続）
  - `evaluated_goals` が空リストの場合は WARNING ログ出力し、空の tasks を返す
  - 重複 `element_id` を検出し WARNING ログ出力（処理継続）
  - スコアが 0.0〜1.0 範囲外の場合は WARNING ログ出力（処理継続）

- **Step3 — HITL 移譲判定（要素単位）**
  - `text` フィールドが空文字列または空白のみ → `hitl_elements` に追加してスキップ
  - `text` に曖昧語（「など」「いろいろ」「何か」）を含む → `hitl_elements` に追加してスキップ
  - `priority` が判定不能（"High"/"Medium"/"Low" 以外）→ WARNING 出力後にスキップ
  - `score_importance` / `score_feasibility` が両方 0.5 未満かつ差が 0.05 以下（極端に曖昧）→ `hitl_elements` に追加してスキップ
  - すべての要素が HITL 移譲対象の場合 → `hitl: True` で返却

- **Step4 — タスク生成**
  - **task_text の生成（priority 別）:**
    - `"High"` → `"【即実行】"` プレフィックスを付与（具体的・即行動可能）
    - `"Medium"` → `"【計画】"` プレフィックスを付与（中粒度タスク）
    - `"Low"` → `"【検討】"` プレフィックスを付与（大まかな方向性）
    - `text` フィールドが存在する場合はそれをベースにする。ない場合は `element_id` を使用。
  - **estimated_effort の算出（1〜5、feasibility の反転）:**
    - `effort = max(1, min(5, round((1 - score_feasibility) * 4) + 1))`
    - feasibility が高いほど effort は低くなる
  - **estimated_value の算出（1〜5、importance の正規化）:**
    - `value = max(1, min(5, round(score_importance * 4) + 1))`
    - importance が高いほど value は高くなる
  - **task_id の付与:** "T1", "T2", ... （HITL スキップを除いた連番）
  - タスク生成中に例外が発生した場合は `RuntimeError`（`__cause__` に元の例外を保持）

- **Step5 — 整合性検証**
  - `estimated_effort` / `estimated_value` が 1〜5 の範囲外 → WARNING ログ出力（処理継続）
  - `task_id` の重複 → WARNING ログ出力（処理継続）

- **Step6 — 保存・返却**
  - 結果を `data/output/f40_result_{timestamp}.json` に UTF-8 で保存
  - 処理日時・生成タスク数・HITL 移譲数を INFO ログに記録（WP3300 準拠）
  - `output_data` として呼び出し元へ返却

---

## 4. Error Handling（例外処理）

`docs/F_series_overview.md` の Error Handling ルールを継承し、以下を追加：

| 例外 / 状態 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外 | 即時送出 |
| `ValueError` | 空 dict / `evaluated_goals` 欠落 / 必須フィールド欠落 | 即時送出 |
| HITL 移譲（要素単位） | `text` 空文字列・曖昧語・スコア極端に曖昧 | `hitl_elements` に記録してスキップ |
| HITL 移譲（全体） | 全要素が HITL 対象 | `hitl: True` で返却 |
| `RuntimeError` | タスク生成ロジック失敗 | `__cause__` に元の例外を保持して送出 |
| WARNING（処理継続） | 重複 element_id / スコア範囲外 / 不正 priority / 不明 trace_id | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f40_module.py` / 実行: `pytest tests/test_f40_module.py -v`

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | タスク生成・task_id 連番・effort/value 範囲・priority プレフィックス |
| Test2 | 異常系 | TypeError（dict 以外）/ ValueError（欠落・型不正）の分離 |
| Test3 | HITL移譲 | 空文字・曖昧語・全体/部分 HITL・hitl_elements |
| Test4 | RuntimeError | タスク生成失敗・`__cause__` 保持 |
| Test5 | WARNING継続 | 重複 element_id・スコア範囲外・不正 priority・不明 trace_id |
| Test6 | trace_id | "F40" 固定・source_trace_id・F10→F20→F30→F40 パイプライン統合 |
