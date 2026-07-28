"""F40_Task_Generation_Module
Traceability: WP7200
前提モジュール: F30_Goal_Element_Evaluator
参照仕様: docs/F_series_overview.md
"""

import json
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

# ── 定数 ───────────────────────────────────────────────
AMBIGUOUS_WORDS   = ["など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"]
VALID_PRIORITIES  = {"High", "Medium", "Low"}
REQUIRED_FIELDS   = ("element_id", "priority", "score_importance", "score_feasibility")

# priority 別タスクプレフィックス
_PREFIX = {
    "High":   "【即実行】",
    "Medium": "【計画】",
    "Low":    "【検討】",
}


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> list:
    """入力検証。正常なら evaluated_goals リストを返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")
    if "evaluated_goals" not in input_data:
        raise ValueError("必須キー 'evaluated_goals' が存在しません")

    goals = input_data["evaluated_goals"]
    if not isinstance(goals, list):
        raise ValueError(
            f"'evaluated_goals' は list 型必須（受け取った型: {type(goals).__name__}）"
        )

    for i, elem in enumerate(goals):
        if not isinstance(elem, dict):
            raise ValueError(f"evaluated_goals[{i}] は dict 型必須")
        for field in REQUIRED_FIELDS:
            if field not in elem:
                raise ValueError(
                    f"evaluated_goals[{i}] に必須フィールド '{field}' が存在しません"
                )

    return goals


# ════════════════════════════════════════════════════════
# Step2: 前処理
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, goals: list) -> None:
    """trace_id チェック・空リスト・重複・スコア範囲の WARNING。"""
    source = input_data.get("trace_id", "")
    if source != "F30":
        log.warning("想定外の source trace_id: '%s'（F30 を期待）。処理は継続します。", source)

    if not goals:
        log.warning("'evaluated_goals' が空リストです。生成対象がありません。")
        return

    seen_ids: set[str] = set()
    for elem in goals:
        eid = elem.get("element_id", "")
        if eid in seen_ids:
            log.warning("重複 element_id を検出: '%s'", eid)
        seen_ids.add(eid)

        for score_key in ("score_importance", "score_feasibility"):
            val = elem.get(score_key)
            if val is not None and not (0.0 <= val <= 1.0):
                log.warning("スコア範囲外を検出: element_id='%s' %s=%s", eid, score_key, val)

        pri = elem.get("priority", "")
        if pri not in VALID_PRIORITIES:
            log.warning("不正な priority 値を検出: element_id='%s' priority='%s'", eid, pri)


# ════════════════════════════════════════════════════════
# Step3: HITL 移譲判定（要素単位）
# ════════════════════════════════════════════════════════

def _check_hitl_element(elem: dict) -> str | None:
    """要素単位で HITL 移譲が必要か判定。問題があれば理由文字列を返す。"""
    eid  = elem.get("element_id", "?")
    text = elem.get("text", "")

    # text フィールドが存在する場合のみテキスト系検証
    if "text" in elem:
        if not isinstance(text, str) or not text.strip():
            return "Goal element text is empty"
        for word in AMBIGUOUS_WORDS:
            if word in text:
                return f"曖昧語「{word}」を含むためタスク生成が困難です（HITL移譲）"

    # priority 判定不能
    pri = elem.get("priority", "")
    if pri not in VALID_PRIORITIES:
        return f"priority が判定不能です（値: '{pri}'）（HITL移譲）"

    # スコアが両方とも 0.5 未満かつ差が 0.05 以下（極端に曖昧）
    imp  = elem.get("score_importance",  0.0)
    feas = elem.get("score_feasibility", 0.0)
    if (isinstance(imp, (int, float)) and isinstance(feas, (int, float))
            and imp < 0.5 and feas < 0.5 and abs(imp - feas) <= 0.05):
        return (
            f"importance={imp} / feasibility={feas} が極端に曖昧なためタスク生成が困難です（HITL移譲）"
        )

    return None


# ════════════════════════════════════════════════════════
# Step4: タスク生成
# ════════════════════════════════════════════════════════

def _calc_effort(score_feasibility: float) -> int:
    """feasibility の反転から estimated_effort（1〜5）を算出する。"""
    return max(1, min(5, round((1 - score_feasibility) * 4) + 1))


def _calc_value(score_importance: float) -> int:
    """importance の正規化から estimated_value（1〜5）を算出する。"""
    return max(1, min(5, round(score_importance * 4) + 1))


def _generate_task(elem: dict, task_id: str) -> dict:
    """1要素からタスクを生成する。"""
    try:
        priority = elem["priority"]
        prefix   = _PREFIX.get(priority, "【タスク】")
        base     = elem.get("text", elem["element_id"]).strip() or elem["element_id"]
        task_text = f"{prefix}{base}"

        effort = _calc_effort(elem["score_feasibility"])
        value  = _calc_value(elem["score_importance"])

        return {
            "task_id":          task_id,
            "element_id":       elem["element_id"],
            "task_text":        task_text,
            "priority":         priority,
            "estimated_effort": effort,
            "estimated_value":  value,
        }
    except Exception as exc:
        wrapped = RuntimeError(
            f"タスク生成処理に失敗しました（element_id='{elem.get('element_id', '?')}'）"
        )
        wrapped.__cause__ = exc
        raise wrapped from exc


# ════════════════════════════════════════════════════════
# Step5: 整合性検証
# ════════════════════════════════════════════════════════

def _validate_tasks(tasks: list) -> None:
    """生成タスクの整合性を検証し、問題は WARNING で記録（処理継続）。"""
    seen_task_ids: set[str] = set()
    for task in tasks:
        tid = task.get("task_id", "?")
        if tid in seen_task_ids:
            log.warning("重複 task_id を検出: '%s'", tid)
        seen_task_ids.add(tid)

        for score_key, rng in (("estimated_effort", (1, 5)), ("estimated_value", (1, 5))):
            val = task.get(score_key)
            if val is None or not (rng[0] <= val <= rng[1]):
                log.warning(
                    "スコア範囲外を検出: task_id='%s' %s=%s（期待: %d〜%d）",
                    tid, score_key, val, rng[0], rng[1],
                )


# ════════════════════════════════════════════════════════
# Step6: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f40_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F40 モジュールの統一インターフェース。

    Args:
        input_data (dict): F30 の出力形式（evaluated_goals + trace_id）

    Returns:
        dict: {
            "trace_id": "F40",
            "source_trace_id": str,
            "tasks": list[dict],
            "hitl": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外
        ValueError:   evaluated_goals の欠落・型不正 / 必須フィールド欠落
        RuntimeError: タスク生成処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    goals        = _validate_input(input_data)
    source_trace = input_data.get("trace_id", "")

    # Step2: 前処理
    _preprocess(input_data, goals)

    # Step3 & Step4: HITL 判定 + タスク生成
    tasks:         list[dict] = []
    hitl_elements: list[str]  = []
    task_counter = 1

    for elem in goals:
        hitl_reason = _check_hitl_element(elem)
        if hitl_reason:
            log.warning(
                "[HITL移譲] element_id='%s' reason=%s", elem.get("element_id"), hitl_reason
            )
            hitl_elements.append(elem.get("element_id", ""))
            continue

        task = _generate_task(elem, f"T{task_counter}")
        tasks.append(task)
        task_counter += 1

    # 全要素が HITL 移譲対象の場合
    all_hitl = bool(goals) and len(hitl_elements) == len(goals)

    # Step5: 整合性検証
    _validate_tasks(tasks)

    output = {
        "trace_id":        "F40",
        "source_trace_id": source_trace,
        "tasks":           tasks,
        "hitl":            all_hitl,
        "hitl_elements":   hitl_elements,
    }

    # Step6: 保存・ログ
    saved = _save_output(output)
    log.info(
        "[F40] 処理完了 | 生成タスク数=%d | HITL移譲=%d件 | 保存: %s",
        len(tasks), len(hitl_elements), saved,
    )
    return output
