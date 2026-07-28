# WP8220 例外処理テスト — 参照インデックス

**実体ファイル:** `tests/phase4/test_8220_exception.py`  
**テストログ:** `docs/phase4/logs/test_8220_exception_log.txt`  
**結果:** 131 passed / 0 failed  

## テストクラス一覧

| クラス | 対象 | テスト数 |
|---|---|---|
| TestWP8221 | F10 例外 | 14 |
| TestWP8222 | F20 例外 | 14 |
| TestWP8223 | F30 例外 | 14 |
| TestWP8224 | F40 例外 | 12 |
| TestWP8225 | F50 例外 | 14 |
| TestWP8226 | F60 例外 | 14 |
| TestWP8227 | F70 例外 | 12 |
| TestWP8228 | F80 例外 | 14 |
| TestWP8229 | F90 例外 | 14 |
| TestWP822A | 例外伝播 | 9 |
| TestWP822B | 例外クラス一貫性 | 7 |
| TestWP822C | WARNING 継続処理 | 3 |

## 重要仕様メモ（例外型非対称）
- F10: ValueError (None/{}/short/missing goal_text)
- F30/F40: TypeError(非dict) + **ValueError**（field level、TypeError ではない）
- F90: ValueError(traceability_map欠損) + **TypeError**（hierarchy欠損）— 非対称
- F50/F90: RuntimeError(__cause__=KeyError/ZeroDivisionError) で原因保持
