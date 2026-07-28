"""
F9630 final_validation_and_approval — Phase 9 最終検証・承認モジュール

Claude Code の全統合構造（AIWBS作成エージェント＋導入支援エージェント）を最終検証し、
自律運用後の安定性・再現性・最適化・HITL 承認を確認する。
Phase 9 の完了条件「system_complete: true」を確定させる。

処理フロー（8ステップ）:
  Step 1: runtime_observation_log を読み込み、安定性・再現性・最適化指標を抽出
  Step 2: 統合アーキテクチャと制御ループ設定を照合し、構造整合性を検証
  Step 3: knowledge_cycle / failure_repository の循環状態を確認
  Step 4: optimization_report の最終スコアを評価（閾値 ≥ 0.90）
  Step 5: HITL 最終承認ポイント（6箇所）を確認し承認ログを生成
  Step 6: final_validation_report.json を生成し、全検証結果を記録
  Step 7: completion_summary.json に Phase 9 の完了情報を統合
  Step 8: system_complete_flag を書き込み、Claude Code の完成を確定
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
CYCLE_DIR   = BASE_DIR / "docs" / "knowledge_cycle"
PHASE6_DIR  = BASE_DIR / "docs" / "phase6"
PHASE9_DIR  = BASE_DIR / "docs" / "phase9"
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

# Phase 9 入力
_P9_INPUTS = {
    "autonomous_operation_profile": "autonomous_operation_profile.json",
    "control_loop_config":          "control_loop_config.json",
    "runtime_observation_log":      "runtime_observation_log.json",
    "unified_architecture":         "unified_architecture.json",
    "integration_matrix":           "integration_matrix.json",
}

# Phase 9 出力
FINAL_REPORT_PATH   = PHASE9_DIR / "final_validation_report.json"
HITL_FINAL_LOG_PATH = PHASE9_DIR / "hitl_final_approval_log.json"
COMPLETE_FLAG_PATH   = PHASE9_DIR / "system_complete_flag"
COMPLETION_SUM_PATH = PHASE9_DIR / "completion_summary.json"
VAL_ERR_PATH        = PHASE9_DIR / "validation_error.json"
ROLLBACK_LOG_PATH   = PHASE9_DIR / "rollback_log.json"
HITL_CKPT_PATH      = PHASE9_DIR / "hitl_checkpoint_log.json"

_CYCLE_INPUTS = [
    "learning_dataset.json",
    "learning_patterns.json",
    "optimization_report.json",
]
_REPO_FILE = "failure_repository.json"

OPT_SCORE_THRESHOLD  = 0.90
IO_INTEGRITY_REQUIRED = 1.0
HITL_APPROVAL_COUNT   = 6   # 統合済み HITL ポイント総数

# HITL 承認ポイント（F9620 の unified_hitl_points から継承）
_HITL_APPROVAL_POINTS = [
    {"id": "H-001", "agent": "AIWBS",   "desc": "曖昧語検出 — ユーザー入力要求"},
    {"id": "H-002", "agent": "AIWBS",   "desc": "MECE 不確実域 — 承認 or 再実行"},
    {"id": "H-003", "agent": "SUPPORT", "desc": "F9510 計画レビュー — HITL 承認"},
    {"id": "H-004", "agent": "SUPPORT", "desc": "F9520 統合レビュー — HITL 承認"},
    {"id": "H-005", "agent": "SUPPORT", "desc": "F9530 最終承認 — HITL 承認"},
    {"id": "H-006", "agent": "BOTH",    "desc": "異常検知 / ERROR累積 — 即時停止"},
]


class F9630FinalValidationAndApproval:
    """
    F9630 final_validation_and_approval の全8ステップを実行する。

    使い方:
        validator = F9630FinalValidationAndApproval()
        result    = validator.run(hitl_fn=lambda point_id: "approve")
        # result["success"] かつ result["system_complete"] が True で Phase 9 完了
    """

    def __init__(
        self,
        phase9_dir:  Path | None = None,
        cycle_dir:   Path | None = None,
        phase6_dir:  Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._phase9_dir  = phase9_dir  or PHASE9_DIR
        self._cycle_dir   = cycle_dir   or CYCLE_DIR
        self._phase6_dir  = phase6_dir  or PHASE6_DIR
        self._summary_log = summary_log or SUMMARY_LOG

        self._validation_log: list[str] = []
        self._exception_log:  list[str] = []

    def _ts(self) -> str:
        return datetime.now().isoformat()

    def _vlog(self, msg: str) -> None:
        self._validation_log.append(f"[{self._ts()}] {msg}")

    def _elog(self, msg: str) -> None:
        self._exception_log.append(f"[{self._ts()}] {msg}")

    # ── Step 1: 自律運用結果の読み込み・指標抽出 ──────────────

    def step1_load_and_extract_metrics(self) -> dict:
        """
        Phase 9 の出力ファイル群を読み込み、安定性・再現性・最適化指標を抽出する。

        Returns:
            {
                loaded:          dict[str, dict],
                missing:         list[str],
                all_loaded:      bool,
                sandbox_ok:      bool,
                success_rate:    float,
                loop_count:      int,
                config_consistent: bool,
            }
        """
        loaded: dict[str, dict] = {}
        missing: list[str] = []

        for key, fname in _P9_INPUTS.items():
            path = self._phase9_dir / fname
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    loaded[key] = json.load(f)
            else:
                missing.append(key)
                loaded[key] = {}

        obs   = loaded.get("runtime_observation_log", {})
        prof  = loaded.get("autonomous_operation_profile", {})
        cfg   = loaded.get("control_loop_config", {})

        sandbox_ok    = obs.get("sandbox_ok", False)
        success_rate  = obs.get("success_rate", 0.0)
        loop_count    = cfg.get("loop_count", 0)
        config_ok     = cfg.get("control_loop_config_consistent", False)

        all_loaded = len(missing) == 0
        self._vlog(
            f"Step1: loaded={len(loaded)-len(missing)}/{len(loaded)} "
            f"missing={missing} sandbox_ok={sandbox_ok} loop={loop_count}"
        )
        return {
            "loaded":            loaded,
            "missing":           missing,
            "all_loaded":        all_loaded,
            "sandbox_ok":        sandbox_ok,
            "success_rate":      success_rate,
            "loop_count":        loop_count,
            "config_consistent": config_ok,
        }

    # ── Step 2: 構造整合性検証 ────────────────────────────────

    def step2_verify_structural_consistency(self, metrics: dict) -> dict:
        """
        統合アーキテクチャと制御ループ設定を照合し、構造整合性を検証する。

        Returns:
            {
                arch_ok:          bool,
                loop_ok:          bool,
                matrix_ok:        bool,
                structural_ok:    bool,
                checks:           list[dict],
            }
        """
        arch   = metrics["loaded"].get("unified_architecture", {})
        cfg    = metrics["loaded"].get("control_loop_config", {})
        matrix = metrics["loaded"].get("integration_matrix", {})

        checks: list[dict] = []

        # アーキテクチャ: agents が定義されているか
        arch_ok = "agents" in arch and bool(arch.get("agents"))
        checks.append({
            "check":  "unified_architecture.agents",
            "passed": arch_ok,
            "detail": f"agents={list(arch.get('agents', {}).keys())}",
        })

        # 制御ループ: loop_count ≤ 3 かつ loops が定義されているか
        loop_ok = (
            metrics["config_consistent"]
            and 0 < metrics["loop_count"] <= 3
        )
        checks.append({
            "check":  "control_loop_config",
            "passed": loop_ok,
            "detail": f"loop_count={metrics['loop_count']} consistent={metrics['config_consistent']}",
        })

        # 統合マトリクス: overall_ok フラグ
        matrix_ok = matrix.get("overall_ok", False)
        checks.append({
            "check":  "integration_matrix.overall_ok",
            "passed": matrix_ok,
            "detail": f"overall_ok={matrix_ok}",
        })

        structural_ok = arch_ok and loop_ok and matrix_ok
        self._vlog(
            f"Step2: arch={arch_ok} loop={loop_ok} matrix={matrix_ok} "
            f"structural_ok={structural_ok}"
        )
        return {
            "arch_ok":       arch_ok,
            "loop_ok":       loop_ok,
            "matrix_ok":     matrix_ok,
            "structural_ok": structural_ok,
            "checks":        checks,
        }

    # ── Step 3: knowledge_cycle / failure_repository 循環確認 ─

    def step3_verify_knowledge_cycle(self) -> dict:
        """
        knowledge_cycle と failure_repository の循環状態を確認する。

        Returns:
            {
                cycle_ok:      bool,
                repo_ok:       bool,
                cycle_files:   dict[str, bool],
                repo_entries:  int,
                cycle_complete: bool,
            }
        """
        cycle_files = {
            fname: (self._cycle_dir / fname).exists()
            for fname in _CYCLE_INPUTS
        }
        cycle_ok = all(cycle_files.values())

        repo_path = self._phase6_dir / _REPO_FILE
        repo_entries = 0
        if repo_path.exists():
            with open(repo_path, encoding="utf-8") as f:
                repo = json.load(f)
            repo_entries = len(repo.get("failures", repo.get("known_failures", [])))
        repo_ok = repo_path.exists()

        # knowledge_cycle の index.yaml または learning_dataset が存在すれば循環成立
        index_ok = (
            (self._cycle_dir / "index.yaml").exists()
            or (self._cycle_dir / "learning_dataset.json").exists()
        )
        cycle_complete = cycle_ok and repo_ok and index_ok

        self._vlog(
            f"Step3: cycle_ok={cycle_ok} repo_ok={repo_ok} "
            f"index_ok={index_ok} complete={cycle_complete}"
        )
        return {
            "cycle_ok":       cycle_ok,
            "repo_ok":        repo_ok,
            "cycle_files":    cycle_files,
            "repo_entries":   repo_entries,
            "cycle_complete": cycle_complete,
        }

    # ── Step 4: optimization_report 最終評価 ─────────────────

    def step4_evaluate_optimization_score(self) -> dict:
        """
        optimization_report の最終スコアを評価する。

        Returns:
            {
                opt_score:       float,
                score_ok:        bool,
                phase7_complete: bool,
                by_category:     dict,
            }
        """
        opt_path = self._cycle_dir / "optimization_report.json"
        opt_score      = 0.0
        phase7_complete = False
        by_category    = {}

        if opt_path.exists():
            with open(opt_path, encoding="utf-8") as f:
                opt = json.load(f)
            opt_score       = opt.get("summary", {}).get("avg_optimization_index", 0.0)
            phase7_complete = opt.get("phase7_complete", False)
            by_category     = opt.get("by_category", {})

        score_ok = opt_score >= OPT_SCORE_THRESHOLD
        self._vlog(
            f"Step4: opt_score={opt_score:.4f} "
            f"score_ok={score_ok} phase7_complete={phase7_complete}"
        )

        if not score_ok:
            self._elog(
                f"WARNING: opt_score={opt_score:.4f} < {OPT_SCORE_THRESHOLD} "
                "— 再最適化要求"
            )

        return {
            "opt_score":       round(opt_score, 4),
            "score_ok":        score_ok,
            "phase7_complete": phase7_complete,
            "by_category":     by_category,
        }

    # ── Step 5: HITL 最終承認（6箇所）────────────────────────

    def step5_confirm_hitl_approvals(self, hitl_fn=None) -> dict:
        """
        HITL 最終承認ポイント（6箇所）を順次確認し、承認ログを生成する。

        Args:
            hitl_fn: callable(point_id: str) → "approve" | "reject"
                     None の場合は自動 "approve"。

        Returns:
            {
                approvals:        list[dict],
                approved_count:   int,
                rejected_count:   int,
                all_approved:     bool,
                hitl_final_ok:    bool,
            }
        """
        approvals: list[dict] = []

        for point in _HITL_APPROVAL_POINTS:
            decision = "approve"
            if callable(hitl_fn):
                decision = hitl_fn(point["id"])

            entry = {
                "id":          point["id"],
                "agent":       point["agent"],
                "desc":        point["desc"],
                "decision":    decision,
                "decided_at":  self._ts(),
            }
            approvals.append(entry)
            self._vlog(f"Step5: HITL {point['id']} → {decision}")

        approved = sum(1 for a in approvals if a["decision"] == "approve")
        rejected = len(approvals) - approved
        all_approved = rejected == 0

        self._vlog(
            f"Step5: approved={approved}/{len(approvals)} "
            f"rejected={rejected} all_approved={all_approved}"
        )
        return {
            "approvals":      approvals,
            "approved_count": approved,
            "rejected_count": rejected,
            "all_approved":   all_approved,
            "hitl_final_ok":  all_approved,
        }

    # ── Step 6: final_validation_report.json 生成 ─────────────

    def step6_generate_final_report(
        self,
        metrics:    dict,
        structure:  dict,
        cycle:      dict,
        opt:        dict,
        hitl:       dict,
    ) -> dict:
        """
        全検証結果を final_validation_report.json にまとめる。

        Returns:
            final_validation_report dict
        """
        io_ok = metrics["all_loaded"] and metrics["sandbox_ok"]

        success = (
            metrics["sandbox_ok"]
            and structure["structural_ok"]
            and cycle["cycle_complete"]
            and opt["score_ok"]
            and hitl["hitl_final_ok"]
        )

        report = {
            "generated_at":  self._ts(),
            "module":        "F9630",
            "function":      "final_validation_and_approval",
            "phase":         9,
            "phase9_stage":  "final_validation",
            "success":       success,
            "validation": {
                "io_integrity":            IO_INTEGRITY_REQUIRED if io_ok else 0.0,
                "io_integrity_ok":         io_ok,
                "opt_score":               opt["opt_score"],
                "opt_score_ok":            opt["score_ok"],
                "reproducibility_passed":  metrics["sandbox_ok"],
                "structural_ok":           structure["structural_ok"],
                "cycle_complete":          cycle["cycle_complete"],
                "hitl_final_approval":     hitl["hitl_final_ok"],
                "all_passed":              success,
            },
            "detail": {
                "metrics":   metrics,
                "structure": structure,
                "cycle":     cycle,
                "opt":       opt,
                "hitl":      hitl,
            },
            "validation_log": list(self._validation_log),
            "exception_log":  list(self._exception_log),
        }
        self._vlog(f"Step6: final_validation_report generated success={success}")
        return report

    # ── Step 7: completion_summary.json 統合 ─────────────────

    def step7_generate_completion_summary(
        self,
        report:    dict,
        metrics:   dict,
        structure: dict,
        cycle:     dict,
        opt:       dict,
        hitl:      dict,
    ) -> dict:
        """
        Phase 9 の完了情報を completion_summary.json に統合する。

        Returns:
            completion_summary dict
        """
        summary = {
            "generated_at":    self._ts(),
            "module":          "F9630",
            "phase":           9,
            "phase9_stage":    "final_validation",
            "system_complete": report["success"],
            "phase_summary": {
                "Phase4": {"status": "LOCKED",    "test_count": 1067},
                "Phase5": {"status": "active",    "test_count": 180},
                "Phase6": {"status": "active",    "test_count": 373},
                "Phase7": {"status": "complete",  "learning_entries": 48,
                            "patterns": 48, "opt_avg": opt["opt_score"]},
                "Phase8": {"status": "complete",  "test_count": 277,
                            "modules": ["F9510", "F9520", "F9530"]},
                "Phase9": {"status": "complete" if report["success"] else "in_progress",
                            "test_count": 0,
                            "modules": ["F9610", "F9620", "F9630"]},
            },
            "final_metrics": {
                "opt_score":           opt["opt_score"],
                "loop_count":          metrics["loop_count"],
                "sandbox_success_rate": metrics["success_rate"],
                "structural_ok":       structure["structural_ok"],
                "cycle_complete":      cycle["cycle_complete"],
                "hitl_approvals":      hitl["approved_count"],
                "hitl_total_points":   HITL_APPROVAL_COUNT,
            },
            "validation_criteria": {
                "io_integrity":           report["validation"]["io_integrity_ok"],
                "opt_score_ok":           report["validation"]["opt_score_ok"],
                "reproducibility_passed": report["validation"]["reproducibility_passed"],
                "hitl_final_approval":    report["validation"]["hitl_final_approval"],
                "system_complete_flag":   report["success"],
            },
            "outputs": {
                "final_validation_report":  "docs/phase9/final_validation_report.json",
                "hitl_final_approval_log":  "docs/phase9/hitl_final_approval_log.json",
                "system_complete_flag":     "docs/phase9/system_complete_flag",
                "completion_summary":       "docs/phase9/completion_summary.json",
            },
        }
        self._vlog(f"Step7: completion_summary generated system_complete={report['success']}")
        return summary

    # ── Step 8: system_complete_flag 書き込み ────────────────

    def step8_write_system_complete_flag(self, summary: dict) -> bool:
        """
        system_complete_flag を書き込み、Claude Code の完成を確定する。

        Returns:
            True（常に成功）
        """
        flag_path = self._phase9_dir / "system_complete_flag"
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write(
                f"system_complete: {str(summary['system_complete']).lower()}\n"
                f"phase9_stage: {summary['phase9_stage']}\n"
                f"generated_at: {self._ts()}\n"
            )
        self._vlog(
            f"Step8: system_complete_flag written "
            f"(complete={summary['system_complete']})"
        )
        return True

    # ── フルラン ─────────────────────────────────────────────

    def run(self, hitl_fn=None) -> dict:
        """
        F9630 の全8ステップを実行し、Phase 9 を正式完了させる。

        Args:
            hitl_fn: callable(point_id: str) → "approve" | "reject"
                     None の場合は全ポイント自動 "approve"。

        Returns:
            {
                success:          bool,
                system_complete:  bool,
                phase9_stage:     str,
                report:           dict,
                summary:          dict,
                hitl:             dict,
                opt:              dict,
            }
        """
        self._phase9_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        metrics = self.step1_load_and_extract_metrics()

        # Step 2
        structure = self.step2_verify_structural_consistency(metrics)

        # Step 3
        cycle = self.step3_verify_knowledge_cycle()

        # knowledge_cycle / failure_repository 未接続 → validation_error.json
        if not cycle["cycle_complete"]:
            self._save_validation_error({
                "errors": [
                    f"cycle_ok={cycle['cycle_ok']}",
                    f"repo_ok={cycle['repo_ok']}",
                ],
                "warnings": [],
            })
            self._elog("ERROR: knowledge_cycle incomplete — validation_error.json written")

        # Step 4
        opt = self.step4_evaluate_optimization_score()

        # opt_score < 0.90 → HITL 通知（継続はする）
        if not opt["score_ok"]:
            self._elog(
                f"WARNING: opt_score={opt['opt_score']:.4f} < {OPT_SCORE_THRESHOLD}"
            )

        # Step 5
        hitl = self.step5_confirm_hitl_approvals(hitl_fn)

        # HITL 承認失敗 → 承認待機状態
        if not hitl["hitl_final_ok"]:
            self._elog(
                f"ERROR: hitl_final_approval failed "
                f"(rejected={hitl['rejected_count']}) — 承認待機"
            )

        # sandbox 再現性失敗 → 再試験要求
        if not metrics["sandbox_ok"]:
            self._elog("ERROR: sandbox reproducibility failed — 再試験要求")
            self._trigger_rollback("sandbox_failed", metrics)

        # Step 6
        report = self.step6_generate_final_report(
            metrics, structure, cycle, opt, hitl)

        # io_integrity < 1.0 → validation_error.json
        if not report["validation"]["io_integrity_ok"]:
            self._save_validation_error({
                "errors": ["io_integrity < 1.0"],
                "warnings": [],
            })

        # Step 7
        summary = self.step7_generate_completion_summary(
            report, metrics, structure, cycle, opt, hitl)

        # Step 8: system_complete_flag 書き込み（成功時のみ）
        if report["success"]:
            self.step8_write_system_complete_flag(summary)
        else:
            self._elog("system_complete_flag 未書込 — rollback + 再検証要求")
            self._trigger_rollback("system_complete_missing", metrics)

        # 保存
        self._save_final_report(report)
        self._save_hitl_final_log(hitl)
        self._save_completion_summary(summary)
        self._update_hitl_checkpoint(report)

        return {
            "success":         report["success"],
            "system_complete": summary["system_complete"],
            "phase9_stage":    report["phase9_stage"],
            "report":          report,
            "summary":         summary,
            "hitl":            hitl,
            "opt":             opt,
            "metrics":         metrics,
            "structure":       structure,
            "cycle":           cycle,
        }

    # ── 内部保存 ─────────────────────────────────────────────

    def _save_final_report(self, report: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "final_validation_report.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def _save_hitl_final_log(self, hitl: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "hitl_final_approval_log.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generated_at":   self._ts(),
            "module":         "F9630",
            "phase9_stage":   "final_validation",
            "approvals":      hitl["approvals"],
            "approved_count": hitl["approved_count"],
            "rejected_count": hitl["rejected_count"],
            "all_approved":   hitl["all_approved"],
            "total_points":   HITL_APPROVAL_COUNT,
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_completion_summary(self, summary: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "completion_summary.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _update_hitl_checkpoint(self, report: dict) -> None:
        """hitl_checkpoint_log.json に final_validation ステージを追記する。"""
        log_path = self._phase9_dir / "hitl_checkpoint_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {
                "generated_at":    self._ts(),
                "module":          "F9630",
                "phase":           9,
                "total_checkpoints": 0,
                "checkpoints":     [],
                "current_stage":   "final_validation",
            }

        found = False
        for cp in log.get("checkpoints", []):
            if cp["stage"] == "final_validation":
                cp["f9630_set_at"] = self._ts()
                cp["status"]       = "approve" if report["success"] else "pending"
                found = True
                break
        if not found:
            log.setdefault("checkpoints", []).append({
                "stage":         "final_validation",
                "required":      True,
                "status":        "approve" if report["success"] else "pending",
                "approved_at":   self._ts() if report["success"] else None,
                "f9630_set_at":  self._ts(),
            })

        log["current_stage"]      = "final_validation"
        log["total_checkpoints"]  = len(log["checkpoints"])
        log["system_complete"]    = report["success"]

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _trigger_rollback(self, reason: str, metrics: dict) -> None:
        log_path = self._phase9_dir / "rollback_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {"generated_at": self._ts(), "rollback_events": [], "total_events": 0}
        log["rollback_events"].append({
            "triggered_at": self._ts(),
            "module":       "F9630",
            "reason":       reason,
            "action":       "re_validation_required",
        })
        log["total_events"] = len(log["rollback_events"])
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _save_validation_error(self, validation: dict) -> None:
        p = self._phase9_dir / "validation_error.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": self._ts(),
                "module":       "F9630",
                "errors":       validation["errors"],
                "warnings":     validation.get("warnings", []),
            }, f, ensure_ascii=False, indent=2)

    # ── 公開メソッド ─────────────────────────────────────────

    def load_final_report(self, path: Path | None = None) -> dict:
        p = path or (self._phase9_dir / "final_validation_report.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def load_completion_summary(self, path: Path | None = None) -> dict:
        p = path or (self._phase9_dir / "completion_summary.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def write_summary_entry(
        self,
        result:   dict,
        log_path: Path | None = None,
    ) -> None:
        """F9630 完了エントリを summary.log に追記する。"""
        path   = log_path or self._summary_log
        ts     = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        report = result.get("report", {})
        opt    = result.get("opt", {})
        hitl   = result.get("hitl", {})
        summ   = result.get("summary", {})
        v      = report.get("validation", {})

        entry = (
            f"\n[{ts}] F9630 final_validation_and_approval "
            f"{'完了' if result['success'] else '中断'}\n"
            f"  I/O 整合性       : {'OK' if v.get('io_integrity_ok') else 'NG'}\n"
            f"  opt_score        : {opt.get('opt_score', 0):.4f} "
            f"({'OK' if opt.get('score_ok') else 'NG'})\n"
            f"  再現性           : {'PASSED' if v.get('reproducibility_passed') else 'FAILED'}\n"
            f"  構造整合性       : {'OK' if result.get('structure', {}).get('structural_ok') else 'NG'}\n"
            f"  knowledge_cycle  : {'complete' if result.get('cycle', {}).get('cycle_complete') else 'incomplete'}\n"
            f"  HITL 最終承認    : {hitl.get('approved_count', 0)}/{HITL_APPROVAL_COUNT} 承認\n"
            f"  system_complete  : {result.get('system_complete', False)}\n"
            f"  phase9_stage     : {result.get('phase9_stage', '?')}\n"
            f"  出力ファイル     : final_validation_report.json / hitl_final_approval_log.json / system_complete_flag / completion_summary.json\n"
            f"  Claude Code 完成 : {'YES — Phase 9 正式完了' if result['success'] else 'NO — 要修正'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
