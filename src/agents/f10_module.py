"""F10_Objective_Structuring_Module
Traceability: WP7000 / WP7100 / WP7200
"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

log = logging.getLogger(__name__)

PROMPT_PATH = BASE_DIR / "src" / "prompts" / "f10_system.txt"
OUTPUT_DIR = BASE_DIR / "data" / "output"

# ── 定数 ───────────────────────────────────────────────
AMBIGUOUS_WORDS = ["など", "いろいろ", "何か", "なんか", "とか", "色々", "諸々", "もろもろ"]
ABSTRACT_WORDS = ["改善", "向上", "最適化", "強化", "推進", "促進", "活性化", "充実"]
MAX_RETRY = 3
RETRY_DELAYS = [1, 2]  # 初回失敗後1秒、2回目失敗後2秒


# ════════════════════════════════════════════════════════
# Step2: Interface — 入力検証・HITL判定
# ════════════════════════════════════════════════════════

def _validate_input(input_data) -> str:
    """入力検証。正常なら goal_text を返す。"""
    if input_data is None or input_data == {}:
        raise ValueError("input_data は dict 形式必須（None および {} は不可）")
    if not isinstance(input_data, dict):
        raise ValueError(f"input_data は dict 型必須（受け取った型: {type(input_data).__name__}）")
    if "goal_text" not in input_data:
        raise ValueError("必須項目 'goal_text' が存在しません")
    goal_text = input_data["goal_text"]
    if not isinstance(goal_text, str) or goal_text.strip() == "":
        raise ValueError("goal_text は空文字列不可")
    return goal_text.strip()


def _check_hitl_conditions(goal_text: str) -> str | None:
    """HITL移譲が必要な条件を検出。問題があれば理由文字列を返す。"""
    for word in AMBIGUOUS_WORDS:
        if word in goal_text:
            return f"曖昧語「{word}」を含むため構造化が困難です（HITL移譲）"
    if len(goal_text) < 10:
        return f"目的文が短すぎ（{len(goal_text)}文字）、粒度不足のため構造化不可（HITL移譲）"
    return None


# ════════════════════════════════════════════════════════
# Step4: Logic — プロンプト生成・API呼出・ツリー構築・整合性検証
# ════════════════════════════════════════════════════════

def _load_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"プロンプトファイルが見つかりません: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def _call_api(system_prompt: str, goal_text: str) -> str:
    """Claude API を呼び出し、レスポンステキストを返す（リトライなし）。"""
    import anthropic
    import os
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": goal_text}],
    )
    return message.content[0].text


def _call_api_with_retry(system_prompt: str, goal_text: str) -> str:
    """最大3回（初回＋再試行2回）API を呼び出す。すべて失敗で RuntimeError。

    修正（バグ修正）: 従来は `_call_api` が JSONDecodeError を送出することがない
    ため、応答が不正な JSON だった場合にリトライされずに一度で失敗していた。
    ここで応答の JSON 妥当性を検証し、不正な場合もリトライ対象に含める。
    （厳密なキー検証・構造検証は従来どおり `_parse_response` が担う）
    """
    import anthropic

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRY):
        try:
            raw = _call_api(system_prompt, goal_text)
            json.loads(raw)  # 妥当な JSON かどうかのみ検証（リトライ判定用）
            return raw
        except anthropic.APIError as exc:
            last_exc = exc
            log.warning("API呼び出し失敗 (%d/%d): %s", attempt + 1, MAX_RETRY, exc)
        except json.JSONDecodeError as exc:
            wrapped = RuntimeError(f"JSON パース失敗（試行 {attempt + 1}/{MAX_RETRY}）")
            wrapped.__cause__ = exc
            last_exc = wrapped
            log.warning("JSONDecodeError (%d/%d): %s", attempt + 1, MAX_RETRY, exc)

        if attempt < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[attempt])

    raise RuntimeError(f"API呼び出しが {MAX_RETRY} 回失敗しました") from last_exc


def _parse_response(raw: str) -> dict:
    """API レスポンスを JSON として解析し、L1/L2/L3 キーを検証する。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        wrapped = RuntimeError("API レスポンスの JSON パースに失敗しました")
        wrapped.__cause__ = exc
        raise wrapped from exc

    for key in ("L1", "L2", "L3"):
        if key not in data:
            raise ValueError(f"API レスポンスに必須キー '{key}' がありません: {data}")
    if not isinstance(data["L1"], str):
        raise ValueError("L1 は str 型必須")
    for key in ("L2", "L3"):
        if not isinstance(data[key], list):
            raise ValueError(f"{key} は list 型必須")
    return data


def _build_tree(parsed: dict) -> dict:
    """フラットな L1/L2/L3 からツリー構造（objective_id / parent_id / children）を生成する。"""
    l1_id = f"L1-{uuid.uuid4().hex[:6]}"
    l1_node = {
        "objective_id": l1_id,
        "objective_text": parsed["L1"],
        "level": "L1",
        "parent_id": None,
        "children": [],
    }

    l2_nodes = []
    for i, text in enumerate(parsed["L2"]):
        nid = f"L2-{uuid.uuid4().hex[:6]}"
        l2_nodes.append({
            "objective_id": nid,
            "objective_text": text,
            "level": "L2",
            "parent_id": l1_id,
            "children": [],
        })

    # L3 を L2 に均等に配分
    l3_texts = parsed["L3"]
    l2_count = len(l2_nodes) if l2_nodes else 1
    for i, text in enumerate(l3_texts):
        parent_l2 = l2_nodes[i % l2_count]
        l3_node = {
            "objective_id": f"L3-{uuid.uuid4().hex[:6]}",
            "objective_text": text,
            "level": "L3",
            "parent_id": parent_l2["objective_id"],
            "children": [],
        }
        parent_l2["children"].append(l3_node)

    for node in l2_nodes:
        l1_node["children"].append(node)

    return {l1_id: l1_node}


def _validate_tree(tree: dict) -> None:
    """ツリーの整合性を検証し、問題は WARNING ログで記録（処理継続）。"""
    all_ids: dict[str, dict] = {}

    def _collect(node: dict):
        nid = node["objective_id"]
        if nid in all_ids:
            log.warning("重複 objective_id を検出: %s", nid)
        all_ids[nid] = node
        for child in node.get("children", []):
            _collect(child)

    for root in tree.values():
        _collect(root)

    for nid, node in all_ids.items():
        pid = node.get("parent_id")
        if pid is not None and pid not in all_ids:
            log.warning("親子不整合（孤立ノード）を検出: id=%s parent_id=%s", nid, pid)

    # 抽象語検出：L2/L3 生成文に抽象語が残る場合は WARNING
    def _check_abstract(node: dict):
        for word in ABSTRACT_WORDS:
            if word in node["objective_text"] and node["level"] == "L3":
                log.warning("L3 に抽象語「%s」を検出: '%s'", word, node["objective_text"])
        for child in node.get("children", []):
            _check_abstract(child)

    for root in tree.values():
        _check_abstract(root)


# ════════════════════════════════════════════════════════
# Step6: Error Handling — ラッパ・保存
# ════════════════════════════════════════════════════════

def _save_output(output: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"f10_result_{ts}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════

def execute(input_data) -> dict:
    """F10 モジュールの統一インターフェース。

    Args:
        input_data (dict): {"goal_text": str}

    Returns:
        dict: {
            "trace_id": "F10",
            "goal": {"L1": str, "L2": list[str], "L3": list[str]},
            "tree": {objective_id: {..., "children": [...]}},
        }

    Raises:
        ValueError: 入力不正（None / {} / 空文字列 / キー欠落 / 型不正）
        RuntimeError: API 3回失敗 / JSON パース失敗
        FileNotFoundError: プロンプトファイル不在
    """
    # Step2: 入力検証
    goal_text = _validate_input(input_data)

    # Step2: HITL 移譲判定
    hitl_reason = _check_hitl_conditions(goal_text)
    if hitl_reason:
        log.warning("[HITL移譲] %s", hitl_reason)
        return {
            "trace_id": "F10",
            "hitl": True,
            "hitl_reason": hitl_reason,
            "goal": None,
            "tree": None,
        }

    # Step3: プロンプト読込
    system_prompt = _load_prompt()

    # Step4: API呼出（リトライ込み）→ パース → ツリー構築
    raw = _call_api_with_retry(system_prompt, goal_text)
    parsed = _parse_response(raw)
    tree = _build_tree(parsed)

    # Step5: 整合性検証（WARNING のみ、処理継続）
    _validate_tree(tree)

    output = {
        "trace_id": "F10",
        "hitl": False,
        "goal": {
            "L1": parsed["L1"],
            "L2": parsed["L2"],
            "L3": parsed["L3"],
        },
        "tree": tree,
    }

    # Step8: 保存・ログ
    saved = _save_output(output)
    log.info(
        "[F10] 処理完了 | L1=%d件 L2=%d件 L3=%d件 | 保存: %s",
        1, len(parsed["L2"]), len(parsed["L3"]), saved,
    )
    return output
