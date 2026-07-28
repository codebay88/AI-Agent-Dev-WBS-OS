# WP8310 想定シナリオテスト — 参照インデックス

**実体ファイル:** `tests/phase4/test_8310_scenario.py`  
**テストログ:** `docs/phase4/logs/test_8310_scenario_log.txt`  
**結果:** 64 passed / 0 failed  

## テストクラス一覧

| クラス | 対象 | テスト数 |
|---|---|---|
| TestWP8311 | 正常シナリオ | 14 |
| TestWP8312 | 異常シナリオ | 10 |
| TestWP8313 | HITLシナリオ | 9 |
| TestWP8314 | パイプラインチェーン検証 | 12 |
| TestWP8315 | 運用ログ確認 | 19 |

## 重要仕様メモ
- efficiency_score / recommendations は `final_output["evaluation_report"]` の中（トップレベルにない）
- module-scoped pipeline fixture（F10→F90 を1回実行して全クラスで共有）
