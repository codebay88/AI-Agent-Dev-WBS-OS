"""F60_MECE_Validation_Module
Traceability: WP7400
前提モジュール: F50_Template_Application_Module
参照仕様: docs/F_series_overview.md, docs/F60_Module.md

cosine 類似度は stdlib のみで実装（外部 NLP ライブラリ不使用）。
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
VALID_PRIORITIES   = {"High", "Medium", "Low"}
REQUIRED_FIELDS    = ("task_id", "templated_text", "priority")
ABSTRACT_WORDS     = ["改善", "向上", "検討", "最適化", "強化", "推進", "活性化"]

DUPLICATE_THRESHOLD   = 0.85   # cosine > 0.85 → duplicate
UNCERTAIN_LOW         = 0.80   # 0.80 ≤ sim ≤ 0.85 → HITL（不確定域）
UNCERTAIN_HIGH        = 0.85


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
    """trace_id チェック・空リスト・重複・不正 priority の WARNING。
    空リストの場合は True（HITL 移譲要）を返す。"""
    source = input_data.get("trace_id", "")
    if source != "F50":
        log.warning("想定外の source trace_id: '%s'（F50 を期待）。処理は継続します。", source)

    if not tasks:
        log.warning("'templated_tasks' が空リストです。検証対象がありません。")
        return True

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
# 類似度計算ユーティリティ（stdlib のみ）
# ════════════════════════════════════════════════════════

def _tokenize(text: str) -> list[str]:
    """テキストを単語トークンのリストに分解する（句読点除去）。"""
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
# Step3: 重複検出
# ════════════════════════════════════════════════════════

def _detect_duplicates(tasks: list) -> tuple[list[str], list[str]]:
    """重複タスクを検出し (duplicate_task_ids, uncertain_task_ids) を返す。"""
    duplicate_ids: set[str] = set()
    uncertain_ids: set[str] = set()

    # 同一 element_id による重複
    seen_element: dict[str, str] = {}
    for task in tasks:
        eid = task.get("element_id")
        tid = task["task_id"]
        if eid is not None:
            if eid in seen_element:
                duplicate_ids.add(tid)
                duplicate_ids.add(seen_element[eid])
            else:
                seen_element[eid] = tid

    # cosine 類似度による重複
    n = len(tasks)
    for i in range(n):
        for j in range(i + 1, n):
            tid_i = tasks[i]["task_id"]
            tid_j = tasks[j]["task_id"]
            try:
                sim = _cosine_similarity(tasks[i]["templated_text"], tasks[j]["templated_text"])
            except RuntimeError:
                raise
            except Exception as exc:
                wrapped = RuntimeError(
                    f"類似度計算に失敗しました（{tid_i} vs {tid_j}）"
                )
                wrapped.__cause__ = exc
                raise wrapped from exc

            if sim > DUPLICATE_THRESHOLD:
                duplicate_ids.add(tid_i)
                duplicate_ids.add(tid_j)
            elif UNCERTAIN_LOW <= sim <= UNCERTAIN_HIGH:
                uncertain_ids.add(tid_i)
                uncertain_ids.add(tid_j)

    # uncertain のうち duplicate に昇格したものは除外
    uncertain_ids -= duplicate_ids
    return sorted(duplicate_ids), sorted(uncertain_ids)


# ════════════════════════════════════════════════════════
# Step4: 抜け漏れ検出
# ════════════════════════════════════════════════════════

def _detect_missing(tasks: list) -> list[str]:
    """element_id の欠番を検出して missing_elements リストを返す。
    tasks に element_id が存在しない場合は空リストを返す。"""
    element_ids = [t.get("element_id") for t in tasks if t.get("element_id")]
    if not element_ids:
        return []

    # "E1", "E2", ... 形式の連番チェック
    nums: list[int] = []
    for eid in element_ids:
        m = re.match(r"^E(\d+)$", eid)
        if m:
            nums.append(int(m.group(1)))

    if not nums:
        return []

    full_range = set(range(min(nums), max(nums) + 1))
    missing    = sorted(full_range - set(nums))
    return [f"E{n}" for n in missing]


# ════════════════════════════════════════════════════════
# Step5: 曖昧検出
# ════════════════════════════════════════════════════════

def _detect_ambiguous(tasks: list) -> list[str]:
    """templated_text に抽象語が含まれるタスクの task_id リストを返す。"""
    result: list[str] = []
    for task in tasks:
        text = task.get("templated_text", "")
        for word in ABSTRACT_WORDS:
            if word in text:
                result.append(task["task_id"])
                break
    return result


# ════════════════════════════════════════════════════════
# Step6: MECE 判定
# ════════════════════════════════════════════════════════

def _build_mece_report(
    duplicate_tasks: list[str],
    missing_elements: list[str],
    ambiguous_tasks: list[str],
) -> dict:
    is_compliant = not (duplicate_tasks or missing_elements or ambiguous_tasks)
    return {
        "duplicate_tasks":  duplicate_tasks,
        "missing_elements": missing_elements,
        "ambiguous_tasks":  ambiguous_tasks,
        "is_mece_compliant": is_compliant,
    }


# ════════════════════════════════════════════════════════
# Step7: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f60_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F60 モジュールの統一インターフェース。

    Args:
        input_data (dict): F50 の出力形式（templated_tasks + trace_id）

    Returns:
        dict: {
            "trace_id": "F60",
            "source_trace_id": str,
            "mece_report": {
                "duplicate_tasks": list[str],
                "missing_elements": list[str],
                "ambiguous_tasks": list[str],
                "is_mece_compliant": bool
            },
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
            "trace_id":        "F60",
            "source_trace_id": source_trace,
            "mece_report": {
                "duplicate_tasks":   [],
                "missing_elements":  [],
                "ambiguous_tasks":   [],
                "is_mece_compliant": False,
            },
            "hitl":          True,
            "hitl_required": True,
            "hitl_elements": [],
            "hitl_reason":   "No tasks provided",
        }
        _save_output(output)
        return output

    # Step3: 重複検出
    duplicate_tasks, uncertain_ids = _detect_duplicates(tasks)

    # Step4: 抜け漏れ検出
    missing_elements = _detect_missing(tasks)

    # Step5: 曖昧検出
    ambiguous_tasks = _detect_ambiguous(tasks)

    # Step6: MECE 判定
    mece_report = _build_mece_report(duplicate_tasks, missing_elements, ambiguous_tasks)

    # HITL 判定
    hitl_required = (
        bool(uncertain_ids)
        or (not mece_report["is_mece_compliant"] and bool(ambiguous_tasks))
    )
    hitl_elements = list(uncertain_ids)

    output = {
        "trace_id":          "F60",
        "source_trace_id":   source_trace,
        "templated_tasks":   tasks,       # F70 へのパススルー
        "mece_report":       mece_report,
        "hitl":              hitl_required,
        "hitl_required":     hitl_required,
        "hitl_elements":     hitl_elements,
    }

    # Step7: 保存・ログ
    saved = _save_output(output)
    log.info(
        "[F60] MECE 検証完了 | compliant=%s | duplicates=%d | missing=%d | ambiguous=%d | 保存: %s",
        mece_report["is_mece_compliant"],
        len(duplicate_tasks), len(missing_elements), len(ambiguous_tasks), saved,
    )
    return output
