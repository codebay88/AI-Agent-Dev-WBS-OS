"""
F10100 api_authentication_verification — Phase 10 外部API認証テストモジュール

Phase 10 の前提条件モジュール。外部 API（Claude API）への接続認証を検証し、
HITL 承認を経て phase10_stage="api_verified" に遷移する。

処理フロー（7ステップ）:
  Step 1: ANTHROPIC_API_KEY 環境変数の存在確認
  Step 2: API ping リクエスト送信（mock 対応）
  Step 3: 認証ステータス判定（authenticated / failed）
  Step 4: レイテンシ測定・閾値チェック（< 2.0s）
  Step 5: error_count 検証（== 0 必須）
  Step 6: api_auth_report.json 生成
  Step 7: HITL 承認ポイント設定（H-P10-002）/ hitl_api_approval_log.json 書き込み

セキュリティ制約（変更禁止）:
  - API キーはコードに記述しない。os.environ 経由のみ
  - API キーをログ・出力に表示しない
  - .env ファイルを Git にコミットしない
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG  = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
PHASE10_DIR  = BASE_DIR / "docs" / "phase10"
PHASE9_DIR   = BASE_DIR / "docs" / "phase9"

AUTH_REPORT_PATH   = PHASE10_DIR / "api_auth_report.json"
AUTH_LOG_PATH      = PHASE10_DIR / "api_auth_log.json"
HITL_LOG_PATH      = PHASE10_DIR / "hitl_api_approval_log.json"
VALIDATION_ERR     = PHASE10_DIR / "validation_error.json"
SYSTEM_FLAG        = PHASE9_DIR  / "system_complete_flag"

LATENCY_THRESHOLD  = 2.0   # seconds
ENV_KEY_NAME       = "ANTHROPIC_API_KEY"  # 修正: 他モジュール（f10_module.py等）と統一。修正前は環境変数名が異なっており、.envに存在しないため常に誤判定される不具合があった
HITL_POINT_ID      = "H-P10-002"
HITL_TRIGGER       = "外部API連携の安全確認"


class F10100ApiAuthVerification:
    """
    F10100 api_authentication_verification の全7ステップを実行する。

    api_mock: テスト用モック関数。指定時は実 API を呼ばない。
              シグネチャ: () -> dict  (keys: status, latency, error_count)
    hitl_fn:  HITL 承認関数。シグネチャ: (point_id: str) -> str ("approve"/"reject")
    """

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        api_mock: Optional[Callable[[], dict]] = None,
        hitl_fn: Optional[Callable[[str], str]] = None,
    ) -> dict[str, Any]:
        """7ステップを順次実行し、結果 dict を返す。"""
        PHASE10_DIR.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: 環境変数確認
            key_present = self.step1_check_env_key()
            if not key_present:
                return self._stop_on_key_missing()

            # Step 2: API ping
            ping = self.step2_send_ping(api_mock)

            # Step 3: ステータス判定
            auth_status = self.step3_determine_status(ping)
            if auth_status == "failed":
                return self._rollback_on_auth_failed(ping)

            # Step 4: レイテンシチェック
            latency_ok, latency_warning = self.step4_check_latency(ping)

            # Step 5: error_count 検証
            error_ok = self.step5_verify_error_count(ping)
            if not error_ok:
                self._write_validation_error(ping)
                return self._build_result(
                    success=False,
                    reason="error_count > 0",
                    ping=ping,
                    latency_warning=latency_warning,
                    hitl_decision=None,
                )

            # Step 6: レポート生成
            report = self.step6_generate_report(ping, latency_warning)

            # Step 7: HITL 承認
            hitl_decision = self.step7_set_hitl_checkpoint(
                report, hitl_fn, latency_warning
            )

            success = hitl_decision == "approve"
            return self._build_result(
                success=success,
                reason="hitl_rejected" if not success else "ok",
                ping=ping,
                latency_warning=latency_warning,
                hitl_decision=hitl_decision,
            )

        except Exception as exc:  # noqa: BLE001
            return self._build_result(
                success=False,
                reason=f"exception: {exc}",
                ping={},
                latency_warning=False,
                hitl_decision=None,
            )

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def step1_check_env_key(self) -> bool:
        """環境変数 ANTHROPIC_API_KEY の存在を確認する（値は参照しない）。"""
        present = bool(os.environ.get(ENV_KEY_NAME))
        self._append_log("step1_check_env_key", {"key_present": present})
        return present

    def step2_send_ping(
        self, api_mock: Optional[Callable[[], dict]]
    ) -> dict[str, Any]:
        """API ping を送信する。api_mock が指定された場合はモックを使用する。"""
        if api_mock is not None:
            result = api_mock()
            self._append_log("step2_send_ping", {"mode": "mock", "result": result})
            return result

        # 実 API 呼び出し（APIキーは環境変数から取得し、ログに出力しない）
        try:
            import anthropic  # type: ignore[import]

            client = anthropic.Anthropic(api_key=os.environ.get(ENV_KEY_NAME))
            t0 = time.monotonic()
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency = round(time.monotonic() - t0, 4)
            result = {"status": "authenticated", "latency": latency, "error_count": 0}
        except Exception as exc:  # noqa: BLE001
            result = {
                "status": "failed",
                "latency": None,
                "error_count": 1,
                "error": str(exc),
            }

        self._append_log("step2_send_ping", {"mode": "real", "status": result["status"]})
        return result

    def step3_determine_status(self, ping: dict) -> str:
        """ping 結果から認証ステータスを判定する。"""
        status = ping.get("status", "failed")
        self._append_log("step3_determine_status", {"auth_status": status})
        return status

    def step4_check_latency(self, ping: dict) -> tuple[bool, bool]:
        """レイテンシが閾値（< 2.0s）を満たすか確認する。"""
        latency = ping.get("latency")
        if latency is None:
            ok, warning = False, True
        else:
            ok = latency < LATENCY_THRESHOLD
            warning = not ok
        self._append_log(
            "step4_check_latency",
            {"latency": latency, "threshold": LATENCY_THRESHOLD, "ok": ok, "warning": warning},
        )
        return ok, warning

    def step5_verify_error_count(self, ping: dict) -> bool:
        """error_count == 0 を検証する。"""
        error_count = ping.get("error_count", 1)
        ok = error_count == 0
        self._append_log("step5_verify_error_count", {"error_count": error_count, "ok": ok})
        return ok

    def step6_generate_report(
        self, ping: dict, latency_warning: bool
    ) -> dict[str, Any]:
        """api_auth_report.json と api_auth_log.json を生成する。"""
        now = datetime.now().isoformat()
        report = {
            "module": "F10100",
            "name": "api_authentication_verification",
            "generated_at": now,
            "result": {
                "auth_status": ping.get("status", "failed"),
                "latency": ping.get("latency"),
                "latency_threshold": LATENCY_THRESHOLD,
                "latency_ok": not latency_warning,
                "latency_warning": latency_warning,
                "error_count": ping.get("error_count", 0),
                "phase10_stage": "api_verified_pending_hitl",
            },
            "hitl_point": HITL_POINT_ID,
        }
        AUTH_REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        log_data = {
            "module": "F10100",
            "generated_at": now,
            "steps": self._log,
        }
        AUTH_LOG_PATH.write_text(
            json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self._append_log("step6_generate_report", {"report_path": str(AUTH_REPORT_PATH)})
        return report

    def step7_set_hitl_checkpoint(
        self,
        report: dict,
        hitl_fn: Optional[Callable[[str], str]],
        latency_warning: bool,
    ) -> str:
        """HITL 承認ポイント H-P10-002 を設定し、承認結果を返す。"""
        decision = hitl_fn(HITL_POINT_ID) if hitl_fn else "approve"

        now = datetime.now().isoformat()
        hitl_log = {
            "module": "F10100",
            "hitl_point_id": HITL_POINT_ID,
            "trigger": HITL_TRIGGER,
            "mandatory": True,
            "decision": decision,
            "decided_at": now,
            "context": {
                "auth_status": report["result"]["auth_status"],
                "latency_warning": latency_warning,
                "phase10_stage_before": "api_verified_pending_hitl",
                "phase10_stage_after": "api_verified" if decision == "approve" else "hitl_rejected",
            },
        }
        HITL_LOG_PATH.write_text(
            json.dumps(hitl_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._append_log("step7_set_hitl_checkpoint", {"decision": decision})
        return decision

    # ------------------------------------------------------------------
    # summary.log integration
    # ------------------------------------------------------------------

    def write_summary_entry(self, result: dict) -> None:
        """summary.log に WP F10100 実行記録を追記する。"""
        success = result.get("success", False)
        tag     = "[PASS]" if success else "[FAIL]"
        line    = (
            f"{tag} [F10100] api_authentication_verification | "
            f"stage={result.get('phase10_stage', 'unknown')} | "
            f"auth={result.get('auth_status', '?')} | "
            f"latency_warning={result.get('latency_warning', '?')} | "
            f"hitl={result.get('hitl_decision', '?')} | "
            f"{datetime.now().isoformat()}\n"
        )
        with SUMMARY_LOG.open("a", encoding="utf-8") as f:
            f.write(line)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _append_log(self, step: str, data: dict) -> None:
        self._log.append({"step": step, "at": datetime.now().isoformat(), **data})

    def _build_result(
        self,
        *,
        success: bool,
        reason: str,
        ping: dict,
        latency_warning: bool,
        hitl_decision: Optional[str],
    ) -> dict[str, Any]:
        stage = "api_verified" if success else "api_auth_failed"
        return {
            "module": "F10100",
            "success": success,
            "reason": reason,
            "auth_status": ping.get("status", "unknown"),
            "latency": ping.get("latency"),
            "latency_warning": latency_warning,
            "error_count": ping.get("error_count", 0),
            "hitl_decision": hitl_decision,
            "phase10_stage": stage,
            "generated_at": datetime.now().isoformat(),
        }

    def _stop_on_key_missing(self) -> dict[str, Any]:
        """ANTHROPIC_API_KEY が未設定の場合: 停止 + HITL 通知相当のログを出力する。"""
        now = datetime.now().isoformat()
        err = {
            "module": "F10100",
            "error": "api_key_missing",
            "message": f"{ENV_KEY_NAME} が環境変数に設定されていません。HITL による手動入力が必要です。",
            "generated_at": now,
        }
        VALIDATION_ERR.write_text(
            json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # HITL 通知ログ
        hitl_log = {
            "module": "F10100",
            "hitl_point_id": HITL_POINT_ID,
            "trigger": HITL_TRIGGER,
            "mandatory": True,
            "decision": "pending",
            "reason": "api_key_missing",
            "decided_at": now,
        }
        HITL_LOG_PATH.write_text(
            json.dumps(hitl_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self._build_result(
            success=False,
            reason="api_key_missing",
            ping={},
            latency_warning=False,
            hitl_decision="pending",
        )

    def _rollback_on_auth_failed(self, ping: dict) -> dict[str, Any]:
        """認証失敗時: ロールバック相当の記録を出力する。"""
        now = datetime.now().isoformat()
        err = {
            "module": "F10100",
            "error": "authentication_failed",
            "message": "API 認証に失敗しました。ロールバックが必要です。",
            "ping": {"status": ping.get("status"), "error": ping.get("error", "")},
            "generated_at": now,
        }
        VALIDATION_ERR.write_text(
            json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self._build_result(
            success=False,
            reason="authentication_failed",
            ping=ping,
            latency_warning=False,
            hitl_decision=None,
        )

    def _write_validation_error(self, ping: dict) -> None:
        err = {
            "module": "F10100",
            "error": "error_count_nonzero",
            "error_count": ping.get("error_count", 1),
            "generated_at": datetime.now().isoformat(),
        }
        VALIDATION_ERR.write_text(
            json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8"
        )
