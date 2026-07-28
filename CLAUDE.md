# AI-Agent-Dev-WBS-OS — Claude Code プロジェクト設定

## プロジェクト概要

F10→F90 AI パイプラインシステム。目的入力から WBS（Work Breakdown Structure）を自動生成する9段階のモジュールチェーン。

## フェーズ状態

| フェーズ | 状態 | 詳細 |
|---|---|---|
| Phase 1〜3 | 完了 | 実装層（F10〜F90 全モジュール） |
| **Phase 4** | **LOCKED（凍結）** | テスト層 WP8110〜WP8330 — 変更禁止 |
| **Phase 5** | **稼働中** | 運用層 — WP9100 監視設定完了 / WP9110 日常運用開始 / WP9120 HITL承認フロー完了 / WP9130 ログ確認完了（2026-07-22） |
| **Phase 6** | **稼働中** | 改善層 — WP9210 フィードバック収集完了 / WP9220 テンプレ改善完了 / WP9230 失敗知識蓄積完了（2026-07-22） |
| **Phase 6.5** | **稼働中** | 基盤維持層 — WP9300 WBS更新完了 / WP9310 WBS更新管理完了 / WP9320 OS更新判断完了（2026-07-22） |
| **知識循環統合** | **完了** | 運用・改善フェーズ統合保存完了 — KnowledgeCycle 実装 / index.yaml 生成 / Phase 7 READY フラグ確認済み（2026-07-22） |
| **Phase 7** | **完了** | 学習層 — WP9410 学習データ統合完了（48エントリ）/ WP9420 学習パターン生成完了（48パターン / MECE OK）/ WP9430 自己最適化評価完了（opt_avg=0.9119 / phase8_ready=True）（2026-07-22） |
| **Phase 8** | **完了** | 展開層 — 5ステージ全完了（F9510/F9520/F9530）/ HITL 全承認 / ロールバックなし / phase8_complete=True（2026-07-23） |
| **Phase 9** | **完了** | 完成層 — F9610 統合アーキテクチャ設計完了 / F9620 自律運用化完了（loop=3 / sandbox=PASSED）/ F9630 最終検証・承認完了（system_complete=True / opt=0.9119 / HITL 6/6承認）（2026-07-23） |
| **Phase 10** | **稼働中** | 運用監視・継続最適化層 — OS思想層固定済み（os_phase10_fixed=True / 6原則 / HITL 5ポイント）/ F10100 api_authentication_verification 完了（phase10_stage=api_verified / HITL H-P10-002 承認済み）/ F10110 daily_operation_monitoring_and_logging 完了（stability=0.9688 / HITL H-P10-003 承認済み）/ F10120 weekly_stability_report_generation 完了（weekly_index=0.97 / HITL H-P10-005 承認済み）/ F10130 continuous_optimization_cycle 完了（cycle_completed=True / HITL H-P10-004 承認済み）/ F10140 exception_detection_and_rollback_control 完了（phase10_stage=safety_reapproved / HITL H-P10-003 承認済み）（2026-07-23） |

## Phase 4 凍結ルール

**Phase 4 のファイルは変更禁止です。**

- `tests/phase4/` — テストファイル（変更禁止）
- `docs/phase4/` — ログ・レポート（変更禁止）
- 変更が必要な場合は Phase 5 の新規 WP として起票すること
- 詳細: [`docs/phase4/PHASE4_LOCK.md`](docs/phase4/PHASE4_LOCK.md)

## 主要レポート

| 種別 | パス |
|---|---|
| Phase 4 移行判定レポート（HTML） | [`docs/phase4/reports/wp8330_report.html`](docs/phase4/reports/wp8330_report.html) |
| Phase 4 移行判定レポート（JSON） | [`docs/phase4/reports/wp8330_report.json`](docs/phase4/reports/wp8330_report.json) |
| Phase 4 成果物インデックス | [`docs/phase4/INDEX.md`](docs/phase4/INDEX.md) |
| Phase 4 統合判定ログ | [`docs/phase4/logs/summary.log`](docs/phase4/logs/summary.log) |
| Visual Dashboard | https://claude.ai/code/artifact/7a059da6-7f09-4af0-bda4-a10ecdf85849 |

## パイプライン構成

```
F10（目的構造化）→ F20（目的展開）→ F30（目的要素評価）→ F40（タスク生成）→ F50（テンプレ適用）
→ F60（MECEチェック）→ F70（階層生成）→ F80（トレーサビリティ生成）→ F90（最終出力生成）
```

## セキュリティ方針（変更禁止）

- APIキーはコードに記述しない。HITL による手動入力のみ
- APIキーをログ・出力に表示しない
- `.env` ファイルは Git にコミットしない（`.gitignore` 適用済み）

## Phase 5 監視システム（WP9100）

| 項目 | 内容 |
|---|---|
| 監視設定 | [`docs/phase5/config/monitoring.yaml`](docs/phase5/config/monitoring.yaml) |
| 実装 | `src/monitoring/` （monitor.py / hitl_tracker.py / alert_rules.py） |
| テスト | `tests/phase5/test_9100_monitoring.py` — 57 passed |

アラートルール（有効）:
- **ERROR** → 即時通知
- **WARNING** → 5件連続で通知
- **RETRY** → 3回連続で通知
- **HITL** → 承認遅延30秒超過で通知

### WP9110 日常運用（稼働中）

`DailyOperationRunner` と `LogReviewer` による日次監視:

```python
from src.monitoring.daily_operation import DailyOperationRunner
runner = DailyOperationRunner()
run    = runner.run_pipeline(goal_text, api_mock=mock_fn)
review = runner.review_logs()
runner.write_daily_record(run, review)
```

異常検知閾値: ERROR≥3件 / HITL>10件 / RETRY>5件 → 異常アラート出力

使い方:
```python
from src.monitoring import install
handler = install()          # F10〜F90 の全ロガーに装着
handler.record_failsafe(module, trace_id, source_trace_id, estimated_effort)
handler.hitl_tracker.record_decision(module, element_id, "approve")
```

### WP9120 HITL承認フロー（完了）

`HITLApprovalFlow` による HITL 検出・承認判断・誤承認検知:

```python
from src.monitoring.hitl_approval import HITLApprovalFlow

flow = HITLApprovalFlow()
info = flow.detect_hitl("F10", module_output)   # HITL 不要なら None
if info:
    flow.submit_decision("F10", "E001", "approve", reason="内容確認済")
    # または "reject" / "reprocess"

summary = flow.get_session_summary()  # 承認率・誤承認警告
flow.write_approval_record()          # summary.log に追記
```

承認フロー機能:
- `detect_hitl(module, result)` — `hitl` / `hitl_required` フラグを検出
- `submit_decision(module, element_id, decision, reason)` — 判断を記録
- `get_session_summary()` — 承認率・誤承認警告（>90%）を集計
- `write_approval_record()` — summary.log に WP9120 承認記録を追記
- `over_max_reprocess(element_id)` — 再処理上限超過チェック（MAX=3）

誤承認検知閾値: 承認率 > 90% → `misapproval_warning = True`

### WP9130 ログ確認（完了）

`OperationalLogReview` による傾向分析・フェイルセーフ確認・安定性評価:

```python
from src.monitoring.log_review import OperationalLogReview

review   = OperationalLogReview()
counts   = review.collect_log_counts(log_path)
trend    = review.analyze_trends(log_path)
failsafe = review.summarize_failsafe(handler)         # MonitoringHandler を渡す
hitl     = review.summarize_hitl_approval(tracker)   # HITLTracker を渡す
stability = review.evaluate_stability(counts, failsafe, hitl)
review.write_review_record(counts, trend, failsafe, hitl, stability, log_path)
```

安定性評価:
- `stable`   — ERROR==0、かつ RETRY/HITL/誤承認が正常範囲内
- `warning`  — ERROR 1〜2件 / RETRY>5件 / HITL>10件 / 誤承認検知 / MAX_RETRY超過
- `critical` — ERROR 3件以上（即時対応要）

## Phase 6 改善層（WP9210〜）

### WP9210 フィードバック収集（完了）

`FeedbackCollector` による Phase 5 運用結果の集約・分析・出力:

```python
from src.improvement.feedback_collector import FeedbackCollector

fc = FeedbackCollector()
log_data      = fc.collect_from_log(log_path)
hitl_data     = fc.collect_from_hitl_tracker(tracker)
failsafe_data = fc.collect_from_monitor(handler)
report        = fc.analyze(log_data, hitl_data, failsafe_data)
fc.save_report(report)               # docs/phase6/feedback_report.json に保存
fc.write_summary_entry(report)       # summary.log に追記
```

改善候補の自動抽出ルール:
- RETRY率 > 10% → `RETRY閾値の見直し`
- フェイルセーフ率 > 5% → `API安定性の確認`
- 誤承認警告あり → `承認フローの見直し`
- HITL異常傾向 → `曖昧語辞書の精査`

出力物:
- [`docs/phase6/feedback_report.json`](docs/phase6/feedback_report.json) — 分析結果 JSON

### WP9220 テンプレ改善（完了）

`TemplateOptimizer` による feedback_report.json 反映・閾値調整・テンプレート構造確認:

```python
from src.improvement.template_optimizer import TemplateOptimizer

opt         = TemplateOptimizer()
feedback    = opt.load_feedback()
adjustments = opt.apply_threshold_adjustments(feedback)
summary     = opt.generate_optimization_summary(feedback, adjustments)
opt.save_thresholds(adjustments["updated_thresholds"])  # src/config/thresholds.yaml に保存
opt.write_summary_entry(summary)                        # summary.log に追記
```

管理ファイル:
- [`src/config/thresholds.yaml`](src/config/thresholds.yaml) — 全閾値設定（Phase 6 管理）
- [`src/templates/template_index.yaml`](src/templates/template_index.yaml) — テンプレート構造インデックス

### WP9230 失敗知識蓄積（完了）

`FailureRepository` による失敗事例登録・クラスタリング・防止パターン生成:

```python
from src.knowledge.failure_repository import FailureRepository

repo = FailureRepository()
repo.load_known_failures()           # Phase 4〜5 の既知事例（FL-001〜FL-005）を登録
for e in repo.extract_from_log(log_path):
    repo.register(e)                 # summary.log からの動的抽出
patterns = repo.generate_prevention_patterns()  # 防止パターン生成
repo.save_repository()               # docs/phase6/failure_repository.json に保存
repo.write_summary_entry()           # summary.log に追記
```

登録済み知識（FL-001〜FL-005）:
- FL-001: F10 曖昧語 HITL 発動
- FL-002: F10 API MAX_RETRY=3 超過 → RuntimeError
- FL-003: F60 cosine 0.80〜0.85 不確実域 → HITL_required
- FL-004: F80 不明 trace_id / 循環依存 → HITL 移譲
- FL-005: F40 タスク空 → HITL_required

防止パターン（PP-001〜PP-004）:
- PP-001: HITL 系 → HITL 移譲・ユーザー承認
- PP-002: RETRY 超過 → RuntimeError・即時停止
- PP-003: TRACE 不整合 → HITL 移譲・要素記録
- PP-004: ERROR 累積 → critical アラート・即時対応

出力物:
- [`docs/phase6/failure_repository.json`](docs/phase6/failure_repository.json) — Phase 7 学習層への引き渡しデータ

## 知識循環統合保存（KnowledgeCycle）

`KnowledgeCycle` による Phase 5〜6.5 成果物の統合管理・依存グラフ・インデックス保存:

```python
from src.knowledge.knowledge_cycle import KnowledgeCycle

kc      = KnowledgeCycle()
summary = kc.export_phase_summary()   # 全フェーズ成果物状態 + 依存グラフ
issues  = kc.validate_artifacts()     # 不足ファイルリスト（[] なら all_ok）
kc.save_cycle_index(summary)          # docs/knowledge_cycle/index.yaml に保存
kc.write_summary_entry(summary)       # summary.log に追記
```

管理フェーズ: Phase5 (6件) / Phase6 (7件) / Phase6.5 (5件) — 計18件
依存関係: Phase5←Phase4 / Phase6←Phase5 / Phase6.5←Phase5+Phase6 / Phase7←Phase6+Phase6.5

出力物:
- [`docs/knowledge_cycle/index.yaml`](docs/knowledge_cycle/index.yaml) — 統合インデックス（phase7_ready: true）

## Phase 7 学習層（WP9410）

### WP9410 学習データ統合（完了）

`LearningDatasetBuilder` による Phase 5〜6.5 蓄積知識の統合・因果分解・学習エントリ生成:

```python
from src.knowledge.learning_dataset import LearningDatasetBuilder

builder = LearningDatasetBuilder()
entries  = builder.build_from_failure_repository()   # FL-001〜FL-005 → 因果分解構造
entries += builder.extract_success_patterns_from_log()  # [PASS] 行 → 成功パターン
entries += builder.build_from_wbs_history()          # WBS差分 → 構造変化パターン
entries += builder.build_from_os_report()            # OS更新 → 環境変化パターン
dataset  = builder.compile_dataset(entries)
builder.save_dataset(dataset)               # docs/knowledge_cycle/learning_dataset.json
builder.write_summary_entry(dataset)        # summary.log に追記
```

学習エントリ構成（48件）:
- 運用パターン（operational）: 38件 — summary.log [PASS] 行から抽出
- 改善パターン（improvement）: 5件  — failure_repository.json から因果分解
- 基盤維持パターン（maintenance）: 1件 — wbs_history.log から構造変化
- 環境変化パターン（environment）: 4件 — os_update_report.json から抽出

`KnowledgeCycle` に追加された Phase 7 連携 I/O:

```python
from src.knowledge.knowledge_cycle import KnowledgeCycle

kc      = KnowledgeCycle()
ds      = kc.load_learning_dataset()           # learning_dataset.json を読み込む
targets = kc.get_learning_targets()            # 全学習エントリを返す
imp     = kc.get_learning_targets("improvement")  # カテゴリ絞り込み
```

出力物:
- [`docs/knowledge_cycle/learning_dataset.json`](docs/knowledge_cycle/learning_dataset.json) — 学習データセット（48エントリ / WP9420/9430 実行可）

### WP9420 学習パターン生成（完了）

`LearningPatternBuilder` による因果分解・MECE検証・スコア化・パターン統合:

```python
from src.knowledge.learning_pattern import LearningPatternBuilder

builder  = LearningPatternBuilder()
dataset  = builder.load_dataset()
patterns = builder.build_learning_patterns(dataset)  # 因果分解 + 重複除去 + スコア付与
mece     = builder.validate_mece_structure(patterns)  # 相互排他・網羅性チェック
result   = builder.export_patterns(patterns, mece)   # スコア統計・カテゴリ別集約
builder.save_patterns(result)            # docs/knowledge_cycle/learning_patterns.json
builder.write_summary_entry(result)      # summary.log に追記
```

生成パターン（48件）:
- スコア平均: 0.9750 / 高信頼度（≥0.9）: 44件 / 中信頼度: 4件 / 低信頼度: 0件
- MECE判定: OK（重複 0件 / 全4カテゴリ網羅）

`KnowledgeCycle` に追加された WP9430 連携 I/O:

```python
from src.knowledge.knowledge_cycle import KnowledgeCycle

kc = KnowledgeCycle()
all_patterns = kc.get_learning_patterns()                        # 全パターン
op_patterns  = kc.get_learning_patterns("operational")          # カテゴリ絞り込み
```

出力物:
- [`docs/knowledge_cycle/learning_patterns.json`](docs/knowledge_cycle/learning_patterns.json) — 学習パターン（48件 / WP9430 実行可）

### WP9430 自己最適化評価（完了）

`OptimizationEvaluator` による再現性・改善効果・最適化指数の定量評価:

```python
from src.knowledge.optimization_evaluator import OptimizationEvaluator

ev       = OptimizationEvaluator()
patterns = ev.load_patterns()
patterns = ev.evaluate_reproducibility(patterns)  # 再現性スコア付与
patterns = ev.evaluate_impact(patterns)           # 改善効果スコア付与
patterns = ev.calculate_optimization_index(patterns)  # opt_index + status
report   = ev.export_report(patterns)            # カテゴリ別集計・全体サマリー
ev.save_report(report)            # docs/knowledge_cycle/optimization_report.json
ev.write_summary_entry(report)    # summary.log に追記
```

評価結果（48パターン）:
- 再現性スコア平均: 0.9612 / 改善効果スコア平均: 0.8379 / 最適化指数平均: 0.9119
- stable: 43件 / warning: 1件 / critical: 4件（maintenance・environment 要注視）
- カテゴリ別: operational=0.9310 / improvement=0.9838 / maintenance=0.6760 / environment=0.6998

`KnowledgeCycle` に追加された Phase 8 連携 I/O:

```python
from src.knowledge.knowledge_cycle import KnowledgeCycle

kc     = KnowledgeCycle()
report = kc.get_optimization_report()  # optimization_report.json を読み込む
```

出力物:
- [`docs/knowledge_cycle/optimization_report.json`](docs/knowledge_cycle/optimization_report.json) — 最適化レポート（phase7_complete=True / phase8_ready=True）

## Phase 8 展開層

### 展開仕様（phase8_spec.json）

展開ステージ: limited_environment → trial_operation → evaluation → expansion → full_deployment
各ステージで HITL 承認必須。ロールバック方針: step_back_one_stage。

```python
from src.deployment.phase8_deployer import Phase8DeploymentManager

manager  = Phase8DeploymentManager()
arts     = manager.load_phase7_artifacts()      # Phase 7 成果物を読み込む
trace    = manager.run_full_deployment(          # 5ステージ一括実行
    hitl_fn=lambda stage: "approve"              # HITL 承認関数（実運用では手動入力）
)
manager.save_deployment_trace(trace)             # docs/phase8/deployment_trace.json
manager.save_rollback_log(trace["rollback_events"])  # docs/phase8/rollback_log.json
manager.write_phase8_complete_flag(trace)        # docs/phase8/phase8_complete_flag
manager.write_summary_entry(trace)               # summary.log に追記
```

展開モジュール:
- **F9510** `deployment_plan_design` — Phase 7 成果物検証・展開計画立案・I/O 整合性確認
- **F9520** `support_agent_integration` — サポートエージェント接続・failure_repository 同期・再現性 3回テスト
- **F9530** `deployment_test_and_stabilization` — ロードテスト・ロールバックテスト・最終安定性確認

展開結果:
- 全5ステージ HITL 承認 / ロールバック 0件 / phase8_complete=True
- F9510: io_integrity=100% / F9520: repro×3 passed / F9530: load_test + rollback_test passed

出力物:
- [`docs/phase8/phase8_spec.json`](docs/phase8/phase8_spec.json) — 展開仕様
- [`docs/phase8/deployment_trace.json`](docs/phase8/deployment_trace.json) — 展開トレース（全ステージ記録）
- [`docs/phase8/rollback_log.json`](docs/phase8/rollback_log.json) — ロールバックログ（0件）
- [`docs/phase8/phase8_complete_flag`](docs/phase8/phase8_complete_flag) — 完了フラグ

### F9510 deployment_plan_design（詳細仕様、完了）

`F9510DeploymentPlanDesigner` による8ステップ処理・3ファイル出力:

```python
from src.deployment.f9510_deployment_plan import F9510DeploymentPlanDesigner

designer = F9510DeploymentPlanDesigner()
result   = designer.run()
# result["success"] が True なら F9520 へ遷移
designer.write_summary_entry(result)   # summary.log に追記
designer.record_hitl_approval("limited_environment", "approve", "内容確認済み")
```

8ステップフロー:
1. `step1_load_spec()` — phase8_spec.json 読み込み・5段階構造解析
2. `step2_register_conditions(spec)` — 各段階の開始/完了条件を内部変数登録
3. `step3_check_io_integrity()` — learning_dataset / learning_patterns / optimization_report 存在確認
4. `step4_initialize_logging(io_r)` — I/O 整合性 OK→"normal" / 部分→"warning" / なし→"error"
5. `step5_mark_hitl_points(spec)` — 仕様 JSON から HITL 承認ポイント取得（5箇所）
6. `step6_init_rollback(spec)` — rollback_policy 読み込み・rollback_log.json 初期化
7. `step7_validate_consistency(spec, io_r, hitl_pts, policy)` — io=100% / hitl=5 / strategy / phase7_complete
8. `step8_generate_plan(...)` — deployment_plan dict 生成（phase8_stage="limited_environment"）

整合性エラー時: `docs/phase8/validation_error.json` を出力

出力ファイル:
- [`docs/phase8/deployment_plan.json`](docs/phase8/deployment_plan.json) — 展開計画書（io_integrity=100% / hitl_count=5）
- [`docs/phase8/deployment_trace.json`](docs/phase8/deployment_trace.json) — "F9510 executed successfully" 記録済み
- [`docs/phase8/hitl_checkpoint_log.json`](docs/phase8/hitl_checkpoint_log.json) — 5ステージ HITL チェックポイント（全 pending）

### F9520 support_agent_integration（詳細仕様、完了）

`F9520SupportAgentIntegration` による8ステップ処理・3ファイル出力:

```python
from src.deployment.f9520_support_agent import F9520SupportAgentIntegration

integrator = F9520SupportAgentIntegration()
result     = integrator.run()
# result["success"] が True なら F9530 へ遷移
integrator.write_summary_entry(result)   # summary.log に追記
integrator.record_hitl_approval("trial_operation", "approve", "内容確認済み")
```

8ステップフロー:
1. `step1_load_plan()` — deployment_plan.json 読み込み・I/O 構造解析
2. `step2_sync_repositories()` — failure_repository / knowledge_cycle 同期（最大3回リトライ）
3. `step3_apply_learning_outcomes()` — 学習成果（dataset/patterns/report）をエージェントへ適用
4. `step4_check_io_integrity(apply, sync)` — 双方向整合性チェック（閾値: 0.98）
5. `step5_reproducibility_test(apply)` — 再現性テスト3回連続成功確認
6. `step6_init_sync_log()` — sync_log.json 初期化
7. `step7_set_hitl_checkpoint()` — trial_operation ステージ HITL 承認ポイント設定
8. `step8_generate_report(...)` — integration_report.json 生成・展開トレース記録

エラー処理:
- I/O 整合性不一致 → ロールバック + HITL 通知
- failure_repository_sync_error → 最大3回リトライ
- knowledge_cycle_update_error → validation_error.json 出力
- 再現性失敗 → sandbox 停止 + HITL 承認待機

出力ファイル:
- [`docs/phase8/integration_report.json`](docs/phase8/integration_report.json) — 統合レポート（io_integrity=1.0 / repro_passed=True）
- [`docs/phase8/sync_log.json`](docs/phase8/sync_log.json) — "F9520 executed successfully" 記録済み
- [`docs/phase8/hitl_checkpoint_log.json`](docs/phase8/hitl_checkpoint_log.json) — trial_operation HITL チェックポイント

### F9530 deployment_test_and_stabilization（詳細仕様、完了）

`F9530DeploymentTestAndStabilization` による8ステップ処理・3ファイル出力・Phase 8 正式完了:

```python
from src.deployment.f9530_deployment_test import F9530DeploymentTestAndStabilization

tester = F9530DeploymentTestAndStabilization()
result = tester.run(hitl_fn=lambda: "approve")
# result["success"] かつ result["phase8_complete"] == True で Phase 9 へ遷移
tester.write_summary_entry(result)   # summary.log に追記
```

8ステップフロー:
1. `step1_load_and_integrate()` — 展開計画・連携結果・同期ログを読み込み、全環境状態を統合
2. `step2_load_test(state)` — ロードテスト（10リクエスト）/ I/O 整合性・エラー率・応答時間測定
3. `step3_monitor_exceptions(load)` — 異常停止・例外発生の有無を監視
4. `step4_reproducibility_test(load)` — 再現性テスト3回連続成功確認
5. `step5_evaluate_stability(load, mon, repro, state)` — error_rate / opt_score / log_completeness 算出
6. `step6_set_hitl_final_approval()` — full_deployment HITL 最終承認ポイント設定
7. `step7_generate_reports(...)` — stability_report.json / deployment_summary.json 生成
8. `step8_write_complete_flag(ds)` — phase8_complete_flag 書き込み・Phase 8 正式完了

安定性評価閾値:
- `io_integrity == 1.0` / `error_rate <= 0.01` / `opt_score >= 0.90` / `repro_passed == True`

エラー処理:
- `error_rate > 0.01` → ロールバック + HITL 通知
- `io_integrity < 1.0` → validation_error.json 出力
- 再現性失敗 → sandbox 停止 + 再試験要求
- HITL reject → 即時中断

実行結果: stability_status=stable / io_integrity=1.0 / opt_score=0.9119 / log_completeness=1.0

出力ファイル:
- [`docs/phase8/stability_report.json`](docs/phase8/stability_report.json) — 安定性レポート（stability_status=stable）
- [`docs/phase8/deployment_summary.json`](docs/phase8/deployment_summary.json) — 展開サマリー（phase8_complete=True）
- [`docs/phase8/hitl_final_approval_log.json`](docs/phase8/hitl_final_approval_log.json) — HITL 最終承認ログ（approve）

## Phase 9 完成層

### F9610 unified_architecture_design（完了）

`F9610UnifiedArchitectureDesigner` による8ステップ処理・4ファイル出力:

```python
from src.phase9.f9610_unified_architecture import F9610UnifiedArchitectureDesigner

designer = F9610UnifiedArchitectureDesigner()
result   = designer.run()
# result["success"] が True なら F9620 へ遷移
designer.write_summary_entry(result)
designer.record_hitl_approval("integration_design", "approve", "設計レビュー完了")
```

8ステップフロー:
1. `step1_load_phase8_outcomes()` — deployment_summary / stability_report / integration_report 読み込み
2. `step2_extract_agent_profiles(outcomes)` — AIWBS（F10〜F90）/ SUPPORT（F9510〜F9530）構造・I/O・責務を抽出
3. `step3_map_boundaries_and_flow(profiles)` — 境界（B-001〜B-002）/ 依存（D-001〜D-003）/ データ流通（DF-001〜DF-004）をマッピング
4. `step4_apply_design_rules(profiles, mapping)` — 5設計ルール（因果分解・MECE・責務分離・データ流通一貫性・HITL統合）を適用
5. `step5_generate_unified_architecture(...)` — unified_architecture.json 生成（統合構造・統合 HITL フロー）
6. `step6_generate_unified_io_map(...)` — unified_io_map.json 生成（全 I/O 整合性定義）
7. `step7_generate_integration_matrix(...)` — integration_matrix.json 生成（統合評価結果）
8. `step8_set_hitl_checkpoint(matrix)` — integration_design ステージ HITL 承認ポイント設定

統合対象エージェント:
- **AIWBS**: F10〜F90（9モジュール）/ WBS 生成・MECE 検証・トレーサビリティ
- **SUPPORT**: F9510〜F9530（3モジュール）/ 展開計画・サポート統合・安定化
- **共有ストア**: `docs/knowledge_cycle/`（唯一のデータストア）

実行結果: io_integrity=1.0 / all_rules_passed=True / mece_ok=True / resp_conflict=False / overall_ok=True

出力ファイル:
- [`docs/phase9/unified_architecture.json`](docs/phase9/unified_architecture.json) — 統合アーキテクチャ（AIWBS+SUPPORT+統合 HITL フロー）
- [`docs/phase9/unified_io_map.json`](docs/phase9/unified_io_map.json) — 統合 I/O マップ（io_integrity=1.0）
- [`docs/phase9/integration_matrix.json`](docs/phase9/integration_matrix.json) — 統合評価結果（overall_ok=True）
- [`docs/phase9/hitl_checkpoint_log.json`](docs/phase9/hitl_checkpoint_log.json) — integration_design HITL チェックポイント

### F9620 autonomous_operation_enablement（完了）

`F9620AutonomousOperationEnabler` による8ステップ処理・4ファイル出力:

```python
from src.phase9.f9620_autonomous_operation import F9620AutonomousOperationEnabler

enabler = F9620AutonomousOperationEnabler()
result  = enabler.run()
# result["success"] が True なら F9630 へ遷移
enabler.write_summary_entry(result)
enabler.record_hitl_approval("autonomous_operation", "approve", "プロファイル確認済み")
```

8ステップフロー:
1. `step1_load_unified_artifacts()` — unified_architecture / io_map / integration_matrix 読み込み
2. `step2_design_control_loops(arts)` — 3制御ループ定義（L-001 WBS生成 / L-002 展開安定化 / L-003 知識循環）
3. `step3_reconstruct_hitl_flow(loops)` — 6 HITL ポイント + 4自律ルール（AR-001〜AR-004）を再構成
4. `step4_link_knowledge_stores()` — knowledge_cycle（3ファイル）/ failure_repository を接続
5. `step5_set_initial_parameters()` — optimization_report から閾値を設定（opt_score=0.9119）
6. `step6_generate_control_loop_config(...)` — control_loop_config.json 生成
7. `step7_run_sandbox_trial(config, links)` — sandbox 試験3回連続成功確認
8. `step8_generate_profile(...)` — autonomous_operation_profile.json 生成

実行結果: loop=3 / hitl_flow_defined=True / kc_linked=True / repo_linked=True / sandbox=PASSED(3/3) / config_consistent=True

出力ファイル:
- [`docs/phase9/autonomous_operation_profile.json`](docs/phase9/autonomous_operation_profile.json) — 自律運用プロファイル
- [`docs/phase9/control_loop_config.json`](docs/phase9/control_loop_config.json) — 制御ループ設定（3ループ全定義）
- [`docs/phase9/hitl_autonomy_flow.json`](docs/phase9/hitl_autonomy_flow.json) — 自律運用 HITL フロー（6ポイント）
- [`docs/phase9/runtime_observation_log.json`](docs/phase9/runtime_observation_log.json) — sandbox 試験記録（3/3 PASS）

### F9630 final_validation_and_approval（完了）

`F9630FinalValidationAndApproval` による最終検証・HITL 6ポイント承認・system_complete_flag 書き込み:

```python
from src.phase9.f9630_final_validation import F9630FinalValidationAndApproval

validator = F9630FinalValidationAndApproval()
result    = validator.run(hitl_fn=lambda point_id: "approve")
# result["success"] かつ result["system_complete"] が True で Claude Code 正式完了
validator.write_summary_entry(result)
```

8ステップフロー:
1. `step1_load_and_extract_metrics()` — Phase 9 入力5ファイル読み込み・sandbox_ok / loop_count / config_consistent 抽出
2. `step2_verify_structural_consistency(metrics)` — arch.agents / loop_count / matrix.overall_ok 照合
3. `step3_verify_knowledge_cycle()` — cycle 3ファイル + failure_repository 存在確認
4. `step4_evaluate_optimization_score()` — optimization_report avg ≥ 0.90 検証
5. `step5_confirm_hitl_approvals(hitl_fn)` — H-001〜H-006 の6ポイント承認取得
6. `step6_generate_final_report(...)` — final_validation_report.json 生成
7. `step7_generate_completion_summary(...)` — Phase 1〜9 全フェーズ統合サマリー生成
8. `step8_write_system_complete_flag(summary)` — system_complete_flag 書き込み

実行結果: success=True / system_complete=True / opt=0.9119 / HITL 6/6承認 / io_integrity=1.0 / repro=PASSED

出力ファイル:
- [`docs/phase9/final_validation_report.json`](docs/phase9/final_validation_report.json) — 最終検証レポート（all_passed=True）
- [`docs/phase9/hitl_final_approval_log.json`](docs/phase9/hitl_final_approval_log.json) — HITL 最終承認ログ（6/6承認）
- [`docs/phase9/system_complete_flag`](docs/phase9/system_complete_flag) — **Claude Code 完成フラグ（system_complete: true）**
- [`docs/phase9/completion_summary.json`](docs/phase9/completion_summary.json) — Phase 1〜9 完了統合サマリー

## Phase 10 運用監視・継続最適化層

### OS 三層構造（思想層 固定済み）

| 層 | ファイル | 状態 |
|---|---|---|
| **思想層（OS）** | [`docs/phase10/os_phase10_philosophy.yaml`](docs/phase10/os_phase10_philosophy.yaml) | **固定済み** |
| 構造層 | `docs/phase10/os_phase10_structure.yaml` | 設計待ち |
| 実装層 | `src/phase10/` (F10100〜F10140) | 実装待ち |

**6つの運用原則（思想層固定）**:

| 優先度 | 原則 | 概要 |
|---|---|---|
| 1 | `stability_first` | エラー率 ≤ 0.01 / rollback=0 / knowledge_cycle 監視 |
| 2 | `hitl_continuity` | 重要判断は HITL 必須（5ポイント） |
| 3 | `continuous_optimization` | knowledge_cycle / failure_repository / optimization_report |
| 4 | `transparency` | 日次・週次ログ / HITL承認ログ |
| 5 | `reproducibility` | sandbox 連続3回成功必須 |
| 6 | `safety` | 例外 → 即 rollback / HITL 未承認なら自律進行停止 |

**HITL ポイント（5箇所）**:
- H-P10-001: 再学習方向性の決定
- H-P10-002: 外部API連携の安全確認
- H-P10-003: 異常検知時の判断
- H-P10-004: 最適化閾値の変更
- H-P10-005: 運用レポートの承認

**Phase 9 → Phase 10 継承**:
- `docs/phase9/system_complete_flag` — system_complete: true 確認済み
- `docs/phase9/unified_architecture.json` — 統合設計の基盤
- `docs/phase9/control_loop_config.json` — 制御ループ（3ループ）
- `docs/knowledge_cycle/optimization_report.json` — opt_score=0.9119
- `docs/phase6/failure_repository.json` — 失敗知識（FL-001〜FL-005）

**モジュール状況**:

| モジュール | 機能 | 状態 |
|---|---|---|
| F10100 | 外部API認証テスト（safety原則の入口） | **完了** |
| F10110 | 日次運用監視 | **完了** |
| F10120 | 週次安定性レポート | **完了** |
| F10130 | 継続最適化サイクル | **完了** |
| F10140 | 例外検知・rollback制御 | **完了** |

### F10100 api_authentication_verification（完了）

`F10100ApiAuthVerification` による7ステップ処理・3ファイル出力:

```python
from src.phase10.f10100_api_auth import F10100ApiAuthVerification

v = F10100ApiAuthVerification()
result = v.run(
    api_mock=None,       # None のとき実 API を呼ぶ（CLAUDE_API_KEY 必須）
    hitl_fn=lambda _: "approve",  # HITL 承認関数
)
v.write_summary_entry(result)
# result["success"] が True かつ result["phase10_stage"] == "api_verified" で F10110 へ
```

7ステップフロー:
1. `step1_check_env_key()` — CLAUDE_API_KEY 環境変数の存在確認（値参照なし）
2. `step2_send_ping(api_mock)` — API ping 送信（mock 対応 / API キーはログに出力しない）
3. `step3_determine_status(ping)` — 認証ステータス判定（authenticated / failed）
4. `step4_check_latency(ping)` — レイテンシ測定・閾値チェック（< 2.0s）
5. `step5_verify_error_count(ping)` — error_count == 0 検証
6. `step6_generate_report(ping, latency_warning)` — api_auth_report.json / api_auth_log.json 生成
7. `step7_set_hitl_checkpoint(report, hitl_fn, latency_warning)` — HITL H-P10-002 承認

エラーパス:
- `api_key_missing` → 停止 + HITL 通知（validation_error.json）
- `authentication_failed` → ロールバック相当記録（validation_error.json）
- `latency_high` → 警告 + HITL 通知（成功扱いで継続）
- `error_count > 0` → validation_error.json 出力 + 停止

実行結果: success=True / phase10_stage=api_verified / auth_status=authenticated / HITL H-P10-002 approve

出力ファイル:
- [`docs/phase10/api_auth_report.json`](docs/phase10/api_auth_report.json) — 認証レポート（auth_status=authenticated）
- [`docs/phase10/api_auth_log.json`](docs/phase10/api_auth_log.json) — 実行ログ（7ステップ）
- [`docs/phase10/hitl_api_approval_log.json`](docs/phase10/hitl_api_approval_log.json) — HITL H-P10-002 承認ログ

### F10110 daily_operation_monitoring_and_logging（完了）

`F10110DailyMonitoring` による7ステップ処理・3ファイル出力:

```python
from src.phase10.f10110_daily_monitoring import F10110DailyMonitoring

m = F10110DailyMonitoring()
result = m.run(
    system_status_fn=None,         # None のとき内部デフォルト状態を使用
    repro_test_fn=lambda: 1.0,     # 再現性テスト関数（0.0〜1.0）
    hitl_fn=lambda _: "approve",   # HITL 承認関数
    previous_log=None,             # 前日ログ dict（省略時はファイルを試みる）
)
m.write_summary_entry(result)
# result["success"] が True かつ result["phase10_stage"] == "daily_monitoring_verified" で F10120 へ
```

7ステップフロー:
1. `step1_load_previous_logs(prev)` — 前日ログを読み込み、異常値（stability低下・エラー・HITL未承認）を検出
2. `step2_get_system_status(fn)` — 稼働率・エラー率・レイテンシを取得
3. `step3_calculate_stability(status)` — stability_index = uptime × (1-error_rate) × latency_score を算出
4. `step4_reproducibility_test(fn)` — 同条件再実行テスト（出力一致率 >= 0.95 必須）
5. `step5_safety_check(status)` — API 認証状態・例外発生有無を検証（api_auth_report.json を参照）
6. `step6_generate_daily_log(...)` — daily_operation_log.json / stability_report.json を生成
7. `step7_set_hitl_checkpoint(report, fn, stability, repro)` — HITL H-P10-003 承認

検証閾値: stability_index >= 0.90 / reproducibility_rate >= 0.95 / error_count == 0 / api_auth == "authenticated"

エラーパス:
- `error_count > 0` → exception_log.json 出力 + 停止
- `api_auth_status != "authenticated"` → 停止（F10100 再試験要求）
- `reproducibility_rate < 0.95` → 停止（再試験要求）
- `hitl_reject` → 承認待機

実行結果: success=True / phase10_stage=daily_monitoring_verified / stability_index=0.9688 / HITL H-P10-003 approve

出力ファイル:
- [`docs/phase10/daily_operation_log.json`](docs/phase10/daily_operation_log.json) — 日次運用ログ
- [`docs/phase10/stability_report.json`](docs/phase10/stability_report.json) — 安定性レポート（stability_index=0.9688）
- [`docs/phase10/hitl_monitoring_approval_log.json`](docs/phase10/hitl_monitoring_approval_log.json) — HITL H-P10-003 承認ログ

### F10120 weekly_stability_report_generation（完了）

`F10120WeeklyReport` による7ステップ処理・3ファイル出力:

```python
from src.phase10.f10120_weekly_report import F10120WeeklyReport

r = F10120WeeklyReport()
result = r.run(
    daily_logs=seven_logs,         # 過去7日分の daily_operation_log dict リスト（省略時はファイルを試みる）
    repro_test_fn=lambda: 1.0,     # 再現性テスト関数（0.0〜1.0）
    hitl_fn=lambda _: "approve",   # HITL 承認関数
)
r.write_summary_entry(result)
# result["success"] かつ result["phase10_stage"] == "weekly_stability_verified" で F10130 へ
```

7ステップフロー:
1. `step1_aggregate_daily_logs(daily_logs)` — 過去7日分ログを集計（稼働率・エラー率・レイテンシ・error_count合計）
2. `step2_calculate_weekly_stability(logs, agg)` — stability_index の週次平均を算出（>= 0.92 必須）
3. `step3_reproducibility_test(fn)` — 週次サンプル再現性テスト（>= 0.95 必須）
4. `step4_safety_check(logs)` — 最新ログ / api_auth_report.json から api_auth_status を検証
5. `step5_generate_weekly_report(...)` — weekly_stability_report.json 生成
6. `step6_generate_optimization_summary(...)` — 改善提案（閾値調整・再学習候補）を optimization_summary.json に出力
7. `step7_set_hitl_checkpoint(report, fn, index, repro)` — HITL H-P10-005 承認

エラーパス:
- `error_count > 0` → exception_log.json + 停止
- `api_auth_status != "authenticated"` → 停止（F10100 再試験要求）
- `reproducibility_rate < 0.95` → 停止（再試験要求）
- `hitl_reject` → 承認待機

実行結果: success=True / phase10_stage=weekly_stability_verified / weekly_stability_index=0.97 / HITL H-P10-005 approve

出力ファイル:
- [`docs/phase10/weekly_stability_report.json`](docs/phase10/weekly_stability_report.json) — 週次安定性レポート（weekly_index=0.97）
- [`docs/phase10/optimization_summary.json`](docs/phase10/optimization_summary.json) — 改善提案（no_action_required_system_stable）
- [`docs/phase10/hitl_weekly_approval_log.json`](docs/phase10/hitl_weekly_approval_log.json) — HITL H-P10-005 承認ログ

### F10130 continuous_optimization_cycle（完了）

`F10130OptimizationCycle` による7ステップ処理・4ファイル出力:

```python
from src.phase10.f10130_optimization_cycle import F10130OptimizationCycle

o = F10130OptimizationCycle()
result = o.run(
    weekly_report=None,          # 省略時は weekly_stability_report.json を読み込む
    opt_summary=None,            # 省略時は optimization_summary.json を読み込む
    failure_repo=None,           # 省略時は failure_repository.json を読み込む
    hitl_fn=lambda _: "approve", # HITL 承認関数
)
o.write_summary_entry(result)
# result["success"] かつ result["phase10_stage"] == "optimization_cycle_verified" で F10140 へ
```

7ステップフロー:
1. `step1_load_weekly_report(report)` — weekly_stability_report.json を解析
2. `step2_extract_proposals(summary)` — optimization_summary.json から改善項目を抽出
3. `step3_analyze_failure_repository(repo)` — failure_repository.json から再発防止策を生成
4. `step4_threshold_adjustment(report, proposals)` — 閾値を保守的に調整（±0.01 / 下限 0.80）
5. `step5_retraining_trigger(report, proposals)` — 再学習必要性を判定（上限 1 回）
6. `step6_generate_cycle_log(...)` — optimization_cycle_log.json を生成
7. `step7_set_hitl_checkpoint(log, fn, adj)` — HITL H-P10-004 承認

エラーパス:
- `threshold_adjustment_invalid` → validation_error.json + 停止
- `retraining_triggered > 1` → 自律ループ停止
- `hitl_reject` → 承認待機

実行結果: success=True / phase10_stage=optimization_cycle_verified / cycle_completed=True / HITL H-P10-004 approve

出力ファイル:
- [`docs/phase10/optimization_cycle_log.json`](docs/phase10/optimization_cycle_log.json) — サイクルログ（cycle_completed=True）
- [`docs/phase10/threshold_adjustment_report.json`](docs/phase10/threshold_adjustment_report.json) — 閾値調整レポート
- [`docs/phase10/retraining_trigger.json`](docs/phase10/retraining_trigger.json) — 再学習トリガー（triggered=0）
- [`docs/phase10/hitl_optimization_approval_log.json`](docs/phase10/hitl_optimization_approval_log.json) — HITL H-P10-004 承認ログ

### F10140 exception_detection_and_rollback_control（完了）

`F10140ExceptionRollback` による7ステップ処理・4ファイル出力。Phase 10 安全閉鎖の最終工程:

```python
from src.phase10.f10140_exception_rollback import F10140ExceptionRollback

er = F10140ExceptionRollback()
result = er.run(
    daily_log=None,          # 省略時は daily_operation_log.json を読み込む
    weekly_report=None,      # 省略時は weekly_stability_report.json を読み込む
    cycle_log=None,          # 省略時は optimization_cycle_log.json を読み込む
    exception_history=None,  # 省略時は exception_log.json を試みる
    hitl_fn=lambda _: "approve",
)
er.write_summary_entry(result)
# result["phase10_stage"] == "safety_reapproved" が Phase 10 安全閉鎖の最終フラグ
```

7ステップフロー:
1. `step1_detect_anomalies(daily, weekly)` — error_count / latency_spike / stability_drop / 前日引継ぎを検出
2. `step2_check_post_optimization(cycle)` — 最適化後の再学習・閾値変更による例外を確認
3. `step3_classify_exception_patterns(history)` — 例外パターンを type / frequency / impact で分類
4. `step4_select_rollback_strategy(anomalies, post_opt, patterns)` — none / partial / full / config_restore を選択
5. `step5_execute_rollback(strategy, required)` — rollback を実行し last_stable_state を復元
6. `step6_generate_reports(...)` — exception_detection_report / rollback_action_log / safety_reapproval_log を生成
7. `step7_set_hitl_checkpoint(report, fn, rollback)` — HITL H-P10-003 承認

rollback 戦略:
- `none` — 異常なし（rollback 不要）
- `partial` — 軽微な異常（latency_spike / post_opt）
- `full` — 重大な異常（error_count_critical / stability_drop）
- `config_restore` — 閾値変更後の例外

エラーパス:
- `rollback_failed` → critical_alert_log.json + 停止
- `last_stable_state_not_found` → safety_mode 移行 + 停止
- `error_count_after_rollback > 0` → validation_error.json + 停止
- `hitl_reject` → 制限モード継続

実行結果: success=True / phase10_stage=safety_reapproved / anomalies=0 / rollback=none / HITL H-P10-003 approve

出力ファイル:
- [`docs/phase10/exception_detection_report.json`](docs/phase10/exception_detection_report.json) — 例外検知レポート（anomalies=[]）
- [`docs/phase10/rollback_action_log.json`](docs/phase10/rollback_action_log.json) — rollback 実行ログ（strategy=none）
- [`docs/phase10/safety_reapproval_log.json`](docs/phase10/safety_reapproval_log.json) — 安全性再承認ログ（safety_status=safe）
- [`docs/phase10/hitl_safety_approval_log.json`](docs/phase10/hitl_safety_approval_log.json) — HITL H-P10-003 承認ログ

## テスト実行

```bash
# Phase 4 全テスト（凍結状態の確認用 — 変更せず実行のみ）
python -m pytest tests/phase4/ --tb=short -q
```

期待結果: **1,067 passed, 1 skipped, 0 failed**

```bash
# Phase 5 監視テスト
python -m pytest tests/phase5/ --tb=short -q
```

期待結果: **180 passed, 0 failed**

```bash
# Phase 6 改善テスト
python -m pytest tests/phase6/ --tb=short -q
```

期待結果: **373 passed, 0 failed**

```bash
# Phase 8 展開テスト
python -m pytest tests/phase8/ --tb=short -q
```

期待結果: **277 passed, 0 failed**

```bash
# Phase 9 完成テスト
python -m pytest tests/phase9/ --tb=short -q
```

期待結果: **263 passed, 0 failed**

```bash
# Phase 10 テスト
python -m pytest tests/phase10/ --tb=short -q
```

期待結果: **305 passed, 0 failed**

## フォルダ構成

```
AI-Agent-Dev-WBS-OS/
├── CLAUDE.md                          ← このファイル
├── src/agents/                        ← F10〜F90 実装
├── tests/phase4/                      ← Phase 4 テストファイル（凍結）
├── src/monitoring/                    ← Phase 5 監視モジュール（WP9100〜WP9130）
├── src/improvement/                   ← Phase 6 改善モジュール（WP9210〜WP9220）
├── src/knowledge/                     ← Phase 6 知識モジュール（WP9230〜）
├── src/management/                    ← Phase 6.5 WBS管理モジュール（WP9310）
├── src/system/                        ← Phase 6.5 OS更新判断モジュール（WP9320）
├── src/config/thresholds.yaml         ← 全閾値設定（WP9220）
├── src/templates/template_index.yaml  ← テンプレート構造インデックス（WP9220）
├── tests/phase5/                      ← Phase 5 テスト（180件）
├── tests/phase6/                      ← Phase 6+6.5+知識循環+Phase7 テスト（373件）
├── docs/phase5/config/monitoring.yaml ← 監視設定
├── docs/wbs_structure.yaml            ← WBS構造定義（WP9300）
├── docs/wbs_history.log               ← WBS更新履歴（WP9310）
├── docs/phase6/feedback_report.json   ← WP9210 フィードバックレポート
├── docs/phase6/failure_repository.json ← WP9230 失敗知識リポジトリ（Phase 7 引き渡し）
├── docs/system/os_update_report.json  ← WP9320 OS更新レポート
├── docs/knowledge_cycle/index.yaml    ← 知識循環統合インデックス（KnowledgeCycle）
├── docs/knowledge_cycle/learning_dataset.json ← WP9410 学習データセット（48エントリ）
├── docs/knowledge_cycle/learning_patterns.json ← WP9420 学習パターン（48件 / MECE OK）
├── docs/knowledge_cycle/optimization_report.json ← WP9430 最適化レポート（phase8_ready=True）
├── docs/phase8/phase8_spec.json               ← Phase 8 展開仕様
├── docs/phase8/deployment_trace.json          ← 展開トレース（5ステージ全完了）
├── docs/phase8/rollback_log.json              ← ロールバックログ（0件）
├── docs/phase8/phase8_complete_flag           ← Phase 8 完了フラグ
├── src/deployment/phase8_deployer.py          ← Phase 8 展開マネージャー
├── src/deployment/f9510_deployment_plan.py   ← F9510 展開計画設計（8ステップ）
├── src/deployment/f9520_support_agent.py     ← F9520 サポートエージェント統合（8ステップ）
├── src/deployment/f9530_deployment_test.py  ← F9530 展開テスト・安定化（8ステップ）
├── docs/phase8/deployment_plan.json          ← F9510 展開計画書
├── docs/phase8/hitl_checkpoint_log.json      ← HITL チェックポイントログ（F9510〜F9530）
├── docs/phase8/integration_report.json       ← F9520 統合レポート
├── docs/phase8/sync_log.json                 ← F9520 同期ログ
├── docs/phase8/stability_report.json         ← F9530 安定性レポート（stability=stable）
├── docs/phase8/deployment_summary.json       ← F9530 展開サマリー（phase8_complete=True）
├── docs/phase8/hitl_final_approval_log.json  ← F9530 HITL 最終承認ログ
├── tests/phase8/                              ← Phase 8 テスト（277件）
├── src/phase9/f9610_unified_architecture.py  ← F9610 統合アーキテクチャ設計（8ステップ）
├── docs/phase9/unified_architecture.json     ← F9610 統合アーキテクチャ（AIWBS+SUPPORT）
├── docs/phase9/unified_io_map.json           ← F9610 統合 I/O マップ（io_integrity=1.0）
├── docs/phase9/integration_matrix.json       ← F9610 統合評価結果（overall_ok=True）
├── docs/phase9/hitl_checkpoint_log.json      ← F9610 HITL チェックポイント
├── src/phase9/f9620_autonomous_operation.py  ← F9620 自律運用化（8ステップ）
├── docs/phase9/autonomous_operation_profile.json ← F9620 自律運用プロファイル
├── docs/phase9/control_loop_config.json     ← F9620 制御ループ設定（3ループ）
├── docs/phase9/hitl_autonomy_flow.json      ← F9620 自律運用 HITL フロー（6ポイント）
├── docs/phase9/runtime_observation_log.json ← F9620 sandbox 試験記録
├── src/phase9/f9630_final_validation.py     ← F9630 最終検証・承認（8ステップ）
├── docs/phase9/final_validation_report.json ← F9630 最終検証レポート（all_passed=True）
├── docs/phase9/hitl_final_approval_log.json ← F9630 HITL 最終承認ログ（6/6承認）
├── docs/phase9/system_complete_flag         ← F9630 Claude Code 完成フラグ（system_complete: true）
├── docs/phase9/completion_summary.json      ← F9630 Phase 1〜9 完了統合サマリー
├── tests/phase9/                              ← Phase 9 テスト（263件）
├── docs/phase10/os_phase10_philosophy.yaml   ← Phase 10 OS 思想層（固定済み / 6原則 / HITL 5ポイント）
├── docs/phase10/OS_LAYER.md                  ← Phase 10 OS 三層構造概要
├── src/phase10/__init__.py                   ← Phase 10 実装層（F10100〜F10140 実装待ち）
└── docs/phase4/
    ├── INDEX.md                       ← 成果物マスターインデックス
    ├── PHASE4_LOCK.md                 ← 凍結宣言
    ├── WP8330_TRANSITION_JUDGMENT.md  ← 移行判定正式記録
    ├── tests/                         ← WP別参照インデックス
    ├── logs/                          ← テストログ群
    │   └── summary.log                ← 統合判定ログ（Phase 5 引き継ぎ用）
    └── reports/
        ├── wp8330_report.html         ← メインレポート
        └── wp8330_report.json         ← 構造化データ
```
