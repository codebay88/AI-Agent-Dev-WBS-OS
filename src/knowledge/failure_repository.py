"""
FailureRepository — Phase 6 WP9230 失敗知識蓄積モジュール

Phase 5〜6 の運用・改善履歴から異常・例外・再試行事例を抽出し、
再発防止パターンを生成して Phase 7 学習層へ引き渡す。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SUMMARY_LOG = BASE_DIR / "docs" / "phase4" / "logs" / "summary.log"
REPO_PATH   = BASE_DIR / "docs" / "phase6" / "failure_repository.json"

# 失敗カテゴリ定数
CAT_API_ERROR     = "api_error"
CAT_HITL          = "hitl"
CAT_RETRY_EXCEEDED = "retry_exceeded"
CAT_FAILSAFE      = "failsafe"
CAT_MECE          = "mece_uncertainty"
CAT_TRACE         = "trace_chain"

# summary.log のパターン → カテゴリ対応
_LOG_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"ALERT ERROR"),  CAT_API_ERROR,      "ERROR アラート検出"),
    (re.compile(r"ALERT RETRY"),  CAT_RETRY_EXCEEDED, "RETRY アラート検出"),
    (re.compile(r"ALERT HITL"),   CAT_HITL,           "HITL 移譲検出"),
    (re.compile(r"ALERT WARNING"),CAT_API_ERROR,      "WARNING アラート検出"),
]

# Phase 5〜6 既知の失敗パターン（Phase 4 テストで確認済みの事例）
_KNOWN_FAILURES: list[dict] = [
    {
        "failure_id":  "FL-001",
        "module":      "F10",
        "category":    CAT_HITL,
        "description": "曖昧語（など/いろいろ等）を含む入力で HITL が発動",
        "condition":   "goal_text に AMBIGUOUS_WORDS が含まれる",
        "resolution":  "ユーザーが曖昧語を除去して再入力する",
        "source":      "WP8230",
    },
    {
        "failure_id":  "FL-002",
        "module":      "F10",
        "category":    CAT_RETRY_EXCEEDED,
        "description": "API 呼び出しが MAX_RETRY=3 回失敗し RuntimeError が発生",
        "condition":   "ネットワーク障害または API タイムアウト",
        "resolution":  "フェイルセーフ発動・エラーを上位に伝播",
        "source":      "WP8220",
    },
    {
        "failure_id":  "FL-003",
        "module":      "F60",
        "category":    CAT_MECE,
        "description": "cosine 類似度が 0.80〜0.85 の不確実域で HITL_required が発動",
        "condition":   "0.80 ≤ cos ≤ 0.85（重複ではなく不確実）",
        "resolution":  "HITL 承認後に再処理またはスキップ",
        "source":      "WP8130",
    },
    {
        "failure_id":  "FL-004",
        "module":      "F80",
        "category":    CAT_TRACE,
        "description": "不明な trace_id または循環依存が検出され HITL 移譲",
        "condition":   "trace_chain に存在しない trace_id が参照される",
        "resolution":  "HITL 移譲・hitl_elements にノードを記録",
        "source":      "WP8230",
    },
    {
        "failure_id":  "FL-005",
        "module":      "F40",
        "category":    CAT_HITL,
        "description": "タスクリストが空で HITL_required が発動",
        "condition":   "goals が空リスト、または全ゴールが除外された場合",
        "resolution":  "ユーザーが目的を見直して再入力",
        "source":      "WP8230",
    },
]

# カテゴリ別防止パターン
_PREVENTION_PATTERNS: list[dict] = [
    {
        "pattern_id":    "PP-001",
        "category":      CAT_HITL,
        "trigger":       "AMBIGUOUS_WORDS 検出 / タスク空 / cosine 不確実域",
        "action":        "HITL 移譲（hitl=True）→ ユーザー承認待ち",
        "threshold":     "曖昧語 1 件以上 / cos 0.80〜0.85 / tasks==[]",
        "related_failures": ["FL-001", "FL-003", "FL-005"],
    },
    {
        "pattern_id":    "PP-002",
        "category":      CAT_RETRY_EXCEEDED,
        "trigger":       "API 連続失敗 MAX_RETRY=3 回",
        "action":        "RuntimeError 発火・パイプライン即時停止",
        "threshold":     "retry_count >= 3",
        "related_failures": ["FL-002"],
    },
    {
        "pattern_id":    "PP-003",
        "category":      CAT_TRACE,
        "trigger":       "不明 trace_id / 循環依存",
        "action":        "HITL 移譲（hitl_elements に対象ノードを記録）",
        "threshold":     "trace_chain 参照エラー 1 件以上",
        "related_failures": ["FL-004"],
    },
    {
        "pattern_id":    "PP-004",
        "category":      CAT_API_ERROR,
        "trigger":       "ERROR アラート 3 件以上（consecutive_errors 閾値）",
        "action":        "critical アラート発火・即時対応要求",
        "threshold":     "consecutive_errors >= 3",
        "related_failures": [],
    },
]


class FailureRepository:
    """
    失敗事例を登録・クラスタリングし、再発防止パターンを生成する。

    使い方:
        repo = FailureRepository()
        repo.load_known_failures()           # 既知事例を読み込む
        log_entries = repo.extract_from_log(log_path)
        for e in log_entries:
            repo.register(e)
        patterns = repo.generate_prevention_patterns()
        repo.save_repository()
        repo.write_summary_entry()
    """

    def __init__(
        self,
        summary_log: Path | None = None,
        repo_path:   Path | None = None,
    ) -> None:
        self._summary_log = summary_log or SUMMARY_LOG
        self._repo_path   = repo_path   or REPO_PATH
        self._entries:  list[dict] = []
        self._patterns: list[dict] = []
        self._id_counter = 0

    # ── 既知事例の読み込み ────────────────────────────────────

    def load_known_failures(self) -> list[dict]:
        """Phase 4〜5 で確認済みの既知失敗事例を登録する。"""
        for entry in _KNOWN_FAILURES:
            if not self._find_by_id(entry["failure_id"]):
                self._entries.append(dict(entry))
        return list(self._entries)

    # ── ログからの抽出 ────────────────────────────────────────

    def extract_from_log(self, log_path: Path) -> list[dict]:
        """
        summary.log からアラートラインを解析して失敗事例候補を返す。

        Returns:
            各アラート行を dict 化したリスト（まだ register は呼ばない）
        """
        if not log_path.exists():
            return []
        extracted: list[dict] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            for pattern, category, desc in _LOG_PATTERNS:
                if pattern.search(line):
                    module = re.search(r"module=([\w.]+)", line)
                    extracted.append({
                        "category":    category,
                        "description": desc,
                        "condition":   line.strip()[:120],
                        "resolution":  "ログ記録済み",
                        "module":      module.group(1).split(".")[-1].upper() if module else "UNKNOWN",
                        "source":      "summary.log",
                    })
                    break
        return extracted

    # ── モニターからの抽出 ────────────────────────────────────

    def extract_from_monitor(self, handler) -> list[dict]:
        """
        MonitoringHandler のフェイルセーフ発動履歴を失敗事例に変換する。

        Returns:
            failsafe_events を dict 化したリスト
        """
        return [
            {
                "category":    CAT_FAILSAFE,
                "description": f"フェイルセーフ発動: {e.get('module', '?')}",
                "condition":   f"trace_id={e.get('trace_id')} estimated_effort={e.get('estimated_effort')}",
                "resolution":  "安全停止・記録済み",
                "module":      e.get("module", "UNKNOWN"),
                "source":      "MonitoringHandler.failsafe_events",
            }
            for e in handler.failsafe_events
        ]

    # ── 登録 ──────────────────────────────────────────────────

    def register(self, entry: dict) -> str:
        """
        失敗事例を登録し、割り当てた failure_id を返す。

        entry に "failure_id" が既に含まれている場合はそれを使用する。
        """
        if "failure_id" not in entry:
            self._id_counter += 1
            entry = dict(entry)
            entry["failure_id"] = f"FL-LOG-{self._id_counter:03}"
        if not entry.get("timestamp"):
            entry["timestamp"] = datetime.now().isoformat()
        self._entries.append(entry)
        return entry["failure_id"]

    # ── クラスタリング ────────────────────────────────────────

    def cluster_similar(self, entries: list[dict] | None = None) -> list[dict]:
        """
        category でグルーピングし、クラスター情報を返す。

        Returns:
            [{"category": str, "count": int, "failure_ids": list[str]}, ...]
        """
        target = entries if entries is not None else self._entries
        clusters: dict[str, list[str]] = {}
        for e in target:
            cat = e.get("category", "unknown")
            clusters.setdefault(cat, []).append(e.get("failure_id", "?"))
        return [
            {"category": cat, "count": len(ids), "failure_ids": ids}
            for cat, ids in sorted(clusters.items())
        ]

    # ── 防止パターン生成 ─────────────────────────────────────

    def generate_prevention_patterns(self) -> list[dict]:
        """
        登録済み事例に基づき再発防止パターンを生成する。

        既知パターン（_PREVENTION_PATTERNS）を基礎とし、
        ログ抽出で新たに追加されたカテゴリがあれば汎用パターンを追加する。
        """
        patterns = list(_PREVENTION_PATTERNS)
        existing_cats = {p["category"] for p in patterns}

        for e in self._entries:
            cat = e.get("category", "unknown")
            if cat not in existing_cats:
                existing_cats.add(cat)
                patterns.append({
                    "pattern_id":    f"PP-AUTO-{len(patterns):03}",
                    "category":      cat,
                    "trigger":       e.get("description", "不明"),
                    "action":        "ログ記録・調査",
                    "threshold":     "1 件以上",
                    "related_failures": [e.get("failure_id", "?")],
                })

        self._patterns = patterns
        return patterns

    # ── 保存 ──────────────────────────────────────────────────

    def save_repository(self, path: Path | None = None) -> None:
        """失敗知識リポジトリを failure_repository.json に保存する。"""
        p = path or self._repo_path
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "generated_at":        datetime.now().isoformat(),
            "total_failures":      len(self._entries),
            "total_patterns":      len(self._patterns),
            "failures":            self._entries,
            "prevention_patterns": self._patterns,
            "clusters":            self.cluster_similar(),
            "phase7_ready":        True,
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── summary.log 追記 ─────────────────────────────────────

    def write_summary_entry(self, log_path: Path | None = None) -> None:
        """WP9230 完了エントリを summary.log に追記する。"""
        path = log_path or self._summary_log
        ts   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        clusters = self.cluster_similar()
        cluster_str = "\n".join(
            f"    {c['category']}: {c['count']}件" for c in clusters
        ) or "    なし"
        patterns_str = "\n".join(
            f"    {p['pattern_id']}: {p['trigger'][:60]}" for p in self._patterns
        ) or "    なし"

        entry = (
            f"\n[{ts}] WP9230 失敗知識蓄積完了\n"
            f"  登録失敗事例    : {len(self._entries)}件\n"
            f"  防止パターン数  : {len(self._patterns)}件\n"
            f"  カテゴリ別件数  :\n{cluster_str}\n"
            f"  防止パターン一覧:\n{patterns_str}\n"
            f"  Phase 6 フラグ  : READY\n"
            f"  Phase 7 準備    : READY（failure_repository.json 生成済み）\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── クエリ ────────────────────────────────────────────────

    def get_all_entries(self) -> list[dict]:
        return list(self._entries)

    def get_prevention_patterns(self) -> list[dict]:
        return list(self._patterns)

    def _find_by_id(self, failure_id: str) -> dict | None:
        for e in self._entries:
            if e.get("failure_id") == failure_id:
                return e
        return None

    def get_by_category(self, category: str) -> list[dict]:
        return [e for e in self._entries if e.get("category") == category]
