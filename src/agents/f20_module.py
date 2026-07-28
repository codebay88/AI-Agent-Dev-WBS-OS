"""F20_Goal_Expansion_Module
Traceability: WP7100 / WP7200
前提モジュール: F10_Objective_Structuring_Module
"""

import json
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

AMBIGUOUS_WORDS = ["など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"]
VALID_PARENTS = {"L1", "L2", "L3"}


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> dict:
    """入力検証。正常なら goal dict を返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")

    if "goal" not in input_data:
        raise ValueError("必須キー 'goal' が存在しません")

    goal = input_data["goal"]
    if not isinstance(goal, dict):
        raise ValueError(f"'goal' は dict 型必須（受け取った型: {type(goal).__name__}）")

    if "L1" not in goal:
        raise ValueError("必須キー 'goal.L1' が存在しません")
    if "L2" not in goal:
        raise ValueError("必須キー 'goal.L2' が存在しません")
    if "L3" not in goal:
        raise ValueError("必須キー 'goal.L3' が存在しません")

    if not isinstance(goal["L1"], str):
        raise ValueError(f"'goal.L1' は str 型必須（受け取った型: {type(goal['L1']).__name__}）")
    if not isinstance(goal["L2"], list):
        raise ValueError(f"'goal.L2' は list 型必須（受け取った型: {type(goal['L2']).__name__}）")
    if not isinstance(goal["L3"], list):
        raise ValueError(f"'goal.L3' は list 型必須（受け取った型: {type(goal['L3']).__name__}）")

    return goal


# ════════════════════════════════════════════════════════
# Step2: HITL 移譲判定
# ════════════════════════════════════════════════════════

def _check_hitl(goal: dict) -> str | None:
    """HITL 移譲が必要な条件を検出。問題があれば理由文字列を返す。"""
    l1 = goal["L1"].strip()
    if not l1:
        return "Goal text is empty"
    for word in AMBIGUOUS_WORDS:
        if word in l1:
            return f"曖昧語「{word}」を含むため展開が困難です（HITL移譲）"
    return None


# ════════════════════════════════════════════════════════
# Step3: 前処理（trace_id 確認・空要素・重複検出）
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, goal: dict) -> None:
    """前処理：trace_id チェック・空要素・重複要素の WARNING。"""
    source_trace = input_data.get("trace_id", "")
    if source_trace != "F10":
        log.warning(
            "想定外の source trace_id: '%s'（F10 を期待）。処理は継続します。", source_trace
        )

    for level in ("L2", "L3"):
        seen: set[str] = set()
        for item in goal[level]:
            if not isinstance(item, str) or not item.strip():
                log.warning("'goal.%s' に空文字列または非 str 要素が含まれています", level)
                continue
            if item in seen:
                log.warning("'goal.%s' に重複要素を検出: '%s'", level, item)
            seen.add(item)


# ════════════════════════════════════════════════════════
# Step4: トークン化・展開
# ════════════════════════════════════════════════════════

def _expand_goals(goal: dict) -> list[dict]:
    """L1/L2/L3 の目的文を展開し、element_id 付き要素リストを返す。"""
    try:
        elements: list[dict] = []
        counter = 1

        # L1: 1要素として展開
        elements.append({
            "element_id": f"E{counter}",
            "text": goal["L1"].strip(),
            "parent": "L1",
        })
        counter += 1

        # L2: 各項目を展開
        for text in goal["L2"]:
            if isinstance(text, str) and text.strip():
                elements.append({
                    "element_id": f"E{counter}",
                    "text": text.strip(),
                    "parent": "L2",
                })
                counter += 1

        # L3: 各項目を展開
        for text in goal["L3"]:
            if isinstance(text, str) and text.strip():
                elements.append({
                    "element_id": f"E{counter}",
                    "text": text.strip(),
                    "parent": "L3",
                })
                counter += 1

        return elements

    except Exception as exc:
        wrapped = RuntimeError("目的展開処理（トークン化）に失敗しました")
        wrapped.__cause__ = exc
        raise wrapped from exc


# ════════════════════════════════════════════════════════
# Step5: 整合性検証
# ════════════════════════════════════════════════════════

def _validate_elements(elements: list[dict]) -> None:
    """展開要素の整合性を検証し、問題は WARNING で記録（処理継続）。"""
    seen_ids: set[str] = set()
    for elem in elements:
        eid = elem.get("element_id", "")
        if eid in seen_ids:
            log.warning("重複 element_id を検出: '%s'", eid)
        seen_ids.add(eid)

        parent = elem.get("parent", "")
        if parent not in VALID_PARENTS:
            log.warning(
                "不正な parent 値を検出: element_id='%s' parent='%s'", eid, parent
            )


# ════════════════════════════════════════════════════════
# Step6: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f20_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F20 モジュールの統一インターフェース。

    F10 の出力（goal.L1/L2/L3）を受け取り、
    element_id 付きの展開要素リストを返す。

    Args:
        input_data (dict): F10 の出力形式（goal.L1/L2/L3 + trace_id）

    Returns:
        dict: {
            "trace_id": "F20",
            "source_trace_id": str,
            "expanded_goals": list[dict],
            "hitl": bool
        }

    Raises:
        TypeError:    input_data が dict 以外
        ValueError:   goal / goal.L1/L2/L3 の欠落・型不正
        RuntimeError: トークン化処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    goal = _validate_input(input_data)
    source_trace = input_data.get("trace_id", "")

    # Step2: HITL 移譲判定
    hitl_reason = _check_hitl(goal)
    if hitl_reason:
        log.warning("[HITL移譲] %s", hitl_reason)
        return {
            "trace_id": "F20",
            "source_trace_id": source_trace,
            "expanded_goals": [],
            "hitl": True,
            "hitl_reason": hitl_reason,
        }

    # Step3: 前処理
    _preprocess(input_data, goal)

    # Step4: トークン化・展開
    elements = _expand_goals(goal)

    # Step5: 整合性検証
    _validate_elements(elements)

    output = {
        "trace_id": "F20",
        "source_trace_id": source_trace,
        "expanded_goals": elements,
        "hitl": False,
    }

    # Step6: 保存・ログ
    saved = _save_output(output)
    log.info(
        "[F20] 処理完了 | 展開要素数=%d | 保存: %s",
        len(elements), saved,
    )
    return output
