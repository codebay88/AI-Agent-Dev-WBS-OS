"""
F9510 deployment_plan_design — Phase 8 展開計画設計モジュール

学習成果（learning_dataset / learning_patterns / optimization_report）を
他エージェントへ安全に展開するための計画を設計し、
展開仕様 JSON に基づいて段階的展開を初期化する。

処理フロー（8ステップ）:
  Step 1: 展開仕様 JSON の読み込みと5段階構造の解析
  Step 2: 各段階の開始条件・完了条件の内部変数登録
  Step 3: I/O 整合性チェック（100% 必須）
  Step 4: ログ出力設定の初期化（log=normal）
  Step 5: HITL 承認ポイントのマーキング（5箇所）
  Step 6: rollback_policy の読み込みと rollback_log.json 初期化
  Step 7: 展開計画書と展開仕様の整合性検証
  Step 8: deployment_plan.json の生成
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG  = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
CYCLE_DIR    = BASE_DIR / "docs" / "knowledge_cycle"
PHASE8_DIR   = BASE_DIR / "docs" / "phase8"
SPEC_PATH    = PHASE8_DIR / "phase8_spec.json"

PLAN_PATH         = PHASE8_DIR / "deployment_plan.json"
TRACE_PATH        = PHASE8_DIR / "deployment_trace.json"
HITL_LOG_PATH     = PHASE8_DIR / "hitl_checkpoint_log.json"
ROLLBACK_LOG_PATH = PHASE8_DIR / "rollback_log.json"
VALIDATION_ERR    = PHASE8_DIR / "validation_error.json"

REQUIRED_STAGES   = [
    "limited_environment",
    "trial_operation",
    "evaluation",
    "expansion",
    "full_deployment",
]

DEFAULT_ROLLBACK_POLICY = {
    "strategy": "step_back_one_stage",
    "log_file":  "rollback_log.json",
}

_REQUIRED_INPUTS = [
    "learning_dataset.json",
    "learning_patterns.json",
    "optimization_report.json",
]


class F9510DeploymentPlanDesigner:
    """
    F9510 deployment_plan_design の全8ステップを実行する。

    使い方:
        designer = F9510DeploymentPlanDesigner()
        result   = designer.run()
        # result["success"] が True なら次ステージ（F9520）へ
    """

    def __init__(
        self,
        spec_path:        Path | None = None,
        cycle_dir:        Path | None = None,
        phase8_dir:       Path | None = None,
        summary_log:      Path | None = None,
    ) -> None:
        self._spec_path   = spec_path   or SPEC_PATH
        self._cycle_dir   = cycle_dir   or CYCLE_DIR
        self._phase8_dir  = phase8_dir  or PHASE8_DIR
        self._summary_log = summary_log or SUMMARY_LOG

        # 内部状態（Step 2 で登録）
        self._stage_conditions: dict[str, dict] = {}
        self._hitl_points:      list[str]       = []
        self._rollback_policy:  dict            = {}
        self._log_status: str = "uninitialized"

    # ── Step 1: 展開仕様 JSON の読み込み ────────────────────

    def step1_load_spec(self) -> dict:
        """
        phase8_spec.json を読み込み、5段階構造を解析する。

        Returns:
            spec dict。読み込み失敗時は空 dict。
        """
        if not self._spec_path.exists():
            return {}
        with open(self._spec_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("phase8", data)

    # ── Step 2: 開始/完了条件の内部変数登録 ─────────────────

    def step2_register_conditions(self, spec: dict) -> dict[str, dict]:
        """
        各段階の start_conditions / completion_conditions を内部変数として登録する。

        Returns:
            {stage_name: {"start": [...], "completion": [...]}}
        """
        stage_details = spec.get("stage_details", {})
        conditions: dict[str, dict] = {}
        for stage in REQUIRED_STAGES:
            detail = stage_details.get(stage, {})
            conditions[stage] = {
                "start":      detail.get("start_conditions",      []),
                "completion": detail.get("completion_conditions", []),
            }
        self._stage_conditions = conditions
        return conditions

    # ── Step 3: I/O 整合性チェック ──────────────────────────

    def step3_check_io_integrity(self) -> dict:
        """
        Phase 7 成果物（learning_dataset / learning_patterns / optimization_report）の
        存在チェックと、optimization_report の phase7_complete フラグを確認する。

        Returns:
            {
                integrity:      float (0〜100),
                present:        list[str],
                missing:        list[str],
                phase7_complete: bool,
                ok:             bool,
                hitl_required:  bool,
            }
        """
        present: list[str] = []
        missing: list[str] = []

        # ファイル存在チェック
        for fname in _REQUIRED_INPUTS:
            path = self._cycle_dir / fname
            if path.exists():
                present.append(fname)
            else:
                missing.append(fname)

        integrity = (len(present) / len(_REQUIRED_INPUTS)) * 100.0

        # phase7_complete フラグ確認
        phase7_complete = False
        opt_path = self._cycle_dir / "optimization_report.json"
        if opt_path.exists():
            with open(opt_path, encoding="utf-8") as f:
                opt = json.load(f)
            phase7_complete = opt.get("phase7_complete", False)

        ok = integrity == 100.0 and phase7_complete

        return {
            "integrity":       integrity,
            "present":         present,
            "missing":         missing,
            "phase7_complete": phase7_complete,
            "ok":              ok,
            "hitl_required":   not ok,
        }

    # ── Step 4: ログ出力設定の初期化 ────────────────────────

    def step4_initialize_logging(self, io_result: dict) -> str:
        """
        ログ出力設定を初期化する。I/O 整合性 OK なら "normal"、失敗なら "error"。

        Returns:
            "normal" | "error" | "warning"
        """
        if io_result["ok"]:
            self._log_status = "normal"
        elif io_result["integrity"] > 0:
            self._log_status = "warning"
        else:
            self._log_status = "error"
        return self._log_status

    # ── Step 5: HITL 承認ポイントのマーキング ──────────────

    def step5_mark_hitl_points(self, spec: dict) -> list[str]:
        """
        仕様 JSON の hitl_points.required からHITL 承認ポイントを取得する。

        Returns:
            list[str] — 5ステージのリスト（仕様通り）
        """
        hitl = spec.get("hitl_points", {}).get("required", REQUIRED_STAGES)
        self._hitl_points = hitl
        return hitl

    # ── Step 6: rollback_policy 読み込みと初期化 ───────────

    def step6_init_rollback(self, spec: dict) -> dict:
        """
        rollback_policy を読み込み、rollback_log.json を初期化する。
        policy が未定義の場合はデフォルト設定を適用する。

        Returns:
            rollback_policy dict
        """
        policy = spec.get("rollback_policy", {})
        if not policy or "strategy" not in policy:
            policy = DEFAULT_ROLLBACK_POLICY

        self._rollback_policy = policy

        # rollback_log.json 初期化
        log_path = self._phase8_dir / policy.get("log_file", "rollback_log.json")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump({
                    "generated_at":    datetime.now().isoformat(),
                    "rollback_events": [],
                    "total_events":    0,
                }, f, ensure_ascii=False, indent=2)

        return policy

    # ── Step 7: 整合性検証 ──────────────────────────────────

    def step7_validate_consistency(
        self,
        spec:       dict,
        io_result:  dict,
        hitl_points: list[str],
        policy:     dict,
    ) -> dict:
        """
        展開計画と仕様の整合性を検証する。

        検証項目:
          - io_integrity == 100%
          - hitl_points  == 5
          - rollback_policy.strategy == "step_back_one_stage"
          - phase7_complete == true

        Returns:
            {valid: bool, errors: list[str], warnings: list[str]}
        """
        errors:   list[str] = []
        warnings: list[str] = []

        if io_result["integrity"] != 100.0:
            errors.append(f"io_integrity={io_result['integrity']:.0f}% (required: 100%)")

        if len(hitl_points) != 5:
            errors.append(f"hitl_points={len(hitl_points)} (required: 5)")

        if policy.get("strategy") != "step_back_one_stage":
            errors.append(f"rollback_policy.strategy='{policy.get('strategy')}' (required: step_back_one_stage)")

        if not io_result.get("phase7_complete"):
            errors.append("phase7_complete == false")

        # 仕様の5段階が全て存在するか
        spec_stages = spec.get("deployment_stages", [])
        missing_stages = [s for s in REQUIRED_STAGES if s not in spec_stages]
        if missing_stages:
            errors.append(f"missing stages in spec: {missing_stages}")

        # sandbox に関する警告（実際のサンドボックス環境がない場合）
        if io_result.get("integrity") == 100.0 and io_result.get("ok"):
            # サンドボックスはシミュレーション環境として扱う（警告なし）
            pass
        else:
            warnings.append("sandbox_not_utilized — 警告ログを出力します")

        return {
            "valid":    len(errors) == 0,
            "errors":   errors,
            "warnings": warnings,
        }

    # ── Step 8: deployment_plan.json 生成 ──────────────────

    def step8_generate_plan(
        self,
        spec:        dict,
        io_result:   dict,
        conditions:  dict,
        hitl_points: list[str],
        policy:      dict,
        validation:  dict,
    ) -> dict:
        """
        deployment_plan.json の内容を生成する。

        Returns:
            deployment_plan dict
        """
        return {
            "generated_at":    datetime.now().isoformat(),
            "module":          "F9510",
            "function":        "deployment_plan_design",
            "phase":           8,
            "phase8_stage":    "limited_environment",
            "io_integrity":    io_result["integrity"],
            "phase7_complete": io_result["phase7_complete"],
            "log_status":      self._log_status,
            "stage_sequence":  REQUIRED_STAGES,
            "stage_conditions": conditions,
            "hitl_points":     hitl_points,
            "hitl_count":      len(hitl_points),
            "rollback_policy": policy,
            "validation":      validation,
            "inputs": {
                "spec":        str(self._spec_path),
                "present":     io_result["present"],
                "missing":     io_result["missing"],
            },
            "outputs": {
                "deployment_plan":      "docs/phase8/deployment_plan.json",
                "deployment_trace":     "docs/phase8/deployment_trace.json",
                "hitl_checkpoint_log":  "docs/phase8/hitl_checkpoint_log.json",
            },
            "success": validation["valid"],
        }

    # ── フルラン ─────────────────────────────────────────────

    def run(self) -> dict:
        """
        F9510 の全8ステップを実行し、出力ファイルを生成する。

        Returns:
            {
                success:          bool,
                plan:             dict,
                io_result:        dict,
                validation:       dict,
                trace_entry:      str,
                phase8_stage:     str,
            }
        """
        self._phase8_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        spec = self.step1_load_spec()

        # Step 2
        conditions = self.step2_register_conditions(spec)

        # Step 3
        io_result = self.step3_check_io_integrity()

        # Step 4
        log_status = self.step4_initialize_logging(io_result)

        # Step 5
        hitl_points = self.step5_mark_hitl_points(spec)

        # Step 6
        policy = self.step6_init_rollback(spec)

        # Step 7
        validation = self.step7_validate_consistency(spec, io_result, hitl_points, policy)

        # I/O 整合性不一致 → validation_error.json 出力
        if not validation["valid"]:
            self._save_validation_error(validation, io_result)

        # Step 8
        plan = self.step8_generate_plan(
            spec, io_result, conditions, hitl_points, policy, validation)

        # 出力ファイル保存
        self.save_deployment_plan(plan)
        trace_entry = self._update_deployment_trace(plan, validation)
        self._save_hitl_checkpoint_log(hitl_points, plan)

        return {
            "success":      plan["success"],
            "plan":         plan,
            "io_result":    io_result,
            "validation":   validation,
            "trace_entry":  trace_entry,
            "phase8_stage": plan["phase8_stage"],
        }

    # ── 出力ファイル保存 ─────────────────────────────────────

    def save_deployment_plan(
        self,
        plan: dict,
        path: Path | None = None,
    ) -> None:
        """deployment_plan.json を保存する。"""
        p = path or (self._phase8_dir / "deployment_plan.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

    def load_deployment_plan(self, path: Path | None = None) -> dict:
        """deployment_plan.json を読み込む。"""
        p = path or (self._phase8_dir / "deployment_plan.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _update_deployment_trace(self, plan: dict, validation: dict) -> str:
        """
        deployment_trace.json に F9510 の実行記録を追記する。
        ファイルが存在しない場合は新規作成する。
        """
        trace_path = self._phase8_dir / "deployment_trace.json"
        if trace_path.exists():
            with open(trace_path, encoding="utf-8") as f:
                trace = json.load(f)
        else:
            trace = {
                "generated_at":    datetime.now().isoformat(),
                "phase":           8,
                "stages":          {},
                "rollback_events": [],
                "phase8_complete": False,
                "abort_reason":    None,
            }

        entry_text = (
            "F9510 executed successfully"
            if plan["success"]
            else f"F9510 failed: {validation['errors']}"
        )
        trace["stages"]["limited_environment"] = {
            "f9510_entry":   entry_text,
            "io_integrity":  plan["io_integrity"],
            "log_status":    plan["log_status"],
            "phase8_stage":  plan["phase8_stage"],
            "hitl_count":    plan["hitl_count"],
            "executed_at":   datetime.now().isoformat(),
        }

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

        return entry_text

    def _save_hitl_checkpoint_log(
        self,
        hitl_points: list[str],
        plan:        dict,
    ) -> None:
        """hitl_checkpoint_log.json を保存する。"""
        log_path = self._phase8_dir / "hitl_checkpoint_log.json"
        log = {
            "generated_at":    datetime.now().isoformat(),
            "module":          "F9510",
            "total_checkpoints": len(hitl_points),
            "checkpoints": [
                {
                    "stage":     stage,
                    "required":  True,
                    "status":    "pending",
                    "approved_at": None,
                }
                for stage in hitl_points
            ],
            "current_stage":   plan.get("phase8_stage", "limited_environment"),
            "log_status":      plan.get("log_status", "normal"),
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _save_validation_error(
        self,
        validation: dict,
        io_result:  dict,
    ) -> None:
        """整合性検証エラー時に validation_error.json を出力する。"""
        err_path = self._phase8_dir / "validation_error.json"
        err_path.parent.mkdir(parents=True, exist_ok=True)
        with open(err_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "module":       "F9510",
                "errors":       validation["errors"],
                "warnings":     validation["warnings"],
                "io_integrity": io_result["integrity"],
            }, f, ensure_ascii=False, indent=2)

    # ── HITL 承認記録 ─────────────────────────────────────────

    def record_hitl_approval(
        self,
        stage:    str,
        decision: str = "approve",
        reason:   str = "",
    ) -> None:
        """
        限定環境ステージ完了時の HITL 承認を hitl_checkpoint_log.json に記録する。

        Args:
            stage:    承認するステージ名
            decision: "approve" / "reject" / "abort"
            reason:   承認理由（任意）
        """
        log_path = self._phase8_dir / "hitl_checkpoint_log.json"
        if not log_path.exists():
            return
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)

        for cp in log["checkpoints"]:
            if cp["stage"] == stage:
                cp["status"]      = decision
                cp["approved_at"] = datetime.now().isoformat()
                cp["reason"]      = reason
                break

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    # ── summary.log 追記 ─────────────────────────────────────

    def write_summary_entry(
        self,
        result:   dict,
        log_path: Path | None = None,
    ) -> None:
        """F9510 完了エントリを summary.log に追記する。"""
        path       = log_path or self._summary_log
        ts         = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        plan       = result.get("plan", {})
        io_r       = result.get("io_result", {})
        validation = result.get("validation", {})

        entry = (
            f"\n[{ts}] F9510 deployment_plan_design {'完了' if result['success'] else '中断'}\n"
            f"  I/O 整合性      : {io_r.get('integrity', 0):.0f}%\n"
            f"  phase7_complete : {io_r.get('phase7_complete', False)}\n"
            f"  ログ状態        : {plan.get('log_status', '?')}\n"
            f"  HITL ポイント数 : {plan.get('hitl_count', 0)}箇所\n"
            f"  rollback 戦略   : {plan.get('rollback_policy', {}).get('strategy', '?')}\n"
            f"  整合性検証      : {'OK' if validation.get('valid') else 'ERROR — ' + ' / '.join(validation.get('errors', []))}\n"
            f"  phase8 ステージ : {plan.get('phase8_stage', '?')}\n"
            f"  出力ファイル    : deployment_plan.json / deployment_trace.json / hitl_checkpoint_log.json\n"
            f"  次ステージ      : {'F9520（trial_operation）へ遷移可' if result['success'] else '修正後に再実行'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
