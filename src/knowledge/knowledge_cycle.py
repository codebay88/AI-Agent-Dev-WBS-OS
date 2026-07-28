"""
KnowledgeCycle — Phase 5〜6.5 知識循環フェーズ統合管理

WBS構造・各フェーズ成果物の読み込み・依存関係定義・
インデックス保存・再利用エクスポートを担う。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG   = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
WBS_PATH      = BASE_DIR / "docs" / "wbs_structure.yaml"
CYCLE_DIR     = BASE_DIR / "docs" / "knowledge_cycle"
CYCLE_INDEX   = CYCLE_DIR / "index.yaml"

# フェーズ別の主要成果物マップ（ファイルパス相対）
_PHASE_ARTIFACTS: dict[str, list[str]] = {
    "Phase5": [
        "src/monitoring/monitor.py",
        "src/monitoring/hitl_tracker.py",
        "src/monitoring/hitl_approval.py",
        "src/monitoring/daily_operation.py",
        "src/monitoring/log_review.py",
        "docs/phase5/config/monitoring.yaml",
    ],
    "Phase6": [
        "src/improvement/feedback_collector.py",
        "src/improvement/template_optimizer.py",
        "src/knowledge/failure_repository.py",
        "src/config/thresholds.yaml",
        "src/templates/template_index.yaml",
        "docs/phase6/feedback_report.json",
        "docs/phase6/failure_repository.json",
    ],
    "Phase6.5": [
        "src/management/wbs_tracker.py",
        "src/system/os_update_checker.py",
        "docs/wbs_structure.yaml",
        "docs/wbs_history.log",
        "docs/system/os_update_report.json",
    ],
}

# フェーズ間依存関係（依存する親フェーズのリスト）
_DEPENDENCIES: dict[str, list[str]] = {
    "Phase1-3": [],
    "Phase4":   ["Phase1-3"],
    "Phase5":   ["Phase4"],
    "Phase6":   ["Phase5"],
    "Phase6.5": ["Phase5", "Phase6"],
    "Phase7":   ["Phase6", "Phase6.5"],
    "Phase8":   ["Phase7"],
}


class KnowledgeCycle:
    """
    Phase 5〜6.5 の成果物を統合管理し、知識循環を永続化する。

    使い方:
        kc      = KnowledgeCycle()
        summary = kc.export_phase_summary()
        issues  = kc.validate_artifacts()
        kc.save_cycle_index(summary)
        kc.write_summary_entry(summary)
    """

    def __init__(
        self,
        base_dir:    Path | None = None,
        wbs_path:    Path | None = None,
        cycle_dir:   Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._base_dir    = base_dir    or BASE_DIR
        self._wbs_path    = wbs_path    or WBS_PATH
        self._cycle_dir   = cycle_dir   or CYCLE_DIR
        self._summary_log = summary_log or SUMMARY_LOG

    # ── WBS 読み込み ─────────────────────────────────────────

    def load_wbs(self) -> dict:
        """wbs_structure.yaml を読み込んで返す。"""
        if not self._wbs_path.exists():
            return {"phases": []}
        with open(self._wbs_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    # ── フェーズデータ読み込み ────────────────────────────────

    def load_phase_data(self, phase_id: str) -> dict:
        """
        指定フェーズの成果物メタデータを返す。

        Returns:
            phase_id   : フェーズ ID
            artifacts  : 成果物パスリスト（相対パス）
            present    : 実際に存在するファイルリスト
            missing    : 存在しないファイルリスト
            status     : "ok" | "partial" | "missing"
            wbs_phase  : WBS から取得したフェーズ dict（なければ None）
        """
        artifacts = _PHASE_ARTIFACTS.get(phase_id, [])
        present   = [a for a in artifacts if (self._base_dir / a).exists()]
        missing   = [a for a in artifacts if a not in present]

        if not artifacts:
            status = "missing"
        elif len(present) == len(artifacts):
            status = "ok"
        elif present:
            status = "partial"
        else:
            status = "missing"

        wbs      = self.load_wbs()
        wbs_phase = next(
            (p for p in wbs.get("phases", []) if p["id"] == phase_id), None
        )

        return {
            "phase_id":  phase_id,
            "artifacts": artifacts,
            "present":   present,
            "missing":   missing,
            "status":    status,
            "wbs_phase": wbs_phase,
        }

    # ── 成果物検証 ────────────────────────────────────────────

    def validate_artifacts(self, phase_id: str | None = None) -> list[str]:
        """
        成果物の存在を確認し、不足ファイルのリストを返す。

        phase_id が None の場合は全フェーズを検証する。
        """
        phases  = [phase_id] if phase_id else list(_PHASE_ARTIFACTS.keys())
        missing: list[str] = []
        for pid in phases:
            data = self.load_phase_data(pid)
            for m in data["missing"]:
                missing.append(f"[{pid}] {m}")
        return missing

    # ── 依存グラフ ────────────────────────────────────────────

    def build_dependency_graph(self) -> dict:
        """
        フェーズ間依存グラフを返す。

        Returns:
            {phase_id: {"depends_on": list[str], "required_by": list[str]}}
        """
        graph: dict[str, dict] = {}
        for phase_id, deps in _DEPENDENCIES.items():
            graph[phase_id] = {
                "depends_on":  deps,
                "required_by": [
                    pid for pid, d in _DEPENDENCIES.items() if phase_id in d
                ],
            }
        return graph

    def get_phase_dependencies(self, phase_id: str) -> list[str]:
        """指定フェーズが依存するフェーズ一覧を返す。"""
        return _DEPENDENCIES.get(phase_id, [])

    # ── フェーズサマリー出力 ──────────────────────────────────

    def export_phase_summary(self) -> dict:
        """
        全フェーズの成果物状態・依存関係を集約したサマリーを返す。

        Returns:
            exported_at     : ISO8601
            total_phases    : 管理フェーズ数
            phases          : フェーズ別状態 dict
            dependency_graph: 依存グラフ
            all_ok          : 全成果物が揃っているか
            missing_files   : 不足ファイルリスト
            phase7_ready    : True（常に）
        """
        phases_summary = {}
        for pid in _PHASE_ARTIFACTS:
            data = self.load_phase_data(pid)
            phases_summary[pid] = {
                "status":        data["status"],
                "total":         len(data["artifacts"]),
                "present_count": len(data["present"]),
                "missing_count": len(data["missing"]),
                "missing":       data["missing"],
            }

        missing_all = self.validate_artifacts()

        return {
            "exported_at":      datetime.now().isoformat(),
            "total_phases":     len(_PHASE_ARTIFACTS),
            "phases":           phases_summary,
            "dependency_graph": self.build_dependency_graph(),
            "all_ok":           len(missing_all) == 0,
            "missing_files":    missing_all,
            "phase7_ready":     True,
        }

    # ── インデックス保存 ──────────────────────────────────────

    def save_cycle_index(
        self,
        summary:  dict,
        path:     Path | None = None,
    ) -> None:
        """knowledge_cycle/index.yaml に統合インデックスを保存する。"""
        p = path or (self._cycle_dir / "index.yaml")
        p.parent.mkdir(parents=True, exist_ok=True)
        index = {
            "generated_at": summary.get("exported_at", ""),
            "total_phases": summary.get("total_phases", 0),
            "all_ok":       summary.get("all_ok", False),
            "phases":       {
                pid: {
                    "status":  info["status"],
                    "present": info["present_count"],
                    "total":   info["total"],
                }
                for pid, info in summary.get("phases", {}).items()
            },
            "dependency_graph": summary.get("dependency_graph", {}),
            "phase7_ready": True,
        }
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(index, f, allow_unicode=True, sort_keys=False)

    # ── summary.log 追記 ─────────────────────────────────────

    def write_summary_entry(
        self,
        summary:  dict,
        log_path: Path | None = None,
    ) -> None:
        """知識循環保存完了エントリを summary.log に追記する。"""
        path = log_path or self._summary_log
        ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        missing_str = "なし" if not summary.get("missing_files") else (
            "\n" + "\n".join(f"    - {f}" for f in summary["missing_files"])
        )
        phase_lines = "\n".join(
            f"    {pid}: {info['status']} ({info['present_count']}/{info['total']}件)"
            for pid, info in summary.get("phases", {}).items()
        )

        entry = (
            f"\n[{ts}] 運用・改善（知識循環）フェーズ統合保存完了\n"
            f"  管理フェーズ数  : {summary.get('total_phases', 0)}\n"
            f"  全成果物確認    : {'OK' if summary.get('all_ok') else '要確認'}\n"
            f"  フェーズ別状態  :\n{phase_lines}\n"
            f"  不足ファイル    : {missing_str}\n"
            f"  Phase 7 フラグ  : READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── プロパティ ────────────────────────────────────────────

    # ── Phase 7 学習データ連携 ───────────────────────────────────

    def load_learning_dataset(
        self,
        path: Path | None = None,
    ) -> dict:
        """
        WP9410 が生成した learning_dataset.json を読み込む。

        Returns:
            dict — learning_dataset.json の内容。ファイルが存在しない場合は空 dict。
        """
        p = path or (self._cycle_dir / "learning_dataset.json")
        if not p.exists():
            return {}
        import json
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def get_optimization_report(
        self,
        path: Path | None = None,
    ) -> dict:
        """
        WP9430 が生成した optimization_report.json を読み込む。

        Args:
            path: optimization_report.json のパス（省略時はデフォルト）

        Returns:
            dict — optimization_report.json の内容。ファイルが存在しない場合は空 dict。
        """
        p = path or (self._cycle_dir / "optimization_report.json")
        if not p.exists():
            return {}
        import json
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def get_learning_patterns(
        self,
        category: str | None = None,
        path:     Path | None = None,
    ) -> list[dict]:
        """
        WP9420 が生成した learning_patterns.json からパターンを返す。

        Args:
            category: "operational" / "improvement" / "maintenance" / "environment" / None（全件）
            path:     learning_patterns.json のパス（省略時はデフォルト）

        Returns:
            list[dict] — 学習パターンのリスト。
        """
        p = path or (self._cycle_dir / "learning_patterns.json")
        if not p.exists():
            return []
        import json
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if category:
            return data.get("by_category", {}).get(category, [])
        return data.get("patterns", [])

    def get_learning_targets(
        self,
        category: str | None = None,
        path:     Path | None = None,
    ) -> list[dict]:
        """
        学習対象エントリを返す。

        Args:
            category: "operational" / "improvement" / "maintenance" / "environment" / None（全件）
            path:     learning_dataset.json のパス（省略時はデフォルト）

        Returns:
            list[dict] — 学習エントリのリスト。
        """
        ds = self.load_learning_dataset(path)
        if not ds:
            return []
        if category:
            return ds.get("categories", {}).get(category, [])
        return ds.get("learning_entries", [])

    # ── プロパティ ────────────────────────────────────────────

    @property
    def managed_phases(self) -> list[str]:
        return list(_PHASE_ARTIFACTS.keys())

    @property
    def cycle_dir(self) -> Path:
        return self._cycle_dir
