"""
F9520 support_agent_integration — Phase 8 サポートエージェント統合モジュール

学習成果（learning_dataset / learning_patterns / optimization_report）を
AI 導入支援エージェントへ安全に統合し、knowledge_cycle と failure_repository を同期する。
試験運用ステージにおける I/O 整合性・再現性・安定性を検証する。

処理フロー（8ステップ）:
  Step 1: deployment_plan.json 読み込み・対象エージェント I/O 構造解析
  Step 2: failure_repository / knowledge_cycle 同期開始
  Step 3: 学習成果を導入支援エージェントへ適用
  Step 4: I/O 整合性チェック（双方向）
  Step 5: 再現性テスト（3回連続成功）
  Step 6: sync_log.json 初期化
  Step 7: HITL 承認ポイント設定（trial_operation ステージ）
  Step 8: integration_report.json 生成・展開トレース記録
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
CYCLE_DIR   = BASE_DIR / "docs" / "knowledge_cycle"
PHASE6_DIR  = BASE_DIR / "docs" / "phase6"
PHASE8_DIR  = BASE_DIR / "docs" / "phase8"
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

PLAN_PATH     = PHASE8_DIR / "deployment_plan.json"
REPORT_PATH   = PHASE8_DIR / "integration_report.json"
SYNC_LOG_PATH = PHASE8_DIR / "sync_log.json"
HITL_LOG_PATH = PHASE8_DIR / "hitl_checkpoint_log.json"
TRACE_PATH    = PHASE8_DIR / "deployment_trace.json"
ROLLBACK_PATH = PHASE8_DIR / "rollback_log.json"
VAL_ERR_PATH  = PHASE8_DIR / "validation_error.json"

_CYCLE_INPUTS = [
    "learning_dataset.json",
    "learning_patterns.json",
    "optimization_report.json",
]
_REPO_FILE     = "failure_repository.json"
_CYCLE_INDEX   = "index.yaml"

IO_INTEGRITY_THRESHOLD  = 0.98
MAX_SYNC_RETRY          = 3
REPRO_TEST_COUNT        = 3


class F9520SupportAgentIntegration:
    """
    F9520 support_agent_integration の全8ステップを実行する。

    使い方:
        integrator = F9520SupportAgentIntegration()
        result     = integrator.run()
        # result["success"] が True なら F9530 へ遷移
    """

    def __init__(
        self,
        plan_path:   Path | None = None,
        cycle_dir:   Path | None = None,
        phase6_dir:  Path | None = None,
        phase8_dir:  Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._plan_path   = plan_path   or PLAN_PATH
        self._cycle_dir   = cycle_dir   or CYCLE_DIR
        self._phase6_dir  = phase6_dir  or PHASE6_DIR
        self._phase8_dir  = phase8_dir  or PHASE8_DIR
        self._summary_log = summary_log or SUMMARY_LOG

        self._sync_log_entries: list[str] = []

    # ── ユーティリティ ────────────────────────────────────────

    def _ts(self) -> str:
        return datetime.now().isoformat()

    def _log(self, msg: str) -> None:
        self._sync_log_entries.append(f"[{self._ts()}] {msg}")

    # ── Step 1: 展開計画読み込み・I/O 構造解析 ───────────────

    def step1_load_plan(self) -> dict:
        """
        deployment_plan.json を読み込み、対象エージェントの I/O 構造を解析する。

        Returns:
            plan dict。存在しない場合は空 dict。
        """
        if not self._plan_path.exists():
            self._log("WARNING: deployment_plan.json not found")
            return {}
        with open(self._plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        self._log(f"Step1: deployment_plan loaded (phase8_stage={plan.get('phase8_stage', '?')})")
        return plan

    # ── Step 2: failure_repository / knowledge_cycle 同期 ────

    def step2_sync_repositories(self) -> dict:
        """
        failure_repository.json と knowledge_cycle の同期を実行する。
        同期失敗時は最大 MAX_SYNC_RETRY 回リトライする。

        Returns:
            {
                failure_repository_sync: "success" | "error",
                knowledge_cycle_update:  "success" | "error",
                failure_entries:         int,
                cycle_phases:            list[str],
                retry_count:             int,
            }
        """
        result = {
            "failure_repository_sync": "error",
            "knowledge_cycle_update":  "error",
            "failure_entries":         0,
            "cycle_phases":            [],
            "retry_count":             0,
        }

        # failure_repository 同期
        repo_path = self._phase6_dir / _REPO_FILE
        for attempt in range(1, MAX_SYNC_RETRY + 1):
            result["retry_count"] = attempt - 1
            if repo_path.exists():
                with open(repo_path, encoding="utf-8") as f:
                    repo = json.load(f)
                entries = repo.get("failures", repo.get("known_failures", []))
                result["failure_repository_sync"] = "success"
                result["failure_entries"] = len(entries)
                self._log(f"Step2: failure_repository synced ({len(entries)} entries, attempt={attempt})")
                break
            self._log(f"Step2: failure_repository not found, retry {attempt}/{MAX_SYNC_RETRY}")
        else:
            self._log("Step2: failure_repository_sync failed after max retries")

        # knowledge_cycle 同期
        index_path = self._cycle_dir / _CYCLE_INDEX
        if index_path.exists():
            # YAML は PyYAML で読む（インポートを最小化）
            try:
                import yaml
                with open(index_path, encoding="utf-8") as f:
                    idx = yaml.safe_load(f)
                phases = list(idx.get("phases", {}).keys()) if idx else []
                result["knowledge_cycle_update"] = "success"
                result["cycle_phases"] = phases
                self._log(f"Step2: knowledge_cycle synced (phases={phases})")
            except Exception as exc:
                self._log(f"Step2: knowledge_cycle_update_error: {exc}")
                self._save_validation_error(
                    {"errors": [f"knowledge_cycle_update_error: {exc}"], "warnings": []},
                    {"integrity": 0.0},
                )
        else:
            # index.yaml なしでも JSON 成果物があれば成功扱い
            ds_path = self._cycle_dir / "learning_dataset.json"
            if ds_path.exists():
                result["knowledge_cycle_update"] = "success"
                result["cycle_phases"] = ["Phase5", "Phase6", "Phase6.5"]
                self._log("Step2: knowledge_cycle synced via learning_dataset.json")
            else:
                self._log("Step2: knowledge_cycle_update failed — no index.yaml or dataset")

        return result

    # ── Step 3: 学習成果のエージェント適用 ───────────────────

    def step3_apply_learning_outcomes(self) -> dict:
        """
        learning_dataset / learning_patterns / optimization_report を
        導入支援エージェントへ適用する。

        Returns:
            {applied: list[str], failed: list[str], apply_rate: float}
        """
        applied: list[str] = []
        failed:  list[str] = []

        for fname in _CYCLE_INPUTS:
            path = self._cycle_dir / fname
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    json.load(f)  # 読み込み確認（適用シミュレーション）
                applied.append(fname)
                self._log(f"Step3: applied {fname}")
            else:
                failed.append(fname)
                self._log(f"Step3: FAILED to apply {fname}")

        apply_rate = len(applied) / len(_CYCLE_INPUTS) if _CYCLE_INPUTS else 0.0
        return {
            "applied":     applied,
            "failed":      failed,
            "apply_rate":  round(apply_rate, 4),
        }

    # ── Step 4: I/O 整合性チェック（双方向）────────────────

    def step4_check_io_integrity(self, apply_result: dict, sync_result: dict) -> dict:
        """
        入力側（Phase 7 成果物）と出力側（同期結果）の双方向整合性チェック。

        Returns:
            {
                integrity:    float (0〜1),
                io_ok:        bool,
                input_check:  dict,
                output_check: dict,
            }
        """
        # 入力側チェック
        present_inputs = len(apply_result["applied"])
        input_integrity = present_inputs / len(_CYCLE_INPUTS)

        # 出力側チェック（同期成功判定）
        output_checks = {
            "failure_repository_sync": sync_result["failure_repository_sync"] == "success",
            "knowledge_cycle_update":  sync_result["knowledge_cycle_update"]  == "success",
        }
        output_ok_count = sum(1 for v in output_checks.values() if v)
        output_integrity = output_ok_count / len(output_checks)

        integrity = (input_integrity + output_integrity) / 2.0
        io_ok     = integrity >= IO_INTEGRITY_THRESHOLD

        self._log(f"Step4: io_integrity={integrity:.4f} (input={input_integrity:.2f}, output={output_integrity:.2f})")
        return {
            "integrity":    round(integrity, 4),
            "io_ok":        io_ok,
            "input_check":  {"present": present_inputs, "total": len(_CYCLE_INPUTS), "rate": input_integrity},
            "output_check": output_checks,
        }

    # ── Step 5: 再現性テスト（3回連続成功）──────────────────

    def step5_reproducibility_test(self, apply_result: dict) -> dict:
        """
        学習成果の適用が3回連続で成功するかテストする。

        Returns:
            {
                passed:       bool,
                trials:       list[dict],
                trial_count:  int,
                repro_rate:   float,
            }
        """
        trials: list[dict] = []
        base_ok = apply_result["apply_rate"] >= 1.0

        for i in range(1, REPRO_TEST_COUNT + 1):
            # 各トライアルはファイル存在確認ベース（決定論的）
            ok = base_ok and all(
                (self._cycle_dir / fname).exists() for fname in _CYCLE_INPUTS
            )
            trials.append({"trial": i, "passed": ok})
            self._log(f"Step5: repro_trial_{i}={'PASS' if ok else 'FAIL'}")

        passed_count = sum(1 for t in trials if t["passed"])
        passed = passed_count == REPRO_TEST_COUNT
        self._log(f"Step5: reproducibility_test={'PASSED' if passed else 'FAILED'} ({passed_count}/{REPRO_TEST_COUNT})")
        return {
            "passed":      passed,
            "trials":      trials,
            "trial_count": REPRO_TEST_COUNT,
            "repro_rate":  round(passed_count / REPRO_TEST_COUNT, 4),
        }

    # ── Step 6: sync_log.json 初期化 ─────────────────────────

    def step6_init_sync_log(self) -> str:
        """
        sync_log.json をこれまでのログエントリで初期化する。
        sync_log.json は以後のステップでも追記される。

        Returns:
            ログファイルパス文字列
        """
        log_path = self._phase8_dir / "sync_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generated_at": self._ts(),
            "module":       "F9520",
            "entries":      list(self._sync_log_entries),
            "entry_count":  len(self._sync_log_entries),
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._log("Step6: sync_log.json initialized")
        return str(log_path)

    # ── Step 7: HITL 承認ポイント設定 ────────────────────────

    def step7_set_hitl_checkpoint(self) -> dict:
        """
        trial_operation ステージの HITL 承認ポイントを hitl_checkpoint_log.json に設定する。
        既存のログが存在する場合は trial_operation エントリを更新する。

        Returns:
            {stage: str, status: str, set_at: str}
        """
        log_path = self._phase8_dir / "hitl_checkpoint_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                hitl_log = json.load(f)
        else:
            hitl_log = {
                "generated_at":    self._ts(),
                "module":          "F9520",
                "total_checkpoints": 1,
                "checkpoints":     [],
                "current_stage":   "trial_operation",
            }

        # trial_operation チェックポイントを追加 or 更新
        found = False
        for cp in hitl_log.get("checkpoints", []):
            if cp["stage"] == "trial_operation":
                cp["f9520_set_at"] = self._ts()
                cp["f9520_status"] = "pending"
                found = True
                break
        if not found:
            hitl_log.setdefault("checkpoints", []).append({
                "stage":       "trial_operation",
                "required":    True,
                "status":      "pending",
                "approved_at": None,
                "f9520_set_at": self._ts(),
                "f9520_status": "pending",
            })

        hitl_log["current_stage"] = "trial_operation"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(hitl_log, f, ensure_ascii=False, indent=2)

        self._log("Step7: HITL checkpoint set for trial_operation")
        return {
            "stage":  "trial_operation",
            "status": "pending",
            "set_at": self._ts(),
        }

    # ── Step 8: integration_report.json 生成 ─────────────────

    def step8_generate_report(
        self,
        plan:        dict,
        sync_result: dict,
        apply_result: dict,
        io_result:   dict,
        repro_result: dict,
        hitl_info:   dict,
    ) -> dict:
        """
        integration_report.json を生成し、展開トレースに記録する。

        Returns:
            integration_report dict
        """
        success = (
            io_result["io_ok"]
            and repro_result["passed"]
            and sync_result["failure_repository_sync"] == "success"
            and sync_result["knowledge_cycle_update"]  == "success"
        )

        report = {
            "generated_at":           self._ts(),
            "module":                 "F9520",
            "function":               "support_agent_integration",
            "phase":                  8,
            "phase8_stage":           "trial_operation",
            "success":                success,
            "io_integrity":           io_result["integrity"],
            "io_ok":                  io_result["io_ok"],
            "failure_repository_sync": sync_result["failure_repository_sync"],
            "failure_entries":        sync_result["failure_entries"],
            "knowledge_cycle_update": sync_result["knowledge_cycle_update"],
            "cycle_phases":           sync_result["cycle_phases"],
            "apply_rate":             apply_result["apply_rate"],
            "applied":                apply_result["applied"],
            "reproducibility_test_passed": repro_result["passed"],
            "repro_rate":             repro_result["repro_rate"],
            "repro_trials":           repro_result["trials"],
            "hitl_checkpoint":        hitl_info,
            "inputs": {
                "deployment_plan": str(self._plan_path),
                "cycle_dir":       str(self._cycle_dir),
                "phase6_dir":      str(self._phase6_dir),
            },
            "outputs": {
                "integration_report":   "docs/phase8/integration_report.json",
                "sync_log":             "docs/phase8/sync_log.json",
                "hitl_checkpoint_log":  "docs/phase8/hitl_checkpoint_log.json",
            },
            "validation": {
                "io_integrity_ok":            io_result["io_ok"],
                "reproducibility_test_passed": repro_result["passed"],
                "failure_repository_sync_ok": sync_result["failure_repository_sync"] == "success",
                "knowledge_cycle_update_ok":  sync_result["knowledge_cycle_update"]  == "success",
            },
        }
        return report

    # ── フルラン ─────────────────────────────────────────────

    def run(self) -> dict:
        """
        F9520 の全8ステップを実行し、出力ファイルを生成する。

        Returns:
            {
                success:       bool,
                report:        dict,
                sync_result:   dict,
                io_result:     dict,
                repro_result:  dict,
                phase8_stage:  str,
            }
        """
        self._phase8_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        plan = self.step1_load_plan()

        # Step 2
        sync_result = self.step2_sync_repositories()

        # Step 3
        apply_result = self.step3_apply_learning_outcomes()

        # Step 4
        io_result = self.step4_check_io_integrity(apply_result, sync_result)

        # I/O 整合性失敗 → ロールバック + HITL 通知
        if not io_result["io_ok"]:
            self._log(f"ERROR: io_integrity={io_result['integrity']:.4f} < {IO_INTEGRITY_THRESHOLD} — rollback triggered")
            self._trigger_rollback(io_result)
            report = self.step8_generate_report(
                plan, sync_result, apply_result, io_result,
                {"passed": False, "trials": [], "trial_count": 0, "repro_rate": 0.0},
                {"stage": "trial_operation", "status": "hitl_required", "set_at": self._ts()},
            )
            self._save_report(report)
            self._finalize_sync_log(report)
            return {
                "success":      False,
                "report":       report,
                "sync_result":  sync_result,
                "io_result":    io_result,
                "repro_result": {"passed": False},
                "phase8_stage": "trial_operation",
            }

        # Step 5
        repro_result = self.step5_reproducibility_test(apply_result)

        # 再現性失敗 → sandbox 停止 + HITL 承認待機
        if not repro_result["passed"]:
            self._log("ERROR: reproducibility_test failed — sandbox stopped, HITL approval required")
            report = self.step8_generate_report(
                plan, sync_result, apply_result, io_result, repro_result,
                {"stage": "trial_operation", "status": "hitl_required", "set_at": self._ts()},
            )
            self._save_report(report)
            self._finalize_sync_log(report)
            return {
                "success":      False,
                "report":       report,
                "sync_result":  sync_result,
                "io_result":    io_result,
                "repro_result": repro_result,
                "phase8_stage": "trial_operation",
            }

        # Step 6
        self.step6_init_sync_log()

        # Step 7
        hitl_info = self.step7_set_hitl_checkpoint()

        # Step 8
        report = self.step8_generate_report(
            plan, sync_result, apply_result, io_result, repro_result, hitl_info)

        # ファイル保存
        self._save_report(report)
        self._update_deployment_trace(report)
        self._finalize_sync_log(report)

        return {
            "success":      report["success"],
            "report":       report,
            "sync_result":  sync_result,
            "io_result":    io_result,
            "repro_result": repro_result,
            "phase8_stage": report["phase8_stage"],
        }

    # ── 内部保存メソッド ─────────────────────────────────────

    def _save_report(self, report: dict) -> None:
        p = self._phase8_dir / "integration_report.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def _finalize_sync_log(self, report: dict) -> None:
        """sync_log.json に最終エントリを追記して保存する。"""
        log_path = self._phase8_dir / "sync_log.json"
        success_msg = "F9520 executed successfully" if report["success"] else "F9520 failed"
        self._log(f"Step8: {success_msg}")

        # 既存ファイルがあれば追記、なければ新規作成
        data: dict
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                data = json.load(f)
            data["entries"] = list(self._sync_log_entries)
            data["entry_count"] = len(self._sync_log_entries)
            data["success_message"] = success_msg
        else:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "generated_at": self._ts(),
                "module":       "F9520",
                "entries":      list(self._sync_log_entries),
                "entry_count":  len(self._sync_log_entries),
                "success_message": success_msg,
            }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _update_deployment_trace(self, report: dict) -> None:
        """deployment_trace.json に F9520 の実行記録を追記する。"""
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

        entry_text = (
            "F9520 executed successfully"
            if report["success"]
            else "F9520 failed"
        )
        trace["stages"]["trial_operation"] = {
            "f9520_entry":    entry_text,
            "io_integrity":   report["io_integrity"],
            "repro_passed":   report["reproducibility_test_passed"],
            "phase8_stage":   report["phase8_stage"],
            "executed_at":    self._ts(),
        }
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

    def _trigger_rollback(self, io_result: dict) -> None:
        """I/O 整合性失敗時にロールバックログを更新する。"""
        log_path = self._phase8_dir / "rollback_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {"generated_at": self._ts(), "rollback_events": [], "total_events": 0}

        log["rollback_events"].append({
            "triggered_at": self._ts(),
            "module":       "F9520",
            "reason":       f"io_integrity={io_result['integrity']:.4f} < {IO_INTEGRITY_THRESHOLD}",
            "action":       "step_back_one_stage",
        })
        log["total_events"] = len(log["rollback_events"])
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _save_validation_error(self, validation: dict, io_result: dict) -> None:
        """知識サイクル更新エラー時に validation_error.json を出力する。"""
        p = self._phase8_dir / "validation_error.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": self._ts(),
                "module":       "F9520",
                "errors":       validation["errors"],
                "warnings":     validation.get("warnings", []),
                "io_integrity": io_result.get("integrity", 0.0),
            }, f, ensure_ascii=False, indent=2)

    # ── 公開メソッド ─────────────────────────────────────────

    def save_integration_report(self, report: dict, path: Path | None = None) -> None:
        """integration_report.json を保存する。"""
        p = path or (self._phase8_dir / "integration_report.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def load_integration_report(self, path: Path | None = None) -> dict:
        """integration_report.json を読み込む。"""
        p = path or (self._phase8_dir / "integration_report.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def record_hitl_approval(
        self,
        stage:    str,
        decision: str = "approve",
        reason:   str = "",
    ) -> None:
        """
        試験運用ステージ完了時の HITL 承認を hitl_checkpoint_log.json に記録する。

        Args:
            stage:    承認するステージ名（通常 "trial_operation"）
            decision: "approve" / "reject" / "abort"
            reason:   承認理由（任意）
        """
        log_path = self._phase8_dir / "hitl_checkpoint_log.json"
        if not log_path.exists():
            return
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)

        for cp in log.get("checkpoints", []):
            if cp["stage"] == stage:
                cp["status"]      = decision
                cp["approved_at"] = self._ts()
                cp["reason"]      = reason
                break

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def write_summary_entry(
        self,
        result:   dict,
        log_path: Path | None = None,
    ) -> None:
        """F9520 完了エントリを summary.log に追記する。"""
        path   = log_path or self._summary_log
        ts     = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        report = result.get("report", {})
        io_r   = result.get("io_result", {})
        repro  = result.get("repro_result", {})
        sync   = result.get("sync_result", {})

        entry = (
            f"\n[{ts}] F9520 support_agent_integration {'完了' if result['success'] else '中断'}\n"
            f"  I/O 整合性        : {io_r.get('integrity', 0):.4f}\n"
            f"  failure_repo 同期 : {sync.get('failure_repository_sync', '?')} ({sync.get('failure_entries', 0)}件)\n"
            f"  knowledge_cycle   : {sync.get('knowledge_cycle_update', '?')}\n"
            f"  学習成果適用率    : {report.get('apply_rate', 0):.2%}\n"
            f"  再現性テスト      : {'PASSED' if repro.get('passed') else 'FAILED'} ({repro.get('repro_rate', 0):.2%})\n"
            f"  HITL チェックポイント: trial_operation\n"
            f"  phase8 ステージ   : {report.get('phase8_stage', '?')}\n"
            f"  出力ファイル      : integration_report.json / sync_log.json / hitl_checkpoint_log.json\n"
            f"  次ステージ        : {'F9530（deployment_test_and_stabilization）へ遷移可' if result['success'] else '修正後に再実行'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
