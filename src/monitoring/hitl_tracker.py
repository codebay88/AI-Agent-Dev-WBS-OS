"""HITL approval history tracker for Phase 5 monitoring."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

HITLDecision = Literal["approve", "reject", "reprocess"]

VALID_DECISIONS: tuple[str, ...] = ("approve", "reject", "reprocess")
APPROVAL_RATE_WARNING_THRESHOLD = 0.90


@dataclass
class HITLEvent:
    module:     str
    element_id: str
    decision:   HITLDecision
    timestamp:  datetime
    reason:     str = ""


class HITLTracker:
    """承認／却下／再処理の履歴を追跡し、誤承認検知ロジックを提供する。"""

    def __init__(self, approval_rate_threshold: float = APPROVAL_RATE_WARNING_THRESHOLD):
        self._history: list[HITLEvent] = []
        self._pending: dict[str, datetime] = {}  # element_id → 受理日時
        self._threshold = approval_rate_threshold

    # ── 保留登録 ────────────────────────────────────────────

    def record_pending(
        self,
        module: str,
        element_id: str,
        timestamp: datetime | None = None,
    ) -> None:
        self._pending[element_id] = timestamp or datetime.now()

    # ── 判断記録 ────────────────────────────────────────────

    def record_decision(
        self,
        module: str,
        element_id: str,
        decision: HITLDecision,
        reason: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        if decision not in VALID_DECISIONS:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {VALID_DECISIONS}")
        ts = timestamp or datetime.now()
        self._history.append(
            HITLEvent(module=module, element_id=element_id, decision=decision, timestamp=ts, reason=reason)
        )
        self._pending.pop(element_id, None)

    # ── クエリ ──────────────────────────────────────────────

    def get_history(self) -> list[HITLEvent]:
        return list(self._history)

    def approval_rate(self) -> float:
        if not self._history:
            return 0.0
        approvals = sum(1 for e in self._history if e.decision == "approve")
        return approvals / len(self._history)

    def is_approval_rate_high(self) -> bool:
        """承認率が閾値（デフォルト90%）を超えているか。"""
        return len(self._history) > 0 and self.approval_rate() > self._threshold

    def pending_over_delay(
        self,
        delay_seconds: float,
        now: datetime | None = None,
    ) -> list[str]:
        """指定秒数を超えて保留中の element_id リストを返す。"""
        ref = now or datetime.now()
        return [
            eid
            for eid, ts in self._pending.items()
            if (ref - ts).total_seconds() > delay_seconds
        ]

    def daily_count(self, date: datetime | None = None) -> int:
        """指定日（デフォルト: 今日）の HITL 判断件数を返す。"""
        d = (date or datetime.now()).date()
        return sum(1 for e in self._history if e.timestamp.date() == d)

    @property
    def pending(self) -> dict[str, datetime]:
        return dict(self._pending)
