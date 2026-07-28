"""
DailyOperationRunner — Phase 5 日常運用タスク管理
LogReviewer         — summary.log 分析・異常傾向検出
"""
from __future__ import annotations

import importlib
import re
from datetime import datetime
from pathlib import Path
from typing import Callable

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

# 異常検知閾値（monitoring.yaml の値と対応）
ANOMALY_THRESHOLDS: dict[str, int] = {
    "consecutive_errors": 3,
    "hitl_per_session":   10,
    "retry_per_session":  5,
}

_F_MODULES = ["F10", "F20", "F30", "F40", "F50", "F60", "F70", "F80", "F90"]


# ════════════════════════════════════════════════════════════════════════════
# LogReviewer
# ════════════════════════════════════════════════════════════════════════════

class LogReviewer:
    """summary.log を解析し、異常傾向を検出する。インスタンスはステートレス。"""

    _ALERT_RE = re.compile(r"ALERT\s+(ERROR|WARNING|RETRY|HITL)\b")
    _INFO_RE  = re.compile(r"\[INFO\]|\bINFO\b")

    def parse_log(self, log_path: Path) -> dict[str, int]:
        """log_path 内の各レベルのアラート件数を返す。"""
        counts: dict[str, int] = {
            "INFO": 0, "WARNING": 0, "ERROR": 0, "RETRY": 0, "HITL": 0
        }
        if not log_path.exists():
            return counts
        for line in log_path.read_text(encoding="utf-8").splitlines():
            m = self._ALERT_RE.search(line)
            if m:
                lvl = m.group(1)
                counts[lvl] = counts.get(lvl, 0) + 1
            elif self._INFO_RE.search(line):
                counts["INFO"] += 1
        return counts

    def detect_anomaly(
        self,
        counts: dict[str, int],
        log_lines: list[str] | None = None,
        thresholds: dict[str, int] | None = None,
    ) -> list[str]:
        """
        異常傾向を検出する。問題がなければ空リストを返す。

        検知対象:
          - ERROR 累積件数が閾値以上
          - HITL 件数が閾値超過
          - RETRY 件数が閾値超過
          - ログ行内の連続 ERROR
        """
        th     = thresholds or ANOMALY_THRESHOLDS
        issues: list[str] = []

        if counts.get("ERROR", 0) >= th["consecutive_errors"]:
            issues.append(
                f"ERROR件数({counts['ERROR']})が閾値({th['consecutive_errors']})を超過"
            )
        if counts.get("HITL", 0) > th["hitl_per_session"]:
            issues.append(
                f"HITL件数({counts['HITL']})が閾値({th['hitl_per_session']})を超過"
            )
        if counts.get("RETRY", 0) > th["retry_per_session"]:
            issues.append(
                f"RETRY件数({counts['RETRY']})が閾値({th['retry_per_session']})を超過"
            )

        if log_lines:
            consecutive = 0
            max_consec  = 0
            for line in log_lines:
                if "ALERT ERROR" in line:
                    consecutive += 1
                    max_consec = max(max_consec, consecutive)
                else:
                    consecutive = 0
            if max_consec >= th["consecutive_errors"]:
                msg = f"連続ERROR({max_consec}件)を検出"
                if msg not in issues:
                    issues.append(msg)

        return issues


# ════════════════════════════════════════════════════════════════════════════
# DailyOperationRunner
# ════════════════════════════════════════════════════════════════════════════

class DailyOperationRunner:
    """
    日次運用タスクの実行・ログ確認・記録管理。

    本番: api_mock=None → F10 が .env の APIキーで実呼び出し（HITL 手動入力）
    テスト: api_mock に callable を渡すと _call_api を差し替え
    """

    MODULES = _F_MODULES

    def __init__(
        self,
        summary_log: Path | None = None,
        reviewer: LogReviewer | None = None,
    ) -> None:
        self._summary_log = summary_log or SUMMARY_LOG
        self._reviewer    = reviewer or LogReviewer()

    # ── パイプライン実行 ──────────────────────────────────────

    # F10→F90 の実行順序
    _PIPELINE: list[tuple[str, str]] = [
        ("F10", "f10"), ("F20", "f20"), ("F30", "f30"),
        ("F40", "f40"), ("F50", "f50"), ("F60", "f60"),
        ("F70", "f70"), ("F80", "f80"), ("F90", "f90"),
    ]

    def run_pipeline(
        self,
        goal_text: str,
        api_mock: Callable | None = None,
    ) -> dict:
        """
        F10→F90 パイプラインを実行して結果 dict を返す。

        Returns:
            status             : "success" | "error"
            completed_modules  : 正常完了したモジュール名リスト
            error              : 例外メッセージ（正常時は None）
            timestamp          : ISO8601 文字列
            results            : モジュール名 → 出力 dict
        """
        results:   dict[str, dict] = {}
        error_msg: str | None      = None
        f10_mod   = importlib.import_module("src.agents.f10_module")
        _original = getattr(f10_mod, "_call_api", None)

        try:
            if api_mock is not None:
                f10_mod._call_api = api_mock  # type: ignore[attr-defined]

            prev = {"goal_text": goal_text}
            for key, fname in self._PIPELINE:
                fmod = (
                    f10_mod if fname == "f10"
                    else importlib.import_module(f"src.agents.{fname}_module")
                )
                out = fmod.execute(prev)
                results[key] = out
                if out.get("hitl") or out.get("hitl_required"):
                    break
                prev = out

        except Exception as exc:
            error_msg = str(exc)
        finally:
            if api_mock is not None and _original is not None:
                f10_mod._call_api = _original  # type: ignore[attr-defined]

        return {
            "status":            "error" if error_msg else "success",
            "completed_modules": list(results.keys()),
            "error":             error_msg,
            "timestamp":         datetime.now().isoformat(),
            "results":           results,
        }

    # ── ログ確認 ───────────────────────────────────────────────

    def review_logs(self, log_path: Path | None = None) -> dict:
        """summary.log を解析して件数・異常傾向を返す。"""
        path   = log_path or self._summary_log
        counts = self._reviewer.parse_log(path)
        lines  = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        issues = self._reviewer.detect_anomaly(counts, lines)
        return {
            "counts":    counts,
            "anomalies": issues,
            "status":    "anomaly" if issues else "normal",
        }

    # ── 日次記録書き込み ────────────────────────────────────────

    def write_daily_record(
        self,
        run_result: dict,
        review_result: dict,
        log_path: Path | None = None,
    ) -> None:
        """日次運用結果を summary.log に追記する。"""
        path      = log_path or self._summary_log
        ts        = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        completed = len(run_result.get("completed_modules", []))
        status    = run_result.get("status", "unknown")
        anomalies = review_result.get("anomalies", [])
        anomaly_str = "なし" if not anomalies else "; ".join(anomalies)

        entry = (
            f"\n[{ts}] WP9110 日常運用記録\n"
            f"  稼働状況     : {status}\n"
            f"  完了モジュール: {completed}/9\n"
            f"  異常件数     : {len(anomalies)}\n"
            f"  異常内容     : {anomaly_str}\n"
            f"  Phase 5 フラグ: READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
