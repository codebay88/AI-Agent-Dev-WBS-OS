"""
OptimizationEvaluator — Phase 7 WP9430 自己最適化評価

learning_patterns.json の各パターンに対して
再現性スコア・改善効果スコア・最適化指数を算出し、
optimization_report.json を生成する。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR       = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG    = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
PATTERNS_PATH  = BASE_DIR / "docs" / "knowledge_cycle" / "learning_patterns.json"
DATASET_PATH   = BASE_DIR / "docs" / "knowledge_cycle" / "learning_dataset.json"
REPORT_PATH    = BASE_DIR / "docs" / "knowledge_cycle" / "optimization_report.json"

# 安定性ステータス閾値
_STATUS_STABLE  = 0.90
_STATUS_WARNING = 0.70

# カテゴリ別の改善効果ウェイト
_IMPACT_WEIGHT = {
    "operational":  0.80,  # 運用: 再現性重視
    "improvement":  1.00,  # 改善: 効果重視
    "maintenance":  0.85,  # 維持: 安定性重視
    "environment":  0.75,  # 環境: 変化対応重視
}

# pattern_type 別再現性係数
_REPRO_COEFF = {
    "success":               1.00,
    "failure_resolved":      0.95,
    "failure_stopped":       0.90,
    "maintenance":           0.85,
    "environment_check":     0.80,
    "environment_assessment": 0.85,
}

# 再現性ラベル → 基本スコア
_REPRO_BASE = {"high": 0.95, "medium": 0.70, "low": 0.50}


def _reproducibility_score(pattern: dict) -> float:
    """
    パターンの再現性スコアを算出する（0〜1.0）。

    score × pattern_type 係数 × 再現性ラベル基本値 の加重平均。
    """
    base   = _REPRO_BASE.get(pattern.get("reproducibility", "medium"), 0.70)
    coeff  = _REPRO_COEFF.get(pattern.get("pattern_type", ""), 1.0)
    score  = pattern.get("score", 0.0)
    return round(min(1.0, (score * 0.5 + base * 0.3 + coeff * 0.2)), 4)


def _impact_score(pattern: dict) -> float:
    """
    パターンの改善効果スコアを算出する（0〜1.0）。

    result の内容・category ウェイト・score を組み合わせる。
    """
    cat    = pattern.get("category", "operational")
    weight = _IMPACT_WEIGHT.get(cat, 0.80)
    score  = pattern.get("score", 0.0)
    result = pattern.get("result", "")

    # 改善効果加算: 結果が具体的な成功状態または解決状態を示すか
    bonus = 0.0
    if "PASS" in result or "確認済み" in result:
        bonus = 0.05
    elif "HITL 移譲" in result or "停止" in result:
        # 安全停止も改善効果として評価（再発防止）
        bonus = 0.03

    return round(min(1.0, score * weight + bonus), 4)


def _optimization_index(repro: float, impact: float) -> float:
    """再現性スコアと改善効果スコアの加重平均（再現性 60%・効果 40%）。"""
    return round(repro * 0.6 + impact * 0.4, 4)


def _status(index: float) -> str:
    """最適化指数から安定性ステータスを返す。"""
    if index >= _STATUS_STABLE:
        return "stable"
    if index >= _STATUS_WARNING:
        return "warning"
    return "critical"


class OptimizationEvaluator:
    """
    学習パターンに対して再現性・改善効果・最適化指数を算出する。

    使い方:
        evaluator = OptimizationEvaluator()
        patterns  = evaluator.load_patterns()
        evaluated = evaluator.evaluate_reproducibility(patterns)
        evaluated = evaluator.evaluate_impact(evaluated)
        evaluated = evaluator.calculate_optimization_index(evaluated)
        report    = evaluator.export_report(evaluated)
        evaluator.save_report(report)
        evaluator.write_summary_entry(report)
    """

    def __init__(
        self,
        patterns_path: Path | None = None,
        dataset_path:  Path | None = None,
        report_path:   Path | None = None,
        summary_log:   Path | None = None,
    ) -> None:
        self._patterns_path = patterns_path or PATTERNS_PATH
        self._dataset_path  = dataset_path  or DATASET_PATH
        self._report_path   = report_path   or REPORT_PATH
        self._summary_log   = summary_log   or SUMMARY_LOG

    # ── データ読み込み ────────────────────────────────────────

    def load_patterns(self, path: Path | None = None) -> list[dict]:
        """learning_patterns.json からパターンリストを読み込む。"""
        p = path or self._patterns_path
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("patterns", [])

    def load_dataset(self, path: Path | None = None) -> dict:
        """learning_dataset.json を読み込む。"""
        p = path or self._dataset_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ── 評価関数 ─────────────────────────────────────────────

    def evaluate_reproducibility(
        self,
        patterns: list[dict],
    ) -> list[dict]:
        """
        各パターンに reproducibility_score を付与して返す。

        Args:
            patterns: load_patterns() の戻り値

        Returns:
            patterns に reproducibility_score フィールドを追加したリスト
        """
        result: list[dict] = []
        for p in patterns:
            entry = dict(p)
            entry["reproducibility_score"] = _reproducibility_score(p)
            result.append(entry)
        return result

    def evaluate_impact(
        self,
        patterns: list[dict],
    ) -> list[dict]:
        """
        各パターンに impact_score を付与して返す。

        Args:
            patterns: evaluate_reproducibility() の戻り値

        Returns:
            patterns に impact_score フィールドを追加したリスト
        """
        result: list[dict] = []
        for p in patterns:
            entry = dict(p)
            entry["impact_score"] = _impact_score(p)
            result.append(entry)
        return result

    def calculate_optimization_index(
        self,
        patterns: list[dict],
    ) -> list[dict]:
        """
        各パターンに optimization_index と status を付与して返す。

        Args:
            patterns: evaluate_impact() の戻り値（reproducibility_score・impact_score 必須）

        Returns:
            patterns に optimization_index / status フィールドを追加したリスト
        """
        result: list[dict] = []
        for p in patterns:
            entry = dict(p)
            repro  = p.get("reproducibility_score", 0.0)
            impact = p.get("impact_score", 0.0)
            index  = _optimization_index(repro, impact)
            entry["optimization_index"] = index
            entry["status"]             = _status(index)
            result.append(entry)
        return result

    # ── レポート生成 ─────────────────────────────────────────

    def export_report(self, evaluated: list[dict]) -> dict:
        """
        評価済みパターンリストから optimization_report.json 用 dict を生成する。

        Returns:
            dict — {generated_at, total_patterns, summary, by_category,
                    evaluated_patterns, phase7_complete, phase8_ready}
        """
        if not evaluated:
            return {
                "generated_at": datetime.now().isoformat(),
                "total_patterns": 0,
                "summary": {},
                "by_category": {},
                "evaluated_patterns": [],
                "phase7_complete": True,
                "phase8_ready": True,
            }

        repro_scores  = [p["reproducibility_score"] for p in evaluated]
        impact_scores = [p["impact_score"] for p in evaluated]
        opt_indexes   = [p["optimization_index"] for p in evaluated]

        by_category: dict[str, dict] = {}
        for p in evaluated:
            cat = p.get("category", "")
            by_category.setdefault(cat, {"patterns": [], "avg_reproducibility": 0.0,
                                          "avg_impact": 0.0, "avg_optimization_index": 0.0})
            by_category[cat]["patterns"].append(p)

        # カテゴリ別平均を計算
        for cat, info in by_category.items():
            ps = info["patterns"]
            info["avg_reproducibility"]    = round(sum(p["reproducibility_score"] for p in ps) / len(ps), 4)
            info["avg_impact"]             = round(sum(p["impact_score"] for p in ps) / len(ps), 4)
            info["avg_optimization_index"] = round(sum(p["optimization_index"] for p in ps) / len(ps), 4)

        stable_count  = sum(1 for p in evaluated if p["status"] == "stable")
        warning_count = sum(1 for p in evaluated if p["status"] == "warning")
        critical_count = sum(1 for p in evaluated if p["status"] == "critical")

        return {
            "generated_at":    datetime.now().isoformat(),
            "version":         "1.0.0",
            "phase":           7,
            "total_patterns":  len(evaluated),
            "summary": {
                "avg_reproducibility_score": round(sum(repro_scores) / len(repro_scores), 4),
                "avg_impact_score":          round(sum(impact_scores) / len(impact_scores), 4),
                "avg_optimization_index":    round(sum(opt_indexes) / len(opt_indexes), 4),
                "status_distribution": {
                    "stable":   stable_count,
                    "warning":  warning_count,
                    "critical": critical_count,
                },
                "overall_status": (
                    "stable" if critical_count == 0 and warning_count == 0
                    else "warning" if critical_count == 0
                    else "critical"
                ),
            },
            "by_category":        {
                cat: {
                    "count":                  len(info["patterns"]),
                    "avg_reproducibility":    info["avg_reproducibility"],
                    "avg_impact":             info["avg_impact"],
                    "avg_optimization_index": info["avg_optimization_index"],
                }
                for cat, info in by_category.items()
            },
            "evaluated_patterns": evaluated,
            "phase7_complete":    True,
            "phase8_ready":       True,
        }

    # ── 保存 / 読み込み ──────────────────────────────────────

    def save_report(
        self,
        report: dict,
        path:   Path | None = None,
    ) -> None:
        """docs/knowledge_cycle/optimization_report.json に保存する。"""
        p = path or self._report_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def load_report(self, path: Path | None = None) -> dict:
        """optimization_report.json を読み込む。"""
        p = path or self._report_path
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ── summary.log 追記 ─────────────────────────────────────

    def write_summary_entry(
        self,
        report:   dict,
        log_path: Path | None = None,
    ) -> None:
        """WP9430 完了エントリを summary.log に追記する。"""
        path    = log_path or self._summary_log
        ts      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        summary = report.get("summary", {})
        sd      = summary.get("status_distribution", {})

        cat_lines = "\n".join(
            f"    {cat}: avg_opt={info.get('avg_optimization_index', 0.0):.4f} ({info.get('count', 0)}件)"
            for cat, info in report.get("by_category", {}).items()
        )

        entry = (
            f"\n[{ts}] WP9430 自己最適化評価完了\n"
            f"  評価パターン総数      : {report.get('total_patterns', 0)}件\n"
            f"  再現性スコア平均      : {summary.get('avg_reproducibility_score', 0.0):.4f}\n"
            f"  改善効果スコア平均    : {summary.get('avg_impact_score', 0.0):.4f}\n"
            f"  最適化指数平均        : {summary.get('avg_optimization_index', 0.0):.4f}\n"
            f"  総合ステータス        : {summary.get('overall_status', 'unknown')}\n"
            f"  stable               : {sd.get('stable', 0)}件\n"
            f"  warning              : {sd.get('warning', 0)}件\n"
            f"  critical             : {sd.get('critical', 0)}件\n"
            f"  カテゴリ別最適化指数:\n{cat_lines}\n"
            f"  出力ファイル          : docs/knowledge_cycle/optimization_report.json\n"
            f"  Phase 7 フラグ        : COMPLETE\n"
            f"  Phase 8 フラグ        : READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
