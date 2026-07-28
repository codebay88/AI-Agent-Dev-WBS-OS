# Fモジュール共通テンプレート（最終版）

## 1. Module Information（モジュール情報）

- **Module Name:** Fxx_xxxxx
- **Purpose（目的）:**
- **Responsibility（責務）:**
- **Traceability ID（対応するWP / L3 / L4）:**

---

## 2. Interface（I/O仕様）

### Input

- 入力データの構造
- 必須項目
- 型（Type）
- 制約条件

### Output

- 出力データの構造
- 必須項目
- 型（Type）
- 粒度（L1/L2/L3）

### execute() インターフェース

```python
def execute(input_data):
    """ Fxx モジュールの統一インターフェース """
    pass
```

---

## 3. Preconditions（前提条件）

- 環境変数
- 設定ファイル
- 外部依存（Claude Code等）
- 安全条件（HITL / 最小権限）

---

## 4. Logic（ロジック）

- Step1
- Step2
- Step3
- 例外処理
- フェイルセーフ

---

## 5. Logging（ログ出力）

- ログ形式
- 保存先
- 監査ログ（WP3300）

---

## 6. Error Handling（例外処理）

- 標準例外
- リトライ条件
- HITL移譲条件

---

## 7. Unit Test（単体テスト）

- テストケース一覧
- 正常系
- 異常系
- 境界値
- WP5100に沿ったテスト仕様

---

## 8. Postconditions（事後条件）

- 出力の整合性
- トレーサビリティ更新
- 次モジュールへの引き渡し条件
