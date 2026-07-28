# WP8320 異常系運用テスト — 参照インデックス

**実体ファイル:** `tests/phase4/test_8320_operational_exception.py`  
**テストログ:** `docs/phase4/logs/test_8320_operational_exception_log.txt`  
**結果:** 51 passed / 1 skipped / 0 failed  

## テストクラス一覧

| クラス | 対象 | テスト数 |
|---|---|---|
| TestWP8321 | リトライ動作 | 9 |
| TestWP8322 | データ破損処理 | 16 |
| TestWP8323 | HITL再承認フロー | 7 |
| TestWP8324 | 構造破損フェイルセーフ | 9 |
| TestWP8325 | 例外ログ記録 | 11 |

## スキップ詳細
`test_f10_prompt_not_found_raises_file_not_found` — プロンプトファイルが環境に存在するため条件付きスキップ。Phase 5 CI 環境で実施予定（制約 C-01）。

## 重要仕様メモ
- リトライテストは `time.sleep` と `_load_prompt` を両方モックする必要あり
- `anthropic.APIError(message=..., request=None, body=None)` — 3引数必須
- _SAFE_GOAL = "売上を前年比120%に成長させる"（10文字以上、曖昧語なし）
