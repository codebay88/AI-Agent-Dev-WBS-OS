"""F90_Final_Output_Generation_Module
Traceability: WP7700
前提モジュール: F80_Traceability_Generation_Module
参照仕様: docs/F_series_overview.md, docs/F90_Module.md
"""

import json
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

# ── 定数 ───────────────────────────────────────────────
EXPECTED_FULL_CHAIN = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]
ABSTRACT_WORDS      = ["改善", "向上", "検討", "最適化", "強化", "推進", "活性化"]
EFFICIENCY_MAX      = 10.0   # これを超えたら異常値


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> tuple[list, dict]:
    """入力検証。正常なら (traceability_map, hierarchy) を返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")
    if "traceability_map" not in input_data:
        raise ValueError("必須キー 'traceability_map' が存在しません")

    tmap = input_data["traceability_map"]
    if not isinstance(tmap, list):
        raise ValueError(
            f"'traceability_map' は list 型必須（受け取った型: {type(tmap).__name__}）"
        )

    # hierarchy は F80 パススルーが存在しない場合 TypeError
    if "hierarchy" not in input_data:
        raise TypeError(
            "'hierarchy' キーが存在しません（F80 の hierarchy パススルーを確認してください）"
        )
    hierarchy = input_data["hierarchy"]
    if not isinstance(hierarchy, dict):
        raise TypeError(
            f"'hierarchy' は dict 型必須（受け取った型: {type(hierarchy).__name__}）"
        )

    return tmap, hierarchy


# ════════════════════════════════════════════════════════
# Step2: 前処理
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, tmap: list, hierarchy: dict) -> bool:
    """trace_id チェック・空チェック・重複 task_id の WARNING 出力。
    空入力の場合は True（HITL 移譲要）を返す。"""
    source = input_data.get("trace_id", "")
    if source != "F80":
        log.warning("想定外の source trace_id: '%s'（F80 を期待）。処理は継続します。", source)

    goals = hierarchy.get("goals", [])
    if not tmap or not goals:
        log.warning("traceability_map または hierarchy.goals が空です。最終出力対象がありません。")
        return True

    seen: set[str] = set()
    for entry in tmap:
        tid = entry.get("task_id", "")
        if tid in seen:
            log.warning("重複 task_id を検出（traceability_map）: '%s'", tid)
        seen.add(tid)

    return False


# ════════════════════════════════════════════════════════
# Step3: 階層統合（hierarchy_with_trace 生成）
# ════════════════════════════════════════════════════════

def _build_trace_lookup(tmap: list) -> dict[str, list[str]]:
    """task_id → trace_chain のルックアップテーブルを構築する。"""
    return {entry["task_id"]: entry.get("trace_chain", []) for entry in tmap if "task_id" in entry}


def _merge_hierarchy_with_trace(hierarchy: dict, trace_lookup: dict) -> list:
    """hierarchy の各タスクに trace_chain を付与した hierarchy_with_trace を返す。"""
    result: list[dict] = []
    for goal in hierarchy.get("goals", []):
        merged_elements: list[dict] = []
        for elem in goal.get("elements", []):
            merged_tasks: list[dict] = []
            for task in elem.get("tasks", []):
                tid    = task.get("task_id", "")
                merged = dict(task)
                merged["trace_chain"] = trace_lookup.get(tid, [])
                merged_tasks.append(merged)
            merged_elements.append({**elem, "tasks": merged_tasks})
        result.append({**goal, "elements": merged_elements})
    return result


# ════════════════════════════════════════════════════════
# Step4: 整合性検証
# ════════════════════════════════════════════════════════

def _check_integrity(tmap: list, hitl_elements: list) -> bool:
    """全エントリの is_complete を検証し、不完全な task_id を hitl_elements に追加する。
    全 complete → True、1件でも不完全 → False。"""
    all_complete = True
    for entry in tmap:
        chain = entry.get("trace_chain", [])
        tid   = entry.get("task_id", "?")
        if not chain:
            log.warning("trace_chain が空です: task_id='%s'", tid)
            hitl_elements.append(tid)
            all_complete = False
        elif not entry.get("is_complete", False):
            hitl_elements.append(tid)
            all_complete = False
    return all_complete


# ════════════════════════════════════════════════════════
# Step5: 評価集計
# ════════════════════════════════════════════════════════

def _compute_evaluation(hierarchy_with_trace: list) -> dict:
    """effort・value の平均と efficiency_score を算出する。"""
    efforts: list[float] = []
    values:  list[float] = []

    for goal in hierarchy_with_trace:
        for elem in goal.get("elements", []):
            for task in elem.get("tasks", []):
                eff = task.get("effort")
                val = task.get("value")
                if eff is not None:
                    efforts.append(float(eff))
                if val is not None:
                    values.append(float(val))

    if not efforts:
        avg_effort = 0.0
    else:
        avg_effort = sum(efforts) / len(efforts)

    if not values:
        avg_value = 0.0
    else:
        avg_value = sum(values) / len(values)

    try:
        if avg_effort == 0.0:
            raise ZeroDivisionError("average_effort が 0 のため efficiency_score を算出できません")
        efficiency_score = round(avg_value / avg_effort, 2)
    except ZeroDivisionError as exc:
        wrapped = RuntimeError("efficiency_score の算出に失敗しました（ゼロ除算）")
        wrapped.__cause__ = exc
        raise wrapped from exc

    return {
        "average_effort":   round(avg_effort, 2),
        "average_value":    round(avg_value, 2),
        "efficiency_score": efficiency_score,
    }


# ════════════════════════════════════════════════════════
# Step6: 推奨事項生成
# ════════════════════════════════════════════════════════

def _generate_recommendations(
    hierarchy_with_trace: list,
    traceability_complete: bool,
    efficiency_score: float,
) -> list[str]:
    """評価結果に基づいて推奨事項リストを生成する。"""
    recs: list[str] = []

    # High priority タスクが存在
    has_high = any(
        task.get("priority") == "High"
        for goal in hierarchy_with_trace
        for elem in goal.get("elements", [])
        for task in elem.get("tasks", [])
    )
    if has_high:
        recs.append("高優先度タスクの実行を最優先とする")

    # 不完全な trace_chain
    if not traceability_complete:
        recs.append("曖昧語を含むタスクは HITL で再確認する")

    # 高効率（value/effort が高い）
    if efficiency_score > 3.0:
        recs.append("工数対比で高価値なタスクを優先的に実行する")

    return recs


def _check_recommendations_abstract(recommendations: list[str], hitl_elements: list) -> None:
    """recommendations 自体に ABSTRACT_WORDS が含まれる場合 hitl_elements に追加する。"""
    for rec in recommendations:
        for word in ABSTRACT_WORDS:
            if word in rec:
                log.warning("recommendation に抽象語が含まれています: '%s'", rec)
                if "recommendations" not in hitl_elements:
                    hitl_elements.append("recommendations")
                break


# ════════════════════════════════════════════════════════
# Step7: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f90_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F90 モジュールの統一インターフェース（F シリーズ最終出力）。

    Args:
        input_data (dict): F80 の出力形式
                           （traceability_map + hierarchy パススルー + trace_id）

    Returns:
        dict: {
            "trace_id": "F90",
            "source_trace_id": str,
            "final_output": {
                "summary": dict,
                "hierarchy_with_trace": list[dict],
                "evaluation_report": dict
            },
            "hitl": bool,
            "hitl_required": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または hierarchy 欠落・型不正
        ValueError:   traceability_map の欠落・型不正
        RuntimeError: 集計処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    tmap, hierarchy  = _validate_input(input_data)
    source_trace     = input_data.get("trace_id", "")

    # Step2: 前処理（空入力なら HITL 移譲）
    empty_hitl = _preprocess(input_data, tmap, hierarchy)
    if empty_hitl:
        output = {
            "trace_id":        "F90",
            "source_trace_id": source_trace,
            "final_output": {
                "summary": {
                    "total_goals":           0,
                    "total_elements":        0,
                    "total_tasks":           0,
                    "pipeline_integrity":    "incomplete",
                    "traceability_complete": False,
                },
                "hierarchy_with_trace": [],
                "evaluation_report": {
                    "average_effort":   0.0,
                    "average_value":    0.0,
                    "efficiency_score": 0.0,
                    "recommendations":  [],
                },
            },
            "hitl":          True,
            "hitl_required": True,
            "hitl_elements": [],
            "hitl_reason":   "No tasks to finalize",
        }
        _save_output(output)
        return output

    hitl_elements: list[str] = []

    # Step3: 階層統合
    trace_lookup        = _build_trace_lookup(tmap)
    hierarchy_with_trace = _merge_hierarchy_with_trace(hierarchy, trace_lookup)

    # Step4: 整合性検証
    traceability_complete = _check_integrity(tmap, hitl_elements)

    # Step5: 評価集計
    eval_metrics = _compute_evaluation(hierarchy_with_trace)
    efficiency_score = eval_metrics["efficiency_score"]

    # efficiency_score 異常値チェック
    if efficiency_score == 0.0 or efficiency_score > EFFICIENCY_MAX:
        log.warning("efficiency_score が異常値です: %s", efficiency_score)
        hitl_elements.append("efficiency_score")

    # Step6: 推奨事項生成
    recommendations = _generate_recommendations(
        hierarchy_with_trace, traceability_complete, efficiency_score
    )
    _check_recommendations_abstract(recommendations, hitl_elements)

    # summary 構築
    goals    = hierarchy.get("goals", [])
    n_goals  = len(goals)
    n_elems  = sum(len(g.get("elements", [])) for g in goals)
    n_tasks  = len(tmap)
    summary = {
        "total_goals":           n_goals,
        "total_elements":        n_elems,
        "total_tasks":           n_tasks,
        "pipeline_integrity":    "verified" if traceability_complete else "incomplete",
        "traceability_complete": traceability_complete,
    }

    evaluation_report = {
        **eval_metrics,
        "recommendations": recommendations,
    }

    final_output = {
        "summary":              summary,
        "hierarchy_with_trace": hierarchy_with_trace,
        "evaluation_report":    evaluation_report,
    }

    hitl_required = bool(hitl_elements)

    output = {
        "trace_id":        "F90",
        "source_trace_id": source_trace,
        "final_output":    final_output,
        "hitl":            hitl_required,
        "hitl_required":   hitl_required,
        "hitl_elements":   sorted(set(hitl_elements)),
    }

    saved = _save_output(output)
    log.info(
        "[F90] 最終出力生成完了 | goals=%d | tasks=%d | efficiency=%.2f | HITL=%s | 保存: %s",
        n_goals, n_tasks, efficiency_score, hitl_required, saved,
    )
    return output
