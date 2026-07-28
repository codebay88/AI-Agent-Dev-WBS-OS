"""F70_Hierarchy_Generation_Module
Traceability: WP7500
前提モジュール: F60_MECE_Validation_Module
参照仕様: docs/F_series_overview.md, docs/F70_Module.md

階層生成ロジックは stdlib のみで実装。
cosine 類似度 + Union-Find によるゴールグループ化。
"""

import json
import logging
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

# ── 定数 ───────────────────────────────────────────────
VALID_PRIORITIES    = {"High", "Medium", "Low"}
REQUIRED_FIELDS     = ("task_id", "templated_text", "priority")
ABSTRACT_WORDS      = ["改善", "向上", "検討", "最適化", "強化", "推進", "活性化"]
GOAL_SIM_THRESHOLD  = 0.80          # これ以上の cosine → 同一 goal にグループ化
PRIORITY_ORDER      = {"High": 0, "Medium": 1, "Low": 2}
PRIORITY_SUFFIX     = {"High": "EL_H", "Medium": "EL_M", "Low": "EL_L"}
PRIORITY_LABEL      = {"High": "High", "Medium": "Medium", "Low": "Low"}


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> list:
    """入力検証。正常なら templated_tasks リストを返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")
    if "templated_tasks" not in input_data:
        raise ValueError("必須キー 'templated_tasks' が存在しません")

    tasks = input_data["templated_tasks"]
    if not isinstance(tasks, list):
        raise ValueError(
            f"'templated_tasks' は list 型必須（受け取った型: {type(tasks).__name__}）"
        )

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TypeError(f"templated_tasks[{i}] は dict 型必須")
        for field in REQUIRED_FIELDS:
            if field not in task:
                raise TypeError(
                    f"templated_tasks[{i}] に必須フィールド '{field}' が存在しません"
                )

    return tasks


# ════════════════════════════════════════════════════════
# Step2: 前処理
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, tasks: list) -> bool:
    """trace_id・重複・不正 priority の WARNING 出力。
    空リストの場合は True（HITL 移譲要）を返す。"""
    source = input_data.get("trace_id", "")
    if source != "F60":
        log.warning("想定外の source trace_id: '%s'（F60 を期待）。処理は継続します。", source)

    if not tasks:
        log.warning("'templated_tasks' が空リストです。階層生成対象がありません。")
        return True

    # MECE 非準拠の WARNING
    mece = input_data.get("mece_report", {})
    if isinstance(mece, dict) and not mece.get("is_mece_compliant", True):
        log.warning("MECE 非準拠の入力を受け取りました。階層整合性に影響する可能性があります。")

    seen_ids: set[str] = set()
    for task in tasks:
        tid = task.get("task_id", "")
        if tid in seen_ids:
            log.warning("重複 task_id を検出: '%s'", tid)
        seen_ids.add(tid)

        pri = task.get("priority", "")
        if pri not in VALID_PRIORITIES:
            log.warning("不正な priority 値を検出: task_id='%s' priority='%s'", tid, pri)

    return False


# ════════════════════════════════════════════════════════
# cosine 類似度ユーティリティ（stdlib のみ）
# ════════════════════════════════════════════════════════

def _tokenize(text: str) -> list[str]:
    """テキストを単語トークンのリストに分解する。"""
    return re.findall(r"[^\s　、。！？「」【】：:]+", text)


def _cosine_similarity(text_a: str, text_b: str) -> float:
    """2テキスト間の cosine 類似度を単語 Counter ベクトルで算出する（0.0〜1.0）。"""
    try:
        vec_a = Counter(_tokenize(text_a))
        vec_b = Counter(_tokenize(text_b))
        keys   = set(vec_a) | set(vec_b)
        dot    = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in keys)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
    except Exception as exc:
        wrapped = RuntimeError("cosine 類似度の計算に失敗しました")
        wrapped.__cause__ = exc
        raise wrapped from exc


# ════════════════════════════════════════════════════════
# Step3: 目的（Goal）グループ化
# ════════════════════════════════════════════════════════

def _union_find_group(tasks: list[dict]) -> list[list[dict]]:
    """Union-Find で cosine > GOAL_SIM_THRESHOLD のタスクをグループ化する。"""
    n = len(tasks)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            try:
                sim = _cosine_similarity(
                    tasks[i]["templated_text"], tasks[j]["templated_text"]
                )
            except RuntimeError:
                raise
            except Exception as exc:
                wrapped = RuntimeError(
                    f"類似度計算に失敗しました（{tasks[i]['task_id']} vs {tasks[j]['task_id']}）"
                )
                wrapped.__cause__ = exc
                raise wrapped from exc
            if sim > GOAL_SIM_THRESHOLD:
                union(i, j)

    groups: dict[int, list[dict]] = {}
    for i, task in enumerate(tasks):
        root = find(i)
        groups.setdefault(root, []).append(task)

    # priority 順でソート
    for group in groups.values():
        group.sort(key=lambda t: PRIORITY_ORDER.get(t.get("priority", ""), 99))

    return list(groups.values())


def _strip_priority_prefix(text: str) -> str:
    """優先度プレフィックスを除去してタスク本文を返す（最後のコロン以降を取得）。"""
    for sep in ["：", ":"]:
        if sep in text:
            return text.rsplit(sep, 1)[-1].strip()
    return text.strip()


def _extract_goal_text(tasks: list[dict]) -> str:
    """グループのタスクから共通トークンを抽出して目的テキストを生成する。"""
    if not tasks:
        return ""
    if len(tasks) == 1:
        return _strip_priority_prefix(tasks[0]["templated_text"])

    token_lists = [_tokenize(t["templated_text"]) for t in tasks]
    counter: Counter = Counter()
    for tokens in token_lists:
        counter.update(set(tokens))  # 各タスクで1回だけカウント

    # ≥2 タスクに出現するトークン（上位5個）
    common = [tok for tok, cnt in counter.most_common() if cnt >= 2]
    if common:
        return " ".join(common[:5])

    # fallback: 最初のタスクのプレフィックス除去テキスト
    return _strip_priority_prefix(tasks[0]["templated_text"])


def _is_only_abstract(text: str) -> bool:
    """テキストが ABSTRACT_WORDS のみで構成されているか判定する。"""
    tokens = _tokenize(text)
    if not tokens:
        return True
    return all(tok in ABSTRACT_WORDS for tok in tokens)


# ════════════════════════════════════════════════════════
# Step4: 要素（Element）グループ化
# ════════════════════════════════════════════════════════

def _group_by_element(goal_id: str, tasks: list[dict]) -> list[dict]:
    """priority でタスクをグループ化して element リストを返す。"""
    pri_groups: dict[str, list[dict]] = {}
    for task in tasks:
        pri = task.get("priority", "Unknown")
        pri_groups.setdefault(pri, []).append(task)

    elements = []
    # priority 順（High → Medium → Low → Unknown）
    order = {**{k: v for k, v in PRIORITY_ORDER.items()}, "Unknown": 99}
    for pri in sorted(pri_groups.keys(), key=lambda p: order.get(p, 99)):
        suffix       = PRIORITY_SUFFIX.get(pri, f"EL_{pri}")
        element_id   = f"{goal_id}_{suffix}"
        label        = PRIORITY_LABEL.get(pri, pri)
        element_text = f"{label}優先度タスク群"
        tasks_in_elem = [
            {
                "task_id":       t["task_id"],
                "templated_text": t["templated_text"],
                "priority":      t.get("priority", ""),
                "effort":        t.get("effort"),
                "value":         t.get("value"),
            }
            for t in pri_groups[pri]
        ]
        elements.append({
            "element_id":   element_id,
            "element_text": element_text,
            "tasks":        tasks_in_elem,
        })
    return elements


# ════════════════════════════════════════════════════════
# Step5: 整合性検証
# ════════════════════════════════════════════════════════

def _validate_hierarchy(goals: list[dict], hitl_elements: list[str]) -> None:
    """各 goal の element / task 存在を検証し、違反があれば WARNING + hitl_elements 追加。"""
    for goal in goals:
        gid      = goal["goal_id"]
        elements = goal.get("elements", [])
        if not elements:
            log.warning("goal '%s' に element が存在しません。", gid)
            hitl_elements.append(gid)
            continue
        for elem in elements:
            eid   = elem["element_id"]
            tasks = elem.get("tasks", [])
            if not tasks:
                log.warning("element '%s' に task が存在しません。", eid)
                hitl_elements.append(eid)


# ════════════════════════════════════════════════════════
# Step7: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f70_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F70 モジュールの統一インターフェース。

    Args:
        input_data (dict): F60 の出力形式（templated_tasks + mece_report + trace_id）

    Returns:
        dict: {
            "trace_id": "F70",
            "source_trace_id": str,
            "hierarchy": {"goals": list[dict]},
            "hitl": bool,
            "hitl_required": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または各要素の必須フィールド欠落
        ValueError:   templated_tasks の欠落・型不正
        RuntimeError: 類似度計算処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    tasks        = _validate_input(input_data)
    source_trace = input_data.get("trace_id", "")

    # Step2: 前処理（空リストなら HITL 移譲）
    empty_hitl = _preprocess(input_data, tasks)
    if empty_hitl:
        output = {
            "trace_id":        "F70",
            "source_trace_id": source_trace,
            "hierarchy":       {"goals": []},
            "hitl":            True,
            "hitl_required":   True,
            "hitl_elements":   [],
            "hitl_reason":     "No hierarchy generated",
        }
        _save_output(output)
        return output

    hitl_elements: list[str] = []

    # Step3: Goal グループ化
    groups = _union_find_group(tasks)
    goals  = []
    for idx, group in enumerate(groups, start=1):
        goal_id   = f"G{idx}"
        goal_text = _extract_goal_text(group)

        # 抽象語のみの goal_text → HITL
        if _is_only_abstract(goal_text):
            log.warning("goal '%s' の goal_text が抽象語のみです: '%s'", goal_id, goal_text)
            hitl_elements.append(goal_id)

        # Step4: Element グループ化
        elements = _group_by_element(goal_id, group)

        # element_text の重複チェック
        seen_texts: set[str] = set()
        for elem in elements:
            et = elem["element_text"]
            if et in seen_texts:
                log.warning("element_text が重複しています: '%s'", et)
                hitl_elements.append(elem["element_id"])
            seen_texts.add(et)

        goals.append({
            "goal_id":   goal_id,
            "goal_text": goal_text,
            "elements":  elements,
        })

    # Step5: 整合性検証
    _validate_hierarchy(goals, hitl_elements)

    # Step6: HITL 判定
    hitl_required = bool(hitl_elements)

    # 集計ログ用
    total_elements = sum(len(g["elements"]) for g in goals)
    total_tasks    = sum(
        len(e["tasks"]) for g in goals for e in g["elements"]
    )

    output = {
        "trace_id":        "F70",
        "source_trace_id": source_trace,
        "hierarchy":       {"goals": goals},
        "hitl":            hitl_required,
        "hitl_required":   hitl_required,
        "hitl_elements":   sorted(set(hitl_elements)),
    }

    saved = _save_output(output)
    log.info(
        "[F70] 階層生成完了 | goals=%d | elements=%d | tasks=%d | HITL=%s | 保存: %s",
        len(goals), total_elements, total_tasks, hitl_required, saved,
    )
    return output
