"""WP9110 日常運用テスト（Daily Operation and Log Review Test）
Phase 5：運用層（9000番台）

テスト対象:
  - src/monitoring/daily_operation.py
    - DailyOperationRunner.run_pipeline()
    - DailyOperationRunner.review_logs()
    - DailyOperationRunner.write_daily_record()
    - LogReviewer.parse_log()
    - LogReviewer.detect_anomaly()
"""

import logging
from datetime import datetime
from pathlib import Path

import pytest

# F10 API モック用定数（Phase 4 テストと同一の安全ゴール文字列）
_SAFE_GOAL  = "売上を前年比120%に成長させる"
_MOCK_JSON  = (
    '{"L1":"売上を前年比120%に成長させる",'
    '"L2":["新規顧客獲得","既存顧客維持"],'
    '"L3":["LP作成する","広告配信する"]}'
)


# ════════════════════════════════════════════════════════════════════════════
# TestWP9111 — 通常タスク処理（パイプライン実行）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9111_DailyTaskProcessing:

    @pytest.fixture
    def runner(self, tmp_path):
        from src.monitoring.daily_operation import DailyOperationRunner
        return DailyOperationRunner(summary_log=tmp_path / "summary.log")

    @pytest.fixture
    def mock_api(self, mocker):
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        return mocker.patch(
            "src.agents.f10_module._call_api",
            return_value=_MOCK_JSON,
        )

    def test_run_result_has_status_key(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert "status" in result

    def test_run_result_status_is_success_on_normal_input(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert result["status"] == "success"

    def test_run_result_has_completed_modules_list(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert isinstance(result["completed_modules"], list)

    def test_f10_in_completed_modules(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert "F10" in result["completed_modules"]

    def test_pipeline_reaches_at_least_f60_on_normal_input(self, runner, mock_api):
        # F60 以降で HITL が発動する場合もあるため、F60 以上の到達を確認
        result = runner.run_pipeline(_SAFE_GOAL)
        assert len(result["completed_modules"]) >= 6

    def test_run_result_has_timestamp(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert "timestamp" in result
        datetime.fromisoformat(result["timestamp"])  # パース可能か

    def test_run_result_has_results_dict(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert isinstance(result["results"], dict)

    def test_run_result_error_is_none_on_success(self, runner, mock_api):
        result = runner.run_pipeline(_SAFE_GOAL)
        assert result["error"] is None


# ════════════════════════════════════════════════════════════════════════════
# TestWP9112 — ログ確認（summary.log 解析・異常検出）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9112_LogReview:

    @pytest.fixture
    def reviewer(self):
        from src.monitoring.daily_operation import LogReviewer
        return LogReviewer()

    def test_parse_log_returns_dict_with_all_levels(self, reviewer, tmp_path):
        log = tmp_path / "summary.log"
        log.write_text("", encoding="utf-8")
        counts = reviewer.parse_log(log)
        for level in ("INFO", "WARNING", "ERROR", "RETRY", "HITL"):
            assert level in counts

    def test_parse_log_counts_error_entries(self, reviewer, tmp_path):
        log = tmp_path / "summary.log"
        log.write_text(
            "[2026-07-22T10:00:00] ALERT ERROR module=src.agents.f10_module msg=テスト\n"
            "[2026-07-22T10:01:00] ALERT ERROR module=src.agents.f20_module msg=テスト\n",
            encoding="utf-8",
        )
        counts = reviewer.parse_log(log)
        assert counts["ERROR"] == 2

    def test_parse_log_counts_warning_entries(self, reviewer, tmp_path):
        log = tmp_path / "summary.log"
        log.write_text(
            "[2026-07-22T10:00:00] ALERT WARNING module=src.agents.f30_module msg=警告\n",
            encoding="utf-8",
        )
        counts = reviewer.parse_log(log)
        assert counts["WARNING"] == 1

    def test_parse_log_counts_retry_entries(self, reviewer, tmp_path):
        log = tmp_path / "summary.log"
        log.write_text(
            "[2026-07-22T10:00:00] ALERT RETRY module=src.agents.f10_module msg=リトライ\n"
            "[2026-07-22T10:01:00] ALERT RETRY module=src.agents.f10_module msg=リトライ\n"
            "[2026-07-22T10:02:00] ALERT RETRY module=src.agents.f10_module msg=リトライ\n",
            encoding="utf-8",
        )
        counts = reviewer.parse_log(log)
        assert counts["RETRY"] == 3

    def test_parse_log_counts_hitl_entries(self, reviewer, tmp_path):
        log = tmp_path / "summary.log"
        log.write_text(
            "[2026-07-22T10:00:00] ALERT HITL module=src.agents.f10_module msg=HITL移譲\n",
            encoding="utf-8",
        )
        counts = reviewer.parse_log(log)
        assert counts["HITL"] == 1

    def test_parse_empty_log_returns_all_zeros(self, reviewer, tmp_path):
        log = tmp_path / "summary.log"
        log.write_text("", encoding="utf-8")
        counts = reviewer.parse_log(log)
        assert all(v == 0 for v in counts.values())

    def test_no_anomaly_on_clean_log(self, reviewer):
        counts = {"INFO": 10, "WARNING": 2, "ERROR": 0, "RETRY": 1, "HITL": 3}
        issues = reviewer.detect_anomaly(counts)
        assert issues == []

    def test_consecutive_errors_detected_as_anomaly(self, reviewer):
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 3, "RETRY": 0, "HITL": 0}
        issues = reviewer.detect_anomaly(counts)
        assert len(issues) >= 1
        assert any("ERROR" in i for i in issues)

    def test_excessive_hitl_detected_as_anomaly(self, reviewer):
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "RETRY": 0, "HITL": 11}
        issues = reviewer.detect_anomaly(counts)
        assert any("HITL" in i for i in issues)

    def test_frequent_retry_detected_as_anomaly(self, reviewer):
        counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "RETRY": 6, "HITL": 0}
        issues = reviewer.detect_anomaly(counts)
        assert any("RETRY" in i for i in issues)


# ════════════════════════════════════════════════════════════════════════════
# TestWP9113 — フェイルセーフ発動（異常時の安全停止）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9113_FailsafeActivation:

    @pytest.fixture
    def runner(self, tmp_path):
        from src.monitoring.daily_operation import DailyOperationRunner
        return DailyOperationRunner(summary_log=tmp_path / "summary.log")

    def test_pipeline_error_sets_status_error(self, runner, mocker):
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=RuntimeError("API障害"),
        )
        result = runner.run_pipeline(_SAFE_GOAL)
        assert result["status"] == "error"

    def test_error_result_has_error_message(self, runner, mocker):
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=RuntimeError("タイムアウト"),
        )
        result = runner.run_pipeline(_SAFE_GOAL)
        assert result["error"] is not None
        assert len(result["error"]) > 0

    def test_hitl_trigger_stops_pipeline_at_f10(self, runner):
        result = runner.run_pipeline("など含む曖昧な目標など")
        assert "F10" in result["completed_modules"]
        assert "F20" not in result["completed_modules"]

    def test_pipeline_error_when_execute_raises(self, runner, mocker):
        # execute() 自体が例外を投げる場合（例: _call_api_with_retry が RuntimeError）
        mocker.patch(
            "src.agents.f10_module.execute",
            side_effect=RuntimeError("F10 内部エラー"),
        )
        result = runner.run_pipeline(_SAFE_GOAL)
        assert result["status"] == "error"

    def test_run_result_always_has_timestamp_even_on_error(self, runner, mocker):
        mocker.patch("src.agents.f10_module._load_prompt", return_value="dummy")
        mocker.patch(
            "src.agents.f10_module._call_api",
            side_effect=RuntimeError("強制エラー"),
        )
        result = runner.run_pipeline(_SAFE_GOAL)
        assert "timestamp" in result


# ════════════════════════════════════════════════════════════════════════════
# TestWP9114 — 日次運用記録更新
# ════════════════════════════════════════════════════════════════════════════

class TestWP9114_DailyRecordUpdate:

    @pytest.fixture
    def runner(self, tmp_path):
        from src.monitoring.daily_operation import DailyOperationRunner
        return DailyOperationRunner(summary_log=tmp_path / "summary.log")

    @pytest.fixture
    def normal_run(self):
        return {
            "status": "success",
            "completed_modules": list("F10 F20 F30 F40 F50 F60 F70 F80 F90".split()),
            "error": None,
            "timestamp": datetime.now().isoformat(),
            "results": {},
        }

    @pytest.fixture
    def clean_review(self):
        return {"counts": {}, "anomalies": [], "status": "normal"}

    def test_daily_record_written_to_log(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        assert log.exists()
        assert len(log.read_text(encoding="utf-8")) > 0

    def test_daily_record_has_timestamp(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "WP9110 日常運用記録" in content

    def test_daily_record_has_status(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "success" in content

    def test_daily_record_has_module_count(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "9/9" in content

    def test_daily_record_has_anomaly_count(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "異常件数" in content

    def test_daily_record_shows_no_anomaly_on_normal(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "なし" in content

    def test_daily_record_has_phase5_ready_flag(self, runner, tmp_path, normal_run, clean_review):
        log = tmp_path / "summary.log"
        runner.write_daily_record(normal_run, clean_review, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "READY" in content


# ════════════════════════════════════════════════════════════════════════════
# TestWP9115 — 安定稼働・再現性確認
# ════════════════════════════════════════════════════════════════════════════

class TestWP9115_StabilityCheck:

    def test_all_f_modules_importable(self):
        import importlib
        for i in range(1, 10):
            mod = importlib.import_module(f"src.agents.f{i*10}_module")
            assert hasattr(mod, "execute")

    def test_monitoring_handler_can_be_installed(self, tmp_path):
        from src.monitoring.monitor import install, MonitoringHandler, F_MODULE_LOGGERS
        h = install(summary_log_path=tmp_path / "summary.log")
        assert isinstance(h, MonitoringHandler)
        for name in F_MODULE_LOGGERS:
            logging.getLogger(name).removeHandler(h)

    def test_log_reviewer_is_stateless(self, tmp_path):
        from src.monitoring.daily_operation import LogReviewer
        r1 = LogReviewer()
        r2 = LogReviewer()
        log = tmp_path / "summary.log"
        log.write_text("[2026] ALERT ERROR module=x msg=y\n", encoding="utf-8")
        assert r1.parse_log(log) == r2.parse_log(log)

    def test_daily_runner_default_log_path_is_summary_log(self):
        from src.monitoring.daily_operation import DailyOperationRunner, SUMMARY_LOG
        runner = DailyOperationRunner()
        assert runner._summary_log == SUMMARY_LOG

    def test_review_logs_returns_normal_status_on_clean_log(self, tmp_path):
        from src.monitoring.daily_operation import DailyOperationRunner
        log = tmp_path / "summary.log"
        log.write_text("通常稼働ログ\n", encoding="utf-8")
        runner = DailyOperationRunner(summary_log=log)
        review = runner.review_logs()
        assert review["status"] == "normal"
        assert review["anomalies"] == []
