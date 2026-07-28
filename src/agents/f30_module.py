"""F30_Goal_Element_Evaluator
Traceability: WP7200
前提モジュール: F20_Goal_Expansion_Module
"""

import json
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

# ── 定数 ───────────────────────────────────────────────
AMBIGUOUS_WORDS  = ["など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"]
ABSTRACT_WORDS   = ["改善", "向上", "最適化", "強化", "推進", "促進", "活性化", "充実"]
ACTION_VERBS     = ["作成する", "実行する", "配信する", "設計する", "導入する",
                    "構築する", "開発する", "運用する", "分析する", "提案する"]
VALID_PARENTS    = {"L1", "L2", "L3"}
VALID_PRIORITIES = {"High", "Medium", "Low"}

# importance 基礎スコア（parent 別）
_IMPORTANCE_BASE = {"L1": 0.85, "L2": 0.60, "L3": 0.40}
# feasibility 基礎スコア（parent 別）
_FEASIBILITY_BASE = {"L1": 0.50, "L2": 0.65, "L3": 0.85}


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> list:
    """入力検証。正常なら expanded_goals リストを返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")
    if "expanded_goals" not in input_data:
        raise ValueError("必須キー 'expanded_goals' が存在しません")

    goals = input_data["expanded_goals"]
    if not isinstance(goals, list):
        raise ValueError(
            f"'expanded_goals' は list 型必須（受け取った型: {type(goals).__name__}）"
        )

    for i, elem in enumerate(goals):
        if not isinstance(elem, dict):
            raise ValueError(f"expanded_goals[{i}] は dict 型必須")
        for field in ("element_id", "text", "parent"):
            if field not in elem:
                raise ValueError(
                    f"expanded_goals[{i}] に必須フィールド '{field}' が存在しません"
                )

    return goals


# ════════════════════════════════════════════════════════
# Step2: 前処理
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, goals: list) -> None:
    """trace_id チェック・空リスト・重複 element_id の WARNING。"""
    source_trace = input_data.get("trace_id", "")
    if source_trace != "F20":
        log.warning(
            "想定外の source trace_id: '%s'（F20 を期待）。処理は継続します。", source_trace
        )

    if not goals:
        log.warning("'expanded_goals' が空リストです。評価対象がありません。")
        return

    seen: set[str] = set()
    for elem in goals:
        eid = elem.get("element_id", "")
        if eid in seen:
            log.warning("重複 element_id を検出: '%s'", eid)
        seen.add(eid)


# ════════════════════════════════════════════════════════
# Step3: HITL 移譲判定（要素単位）
# ════════════════════════════════════════════════════════

def _check_hitl_element(elem: dict) -> str | None:
    """要素単位で HITL 移譲が必要か判定。問題があれば理由文字列を返す。"""
    text = elem.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return "Goal element text is empty"
    for word in AMBIGUOUS_WORDS:
        if word in text:
            return f"曖昧語「{word}」を含むため評価が困難です（HITL移譲）"
    return None


# ════════════════════════════════════════════════════════
# Step4: スコア算出
# ════════════════════════════════════════════════════════

def _score_importance(text: str, parent: str) -> float:
    """重要度スコアを算出する（0.0〜1.0）。"""
    score = _IMPORTANCE_BASE.get(parent, 0.50)

    # 具体性ボーナス: 数値・比率表現を含む場合
    import re
    if re.search(r"\d+[%倍割]", text):
        score += 0.10

    # 抽象性ペナルティ: 抽象語のみで構成される場合
    words_in_text = [w for w in ABSTRACT_WORDS if w in text]
    if words_in_text and len(text) <= 10:
        score -= 0.10

    return max(0.0, min(1.0, round(score, 4)))


def _score_feasibility(text: str, parent: str) -> float:
    """実現可能性スコアを算出する（0.0〜1.0）。"""
    score = _FEASIBILITY_BASE.get(parent, 0.60)

    # 実行可能性ボーナス: 動作動詞を含む場合
    if any(verb in text for verb in ACTION_VERBS):
        score += 0.10

    # 粒度不足ペナルティ: テキストが短すぎる場合
    if len(text.strip()) <= 5:
        score -= 0.10

    return max(0.0, min(1.0, round(score, 4)))


def _classify_priority(importance: float, feasibility: float) -> str:
    """スコア平均に基づき priority を分類する。"""
    avg = (importance + feasibility) / 2
    if avg >= 0.70:
        return "High"
    if avg >= 0.50:
        return "Medium"
    return "Low"


def _evaluate_element(elem: dict) -> dict:
    """1要素を評価し、スコアと priority を付与した dict を返す。"""
    try:
        text   = elem["text"]
        parent = elem["parent"]
        imp  = _score_importance(text, parent)
        feas = _score_feasibility(text, parent)
        pri  = _classify_priority(imp, feas)
        return {
            "element_id":        elem["element_id"],
            "text":              text,
            "parent":            parent,
            "score_importance":  imp,
            "score_feasibility": feas,
            "priority":          pri,
        }
    except Exception as exc:
        wrapped = RuntimeError(
            f"スコア算出処理に失敗しました（element_id='{elem.get('element_id', '?')}'）"
        )
        wrapped.__cause__ = exc
        raise wrapped from exc


# ════════════════════════════════════════════════════════
# Step5: 整合性検証
# ════════════════════════════════════════════════════════

def _validate_evaluated(evaluated: list) -> None:
    """評価結果の整合性を検証し、問題は WARNING で記録（処理継続）。"""
    for elem in evaluated:
        eid = elem.get("element_id", "?")

        for score_key in ("score_importance", "score_feasibility"):
            val = elem.get(score_key)
            if val is None or not (0.0 <= val <= 1.0):
                log.warning(
                    "スコア範囲外を検出: element_id='%s' %s=%s", eid, score_key, val
                )

        pri = elem.get("priority", "")
        if pri not in VALID_PRIORITIES:
            log.warning("不正な priority 値を検出: element_id='%s' priority='%s'", eid, pri)

        par = elem.get("parent", "")
        if par not in VALID_PARENTS:
            log.warning("不正な parent 値を検出: element_id='%s' parent='%s'", eid, par)


# ════════════════════════════════════════════════════════
# Step6: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f30_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F30 モジュールの統一インターフェース。

    F20 の出力（expanded_goals）を受け取り、
    各要素にスコアと priority を付与した evaluated_goals を返す。

    Args:
        input_data (dict): F20 の出力形式（expanded_goals + trace_id）

    Returns:
        dict: {
            "trace_id": "F30",
            "source_trace_id": str,
            "evaluated_goals": list[dict],
            "hitl": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外
        ValueError:   expanded_goals の欠落・型不正 / 必須フィールド欠落
        RuntimeError: スコア算出処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    goals        = _validate_input(input_data)
    source_trace = input_data.get("trace_id", "")

    # Step2: 前処理
    _preprocess(input_data, goals)

    # Step3 & Step4: HITL 判定 + スコア算出
    evaluated:    list[dict] = []
    hitl_elements: list[str] = []

    for elem in goals:
        hitl_reason = _check_hitl_element(elem)
        if hitl_reason:
            log.warning("[HITL移譲] element_id='%s' reason=%s", elem.get("element_id"), hitl_reason)
            hitl_elements.append(elem.get("element_id", ""))
            continue
        evaluated.append(_evaluate_element(elem))

    # 全要素が HITL 移譲対象の場合
    all_hitl = bool(goals) and len(hitl_elements) == len(goals)

    # Step5: 整合性検証
    _validate_evaluated(evaluated)

    output = {
        "trace_id":        "F30",
        "source_trace_id": source_trace,
        "evaluated_goals": evaluated,
        "hitl":            all_hitl,
        "hitl_elements":   hitl_elements,
    }

    # Step6: 保存・ログ
    saved = _save_output(output)
    log.info(
        "[F30] 処理完了 | 評価要素数=%d | HITL移譲=%d件 | 保存: %s",
        len(evaluated), len(hitl_elements), saved,
    )
    return output
