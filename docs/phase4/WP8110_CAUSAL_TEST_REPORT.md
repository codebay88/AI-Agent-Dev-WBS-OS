# WP8110 因果分解テスト 完了レポート

**実施日時:** 2026-07-21  
**テストファイル:** `tests/phase4/test_8110_causal.py`  
**テスト結果:** ✅ **116 passed / 116 件（0 failed）**  
**詳細ログ:** `docs/phase4/test_8110_causal_log.txt`

---

## 1. 因果構造マップ（検証済み）

| モジュール | 原因（Cause） | 中間処理（Process） | 結果（Effect） | 判定 |
|---|---|---|---|---|
| F10 | `goal_text`（目標テキスト） | `_call_api` → `_parse_response` → `_build_tree` | `goal`（L1/L2/L3）＋ `tree`（objective_id付き階層） | ✅ |
| F20 | `goal.L1/L2/L3` ＋ `tree` | `_expand_goals` | `expanded_goals`（element_id付きフラットリスト） | ✅ |
| F30 | `expanded_goals`（text/parent） | `_score_importance` / `_score_feasibility` → `_classify_priority` | `evaluated_goals`（score＋priority付きリスト） | ✅ |
| F40 | `evaluated_goals`（score/priority） | `_calc_effort` / `_calc_value` → `_generate_task` | `tasks`（estimated_effort/estimated_value付き） | ✅ |
| F50 | `tasks`（priority） | `_apply_template`（TMP_HIGH/MEDIUM/LOW） | `templated_tasks`（templated_text/template_id） | ✅ |
| F60 | `templated_tasks` | `_detect_duplicates` / `_detect_missing` / `_detect_ambiguous` | `mece_report`（is_mece_compliant/dup/missing/ambig） | ✅ |
| F70 | `templated_tasks`（類似度） | `_union_find_group` → `_group_by_element` | `hierarchy`（goals/elements/tasks の3階層） | ✅ |
| F80 | `hierarchy`（goals/elements/tasks） | `_build_trace_chain` → `_build_trace_entry` | `traceability_map`（trace_chain/is_complete） | ✅ |
| F90 | `traceability_map` ＋ `hierarchy` | `_merge_hierarchy_with_trace` → `_compute_evaluation` → `_generate_recommendations` | `final_output`（summary/hierarchy_with_trace/evaluation_report） | ✅ |

---

## 2. テスト区分別 結果

| テストクラス | 件数 | 合格 | 判定 |
|---|---|---|---|
| TestCausal_F10（F10 因果分解） | 11 | 11 | ✅ |
| TestCausal_F20（F20 因果分解） | 10 | 10 | ✅ |
| TestCausal_F30（F30 因果分解） | 13 | 13 | ✅ |
| TestCausal_F40（F40 因果分解） | 10 | 10 | ✅ |
| TestCausal_F50（F50 因果分解） | 10 | 10 | ✅ |
| TestCausal_F60（F60 因果分解） | 9 | 9 | ✅ |
| TestCausal_F70（F70 因果分解） | 8 | 8 | ✅ |
| TestCausal_F80（F80 因果分解） | 10 | 10 | ✅ |
| TestCausal_F90（F90 因果分解） | 12 | 12 | ✅ |
| TestCausal_ChainIntegrity（連鎖不断性） | 23 | 23 | ✅ |
| **合計** | **116** | **116** | ✅ |

---

## 3. 判定基準 チェックリスト

| 判定基準 | 結果 |
|---|---|
| 原因 → 処理 → 結果 の流れが仕様どおりであること | ✅ 全9モジュール確認済み |
| 中間処理が省略されていないこと（INFOログで確認） | ✅ F10〜F90 全モジュールの `[Fxx]` INFO ログを確認 |
| 出力が因果構造の結果として妥当であること | ✅ 各フィールド型・値・範囲を検証 |
| 異常系で因果チェーンが破綻せず例外処理が発火すること | ✅ TypeError/ValueError/RuntimeError 全件確認 |
| HITL系で人間承認フローが正しく発動すること | ✅ F30/F50/F90 HITL発動を確認 |
| 因果チェーン（F10→F90）が途切れないこと | ✅ source_trace_id リンクを全隣接ペアで確認 |

---

## 4. テスト中に発見した仕様理解の誤り（テスト設計誤りとして是正済み）

> **分類: 不具合（Bug）ではない — テスト設計誤り（Test Design Error）として記録**

| 誤り | 正しい仕様 | 是正方法 |
|---|---|---|
| F10 に `None` を渡すと `TypeError` と仮定 | 実際は `ValueError` が発生（`dict 形式必須`のチェックが先） | テストを `ValueError` に変更 |
| F30 出力キーを `evaluated_elements` と仮定 | 実際は `evaluated_goals` | テストのキー名を修正 |
| F30 HITLトリガーに `ABSTRACT_WORDS` を使用 | F30 の HITL チェックは `AMBIGUOUS_WORDS`（"など"等）を使用；ABSTRACT_WORDS（"改善"等）はスコアペナルティに使用 | テストを `AMBIGUOUS_WORDS[0]` に変更 |
| F40 タスクに `effort`/`value` キーを期待 | 実際は `estimated_effort`/`estimated_value`（F50 で `effort`/`value` に変換される） | テストのキー名を修正 |

> ※ これらは全て **仕様書どおりの正常動作** であり、Fシリーズのコードに不具合なし。

---

## 5. 仕様変更要求（Request）

なし（テスト期間中のため、要改善点は次フェーズへ移管）

---

## 6. 不具合（Bug）

なし

---

## 7. 全体テスト状況（2026-07-21 時点）

| テストスイート | ファイル | 件数 |
|---|---|---|
| Fシリーズ既存テスト | tests/test_f*_module.py (×9) | 590 |
| Phase 4 WP8100 単体 | test_8100_unit.py | 61件 |
| Phase 4 WP8110 因果分解 | test_8110_causal.py | **116件** |
| Phase 4 WP8200 連携 | test_8200_integration.py | 35件 |
| Phase 4 WP8300 運用 | test_8300_operational.py | 29件 |
| Phase 4 WP8400 再現性 | test_8400_reproducibility.py | 29件 (パラメ展開で77件) |
| **総計** | — | **908 passed** |

**`pytest tests/ -q` → 908 passed in 11.07s**

---

*本レポートは WP8110 因果分解テストの正式完了記録である。*  
*テスト期間中、Fシリーズの仕様変更・コード変更は行っていない。*
