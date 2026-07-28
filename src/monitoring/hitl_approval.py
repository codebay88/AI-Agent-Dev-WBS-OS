"""
HITLApprovalFlow — Phase 5 HITL承認フロー管理

F モジュール出力から HITL 情報を検出し、
承認／却下／再処理の判断を記録・集計・出力する。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .hitl_tracker import HITLTracker, HITLDecision, VALID_DECISIONS

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

# MAX_RETRY と同値（alert_rules.py の retry.threshold と対応）
MAX_REPROCESS = 3


class HITLApprovalFlow:
    """
    F モジュール出力の HITL 情報を検出し、承認フローを管理する。

    使い方:
        flow = HITLApprovalFlow()
        info = flow.detect_hitl("F10", r10)
        if info:
            flow.submit_decision("F10", "E001", "approve", reason="内容確認済")
        flow.write_approval_record()
    """

    def __init__(
        self,
        tracker: HITLTracker | None = None,
        summary_log: Path | None    = None,
    ) -> None:
        self._tracker     = tracker or HITLTracker()
        self._summary_log = summary_log or SUMMARY_LOG
        self._decisions:   list[dict] = []
        self._reprocess_counts: dict[str, int] = {}  # element_id → 再処理回数

    # ── HITL 検出 ────────────────────────────────────────────

    def detect_hitl(self, module: str, result: dict) -> dict | None:
        """
        F モジュール出力から HITL 情報を抽出する。

        HITL が不要なら None を返す。
        HITL が必要なら以下のキーを持つ dict を返す:
          module, reason, elements, needs_approval
        """
        is_hitl = bool(result.get("hitl") or result.get("hitl_required"))
        if not is_hitl:
            return None

        return {
            "module":         module,
            "reason":         result.get("hitl_reason", ""),
            "elements":       result.get("hitl_elements", []),
            "needs_approval": True,
        }

    # ── 承認フロー実行 ────────────────────────────────────────

    def submit_decision(
        self,
        module:     str,
        element_id: str,
        decision:   HITLDecision,
        reason:     str = "",
    ) -> None:
        """
        承認・却下・再処理の判断を記録する。

        Raises:
            ValueError: decision が無効な値の場合
        """
        if decision not in VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision '{decision}'. Must be one of {VALID_DECISIONS}"
            )
        ts = datetime.now()
        self._tracker.record_decision(module, element_id, decision, reason, timestamp=ts)
        self._decisions.append({
            "module":     module,
            "element_id": element_id,
            "decision":   decision,
            "reason":     reason,
            "timestamp":  ts.isoformat(),
        })
        if decision == "reprocess":
            self._reprocess_counts[element_id] = (
                self._reprocess_counts.get(element_id, 0) + 1
            )

    # ── セッションサマリー ────────────────────────────────────

    def get_session_summary(self) -> dict:
        """セッション内の承認・却下・再処理件数と承認率を返す。"""
        counts: dict[str, int] = {"approve": 0, "reject": 0, "reprocess": 0}
        for d in self._decisions:
            counts[d["decision"]] = counts.get(d["decision"], 0) + 1
        rate = self._tracker.approval_rate()
        return {
            "total":               len(self._decisions),
            "counts":              counts,
            "approval_rate":       rate,
            "misapproval_warning": self._tracker.is_approval_rate_high(),
        }

    def reprocess_count(self, element_id: str) -> int:
        """指定 element_id の累積再処理回数を返す。"""
        return self._reprocess_counts.get(element_id, 0)

    def over_max_reprocess(self, element_id: str) -> bool:
        """再処理回数が MAX_REPROCESS を超えているかを返す。"""
        return self._reprocess_counts.get(element_id, 0) > MAX_REPROCESS

    # ── summary.log への書き込み ─────────────────────────────

    def write_approval_record(self, log_path: Path | None = None) -> None:
        """承認履歴サマリーを summary.log に追記する。"""
        path    = log_path or self._summary_log
        ts      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        summary = self.get_session_summary()
        counts  = summary["counts"]
        rate    = summary["approval_rate"]
        warn    = " ⚠ 誤承認検知" if summary["misapproval_warning"] else ""

        entry = (
            f"\n[{ts}] WP9120 HITL承認記録\n"
            f"  総件数   : {summary['total']}\n"
            f"  承認     : {counts['approve']}\n"
            f"  却下     : {counts['reject']}\n"
            f"  再処理   : {counts['reprocess']}\n"
            f"  承認率   : {rate:.1%}{warn}\n"
            f"  Phase 5 フラグ: READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── プロパティ ────────────────────────────────────────────

    @property
    def tracker(self) -> HITLTracker:
        return self._tracker

    @property
    def decisions(self) -> list[dict]:
        return list(self._decisions)
