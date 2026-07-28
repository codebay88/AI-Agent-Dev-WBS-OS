"""知識循環フェーズ統合保存テスト（Knowledge Cycle Storage Test）
Phase 6 / 6.5：知識循環層

テスト対象:
  - src/knowledge/knowledge_cycle.py
    - KnowledgeCycle.load_wbs()
    - KnowledgeCycle.load_phase_data()
    - KnowledgeCycle.validate_artifacts()
    - KnowledgeCycle.build_dependency_graph()
    - KnowledgeCycle.get_phase_dependencies()
    - KnowledgeCycle.export_phase_summary()
    - KnowledgeCycle.save_cycle_index()
    - KnowledgeCycle.write_summary_entry()
"""

from pathlib import Path

import pytest
import yaml

from src.knowledge.knowledge_cycle import KnowledgeCycle, _PHASE_ARTIFACTS, _DEPENDENCIES


# ════════════════════════════════════════════════════════════════════════════
# TestKC01 — WBS・フェーズデータ読み込み
# ════════════════════════════════════════════════════════════════════════════

class TestKC01_PhaseDataLoading:

    @pytest.fixture
    def kc(self, tmp_path):
        return KnowledgeCycle(
            cycle_dir=tmp_path / "knowledge_cycle",
            summary_log=tmp_path / "summary.log",
        )

    def test_load_wbs_returns_dict(self, kc):
        data = kc.load_wbs()
        assert isinstance(data, dict)

    def test_load_wbs_has_phases(self, kc):
        data = kc.load_wbs()
        assert "phases" in data

    def test_load_phase_data_returns_dict(self, kc):
        d = kc.load_phase_data("Phase5")
        assert isinstance(d, dict)

    def test_load_phase_data_has_phase_id(self, kc):
        d = kc.load_phase_data("Phase5")
        assert d["phase_id"] == "Phase5"

    def test_load_phase_data_has_artifacts_list(self, kc):
        d = kc.load_phase_data("Phase5")
        assert isinstance(d["artifacts"], list) and len(d["artifacts"]) > 0

    def test_load_phase_data_has_status(self, kc):
        d = kc.load_phase_data("Phase5")
        assert d["status"] in ("ok", "partial", "missing")

    def test_load_phase_data_status_ok_when_all_present(self, kc):
        d = kc.load_phase_data("Phase5")
        if d["status"] == "ok":
            assert len(d["missing"]) == 0

    def test_load_phase_data_unknown_phase_returns_empty(self, kc):
        d = kc.load_phase_data("PhaseX")
        assert d["artifacts"] == []
        assert d["status"] == "missing"


# ════════════════════════════════════════════════════════════════════════════
# TestKC02 — 成果物検証
# ════════════════════════════════════════════════════════════════════════════

class TestKC02_ArtifactValidation:

    @pytest.fixture
    def kc(self):
        return KnowledgeCycle()

    def test_validate_all_returns_list(self, kc):
        issues = kc.validate_artifacts()
        assert isinstance(issues, list)

    def test_validate_phase5_artifacts_present(self, kc):
        # Phase5 の主要ファイルは実際に存在するはず
        d = kc.load_phase_data("Phase5")
        assert len(d["present"]) > 0

    def test_validate_phase6_artifacts_present(self, kc):
        d = kc.load_phase_data("Phase6")
        assert len(d["present"]) > 0

    def test_validate_phase65_artifacts_present(self, kc):
        d = kc.load_phase_data("Phase6.5")
        assert len(d["present"]) > 0

    def test_validate_specific_phase_returns_missing_only(self, kc):
        # 既存フェーズを確認 — missing は [] または存在しないファイルのみ
        issues = kc.validate_artifacts("Phase5")
        for item in issues:
            assert item.startswith("[Phase5]")

    def test_managed_phases_property_correct(self, kc):
        phases = kc.managed_phases
        assert "Phase5" in phases
        assert "Phase6" in phases
        assert "Phase6.5" in phases

    def test_phase_artifacts_constants_not_empty(self):
        assert len(_PHASE_ARTIFACTS) >= 3

    def test_all_phase5_monitoring_modules_registered(self):
        arts = _PHASE_ARTIFACTS.get("Phase5", [])
        assert any("monitor.py" in a for a in arts)
        assert any("hitl_tracker.py" in a for a in arts)


# ════════════════════════════════════════════════════════════════════════════
# TestKC03 — 依存グラフ
# ════════════════════════════════════════════════════════════════════════════

class TestKC03_DependencyGraph:

    @pytest.fixture
    def kc(self):
        return KnowledgeCycle()

    def test_build_dependency_graph_returns_dict(self, kc):
        graph = kc.build_dependency_graph()
        assert isinstance(graph, dict)

    def test_dependency_graph_has_phase5(self, kc):
        graph = kc.build_dependency_graph()
        assert "Phase5" in graph

    def test_dependency_graph_has_depends_on(self, kc):
        graph = kc.build_dependency_graph()
        assert "depends_on" in graph["Phase5"]

    def test_dependency_graph_has_required_by(self, kc):
        graph = kc.build_dependency_graph()
        assert "required_by" in graph["Phase5"]

    def test_phase5_depends_on_phase4(self, kc):
        deps = kc.get_phase_dependencies("Phase5")
        assert "Phase4" in deps

    def test_phase7_depends_on_phase6_and_65(self, kc):
        deps = kc.get_phase_dependencies("Phase7")
        assert "Phase6" in deps and "Phase6.5" in deps

    def test_phase8_depends_on_phase7(self, kc):
        deps = kc.get_phase_dependencies("Phase8")
        assert "Phase7" in deps


# ════════════════════════════════════════════════════════════════════════════
# TestKC04 — サイクルインデックス保存
# ════════════════════════════════════════════════════════════════════════════

class TestKC04_CycleIndexSave:

    @pytest.fixture
    def kc(self, tmp_path):
        return KnowledgeCycle(
            cycle_dir=tmp_path / "knowledge_cycle",
            summary_log=tmp_path / "summary.log",
        )

    @pytest.fixture
    def sample_summary(self, kc):
        return kc.export_phase_summary()

    def test_save_cycle_index_creates_file(self, kc, tmp_path, sample_summary):
        p = tmp_path / "knowledge_cycle" / "index.yaml"
        kc.save_cycle_index(sample_summary, path=p)
        assert p.exists()

    def test_save_cycle_index_is_valid_yaml(self, kc, tmp_path, sample_summary):
        p = tmp_path / "knowledge_cycle" / "index.yaml"
        kc.save_cycle_index(sample_summary, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_cycle_index_has_phases(self, kc, tmp_path, sample_summary):
        p = tmp_path / "knowledge_cycle" / "index.yaml"
        kc.save_cycle_index(sample_summary, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "phases" in data

    def test_cycle_index_has_phase7_ready(self, kc, tmp_path, sample_summary):
        p = tmp_path / "knowledge_cycle" / "index.yaml"
        kc.save_cycle_index(sample_summary, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert data.get("phase7_ready") is True

    def test_cycle_index_has_dependency_graph(self, kc, tmp_path, sample_summary):
        p = tmp_path / "knowledge_cycle" / "index.yaml"
        kc.save_cycle_index(sample_summary, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "dependency_graph" in data

    def test_cycle_index_has_total_phases(self, kc, tmp_path, sample_summary):
        p = tmp_path / "knowledge_cycle" / "index.yaml"
        kc.save_cycle_index(sample_summary, path=p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert data.get("total_phases", 0) >= 3

    def test_cycle_dir_property_is_path(self, kc):
        assert isinstance(kc.cycle_dir, Path)


# ════════════════════════════════════════════════════════════════════════════
# TestKC05 — フェーズサマリー出力
# ════════════════════════════════════════════════════════════════════════════

class TestKC05_PhaseSummaryExport:

    @pytest.fixture
    def kc(self):
        return KnowledgeCycle()

    def test_export_phase_summary_returns_dict(self, kc):
        s = kc.export_phase_summary()
        assert isinstance(s, dict)

    def test_summary_has_exported_at(self, kc):
        assert "exported_at" in kc.export_phase_summary()

    def test_summary_has_total_phases(self, kc):
        s = kc.export_phase_summary()
        assert s["total_phases"] >= 3

    def test_summary_has_phases_key(self, kc):
        s = kc.export_phase_summary()
        assert "phases" in s and isinstance(s["phases"], dict)

    def test_summary_has_all_ok_flag(self, kc):
        s = kc.export_phase_summary()
        assert "all_ok" in s

    def test_summary_phase7_ready_true(self, kc):
        s = kc.export_phase_summary()
        assert s["phase7_ready"] is True

    def test_summary_has_missing_files_list(self, kc):
        s = kc.export_phase_summary()
        assert "missing_files" in s and isinstance(s["missing_files"], list)


# ════════════════════════════════════════════════════════════════════════════
# TestKC06 — summary.log への完了エントリ
# ════════════════════════════════════════════════════════════════════════════

class TestKC06_SummaryLogEntry:

    @pytest.fixture
    def kc(self, tmp_path):
        return KnowledgeCycle(
            cycle_dir=tmp_path / "knowledge_cycle",
            summary_log=tmp_path / "summary.log",
        )

    def test_write_summary_entry_creates_log(self, kc, tmp_path):
        summary = kc.export_phase_summary()
        log     = tmp_path / "summary.log"
        kc.write_summary_entry(summary, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_cycle_header(self, kc, tmp_path):
        summary = kc.export_phase_summary()
        log     = tmp_path / "summary.log"
        kc.write_summary_entry(summary, log_path=log)
        assert "知識循環" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_phase_count(self, kc, tmp_path):
        summary = kc.export_phase_summary()
        log     = tmp_path / "summary.log"
        kc.write_summary_entry(summary, log_path=log)
        assert "管理フェーズ数" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_phase7_ready(self, kc, tmp_path):
        summary = kc.export_phase_summary()
        log     = tmp_path / "summary.log"
        kc.write_summary_entry(summary, log_path=log)
        assert "Phase 7" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_ready_flag(self, kc, tmp_path):
        summary = kc.export_phase_summary()
        log     = tmp_path / "summary.log"
        kc.write_summary_entry(summary, log_path=log)
        assert "READY" in log.read_text(encoding="utf-8")
