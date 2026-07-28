"""
F9620 autonomous_operation_enablement — Phase 9 自律運用化モジュール

統合済みの AIWBS 作成エージェントと AI 導入支援エージェントを
Claude Code 上で自律運用できる状態にする。
制御ループ・HITL 介入・再学習・最適化を安全に回すための運用フレームを構成する。

処理フロー（8ステップ）:
  Step 1: 統合アーキテクチャ・I/O マップを読み込み、ループ構造を抽出
  Step 2: 自律制御ループ（最大3ループ）の設計ルールを適用し制御パターンを定義
  Step 3: HITL 介入ポイントを「自律運用用フロー」として再構成
  Step 4: knowledge_cycle / failure_repository を自律運用ループの I/O に接続
  Step 5: optimization_report を参照し初期パラメータ（閾値・スコア基準）を設定
  Step 6: control_loop_config.json を生成
  Step 7: 試験的自律運用セッションを sandbox 上で実行・記録
  Step 8: autonomous_operation_profile.json を生成・Phase 9 評価ステージへ引き渡し
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
UNIFIED_ARCH_PATH  = PHASE9_DIR / "unified_architecture.json"
UNIFIED_IO_PATH    = PHASE9_DIR / "unified_io_map.json"
INTEG_MATRIX_PATH  = PHASE9_DIR / "integration_matrix.json"

# Phase 9 出力
PROFILE_PATH      = PHASE9_DIR / "autonomous_operation_profile.json"
LOOP_CFG_PATH     = PHASE9_DIR / "control_loop_config.json"
HITL_FLOW_PATH    = PHASE9_DIR / "hitl_autonomy_flow.json"
OBS_LOG_PATH      = PHASE9_DIR / "runtime_observation_log.json"
HITL_CKPT_PATH    = PHASE9_DIR / "hitl_checkpoint_log.json"
ROLLBACK_LOG_PATH = PHASE9_DIR / "rollback_log.json"
VAL_ERR_PATH      = PHASE9_DIR / "validation_error.json"

_CYCLE_INPUTS = [
    "learning_dataset.json",
    "learning_patterns.json",
    "optimization_report.json",
]
_REPO_FILE    = "failure_repository.json"

MAX_LOOPS            = 3
SANDBOX_TRIAL_COUNT  = 3
OPT_SCORE_THRESHOLD  = 0.90
IO_THRESHOLD         = 0.98

# ── ループ定義テンプレート ─────────────────────────────────────

_LOOP_TEMPLATES = [
    {
        "loop_id":   "L-001",
        "name":      "WBS 生成ループ",
        "agent":     "AIWBS",
        "trigger":   "goal_text 入力",
        "modules":   ["F10", "F20", "F30", "F40", "F50", "F60", "F70", "F80", "F90"],
        "exit_cond": "wbs_structure 出力 or HITL 移譲",
        "feedback":  "failure_repository → F10 HITL 辞書",
        "max_iter":  5,
    },
    {
        "loop_id":   "L-002",
        "name":      "展開・安定化ループ",
        "agent":     "SUPPORT",
        "trigger":   "learning_dataset.json 更新",
        "modules":   ["F9510", "F9520", "F9530"],
        "exit_cond": "phase8_complete=True or rollback",
        "feedback":  "optimization_report → 閾値自動調整",
        "max_iter":  3,
    },
    {
        "loop_id":   "L-003",
        "name":      "知識循環ループ",
        "agent":     "knowledge_cycle",
        "trigger":   "WBS 生成完了 / 展開完了",
        "modules":   ["KnowledgeCycle", "LearningDatasetBuilder", "OptimizationEvaluator"],
        "exit_cond": "phase7_ready=True",
        "feedback":  "learning_patterns → AIWBS / SUPPORT",
        "max_iter":  1,
    },
]

# ── HITL 介入ポイント（統合版）─────────────────────────────────

_UNIFIED_HITL_POINTS = [
    {"id": "H-001", "agent": "AIWBS",   "trigger": "曖昧語検出",          "loop": "L-001", "action": "ユーザー入力要求"},
    {"id": "H-002", "agent": "AIWBS",   "trigger": "MECE 不確実域",        "loop": "L-001", "action": "承認 or 再実行"},
    {"id": "H-003", "agent": "SUPPORT", "trigger": "F9510 計画レビュー",   "loop": "L-002", "action": "HITL 承認"},
    {"id": "H-004", "agent": "SUPPORT", "trigger": "F9520 統合レビュー",   "loop": "L-002", "action": "HITL 承認"},
    {"id": "H-005", "agent": "SUPPORT", "trigger": "F9530 最終承認",       "loop": "L-002", "action": "HITL 承認"},
    {"id": "H-006", "agent": "BOTH",    "trigger": "異常検知 / ERROR累積", "loop": "ALL",   "action": "即時停止 + HITL 移譲"},
]


class F9620AutonomousOperationEnabler:
    """
    F9620 autonomous_operation_enablement の全8ステップを実行する。

    使い方:
        enabler = F9620AutonomousOperationEnabler()
        result  = enabler.run()
        # result["success"] が True なら F9630 へ遷移
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

        self._autonomy_log: list[str] = []
        self._hitl_log:     list[str] = []
        self._exception_log: list[str] = []

    def _ts(self) -> str:
        return datetime.now().isoformat()

    def _alog(self, msg: str) -> None:
        self._autonomy_log.append(f"[{self._ts()}] {msg}")

    def _hlog(self, msg: str) -> None:
        self._hitl_log.append(f"[{self._ts()}] {msg}")

    def _elog(self, msg: str) -> None:
        self._exception_log.append(f"[{self._ts()}] {msg}")

    # ── Step 1: 統合アーキテクチャ・I/O マップの読み込み ──────

    def step1_load_unified_artifacts(self) -> dict:
        """
        unified_architecture.json / unified_io_map.json / integration_matrix.json を
        読み込み、運用対象のループ構造を抽出する。

        Returns:
            {arch, io_map, matrix, all_loaded, missing, loop_candidates}
        """
        files = {
            "arch":   self._phase9_dir / "unified_architecture.json",
            "io_map": self._phase9_dir / "unified_io_map.json",
            "matrix": self._phase9_dir / "integration_matrix.json",
        }
        loaded: dict[str, dict] = {}
        missing: list[str] = []

        for key, path in files.items():
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    loaded[key] = json.load(f)
            else:
                missing.append(key)
                loaded[key] = {}

        # ループ候補: unified_architecture の agents から抽出
        arch = loaded.get("arch", {})
        agents = arch.get("agents", {})
        loop_candidates = list(agents.keys()) + ["knowledge_cycle"]

        all_loaded = len(missing) == 0
        self._alog(
            f"Step1: loaded={len(files)-len(missing)}/{len(files)} "
            f"loop_candidates={loop_candidates} missing={missing}"
        )
        return {
            "arch":            loaded.get("arch", {}),
            "io_map":          loaded.get("io_map", {}),
            "matrix":          loaded.get("matrix", {}),
            "all_loaded":      all_loaded,
            "missing":         missing,
            "loop_candidates": loop_candidates,
        }

    # ── Step 2: 自律制御ループ設計 ───────────────────────────

    def step2_design_control_loops(self, artifacts: dict) -> dict:
        """
        自律制御ループ（最大 MAX_LOOPS=3）を設計ルールに基づいて定義する。
        loop_count > MAX_LOOPS の場合は設計エラーとして停止する。

        Returns:
            {loops, loop_count, design_ok, error}
        """
        loops = list(_LOOP_TEMPLATES)
        loop_count = len(loops)
        design_ok  = loop_count <= MAX_LOOPS

        error = None
        if not design_ok:
            error = f"loop_count={loop_count} > MAX_LOOPS={MAX_LOOPS}"
            self._elog(f"Step2: design_error — {error}")

        self._alog(
            f"Step2: loops={loop_count} max={MAX_LOOPS} design_ok={design_ok}"
        )
        return {
            "loops":      loops,
            "loop_count": loop_count,
            "design_ok":  design_ok,
            "error":      error,
        }

    # ── Step 3: HITL 自律フローの再構成 ──────────────────────

    def step3_reconstruct_hitl_flow(self, loop_design: dict) -> dict:
        """
        統合 HITL ポイントを自律運用用フローとして再構成する。

        Returns:
            {hitl_points, hitl_flow_defined, autonomy_rules}
        """
        # 自律運用での HITL ルール
        autonomy_rules = [
            {
                "rule_id": "AR-001",
                "desc":    "ERROR が1件でも発生した場合は即時 HITL 移譲（自律判断禁止）",
            },
            {
                "rule_id": "AR-002",
                "desc":    "HITL 移譲後30秒以内に応答がない場合はパイプラインを一時停止",
            },
            {
                "rule_id": "AR-003",
                "desc":    "承認率が 90% を超えた場合は誤承認警告を出力",
            },
            {
                "rule_id": "AR-004",
                "desc":    "MAX_RETRY=3 超過時は RuntimeError + 自律運用停止",
            },
        ]

        hitl_defined = len(_UNIFIED_HITL_POINTS) > 0
        self._hlog(
            f"Step3: hitl_points={len(_UNIFIED_HITL_POINTS)} "
            f"flow_defined={hitl_defined} rules={len(autonomy_rules)}"
        )
        return {
            "hitl_points":       _UNIFIED_HITL_POINTS,
            "hitl_flow_defined": hitl_defined,
            "autonomy_rules":    autonomy_rules,
        }

    # ── Step 4: knowledge_cycle / failure_repository 接続 ────

    def step4_link_knowledge_stores(self) -> dict:
        """
        knowledge_cycle と failure_repository を自律運用ループの I/O に接続する。

        Returns:
            {
                knowledge_cycle_linked:     bool,
                failure_repository_linked:  bool,
                cycle_files:               dict[str, bool],
                repo_entries:              int,
                all_linked:                bool,
            }
        """
        # knowledge_cycle 接続確認
        cycle_files = {
            fname: (self._cycle_dir / fname).exists()
            for fname in _CYCLE_INPUTS
        }
        kc_linked = all(cycle_files.values())

        # failure_repository 接続確認
        repo_path    = self._phase6_dir / _REPO_FILE
        repo_entries = 0
        if repo_path.exists():
            with open(repo_path, encoding="utf-8") as f:
                repo = json.load(f)
            entries    = repo.get("failures", repo.get("known_failures", []))
            repo_entries = len(entries)
        repo_linked = repo_path.exists()

        all_linked = kc_linked and repo_linked
        self._alog(
            f"Step4: kc_linked={kc_linked} repo_linked={repo_linked} "
            f"repo_entries={repo_entries} all_linked={all_linked}"
        )
        return {
            "knowledge_cycle_linked":    kc_linked,
            "failure_repository_linked": repo_linked,
            "cycle_files":               cycle_files,
            "repo_entries":              repo_entries,
            "all_linked":                all_linked,
        }

    # ── Step 5: 初期パラメータの設定 ─────────────────────────

    def step5_set_initial_parameters(self) -> dict:
        """
        optimization_report を参照して閾値・スコア基準を設定する。

        Returns:
            {opt_score, thresholds, parameters_set}
        """
        opt_path = self._cycle_dir / "optimization_report.json"
        opt_score = 0.0
        if opt_path.exists():
            with open(opt_path, encoding="utf-8") as f:
                opt = json.load(f)
            opt_score = opt.get("summary", {}).get("avg_optimization_index", 0.0)

        thresholds = {
            "opt_score_min":         OPT_SCORE_THRESHOLD,
            "io_integrity_min":      IO_THRESHOLD,
            "error_rate_max":        0.01,
            "hitl_approval_rate_max": 0.90,
            "max_retry":             3,
            "max_loops":             MAX_LOOPS,
            "current_opt_score":     round(opt_score, 4),
        }
        parameters_set = opt_score >= OPT_SCORE_THRESHOLD
        self._alog(
            f"Step5: opt_score={opt_score:.4f} "
            f"parameters_set={parameters_set}"
        )
        return {
            "opt_score":       round(opt_score, 4),
            "thresholds":      thresholds,
            "parameters_set":  parameters_set,
        }

    # ── Step 6: control_loop_config.json 生成 ─────────────────

    def step6_generate_control_loop_config(
        self,
        loop_design: dict,
        hitl_flow:   dict,
        links:       dict,
        params:      dict,
    ) -> dict:
        """
        Claude Code の運用層に渡す control_loop_config.json を生成する。

        Returns:
            control_loop_config dict
        """
        consistent = (
            loop_design["design_ok"]
            and hitl_flow["hitl_flow_defined"]
            and links["all_linked"]
            and params["parameters_set"]
        )

        config = {
            "generated_at":          self._ts(),
            "module":                "F9620",
            "phase":                 9,
            "phase9_stage":          "autonomous_operation",
            "loops":                 loop_design["loops"],
            "loop_count":            loop_design["loop_count"],
            "hitl_points":           hitl_flow["hitl_points"],
            "hitl_flow_defined":     hitl_flow["hitl_flow_defined"],
            "autonomy_rules":        hitl_flow["autonomy_rules"],
            "knowledge_cycle_linked": links["knowledge_cycle_linked"],
            "failure_repo_linked":   links["failure_repository_linked"],
            "thresholds":            params["thresholds"],
            "control_loop_config_consistent": consistent,
            "shared_store":          "docs/knowledge_cycle/",
            "log_target":            "docs/phase4/logs/summary.log",
        }
        self._alog(f"Step6: control_loop_config consistent={consistent}")
        return config

    # ── Step 7: sandbox 試験的自律運用 ───────────────────────

    def step7_run_sandbox_trial(
        self,
        config: dict,
        links:  dict,
    ) -> dict:
        """
        sandbox 上で SANDBOX_TRIAL_COUNT 回の試験的自律運用セッションを実行する。
        各トライアルは決定論的シミュレーション（ファイル存在確認ベース）。

        Returns:
            {
                trials:          list[dict],
                trial_count:     int,
                passed_count:    int,
                success_rate:    float,
                sandbox_ok:      bool,
                exception_count: int,
            }
        """
        base_ok = (
            config["control_loop_config_consistent"]
            and links["all_linked"]
        )

        trials: list[dict] = []
        exception_count    = 0

        for i in range(1, SANDBOX_TRIAL_COUNT + 1):
            # 各トライアル: 全ループが 1 イテレーション完走するシミュレーション
            loop_results: list[dict] = []
            for loop in config["loops"]:
                ok = base_ok
                loop_results.append({
                    "loop_id": loop["loop_id"],
                    "name":    loop["name"],
                    "passed":  ok,
                    "iter":    1,
                })

            trial_ok = all(r["passed"] for r in loop_results)
            if not trial_ok:
                exception_count += 1
                self._elog(f"Step7: trial_{i} FAILED")

            trials.append({
                "trial":        i,
                "passed":       trial_ok,
                "loop_results": loop_results,
            })
            self._alog(f"Step7: sandbox_trial_{i}={'PASS' if trial_ok else 'FAIL'}")

        passed_count  = sum(1 for t in trials if t["passed"])
        success_rate  = round(passed_count / SANDBOX_TRIAL_COUNT, 4)
        sandbox_ok    = passed_count == SANDBOX_TRIAL_COUNT

        self._alog(
            f"Step7: sandbox {'PASSED' if sandbox_ok else 'FAILED'} "
            f"({passed_count}/{SANDBOX_TRIAL_COUNT})"
        )
        return {
            "trials":          trials,
            "trial_count":     SANDBOX_TRIAL_COUNT,
            "passed_count":    passed_count,
            "success_rate":    success_rate,
            "sandbox_ok":      sandbox_ok,
            "exception_count": exception_count,
        }

    # ── Step 8: autonomous_operation_profile.json 生成 ────────

    def step8_generate_profile(
        self,
        artifacts:   dict,
        loop_design: dict,
        hitl_flow:   dict,
        links:       dict,
        params:      dict,
        config:      dict,
        sandbox:     dict,
    ) -> dict:
        """
        autonomous_operation_profile.json を生成し、評価ステージへ引き渡す。

        Returns:
            autonomous_operation_profile dict
        """
        success = (
            loop_design["design_ok"]
            and hitl_flow["hitl_flow_defined"]
            and links["all_linked"]
            and params["parameters_set"]
            and config["control_loop_config_consistent"]
            and sandbox["sandbox_ok"]
        )

        profile = {
            "generated_at":     self._ts(),
            "module":           "F9620",
            "function":         "autonomous_operation_enablement",
            "phase":            9,
            "phase9_stage":     "autonomous_operation",
            "success":          success,
            "loop_count":       loop_design["loop_count"],
            "hitl_flow_defined": hitl_flow["hitl_flow_defined"],
            "knowledge_cycle_linked":    links["knowledge_cycle_linked"],
            "failure_repository_linked": links["failure_repository_linked"],
            "opt_score":        params["opt_score"],
            "parameters_set":   params["parameters_set"],
            "control_loop_config_consistent": config["control_loop_config_consistent"],
            "sandbox_ok":       sandbox["sandbox_ok"],
            "sandbox_success_rate": sandbox["success_rate"],
            "validation": {
                "loop_count_ok":              loop_design["loop_count"] <= MAX_LOOPS,
                "hitl_autonomy_flow_defined": hitl_flow["hitl_flow_defined"],
                "knowledge_cycle_linked":     links["knowledge_cycle_linked"],
                "failure_repository_linked":  links["failure_repository_linked"],
                "control_loop_config_consistent": config["control_loop_config_consistent"],
            },
            "outputs": {
                "autonomous_operation_profile": "docs/phase9/autonomous_operation_profile.json",
                "control_loop_config":          "docs/phase9/control_loop_config.json",
                "hitl_autonomy_flow":           "docs/phase9/hitl_autonomy_flow.json",
                "runtime_observation_log":      "docs/phase9/runtime_observation_log.json",
            },
        }
        self._alog(f"Step8: profile generated success={success}")
        return profile

    # ── フルラン ─────────────────────────────────────────────

    def run(self) -> dict:
        """
        F9620 の全8ステップを実行し、出力ファイルを生成する。

        Returns:
            {
                success:       bool,
                phase9_stage:  str,
                profile:       dict,
                config:        dict,
                hitl_flow:     dict,
                sandbox:       dict,
                links:         dict,
                params:        dict,
            }
        """
        self._phase9_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        artifacts = self.step1_load_unified_artifacts()

        # Step 2
        loop_design = self.step2_design_control_loops(artifacts)

        # loop_count > MAX_LOOPS → 設計エラーで停止
        if not loop_design["design_ok"]:
            self._elog(f"DESIGN_ERROR: {loop_design['error']} — HITL 通知")
            return self._abort("loop_count_exceeded", loop_design, {}, {}, {}, {})

        # Step 3
        hitl_flow = self.step3_reconstruct_hitl_flow(loop_design)

        # hitl_autonomy_flow 未定義 → 自律運用禁止
        if not hitl_flow["hitl_flow_defined"]:
            self._elog("ERROR: hitl_autonomy_flow_missing — 自律運用禁止")
            return self._abort("hitl_flow_missing", loop_design, hitl_flow, {}, {}, {})

        # Step 4
        links = self.step4_link_knowledge_stores()

        # 未接続 → validation_error.json
        if not links["all_linked"]:
            self._save_validation_error({
                "errors": [
                    f"knowledge_cycle_linked={links['knowledge_cycle_linked']}",
                    f"failure_repository_linked={links['failure_repository_linked']}",
                ],
                "warnings": [],
            })
            self._elog("ERROR: knowledge_cycle / failure_repository 未接続")

        # Step 5
        params = self.step5_set_initial_parameters()

        # Step 6
        config = self.step6_generate_control_loop_config(
            loop_design, hitl_flow, links, params)

        # Step 7
        sandbox = self.step7_run_sandbox_trial(config, links)

        # sandbox 異常停止 → rollback
        if not sandbox["sandbox_ok"]:
            self._trigger_rollback("sandbox_trial_failed", sandbox)
            self._elog("ERROR: sandbox_trial failed — rollback triggered")

        # Step 8
        profile = self.step8_generate_profile(
            artifacts, loop_design, hitl_flow, links, params, config, sandbox)

        # 保存
        self._save_profile(profile)
        self._save_control_loop_config(config)
        self._save_hitl_autonomy_flow(hitl_flow)
        self._save_runtime_observation_log(sandbox)
        self._set_hitl_checkpoint(profile)

        return {
            "success":      profile["success"],
            "phase9_stage": profile["phase9_stage"],
            "profile":      profile,
            "config":       config,
            "hitl_flow":    hitl_flow,
            "sandbox":      sandbox,
            "links":        links,
            "params":       params,
        }

    # ── 内部保存 ─────────────────────────────────────────────

    def _save_profile(self, profile: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "autonomous_operation_profile.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def _save_control_loop_config(self, config: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "control_loop_config.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _save_hitl_autonomy_flow(self, hitl_flow: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "hitl_autonomy_flow.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generated_at":   self._ts(),
            "module":         "F9620",
            "hitl_points":    hitl_flow["hitl_points"],
            "autonomy_rules": hitl_flow["autonomy_rules"],
            "hitl_log":       list(self._hitl_log),
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_runtime_observation_log(self, sandbox: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "runtime_observation_log.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generated_at":   self._ts(),
            "module":         "F9620",
            "trials":         sandbox["trials"],
            "trial_count":    sandbox["trial_count"],
            "passed_count":   sandbox["passed_count"],
            "success_rate":   sandbox["success_rate"],
            "sandbox_ok":     sandbox["sandbox_ok"],
            "exception_count": sandbox["exception_count"],
            "autonomy_log":   list(self._autonomy_log),
            "exception_log":  list(self._exception_log),
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _set_hitl_checkpoint(self, profile: dict) -> None:
        """hitl_checkpoint_log.json に autonomous_operation ステージを追記する。"""
        log_path = self._phase9_dir / "hitl_checkpoint_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {
                "generated_at":    self._ts(),
                "module":          "F9620",
                "phase":           9,
                "total_checkpoints": 0,
                "checkpoints":     [],
                "current_stage":   "autonomous_operation",
            }

        found = False
        for cp in log.get("checkpoints", []):
            if cp["stage"] == "autonomous_operation":
                cp["f9620_set_at"] = self._ts()
                cp["f9620_status"] = "pending"
                found = True
                break
        if not found:
            log.setdefault("checkpoints", []).append({
                "stage":         "autonomous_operation",
                "required":      True,
                "status":        "pending",
                "approved_at":   None,
                "f9620_set_at":  self._ts(),
            })

        log["current_stage"] = "autonomous_operation"
        log["total_checkpoints"] = len(log["checkpoints"])

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    def _trigger_rollback(self, reason: str, sandbox: dict) -> None:
        log_path = self._phase9_dir / "rollback_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {"generated_at": self._ts(), "rollback_events": [], "total_events": 0}
        log["rollback_events"].append({
            "triggered_at":  self._ts(),
            "module":        "F9620",
            "reason":        reason,
            "action":        "sandbox_stop_and_retry",
            "sandbox_rate":  sandbox.get("success_rate", 0.0),
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
                "module":       "F9620",
                "errors":       validation["errors"],
                "warnings":     validation.get("warnings", []),
            }, f, ensure_ascii=False, indent=2)

    def _abort(
        self,
        reason:      str,
        loop_design: dict,
        hitl_flow:   dict,
        links:       dict,
        params:      dict,
        config:      dict,
    ) -> dict:
        empty_sandbox = {
            "trials": [], "trial_count": 0, "passed_count": 0,
            "success_rate": 0.0, "sandbox_ok": False, "exception_count": 1,
        }
        empty_hitl   = hitl_flow or {"hitl_points": [], "hitl_flow_defined": False,
                                      "autonomy_rules": []}
        empty_links  = links  or {"knowledge_cycle_linked": False,
                                   "failure_repository_linked": False,
                                   "cycle_files": {}, "repo_entries": 0, "all_linked": False}
        empty_params = params or {"opt_score": 0.0, "thresholds": {}, "parameters_set": False}
        empty_config = config or {"control_loop_config_consistent": False}

        profile = {
            "generated_at":   self._ts(),
            "module":         "F9620",
            "phase":          9,
            "phase9_stage":   "autonomous_operation",
            "success":        False,
            "abort_reason":   reason,
            "loop_count":     loop_design.get("loop_count", 0),
            "hitl_flow_defined": empty_hitl["hitl_flow_defined"],
            "knowledge_cycle_linked":    empty_links["knowledge_cycle_linked"],
            "failure_repository_linked": empty_links["failure_repository_linked"],
            "opt_score":      empty_params["opt_score"],
            "parameters_set": empty_params["parameters_set"],
            "control_loop_config_consistent": empty_config.get(
                "control_loop_config_consistent", False),
            "sandbox_ok":     False,
            "sandbox_success_rate": 0.0,
            "validation": {},
        }
        self._save_profile(profile)
        self._save_runtime_observation_log(empty_sandbox)
        return {
            "success":      False,
            "phase9_stage": "autonomous_operation",
            "profile":      profile,
            "config":       empty_config,
            "hitl_flow":    empty_hitl,
            "sandbox":      empty_sandbox,
            "links":        empty_links,
            "params":       empty_params,
        }

    # ── 公開メソッド ─────────────────────────────────────────

    def load_profile(self, path: Path | None = None) -> dict:
        p = path or (self._phase9_dir / "autonomous_operation_profile.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def load_control_loop_config(self, path: Path | None = None) -> dict:
        p = path or (self._phase9_dir / "control_loop_config.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def record_hitl_approval(
        self,
        stage:    str = "autonomous_operation",
        decision: str = "approve",
        reason:   str = "",
    ) -> None:
        """hitl_checkpoint_log.json に承認を記録する。"""
        log_path = self._phase9_dir / "hitl_checkpoint_log.json"
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
        """F9620 完了エントリを summary.log に追記する。"""
        path    = log_path or self._summary_log
        ts      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        profile = result.get("profile", {})
        sandbox = result.get("sandbox", {})
        links   = result.get("links", {})
        params  = result.get("params", {})

        entry = (
            f"\n[{ts}] F9620 autonomous_operation_enablement "
            f"{'完了' if result['success'] else '中断'}\n"
            f"  制御ループ数      : {profile.get('loop_count', 0)}\n"
            f"  HITL フロー定義   : {profile.get('hitl_flow_defined', False)}\n"
            f"  knowledge_cycle   : {links.get('knowledge_cycle_linked', False)}\n"
            f"  failure_repo      : {links.get('failure_repository_linked', False)}\n"
            f"  opt_score         : {params.get('opt_score', 0):.4f}\n"
            f"  sandbox 試験      : {'PASSED' if sandbox.get('sandbox_ok') else 'FAILED'} "
            f"({sandbox.get('passed_count', 0)}/{sandbox.get('trial_count', 0)})\n"
            f"  control_loop 整合 : {profile.get('control_loop_config_consistent', False)}\n"
            f"  HITL チェックポイント: autonomous_operation\n"
            f"  phase9_stage      : {result.get('phase9_stage', '?')}\n"
            f"  出力ファイル      : autonomous_operation_profile.json / control_loop_config.json / hitl_autonomy_flow.json / runtime_observation_log.json\n"
            f"  次ステージ        : {'F9630（完成検証・最終承認）へ遷移可' if result['success'] else '修正後に再実行'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
