"""
WBSTracker — Phase 6.5 WP9300/9310 WBS構造更新・差分管理

docs/wbs_structure.yaml の読み込み・更新・差分記録を行い、
WBS更新履歴を docs/wbs_history.log に追記する。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG  = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
WBS_PATH     = BASE_DIR / "docs" / "wbs_structure.yaml"
HISTORY_LOG  = BASE_DIR / "docs" / "wbs_history.log"

# 差分件数がこれ以上、または削除がある場合に HITL 承認を要求する
HITL_THRESHOLD = 3


class WBSTracker:
    """
    WBS構造の読み込み・更新・差分検出・履歴記録を担う。

    使い方:
        tracker = WBSTracker()
        before  = tracker.load_structure()
        after   = tracker.apply_phase_update(before, new_phases)
        diff    = tracker.detect_diff(before, after)
        tracker.save_structure(after)
        tracker.record_history(diff)
        tracker.write_summary_entry(diff)
    """

    def __init__(
        self,
        wbs_path:    Path | None = None,
        history_log: Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._wbs_path    = wbs_path    or WBS_PATH
        self._history_log = history_log or HISTORY_LOG
        self._summary_log = summary_log or SUMMARY_LOG

    # ── 読み書き ──────────────────────────────────────────────

    def load_structure(self, path: Path | None = None) -> dict:
        """wbs_structure.yaml を読み込んで返す。存在しない場合は空 dict。"""
        p = path or self._wbs_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_structure(self, data: dict, path: Path | None = None) -> None:
        """wbs_structure.yaml に書き込む。"""
        p = path or self._wbs_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    # ── フェーズ更新 ──────────────────────────────────────────

    def apply_phase_update(
        self,
        structure:  dict,
        new_phases: list[dict],
    ) -> dict:
        """
        structure の phases リストに new_phases を追加/更新して返す。

        既存の id と一致するフェーズがある場合は更新、
        一致しない場合は末尾に追加する。
        """
        updated = dict(structure)
        phases  = list(updated.get("phases", []))
        phase_map = {p["id"]: i for i, p in enumerate(phases)}

        for new_phase in new_phases:
            pid = new_phase.get("id")
            if pid in phase_map:
                phases[phase_map[pid]] = new_phase
            else:
                phases.append(new_phase)
                phase_map[pid] = len(phases) - 1

        updated["phases"]       = phases
        updated["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        return updated

    # ── 差分検出 ──────────────────────────────────────────────

    def detect_diff(self, before: dict, after: dict) -> dict:
        """
        フェーズリストの差分（追加・削除・変更）を検出する。

        Returns:
            added   : after にのみ存在するフェーズ id リスト
            removed : before にのみ存在するフェーズ id リスト
            changed : 内容が変わったフェーズ id リスト
            total   : 変更総件数
        """
        def _phase_map(structure: dict) -> dict[str, dict]:
            return {p["id"]: p for p in structure.get("phases", [])}

        bmap = _phase_map(before)
        amap = _phase_map(after)

        added   = [pid for pid in amap if pid not in bmap]
        removed = [pid for pid in bmap if pid not in amap]
        changed = [
            pid for pid in amap
            if pid in bmap and amap[pid] != bmap[pid]
        ]

        return {
            "added":   added,
            "removed": removed,
            "changed": changed,
            "total":   len(added) + len(removed) + len(changed),
        }

    # ── 履歴記録 ──────────────────────────────────────────────

    def record_history(
        self,
        diff:     dict,
        log_path: Path | None = None,
        note:     str = "",
    ) -> None:
        """差分を wbs_history.log に追記する。"""
        path = log_path or self._history_log
        path.parent.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        note_str = f"  備考: {note}\n" if note else ""
        entry = (
            f"[{ts}] WBS差分記録\n"
            f"  追加フェーズ: {diff.get('added', []) or 'なし'}\n"
            f"  削除フェーズ: {diff.get('removed', []) or 'なし'}\n"
            f"  変更フェーズ: {diff.get('changed', []) or 'なし'}\n"
            f"  変更総件数  : {diff.get('total', 0)}\n"
            f"{note_str}"
            "---\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── HITL 連携 ─────────────────────────────────────────────

    def requires_hitl_approval(self, diff: dict) -> bool:
        """
        削除フェーズがある場合、または変更件数が多い場合に HITL 承認を要求する。

        基準:
          - removed が 1 件以上
          - total が 3 件以上
        """
        return bool(diff.get("removed")) or diff.get("total", 0) >= 3

    # ── summary.log 追記 ─────────────────────────────────────

    def write_summary_entry(
        self,
        diff:     dict,
        log_path: Path | None = None,
    ) -> None:
        """WP9310 完了エントリを summary.log に追記する。"""
        path = log_path or self._summary_log
        ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        hitl_needed = "あり（要承認）" if self.requires_hitl_approval(diff) else "不要"

        entry = (
            f"\n[{ts}] WP9310 WBS更新管理\n"
            f"  追加フェーズ  : {diff.get('added', []) or 'なし'}\n"
            f"  変更フェーズ  : {diff.get('changed', []) or 'なし'}\n"
            f"  HITL承認      : {hitl_needed}\n"
            f"  変更総件数    : {diff.get('total', 0)}\n"
            f"  Phase 6.5 フラグ: READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
