"""WP9300〜9320 基盤維持層テスト（Maintenance Layer Test）
Phase 6.5：基盤維持層

テスト対象:
  - src/management/wbs_tracker.py
    - WBSTracker.load_structure / save_structure
    - WBSTracker.apply_phase_update
    - WBSTracker.detect_diff
    - WBSTracker.record_history
    - WBSTracker.requires_hitl_approval
    - WBSTracker.write_summary_entry
  - src/system/os_update_checker.py
    - OSUpdateChecker.check_environment
    - OSUpdateChecker.check_installed_packages
    - OSUpdateChecker.calculate_safety_score
    - OSUpdateChecker.classify_updates
    - OSUpdateChecker.generate_report
    - OSUpdateChecker.save_report
    - OSUpdateChecker.write_summary_entry
"""

import json
from pathlib import Path

import pytest
import yaml

from src.management.wbs_tracker import WBSTracker, HITL_THRESHOLD as WBS_HITL_LIMIT
from src.system.os_update_checker import (
    OSUpdateChecker, HITL_THRESHOLD, _get_package_version, _version_lt
)


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _sample_structure() -> dict:
    return {
        "version": "1.0.0",
        "last_updated": "2026-07-22",
        "phases": [
            {"id": "Phase5", "name": "運用層", "status": "active", "wps": ["WP9100"]},
            {"id": "Phase6", "name": "改善層", "status": "active", "wps": ["WP9210"]},
        ],
    }


# ════════════════════════════════════════════════════════════════════════════
# TestWP9301 — WBS構造の読み書き（WP9300）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9301_WBSStructure:

    @pytest.fixture
    def tracker(self, tmp_path):
        return WBSTracker(
            wbs_path=tmp_path / "wbs_structure.yaml",
            history_log=tmp_path / "wbs_history.log",
            summary_log=tmp_path / "summary.log",
        )

    def test_load_structure_returns_dict(self, tracker, tmp_path):
        p = tmp_path / "wbs_structure.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(_sample_structure(), f, allow_unicode=True)
        assert isinstance(tracker.load_structure(), dict)

    def test_load_structure_has_phases(self, tracker, tmp_path):
        p = tmp_path / "wbs_structure.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(_sample_structure(), f, allow_unicode=True)
        assert "phases" in tracker.load_structure()

    def test_load_structure_missing_file_returns_empty(self, tracker):
        assert tracker.load_structure() == {}

    def test_save_structure_creates_file(self, tracker, tmp_path):
        tracker.save_structure(_sample_structure())
        assert (tmp_path / "wbs_structure.yaml").exists()

    def test_save_and_reload_roundtrip(self, tracker):
        data = _sample_structure()
        tracker.save_structure(data)
        loaded = tracker.load_structure()
        assert loaded.get("version") == "1.0.0"
        assert len(loaded["phases"]) == 2

    def test_actual_wbs_structure_is_readable(self):
        tracker = WBSTracker()
        data = tracker.load_structure()
        assert "phases" in data

    def test_actual_wbs_has_phase7(self):
        tracker = WBSTracker()
        data    = tracker.load_structure()
        ids     = [p["id"] for p in data.get("phases", [])]
        assert "Phase7" in ids

    def test_actual_wbs_has_phase8(self):
        tracker = WBSTracker()
        data    = tracker.load_structure()
        ids     = [p["id"] for p in data.get("phases", [])]
        assert "Phase8" in ids


# ════════════════════════════════════════════════════════════════════════════
# TestWP9311 — 差分検出・履歴記録（WP9310）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9311_WBSDiff:

    @pytest.fixture
    def tracker(self, tmp_path):
        return WBSTracker(
            wbs_path=tmp_path / "wbs_structure.yaml",
            history_log=tmp_path / "wbs_history.log",
            summary_log=tmp_path / "summary.log",
        )

    def test_detect_diff_returns_dict(self, tracker):
        before = _sample_structure()
        after  = _sample_structure()
        diff   = tracker.detect_diff(before, after)
        assert isinstance(diff, dict)

    def test_detect_diff_no_changes_on_same_structure(self, tracker):
        s    = _sample_structure()
        diff = tracker.detect_diff(s, s)
        assert diff["total"] == 0

    def test_detect_diff_detects_added_phase(self, tracker):
        before = _sample_structure()
        after  = _sample_structure()
        after["phases"].append({"id": "Phase7", "status": "planned"})
        diff = tracker.detect_diff(before, after)
        assert "Phase7" in diff["added"]

    def test_detect_diff_detects_removed_phase(self, tracker):
        before = _sample_structure()
        after  = {"phases": [before["phases"][0]]}
        diff   = tracker.detect_diff(before, after)
        assert "Phase6" in diff["removed"]

    def test_detect_diff_detects_changed_phase(self, tracker):
        before = _sample_structure()
        after  = _sample_structure()
        after["phases"][0]["status"] = "completed"
        diff   = tracker.detect_diff(before, after)
        assert "Phase5" in diff["changed"]

    def test_apply_phase_update_adds_new_phase(self, tracker):
        structure = _sample_structure()
        new       = [{"id": "Phase7", "status": "planned", "wps": []}]
        result    = tracker.apply_phase_update(structure, new)
        ids       = [p["id"] for p in result["phases"]]
        assert "Phase7" in ids

    def test_apply_phase_update_updates_existing(self, tracker):
        structure = _sample_structure()
        updated   = [{"id": "Phase5", "name": "運用層", "status": "completed", "wps": []}]
        result    = tracker.apply_phase_update(structure, updated)
        phase5    = next(p for p in result["phases"] if p["id"] == "Phase5")
        assert phase5["status"] == "completed"

    def test_record_history_creates_log(self, tracker, tmp_path):
        diff = {"added": ["Phase7"], "removed": [], "changed": [], "total": 1}
        log  = tmp_path / "wbs_history.log"
        tracker.record_history(diff, log_path=log)
        assert log.exists() and "Phase7" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# TestWP9312 — HITL連携（WP9310）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9312_WBSApproval:

    @pytest.fixture
    def tracker(self, tmp_path):
        return WBSTracker(summary_log=tmp_path / "summary.log")

    def test_requires_hitl_false_on_small_diff(self, tracker):
        diff = {"added": ["Phase7"], "removed": [], "changed": [], "total": 1}
        assert tracker.requires_hitl_approval(diff) is False

    def test_requires_hitl_true_on_removal(self, tracker):
        diff = {"added": [], "removed": ["Phase5"], "changed": [], "total": 1}
        assert tracker.requires_hitl_approval(diff) is True

    def test_requires_hitl_true_on_large_diff(self, tracker):
        diff = {"added": ["A", "B"], "removed": [], "changed": ["C"], "total": 3}
        assert tracker.requires_hitl_approval(diff) is True

    def test_write_summary_entry_creates_log(self, tracker, tmp_path):
        diff = {"added": [], "removed": [], "changed": [], "total": 0}
        log  = tmp_path / "summary.log"
        tracker.write_summary_entry(diff, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_wp9310_header(self, tracker, tmp_path):
        diff = {"added": [], "removed": [], "changed": [], "total": 0}
        log  = tmp_path / "summary.log"
        tracker.write_summary_entry(diff, log_path=log)
        assert "WP9310 WBS更新管理" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_ready_flag(self, tracker, tmp_path):
        diff = {"added": [], "removed": [], "changed": [], "total": 0}
        log  = tmp_path / "summary.log"
        tracker.write_summary_entry(diff, log_path=log)
        assert "READY" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# TestWP9321 — OS更新候補検出・スコア算出（WP9320）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9321_OSUpdateCheck:

    @pytest.fixture
    def checker(self, tmp_path):
        return OSUpdateChecker(
            report_path=tmp_path / "os_update_report.json",
            summary_log=tmp_path / "summary.log",
        )

    def test_check_environment_returns_dict(self, checker):
        assert isinstance(checker.check_environment(), dict)

    def test_check_environment_has_python_version(self, checker):
        env = checker.check_environment()
        assert "python_version" in env
        assert env["python_version"].startswith("3.")

    def test_check_packages_returns_list(self, checker):
        pkgs = checker.check_installed_packages()
        assert isinstance(pkgs, list)

    def test_check_packages_has_status(self, checker):
        pkgs = checker.check_installed_packages()
        assert all("status" in p for p in pkgs)

    def test_check_packages_known_installed(self, checker):
        # pytest は実行環境に必ずある
        pkgs   = checker.check_installed_packages({"pytest": "7.0.0"})
        pytest_ = pkgs[0]
        assert pytest_["status"] in ("ok", "version_low")

    def test_calculate_safety_score_is_int(self, checker):
        pkgs  = checker.check_installed_packages()
        score = checker.calculate_safety_score(pkgs)
        assert isinstance(score, int)

    def test_calculate_safety_score_100_on_all_ok(self, checker):
        pkgs  = [{"status": "ok", "update_type": "optional"},
                 {"status": "ok", "update_type": "optional"}]
        score = checker.calculate_safety_score(pkgs)
        assert score == 100

    def test_calculate_safety_score_decreased_on_compat(self, checker):
        pkgs  = [{"status": "version_low", "update_type": "compatibility"}]
        score = checker.calculate_safety_score(pkgs)
        assert score < 100


# ════════════════════════════════════════════════════════════════════════════
# TestWP9322 — レポート生成・記録更新（WP9320）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9322_MaintenanceRecord:

    @pytest.fixture
    def checker(self, tmp_path):
        return OSUpdateChecker(
            report_path=tmp_path / "os_update_report.json",
            summary_log=tmp_path / "summary.log",
        )

    @pytest.fixture
    def sample_report(self, checker):
        env   = checker.check_environment()
        pkgs  = checker.check_installed_packages()
        score = checker.calculate_safety_score(pkgs)
        return checker.generate_report(env, pkgs, score)

    def test_generate_report_has_safety_score(self, sample_report):
        assert "safety_score" in sample_report

    def test_generate_report_has_hitl_required(self, sample_report):
        assert "hitl_required" in sample_report

    def test_generate_report_has_phase_ready(self, sample_report):
        assert sample_report["phase6_5_ready"] is True

    def test_save_report_creates_file(self, checker, tmp_path, sample_report):
        p = tmp_path / "report.json"
        checker.save_report(sample_report, path=p)
        assert p.exists()

    def test_save_report_is_valid_json(self, checker, tmp_path, sample_report):
        p = tmp_path / "report.json"
        checker.save_report(sample_report, path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "safety_score" in data

    def test_write_summary_entry_creates_log(self, checker, tmp_path, sample_report):
        log = tmp_path / "summary.log"
        checker.write_summary_entry(sample_report, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_wp9320_header(self, checker, tmp_path, sample_report):
        log = tmp_path / "summary.log"
        checker.write_summary_entry(sample_report, log_path=log)
        assert "WP9320 OS更新判断" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# TestWP9323 — 統合確認
# ════════════════════════════════════════════════════════════════════════════

class TestWP9323_Integration:

    def test_version_lt_detects_older(self):
        assert _version_lt("6.0.0", "7.0.0") is True

    def test_version_lt_false_on_equal(self):
        assert _version_lt("7.0.0", "7.0.0") is False

    def test_version_lt_false_on_newer(self):
        assert _version_lt("8.1.0", "7.0.0") is False

    def test_get_package_version_pytest_installed(self):
        v = _get_package_version("pytest")
        assert v is not None and "." in v

    def test_get_package_version_returns_none_for_missing(self):
        assert _get_package_version("__nonexistent_pkg__") is None
