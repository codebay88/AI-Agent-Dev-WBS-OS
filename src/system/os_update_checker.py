"""
OSUpdateChecker — Phase 6.5 WP9320 OS・依存ライブラリ更新判断

Python バージョン・インストール済みパッケージの状態を確認し、
更新候補の安全性スコアを算出してレポートを生成する。
セキュリティ・互換性に関わる重大更新は HITL 承認へ移譲する。
"""
from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
REPORT_DIR  = BASE_DIR / "docs" / "system"
REPORT_PATH = REPORT_DIR / "os_update_report.json"

# プロジェクト依存パッケージ（requirements で管理）
REQUIRED_PACKAGES: dict[str, str] = {
    "pytest":      "7.0.0",
    "pytest-mock": "3.0.0",
    "pyyaml":      "6.0",
}

# 安全性スコアの重み
_SCORE_WEIGHTS = {
    "security":     -30,   # セキュリティ更新 → スコアを大きく下げる（HITL 必要）
    "compatibility": -15,  # 互換性変更 → 中程度
    "optional":       0,   # 任意更新 → スコアに影響なし
}

# HITL 承認が必要な安全性スコアの下限
HITL_THRESHOLD = 70


class OSUpdateChecker:
    """
    OS・Python・パッケージの更新候補を検出し、安全性スコアを算出する。

    使い方:
        checker = OSUpdateChecker()
        env     = checker.check_environment()
        pkgs    = checker.check_installed_packages()
        score   = checker.calculate_safety_score(pkgs)
        report  = checker.generate_report(env, pkgs, score)
        checker.save_report(report)
        checker.write_summary_entry(report)
    """

    def __init__(
        self,
        report_path: Path | None = None,
        summary_log: Path | None = None,
    ) -> None:
        self._report_path = report_path or REPORT_PATH
        self._summary_log = summary_log or SUMMARY_LOG

    # ── 環境確認 ─────────────────────────────────────────────

    def check_environment(self) -> dict:
        """Python バージョン・OS 情報を返す。"""
        v = sys.version_info
        return {
            "python_version":   f"{v.major}.{v.minor}.{v.micro}",
            "python_major":     v.major,
            "python_minor":     v.minor,
            "platform":         platform.system(),
            "platform_version": platform.version()[:80],
            "architecture":     platform.machine(),
        }

    # ── パッケージ確認 ───────────────────────────────────────

    def check_installed_packages(
        self,
        required: dict[str, str] | None = None,
    ) -> list[dict]:
        """
        必須パッケージのインストール状況を確認する。

        Returns:
            [{"name": str, "installed": str|None, "required_min": str,
              "status": "ok"|"missing"|"version_low",
              "update_type": "optional"|"compatibility"|"security"}]
        """
        req = required or REQUIRED_PACKAGES
        result: list[dict] = []

        for pkg, min_ver in req.items():
            installed = _get_package_version(pkg)
            if installed is None:
                status      = "missing"
                update_type = "compatibility"
            elif _version_lt(installed, min_ver):
                status      = "version_low"
                update_type = "compatibility"
            else:
                status      = "ok"
                update_type = "optional"

            result.append({
                "name":         pkg,
                "installed":    installed,
                "required_min": min_ver,
                "status":       status,
                "update_type":  update_type,
            })

        return result

    # ── 安全性スコア算出 ─────────────────────────────────────

    def calculate_safety_score(self, packages: list[dict]) -> int:
        """
        インストール状況から安全性スコア（0〜100）を算出する。

        100 = 全パッケージ正常。問題があるほど減点。
        score < HITL_THRESHOLD(70) → HITL 承認推奨。
        """
        score = 100
        for pkg in packages:
            update_type = pkg.get("update_type", "optional")
            score += _SCORE_WEIGHTS.get(update_type, 0)
        return max(0, min(100, score))

    def requires_hitl(self, score: int) -> bool:
        """安全性スコアが閾値を下回る場合 HITL 承認が必要。"""
        return score < HITL_THRESHOLD

    # ── 分類 ────────────────────────────────────────────────

    def classify_updates(self, packages: list[dict]) -> dict:
        """
        更新候補をカテゴリ別に分類する。

        Returns:
            security / compatibility / optional / ok の件数 dict
        """
        counts: dict[str, int] = {
            "security": 0, "compatibility": 0, "optional": 0, "ok": 0
        }
        for pkg in packages:
            key = pkg.get("update_type", "optional") if pkg["status"] != "ok" else "ok"
            counts[key] = counts.get(key, 0) + 1
        return counts

    # ── レポート生成 ─────────────────────────────────────────

    def generate_report(
        self,
        environment: dict,
        packages:    list[dict],
        score:       int,
    ) -> dict:
        """最終レポート dict を生成する。"""
        classification = self.classify_updates(packages)
        return {
            "generated_at":    datetime.now().isoformat(),
            "environment":     environment,
            "packages":        packages,
            "classification":  classification,
            "safety_score":    score,
            "hitl_required":   self.requires_hitl(score),
            "summary": (
                "全パッケージ正常 — 更新不要"
                if classification["ok"] == len(packages)
                else f"更新候補 {len(packages) - classification['ok']} 件"
            ),
            "phase6_5_ready":  True,
        }

    def save_report(self, report: dict, path: Path | None = None) -> None:
        """レポートを os_update_report.json に保存する。"""
        p = path or self._report_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def write_summary_entry(
        self,
        report:   dict,
        log_path: Path | None = None,
    ) -> None:
        """WP9320 完了エントリを summary.log に追記する。"""
        path  = log_path or self._summary_log
        ts    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        score = report.get("safety_score", 100)
        hitl  = "あり（承認要）" if report.get("hitl_required") else "不要"
        classification = report.get("classification", {})

        entry = (
            f"\n[{ts}] WP9320 OS更新判断\n"
            f"  安全性スコア  : {score}/100\n"
            f"  HITL承認      : {hitl}\n"
            f"  正常パッケージ: {classification.get('ok', 0)}件\n"
            f"  互換性更新候補: {classification.get('compatibility', 0)}件\n"
            f"  任意更新候補  : {classification.get('optional', 0)}件\n"
            f"  判定サマリー  : {report.get('summary', '')}\n"
            f"  Phase 6.5 フラグ: READY\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)


# ── ユーティリティ ────────────────────────────────────────────

def _get_package_version(name: str) -> str | None:
    """インストール済みパッケージのバージョンを返す。見つからなければ None。"""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _version_lt(installed: str, minimum: str) -> bool:
    """installed < minimum なら True。"""
    def _parse(v: str) -> tuple[int, ...]:
        parts = []
        for seg in v.split(".")[:3]:
            try:
                parts.append(int(seg))
            except ValueError:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)
    return _parse(installed) < _parse(minimum)
