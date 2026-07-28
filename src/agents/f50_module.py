"""F50_Template_Application_Module
Traceability: WP7300
前提モジュール: F40_Task_Generation_Module
参照仕様: docs/F_series_overview.md, docs/F50_Module.md
"""

import json
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"

log = logging.getLogger(__name__)

# ── 定数 ───────────────────────────────────────────────
AMBIGUOUS_WORDS  = ["など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ",
                    "改善", "向上", "検討"]
VALID_PRIORITIES = {"High", "Medium", "Low"}
REQUIRED_FIELDS  = ("task_id", "task_text", "priority")

# テンプレート定義
_TEMPLATES = {
    "High":   ("TMP_HIGH",   "【優先度: 高】次のタスクを実行せよ: {task_text}"),
    "Medium": ("TMP_MEDIUM", "【優先度: 中】検討すべきタスク: {task_text}"),
    "Low":    ("TMP_LOW",    "【優先度: 低】参考タスク: {task_text}"),
}


# ════════════════════════════════════════════════════════
# Step1: 入力検証
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> list:
    """入力検証。正常なら tasks リストを返す。"""
    if not isinstance(input_data, dict):
        raise TypeError(
            f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）"
        )
    if not input_data:
        raise ValueError("input_data が空 dict です")
    if "tasks" not in input_data:
        raise ValueError("必須キー 'tasks' が存在しません")

    tasks = input_data["tasks"]
    if not isinstance(tasks, list):
        raise ValueError(
            f"'tasks' は list 型必須（受け取った型: {type(tasks).__name__}）"
        )

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TypeError(f"tasks[{i}] は dict 型必須")
        for field in REQUIRED_FIELDS:
            if field not in task:
                raise TypeError(
                    f"tasks[{i}] に必須フィールド '{field}' が存在しません"
                )

    return tasks


# ════════════════════════════════════════════════════════
# Step2: 前処理
# ════════════════════════════════════════════════════════

def _preprocess(input_data: dict, tasks: list) -> None:
    """trace_id チェック・空リスト・重複・不正 priority の WARNING。"""
    source = input_data.get("trace_id", "")
    if source != "F40":
        log.warning("想定外の source trace_id: '%s'（F40 を期待）。処理は継続します。", source)

    if not tasks:
        log.warning("'tasks' が空リストです。適用対象がありません。")
        return

    seen_ids: set[str] = set()
    for task in tasks:
        tid = task.get("task_id", "")
        if tid in seen_ids:
            log.warning("重複 task_id を検出: '%s'", tid)
        seen_ids.add(tid)

        pri = task.get("priority", "")
        if pri not in VALID_PRIORITIES:
            log.warning("不正な priority 値を検出: task_id='%s' priority='%s'", tid, pri)


# ════════════════════════════════════════════════════════
# Step3: HITL 移譲判定（要素単位）
# ════════════════════════════════════════════════════════

def _check_hitl_task(task: dict) -> str | None:
    """要素単位で HITL 移譲が必要か判定。問題があれば理由文字列を返す。"""
    text = task.get("task_text", "")

    if not isinstance(text, str) or not text.strip():
        return "Task text is empty or ambiguous"

    for word in AMBIGUOUS_WORDS:
        if word in text:
            return f"Task text is empty or ambiguous（曖昧語「{word}」を含む）"

    pri = task.get("priority", "")
    if pri not in VALID_PRIORITIES:
        return f"priority が判定不能です（値: '{pri}'）（HITL移譲）"

    return None


# ════════════════════════════════════════════════════════
# Step4: テンプレート適用
# ════════════════════════════════════════════════════════

def _apply_template(task: dict) -> dict:
    """1タスクにテンプレートを適用して返す。"""
    try:
        priority   = task["priority"]
        task_text  = task["task_text"]
        template_id, template_fmt = _TEMPLATES[priority]
        templated_text = template_fmt.format(task_text=task_text)

        return {
            "task_id":       task["task_id"],
            "template_id":   template_id,
            "templated_text": templated_text,
            "priority":      priority,
            "effort":        task.get("estimated_effort"),
            "value":         task.get("estimated_value"),
        }
    except Exception as exc:
        wrapped = RuntimeError(
            f"テンプレート適用処理に失敗しました（task_id='{task.get('task_id', '?')}'）"
        )
        wrapped.__cause__ = exc
        raise wrapped from exc


# ════════════════════════════════════════════════════════
# Step5: 整合性検証
# ════════════════════════════════════════════════════════

def _validate_templated(templated_tasks: list) -> None:
    """生成済みテンプレートタスクの整合性を検証し、問題は WARNING で記録（処理継続）。"""
    valid_template_ids = {"TMP_HIGH", "TMP_MEDIUM", "TMP_LOW"}
    for task in templated_tasks:
        tid = task.get("task_id", "?")

        tmpl_id = task.get("template_id", "")
        if tmpl_id not in valid_template_ids:
            log.warning("想定外の template_id: task_id='%s' template_id='%s'", tid, tmpl_id)

        text = task.get("templated_text", "")
        if not text or not text.strip():
            log.warning("templated_text が空です: task_id='%s'", tid)


# ════════════════════════════════════════════════════════
# Step6: 保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f50_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F50 モジュールの統一インターフェース。

    Args:
        input_data (dict): F40 の出力形式（tasks + trace_id）

    Returns:
        dict: {
            "trace_id": "F50",
            "source_trace_id": str,
            "templated_tasks": list[dict],
            "hitl": bool,
            "hitl_elements": list[str]
        }

    Raises:
        TypeError:    input_data が dict 以外、または各要素の必須フィールド欠落
        ValueError:   tasks の欠落・型不正
        RuntimeError: テンプレート適用処理の失敗（__cause__ 保持）
    """
    # Step1: 入力検証
    tasks        = _validate_input(input_data)
    source_trace = input_data.get("trace_id", "")

    # Step2: 前処理
    _preprocess(input_data, tasks)

    # Step3 & Step4: HITL 判定 + テンプレート適用
    templated_tasks: list[dict] = []
    hitl_elements:   list[str]  = []

    for task in tasks:
        hitl_reason = _check_hitl_task(task)
        if hitl_reason:
            log.warning(
                "[HITL移譲] task_id='%s' reason=%s", task.get("task_id"), hitl_reason
            )
            hitl_elements.append(task.get("task_id", ""))
            continue

        applied = _apply_template(task)
        templated_tasks.append(applied)

    # 全要素が HITL 移譲対象の場合
    all_hitl = bool(tasks) and len(hitl_elements) == len(tasks)

    # Step5: 整合性検証
    _validate_templated(templated_tasks)

    output = {
        "trace_id":        "F50",
        "source_trace_id": source_trace,
        "templated_tasks": templated_tasks,
        "hitl":            all_hitl,
        "hitl_elements":   hitl_elements,
    }

    # Step6: 保存・ログ
    saved = _save_output(output)
    log.info(
        "[F50] 処理完了 | 適用タスク数=%d | HITL移譲=%d件 | 保存: %s",
        len(templated_tasks), len(hitl_elements), saved,
    )
    return output
