# Phase 4 テスト層 成果物インデックス
## WP8110〜WP8330 — 正式保存記録

**保存完了日:** 2026-07-22  
**Phase 5 移行フラグ:** READY ✅

---

## テストファイル群（tests/phase4/）

| WP番号 | ファイル | 区分 | passed |
|---|---|---|---|
| WP8100 | [test_8100_unit.py](../../tests/phase4/test_8100_unit.py) | 単体テスト | 61 |
| WP8110 | [test_8110_causal.py](../../tests/phase4/test_8110_causal.py) | 因果構造テスト | 116 |
| WP8120 | [test_8120_template.py](../../tests/phase4/test_8120_template.py) | テンプレ適用テスト | 154 |
| WP8130 | [test_8130_mece.py](../../tests/phase4/test_8130_mece.py) | MECEチェックテスト | 87 |
| WP8200 | [test_8200_integration.py](../../tests/phase4/test_8200_integration.py) | 結合テスト | 48 |
| WP8210 | [test_8210_io.py](../../tests/phase4/test_8210_io.py) | I/O連携テスト | 150 |
| WP8220 | [test_8220_exception.py](../../tests/phase4/test_8220_exception.py) | 例外処理テスト | 131 |
| WP8230 | [test_8230_hitl.py](../../tests/phase4/test_8230_hitl.py) | HITL承認フローテスト | 112 |
| WP8300 | [test_8300_operational.py](../../tests/phase4/test_8300_operational.py) | 運用テスト | 64 |
| WP8310 | [test_8310_scenario.py](../../tests/phase4/test_8310_scenario.py) | 想定シナリオテスト | 64 |
| WP8320 | [test_8320_operational_exception.py](../../tests/phase4/test_8320_operational_exception.py) | 異常系運用テスト | 51 (+1 skip) |
| WP8400 | [test_8400_reproducibility.py](../../tests/phase4/test_8400_reproducibility.py) | 再現性テスト | 29 |
| — | [conftest.py](../../tests/phase4/conftest.py) | pytest 共通設定 | — |

**合計: 1,067 passed / 1 skipped / 0 failed**

---

## テストログ群（logs/）

| ファイル | 内容 |
|---|---|
| [summary.log](logs/summary.log) | **統合判定ログ（メインリファレンス）** |
| [WP8330_ALL_PHASE4_RUN.txt](logs/WP8330_ALL_PHASE4_RUN.txt) | Phase 4 全件実行ログ（生ログ） |
| [test_8110_causal_log.txt](logs/test_8110_causal_log.txt) | WP8110 因果構造テストログ |
| [test_8120_template_log.txt](logs/test_8120_template_log.txt) | WP8120 テンプレ適用テストログ |
| [test_8130_mece_log.txt](logs/test_8130_mece_log.txt) | WP8130 MECEチェックテストログ |
| [test_8210_io_log.txt](logs/test_8210_io_log.txt) | WP8210 I/O連携テストログ |
| [test_8220_exception_log.txt](logs/test_8220_exception_log.txt) | WP8220 例外処理テストログ |
| [test_8230_hitl_log.txt](logs/test_8230_hitl_log.txt) | WP8230 HITL承認フローテストログ |
| [test_8310_scenario_log.txt](logs/test_8310_scenario_log.txt) | WP8310 想定シナリオテストログ |
| [test_8320_operational_exception_log.txt](logs/test_8320_operational_exception_log.txt) | WP8320 異常系運用テストログ |

---

## 判定レポート群（reports/）

| ファイル | 内容 |
|---|---|
| [wp8330_report.html](reports/wp8330_report.html) | **本番移行判定レポート（HTMLビジュアル版）** |
| [wp8330_report.json](reports/wp8330_report.json) | **本番移行判定レポート（構造化データ版）** |
| Visual Dashboard | https://claude.ai/code/artifact/7a059da6-7f09-4af0-bda4-a10ecdf85849 |

---

## 補足ドキュメント（docs/phase4/ 直下）

| ファイル | 内容 |
|---|---|
| [WP8330_TRANSITION_JUDGMENT.md](WP8330_TRANSITION_JUDGMENT.md) | 移行判定マークダウン正式記録 |
| [WP8110_CAUSAL_TEST_REPORT.md](WP8110_CAUSAL_TEST_REPORT.md) | WP8110 因果構造テスト報告書 |
| [PHASE4_TEST_START_DECLARATION.md](PHASE4_TEST_START_DECLARATION.md) | Phase 4 テスト開始宣言 |

---

## Phase 5 移行フラグ確認

```
判定: 移行可（Ready for Phase 5）
Phase 5 移行フラグ: READY ✅
判定日時: 2026-07-22
判定者  : Claude Code WP8330
```

*本インデックスは Phase 4 成果物の完全な参照点として保持する。Phase 5 開始後も変更しないこと。*
