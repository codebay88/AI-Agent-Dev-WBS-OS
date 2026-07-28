# WP8130 MECEチェックテスト — 参照インデックス

**実体ファイル:** `tests/phase4/test_8130_mece.py`  
**テストログ:** `docs/phase4/logs/test_8130_mece_log.txt`  
**結果:** 87 passed / 0 failed  

## テストクラス一覧

| クラス | 対象 | テスト数 |
|---|---|---|
| TestWP8131_MutuallyExclusive | 重複検出・排他性 | 17 |
| TestWP8132_CollectivelyExhaustive | 網羅性・欠損検出 | 13 |
| TestWP8133_MECEBoundaryValues | 閾値境界値（cos=0.80/0.85） | 9 |
| TestWP8134_AmbiguousDetection | 曖昧語検出 | 8 |
| TestWP8135_MECECompliance | MECE適合判定 | 8 |
| TestWP8136_HITLFlow | HITL発動条件 | 10 |
| TestWP8137_CrossModuleMECE | モジュール間一意性 | 8 |
| TestWP8138_MECEAbnormal | 異常系テスト | 11 |

## 重要仕様メモ
- cos=0.85 **超過**のみが duplicate（境界値 0.85 は duplicate ではない）
- duplicate-only は HITL を**発動しない**（uncertain/ambiguous のみ発動）
