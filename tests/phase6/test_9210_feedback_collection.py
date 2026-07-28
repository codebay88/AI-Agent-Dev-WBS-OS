"""WP9210 フィードバック収集テスト（Feedback Aggregation and Insight Extraction Test）
Phase 6：改善層（9200番台）

テスト対象:
  - src/improvement/feedback_collector.py
    - FeedbackCollector.collect_from_log()
    - FeedbackCollector.collect_from_hitl_tracker()
    - FeedbackCollector.collect_from_monitor()
    - FeedbackCollector.analyze()
    - FeedbackCollector.save_report()
    - FeedbackCollector.write_summary_entry()
"""

import json
from pathlib import Path

import pytest

from src.improvement.feedback_collector import FeedbackCollector
from src.monitoring.hitl_tracker import HITLTracker
from src.monitoring.monitor import MonitoringHandler


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _make_log(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════════════════════════
# TestWP9211 — summary.log からのデータ収集
# ════════════════════════════════════════════════════════════════════════════

class TestWP9211_LogDataCollection:

    @pytest.fixture
    def fc(self):
        return FeedbackCollector()

    def test_collect_from_log_has_counts_key(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log", "")
        result = fc.collect_from_log(log)
        assert "counts" in result

    def test_collect_from_log_has_total_ops(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log", "")
        assert "total_ops" in fc.collect_from_log(log)

    def test_collect_from_log_has_anomalies(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log", "")
        assert "anomalies" in fc.collect_from_log(log)

    def test_collect_from_log_error_count_correct(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log",
            "[T] ALERT ERROR module=f10 msg=X\n"
            "[T] ALERT ERROR module=f10 msg=Y\n")
        assert fc.collect_from_log(log)["counts"]["ERROR"] == 2

    def test_collect_from_log_total_ops_sums_non_info(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log",
            "[T] ALERT ERROR module=f10 msg=E\n"
            "[T] ALERT RETRY module=f10 msg=R\n"
            "[T] ALERT HITL module=f10 msg=H\n")
        result = fc.collect_from_log(log)
        assert result["total_ops"] == 3

    def test_collect_from_log_anomalies_on_high_error(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log",
            "[T] ALERT ERROR module=f10 msg=X\n" * 3)
        result = fc.collect_from_log(log)
        assert len(result["anomalies"]) > 0

    def test_collect_from_log_no_anomalies_on_clean(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log", "通常稼働\n")
        assert fc.collect_from_log(log)["anomalies"] == []

    def test_collect_from_log_empty_file_zero_total(self, fc, tmp_path):
        log = _make_log(tmp_path / "s.log", "")
        assert fc.collect_from_log(log)["total_ops"] == 0


# ════════════════════════════════════════════════════════════════════════════
# TestWP9212 — HITLTracker からのデータ収集
# ════════════════════════════════════════════════════════════════════════════

class TestWP9212_HITLDataCollection:

    @pytest.fixture
    def fc(self):
        return FeedbackCollector()

    @pytest.fixture
    def tracker(self):
        t = HITLTracker()
        t.record_decision("F10", "E001", "approve")
        t.record_decision("F10", "E002", "approve")
        t.record_decision("F10", "E003", "reject")
        t.record_decision("F10", "E004", "reprocess")
        return t

    def test_collect_hitl_has_approved(self, fc, tracker):
        assert "approved" in fc.collect_from_hitl_tracker(tracker)

    def test_collect_hitl_approved_count_correct(self, fc, tracker):
        assert fc.collect_from_hitl_tracker(tracker)["approved"] == 2

    def test_collect_hitl_rejected_count_correct(self, fc, tracker):
        assert fc.collect_from_hitl_tracker(tracker)["rejected"] == 1

    def test_collect_hitl_reprocessed_count_correct(self, fc, tracker):
        assert fc.collect_from_hitl_tracker(tracker)["reprocessed"] == 1

    def test_collect_hitl_total_correct(self, fc, tracker):
        assert fc.collect_from_hitl_tracker(tracker)["total"] == 4

    def test_collect_hitl_approval_rate(self, fc, tracker):
        r = fc.collect_from_hitl_tracker(tracker)
        assert abs(r["approval_rate"] - 0.5) < 0.01

    def test_collect_hitl_misapproval_false_on_normal(self, fc, tracker):
        assert fc.collect_from_hitl_tracker(tracker)["misapproval_warning"] is False


# ════════════════════════════════════════════════════════════════════════════
# TestWP9213 — MonitoringHandler からのデータ収集
# ════════════════════════════════════════════════════════════════════════════

class TestWP9213_FailsafeDataCollection:

    @pytest.fixture
    def fc(self):
        return FeedbackCollector()

    @pytest.fixture
    def handler(self, tmp_path):
        return MonitoringHandler(summary_log_path=tmp_path / "s.log")

    def test_collect_monitor_has_failsafe_count(self, fc, handler):
        assert "failsafe_count" in fc.collect_from_monitor(handler)

    def test_collect_monitor_failsafe_count_zero_initially(self, fc, handler):
        assert fc.collect_from_monitor(handler)["failsafe_count"] == 0

    def test_collect_monitor_failsafe_count_increments(self, fc, handler):
        handler.record_failsafe("F10", "T001", "S001", "L")
        handler.record_failsafe("F20", "T002", "S002", "M")
        assert fc.collect_from_monitor(handler)["failsafe_count"] == 2

    def test_collect_monitor_alert_count_on_error(self, fc, handler):
        import logging
        lg = logging.getLogger("src.agents.f10_module")
        lg.addHandler(handler)
        lg.error("テスト")
        lg.removeHandler(handler)
        assert fc.collect_from_monitor(handler)["alert_count"] >= 1

    def test_collect_monitor_has_max_retry_exceeded(self, fc, handler):
        assert "max_retry_exceeded" in fc.collect_from_monitor(handler)

    def test_collect_monitor_max_retry_false_initially(self, fc, handler):
        assert fc.collect_from_monitor(handler)["max_retry_exceeded"] is False


# ════════════════════════════════════════════════════════════════════════════
# TestWP9214 — フィードバック分析
# ════════════════════════════════════════════════════════════════════════════

class TestWP9214_FeedbackAnalysis:

    @pytest.fixture
    def fc(self):
        return FeedbackCollector()

    @pytest.fixture
    def clean_log_data(self):
        return {"counts": {}, "total_ops": 10, "anomalies": []}

    @pytest.fixture
    def clean_hitl_data(self):
        return {"approved": 4, "rejected": 2, "reprocessed": 1,
                "total": 7, "approval_rate": 0.571, "misapproval_warning": False}

    @pytest.fixture
    def clean_failsafe_data(self):
        return {"failsafe_count": 0, "alert_count": 0,
                "retry_alert_count": 0, "error_alert_count": 0,
                "max_retry_exceeded": False}

    def test_analyze_has_collected_at(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert "collected_at" in r

    def test_analyze_has_approval_rate(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert "approval_rate" in r

    def test_analyze_has_retry_rate(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert "retry_rate" in r

    def test_analyze_has_failsafe_rate(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert "failsafe_rate" in r

    def test_analyze_has_improvement_targets(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert isinstance(r["improvement_targets"], list)

    def test_analyze_no_targets_on_clean_data(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert r["improvement_targets"] == []

    def test_analyze_retry_target_on_high_retry_rate(self, fc, clean_hitl_data):
        log_data      = {"counts": {}, "total_ops": 10, "anomalies": []}
        failsafe_data = {"failsafe_count": 0, "alert_count": 0,
                         "retry_alert_count": 2, "error_alert_count": 0,
                         "max_retry_exceeded": False}
        r = fc.analyze(log_data, clean_hitl_data, failsafe_data)
        assert any("RETRY" in t for t in r["improvement_targets"])

    def test_analyze_misapproval_target_on_high_rate(self, fc, clean_log_data, clean_failsafe_data):
        hitl_data = {"approved": 10, "rejected": 0, "reprocessed": 0,
                     "total": 10, "approval_rate": 1.0, "misapproval_warning": True}
        r = fc.analyze(clean_log_data, hitl_data, clean_failsafe_data)
        assert any("誤承認" in t for t in r["improvement_targets"])

    def test_analyze_phase6_ready_always_true(self, fc, clean_log_data, clean_hitl_data, clean_failsafe_data):
        r = fc.analyze(clean_log_data, clean_hitl_data, clean_failsafe_data)
        assert r["phase6_ready"] is True


# ════════════════════════════════════════════════════════════════════════════
# TestWP9215 — feedback_report.json 出力
# ════════════════════════════════════════════════════════════════════════════

class TestWP9215_ReportOutput:

    @pytest.fixture
    def fc(self):
        return FeedbackCollector()

    @pytest.fixture
    def sample_report(self):
        return {
            "collected_at": "2026-07-22T00:00:00",
            "anomaly_trends": [],
            "approval_rate": 0.6,
            "retry_rate": 0.01,
            "failsafe_rate": 0.00,
            "misapproval_warning": False,
            "improvement_targets": [],
            "phase6_ready": True,
        }

    def test_save_report_creates_file(self, fc, tmp_path, sample_report):
        p = tmp_path / "report.json"
        fc.save_report(sample_report, path=p)
        assert p.exists()

    def test_save_report_is_valid_json(self, fc, tmp_path, sample_report):
        p = tmp_path / "report.json"
        fc.save_report(sample_report, path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_save_report_has_approval_rate(self, fc, tmp_path, sample_report):
        p = tmp_path / "report.json"
        fc.save_report(sample_report, path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "approval_rate" in data

    def test_save_report_has_phase6_ready(self, fc, tmp_path, sample_report):
        p = tmp_path / "report.json"
        fc.save_report(sample_report, path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["phase6_ready"] is True

    def test_save_report_creates_parent_dirs(self, fc, tmp_path, sample_report):
        p = tmp_path / "deep" / "nested" / "report.json"
        fc.save_report(sample_report, path=p)
        assert p.exists()

    def test_save_report_japanese_chars_preserved(self, fc, tmp_path):
        p = tmp_path / "report.json"
        report = {"improvement_targets": ["RETRY閾値の見直し"], "phase6_ready": True}
        fc.save_report(report, path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "RETRY閾値の見直し" in data["improvement_targets"]

    def test_save_report_overwrite_on_second_call(self, fc, tmp_path, sample_report):
        p = tmp_path / "report.json"
        fc.save_report(sample_report, path=p)
        sample_report["approval_rate"] = 0.99
        fc.save_report(sample_report, path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["approval_rate"] == 0.99


# ════════════════════════════════════════════════════════════════════════════
# TestWP9216 — summary.log への完了エントリ出力
# ════════════════════════════════════════════════════════════════════════════

class TestWP9216_SummaryLogEntry:

    @pytest.fixture
    def fc(self):
        return FeedbackCollector()

    @pytest.fixture
    def sample_report(self):
        return {
            "collected_at": "2026-07-22T00:00:00",
            "anomaly_trends": [],
            "approval_rate": 0.6,
            "retry_rate": 0.01,
            "failsafe_rate": 0.00,
            "misapproval_warning": False,
            "improvement_targets": [],
            "phase6_ready": True,
        }

    def test_summary_entry_creates_log(self, fc, tmp_path, sample_report):
        log = tmp_path / "summary.log"
        fc.write_summary_entry(sample_report, log_path=log)
        assert log.exists()

    def test_summary_entry_has_wp9210_header(self, fc, tmp_path, sample_report):
        log = tmp_path / "summary.log"
        fc.write_summary_entry(sample_report, log_path=log)
        assert "WP9210 フィードバック収集完了" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_approval_rate(self, fc, tmp_path, sample_report):
        log = tmp_path / "summary.log"
        fc.write_summary_entry(sample_report, log_path=log)
        assert "承認率" in log.read_text(encoding="utf-8")

    def test_summary_entry_has_phase6_flag(self, fc, tmp_path, sample_report):
        log = tmp_path / "summary.log"
        fc.write_summary_entry(sample_report, log_path=log)
        assert "READY" in log.read_text(encoding="utf-8")

    def test_summary_entry_shows_misapproval_warning(self, fc, tmp_path):
        log = tmp_path / "summary.log"
        report = {
            "collected_at": "2026-07-22T00:00:00",
            "anomaly_trends": [],
            "approval_rate": 1.0,
            "retry_rate": 0.0,
            "failsafe_rate": 0.0,
            "misapproval_warning": True,
            "improvement_targets": ["誤承認率が高い（承認フローの見直し）"],
            "phase6_ready": True,
        }
        fc.write_summary_entry(report, log_path=log)
        assert "あり" in log.read_text(encoding="utf-8")
