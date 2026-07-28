"""WP9100 初期監視設定テスト（Initial Monitoring Configuration Test）
Phase 5：運用層（9000番台）

テスト対象:
  - docs/phase5/config/monitoring.yaml
  - src/monitoring/monitor.py
  - src/monitoring/hitl_tracker.py
  - src/monitoring/alert_rules.py
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "docs" / "phase5" / "config" / "monitoring.yaml"
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"


# ════════════════════════════════════════════════════════════════════════════
# TestWP9101 — monitoring.yaml 設定ファイル検証
# ════════════════════════════════════════════════════════════════════════════

class TestWP9101_AlertConfig:

    def _cfg(self):
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_monitoring_yaml_exists(self):
        assert CONFIG_PATH.exists(), "monitoring.yaml が存在しません"

    def test_yaml_has_modules_list(self):
        cfg = self._cfg()
        assert "modules" in cfg
        assert len(cfg["modules"]) == 9  # F10〜F90

    def test_yaml_error_threshold_is_immediate(self):
        cfg = self._cfg()
        assert cfg["alert_rules"]["error"]["notify"] == "immediate"

    def test_yaml_warning_consecutive_threshold_is_5(self):
        cfg = self._cfg()
        assert cfg["alert_rules"]["warning"]["consecutive_threshold"] == 5

    def test_yaml_retry_consecutive_threshold_is_3(self):
        cfg = self._cfg()
        assert cfg["alert_rules"]["retry"]["consecutive_threshold"] == 3

    def test_yaml_hitl_delay_threshold_is_30s(self):
        cfg = self._cfg()
        assert cfg["alert_rules"]["hitl"]["delay_threshold_seconds"] == 30

    def test_yaml_hitl_tracking_enabled(self):
        cfg = self._cfg()
        assert cfg["hitl_tracking"]["enabled"] is True

    def test_yaml_approval_rate_warning_threshold_is_90_percent(self):
        cfg = self._cfg()
        assert cfg["hitl_tracking"]["approval_rate_warning_threshold"] == 0.90

    def test_yaml_failsafe_monitoring_enabled(self):
        cfg = self._cfg()
        assert cfg["failsafe_monitoring"]["enabled"] is True

    def test_yaml_failsafe_tracks_trace_id(self):
        cfg = self._cfg()
        assert "trace_id" in cfg["failsafe_monitoring"]["track_fields"]


# ════════════════════════════════════════════════════════════════════════════
# TestWP9102 — ERROR アラート（即時発動）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9102_ErrorAlert:

    @pytest.fixture
    def handler(self, tmp_path):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def _emit_error(self, handler, msg="エラー発生", module="src.agents.f10_module"):
        record = logging.LogRecord(
            name=module, level=logging.ERROR,
            pathname="", lineno=0, msg=msg, args=(), exc_info=None
        )
        handler.emit(record)

    def test_error_log_triggers_immediate_alert(self, handler):
        self._emit_error(handler)
        assert len(handler.alerts) == 1

    def test_error_alert_has_level_error(self, handler):
        self._emit_error(handler)
        assert handler.alerts[0]["level"] == "ERROR"

    def test_error_alert_has_module_name(self, handler):
        self._emit_error(handler, module="src.agents.f30_module")
        assert handler.alerts[0]["module"] == "src.agents.f30_module"

    def test_error_alert_has_timestamp(self, handler):
        self._emit_error(handler)
        assert "timestamp" in handler.alerts[0]
        assert handler.alerts[0]["timestamp"] != ""

    def test_error_resets_warning_counter(self, handler):
        # WARNING を3件送信してから ERROR
        for _ in range(3):
            rec = logging.LogRecord(
                name="src.agents.f20_module", level=logging.WARNING,
                pathname="", lineno=0, msg="警告", args=(), exc_info=None
            )
            handler.emit(rec)
        assert handler.consecutive_warnings == 3
        self._emit_error(handler)
        assert handler.consecutive_warnings == 0


# ════════════════════════════════════════════════════════════════════════════
# TestWP9103 — WARNING アラート（5件連続）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9103_WarningAlert:

    @pytest.fixture
    def handler(self, tmp_path):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def _emit_warning(self, handler, msg="警告メッセージ", module="src.agents.f20_module"):
        record = logging.LogRecord(
            name=module, level=logging.WARNING,
            pathname="", lineno=0, msg=msg, args=(), exc_info=None
        )
        handler.emit(record)

    def test_single_warning_does_not_trigger_alert(self, handler):
        self._emit_warning(handler)
        assert len(handler.alerts) == 0

    def test_four_consecutive_warnings_no_alert(self, handler):
        for _ in range(4):
            self._emit_warning(handler)
        assert len(handler.alerts) == 0

    def test_five_consecutive_warnings_trigger_alert(self, handler):
        for _ in range(5):
            self._emit_warning(handler)
        assert len(handler.alerts) == 1
        assert handler.alerts[0]["level"] == "WARNING"

    def test_warning_counter_resets_after_alert(self, handler):
        for _ in range(5):
            self._emit_warning(handler)
        assert handler.consecutive_warnings == 0

    def test_warning_counter_resets_on_error(self, handler):
        for _ in range(3):
            self._emit_warning(handler)
        rec = logging.LogRecord(
            name="src.agents.f10_module", level=logging.ERROR,
            pathname="", lineno=0, msg="ERROR", args=(), exc_info=None
        )
        handler.emit(rec)
        assert handler.consecutive_warnings == 0


# ════════════════════════════════════════════════════════════════════════════
# TestWP9104 — RETRY アラート（3回連続）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9104_RetryAlert:

    @pytest.fixture
    def handler(self, tmp_path):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def _emit_retry(self, handler, module="src.agents.f10_module"):
        record = logging.LogRecord(
            name=module, level=logging.WARNING,
            pathname="", lineno=0, msg="リトライ実行（attempt 1）", args=(), exc_info=None
        )
        handler.emit(record)

    def test_single_retry_does_not_trigger_alert(self, handler):
        self._emit_retry(handler)
        assert len(handler.alerts) == 0

    def test_two_retries_no_alert(self, handler):
        for _ in range(2):
            self._emit_retry(handler)
        assert len(handler.alerts) == 0

    def test_three_consecutive_retries_trigger_alert(self, handler):
        for _ in range(3):
            self._emit_retry(handler)
        assert len(handler.alerts) == 1
        assert handler.alerts[0]["level"] == "RETRY"

    def test_retry_detected_by_english_pattern(self, handler):
        record = logging.LogRecord(
            name="src.agents.f10_module", level=logging.WARNING,
            pathname="", lineno=0, msg="RETRY attempt 2", args=(), exc_info=None
        )
        for _ in range(3):
            handler.emit(record)
        assert any(a["level"] == "RETRY" for a in handler.alerts)

    def test_retry_counter_resets_after_alert(self, handler):
        for _ in range(3):
            self._emit_retry(handler)
        assert handler.consecutive_retries == 0


# ════════════════════════════════════════════════════════════════════════════
# TestWP9105 — HITL ログ監視
# ════════════════════════════════════════════════════════════════════════════

class TestWP9105_HITLMonitoring:

    @pytest.fixture
    def handler(self, tmp_path):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def _emit_hitl(self, handler, msg="HITL移譲: 曖昧語検出", module="src.agents.f10_module"):
        record = logging.LogRecord(
            name=module, level=logging.WARNING,
            pathname="", lineno=0, msg=msg, args=(), exc_info=None
        )
        handler.emit(record)

    def test_hitl_log_recorded_in_tracker(self, handler):
        self._emit_hitl(handler)
        assert len(handler.hitl_tracker.pending) == 1

    def test_hitl_pending_tracked_with_timestamp(self, handler):
        self._emit_hitl(handler)
        for ts in handler.hitl_tracker.pending.values():
            assert isinstance(ts, datetime)

    def test_hitl_over_30s_detected(self, handler):
        self._emit_hitl(handler)
        # 保留時刻を 31 秒前に上書き
        for key in list(handler.hitl_tracker.pending.keys()):
            handler.hitl_tracker._pending[key] = datetime.now() - timedelta(seconds=31)
        delayed = handler.hitl_tracker.pending_over_delay(30.0)
        assert len(delayed) == 1

    def test_hitl_under_30s_not_detected_as_delayed(self, handler):
        self._emit_hitl(handler)
        delayed = handler.hitl_tracker.pending_over_delay(30.0)
        assert len(delayed) == 0

    def test_hitl_alert_has_level_hitl(self, handler):
        self._emit_hitl(handler)
        assert handler.alerts[-1]["level"] == "HITL"

    def test_hitl_alert_recorded_in_alerts_list(self, handler):
        self._emit_hitl(handler)
        assert len(handler.alerts) >= 1


# ════════════════════════════════════════════════════════════════════════════
# TestWP9106 — HITL承認履歴追跡
# ════════════════════════════════════════════════════════════════════════════

class TestWP9106_HITLTracking:

    @pytest.fixture
    def tracker(self):
        from src.monitoring.hitl_tracker import HITLTracker
        return HITLTracker()

    def test_approve_decision_recorded(self, tracker):
        tracker.record_decision("src.agents.f10_module", "E001", "approve")
        assert tracker.get_history()[0].decision == "approve"

    def test_reject_decision_recorded(self, tracker):
        tracker.record_decision("src.agents.f30_module", "E002", "reject")
        assert tracker.get_history()[0].decision == "reject"

    def test_reprocess_decision_recorded(self, tracker):
        tracker.record_decision("src.agents.f50_module", "E003", "reprocess")
        assert tracker.get_history()[0].decision == "reprocess"

    def test_history_event_has_timestamp(self, tracker):
        tracker.record_decision("src.agents.f10_module", "E001", "approve")
        assert isinstance(tracker.get_history()[0].timestamp, datetime)

    def test_approval_rate_below_90_no_warning(self, tracker):
        for i in range(5):
            tracker.record_decision("src.agents.f10_module", f"E{i:03d}", "approve")
        for i in range(5, 10):
            tracker.record_decision("src.agents.f10_module", f"E{i:03d}", "reject")
        assert tracker.approval_rate() == 0.5
        assert not tracker.is_approval_rate_high()

    def test_approval_rate_over_90_triggers_high_flag(self, tracker):
        for i in range(10):
            tracker.record_decision("src.agents.f10_module", f"E{i:03d}", "approve")
        assert tracker.approval_rate() > 0.90
        assert tracker.is_approval_rate_high()

    def test_daily_count_aggregated(self, tracker):
        today = datetime.now()
        tracker.record_decision("src.agents.f10_module", "E001", "approve", timestamp=today)
        tracker.record_decision("src.agents.f20_module", "E002", "reject", timestamp=today)
        assert tracker.daily_count(today) == 2


# ════════════════════════════════════════════════════════════════════════════
# TestWP9107 — フェイルセーフ監視
# ════════════════════════════════════════════════════════════════════════════

class TestWP9107_FailsafeMonitoring:

    @pytest.fixture
    def handler(self, tmp_path):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def test_failsafe_event_recorded(self, handler):
        handler.record_failsafe("src.agents.f10_module", "F10", "F10", 3)
        assert len(handler.failsafe_events) == 1

    def test_failsafe_has_trace_id(self, handler):
        handler.record_failsafe("src.agents.f40_module", "F40", "F30", 2)
        assert handler.failsafe_events[0]["trace_id"] == "F40"

    def test_failsafe_has_source_trace_id(self, handler):
        handler.record_failsafe("src.agents.f40_module", "F40", "F30", 2)
        assert handler.failsafe_events[0]["source_trace_id"] == "F30"

    def test_failsafe_has_estimated_effort(self, handler):
        handler.record_failsafe("src.agents.f40_module", "F40", "F30", 4)
        assert handler.failsafe_events[0]["estimated_effort"] == 4

    def test_failsafe_has_timestamp(self, handler):
        handler.record_failsafe("src.agents.f90_module", "F90", "F80", 1)
        assert "timestamp" in handler.failsafe_events[0]

    def test_failsafe_multiple_events_tracked(self, handler):
        for i in range(3):
            handler.record_failsafe(f"src.agents.f{(i+1)*10}_module", f"F{(i+1)*10}", f"F{i*10}", i+1)
        assert len(handler.failsafe_events) == 3


# ════════════════════════════════════════════════════════════════════════════
# TestWP9108 — モジュールへのハンドラ装着
# ════════════════════════════════════════════════════════════════════════════

class TestWP9108_ModuleInstall:

    def test_install_returns_monitoring_handler(self, tmp_path):
        from src.monitoring.monitor import install, MonitoringHandler
        h = install(summary_log_path=tmp_path / "summary.log")
        assert isinstance(h, MonitoringHandler)
        # クリーンアップ
        from src.monitoring.monitor import F_MODULE_LOGGERS
        for name in F_MODULE_LOGGERS:
            logging.getLogger(name).removeHandler(h)

    def test_all_f_module_loggers_receive_handler(self, tmp_path):
        from src.monitoring.monitor import install, F_MODULE_LOGGERS, MonitoringHandler
        h = install(summary_log_path=tmp_path / "summary.log")
        for name in F_MODULE_LOGGERS:
            handlers = logging.getLogger(name).handlers
            assert any(isinstance(hh, MonitoringHandler) for hh in handlers), \
                f"{name} に MonitoringHandler が装着されていません"
        for name in F_MODULE_LOGGERS:
            logging.getLogger(name).removeHandler(h)

    def test_f10_logger_name_included(self):
        from src.monitoring.monitor import F_MODULE_LOGGERS
        assert "src.agents.f10_module" in F_MODULE_LOGGERS

    def test_f90_logger_name_included(self):
        from src.monitoring.monitor import F_MODULE_LOGGERS
        assert "src.agents.f90_module" in F_MODULE_LOGGERS

    def test_nine_modules_in_constant(self):
        from src.monitoring.monitor import F_MODULE_LOGGERS
        assert len(F_MODULE_LOGGERS) == 9


# ════════════════════════════════════════════════════════════════════════════
# TestWP9109 — summary.log への出力
# ════════════════════════════════════════════════════════════════════════════

class TestWP9109_SummaryLogOutput:

    @pytest.fixture
    def tmp_log(self, tmp_path):
        return tmp_path / "summary.log"

    @pytest.fixture
    def handler(self, tmp_log):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_log)

    def _emit_error(self, handler):
        record = logging.LogRecord(
            name="src.agents.f10_module", level=logging.ERROR,
            pathname="", lineno=0, msg="テストエラー", args=(), exc_info=None
        )
        handler.emit(record)

    def test_error_alert_written_to_summary_log(self, handler, tmp_log):
        self._emit_error(handler)
        assert tmp_log.exists()
        content = tmp_log.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_summary_log_entry_has_timestamp(self, handler, tmp_log):
        self._emit_error(handler)
        content = tmp_log.read_text(encoding="utf-8")
        assert "[" in content  # タイムスタンプは "[2026-..." 形式

    def test_summary_log_entry_has_level(self, handler, tmp_log):
        self._emit_error(handler)
        content = tmp_log.read_text(encoding="utf-8")
        assert "ALERT ERROR" in content

    def test_summary_log_entry_has_module_name(self, handler, tmp_log):
        self._emit_error(handler)
        content = tmp_log.read_text(encoding="utf-8")
        assert "src.agents.f10_module" in content

    def test_on_alert_callback_called(self, tmp_log):
        from src.monitoring.monitor import MonitoringHandler
        received = []
        h = MonitoringHandler(summary_log_path=tmp_log, on_alert=received.append)
        record = logging.LogRecord(
            name="src.agents.f80_module", level=logging.ERROR,
            pathname="", lineno=0, msg="callback test", args=(), exc_info=None
        )
        h.emit(record)
        assert len(received) == 1
        assert received[0]["level"] == "ERROR"


# ════════════════════════════════════════════════════════════════════════════
# TestWP910A — F モジュールとの統合
# ════════════════════════════════════════════════════════════════════════════

class TestWP910A_Integration:

    @pytest.fixture
    def handler(self, tmp_path):
        from src.monitoring.monitor import MonitoringHandler
        return MonitoringHandler(summary_log_path=tmp_path / "summary.log")

    def test_warning_from_f_module_detected(self, handler):
        logger = logging.getLogger("src.agents.f20_module")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        logger.warning("不明な trace_id を検出 [F20]")
        logger.removeHandler(handler)
        # WARNING カウンタが増加している
        assert handler.consecutive_warnings >= 1

    def test_retry_from_f_module_detected(self, handler):
        logger = logging.getLogger("src.agents.f10_module")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        for _ in range(3):
            logger.warning("リトライ実行（attempt）")
        logger.removeHandler(handler)
        assert any(a["level"] == "RETRY" for a in handler.alerts)

    def test_hitl_from_f_module_detected(self, handler):
        logger = logging.getLogger("src.agents.f30_module")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        logger.warning("HITL移譲: 曖昧語 'など' を検出")
        logger.removeHandler(handler)
        assert any(a["level"] == "HITL" for a in handler.alerts)
