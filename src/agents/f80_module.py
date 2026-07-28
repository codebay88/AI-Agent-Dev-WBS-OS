"""F80_Traceability_Generation_Module
Traceability: WP7600
前提モジュール: F70_Hierarchy_Generation_Module
参照仕様: docs/F_series_overview.md, docs/F80_Module.md
"""

import json
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

# ── 定数 ───────────────────────────────────────────────
PIPELINE_ORDER: list[str] = ["F10", "F20", "F30", "F40", "F50", "F60", "F70"]
EXPECTED_ORIGIN = "F10"


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> list:
    """入力検証。正常なら goals リストを返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")
    if "hierarchy" not in input_data:
        raise ValueError("必須キー 'hierarchy' が存在しません")

    hierarchy = input_data["hierarchy"]
    if not isinstance(hierarchy, dict):
        raise ValueError(
            f"'hierarchy' は dict 型必須（受け取った型: {type(hierarchy).__name__}）"
        )
    if "goals" not in hierarchy:
        raise ValueError("必須キー 'hierarchy.goals' が存在しません")

    goals = hierarchy["goals"]
    if not isinstance(goals, list):
        raise ValueError(
            f"'hierarchy.goals' は list 型必須（受け取った型: {type(goals).__name__}）"
        )

    for gi, goal in enumerate(goals):
        if not isinstance(goal, dict):
            raise TypeError(f"goals[{gi}] は dict 型必須")
        if "goal_id" not in goal:
            raise TypeError(f"goals[{gi}] に必須フィールド 'goal_id' が存在しません")
        if "elements" not in goal:
            raise TypeError(f"goals[{gi}] に必須フィールド 'elements' が存在しません")

        for ei, elem in enumerate(goal["elements"]):
            if not isinstance(elem, dict):
                raise TypeError(f"goals[{gi}].elements[{ei}] は dict 型必須")
            if "element_id" not in elem:
                raise TypeError(
                    f"goals[{gi}].elements[{ei}] に必須フィールド 'element_id' が存在しません"
                )
            if "tasks" not in elem:
                raise TypeError(
                    f"goals[{gi}].elements[{ei}] に必須フィールド 'tasks' が存在しません"
                )
            for ti, task in enumerate(elem["tasks"]):
                if not isinstance(task, dict):
                    raise TypeError(
                        f"goals[{gi}].elements[{ei}].tasks[{ti}] は dict 型必須"
                    )
                if "task_id" not in task:
                    raise TypeError(
                        f"goals[{gi}].elements[{ei}].tasks[{ti}] に必須フィールド "
                        f"'task_id' が存在しません"
                    )

    return goals


# ════════════════════════════════════════════════════════
# Step2: 前処理
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, goals: list) -> bool:
    """trace_id チェック・空 goals・重複 task_id の WARNING 出力。
    空 goals の場合は True（HITL 移譲要）を返す。"""
    source = input_data.get("trace_id", "")
    if source != "F70":
        log.warning("想定外の source trace_id: '%s'（F70 を期待）。処理は継続します。", source)

    if not goals:
        log.warning("'hierarchy.goals' が空リストです。トレーサビリティ生成対象がありません。")
        return True

    # 全 goal を横断した重複 task_id 検出
    seen_task_ids: set[str] = set()
    for goal in goals:
        for elem in goal.get("elements", []):
            for task in elem.get("tasks", []):
                tid = task.get("task_id", "")
                if tid in seen_task_ids:
                    log.warning("重複 task_id を検出（横断）: '%s'", tid)
                seen_task_ids.add(tid)

    return False


# ════════════════════════════════════════════════════════
# Step3: trace_chain 構築
# ════════════════════════════════════════════════════════

def _build_trace_chain(source_trace_id: str) -> list[str]:
    """source_trace_id までの trace_chain を PIPELINE_ORDER から構築する。"""
    if source_trace_id in PIPELINE_ORDER:
        idx = PIPELINE_ORDER.index(source_trace_id)
        return list(PIPELINE_ORDER[: idx + 1])
    return []


# ════════════════════════════════════════════════════════
# Step4: 完全性チェック
# ════════════════════════════════════════════════════════

def _is_chain_complete(chain: list[str]) -> bool:
    """chain が PIPELINE_ORDER の全モジュールを含むか検証する。"""
    return bool(chain) and all(m in chain for m in PIPELINE_ORDER)


# ════════════════════════════════════════════════════════
# Step6: 循環依存 Union-Find 検出
# ════════════════════════════════════════════════════════

def _detect_circular_deps(goals: list) -> list[str]:
    """同一 task_id が複数 element に存在する場合を循環依存として検出する。"""
    task_to_elements: dict[str, list[str]] = {}
    for goal in goals:
        for elem in goal.get("elements", []):
            eid = elem.get("element_id", "")
            for task in elem.get("tasks", []):
                tid = task.get("task_id", "")
                task_to_elements.setdefault(tid, []).append(eid)

    circular: list[str] = []
    for tid, eids in task_to_elements.items():
        if len(eids) > 1:
            log.warning(
                "循環依存を検出: task_id='%s' が複数 element に存在: %s", tid, eids
            )
            circular.append(tid)
    return circular


# ════════════════════════════════════════════════════════
# Step3 + Step4 + Step5: 各タスクのエントリ生成
# ════════════════════════════════════════════════════════

def _build_trace_entry(
    goal_id:  str,
    elem_id:  str,
    task_id:  str,
    chain:    list[str],
    hitl_elements: list[str],
) -> dict:
    """1タスクのトレーサビリティエントリを生成する。"""
    try:
        is_complete    = _is_chain_complete(chain)
        origin_module  = chain[0]  if chain else None
        latest_module  = chain[-1] if chain else None

        # chain が空 → HITL
        if not chain:
            log.warning("trace_chain が空です: task_id='%s'", task_id)
            hitl_elements.append(task_id)

        # is_complete = False → HITL
        if not is_complete:
            hitl_elements.append(task_id)

        # origin_module が期待値以外 → WARNING + HITL
        if origin_module and origin_module != EXPECTED_ORIGIN:
            log.warning(
                "origin_module が不正: task_id='%s' origin='%s'（期待: '%s'）",
                task_id, origin_module, EXPECTED_ORIGIN,
            )
            hitl_elements.append(task_id)

        return {
            "goal_id":       goal_id,
            "element_id":    elem_id,
            "task_id":       task_id,
            "trace_chain":   chain,
            "origin_module": origin_module,
            "latest_module": latest_module,
            "is_complete":   is_complete,
        }
    except Exception as exc:
        wrapped = RuntimeError(
            f"trace_chain 構築に失敗しました（task_id='{task_id}'）"
        )
        wrapped.__cause__ = exc
        raise wrapped from exc


# ════════════════════════════════════════════════════════
# Step7: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f80_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F80 モジュールの統一インターフェース。

    Args:
        input_data (dict): F70 の出力形式（hierarchy + trace_id）

    Returns:
        dict: {
            "trace_id": "F80",
            "source_trace_id": str,
            "traceability_map": list[dict],
            "hitl": bool,
            "hitl_required": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または必須フィールド欠落
        ValueError:   hierarchy の欠落・型不正
        RuntimeError: trace_chain 構築処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    goals        = _validate_input(input_data)
    source_trace = input_data.get("trace_id", "")

    # Step2: 前処理（空 goals なら HITL 移譲）
    empty_hitl = _preprocess(input_data, goals)
    if empty_hitl:
        output = {
            "trace_id":          "F80",
            "source_trace_id":   source_trace,
            "traceability_map":  [],
            "hitl":              True,
            "hitl_required":     True,
            "hitl_elements":     [],
            "hitl_reason":       "No hierarchy provided",
        }
        _save_output(output)
        return output

    # Step3: trace_chain を source_trace_id から構築
    chain = _build_trace_chain(source_trace)

    # chain が空（source_trace_id 不明） → HITL 移譲
    if not chain:
        log.warning("trace_chain を構築できません（source_trace_id='%s'）。", source_trace)
        output = {
            "trace_id":          "F80",
            "source_trace_id":   source_trace,
            "traceability_map":  [],
            "hitl":              True,
            "hitl_required":     True,
            "hitl_elements":     [],
            "hitl_reason":       "Trace chain missing",
        }
        _save_output(output)
        return output

    hitl_elements: list[str] = []

    # Step3〜5: 各タスクのエントリ生成
    traceability_map: list[dict] = []
    for goal in goals:
        goal_id = goal["goal_id"]
        for elem in goal.get("elements", []):
            elem_id = elem["element_id"]
            for task in elem.get("tasks", []):
                task_id = task["task_id"]
                entry   = _build_trace_entry(goal_id, elem_id, task_id, chain, hitl_elements)
                traceability_map.append(entry)

    # Step6: 循環依存検出
    circular = _detect_circular_deps(goals)
    hitl_elements.extend(circular)

    # Step7: HITL 判定・保存
    hitl_required = bool(hitl_elements)

    output = {
        "trace_id":         "F80",
        "source_trace_id":  source_trace,
        "traceability_map": traceability_map,
        "hierarchy":        input_data.get("hierarchy", {"goals": []}),  # F90 へのパススルー
        "hitl":             hitl_required,
        "hitl_required":    hitl_required,
        "hitl_elements":    sorted(set(hitl_elements)),
    }

    saved = _save_output(output)
    log.info(
        "[F80] トレーサビリティ生成完了 | entries=%d | complete=%d | HITL=%s | 保存: %s",
        len(traceability_map),
        sum(1 for e in traceability_map if e["is_complete"]),
        hitl_required,
        saved,
    )
    return output
