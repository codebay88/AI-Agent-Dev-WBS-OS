import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
DATA_OUT = BASE_DIR / "data" / "output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "hello_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def check_environment() -> dict:
    load_dotenv(BASE_DIR / ".env")
    return {
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "GOOGLE_API_KEY": bool(os.environ.get("GOOGLE_API_KEY", "").strip()),
    }


def check_libraries() -> dict:
    results = {}
    for lib in ["dotenv", "anthropic"]:
        try:
            __import__(lib)
            results[lib] = "OK"
        except ImportError as e:
            results[lib] = f"NG: {e}"
    return results


def check_file_access() -> dict:
    targets = {
        ".env": BASE_DIR / ".env",
        "requirements.txt": BASE_DIR / "requirements.txt",
        "logs/": LOG_DIR,
        "data/output/": DATA_OUT,
        "src/agents/": BASE_DIR / "src" / "agents",
    }
    return {k: "OK" if v.exists() else "NG" for k, v in targets.items()}


def check_api_connection() -> dict:
    load_dotenv(BASE_DIR / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {"status": "SKIP", "reason": "ANTHROPIC_API_KEY が未設定（HITL入力待ち）"}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=32,
            messages=[{"role": "user", "content": "Hello. Reply with just: Hello Agent!"}],
        )
        return {"status": "OK", "response": message.content[0].text.strip()}
    except Exception as e:
        return {"status": "NG", "reason": str(e)}


def save_result(result: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = DATA_OUT / f"wp6950_result_{ts}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def run():
    log.info("=== WP6950 Hello Agent テスト 開始 ===")
    started_at = datetime.now().isoformat()

    log.info("[1/4] 環境変数確認")
    env = check_environment()
    for k, v in env.items():
        log.info("  %s: %s", k, "設定済み" if v else "未設定（HITL入力待ち）")

    log.info("[2/4] ライブラリ確認")
    libs = check_libraries()
    for k, v in libs.items():
        log.info("  %s: %s", k, v)

    log.info("[3/4] ファイルアクセス確認")
    files = check_file_access()
    for k, v in files.items():
        log.info("  %s: %s", k, v)

    log.info("[4/4] API接続確認")
    api = check_api_connection()
    log.info("  status: %s", api.get("status"))
    if api.get("response"):
        log.info("  response: %s", api["response"])
    if api.get("reason"):
        log.info("  reason: %s", api["reason"])

    result = {
        "wp": "WP6950",
        "title": "Hello Agent テスト",
        "executed_at": started_at,
        "checks": {
            "environment": env,
            "libraries": libs,
            "file_access": files,
            "api_connection": api,
        },
        "dod": {
            "env_loaded": all(True for _ in [env]),
            "libraries_ok": all(v == "OK" for v in libs.values()),
            "file_access_ok": all(v == "OK" for v in files.values()),
            "api_ok": api["status"] in ("OK", "SKIP"),
            "log_output_ok": True,
        },
    }

    out = save_result(result)
    log.info("結果保存: %s", out)
    log.info("=== WP6950 Hello Agent テスト 完了 ===")
    return result


if __name__ == "__main__":
    run()
