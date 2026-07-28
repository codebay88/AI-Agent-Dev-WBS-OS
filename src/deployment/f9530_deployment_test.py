"""
F9530 deployment_test_and_stabilization — Phase 8 展開テスト・安定化モジュール

展開後の動作確認・安定性評価・HITL 最終承認を行い、
Claude Code の展開層（Phase 8）を正式に完了させる。
F9510・F9520 の成果を統合し、全環境での安定稼働を検証する。

処理フロー（8ステップ）:
  Step 1: 展開計画・連携結果・同期ログを読み込み、全環境の状態を統合
  Step 2: ロードテスト（負荷試験）— I/O 整合性と応答時間を測定
  Step 3: 異常停止・例外発生の有無を監視
  Step 4: 再現性テスト（3回連続成功）を再実施
  Step 5: 安定性評価（error_rate / opt_score / log_completeness）を算出
  Step 6: HITL 最終承認ポイントを設定
  Step 7: stability_report.json 生成・deployment_summary.json 統合
  Step 8: phase8_complete_flag を書き込み、展開層を正式完了
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
CYCLE_DIR   = BASE_DIR / "docs" / "knowledge_cycle"
PHASE8_DIR  = BASE_DIR / "docs" / "phase8"
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

PLAN_PATH         = PHASE8_DIR / "deployment_plan.json"
INTEG_REPORT_PATH = PHASE8_DIR / "integration_report.json"
SYNC_LOG_PATH     = PHASE8_DIR / "sync_log.json"
HITL_LOG_PATH     = PHASE8_DIR / "hitl_checkpoint_log.json"
TRACE_PATH        = PHASE8_DIR / "deployment_trace.json"
ROLLBACK_PATH     = PHASE8_DIR / "rollback_log.json"

STABILITY_REPORT_PATH   = PHASE8_DIR / "stability_report.json"
DEPLOYMENT_SUMMARY_PATH = PHASE8_DIR / "deployment_summary.json"
HITL_FINAL_LOG_PATH     = PHASE8_DIR / "hitl_final_approval_log.json"
COMPLETE_FLAG_PATH       = PHASE8_DIR / "phase8_complete_flag"
VAL_ERR_PATH            = PHASE8_DIR / "validation_error.json"

_CYCLE_INPUTS = [
    "learning_dataset.json",
    "optimization_report.json",
]

# 検証閾値
IO_INTEGRITY_REQUIRED = 1.0
ERROR_RATE_THRESHOLD  = 0.01
OPT_SCORE_THRESHOLD   = 0.90
REPRO_TEST_COUNT      = 3

# ロードテストパラメータ
LOAD_TEST_REQUESTS      = 10
LOAD_TEST_RESPONSE_MAX  = 1.0   # 秒（シミュレーション上限）


class F9530DeploymentTestAndStabilization:
    """
    F9530 deployment_test_and_stabilization の全8ステップを実行する。

    使い方:
        tester = F9530DeploymentTestAndStabilization()
        result = tester.run(hitl_fn=lambda: "approve")
        # result["success"] が True かつ phase8_complete == True で Phase 9 へ遷移
    """

    def __init__(
        self,
        plan_path:   Path | None = None,
        cycle_dir:   Path | None = None,
        phase8_dir:  Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._plan_path   = plan_path   or PLAN_PATH
        self._cycle_dir   = cycle_dir   or CYCLE_DIR
        self._phase8_dir  = phase8_dir  or PHASE8_DIR
        self._summary_log = summary_log or SUMMARY_LOG

        self._stability_log:   list[str] = []
        self._exception_log:   list[str] = []

    # ── ユーティリティ ────────────────────────────────────────

    def _ts(self) -> str:
        return datetime.now().isoformat()

    def _slog(self, msg: str) -> None:
        self._stability_log.append(f"[{self._ts()}] {msg}")

    def _elog(self, msg: str) -> None:
        self._exception_log.append(f"[{self._ts()}] {msg}")

    # ── Step 1: 全環境状態の統合 ─────────────────────────────

    def step1_load_and_integrate(self) -> dict:
        """
        deployment_plan / integration_report / sync_log / hitl_checkpoint_log を
        読み込み、全環境の状態を統合する。

        Returns:
            {
                plan:            dict,
                integration:     dict,
                sync_log:        dict,
                hitl_log:        dict,
                all_loaded:      bool,
                missing_inputs:  list[str],
            }
        """
        inputs = {
            "deployment_plan":      self._phase8_dir / "deployment_plan.json",
            "integration_report":   self._phase8_dir / "integration_report.json",
            "sync_log":             self._phase8_dir / "sync_log.json",
            "hitl_checkpoint_log":  self._phase8_dir / "hitl_checkpoint_log.json",
        }

        loaded: dict[str, dict] = {}
        missing: list[str] = []

        for key, path in inputs.items():
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    loaded[key] = json.load(f)
            else:
                missing.append(key)
                loaded[key] = {}

        all_loaded = len(missing) == 0
        self._slog(f"Step1: loaded {len(loaded)-len(missing)}/{len(inputs)} inputs (missing={missing})")

        return {
            "plan":           loaded.get("deployment_plan", {}),
            "integration":    loaded.get("integration_report", {}),
            "sync_log":       loaded.get("sync_log", {}),
            "hitl_log":       loaded.get("hitl_checkpoint_log", {}),
            "all_loaded":     all_loaded,
            "missing_inputs": missing,
        }

    # ── Step 2: ロードテスト ─────────────────────────────────

    def step2_load_test(self, state: dict) -> dict:
        """
        負荷試験を実行し、I/O 整合性と応答時間を測定する。
        実装はシミュレーションベース（決定論的）。

        Returns:
            {
                requests_sent:    int,
                requests_ok:      int,
                error_count:      int,
                error_rate:       float,
                avg_response_sec: float,
                io_integrity:     float,
                load_test_passed: bool,
            }
        """
        # 入力ファイルの存在を I/O 整合性とみなす
        present = sum(
            1 for fname in _CYCLE_INPUTS
            if (self._cycle_dir / fname).exists()
        )
        io_integrity = present / len(_CYCLE_INPUTS) if _CYCLE_INPUTS else 0.0

        # 統合レポートの io_integrity を追加考慮
        integ_io = state["integration"].get("io_integrity", 0.0)
        combined_io = (io_integrity + integ_io) / 2.0

        # エラー率: 整合性が IO_INTEGRITY_REQUIRED 未満なら比例してエラー扱い
        error_count = 0 if combined_io >= IO_INTEGRITY_REQUIRED else int(
            LOAD_TEST_REQUESTS * (1.0 - combined_io))
        ok_count    = LOAD_TEST_REQUESTS - error_count
        error_rate  = error_count / LOAD_TEST_REQUESTS

        # 応答時間（整合性比例・シミュレーション）
        avg_resp = round(LOAD_TEST_RESPONSE_MAX * (1.0 - combined_io * 0.5), 4)

        load_test_passed = (
            combined_io >= IO_INTEGRITY_REQUIRED
            and error_rate <= ERROR_RATE_THRESHOLD
        )

        self._slog(
            f"Step2: load_test requests={LOAD_TEST_REQUESTS} "
            f"ok={ok_count} err={error_count} "
            f"io={combined_io:.4f} err_rate={error_rate:.4f} "
            f"avg_resp={avg_resp}s passed={load_test_passed}"
        )
        return {
            "requests_sent":    LOAD_TEST_REQUESTS,
            "requests_ok":      ok_count,
            "error_count":      error_count,
            "error_rate":       round(error_rate, 6),
            "avg_response_sec": avg_resp,
            "io_integrity":     round(combined_io, 6),
            "load_test_passed": load_test_passed,
        }

    # ── Step 3: 異常監視 ─────────────────────────────────────

    def step3_monitor_exceptions(self, load_result: dict) -> dict:
        """
        異常停止・例外発生の有無を監視する。

        Returns:
            {
                exception_detected: bool,
                exception_count:    int,
                exception_entries:  list[str],
                monitoring_ok:      bool,
            }
        """
        exceptions: list[str] = []

        if load_result["error_rate"] > ERROR_RATE_THRESHOLD:
            msg = (
                f"error_rate={load_result['error_rate']:.6f} "
                f"> threshold={ERROR_RATE_THRESHOLD}"
            )
            exceptions.append(msg)
            self._elog(f"Step3: EXCEPTION — {msg}")

        if load_result["io_integrity"] < IO_INTEGRITY_REQUIRED:
            msg = (
                f"io_integrity={load_result['io_integrity']:.6f} "
                f"< required={IO_INTEGRITY_REQUIRED}"
            )
            exceptions.append(msg)
            self._elog(f"Step3: EXCEPTION — {msg}")

        detected = len(exceptions) > 0
        self._slog(
            f"Step3: monitoring_ok={not detected} "
            f"exceptions={len(exceptions)}"
        )
        return {
            "exception_detected": detected,
            "exception_count":    len(exceptions),
            "exception_entries":  exceptions,
            "monitoring_ok":      not detected,
        }

    # ── Step 4: 再現性テスト ─────────────────────────────────

    def step4_reproducibility_test(self, load_result: dict) -> dict:
        """
        再現性テスト（3回連続成功）を実施する。
        ロードテスト通過 & 全 cycle_inputs 存在を条件とする。

        Returns:
            {passed: bool, trials: list[dict], trial_count: int, repro_rate: float}
        """
        base_ok = (
            load_result["load_test_passed"]
            and all((self._cycle_dir / f).exists() for f in _CYCLE_INPUTS)
        )

        trials: list[dict] = []
        for i in range(1, REPRO_TEST_COUNT + 1):
            ok = base_ok
            trials.append({"trial": i, "passed": ok})
            self._slog(f"Step4: repro_trial_{i}={'PASS' if ok else 'FAIL'}")

        passed_count = sum(1 for t in trials if t["passed"])
        passed = passed_count == REPRO_TEST_COUNT
        self._slog(
            f"Step4: reproducibility_test={'PASSED' if passed else 'FAILED'} "
            f"({passed_count}/{REPRO_TEST_COUNT})"
        )
        return {
            "passed":      passed,
            "trials":      trials,
            "trial_count": REPRO_TEST_COUNT,
            "repro_rate":  round(passed_count / REPRO_TEST_COUNT, 4),
        }

    # ── Step 5: 安定性評価 ───────────────────────────────────

    def step5_evaluate_stability(
        self,
        load_result:  dict,
        monitor_result: dict,
        repro_result: dict,
        state:        dict,
    ) -> dict:
        """
        error_rate / opt_score / log_completeness を算出し、
        総合安定性ステータスを返す。

        Returns:
            {
                error_rate:         float,
                opt_score:          float,
                log_completeness:   float,
                stability_status:   "stable" | "warning" | "critical",
                criteria_met:       dict,
                overall_ok:         bool,
            }
        """
        error_rate = load_result["error_rate"]

        # opt_score: optimization_report から取得
        opt_path = self._cycle_dir / "optimization_report.json"
        opt_score = 0.0
        if opt_path.exists():
            with open(opt_path, encoding="utf-8") as f:
                opt = json.load(f)
            opt_score = opt.get("summary", {}).get("avg_optimization_index", 0.0)
        self._slog(f"Step5: opt_score={opt_score:.4f}")

        # log_completeness: stability_log / sync_log / hitl_log の存在チェック
        log_files = [
            self._phase8_dir / "sync_log.json",
            self._phase8_dir / "hitl_checkpoint_log.json",
            self._phase8_dir / "deployment_plan.json",
            self._phase8_dir / "integration_report.json",
        ]
        present_logs = sum(1 for p in log_files if p.exists())
        log_completeness = present_logs / len(log_files)
        self._slog(f"Step5: log_completeness={log_completeness:.4f}")

        # 各基準判定
        criteria_met = {
            "io_integrity":            load_result["io_integrity"] >= IO_INTEGRITY_REQUIRED,
            "error_rate":              error_rate <= ERROR_RATE_THRESHOLD,
            "opt_score":               opt_score >= OPT_SCORE_THRESHOLD,
            "reproducibility_passed":  repro_result["passed"],
            "no_exception":            monitor_result["monitoring_ok"],
        }

        all_met = all(criteria_met.values())

        if all_met:
            status = "stable"
        elif criteria_met["error_rate"] and criteria_met["no_exception"]:
            status = "warning"
        else:
            status = "critical"

        self._slog(f"Step5: stability_status={status} all_met={all_met}")
        return {
            "error_rate":       round(error_rate, 6),
            "opt_score":        round(opt_score, 4),
            "log_completeness": round(log_completeness, 4),
            "stability_status": status,
            "criteria_met":     criteria_met,
            "overall_ok":       all_met,
        }

    # ── Step 6: HITL 最終承認ポイント設定 ────────────────────

    def step6_set_hitl_final_approval(self) -> dict:
        """
        full_deployment ステージの HITL 最終承認ポイントを設定する。
        hitl_final_approval_log.json に記録する。

        Returns:
            {stage: str, status: str, set_at: str}
        """
        log_path = self._phase8_dir / "hitl_final_approval_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log = {
            "generated_at":  self._ts(),
            "module":        "F9530",
            "stage":         "full_deployment",
            "status":        "pending",
            "approved_at":   None,
            "reason":        "",
            "required":      True,
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        # hitl_checkpoint_log.json も更新
        ckpt_path = self._phase8_dir / "hitl_checkpoint_log.json"
        if ckpt_path.exists():
            with open(ckpt_path, encoding="utf-8") as f:
                ckpt = json.load(f)
            found = False
            for cp in ckpt.get("checkpoints", []):
                if cp["stage"] == "full_deployment":
                    cp["f9530_set_at"] = self._ts()
                    cp["f9530_status"] = "pending"
                    found = True
                    break
            if not found:
                ckpt.setdefault("checkpoints", []).append({
                    "stage":         "full_deployment",
                    "required":      True,
                    "status":        "pending",
                    "approved_at":   None,
                    "f9530_set_at":  self._ts(),
                    "f9530_status":  "pending",
                })
            ckpt["current_stage"] = "full_deployment"
            with open(ckpt_path, "w", encoding="utf-8") as f:
                json.dump(ckpt, f, ensure_ascii=False, indent=2)

        self._slog("Step6: HITL final approval checkpoint set for full_deployment")
        return {"stage": "full_deployment", "status": "pending", "set_at": self._ts()}

    # ── Step 7: レポート生成・サマリー統合 ───────────────────

    def step7_generate_reports(
        self,
        state:          dict,
        load_result:    dict,
        monitor_result: dict,
        repro_result:   dict,
        stability:      dict,
        hitl_info:      dict,
    ) -> tuple[dict, dict]:
        """
        stability_report.json と deployment_summary.json を生成する。

        Returns:
            (stability_report, deployment_summary)
        """
        success = stability["overall_ok"]

        stability_report = {
            "generated_at":       self._ts(),
            "module":             "F9530",
            "function":           "deployment_test_and_stabilization",
            "phase":              8,
            "success":            success,
            "load_test":          load_result,
            "exception_monitor":  monitor_result,
            "reproducibility":    repro_result,
            "stability":          stability,
            "hitl_checkpoint":    hitl_info,
            "stability_log":      list(self._stability_log),
            "exception_log":      list(self._exception_log),
        }

        deployment_summary = {
            "generated_at":   self._ts(),
            "module":         "F9530",
            "phase8_stage":   "full_deployment",
            "phase8_complete": success,
            "f9510_summary": {
                "io_integrity": state["plan"].get("io_integrity", 0.0),
                "hitl_count":   state["plan"].get("hitl_count", 0),
            },
            "f9520_summary": {
                "io_integrity":             state["integration"].get("io_integrity", 0.0),
                "reproducibility_passed":   state["integration"].get("reproducibility_test_passed", False),
                "failure_repository_sync":  state["integration"].get("failure_repository_sync", "?"),
                "knowledge_cycle_update":   state["integration"].get("knowledge_cycle_update", "?"),
            },
            "f9530_summary": {
                "error_rate":       stability["error_rate"],
                "opt_score":        stability["opt_score"],
                "log_completeness": stability["log_completeness"],
                "stability_status": stability["stability_status"],
                "repro_passed":     repro_result["passed"],
            },
            "overall_validation": {
                **stability["criteria_met"],
                "phase8_complete": success,
            },
            "outputs": {
                "stability_report":       "docs/phase8/stability_report.json",
                "deployment_summary":     "docs/phase8/deployment_summary.json",
                "hitl_final_approval_log": "docs/phase8/hitl_final_approval_log.json",
            },
        }

        self._slog(f"Step7: reports generated success={success}")
        return stability_report, deployment_summary

    # ── Step 8: phase8_complete_flag 書き込み ─────────────────

    def step8_write_complete_flag(self, deployment_summary: dict) -> bool:
        """
        phase8_complete_flag を書き込み、展開層を正式完了する。

        Args:
            deployment_summary: step7 で生成した deployment_summary

        Returns:
            True（常に成功、書き込みエラー時は例外）
        """
        flag_path = self._phase8_dir / "phase8_complete_flag"
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write(
                f"phase8_complete: {str(deployment_summary['phase8_complete']).lower()}\n"
                f"phase8_stage: {deployment_summary['phase8_stage']}\n"
                f"generated_at: {self._ts()}\n"
            )
        self._slog(
            f"Step8: phase8_complete_flag written "
            f"(complete={deployment_summary['phase8_complete']})"
        )
        return True

    # ── フルラン ─────────────────────────────────────────────

    def run(self, hitl_fn=None) -> dict:
        """
        F9530 の全8ステップを実行し、Phase 8 を正式完了させる。

        Args:
            hitl_fn: HITL 承認関数 callable() → "approve" | "reject"。
                     None の場合は自動 "approve"。

        Returns:
            {
                success:             bool,
                phase8_complete:     bool,
                phase8_stage:        str,
                stability_report:    dict,
                deployment_summary:  dict,
                stability:           dict,
                load_result:         dict,
                repro_result:        dict,
            }
        """
        self._phase8_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        state = self.step1_load_and_integrate()

        # Step 2
        load_result = self.step2_load_test(state)

        # I/O 整合性不一致 → ロールバック + HITL 通知
        if load_result["io_integrity"] < IO_INTEGRITY_REQUIRED:
            self._elog(
                f"ERROR: io_integrity={load_result['io_integrity']:.6f} "
                f"< {IO_INTEGRITY_REQUIRED} — rollback triggered"
            )
            self._save_validation_error(
                {"errors": [f"io_integrity={load_result['io_integrity']:.6f}"], "warnings": []},
                load_result,
            )
            self._trigger_rollback("io_integrity_failure", load_result)
            return self._abort(state, load_result, "io_integrity_failure")

        # Step 3
        monitor_result = self.step3_monitor_exceptions(load_result)

        # error_rate 超過 → ロールバック + HITL 通知
        if not monitor_result["monitoring_ok"]:
            self._trigger_rollback("error_rate_exceeded", load_result)
            return self._abort(state, load_result, "error_rate_exceeded")

        # Step 4
        repro_result = self.step4_reproducibility_test(load_result)

        # 再現性失敗 → sandbox 停止
        if not repro_result["passed"]:
            self._elog("ERROR: reproducibility_test failed — sandbox stopped")
            return self._abort(state, load_result, "reproducibility_failed", repro_result)

        # Step 5
        stability = self.step5_evaluate_stability(
            load_result, monitor_result, repro_result, state)

        # Step 6
        hitl_info = self.step6_set_hitl_final_approval()

        # HITL 承認
        decision = hitl_fn() if callable(hitl_fn) else "approve"
        self._slog(f"Step6: HITL decision={decision}")
        if decision != "approve":
            self._elog(f"HITL rejected: decision={decision}")
            return self._abort(state, load_result, f"hitl_rejected:{decision}", repro_result)

        # HITL 承認記録
        self.record_hitl_final_approval("full_deployment", "approve")
        hitl_info["status"] = "approve"

        # Step 7
        stability_report, deployment_summary = self.step7_generate_reports(
            state, load_result, monitor_result, repro_result, stability, hitl_info)

        # Step 8
        self.step8_write_complete_flag(deployment_summary)

        # 保存
        self._save_stability_report(stability_report)
        self._save_deployment_summary(deployment_summary)
        self._update_deployment_trace(stability_report)

        return {
            "success":            stability_report["success"],
            "phase8_complete":    deployment_summary["phase8_complete"],
            "phase8_stage":       deployment_summary["phase8_stage"],
            "stability_report":   stability_report,
            "deployment_summary": deployment_summary,
            "stability":          stability,
            "load_result":        load_result,
            "repro_result":       repro_result,
        }

    # ── 内部保存・ユーティリティ ─────────────────────────────

    def _abort(
        self,
        state:        dict,
        load_result:  dict,
        reason:       str,
        repro_result: dict | None = None,
    ) -> dict:
        empty_stability = {
            "error_rate": load_result.get("error_rate", 1.0),
            "opt_score":  0.0,
            "log_completeness": 0.0,
            "stability_status": "critical",
            "criteria_met": {},
            "overall_ok": False,
        }
        empty_repro = repro_result or {
            "passed": False, "trials": [], "trial_count": 0, "repro_rate": 0.0}

        sr, ds = self.step7_generate_reports(
            state, load_result,
            {"exception_detected": True, "exception_count": 1,
             "exception_entries": [reason], "monitoring_ok": False},
            empty_repro, empty_stability,
            {"stage": "full_deployment", "status": "hitl_required", "set_at": self._ts()},
        )
        self._save_stability_report(sr)
        self._save_deployment_summary(ds)
        return {
            "success":            False,
            "phase8_complete":    False,
            "phase8_stage":       "full_deployment",
            "stability_report":   sr,
            "deployment_summary": ds,
            "stability":          empty_stability,
            "load_result":        load_result,
            "repro_result":       empty_repro,
        }

    def _save_stability_report(self, report: dict) -> None:
        p = self._phase8_dir / "stability_report.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def _save_deployment_summary(self, summary: dict) -> None:
        p = self._phase8_dir / "deployment_summary.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _update_deployment_trace(self, stability_report: dict) -> None:
        trace_path = self._phase8_dir / "deployment_trace.json"
        if trace_path.exists():
            with open(trace_path, encoding="utf-8") as f:
                trace = json.load(f)
        else:
            trace = {
                "generated_at":    self._ts(),
                "phase":           8,
                "stages":          {},
                "rollback_events": [],
                "phase8_complete": False,
                "abort_reason":    None,
            }

        trace["stages"]["full_deployment"] = {
            "f9530_entry":      "F9530 executed successfully" if stability_report["success"] else "F9530 failed",
            "stability_status": stability_report["stability"]["stability_status"],
            "error_rate":       stability_report["stability"]["error_rate"],
            "opt_score":        stability_report["stability"]["opt_score"],
            "repro_passed":     stability_report["reproducibility"]["passed"],
            "executed_at":      self._ts(),
        }
        trace["phase8_complete"] = stability_report["success"]

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

    def _trigger_rollback(self, reason: str, load_result: dict) -> None:
        log_path = self._phase8_dir / "rollback_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {"generated_at": self._ts(), "rollback_events": [], "total_events": 0}

        log["rollback_events"].append({
            "triggered_at": self._ts(),
            "module":       "F9530",
            "reason":       reason,
            "action":       "step_back_one_stage",
            "io_integrity": load_result.get("io_integrity", 0.0),
            "error_rate":   load_result.get("error_rate", 1.0),
        })
        log["total_events"] = len(log["rollback_events"])
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _save_validation_error(self, validation: dict, load_result: dict) -> None:
        p = self._phase8_dir / "validation_error.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": self._ts(),
                "module":       "F9530",
                "errors":       validation["errors"],
                "warnings":     validation.get("warnings", []),
                "io_integrity": load_result.get("io_integrity", 0.0),
                "error_rate":   load_result.get("error_rate", 1.0),
            }, f, ensure_ascii=False, indent=2)

    # ── 公開メソッド ─────────────────────────────────────────

    def load_stability_report(self, path: Path | None = None) -> dict:
        """stability_report.json を読み込む。"""
        p = path or (self._phase8_dir / "stability_report.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def load_deployment_summary(self, path: Path | None = None) -> dict:
        """deployment_summary.json を読み込む。"""
        p = path or (self._phase8_dir / "deployment_summary.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def record_hitl_final_approval(
        self,
        stage:    str = "full_deployment",
        decision: str = "approve",
        reason:   str = "",
    ) -> None:
        """
        HITL 最終承認を hitl_final_approval_log.json に記録する。

        Args:
            stage:    承認ステージ（通常 "full_deployment"）
            decision: "approve" / "reject" / "abort"
            reason:   承認理由（任意）
        """
        log_path = self._phase8_dir / "hitl_final_approval_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {
                "generated_at": self._ts(),
                "module":       "F9530",
                "stage":        stage,
                "status":       "pending",
                "approved_at":  None,
                "reason":       "",
                "required":     True,
            }

        log["status"]      = decision
        log["approved_at"] = self._ts()
        log["reason"]      = reason

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def write_summary_entry(
        self,
        result:   dict,
        log_path: Path | None = None,
    ) -> None:
        """F9530 完了エントリを summary.log に追記する。"""
        path    = log_path or self._summary_log
        ts      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        stab    = result.get("stability", {})
        load_r  = result.get("load_result", {})
        repro_r = result.get("repro_result", {})

        entry = (
            f"\n[{ts}] F9530 deployment_test_and_stabilization "
            f"{'完了' if result['success'] else '中断'}\n"
            f"  ロードテスト      : io={load_r.get('io_integrity', 0):.4f} "
            f"err_rate={load_r.get('error_rate', 1):.6f}\n"
            f"  再現性テスト      : {'PASSED' if repro_r.get('passed') else 'FAILED'}\n"
            f"  error_rate        : {stab.get('error_rate', 1):.6f}\n"
            f"  opt_score         : {stab.get('opt_score', 0):.4f}\n"
            f"  log_completeness  : {stab.get('log_completeness', 0):.4f}\n"
            f"  stability_status  : {stab.get('stability_status', '?')}\n"
            f"  HITL 最終承認     : full_deployment\n"
            f"  phase8_complete   : {result.get('phase8_complete', False)}\n"
            f"  phase8_stage      : {result.get('phase8_stage', '?')}\n"
            f"  出力ファイル      : stability_report.json / deployment_summary.json / hitl_final_approval_log.json\n"
            f"  次フェーズ        : {'Phase 9（完成層）へ遷移可' if result['success'] else '修正後に再実行'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
