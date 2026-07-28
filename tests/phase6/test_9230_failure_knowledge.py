"""WP9230 失敗知識蓄積テスト（Failure Knowledge Accumulation and Preventive Learning Test）
Phase 6：改善層（9200番台）

テスト対象:
  - src/knowledge/failure_repository.py
    - FailureRepository.load_known_failures()
    - FailureRepository.extract_from_log()
    - FailureRepository.extract_from_monitor()
    - FailureRepository.register()
    - FailureRepository.cluster_similar()
    - FailureRepository.generate_prevention_patterns()
    - FailureRepository.save_repository()
    - FailureRepository.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.knowledge.failure_repository import (
    FailureRepository,
    CAT_API_ERROR, CAT_HITL, CAT_RETRY_EXCEEDED, CAT_FAILSAFE,
    CAT_MECE, CAT_TRACE,
)
from src.monitoring.monitor import MonitoringHandler


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _make_log(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════════════════════════
# TestWP9231 — データ抽出（ログ・モニター）
# ════════════════════════════════════════════════════════════════════════════

class TestWP9231_DataExtraction:

    @pytest.fixture
    def repo(self, tmp_path):
        return FailureRepository(
            summary_log=tmp_path / "summary.log",
            repo_path=tmp_path / "failure_repository.json",
        )

    @pytest.fixture
    def handler(self, tmp_path):
        return MonitoringHandler(summary_log_path=tmp_path / "s.log")

    def test_extract_from_log_returns_list(self, repo, tmp_path):
        log = _make_log(tmp_path / "summary.log", "")
        assert isinstance(repo.extract_from_log(log), list)

    def test_extract_from_log_detects_error_line(self, repo, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT ERROR module=src.agents.f10_module msg=X\n")
        entries = repo.extract_from_log(log)
        assert any(e["category"] == CAT_API_ERROR for e in entries)

    def test_extract_from_log_detects_retry_line(self, repo, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT RETRY module=src.agents.f10_module msg=リトライ\n")
        entries = repo.extract_from_log(log)
        assert any(e["category"] == CAT_RETRY_EXCEEDED for e in entries)

    def test_extract_from_log_detects_hitl_line(self, repo, tmp_path):
        log = _make_log(tmp_path / "summary.log",
            "[T] ALERT HITL module=src.agents.f10_module msg=HITL移譲\n")
        entries = repo.extract_from_log(log)
        assert any(e["category"] == CAT_HITL for e in entries)

    def test_extract_from_log_empty_returns_empty(self, repo, tmp_path):
        log = _make_log(tmp_path / "summary.log", "通常稼働\n")
        assert repo.extract_from_log(log) == []

    def test_extract_from_log_nonexistent_returns_empty(self, repo, tmp_path):
        assert repo.extract_from_log(tmp_path / "no.log") == []

    def test_extract_from_monitor_returns_list(self, repo, handler):
        assert isinstance(repo.extract_from_monitor(handler), list)

    def test_extract_from_monitor_detects_failsafe(self, repo, handler):
        handler.record_failsafe("F10", "TRC-001", "SRC-001", "L")
        entries = repo.extract_from_monitor(handler)
        assert len(entries) == 1
        assert entries[0]["category"] == CAT_FAILSAFE


# ════════════════════════════════════════════════════════════════════════════
# TestWP9232 — 既知事例読み込みと登録
# ════════════════════════════════════════════════════════════════════════════

class TestWP9232_FailureRegistration:

    @pytest.fixture
    def repo(self, tmp_path):
        return FailureRepository(
            summary_log=tmp_path / "summary.log",
            repo_path=tmp_path / "failure_repository.json",
        )

    def test_load_known_failures_returns_list(self, repo):
        entries = repo.load_known_failures()
        assert isinstance(entries, list)

    def test_load_known_failures_has_five_entries(self, repo):
        entries = repo.load_known_failures()
        assert len(entries) == 5

    def test_known_failures_include_hitl_category(self, repo):
        repo.load_known_failures()
        cats = {e["category"] for e in repo.get_all_entries()}
        assert CAT_HITL in cats

    def test_known_failures_include_retry_exceeded(self, repo):
        repo.load_known_failures()
        cats = {e["category"] for e in repo.get_all_entries()}
        assert CAT_RETRY_EXCEEDED in cats

    def test_register_returns_failure_id(self, repo):
        fid = repo.register({"category": CAT_API_ERROR, "description": "テスト"})
        assert isinstance(fid, str) and len(fid) > 0

    def test_register_assigns_id_when_missing(self, repo):
        repo.register({"category": CAT_API_ERROR, "description": "テスト"})
        entries = repo.get_all_entries()
        assert all("failure_id" in e for e in entries)

    def test_register_preserves_existing_id(self, repo):
        fid = repo.register({"failure_id": "CUSTOM-001", "category": CAT_API_ERROR})
        assert fid == "CUSTOM-001"

    def test_load_known_failures_not_duplicated_on_second_call(self, repo):
        repo.load_known_failures()
        count1 = len(repo.get_all_entries())
        repo.load_known_failures()
        count2 = len(repo.get_all_entries())
        assert count1 == count2


# ════════════════════════════════════════════════════════════════════════════
# TestWP9233 — 類似事例クラスタリング
# ════════════════════════════════════════════════════════════════════════════

class TestWP9233_SimilarClustering:

    @pytest.fixture
    def repo_with_known(self, tmp_path):
        repo = FailureRepository(
            summary_log=tmp_path / "summary.log",
            repo_path=tmp_path / "failure_repository.json",
        )
        repo.load_known_failures()
        return repo

    def test_cluster_returns_list(self, repo_with_known):
        clusters = repo_with_known.cluster_similar()
        assert isinstance(clusters, list)

    def test_cluster_has_category_key(self, repo_with_known):
        clusters = repo_with_known.cluster_similar()
        assert all("category" in c for c in clusters)

    def test_cluster_has_count_key(self, repo_with_known):
        clusters = repo_with_known.cluster_similar()
        assert all("count" in c for c in clusters)

    def test_cluster_has_failure_ids(self, repo_with_known):
        clusters = repo_with_known.cluster_similar()
        assert all("failure_ids" in c for c in clusters)

    def test_cluster_counts_sum_to_total(self, repo_with_known):
        clusters = repo_with_known.cluster_similar()
        total = sum(c["count"] for c in clusters)
        assert total == len(repo_with_known.get_all_entries())

    def test_cluster_hitl_group_has_multiple(self, repo_with_known):
        clusters = repo_with_known.cluster_similar()
        hitl_cluster = next((c for c in clusters if c["category"] == CAT_HITL), None)
        assert hitl_cluster is not None
        assert hitl_cluster["count"] >= 2

    def test_cluster_with_custom_entries(self, tmp_path):
        repo = FailureRepository(summary_log=tmp_path / "s.log")
        repo.register({"category": CAT_API_ERROR, "description": "A"})
        repo.register({"category": CAT_API_ERROR, "description": "B"})
        repo.register({"category": CAT_HITL, "description": "C"})
        clusters = repo.cluster_similar()
        api_c = next(c for c in clusters if c["category"] == CAT_API_ERROR)
        assert api_c["count"] == 2


# ════════════════════════════════════════════════════════════════════════════
# TestWP9234 — 防止パターン生成
# ════════════════════════════════════════════════════════════════════════════

class TestWP9234_PreventionPattern:

    @pytest.fixture
    def repo_with_patterns(self, tmp_path):
        repo = FailureRepository(
            summary_log=tmp_path / "summary.log",
            repo_path=tmp_path / "failure_repository.json",
        )
        repo.load_known_failures()
        repo.generate_prevention_patterns()
        return repo

    def test_generate_returns_list(self, repo_with_patterns):
        assert isinstance(repo_with_patterns.get_prevention_patterns(), list)

    def test_generates_at_least_four_patterns(self, repo_with_patterns):
        assert len(repo_with_patterns.get_prevention_patterns()) >= 4

    def test_patterns_have_pattern_id(self, repo_with_patterns):
        patterns = repo_with_patterns.get_prevention_patterns()
        assert all("pattern_id" in p for p in patterns)

    def test_patterns_have_category(self, repo_with_patterns):
        patterns = repo_with_patterns.get_prevention_patterns()
        assert all("category" in p for p in patterns)

    def test_patterns_have_trigger(self, repo_with_patterns):
        patterns = repo_with_patterns.get_prevention_patterns()
        assert all("trigger" in p for p in patterns)

    def test_hitl_pattern_present(self, repo_with_patterns):
        cats = {p["category"] for p in repo_with_patterns.get_prevention_patterns()}
        assert CAT_HITL in cats

    def test_retry_pattern_present(self, repo_with_patterns):
        cats = {p["category"] for p in repo_with_patterns.get_prevention_patterns()}
        assert CAT_RETRY_EXCEEDED in cats


# ════════════════════════════════════════════════════════════════════════════
# TestWP9235 — failure_repository.json 出力
# ════════════════════════════════════════════════════════════════════════════

class TestWP9235_RepositoryOutput:

    @pytest.fixture
    def repo_ready(self, tmp_path):
        repo = FailureRepository(
            summary_log=tmp_path / "summary.log",
            repo_path=tmp_path / "failure_repository.json",
        )
        repo.load_known_failures()
        repo.generate_prevention_patterns()
        return repo, tmp_path / "failure_repository.json"

    def test_save_repository_creates_file(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        assert path.exists()

    def test_save_repository_is_valid_json(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_repository_has_failures_key(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "failures" in data

    def test_repository_has_prevention_patterns(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "prevention_patterns" in data

    def test_repository_has_phase7_ready_flag(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["phase7_ready"] is True

    def test_repository_total_failures_correct(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["total_failures"] == len(repo.get_all_entries())

    def test_repository_has_clusters(self, repo_ready):
        repo, path = repo_ready
        repo.save_repository(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "clusters" in data


# ════════════════════════════════════════════════════════════════════════════
# TestWP9236 — summary.log への完了エントリ出力
# ════════════════════════════════════════════════════════════════════════════

class TestWP9236_SummaryLogEntry:

    @pytest.fixture
    def repo_ready(self, tmp_path):
        repo = FailureRepository(
            summary_log=tmp_path / "summary.log",
            repo_path=tmp_path / "failure_repository.json",
        )
        repo.load_known_failures()
        repo.generate_prevention_patterns()
        return repo, tmp_path / "summary.log"

    def test_write_summary_creates_log(self, repo_ready):
        repo, log = repo_ready
        repo.write_summary_entry(log_path=log)
        assert log.exists()

    def test_summary_has_wp9230_header(self, repo_ready):
        repo, log = repo_ready
        repo.write_summary_entry(log_path=log)
        assert "WP9230 失敗知識蓄積完了" in log.read_text(encoding="utf-8")

    def test_summary_shows_failure_count(self, repo_ready):
        repo, log = repo_ready
        repo.write_summary_entry(log_path=log)
        assert "件" in log.read_text(encoding="utf-8")

    def test_summary_has_phase7_ready(self, repo_ready):
        repo, log = repo_ready
        repo.write_summary_entry(log_path=log)
        assert "Phase 7" in log.read_text(encoding="utf-8")

    def test_summary_has_phase6_ready_flag(self, repo_ready):
        repo, log = repo_ready
        repo.write_summary_entry(log_path=log)
        assert "READY" in log.read_text(encoding="utf-8")
