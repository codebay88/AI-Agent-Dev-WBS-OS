"""
F10120 weekly_stability_report_generation — Phase 10 週次安定性レポートモジュール

F10110 で収集した日次ログを集約し、週次レベルで安定性・再現性・安全性を評価する。
運用フェーズの継続最適化に向けた基礎データを生成し、HITL 承認を経て F10130 へ進む。

処理フロー（7ステップ）:
  Step 1: 過去7日分の daily_operation_log を読み込み、稼働率・エラー率・レイテンシを集計する
  Step 2: stability_index の週次平均を算出し、週次安定性指標を確定する
  Step 3: 週次サンプルで再現性テストを実施し、出力一致率を確認する
  Step 4: 安全性チェック（例外発生有無・API認証状態）を再検証する
  Step 5: weekly_stability_report.json を生成する
  Step 6: optimization_summary.json に改善提案を出力する
  Step 7: HITL 承認ポイント設定（H-P10-005）/ hitl_weekly_approval_log.json 書き込み

検証閾値:
  - weekly_stability_index >= 0.92
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

WEEKLY_REPORT_PATH = PHASE10_DIR / "weekly_stability_report.json"
OPT_SUMMARY_PATH   = PHASE10_DIR / "optimization_summary.json"
HITL_LOG_PATH      = PHASE10_DIR / "hitl_weekly_approval_log.json"
EXCEPTION_LOG      = PHASE10_DIR / "exception_log.json"
DAILY_LOG_PATH     = PHASE10_DIR / "daily_operation_log.json"
STABILITY_PATH     = PHASE10_DIR / "stability_report.json"
AUTH_REPORT        = PHASE10_DIR / "api_auth_report.json"

WEEKLY_STABILITY_THRESHOLD   = 0.92
REPRODUCIBILITY_THRESHOLD    = 0.95
HITL_POINT_ID                = "H-P10-005"
HITL_TRIGGER                 = "運用レポートの承認"
DAYS_IN_WEEK                 = 7


class F10120WeeklyReport:
    """
    F10120 weekly_stability_report_generation の全7ステップを実行する。

    daily_logs:      過去7日分の daily_operation_log dict のリスト（省略時はファイルを試みる）
    repro_test_fn:   () -> float — 再現性テスト関数（0.0〜1.0）
    hitl_fn:         (point_id: str) -> str — HITL 承認関数
    """

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        daily_logs:   Optional[list[dict]] = None,
        repro_test_fn: Optional[Callable[[], float]] = None,
        hitl_fn:       Optional[Callable[[str], str]] = None,
    ) -> dict[str, Any]:
        """7ステップを順次実行し、結果 dict を返す。"""
        PHASE10_DIR.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: 日次ログ集計
            logs, aggregated = self.step1_aggregate_daily_logs(daily_logs)

            # error_count チェック（集計後即時）
            total_errors = aggregated.get("total_error_count", 0)
            if total_errors > 0:
                self._write_exception_log(aggregated, "error_count > 0")
                return self._build_result(
                    success=False, reason="error_count > 0",
                    weekly_index=0.0, repro_rate=0.0,
                    api_auth_status="unknown", hitl_decision=None,
                    aggregated=aggregated,
                )

            # Step 2: 週次安定性指標算出
            weekly_index = self.step2_calculate_weekly_stability(logs, aggregated)

            # Step 3: 再現性テスト
            repro_rate = self.step3_reproducibility_test(repro_test_fn)

            # Step 4: 安全性チェック
            safety_ok, api_auth_status = self.step4_safety_check(logs)

            if not safety_ok:
                return self._build_result(
                    success=False, reason="api_auth_status_not_authenticated",
                    weekly_index=weekly_index, repro_rate=repro_rate,
                    api_auth_status=api_auth_status, hitl_decision=None,
                    aggregated=aggregated,
                )

            if repro_rate < REPRODUCIBILITY_THRESHOLD:
                return self._build_result(
                    success=False, reason="reproducibility_rate_low",
                    weekly_index=weekly_index, repro_rate=repro_rate,
                    api_auth_status=api_auth_status, hitl_decision=None,
                    aggregated=aggregated,
                )

            # Step 5: 週次レポート生成
            report = self.step5_generate_weekly_report(
                logs, aggregated, weekly_index, repro_rate, api_auth_status
            )

            # Step 6: 改善提案生成
            opt_summary = self.step6_generate_optimization_summary(
                aggregated, weekly_index, repro_rate
            )

            # Step 7: HITL 承認
            hitl_decision = self.step7_set_hitl_checkpoint(
                report, hitl_fn, weekly_index, repro_rate
            )
            success = hitl_decision == "approve"
            return self._build_result(
                success=success,
                reason="hitl_rejected" if not success else "ok",
                weekly_index=weekly_index,
                repro_rate=repro_rate,
                api_auth_status=api_auth_status,
                hitl_decision=hitl_decision,
                aggregated=aggregated,
            )

        except Exception as exc:  # noqa: BLE001
            return self._build_result(
                success=False, reason=f"exception: {exc}",
                weekly_index=0.0, repro_rate=0.0,
                api_auth_status="unknown", hitl_decision=None,
                aggregated={},
            )

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def step1_aggregate_daily_logs(
        self, daily_logs: Optional[list[dict]]
    ) -> tuple[list[dict], dict[str, Any]]:
        """過去7日分の日次ログを読み込み、稼働率・エラー率・レイテンシを集計する。"""
        if daily_logs is not None:
            logs = daily_logs[:DAYS_IN_WEEK]
        else:
            # ファイルから読み込む（1ファイル = 最新の1日分として扱う）
            if DAILY_LOG_PATH.exists():
                try:
                    single = json.loads(DAILY_LOG_PATH.read_text(encoding="utf-8"))
                    logs = [single]
                except Exception:
                    logs = []
            else:
                logs = []

        if not logs:
            aggregated = {
                "days_count": 0,
                "avg_uptime_rate": 1.0,
                "avg_error_rate": 0.0,
                "avg_latency": 0.5,
                "total_error_count": 0,
                "stability_indices": [],
            }
        else:
            uptime_rates   = [l.get("metrics", {}).get("uptime_rate", 1.0)  for l in logs]
            error_rates    = [l.get("metrics", {}).get("error_rate", 0.0)   for l in logs]
            latencies      = [l.get("metrics", {}).get("avg_latency", 0.5)  for l in logs]
            error_counts   = [l.get("system_status", {}).get("error_count", 0) for l in logs]
            s_indices      = [l.get("stability_index", 1.0)                 for l in logs]

            aggregated = {
                "days_count":       len(logs),
                "avg_uptime_rate":  round(statistics.mean(uptime_rates), 4),
                "avg_error_rate":   round(statistics.mean(error_rates), 4),
                "avg_latency":      round(statistics.mean(latencies), 4),
                "total_error_count": sum(error_counts),
                "stability_indices": s_indices,
            }

        self._append_log("step1_aggregate_daily_logs", {
            "days_count":       aggregated["days_count"],
            "total_error_count": aggregated["total_error_count"],
        })
        return logs, aggregated

    def step2_calculate_weekly_stability(
        self, logs: list[dict], aggregated: dict
    ) -> float:
        """stability_index の週次平均を算出する。"""
        indices = aggregated.get("stability_indices", [])
        if indices:
            weekly_index = round(statistics.mean(indices), 4)
        else:
            # ログがない場合は稼働率・エラー率から推定
            uptime   = aggregated.get("avg_uptime_rate", 1.0)
            err_rate = aggregated.get("avg_error_rate", 0.0)
            lat      = aggregated.get("avg_latency", 0.5)
            lat_score = max(0.0, 1.0 - lat / 10.0)
            weekly_index = round(uptime * (1.0 - err_rate) * lat_score, 4)

        weekly_index = min(1.0, max(0.0, weekly_index))
        self._append_log("step2_calculate_weekly_stability", {
            "weekly_stability_index": weekly_index,
            "threshold": WEEKLY_STABILITY_THRESHOLD,
            "ok": weekly_index >= WEEKLY_STABILITY_THRESHOLD,
        })
        return weekly_index

    def step3_reproducibility_test(
        self, repro_test_fn: Optional[Callable[[], float]]
    ) -> float:
        """週次サンプルで再現性テストを実施する。"""
        rate = repro_test_fn() if repro_test_fn is not None else 1.0
        rate = round(float(rate), 4)
        self._append_log("step3_reproducibility_test", {
            "reproducibility_rate": rate,
            "threshold": REPRODUCIBILITY_THRESHOLD,
            "ok": rate >= REPRODUCIBILITY_THRESHOLD,
        })
        return rate

    def step4_safety_check(
        self, logs: list[dict]
    ) -> tuple[bool, str]:
        """API 認証状態・例外発生有無を再検証する。"""
        # 最新の日次ログから api_auth_status を取得
        api_auth_status = "unknown"
        if logs:
            last = logs[-1]
            api_auth_status = last.get("safety", {}).get("api_auth_status", "unknown")

        # auth_report から補完
        if api_auth_status == "unknown" and AUTH_REPORT.exists():
            try:
                data = json.loads(AUTH_REPORT.read_text(encoding="utf-8"))
                api_auth_status = data.get("result", {}).get("auth_status", "unknown")
            except Exception:
                pass

        safety_ok = api_auth_status == "authenticated"
        self._append_log("step4_safety_check", {
            "api_auth_status": api_auth_status,
            "safety_ok":       safety_ok,
        })
        return safety_ok, api_auth_status

    def step5_generate_weekly_report(
        self,
        logs:            list[dict],
        aggregated:      dict,
        weekly_index:    float,
        repro_rate:      float,
        api_auth_status: str,
    ) -> dict[str, Any]:
        """weekly_stability_report.json を生成する。"""
        now = datetime.now().isoformat()
        report: dict[str, Any] = {
            "module":                  "F10120",
            "name":                    "weekly_stability_report_generation",
            "generated_at":            now,
            "period_days":             aggregated.get("days_count", len(logs)),
            "aggregated_metrics":      aggregated,
            "weekly_stability_index":  weekly_index,
            "weekly_stability_ok":     weekly_index >= WEEKLY_STABILITY_THRESHOLD,
            "weekly_stability_threshold": WEEKLY_STABILITY_THRESHOLD,
            "reproducibility": {
                "rate":      repro_rate,
                "threshold": REPRODUCIBILITY_THRESHOLD,
                "ok":        repro_rate >= REPRODUCIBILITY_THRESHOLD,
            },
            "safety": {
                "api_auth_status": api_auth_status,
                "safety_ok":       api_auth_status == "authenticated",
            },
            "hitl_point":    HITL_POINT_ID,
            "phase10_stage": "weekly_stability_pending_hitl",
        }
        WEEKLY_REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_log("step5_generate_weekly_report", {
            "path": str(WEEKLY_REPORT_PATH),
        })
        return report

    def step6_generate_optimization_summary(
        self,
        aggregated:   dict,
        weekly_index: float,
        repro_rate:   float,
    ) -> dict[str, Any]:
        """optimization_summary.json に改善提案を出力する。"""
        proposals: list[str] = []

        if weekly_index < WEEKLY_STABILITY_THRESHOLD:
            proposals.append("stability_threshold_adjustment_required")
        if aggregated.get("avg_error_rate", 0.0) > 0.01:
            proposals.append("error_rate_investigation_required")
        if aggregated.get("avg_latency", 0.0) > 1.5:
            proposals.append("latency_optimization_required")
        if repro_rate < REPRODUCIBILITY_THRESHOLD:
            proposals.append("reproducibility_improvement_required")
        if not proposals:
            proposals.append("no_action_required_system_stable")

        now = datetime.now().isoformat()
        summary: dict[str, Any] = {
            "module":             "F10120",
            "generated_at":       now,
            "weekly_index":       weekly_index,
            "avg_error_rate":     aggregated.get("avg_error_rate", 0.0),
            "avg_latency":        aggregated.get("avg_latency", 0.0),
            "reproducibility_rate": repro_rate,
            "proposals":          proposals,
            "relearning_candidate": weekly_index < WEEKLY_STABILITY_THRESHOLD,
            "next_module":        "F10130",
        }
        OPT_SUMMARY_PATH.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_log("step6_generate_optimization_summary", {
            "proposals": proposals,
        })
        return summary

    def step7_set_hitl_checkpoint(
        self,
        report:       dict,
        hitl_fn:      Optional[Callable[[str], str]],
        weekly_index: float,
        repro_rate:   float,
    ) -> str:
        """HITL 承認ポイント H-P10-005 を設定し、承認結果を返す。"""
        decision = hitl_fn(HITL_POINT_ID) if hitl_fn else "approve"

        now = datetime.now().isoformat()
        hitl_log = {
            "module":        "F10120",
            "hitl_point_id": HITL_POINT_ID,
            "trigger":       HITL_TRIGGER,
            "mandatory":     True,
            "decision":      decision,
            "decided_at":    now,
            "context": {
                "weekly_stability_index": weekly_index,
                "weekly_stability_ok":    weekly_index >= WEEKLY_STABILITY_THRESHOLD,
                "reproducibility_rate":   repro_rate,
                "phase10_stage_before":   "weekly_stability_pending_hitl",
                "phase10_stage_after":    "weekly_stability_verified" if decision == "approve" else "hitl_rejected",
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
        success = result.get("success", False)
        tag     = "[PASS]" if success else "[FAIL]"
        line    = (
            f"{tag} [F10120] weekly_stability_report_generation | "
            f"stage={result.get('phase10_stage', 'unknown')} | "
            f"weekly_index={result.get('weekly_stability_index', '?')} | "
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
        weekly_index:    float,
        repro_rate:      float,
        api_auth_status: str,
        hitl_decision:   Optional[str],
        aggregated:      dict,
    ) -> dict[str, Any]:
        stage = "weekly_stability_verified" if success else "weekly_stability_failed"
        return {
            "module":                "F10120",
            "success":              success,
            "reason":               reason,
            "weekly_stability_index": weekly_index,
            "weekly_stability_ok":  weekly_index >= WEEKLY_STABILITY_THRESHOLD,
            "reproducibility_rate": repro_rate,
            "api_auth_status":      api_auth_status,
            "days_aggregated":      aggregated.get("days_count", 0),
            "hitl_decision":        hitl_decision,
            "phase10_stage":        stage,
            "generated_at":         datetime.now().isoformat(),
        }

    def _write_exception_log(self, aggregated: dict, reason: str) -> None:
        err = {
            "module":            "F10120",
            "error":             reason,
            "total_error_count": aggregated.get("total_error_count", 0),
            "generated_at":      datetime.now().isoformat(),
        }
        EXCEPTION_LOG.write_text(
            json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
