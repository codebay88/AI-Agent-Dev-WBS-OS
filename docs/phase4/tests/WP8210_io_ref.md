# WP8210 I/O連携テスト — 参照インデックス

**実体ファイル:** `tests/phase4/test_8210_io.py`  
**テストログ:** `docs/phase4/logs/test_8210_io_log.txt`  
**結果:** 150 passed / 0 failed  

## 検証内容
- F10→F90 全モジュール間の I/O データ型・キー名・チェーン整合性
- trace_id / source_trace_id 連鎖（F10=F10, F20.source=F10, ...）
- F60 templated_tasks パススルー同一性
- F80 hierarchy パススルー同一性
- estimated_effort → effort キー変換（F40→F50）
