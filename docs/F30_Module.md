# F30 目的要素評価モジュール仕様

## 1. Module（概要）

- **Module Name:** F30_Goal_Element_Evaluator
- **Purpose（目的）:** F20 の expanded_goals を受け取り、各要素の重要度・実現可能性を評価し priority を算出する
- **Responsibility（責務）:** 各 expanded_goal の text を解析し、score_importance / score_feasibility / priority を付与した evaluated_goals を生成して後続モジュールへ引き渡す
- **Traceability ID:** WP7200
- **前提モジュール:** F20_Goal_Expansion_Module

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F20 の出力（expanded_goals + trace_id）を含む dict
- **必須項目:** `expanded_goals`（list）、各要素の `element_id` / `text` / `parent`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `expanded_goals` キーが存在しない場合は `ValueError`
  - 各要素に `element_id` / `text` / `parent` が欠落している場合は `ValueError`
  - `text` が空文字列の場合は HITL 移譲（要素単位で判定）
  - `trace_id` が `"F20"` 以外の場合は WARNING ログ出力（処理継続）

```python
# 正常な入力例（F20 の出力をそのまま渡す）
input_data = {
    "trace_id": "F20",
    "expanded_goals": [
        {"element_id": "E1", "text": "売上を前年比120%に成長させる", "parent": "L1"},
        {"element_id": "E2", "text": "新規顧客獲得施策を推進する",   "parent": "L2"},
        {"element_id": "E3", "text": "LPを作成する",                "parent": "L3"},
    ]
}
```

### Output

- **出力データの構造:** 評価済み目的要素リストとトレース情報
- **必須項目:** `evaluated_goals`（list）、`trace_id`
- **型（Type）:** `dict`
- **各要素の構造:**
  - `element_id`: 入力の element_id を引き継ぐ
  - `text`: 入力の text を引き継ぐ
  - `parent`: 入力の parent を引き継ぐ
  - `score_importance`: 重要度スコア（0.0〜1.0）
  - `score_feasibility`: 実現可能性スコア（0.0〜1.0）
  - `priority`: "High" / "Medium" / "Low"

```python
# 出力例
output_data = {
    "trace_id": "F30",
    "source_trace_id": "F20",
    "evaluated_goals": [
        {"element_id": "E1", "text": "売上を前年比120%に成長させる",
         "parent": "L1", "score_importance": 0.85, "score_feasibility": 0.70, "priority": "High"},
        {"element_id": "E2", "text": "新規顧客獲得施策を推進する",
         "parent": "L2", "score_importance": 0.60, "score_feasibility": 0.80, "priority": "Medium"},
        {"element_id": "E3", "text": "LPを作成する",
         "parent": "L3", "score_importance": 0.40, "score_feasibility": 0.90, "priority": "Medium"},
    ],
    "hitl": False,
    "hitl_elements": []  # HITL 移譲対象の element_id リスト
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F30 モジュールの統一インターフェース。

    F20 の出力（expanded_goals）を受け取り、
    各要素にスコアと priority を付与した evaluated_goals を返す。

    Args:
        input_data (dict): F20 の出力形式（expanded_goals + trace_id）

    Returns:
        dict: {
            "trace_id": "F30",
            "source_trace_id": str,
            "evaluated_goals": list[dict],
            "hitl": bool,
            "hitl_elements": list[str]  # HITL 移譲対象の element_id
        }

    Raises:
        TypeError:    input_data が dict 以外
        ValueError:   expanded_goals の欠落 / 各要素の必須フィールド欠落
        RuntimeError: スコア算出処理の失敗（__cause__ 保持）
    """
    pass
```

---

## 3. Logic（ロジック）

- **Step1 — 入力検証**
  - `input_data` が dict 以外 → `TypeError`
  - `input_data` が空 `{}` → `ValueError`
  - `"expanded_goals"` キーが存在しない → `ValueError`
  - `expanded_goals` が list 以外 → `ValueError`
  - 各要素に `element_id` / `text` / `parent` が存在しない → `ValueError`

- **Step2 — 前処理**
  - `trace_id` が `"F20"` 以外の場合は WARNING ログ出力（処理継続）
  - `expanded_goals` が空リストの場合は WARNING ログ出力し、空の evaluated_goals を返す
  - 重複 `element_id` を検出し WARNING ログ出力（処理継続）

- **Step3 — HITL 移譲判定（要素単位）**
  - 各要素の `text` が空文字列または空白のみ → `hitl_elements` に追加してスキップ
  - 曖昧語（「など」「いろいろ」「何か」）を含む `text` → `hitl_elements` に追加してスキップ
  - すべての要素が HITL 移譲対象の場合は `hitl: True` で返却

- **Step4 — スコア算出**
  - **score_importance（重要度）の算出基準:**
    - `parent == "L1"`: 基礎スコア 0.85（全体方針は重要度が高い）
    - `parent == "L2"`: 基礎スコア 0.60（施策単位は中程度）
    - `parent == "L3"`: 基礎スコア 0.40（タスク単位は相対的に低い）
    - 数値・比率表現（"120%", "3倍" 等）を含む場合 +0.10（具体性ボーナス）
    - 抽象語（「改善」「向上」「最適化」）のみで構成される場合 −0.10（抽象性ペナルティ）
    - 最終値を 0.0〜1.0 にクリップ
  - **score_feasibility（実現可能性）の算出基準:**
    - `parent == "L3"`: 基礎スコア 0.85（具体的タスクは実現しやすい）
    - `parent == "L2"`: 基礎スコア 0.65（施策は中程度）
    - `parent == "L1"`: 基礎スコア 0.50（全体方針は不確実性が高い）
    - 動作動詞（「作成する」「実行する」「配信する」）を含む場合 +0.10（実行可能性ボーナス）
    - 文字数が 5 文字以下の場合 −0.10（粒度不足ペナルティ）
    - 最終値を 0.0〜1.0 にクリップ
  - **priority の分類:**
    - `(score_importance + score_feasibility) / 2 >= 0.70` → "High"
    - `0.50 <= 平均 < 0.70` → "Medium"
    - `平均 < 0.50` → "Low"
  - スコア算出中に例外が発生した場合は `RuntimeError`（`__cause__` に元の例外を保持）

- **Step5 — 整合性検証**
  - `score_importance` / `score_feasibility` が 0.0〜1.0 の範囲外 → WARNING（処理継続）
  - `priority` が "High" / "Medium" / "Low" 以外 → WARNING（処理継続）
  - `parent` 値が "L1" / "L2" / "L3" 以外 → WARNING（処理継続）

- **Step6 — 保存・返却**
  - 結果を `data/output/f30_result_{timestamp}.json` に UTF-8 で保存
  - 処理日時・評価要素数・HITL 移譲数を INFO ログに記録（WP3300 準拠）
  - `output_data` として呼び出し元へ返却

---

## 4. Error Handling（例外処理）

| 例外 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外 | 即時送出、ログ記録 |
| `ValueError` | 空 dict / `expanded_goals` 欠落・型不正 / 必須フィールド欠落 | 即時送出、ログ記録 |
| HITL 移譲（要素単位） | `text` が空文字列・曖昧語 | `hitl_elements` に記録してスキップ |
| HITL 移譲（全体） | 全要素が HITL 対象 | `hitl: True` で返却 |
| `RuntimeError` | スコア算出失敗 | `__cause__` に元の例外を保持して送出 |
| WARNING（処理継続） | 重複 element_id / スコア範囲外 / 不正 parent / 不明 trace_id | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f30_module.py` / 実行: `pytest tests/test_f30_module.py -v`（WP5100準拠）

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | スコア算出・0.0〜1.0 範囲・priority 分類・全フィールド存在 |
| Test2 | 異常系 | None・{}・型不正・expanded_goals 欠落・必須フィールド欠落 |
| Test3 | HITL移譲 | 空文字・曖昧語での hitl_elements 追加・全要素 HITL 時の hitl:True |
| Test4 | スコア算出失敗 | RuntimeError・`__cause__` 保持 |
| Test5 | WARNING継続 | 重複 element_id・不正 parent・スコア範囲外の WARNING ログ |
| Test6 | trace_id | 出力の `trace_id=="F30"` / `source_trace_id` 反映 |
