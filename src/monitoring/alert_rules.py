"""Alert rule definitions for Phase 5 monitoring."""
from dataclasses import dataclass, field
from enum import Enum


class AlertLevel(str, Enum):
    IMMEDIATE    = "immediate"
    ON_THRESHOLD = "on_threshold"
    ON_DELAY     = "on_delay"


@dataclass
class AlertRule:
    name:          str
    log_level:     str
    notify:        AlertLevel
    threshold:     int            = 1
    patterns:      list[str]      = field(default_factory=list)
    delay_seconds: float | None   = None


# デフォルトルール（monitoring.yaml の設定値と一致）
DEFAULT_RULES: dict[str, AlertRule] = {
    "error": AlertRule(
        name="error",
        log_level="ERROR",
        notify=AlertLevel.IMMEDIATE,
        threshold=1,
    ),
    "warning": AlertRule(
        name="warning",
        log_level="WARNING",
        notify=AlertLevel.ON_THRESHOLD,
        threshold=5,
    ),
    "retry": AlertRule(
        name="retry",
        log_level="WARNING",
        notify=AlertLevel.ON_THRESHOLD,
        threshold=3,
        patterns=["リトライ", "retry", "RETRY"],
    ),
    "hitl": AlertRule(
        name="hitl",
        log_level="WARNING",
        notify=AlertLevel.ON_DELAY,
        threshold=1,
        patterns=["HITL", "HITL移譲"],
        delay_seconds=30.0,
    ),
}
