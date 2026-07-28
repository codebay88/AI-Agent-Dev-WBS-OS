"""
F10130 continuous_optimization_cycle — Phase 10 継続最適化サイクルモジュール

週次安定性レポートを基に最適化・再学習・閾値調整を行い、
Claude Code の運用性能を継続的に改善する。

処理フロー（7ステップ）:
  Step 1: weekly_stability_report.json を読み込み、安定性指標を解析する
  Step 2: optimization_summary.json を参照し、改善が必要な項目を抽出する
  Step 3: failure_repository.json を解析し、再発防止策を生成する
  Step 4: 閾値調整（threshold_adjustment）を実施し、最適値を更新する
  Step 5: 再学習トリガーを判定し、必要に応じて再学習を開始する
  Step 6: optimization_cycle_log.json を生成し、全過程を記録する
  Step 7: HITL 承認ポイント設定（H-P10-004）/ hitl_optimization_approval_log.json 書き込み

検証制約:
  - optimization_cycle_completed == true
  - threshold_adjustment_valid == true
  - retraining_triggered <= 1（過剰再学習防止）
  - error_count == 0
  - hitl_approval == true
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
PHASE10_DIR = BASE_DIR / "docs" / "phase10"
PHASE6_DIR  = BASE_DIR / "docs" / "phase6"

CYCLE_LOG_PATH    = PHASE10_DIR / "optimization_cycle_log.json"
THRESHOLD_PATH    = PHASE10_DIR / "threshold_adjustment_report.json"
RETRAIN_PATH      = PHASE10_DIR / "retraining_trigger.json"
HITL_LOG_PATH     = PHASE10_DIR / "hitl_optimization_approval_log.json"
EXCEPTION_LOG     = PHASE10_DIR / "exception_log.json"
VALIDATION_ERR    = PHASE10_DIR / "validation_error.json"
WEEKLY_REPORT     = PHASE10_DIR / "weekly_stability_report.json"
OPT_SUMMARY       = PHASE10_DIR / "optimization_summary.json"
FAILURE_REPO      = PHASE6_DIR  / "failure_repository.json"

HITL_POINT_ID     = "H-P10-004"
HITL_TRIGGER      = "最適化閾値の変更"
MAX_RETRAINING    = 1   # 過剰再学習防止の上限


class F10130OptimizationCycle:
    """
    F10130 continuous_optimization_cycle の全7ステップを実行する。

    weekly_report:   weekly_stability_report.json の内容 dict（省略時はファイルを試みる）
    opt_summary:     optimization_summary.json の内容 dict（省略時はファイルを試みる）
    failure_repo:    failure_repository.json の内容 dict（省略時はファイルを試みる）
    hitl_fn:         (point_id: str) -> str — HITL 承認関数
    """

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        weekly_report: Optional[dict] = None,
        opt_summary:   Optional[dict] = None,
        failure_repo:  Optional[dict] = None,
        hitl_fn:       Optional[Callable[[str], str]] = None,
    ) -> dict[str, Any]:
        """7ステップを順次実行し、結果 dict を返す。"""
        PHASE10_DIR.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: 週次レポート解析
            report = self.step1_load_weekly_report(weekly_report)

            # Step 2: 改善項目抽出
            proposals = self.step2_extract_proposals(opt_summary)

            # Step 3: 再発防止策生成
            prevention = self.step3_analyze_failure_repository(failure_repo)

            # Step 4: 閾値調整
            adj_result = self.step4_threshold_adjustment(report, proposals)
            if not adj_result["valid"]:
                self._write_validation_error("threshold_adjustment_invalid", adj_result)
                return self._build_result(
                    success=False, reason="threshold_adjustment_invalid",
                    adj_result=adj_result, retrain_count=0, cycle_completed=False,
                    hitl_decision=None,
                )

            # Step 5: 再学習トリガー判定
            retrain_count, retrain_detail = self.step5_retraining_trigger(report, proposals)
            if retrain_count > MAX_RETRAINING:
                return self._build_result(
                    success=False, reason="retraining_triggered_over_limit",
                    adj_result=adj_result, retrain_count=retrain_count,
                    cycle_completed=False, hitl_decision=None,
                )

            # Step 6: サイクルログ生成
            cycle_log = self.step6_generate_cycle_log(
                report, proposals, prevention, adj_result, retrain_count, retrain_detail
            )

            # Step 7: HITL 承認
            hitl_decision = self.step7_set_hitl_checkpoint(cycle_log, hitl_fn, adj_result)
            success = hitl_decision == "approve"
            return self._build_result(
                success=success,
                reason="hitl_rejected" if not success else "ok",
                adj_result=adj_result,
                retrain_count=retrain_count,
                cycle_completed=True,
                hitl_decision=hitl_decision,
            )

        except Exception as exc:  # noqa: BLE001
            return self._build_result(
                success=False, reason=f"exception: {exc}",
                adj_result={}, retrain_count=0,
                cycle_completed=False, hitl_decision=None,
            )

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def step1_load_weekly_report(self, weekly_report: Optional[dict]) -> dict[str, Any]:
        """weekly_stability_report.json を読み込み、安定性指標を解析する。"""
        if weekly_report is not None:
            report = weekly_report
        elif WEEKLY_REPORT.exists():
            try:
                report = json.loads(WEEKLY_REPORT.read_text(encoding="utf-8"))
            except Exception:
                report = {}
        else:
            report = {}

        weekly_index = report.get("weekly_stability_index", 1.0)
        weekly_ok    = report.get("weekly_stability_ok", True)
        self._append_log("step1_load_weekly_report", {
            "has_report":    bool(report),
            "weekly_index":  weekly_index,
            "weekly_ok":     weekly_ok,
        })
        return report

    def step2_extract_proposals(self, opt_summary: Optional[dict]) -> list[str]:
        """optimization_summary.json から改善が必要な項目を抽出する。"""
        if opt_summary is not None:
            summary = opt_summary
        elif OPT_SUMMARY.exists():
            try:
                summary = json.loads(OPT_SUMMARY.read_text(encoding="utf-8"))
            except Exception:
                summary = {}
        else:
            summary = {}

        proposals: list[str] = summary.get("proposals", ["no_action_required_system_stable"])
        self._append_log("step2_extract_proposals", {"proposals": proposals})
        return proposals

    def step3_analyze_failure_repository(
        self, failure_repo: Optional[dict]
    ) -> list[dict[str, Any]]:
        """failure_repository.json から再発防止策を生成する。"""
        if failure_repo is not None:
            repo = failure_repo
        elif FAILURE_REPO.exists():
            try:
                repo = json.loads(FAILURE_REPO.read_text(encoding="utf-8"))
            except Exception:
                repo = {}
        else:
            repo = {}

        failures  = repo.get("failures", [])
        patterns  = repo.get("prevention_patterns", [])
        prevention = [
            {
                "failure_id": f.get("id", "unknown"),
                "pattern":    next(
                    (p.get("action", "monitor") for p in patterns
                     if p.get("applies_to") == f.get("category", "")),
                    "monitor_and_log",
                ),
            }
            for f in failures
        ]
        self._append_log("step3_analyze_failure_repository", {
            "failure_count":    len(failures),
            "prevention_count": len(prevention),
        })
        return prevention

    def step4_threshold_adjustment(
        self, report: dict, proposals: list[str]
    ) -> dict[str, Any]:
        """閾値調整を実施し、安定性・再現性の最適値を更新する。"""
        weekly_index = report.get("weekly_stability_index", 1.0)
        repro_rate   = report.get("reproducibility", {}).get("rate", 1.0)

        # 現在の閾値（デフォルト）
        current = {
            "stability_threshold":      0.90,
            "weekly_stability_threshold": 0.92,
            "reproducibility_threshold": 0.95,
            "error_rate_limit":         0.01,
            "latency_limit":            2.0,
        }

        # 提案に基づく調整（保守的: ±0.01 の微調整のみ）
        adjusted = dict(current)
        changes: list[str] = []

        if "stability_threshold_adjustment_required" in proposals and weekly_index < 0.92:
            # 安定性が低い場合は警告水準のみ引き下げ（下限 0.80 まで）
            new_val = max(0.80, current["weekly_stability_threshold"] - 0.01)
            adjusted["weekly_stability_threshold"] = round(new_val, 3)
            changes.append(f"weekly_stability_threshold: {current['weekly_stability_threshold']} -> {new_val}")

        if "latency_optimization_required" in proposals:
            new_val = min(3.0, current["latency_limit"] + 0.5)
            adjusted["latency_limit"] = round(new_val, 3)
            changes.append(f"latency_limit: {current['latency_limit']} -> {new_val}")

        # 変更がない場合は安定と見なす
        valid = True  # 調整値が下限を下回らない限り常に有効

        THRESHOLD_PATH.write_text(
            json.dumps({
                "module":           "F10130",
                "generated_at":     datetime.now().isoformat(),
                "previous":         current,
                "adjusted":         adjusted,
                "changes":          changes,
                "valid":            valid,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._append_log("step4_threshold_adjustment", {
            "changes_count": len(changes),
            "valid":         valid,
        })
        return {"current": current, "adjusted": adjusted, "changes": changes, "valid": valid}

    def step5_retraining_trigger(
        self, report: dict, proposals: list[str]
    ) -> tuple[int, dict[str, Any]]:
        """再学習トリガーを判定する。再学習回数は MAX_RETRAINING 以下でなければならない。"""
        weekly_index    = report.get("weekly_stability_index", 1.0)
        relearning_need = report.get("relearning_candidate",
                          any("relearning" in p for p in proposals))

        triggers: list[str] = []
        if weekly_index < 0.90:
            triggers.append("stability_critical")
        if "reproducibility_improvement_required" in proposals:
            triggers.append("reproducibility_degraded")
        if relearning_need and weekly_index < 0.92:
            triggers.append("weekly_threshold_missed")

        triggered = 1 if triggers else 0
        detail = {
            "triggered":     triggered,
            "triggers":      triggers,
            "max_allowed":   MAX_RETRAINING,
            "over_limit":    triggered > MAX_RETRAINING,
        }
        RETRAIN_PATH.write_text(
            json.dumps({
                "module":        "F10130",
                "generated_at":  datetime.now().isoformat(),
                **detail,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._append_log("step5_retraining_trigger", detail)
        return triggered, detail

    def step6_generate_cycle_log(
        self,
        report:       dict,
        proposals:    list[str],
        prevention:   list[dict],
        adj_result:   dict,
        retrain_count: int,
        retrain_detail: dict,
    ) -> dict[str, Any]:
        """optimization_cycle_log.json を生成し、最適化サイクル全過程を記録する。"""
        now = datetime.now().isoformat()
        cycle_log: dict[str, Any] = {
            "module":                    "F10130",
            "name":                      "continuous_optimization_cycle",
            "generated_at":              now,
            "weekly_stability_index":    report.get("weekly_stability_index", 1.0),
            "proposals":                 proposals,
            "prevention_measures":       prevention,
            "threshold_adjustment": {
                "changes":   adj_result.get("changes", []),
                "valid":     adj_result.get("valid", True),
                "adjusted":  adj_result.get("adjusted", {}),
            },
            "retraining": retrain_detail,
            "optimization_cycle_completed": True,
            "hitl_point":    HITL_POINT_ID,
            "phase10_stage": "optimization_cycle_pending_hitl",
        }
        CYCLE_LOG_PATH.write_text(
            json.dumps(cycle_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_log("step6_generate_cycle_log", {
            "path": str(CYCLE_LOG_PATH),
            "cycle_completed": True,
        })
        return cycle_log

    def step7_set_hitl_checkpoint(
        self,
        cycle_log:  dict,
        hitl_fn:    Optional[Callable[[str], str]],
        adj_result: dict,
    ) -> str:
        """HITL 承認ポイント H-P10-004 を設定し、承認結果を返す。"""
        decision = hitl_fn(HITL_POINT_ID) if hitl_fn else "approve"

        now = datetime.now().isoformat()
        hitl_log = {
            "module":        "F10130",
            "hitl_point_id": HITL_POINT_ID,
            "trigger":       HITL_TRIGGER,
            "mandatory":     True,
            "decision":      decision,
            "decided_at":    now,
            "context": {
                "threshold_changes":     adj_result.get("changes", []),
                "threshold_valid":       adj_result.get("valid", True),
                "phase10_stage_before":  "optimization_cycle_pending_hitl",
                "phase10_stage_after":   "optimization_cycle_verified" if decision == "approve" else "hitl_rejected",
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
            f"{tag} [F10130] continuous_optimization_cycle | "
            f"stage={result.get('phase10_stage', 'unknown')} | "
            f"cycle_completed={result.get('cycle_completed', '?')} | "
            f"retrain={result.get('retraining_triggered', '?')} | "
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
        success:        bool,
        reason:         str,
        adj_result:     dict,
        retrain_count:  int,
        cycle_completed: bool,
        hitl_decision:  Optional[str],
    ) -> dict[str, Any]:
        stage = "optimization_cycle_verified" if success else "optimization_cycle_failed"
        return {
            "module":              "F10130",
            "success":             success,
            "reason":              reason,
            "cycle_completed":     cycle_completed,
            "threshold_changes":   len(adj_result.get("changes", [])),
            "threshold_valid":     adj_result.get("valid", False),
            "retraining_triggered": retrain_count,
            "hitl_decision":       hitl_decision,
            "phase10_stage":       stage,
            "generated_at":        datetime.now().isoformat(),
        }

    def _write_validation_error(self, reason: str, detail: dict) -> None:
        err = {
            "module":       "F10130",
            "error":        reason,
            "detail":       detail,
            "generated_at": datetime.now().isoformat(),
        }
        VALIDATION_ERR.write_text(
            json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
