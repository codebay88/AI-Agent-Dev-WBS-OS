"""MonitoringHandler — Phase 5 log-based alert system for the F10→F90 pipeline."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from .alert_rules import AlertRule, AlertLevel, DEFAULT_RULES
from .hitl_tracker import HITLTracker

BASE_DIR = Path(__file__).resolve().parent.parent.parent

F_MODULE_LOGGERS = [
    "src.agents.f10_module",
    "src.agents.f20_module",
    "src.agents.f30_module",
    "src.agents.f40_module",
    "src.agents.f50_module",
    "src.agents.f60_module",
    "src.agents.f70_module",
    "src.agents.f80_module",
    "src.agents.f90_module",
]


class MonitoringHandler(logging.Handler):
    """
    F シリーズモジュールのログレコードを受信し、アラートルールを適用する。

    分類:
      ERROR   → 即時アラート
      WARNING + retry pattern → RETRY カウンタ（3回連続でアラート）
      WARNING + HITL pattern  → HITL 記録（保留タイムスタンプ付き）
      WARNING （その他）       → WARNING カウンタ（5回連続でアラート）
    """

    def __init__(
        self,
        rules: dict[str, AlertRule] | None = None,
        hitl_tracker: HITLTracker | None = None,
        summary_log_path: Path | None = None,
        on_alert: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__()
        self._rules           = rules or DEFAULT_RULES
        self._tracker         = hitl_tracker or HITLTracker()
        self._summary_log     = summary_log_path or (BASE_DIR / "docs" / "phase4" / "logs" / "summary.log")
        self._on_alert        = on_alert
        self._alerts: list[dict]          = []
        self._failsafe_events: list[dict] = []
        self._consecutive_warnings        = 0
        self._consecutive_retries         = 0

    # ── logging.Handler interface ────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()

        if record.levelno >= logging.ERROR:
            self._handle_error(record, msg)
        elif record.levelno >= logging.WARNING:
            if self._is_retry(msg):
                self._handle_retry(record, msg)
            elif self._is_hitl(msg):
                self._handle_hitl(record, msg)
            else:
                self._handle_warning(record, msg)

    # ── 分類判定 ────────────────────────────────────────────

    def _is_retry(self, msg: str) -> bool:
        rule = self._rules.get("retry")
        if rule is None:
            return False
        return any(p in msg for p in rule.patterns)

    def _is_hitl(self, msg: str) -> bool:
        rule = self._rules.get("hitl")
        if rule is None:
            return False
        return any(p in msg for p in rule.patterns)

    # ── ハンドラ ────────────────────────────────────────────

    def _handle_error(self, record: logging.LogRecord, msg: str) -> None:
        self._consecutive_warnings = 0
        self._consecutive_retries  = 0
        self._fire(self._make_alert("ERROR", record.name, msg))

    def _handle_warning(self, record: logging.LogRecord, msg: str) -> None:
        self._consecutive_retries   = 0
        self._consecutive_warnings += 1
        rule = self._rules.get("warning")
        if rule and self._consecutive_warnings >= rule.threshold:
            self._fire(self._make_alert(
                "WARNING", record.name, msg, count=self._consecutive_warnings
            ))
            self._consecutive_warnings = 0

    def _handle_retry(self, record: logging.LogRecord, msg: str) -> None:
        self._consecutive_retries += 1
        rule = self._rules.get("retry")
        if rule and self._consecutive_retries >= rule.threshold:
            self._fire(self._make_alert(
                "RETRY", record.name, msg, count=self._consecutive_retries
            ))
            self._consecutive_retries = 0

    def _handle_hitl(self, record: logging.LogRecord, msg: str) -> None:
        self._consecutive_warnings = 0
        self._tracker.record_pending(record.name, msg, datetime.now())
        alert = self._make_alert("HITL", record.name, msg)
        self._alerts.append(alert)
        if self._on_alert:
            self._on_alert(alert)

    # ── アラート送出 ────────────────────────────────────────

    def _make_alert(
        self, level: str, module: str, msg: str, count: int = 1
    ) -> dict:
        return {
            "level":     level,
            "module":    module,
            "message":   msg,
            "count":     count,
            "timestamp": datetime.now().isoformat(),
        }

    def _fire(self, alert: dict) -> None:
        self._alerts.append(alert)
        self._write_summary(alert)
        if self._on_alert:
            self._on_alert(alert)

    def _write_summary(self, alert: dict) -> None:
        try:
            with open(self._summary_log, "a", encoding="utf-8") as f:
                f.write(
                    f"[{alert['timestamp']}] ALERT {alert['level']}"
                    f" module={alert['module']}"
                    f" msg={alert['message'][:80]}\n"
                )
        except OSError:
            pass

    # ── フェイルセーフ記録（外部から呼び出し） ────────────────

    def record_failsafe(
        self,
        module: str,
        trace_id: str,
        source_trace_id: str,
        estimated_effort,
    ) -> None:
        """フェイルセーフ発動イベントを記録する。"""
        self._failsafe_events.append({
            "module":           module,
            "trace_id":         trace_id,
            "source_trace_id":  source_trace_id,
            "estimated_effort": estimated_effort,
            "timestamp":        datetime.now().isoformat(),
        })

    # ── プロパティ ──────────────────────────────────────────

    @property
    def alerts(self) -> list[dict]:
        return list(self._alerts)

    @property
    def failsafe_events(self) -> list[dict]:
        return list(self._failsafe_events)

    @property
    def hitl_tracker(self) -> HITLTracker:
        return self._tracker

    @property
    def consecutive_warnings(self) -> int:
        return self._consecutive_warnings

    @property
    def consecutive_retries(self) -> int:
        return self._consecutive_retries


# ── インストールヘルパー ──────────────────────────────────────

def install(
    modules: list[str] | None = None,
    **handler_kwargs,
) -> MonitoringHandler:
    """F シリーズモジュールの全ロガーに MonitoringHandler を装着して返す。"""
    handler = MonitoringHandler(**handler_kwargs)
    for name in (modules or F_MODULE_LOGGERS):
        logging.getLogger(name).addHandler(handler)
    return handler
