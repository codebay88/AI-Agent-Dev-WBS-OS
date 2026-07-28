"""WP9220 テンプレ改善テスト（Template Optimization and Rule Refinement Test）
Phase 6：改善層（9200番台）

テスト対象:
  - src/improvement/template_optimizer.py
    - TemplateOptimizer.load_feedback()
    - TemplateOptimizer.apply_threshold_adjustments()
    - TemplateOptimizer.load_thresholds() / save_thresholds()
    - TemplateOptimizer.load_template_index() / validate_template_structure()
    - TemplateOptimizer.generate_optimization_summary()
    - TemplateOptimizer.write_summary_entry()
"""

import json
from pathlib import Path

import pytest
import yaml

from src.improvement.template_optimizer import TemplateOptimizer


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_yaml(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
    return path


def _base_thresholds() -> dict:
    return {
        "monitoring": {
            "consecutive_errors": 3,
            "hitl_per_session": 10,
            "retry_per_session": 5,
        },
        "hitl": {
            "approval_rate_warning": 0.90,
            "max_reprocess": 3,
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# TestWP9221 — feedback_report.json の読み込み
# ════════════════════════════════════════════════════════════════════════════

class TestWP9221_FeedbackLoading:

    @pytest.fixture
    def opt(self, tmp_path):
        return TemplateOptimizer(
            feedback_path=tmp_path / "feedback_report.json",
            threshold_path=tmp_path / "thresholds.yaml",
            template_index=tmp_path / "template_index.yaml",
            summary_log=tmp_path / "summary.log",
        )

    def test_load_feedback_returns_dict(self, opt, tmp_path):
        _write_json(tmp_path / "feedback_report.json", {"phase6_ready": True})
        assert isinstance(opt.load_feedback(), dict)

    def test_load_feedback_has_improvement_targets(self, opt, tmp_path):
        _write_json(tmp_path / "feedback_report.json",
                    {"improvement_targets": [], "phase6_ready": True})
        assert "improvement_targets" in opt.load_feedback()

    def test_load_feedback_reads_targets(self, opt, tmp_path):
        _write_json(tmp_path / "feedback_report.json",
                    {"improvement_targets": ["RETRY閾値の見直し"], "phase6_ready": True})
        r = opt.load_feedback()
        assert r["improvement_targets"] == ["RETRY閾値の見直し"]

    def test_load_feedback_returns_stable_dict_when_file_missing(self, opt):
        r = opt.load_feedback()
        assert r["phase6_ready"] is True
        assert r["improvement_targets"] == []

    def test_load_feedback_has_phase6_ready(self, opt, tmp_path):
        _write_json(tmp_path / "feedback_report.json", {"phase6_ready": True})
        assert opt.load_feedback()["phase6_ready"] is True

    def test_load_feedback_custom_path(self, opt, tmp_path):
        p = tmp_path / "custom.json"
        _write_json(p, {"improvement_targets": ["test"], "phase6_ready": True})
        r = opt.load_feedback(path=p)
        assert r["improvement_targets"] == ["test"]

    def test_load_feedback_actual_report_parseable(self):
        from src.improvement.template_optimizer import FEEDBACK_PATH
        opt = TemplateOptimizer()
        r = opt.load_feedback()
        assert "phase6_ready" in r


# ════════════════════════════════════════════════════════════════════════════
# TestWP9222 — 閾値調整
# ════════════════════════════════════════════════════════════════════════════

class TestWP9222_ThresholdAdjustment:

    @pytest.fixture
    def opt(self, tmp_path):
        return TemplateOptimizer(
            threshold_path=tmp_path / "thresholds.yaml",
            summary_log=tmp_path / "summary.log",
        )

    def test_no_change_when_no_targets(self, opt):
        feedback = {"improvement_targets": []}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        assert result["status"] == "stable_no_change"

    def test_no_changes_dict_on_stable(self, opt):
        feedback = {"improvement_targets": []}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        assert result["changes"] == {}

    def test_updated_thresholds_returned_on_stable(self, opt):
        feedback = {"improvement_targets": []}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        assert "updated_thresholds" in result

    def test_status_adjusted_when_targets_present(self, opt):
        feedback = {"improvement_targets": ["RETRY閾値の見直し（retry_per_session の再設定）"]}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        assert result["status"] == "adjusted"

    def test_retry_threshold_decreased_on_retry_target(self, opt):
        feedback = {"improvement_targets": ["RETRY閾値の見直し（retry_per_session の再設定）"]}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        base = _base_thresholds()
        after = result["updated_thresholds"]["monitoring"]["retry_per_session"]
        assert after < base["monitoring"]["retry_per_session"]

    def test_changes_has_before_after_on_adjustment(self, opt):
        feedback = {"improvement_targets": ["RETRY閾値の見直し（retry_per_session の再設定）"]}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        for field, chg in result["changes"].items():
            assert "before" in chg and "after" in chg

    def test_hitl_threshold_decreased_on_failsafe_target(self, opt):
        feedback = {"improvement_targets": ["フェイルセーフ発動頻度が高い（API安定性の確認）"]}
        result = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        base = _base_thresholds()
        after = result["updated_thresholds"]["monitoring"]["hitl_per_session"]
        assert after < base["monitoring"]["hitl_per_session"]

    def test_threshold_never_drops_below_one(self, opt):
        base = _base_thresholds()
        base["monitoring"]["retry_per_session"] = 1
        feedback = {"improvement_targets": ["RETRY閾値の見直し（retry_per_session の再設定）"]}
        result = opt.apply_threshold_adjustments(feedback, base)
        assert result["updated_thresholds"]["monitoring"]["retry_per_session"] >= 1

    def test_save_thresholds_writes_yaml(self, opt, tmp_path):
        p = tmp_path / "out.yaml"
        opt.save_thresholds(_base_thresholds(), path=p)
        assert p.exists()
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "monitoring" in data


# ════════════════════════════════════════════════════════════════════════════
# TestWP9223 — テンプレート構造確認
# ════════════════════════════════════════════════════════════════════════════

class TestWP9223_TemplateStructureCheck:

    @pytest.fixture
    def opt(self, tmp_path):
        return TemplateOptimizer(
            template_index=tmp_path / "template_index.yaml",
            summary_log=tmp_path / "summary.log",
        )

    @pytest.fixture
    def valid_index(self):
        return {
            "version": "1.0.0",
            "templates": [
                {"id": "TMP_HIGH",   "priority": "High",   "module": "F50",
                 "pattern": "【優先度: 高】次のタスクを実行せよ: {task_text}"},
                {"id": "TMP_MEDIUM", "priority": "Medium", "module": "F50",
                 "pattern": "【優先度: 中】検討すべきタスク: {task_text}"},
                {"id": "TMP_LOW",    "priority": "Low",    "module": "F50",
                 "pattern": "【優先度: 低】参考タスク: {task_text}"},
            ],
        }

    def test_load_template_index_returns_dict(self, opt, tmp_path, valid_index):
        _write_yaml(tmp_path / "template_index.yaml", valid_index)
        assert isinstance(opt.load_template_index(), dict)

    def test_load_template_index_has_templates_key(self, opt, tmp_path, valid_index):
        _write_yaml(tmp_path / "template_index.yaml", valid_index)
        assert "templates" in opt.load_template_index()

    def test_validate_structure_no_issues_on_valid_index(self, opt, valid_index):
        issues = opt.validate_template_structure(valid_index)
        assert issues == []

    def test_validate_structure_detects_missing_template(self, opt):
        index = {"templates": [
            {"id": "TMP_HIGH", "priority": "High", "module": "F50", "pattern": "X"},
        ]}
        issues = opt.validate_template_structure(index)
        assert any("TMP_MEDIUM" in i or "TMP_LOW" in i for i in issues)

    def test_validate_structure_detects_empty_templates(self, opt):
        issues = opt.validate_template_structure({"templates": []})
        assert len(issues) > 0

    def test_actual_template_index_is_valid(self):
        opt = TemplateOptimizer()
        index = opt.load_template_index()
        issues = opt.validate_template_structure(index)
        assert issues == []

    def test_all_required_template_ids_present(self):
        opt = TemplateOptimizer()
        index = opt.load_template_index()
        ids = {t["id"] for t in index.get("templates", [])}
        assert {"TMP_HIGH", "TMP_MEDIUM", "TMP_LOW"}.issubset(ids)

    def test_templates_match_f50_module_definitions(self):
        from src.agents.f50_module import _TEMPLATES
        opt   = TemplateOptimizer()
        index = opt.load_template_index()
        index_ids = {t["id"] for t in index.get("templates", [])}
        f50_ids   = {tid for tid, _ in _TEMPLATES.values()}
        assert f50_ids.issubset(index_ids)


# ════════════════════════════════════════════════════════════════════════════
# TestWP9224 — 再試行ロジック確認
# ════════════════════════════════════════════════════════════════════════════

class TestWP9224_RetryLogicVerification:

    def test_f10_max_retry_constant_is_three(self):
        from src.agents.f10_module import MAX_RETRY
        assert MAX_RETRY == 3

    def test_threshold_yaml_retry_consecutive_matches_f10(self):
        opt = TemplateOptimizer()
        th  = opt.load_thresholds()
        assert th.get("alert_rules", {}).get("retry_consecutive") == 3

    def test_monitoring_alert_rule_retry_threshold_is_three(self):
        from src.monitoring.alert_rules import DEFAULT_RULES
        assert DEFAULT_RULES["retry"].threshold == 3

    def test_hitl_max_reprocess_in_yaml_matches_hitl_approval(self):
        from src.monitoring.hitl_approval import MAX_REPROCESS
        opt = TemplateOptimizer()
        th  = opt.load_thresholds()
        assert th.get("hitl", {}).get("max_reprocess") == MAX_REPROCESS

    def test_approval_rate_warning_threshold_in_yaml(self):
        opt = TemplateOptimizer()
        th  = opt.load_thresholds()
        assert th.get("hitl", {}).get("approval_rate_warning") == 0.90

    def test_error_threshold_is_one_for_immediate_alert(self):
        opt = TemplateOptimizer()
        th  = opt.load_thresholds()
        assert th.get("alert_rules", {}).get("error_threshold") == 1

    def test_hitl_delay_threshold_thirty_seconds(self):
        opt = TemplateOptimizer()
        th  = opt.load_thresholds()
        assert th.get("alert_rules", {}).get("hitl_delay_seconds") == 30.0


# ════════════════════════════════════════════════════════════════════════════
# TestWP9225 — 最適化サマリーと記録更新
# ════════════════════════════════════════════════════════════════════════════

class TestWP9225_OptimizationRecord:

    @pytest.fixture
    def opt(self, tmp_path):
        return TemplateOptimizer(summary_log=tmp_path / "summary.log")

    @pytest.fixture
    def stable_summary(self, opt):
        feedback    = {"improvement_targets": []}
        adjustments = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        return opt.generate_optimization_summary(feedback, adjustments)

    def test_summary_has_optimized_at(self, stable_summary):
        assert "optimized_at" in stable_summary

    def test_summary_has_stability_status(self, stable_summary):
        assert "stability_status" in stable_summary

    def test_summary_has_phase6_ready(self, stable_summary):
        assert stable_summary["phase6_ready"] is True

    def test_summary_stable_status_on_no_targets(self, stable_summary):
        assert stable_summary["stability_status"] == "stable_no_change"

    def test_write_summary_entry_creates_log(self, opt, tmp_path, stable_summary):
        log = tmp_path / "summary.log"
        opt.write_summary_entry(stable_summary, log_path=log)
        assert log.exists()

    def test_write_summary_entry_has_wp9220_header(self, opt, tmp_path, stable_summary):
        log = tmp_path / "summary.log"
        opt.write_summary_entry(stable_summary, log_path=log)
        assert "WP9220 テンプレ改善完了" in log.read_text(encoding="utf-8")

    def test_write_summary_entry_has_phase6_ready(self, opt, tmp_path, stable_summary):
        log = tmp_path / "summary.log"
        opt.write_summary_entry(stable_summary, log_path=log)
        assert "READY" in log.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# TestWP9226 — 安定稼働状態の処理
# ════════════════════════════════════════════════════════════════════════════

class TestWP9226_StableStateHandling:

    @pytest.fixture
    def opt(self, tmp_path):
        return TemplateOptimizer(
            feedback_path=tmp_path / "feedback_report.json",
            summary_log=tmp_path / "summary.log",
        )

    def test_stable_state_logged_correctly(self, opt, tmp_path):
        _write_json(tmp_path / "feedback_report.json",
                    {"improvement_targets": [], "phase6_ready": True})
        feedback    = opt.load_feedback()
        adjustments = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        summary     = opt.generate_optimization_summary(feedback, adjustments)
        log         = tmp_path / "summary.log"
        opt.write_summary_entry(summary, log_path=log)
        content = log.read_text(encoding="utf-8")
        assert "stable_no_change" in content or "安定稼働状態" in content

    def test_actual_feedback_is_stable(self):
        opt      = TemplateOptimizer()
        feedback = opt.load_feedback()
        assert feedback.get("improvement_targets", []) == []

    def test_stable_feedback_produces_no_changes(self):
        opt         = TemplateOptimizer()
        feedback    = opt.load_feedback()
        adjustments = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        assert adjustments["changes"] == {}

    def test_stable_thresholds_yaml_valid(self):
        opt = TemplateOptimizer()
        th  = opt.load_thresholds()
        assert th.get("monitoring", {}).get("consecutive_errors") == 3
        assert th.get("monitoring", {}).get("hitl_per_session") == 10

    def test_full_optimization_flow_on_stable_state(self, opt, tmp_path):
        _write_json(tmp_path / "feedback_report.json",
                    {"improvement_targets": [], "phase6_ready": True})
        feedback    = opt.load_feedback()
        adjustments = opt.apply_threshold_adjustments(feedback, _base_thresholds())
        summary     = opt.generate_optimization_summary(feedback, adjustments)
        assert summary["stability_status"] == "stable_no_change"
        assert summary["threshold_changes"] == {}
        assert summary["phase6_ready"] is True
