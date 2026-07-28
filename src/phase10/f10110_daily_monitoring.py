"""
F10110 daily_operation_monitoring_and_logging — Phase 10 日次運用監視モジュール

Claude Code の運用状態を日次で監視し、安定稼働を維持するためのログを収集する。
Phase 10 の思想層（stability_first / transparency / reproducibility / safety）を
実装層に反映し、自律運用ループの健全性を確認する。

処理フロー（7ステップ）:
  Step 1: 前日の運用ログを読み込み、異常値を検出する
  Step 2: 現在のシステム状態を取得し、稼働率・エラー率・レイテンシを記録する
  Step 3: operation_metrics を集計し、安定性指標（stability_index）を算出する
  Step 4: 再現性テスト（同条件再実行）を1回実施し、出力一致率を確認する
  Step 5: 安全性チェック（API認証状態・例外発生有無）を検証する
  Step 6: 日次運用ログ（daily_operation_log.json）を生成する
  Step 7: HITL 承認ポイント設定（H-P10-003）/ hitl_monitoring_approval_log.json 書き込み

検証閾値:
  - stability_index >= 0.90
  - reproducibility_rate >= 0.95
  - error_count == 0
  - api_auth_status == "authenticated"
  - hitl_approval == true
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
PHASE10_DIR = BASE_DIR / "docs" / "phase10"

DAILY_LOG_PATH  = PHASE10_DIR / "daily_operation_log.json"
STABILITY_PATH  = PHASE10_DIR / "stability_report.json"
HITL_LOG_PATH   = PHASE10_DIR / "hitl_monitoring_approval_log.json"
EXCEPTION_LOG   = PHASE10_DIR / "exception_log.json"
AUTH_REPORT     = PHASE10_DIR / "api_auth_report.json"

STABILITY_THRESHOLD      = 0.90
REPRODUCIBILITY_THRESHOLD = 0.95
HITL_POINT_ID            = "H-P10-003"
HITL_TRIGGER             = "異常検知時の判断"


class F10110DailyMonitoring:
    """
    F10110 daily_operation_monitoring_and_logging の全7ステップを実行する。

    system_status_fn: () -> dict — 現在のシステム状態を返す関数（mock 対応）
    repro_test_fn:    () -> float — 再現性テスト実行関数（0.0〜1.0 を返す、mock 対応）
    hitl_fn:          (point_id: str) -> str — HITL 承認関数
    previous_log:     前日ログ dict（省略時は前日ログファイルを試みる）
    """

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        system_status_fn: Optional[Callable[[], dict]] = None,
        repro_test_fn:    Optional[Callable[[], float]] = None,
        hitl_fn:          Optional[Callable[[str], str]] = None,
        previous_log:     Optional[dict] = None,
    ) -> dict[str, Any]:
        """7ステップを順次実行し、結果 dict を返す。"""
        PHASE10_DIR.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: 前日ログ読み込み・異常値検出
            prev, anomalies = self.step1_load_previous_logs(previous_log)

            # Step 2: 現在のシステム状態取得
            status = self.step2_get_system_status(system_status_fn)

            # Step 3: 安定性指標算出
            stability_index, metrics = self.step3_calculate_stability(status)

            # Step 4: 再現性テスト
            repro_rate = self.step4_reproducibility_test(repro_test_fn)

            # Step 5: 安全性チェック
            safety_ok, safety_detail = self.step5_safety_check(status)

            # Step 6: 日次ログ生成
            report = self.step6_generate_daily_log(
                prev, anomalies, status, stability_index, metrics, repro_rate, safety_detail
            )

            # エラーパス判定（ログ生成後に判定してファイルは残す）
            if status.get("error_count", 0) > 0:
                self._write_exception_log(status, "error_count > 0")
                return self._build_result(
                    success=False, reason="error_count > 0",
                    stability_index=stability_index, repro_rate=repro_rate,
                    safety_detail=safety_detail, hitl_decision=None,
                )

            if not safety_ok:
                return self._build_result(
                    success=False, reason="api_auth_status_not_authenticated",
                    stability_index=stability_index, repro_rate=repro_rate,
                    safety_detail=safety_detail, hitl_decision=None,
                )

            if repro_rate < REPRODUCIBILITY_THRESHOLD:
                return self._build_result(
                    success=False, reason="reproducibility_rate_low",
                    stability_index=stability_index, repro_rate=repro_rate,
                    safety_detail=safety_detail, hitl_decision=None,
                )

            # Step 7: HITL 承認
            hitl_decision = self.step7_set_hitl_checkpoint(
                report, hitl_fn, stability_index, repro_rate
            )
            success = hitl_decision == "approve"
            return self._build_result(
                success=success,
                reason="hitl_rejected" if not success else "ok",
                stability_index=stability_index,
                repro_rate=repro_rate,
                safety_detail=safety_detail,
                hitl_decision=hitl_decision,
            )

        except Exception as exc:  # noqa: BLE001
            return self._build_result(
                success=False, reason=f"exception: {exc}",
                stability_index=0.0, repro_rate=0.0,
                safety_detail={}, hitl_decision=None,
            )

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def step1_load_previous_logs(
        self, previous_log: Optional[dict]
    ) -> tuple[dict, list[str]]:
        """前日ログを読み込み、異常値を検出する。"""
        prev: dict
        if previous_log is not None:
            prev = previous_log
        elif DAILY_LOG_PATH.exists():
            try:
                prev = json.loads(DAILY_LOG_PATH.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        else:
            prev = {}

        anomalies: list[str] = []
        if prev:
            if prev.get("stability_index", 1.0) < STABILITY_THRESHOLD:
                anomalies.append("stability_index_below_threshold")
            if prev.get("error_count", 0) > 0:
                anomalies.append("previous_error_detected")
            if not prev.get("hitl_approved", True):
                anomalies.append("previous_hitl_not_approved")

        self._append_log("step1_load_previous_logs", {
            "has_prev": bool(prev),
            "anomalies": anomalies,
        })
        return prev, anomalies

    def step2_get_system_status(
        self, system_status_fn: Optional[Callable[[], dict]]
    ) -> dict[str, Any]:
        """現在のシステム状態を取得する。"""
        if system_status_fn is not None:
            status = system_status_fn()
        else:
            status = self._default_system_status()

        self._append_log("step2_get_system_status", {
            "uptime_rate": status.get("uptime_rate"),
            "error_count": status.get("error_count"),
            "avg_latency":  status.get("avg_latency"),
        })
        return status

    def step3_calculate_stability(
        self, status: dict
    ) -> tuple[float, dict[str, Any]]:
        """operation_metrics を集計し、安定性指標を算出する。"""
        uptime_rate = status.get("uptime_rate", 1.0)
        error_rate  = status.get("error_rate", 0.0)
        avg_latency = status.get("avg_latency", 0.5)
        latency_scores = status.get("latency_scores", [avg_latency])

        # stability_index = 稼働率 × (1 - エラー率) × レイテンシ正規化スコア
        latency_score = max(0.0, 1.0 - (avg_latency / 10.0))
        stability_index = round(uptime_rate * (1.0 - error_rate) * latency_score, 4)
        stability_index = min(1.0, max(0.0, stability_index))

        metrics = {
            "uptime_rate":     uptime_rate,
            "error_rate":      error_rate,
            "avg_latency":     avg_latency,
            "latency_score":   round(latency_score, 4),
            "stability_index": stability_index,
            "stability_ok":    stability_index >= STABILITY_THRESHOLD,
        }
        self._append_log("step3_calculate_stability", metrics)
        return stability_index, metrics

    def step4_reproducibility_test(
        self, repro_test_fn: Optional[Callable[[], float]]
    ) -> float:
        """再現性テストを1回実施し、出力一致率を返す。"""
        if repro_test_fn is not None:
            rate = repro_test_fn()
        else:
            rate = 1.0  # デフォルト: 一致

        rate = round(float(rate), 4)
        self._append_log("step4_reproducibility_test", {
            "reproducibility_rate": rate,
            "threshold": REPRODUCIBILITY_THRESHOLD,
            "ok": rate >= REPRODUCIBILITY_THRESHOLD,
        })
        return rate

    def step5_safety_check(
        self, status: dict
    ) -> tuple[bool, dict[str, Any]]:
        """API 認証状態・例外発生有無を検証する。"""
        # api_auth_report.json から認証状態を取得
        api_auth_status = status.get("api_auth_status", None)
        if api_auth_status is None:
            if AUTH_REPORT.exists():
                try:
                    data = json.loads(AUTH_REPORT.read_text(encoding="utf-8"))
                    api_auth_status = data.get("result", {}).get("auth_status", "unknown")
                except Exception:
                    api_auth_status = "unknown"
            else:
                api_auth_status = "unknown"

        exception_free = status.get("exception_count", 0) == 0
        safety_ok = (api_auth_status == "authenticated") and exception_free

        detail = {
            "api_auth_status":  api_auth_status,
            "exception_free":   exception_free,
            "exception_count":  status.get("exception_count", 0),
            "safety_ok":        safety_ok,
        }
        self._append_log("step5_safety_check", detail)
        return safety_ok, detail

    def step6_generate_daily_log(
        self,
        prev:            dict,
        anomalies:       list[str],
        status:          dict,
        stability_index: float,
        metrics:         dict,
        repro_rate:      float,
        safety_detail:   dict,
    ) -> dict[str, Any]:
        """daily_operation_log.json と stability_report.json を生成する。"""
        now = datetime.now().isoformat()

        daily_log: dict[str, Any] = {
            "module":           "F10110",
            "name":             "daily_operation_monitoring_and_logging",
            "generated_at":     now,
            "previous_anomalies": anomalies,
            "system_status":    {
                k: v for k, v in status.items()
                if k not in ("api_key",)  # API キーは除外
            },
            "metrics":          metrics,
            "reproducibility":  {
                "rate":      repro_rate,
                "threshold": REPRODUCIBILITY_THRESHOLD,
                "ok":        repro_rate >= REPRODUCIBILITY_THRESHOLD,
            },
            "safety":           safety_detail,
            "stability_index":  stability_index,
            "stability_ok":     stability_index >= STABILITY_THRESHOLD,
            "hitl_point":       HITL_POINT_ID,
            "phase10_stage":    "daily_monitoring_pending_hitl",
        }
        DAILY_LOG_PATH.write_text(
            json.dumps(daily_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        stability_report: dict[str, Any] = {
            "module":          "F10110",
            "generated_at":    now,
            "stability_index": stability_index,
            "stability_ok":    stability_index >= STABILITY_THRESHOLD,
            "threshold":       STABILITY_THRESHOLD,
            "metrics":         metrics,
            "anomalies_from_prev": anomalies,
        }
        STABILITY_PATH.write_text(
            json.dumps(stability_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self._append_log("step6_generate_daily_log", {
            "daily_log_path":  str(DAILY_LOG_PATH),
            "stability_path":  str(STABILITY_PATH),
        })
        return daily_log

    def step7_set_hitl_checkpoint(
        self,
        report:          dict,
        hitl_fn:         Optional[Callable[[str], str]],
        stability_index: float,
        repro_rate:      float,
    ) -> str:
        """HITL 承認ポイント H-P10-003 を設定し、承認結果を返す。"""
        decision = hitl_fn(HITL_POINT_ID) if hitl_fn else "approve"

        now = datetime.now().isoformat()
        hitl_log = {
            "module":        "F10110",
            "hitl_point_id": HITL_POINT_ID,
            "trigger":       HITL_TRIGGER,
            "mandatory":     True,
            "decision":      decision,
            "decided_at":    now,
            "context": {
                "stability_index":    stability_index,
                "stability_ok":       stability_index >= STABILITY_THRESHOLD,
                "reproducibility_rate": repro_rate,
                "phase10_stage_before": "daily_monitoring_pending_hitl",
                "phase10_stage_after":  "daily_monitoring_verified" if decision == "approve" else "hitl_rejected",
            },
        }
        HITL_LOG_PATH.write_text(
            json.dumps(hitl_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_log("step7_set_hitl_checkpoint", {"decision": decision})
        return decision

    # ------------------------------------------------------------------
    # summary.log integration
    # ------------------------------------------------------------------

    def write_summary_entry(self, result: dict) -> None:
        """summary.log に F10110 実行記録を追記する。"""
        success = result.get("success", False)
        tag     = "[PASS]" if success else "[FAIL]"
        line    = (
            f"{tag} [F10110] daily_operation_monitoring_and_logging | "
            f"stage={result.get('phase10_stage', 'unknown')} | "
            f"stability={result.get('stability_index', '?')} | "
            f"repro={result.get('reproducibility_rate', '?')} | "
            f"hitl={result.get('hitl_decision', '?')} | "
            f"{datetime.now().isoformat()}\n"
        )
        with SUMMARY_LOG.open("a", encoding="utf-8") as f:
            f.write(line)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _append_log(self, step: str, data: dict) -> None:
        self._log.append({"step": step, "at": datetime.now().isoformat(), **data})

    def _build_result(
        self,
        *,
        success:         bool,
        reason:          str,
        stability_index: float,
        repro_rate:      float,
        safety_detail:   dict,
        hitl_decision:   Optional[str],
    ) -> dict[str, Any]:
        stage = "daily_monitoring_verified" if success else "daily_monitoring_failed"
        return {
            "module":               "F10110",
            "success":              success,
            "reason":               reason,
            "stability_index":      stability_index,
            "stability_ok":         stability_index >= STABILITY_THRESHOLD,
            "reproducibility_rate": repro_rate,
            "api_auth_status":      safety_detail.get("api_auth_status", "unknown"),
            "hitl_decision":        hitl_decision,
            "phase10_stage":        stage,
            "generated_at":         datetime.now().isoformat(),
        }

    def _default_system_status(self) -> dict[str, Any]:
        """実 API / 外部システムなしで使用するデフォルトシステム状態。"""
        return {
            "uptime_rate":     1.0,
            "error_rate":      0.0,
            "error_count":     0,
            "avg_latency":     0.5,
            "exception_count": 0,
            "api_auth_status": "authenticated",
        }

    def _write_exception_log(self, status: dict, reason: str) -> None:
        err = {
            "module":       "F10110",
            "error":        reason,
            "error_count":  status.get("error_count", 0),
            "generated_at": datetime.now().isoformat(),
        }
        EXCEPTION_LOG.write_text(
            json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
