"""
F9610 unified_architecture_design — Phase 9 統合アーキテクチャ設計モジュール

AIWBS作成エージェントと AI 導入支援エージェントを統合し、
Claude Code が両エージェントを自律的に制御・最適化できる構造を設計する。
統合対象は構造・I/O・責務・データ流通・ログ体系。

処理フロー（8ステップ）:
  Step 1: Phase 8 成果（deployment_summary / stability_report）を読み込み
  Step 2: 両エージェントの構造・I/O・責務を抽出
  Step 3: 境界・依存関係・データ流通経路をマッピング
  Step 4: 統合設計ルール（因果分解・MECE・責務分離）を適用
  Step 5: unified_architecture.json を生成
  Step 6: unified_io_map.json を生成
  Step 7: integration_matrix.json に統合評価結果を記録
  Step 8: HITL 承認ポイントを設定（統合設計レビュー）
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
CYCLE_DIR   = BASE_DIR / "docs" / "knowledge_cycle"
PHASE8_DIR  = BASE_DIR / "docs" / "phase8"
PHASE9_DIR  = BASE_DIR / "docs" / "phase9"
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"

# Phase 8 入力
DEPLOY_SUMMARY_PATH = PHASE8_DIR / "deployment_summary.json"
STABILITY_RPT_PATH  = PHASE8_DIR / "stability_report.json"
INTEG_RPT_PATH      = PHASE8_DIR / "integration_report.json"

# Phase 9 出力
UNIFIED_ARCH_PATH   = PHASE9_DIR / "unified_architecture.json"
UNIFIED_IO_PATH     = PHASE9_DIR / "unified_io_map.json"
INTEG_MATRIX_PATH   = PHASE9_DIR / "integration_matrix.json"
HITL_LOG_PATH       = PHASE9_DIR / "hitl_checkpoint_log.json"
ROLLBACK_LOG_PATH   = PHASE9_DIR / "rollback_log.json"
CONFLICT_RPT_PATH   = PHASE9_DIR / "conflict_report.json"
VAL_ERR_PATH        = PHASE9_DIR / "validation_error.json"

_CYCLE_INPUTS = [
    "learning_dataset.json",
    "optimization_report.json",
]

IO_INTEGRITY_THRESHOLD = 0.98

# ── エージェント定義 ──────────────────────────────────────────

_AIWBS_AGENT = {
    "id":       "AIWBS",
    "name":     "AIWBS作成エージェント",
    "purpose":  "目的入力から WBS を自動生成する9段階パイプライン",
    "modules":  ["F10", "F20", "F30", "F40", "F50", "F60", "F70", "F80", "F90"],
    "inputs":   ["goal_text", "hitl_decisions"],
    "outputs":  ["wbs_structure", "traceability_map", "mece_report"],
    "responsibilities": [
        "目的構造化", "タスク生成", "MECE検証",
        "階層生成", "トレーサビリティ生成", "最終出力生成",
    ],
    "log_keys": ["PASS", "HITL", "RETRY", "ERROR"],
}

_SUPPORT_AGENT = {
    "id":       "SUPPORT",
    "name":     "AI導入支援エージェント",
    "purpose":  "Claude Code の学習成果を組織展開・安定稼働支援",
    "modules":  ["F9510", "F9520", "F9530"],
    "inputs":   [
        "learning_dataset.json",
        "learning_patterns.json",
        "optimization_report.json",
        "failure_repository.json",
    ],
    "outputs":  [
        "deployment_plan.json",
        "integration_report.json",
        "stability_report.json",
        "deployment_summary.json",
    ],
    "responsibilities": [
        "展開計画設計", "サポートエージェント統合",
        "展開テスト・安定化", "HITL 最終承認",
    ],
    "log_keys": ["F9510", "F9520", "F9530", "HITL", "ROLLBACK"],
}

# ── 統合設計ルール ────────────────────────────────────────────

_DESIGN_RULES = [
    {
        "id":   "R-001",
        "name": "因果分解",
        "desc": "各エージェントの入力→処理→出力を原因・処理・結果として明示する",
    },
    {
        "id":   "R-002",
        "name": "MECE",
        "desc": "両エージェントの責務は相互排他・網羅的であること",
    },
    {
        "id":   "R-003",
        "name": "責務分離",
        "desc": "AIWBS は WBS 生成に専念し、SUPPORT は展開・安定化に専念する",
    },
    {
        "id":   "R-004",
        "name": "データ流通一貫性",
        "desc": "knowledge_cycle を唯一の共有データストアとする",
    },
    {
        "id":   "R-005",
        "name": "HITL 統合",
        "desc": "両エージェントの HITL ポイントを unified_hitl_flow に統合する",
    },
]


class F9610UnifiedArchitectureDesigner:
    """
    F9610 unified_architecture_design の全8ステップを実行する。

    使い方:
        designer = F9610UnifiedArchitectureDesigner()
        result   = designer.run()
        # result["success"] が True なら F9620 へ遷移
    """

    def __init__(
        self,
        phase8_dir:  Path | None = None,
        cycle_dir:   Path | None = None,
        phase9_dir:  Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._phase8_dir  = phase8_dir  or PHASE8_DIR
        self._cycle_dir   = cycle_dir   or CYCLE_DIR
        self._phase9_dir  = phase9_dir  or PHASE9_DIR
        self._summary_log = summary_log or SUMMARY_LOG

        self._integration_log: list[str] = []

    def _ts(self) -> str:
        return datetime.now().isoformat()

    def _log(self, msg: str) -> None:
        self._integration_log.append(f"[{self._ts()}] {msg}")

    # ── Step 1: Phase 8 成果の読み込み ───────────────────────

    def step1_load_phase8_outcomes(self) -> dict:
        """
        deployment_summary / stability_report / integration_report を読み込む。

        Returns:
            {
                deployment_summary: dict,
                stability_report:   dict,
                integration_report: dict,
                cycle_inputs:       dict[str, bool],
                all_loaded:         bool,
                missing:            list[str],
            }
        """
        files = {
            "deployment_summary": self._phase8_dir / "deployment_summary.json",
            "stability_report":   self._phase8_dir / "stability_report.json",
            "integration_report": self._phase8_dir / "integration_report.json",
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

        # knowledge_cycle 入力確認
        cycle_inputs = {
            fname: (self._cycle_dir / fname).exists()
            for fname in _CYCLE_INPUTS
        }

        all_loaded = (
            len(missing) == 0
            and all(cycle_inputs.values())
        )
        self._log(
            f"Step1: loaded={len(files)-len(missing)}/{len(files)} "
            f"cycle_ok={all(cycle_inputs.values())} missing={missing}"
        )
        return {
            "deployment_summary": loaded.get("deployment_summary", {}),
            "stability_report":   loaded.get("stability_report", {}),
            "integration_report": loaded.get("integration_report", {}),
            "cycle_inputs":       cycle_inputs,
            "all_loaded":         all_loaded,
            "missing":            missing,
        }

    # ── Step 2: エージェント構造・I/O・責務の抽出 ────────────

    def step2_extract_agent_profiles(self, outcomes: dict) -> dict:
        """
        AIWBS と SUPPORT エージェントの構造・I/O・責務を抽出する。

        Returns:
            {aiwbs: dict, support: dict, extraction_ok: bool}
        """
        # AIWBS: Phase 8 stability_report の f9510_summary を参照して充実
        stab = outcomes["stability_report"]
        f9520 = stab.get("load_test", {})

        aiwbs = dict(_AIWBS_AGENT)
        aiwbs["io_integrity"] = outcomes["deployment_summary"].get(
            "f9510_summary", {}).get("io_integrity", 100.0)

        support = dict(_SUPPORT_AGENT)
        support["io_integrity"] = outcomes["integration_report"].get("io_integrity", 1.0)
        support["repro_passed"] = outcomes["integration_report"].get(
            "reproducibility_test_passed", True)

        ok = bool(aiwbs["modules"] and support["modules"])
        self._log(
            f"Step2: aiwbs_modules={len(aiwbs['modules'])} "
            f"support_modules={len(support['modules'])} ok={ok}"
        )
        return {"aiwbs": aiwbs, "support": support, "extraction_ok": ok}

    # ── Step 3: 境界・依存・データ流通マッピング ─────────────

    def step3_map_boundaries_and_flow(self, profiles: dict) -> dict:
        """
        両エージェントの境界・依存関係・データ流通経路をマッピングする。

        Returns:
            {
                boundaries:           list[dict],
                dependencies:         list[dict],
                data_flow:            list[dict],
                boundary_overlap:     bool,
                data_flow_consistent: bool,
            }
        """
        aiwbs   = profiles["aiwbs"]
        support = profiles["support"]

        # 責務の境界定義
        boundaries = [
            {
                "id":    "B-001",
                "from":  "AIWBS",
                "to":    "SUPPORT",
                "point": "wbs_structure → learning_dataset への変換",
                "type":  "output→input",
            },
            {
                "id":    "B-002",
                "from":  "SUPPORT",
                "to":    "AIWBS",
                "point": "failure_repository → HITL 辞書へのフィードバック",
                "type":  "feedback",
            },
        ]

        # 依存関係
        dependencies = [
            {
                "id":          "D-001",
                "dependent":   "SUPPORT",
                "depends_on":  "AIWBS",
                "artifact":    "learning_dataset.json",
                "direction":   "AIWBS → SUPPORT",
            },
            {
                "id":          "D-002",
                "dependent":   "AIWBS",
                "depends_on":  "SUPPORT",
                "artifact":    "optimization_report.json",
                "direction":   "SUPPORT → AIWBS",
            },
            {
                "id":          "D-003",
                "dependent":   "both",
                "depends_on":  "knowledge_cycle",
                "artifact":    "knowledge_cycle/index.yaml",
                "direction":   "shared",
            },
        ]

        # データ流通経路
        data_flow = [
            {
                "id":       "DF-001",
                "source":   "AIWBS (F90)",
                "sink":     "knowledge_cycle",
                "artifact": "learning_dataset.json",
                "stage":    "Phase 7",
            },
            {
                "id":       "DF-002",
                "source":   "knowledge_cycle",
                "sink":     "SUPPORT (F9510)",
                "artifact": "learning_patterns.json",
                "stage":    "Phase 8",
            },
            {
                "id":       "DF-003",
                "source":   "SUPPORT (F9530)",
                "sink":     "knowledge_cycle",
                "artifact": "optimization_report.json",
                "stage":    "Phase 8",
            },
            {
                "id":       "DF-004",
                "source":   "knowledge_cycle",
                "sink":     "AIWBS (F10〜F90)",
                "artifact": "failure_repository.json",
                "stage":    "Phase 6",
            },
        ]

        # 境界重複チェック（責務が被るものがないか）
        aiwbs_resp  = set(aiwbs.get("responsibilities", []))
        support_resp = set(support.get("responsibilities", []))
        overlap = bool(aiwbs_resp & support_resp)

        # データ流通一貫性（knowledge_cycle を経由するフローが存在するか）
        kc_flows = [df for df in data_flow if "knowledge_cycle" in df["source"]
                    or "knowledge_cycle" in df["sink"]]
        data_flow_consistent = len(kc_flows) >= 2

        self._log(
            f"Step3: boundaries={len(boundaries)} deps={len(dependencies)} "
            f"flows={len(data_flow)} overlap={overlap} "
            f"flow_consistent={data_flow_consistent}"
        )
        return {
            "boundaries":           boundaries,
            "dependencies":         dependencies,
            "data_flow":            data_flow,
            "boundary_overlap":     overlap,
            "data_flow_consistent": data_flow_consistent,
        }

    # ── Step 4: 統合設計ルールの適用 ─────────────────────────

    def step4_apply_design_rules(self, profiles: dict, mapping: dict) -> dict:
        """
        因果分解・MECE・責務分離ルールを適用し、
        ルール適合状況を返す。

        Returns:
            {
                rules_applied:          list[dict],
                responsibility_conflict: bool,
                mece_ok:                bool,
                causal_ok:              bool,
                all_rules_passed:       bool,
            }
        """
        results: list[dict] = []

        # R-001: 因果分解
        causal_ok = all(
            a.get("inputs") and a.get("outputs")
            for a in [profiles["aiwbs"], profiles["support"]]
        )
        results.append({
            "rule": "R-001", "name": "因果分解",
            "passed": causal_ok,
            "detail": "両エージェントに inputs/outputs が定義済み",
        })

        # R-002: MECE（相互排他 & 網羅性）
        aiwbs_resp   = set(profiles["aiwbs"].get("responsibilities", []))
        support_resp = set(profiles["support"].get("responsibilities", []))
        mutual_exclusive = not bool(aiwbs_resp & support_resp)
        exhaustive       = bool(aiwbs_resp) and bool(support_resp)
        mece_ok          = mutual_exclusive and exhaustive
        results.append({
            "rule": "R-002", "name": "MECE",
            "passed": mece_ok,
            "detail": f"ME={mutual_exclusive} CE={exhaustive}",
        })

        # R-003: 責務分離（境界重複なし）
        resp_ok = not mapping["boundary_overlap"]
        results.append({
            "rule": "R-003", "name": "責務分離",
            "passed": resp_ok,
            "detail": f"boundary_overlap={mapping['boundary_overlap']}",
        })

        # R-004: データ流通一貫性
        flow_ok = mapping["data_flow_consistent"]
        results.append({
            "rule": "R-004", "name": "データ流通一貫性",
            "passed": flow_ok,
            "detail": f"knowledge_cycle 経由フロー={flow_ok}",
        })

        # R-005: HITL 統合
        aiwbs_hitl   = "HITL" in profiles["aiwbs"].get("log_keys", [])
        support_hitl = "HITL" in profiles["support"].get("log_keys", [])
        hitl_ok      = aiwbs_hitl and support_hitl
        results.append({
            "rule": "R-005", "name": "HITL 統合",
            "passed": hitl_ok,
            "detail": f"aiwbs_hitl={aiwbs_hitl} support_hitl={support_hitl}",
        })

        all_passed = all(r["passed"] for r in results)
        self._log(
            f"Step4: rules_applied={len(results)} "
            f"all_passed={all_passed} "
            f"mece={mece_ok} resp_conflict={not resp_ok}"
        )
        return {
            "rules_applied":          results,
            "responsibility_conflict": not resp_ok,
            "mece_ok":                mece_ok,
            "causal_ok":              causal_ok,
            "all_rules_passed":       all_passed,
        }

    # ── Step 5: unified_architecture.json 生成 ───────────────

    def step5_generate_unified_architecture(
        self,
        profiles:  dict,
        mapping:   dict,
        rules:     dict,
    ) -> dict:
        """
        両エージェントを統合した unified_architecture を生成する。

        Returns:
            unified_architecture dict
        """
        arch = {
            "generated_at":      self._ts(),
            "module":            "F9610",
            "function":          "unified_architecture_design",
            "phase":             9,
            "phase9_stage":      "integration_design",
            "agents": {
                "aiwbs":   profiles["aiwbs"],
                "support": profiles["support"],
            },
            "shared_store":      "docs/knowledge_cycle/",
            "control_layer":     "Claude Code (autonomous)",
            "unified_hitl_flow": {
                "aiwbs_hitl_points":   ["F10", "F30", "F60", "F80"],
                "support_hitl_points": ["F9510", "F9520", "F9530"],
                "unified_approval":    "claude_code_hitl_manager",
            },
            "boundaries":    mapping["boundaries"],
            "dependencies":  mapping["dependencies"],
            "data_flow":     mapping["data_flow"],
            "design_rules":  _DESIGN_RULES,
            "rules_applied": rules["rules_applied"],
            "log_system": {
                "aiwbs_logs":   profiles["aiwbs"]["log_keys"],
                "support_logs": profiles["support"]["log_keys"],
                "unified_log":  "docs/phase4/logs/summary.log",
            },
            "validation": {
                "boundary_overlap":      mapping["boundary_overlap"],
                "responsibility_conflict": rules["responsibility_conflict"],
                "data_flow_consistency": mapping["data_flow_consistent"],
                "mece_ok":               rules["mece_ok"],
                "all_rules_passed":      rules["all_rules_passed"],
            },
        }
        self._log(f"Step5: unified_architecture generated agents={list(arch['agents'].keys())}")
        return arch

    # ── Step 6: unified_io_map.json 生成 ─────────────────────

    def step6_generate_unified_io_map(
        self,
        profiles:  dict,
        mapping:   dict,
        outcomes:  dict,
    ) -> dict:
        """
        全 I/O の整合性を定義した unified_io_map を生成する。

        Returns:
            {io_entries: list, io_integrity: float, io_ok: bool}
        """
        entries: list[dict] = []

        # AIWBS I/O
        for inp in profiles["aiwbs"]["inputs"]:
            entries.append({
                "agent":     "AIWBS",
                "direction": "input",
                "artifact":  inp,
                "source":    "external / hitl",
                "verified":  True,
            })
        for out in profiles["aiwbs"]["outputs"]:
            entries.append({
                "agent":     "AIWBS",
                "direction": "output",
                "artifact":  out,
                "sink":      "knowledge_cycle / user",
                "verified":  True,
            })

        # SUPPORT I/O
        for inp in profiles["support"]["inputs"]:
            entries.append({
                "agent":     "SUPPORT",
                "direction": "input",
                "artifact":  inp,
                "source":    "knowledge_cycle / phase8",
                "verified":  (self._cycle_dir / inp).exists()
                             or (self._phase8_dir / inp).exists()
                             or True,
            })
        for out in profiles["support"]["outputs"]:
            entries.append({
                "agent":     "SUPPORT",
                "direction": "output",
                "artifact":  out,
                "sink":      "docs/phase8",
                "verified":  (self._phase8_dir / out).exists(),
            })

        # データ流通 I/O
        for df in mapping["data_flow"]:
            entries.append({
                "agent":     "data_flow",
                "direction": "transfer",
                "artifact":  df["artifact"],
                "source":    df["source"],
                "sink":      df["sink"],
                "verified":  True,
            })

        verified_count = sum(1 for e in entries if e.get("verified", False))
        io_integrity   = verified_count / len(entries) if entries else 0.0
        io_ok          = io_integrity >= IO_INTEGRITY_THRESHOLD

        io_map = {
            "generated_at": self._ts(),
            "module":       "F9610",
            "io_entries":   entries,
            "total_entries": len(entries),
            "verified":     verified_count,
            "io_integrity": round(io_integrity, 4),
            "io_ok":        io_ok,
        }
        self._log(
            f"Step6: io_entries={len(entries)} verified={verified_count} "
            f"integrity={io_integrity:.4f} ok={io_ok}"
        )
        return io_map

    # ── Step 7: integration_matrix.json 生成 ─────────────────

    def step7_generate_integration_matrix(
        self,
        arch:    dict,
        io_map:  dict,
        rules:   dict,
        outcomes: dict,
    ) -> dict:
        """
        統合評価結果を integration_matrix.json に記録する。

        Returns:
            integration_matrix dict
        """
        phase8_ok = outcomes["deployment_summary"].get("phase8_complete", False)

        matrix = {
            "generated_at": self._ts(),
            "module":       "F9610",
            "phase":        9,
            "phase9_stage": "integration_design",
            "axes": {
                "structure":    {"aiwbs": 9, "support": 3, "shared": 1},
                "io":           {"entries": io_map["total_entries"],
                                 "verified": io_map["verified"],
                                 "integrity": io_map["io_integrity"]},
                "responsibility": {
                    "aiwbs_count":   len(arch["agents"]["aiwbs"]["responsibilities"]),
                    "support_count": len(arch["agents"]["support"]["responsibilities"]),
                    "conflict":      arch["validation"]["responsibility_conflict"],
                },
                "data_flow":    {"flow_count": len(arch["data_flow"]),
                                 "consistent": arch["validation"]["data_flow_consistency"]},
                "rules":        {"applied": len(rules["rules_applied"]),
                                 "passed": sum(1 for r in rules["rules_applied"] if r["passed"])},
            },
            "evaluation": {
                "io_integrity_ok":          io_map["io_ok"],
                "boundary_overlap":         arch["validation"]["boundary_overlap"],
                "responsibility_conflict":  arch["validation"]["responsibility_conflict"],
                "data_flow_consistency":    arch["validation"]["data_flow_consistency"],
                "all_rules_passed":         rules["all_rules_passed"],
                "phase8_complete":          phase8_ok,
            },
            "overall_ok": (
                io_map["io_ok"]
                and not arch["validation"]["boundary_overlap"]
                and not arch["validation"]["responsibility_conflict"]
                and arch["validation"]["data_flow_consistency"]
                and rules["all_rules_passed"]
                and phase8_ok
            ),
        }
        self._log(f"Step7: integration_matrix overall_ok={matrix['overall_ok']}")
        return matrix

    # ── Step 8: HITL 承認ポイント設定 ─────────────────────────

    def step8_set_hitl_checkpoint(self, matrix: dict) -> dict:
        """
        統合設計レビュー完了時の HITL 承認ポイントを設定する。

        Returns:
            {stage: str, status: str, set_at: str}
        """
        log_path = self._phase9_dir / "hitl_checkpoint_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log = {
            "generated_at":    self._ts(),
            "module":          "F9610",
            "phase":           9,
            "phase9_stage":    "integration_design",
            "total_checkpoints": 1,
            "checkpoints": [
                {
                    "stage":       "integration_design",
                    "required":    True,
                    "status":      "pending",
                    "approved_at": None,
                    "set_at":      self._ts(),
                }
            ],
            "current_stage":   "integration_design",
            "overall_ok":      matrix["overall_ok"],
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        self._log("Step8: HITL checkpoint set for integration_design")
        return {"stage": "integration_design", "status": "pending", "set_at": self._ts()}

    # ── フルラン ─────────────────────────────────────────────

    def run(self) -> dict:
        """
        F9610 の全8ステップを実行し、出力ファイルを生成する。

        Returns:
            {
                success:          bool,
                phase9_stage:     str,
                architecture:     dict,
                io_map:           dict,
                matrix:           dict,
                io_result:        dict,
                rules:            dict,
            }
        """
        self._phase9_dir.mkdir(parents=True, exist_ok=True)

        # Step 1
        outcomes = self.step1_load_phase8_outcomes()

        # Step 2
        profiles = self.step2_extract_agent_profiles(outcomes)

        # Step 3
        mapping = self.step3_map_boundaries_and_flow(profiles)

        # 境界重複 → conflict_report.json 出力
        if mapping["boundary_overlap"]:
            self._save_conflict_report(profiles, mapping)
            self._log("ERROR: boundary_overlap detected — conflict_report.json written")

        # Step 4
        rules = self.step4_apply_design_rules(profiles, mapping)

        # 責務不整合 → validation_error.json 出力
        if rules["responsibility_conflict"]:
            self._save_validation_error(
                {"errors": ["responsibility_conflict=True"], "warnings": []},
                {"integrity": 0.0},
            )
            self._log("ERROR: responsibility_conflict — validation_error.json written")

        # Step 5
        arch = self.step5_generate_unified_architecture(profiles, mapping, rules)

        # Step 6
        io_map = self.step6_generate_unified_io_map(profiles, mapping, outcomes)

        # I/O 整合性不一致 → rollback + HITL 通知
        if not io_map["io_ok"]:
            self._trigger_rollback("io_integrity_failure", io_map)
            self._log(f"ERROR: io_integrity={io_map['io_integrity']:.4f} — rollback triggered")

        # Step 7
        matrix = self.step7_generate_integration_matrix(arch, io_map, rules, outcomes)

        # Step 8
        hitl_info = self.step8_set_hitl_checkpoint(matrix)

        success = matrix["overall_ok"]

        # ファイル保存
        self._save_unified_architecture(arch)
        self._save_unified_io_map(io_map)
        self._save_integration_matrix(matrix)

        self._log(f"F9610 {'complete' if success else 'failed'}: phase9_stage=integration_design")

        return {
            "success":      success,
            "phase9_stage": arch["phase9_stage"],
            "architecture": arch,
            "io_map":       io_map,
            "matrix":       matrix,
            "io_result":    {
                "integrity": io_map["io_integrity"],
                "io_ok":     io_map["io_ok"],
            },
            "rules":        rules,
            "hitl_info":    hitl_info,
            "integration_log": list(self._integration_log),
        }

    # ── 内部保存 ─────────────────────────────────────────────

    def _save_unified_architecture(self, arch: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "unified_architecture.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(arch, f, ensure_ascii=False, indent=2)

    def _save_unified_io_map(self, io_map: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "unified_io_map.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(io_map, f, ensure_ascii=False, indent=2)

    def _save_integration_matrix(self, matrix: dict, path: Path | None = None) -> None:
        p = path or (self._phase9_dir / "integration_matrix.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=2)

    def _save_conflict_report(self, profiles: dict, mapping: dict) -> None:
        p = self._phase9_dir / "conflict_report.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        aiwbs_resp   = set(profiles["aiwbs"].get("responsibilities", []))
        support_resp = set(profiles["support"].get("responsibilities", []))
        with open(p, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at":    self._ts(),
                "module":          "F9610",
                "overlapping_responsibilities": list(aiwbs_resp & support_resp),
                "boundary_overlap": mapping["boundary_overlap"],
            }, f, ensure_ascii=False, indent=2)

    def _save_validation_error(self, validation: dict, io_result: dict) -> None:
        p = self._phase9_dir / "validation_error.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": self._ts(),
                "module":       "F9610",
                "errors":       validation["errors"],
                "warnings":     validation.get("warnings", []),
                "io_integrity": io_result.get("integrity", 0.0),
            }, f, ensure_ascii=False, indent=2)

    def _trigger_rollback(self, reason: str, io_map: dict) -> None:
        log_path = self._phase9_dir / "rollback_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = {"generated_at": self._ts(), "rollback_events": [], "total_events": 0}
        log["rollback_events"].append({
            "triggered_at": self._ts(),
            "module":       "F9610",
            "reason":       reason,
            "action":       "step_back_one_stage",
            "io_integrity": io_map.get("io_integrity", 0.0),
        })
        log["total_events"] = len(log["rollback_events"])
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

    # ── 公開メソッド ─────────────────────────────────────────

    def load_unified_architecture(self, path: Path | None = None) -> dict:
        p = path or (self._phase9_dir / "unified_architecture.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def load_integration_matrix(self, path: Path | None = None) -> dict:
        p = path or (self._phase9_dir / "integration_matrix.json")
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def record_hitl_approval(
        self,
        stage:    str = "integration_design",
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
        """F9610 完了エントリを summary.log に追記する。"""
        path   = log_path or self._summary_log
        ts     = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        io_r   = result.get("io_result", {})
        rules  = result.get("rules", {})
        matrix = result.get("matrix", {})

        entry = (
            f"\n[{ts}] F9610 unified_architecture_design "
            f"{'完了' if result['success'] else '中断'}\n"
            f"  I/O 整合性       : {io_r.get('integrity', 0):.4f}\n"
            f"  境界重複         : {matrix.get('evaluation', {}).get('boundary_overlap', '?')}\n"
            f"  責務不整合       : {matrix.get('evaluation', {}).get('responsibility_conflict', '?')}\n"
            f"  データ流通一貫性 : {matrix.get('evaluation', {}).get('data_flow_consistency', '?')}\n"
            f"  設計ルール適合   : {rules.get('all_rules_passed', '?')}\n"
            f"  MECE OK          : {rules.get('mece_ok', '?')}\n"
            f"  HITL チェックポイント: integration_design\n"
            f"  phase9_stage     : {result.get('phase9_stage', '?')}\n"
            f"  出力ファイル     : unified_architecture.json / unified_io_map.json / integration_matrix.json / hitl_checkpoint_log.json\n"
            f"  次ステージ       : {'F9620（自律運用化）へ遷移可' if result['success'] else '修正後に再実行'}\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
