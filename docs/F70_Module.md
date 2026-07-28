# F70 階層生成モジュール仕様

## 1. Module（概要）

- **Module Name:** F70_Hierarchy_Generation_Module
- **Purpose（目的）:** F60 の templated_tasks を受け取り、目的（Goal）・要素（Element）・タスク（Task）の三層階層構造を生成する
- **Responsibility（責務）:** cosine 類似度によるゴールグループ化・priority 別要素化・整合性検証・HITL 判定を行い、後続モジュールへ引き渡す
- **Traceability ID:** WP7500
- **前提モジュール:** F60_MECE_Validation_Module
- **参照仕様:** `docs/F_series_overview.md`, `docs/F60_Module.md`
- **外部ライブラリ:** なし（stdlib のみ。cosine 類似度・Union-Find グループ化を純粋 Python で実装）

---

## 2. Interface（I/O仕様）

### Input

- **入力データの構造:** F60 の出力（templated_tasks + mece_report + trace_id）を含む dict
- **必須項目:** `templated_tasks`（list）、各要素の `task_id` / `templated_text` / `priority`
- **型（Type）:** `dict`
- **制約条件:**
  - dict 形式必須（それ以外は `TypeError`）
  - `templated_tasks` キーが存在しない場合は `ValueError`
  - 各要素に必須フィールドが欠落している場合は `TypeError`
  - 空リスト入力 → HITL 移譲（`hitl_required: true`, `hitl_reason: "No hierarchy generated"`）

```python
# 正常な入力例（F60 の出力をそのまま渡す）
input_data = {
    "trace_id": "F60",
    "templated_tasks": [
        {
            "task_id": "T1",
            "template_id": "TMP_HIGH",
            "templated_text": "【優先度: 高】次のタスクを実行せよ: LPを作成する",
            "priority": "High",
            "effort": 3,
            "value": 5
        }
    ],
    "mece_report": {
        "duplicate_tasks": [],
        "missing_elements": [],
        "ambiguous_tasks": [],
        "is_mece_compliant": True
    }
}
```

### Output

- **出力データの構造:** 三層階層構造とトレース情報
- **必須項目:** `hierarchy`（dict）、`trace_id`
- **型（Type）:** `dict`
- **hierarchy.goals の各 goal 構造:**
  - `goal_id`: "G1", "G2", ... （連番）
  - `goal_text`: 目的テキスト（グループ内共通トークンまたはプレフィックス除去済みテキスト）
  - `elements`: 要素リスト（priority 別グループ化）
    - `element_id`: "G1_EL_H" / "G1_EL_M" / "G1_EL_L"
    - `element_text`: 要素テキスト（priority + 共通トークン）
    - `tasks`: タスクリスト（priority 順）

```python
# 出力例
output_data = {
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
    },
    "hitl": False,
    "hitl_required": False,
    "hitl_elements": []
}
```

### execute() インターフェース

```python
def execute(input_data: dict) -> dict:
    """F70 モジュールの統一インターフェース。

    Args:
        input_data (dict): F60 の出力形式（templated_tasks + mece_report + trace_id）

    Returns:
        dict: {
            "trace_id": "F70",
            "source_trace_id": str,
            "hierarchy": {"goals": list[dict]},
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
  - `trace_id` が `"F60"` 以外 → WARNING ログ出力（処理継続）
  - `templated_tasks` が空リスト → HITL 移譲（`hitl_required: true, hitl_reason: "No hierarchy generated"`）
  - 重複 `task_id` → WARNING ログ出力（処理継続）
  - `priority` が "High"/"Medium"/"Low" 以外 → WARNING ログ出力（処理継続）

- **Step3 — 目的（Goal）グループ化**
  - Union-Find で `templated_text` 間 cosine 類似度 > `GOAL_SIM_THRESHOLD`（0.80）のタスクを同一 goal に統合
  - 各グループから `goal_text` を生成:
    - 複数タスク: ≥2タスクに出現する共通トークンを最大5個連結
    - 単一タスク: 優先度プレフィックスを除去したテキスト
  - `goal_id` は "G1", "G2", ... （連番）
  - goal_text が ABSTRACT_WORDS のみで構成される場合 → `hitl_elements` に goal_id を追加

- **Step4 — 要素（Element）グループ化**
  - 各 goal 内のタスクを priority（High → Medium → Low）でグループ化
  - `element_id` は "{goal_id}_EL_H" / "{goal_id}_EL_M" / "{goal_id}_EL_L"
  - `element_text` は "{priority}優先度タスク群"
  - element_text が重複または ABSTRACT_WORDS のみ → `hitl_elements` に element_id を追加

- **Step5 — 整合性検証**
  - 各 goal に element が1つ以上、各 element に task が1つ以上存在すること
  - 違反があれば WARNING ログ出力（処理継続）かつ `hitl_elements` に追加

- **Step6 — HITL 判定**
  - `hitl_elements` が存在 → `hitl_required = True`
  - 空階層（goals = []）→ `hitl_required = True, hitl_reason = "No hierarchy generated"`
  - mece_report が存在し `is_mece_compliant = False` → WARNING ログ出力（hitl_required は変えない）

- **Step7 — 保存・返却**
  - 結果を `data/output/f70_result_{timestamp}.json` に UTF-8 で保存
  - INFO ログに goal 数・element 数・task 数を記録（WP3300 準拠）

---

## 4. Error Handling（例外処理）

`docs/F_series_overview.md` の Error Handling ルールを継承し、以下を追加：

| 例外 / 状態 | 発生条件 | 処理 |
|---|---|---|
| `TypeError` | `input_data` が dict 以外、または各要素の必須フィールド欠落 | 即時送出 |
| `ValueError` | 空 dict / `templated_tasks` 欠落・型不正 | 即時送出 |
| HITL 移譲（空） | `templated_tasks` が空 | `hitl_required: True, hitl_reason: "No hierarchy generated"` |
| HITL 移譲（抽象） | goal_text / element_text が抽象語のみ | `hitl_elements` に追加 |
| HITL 移譲（整合性） | goal に element/task が存在しない | `hitl_elements` に追加 |
| `RuntimeError` | 類似度計算ロジック失敗 | `__cause__` に元の例外を保持して送出 |
| WARNING（処理継続） | 重複 task_id / 不正 priority / 不明 trace_id / MECE 非準拠 | WARNING ログ出力、処理継続 |

---

## 5. Unit Test（単体テスト）

テストファイル: `tests/test_f70_module.py` / 実行: `pytest tests/test_f70_module.py -v`

| テスト | 区分 | 確認内容 |
|---|---|---|
| Test1 | 正常系 | 三層構造生成・goal_id 連番・element_id・task 配置・priority 順 |
| Test2 | 異常系 | TypeError（dict 以外・フィールド欠落）/ ValueError（tasks 欠落）の分離 |
| Test3 | グループ化 | 類似タスクのゴール統合・priority 別 element 分離・単一タスク goal |
| Test4 | HITL移譲 | 空入力・抽象 goal_text・整合性不完全・hitl_elements |
| Test5 | RuntimeError | 類似度計算失敗・`__cause__` 保持 |
| Test6 | WARNING継続 | 重複 task_id・不正 priority・不明 trace_id・MECE 非準拠 |
| Test7 | trace_id | "F70" 固定・source_trace_id・F10→…→F70 パイプライン統合 |
