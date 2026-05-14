"""DashboardAggregator — TTM/SDT 数据聚合服务 (带 YAML 缓存 + 错误处理).

Phase 32: 实例化模型 — 单次 dashboard 加载共享一个 SessionPersistence (5→1 DB 连接).
Phase 36: 新增 LLM runtime observability 聚合.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "coach_defaults.yaml"
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "coherence.db"

# Phase 36: 轻量 runtime observability 缓冲区 (最近 200 条)
_OBS_BUFFER: deque[dict] = deque(maxlen=200)
_OBS_BUFFER_LOCK = threading.Lock()


def _ensure_llm_runtime_table() -> None:
    """创建 llm_runtime_log 表（幂等）."""
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_runtime_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at_utc TEXT NOT NULL,
                session_id TEXT DEFAULT '',
                path TEXT DEFAULT '',
                latency_ms REAL DEFAULT 0,
                first_chunk_latency_ms REAL,
                tokens_total INTEGER DEFAULT 0,
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                cache_eligible INTEGER DEFAULT 0,
                stable_prefix_hash TEXT DEFAULT '',
                stable_prefix_share REAL DEFAULT 0,
                transport_status TEXT DEFAULT 'ok',
                retention_history_hits INTEGER DEFAULT 0,
                retention_memory_hits INTEGER DEFAULT 0,
                finish_reason TEXT DEFAULT 'stop'
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass  # 表创建失败不阻塞主流程


def persist_llm_observability(obs: dict, session_id: str = "") -> None:
    """持久化一条 LLM observability 到 SQLite."""
    if not obs or not isinstance(obs, dict):
        return
    try:
        _ensure_llm_runtime_table()
        runtime = obs.get("runtime", {}) if isinstance(obs.get("runtime"), dict) else {}
        cache = obs.get("cache", {}) if isinstance(obs.get("cache"), dict) else {}
        retention = obs.get("retention", {}) if isinstance(obs.get("retention"), dict) else {}
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute(
            """INSERT INTO llm_runtime_log
               (created_at_utc, session_id, path, latency_ms, first_chunk_latency_ms,
                tokens_total, tokens_prompt, tokens_completion,
                cache_eligible, stable_prefix_hash, stable_prefix_share,
                transport_status, retention_history_hits, retention_memory_hits, finish_reason,
                prompt_cache_hit_tokens, prompt_cache_miss_tokens, token_usage_available)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                str(session_id)[:128],
                runtime.get("path", ""),
                runtime.get("latency_ms", 0),
                runtime.get("first_chunk_latency_ms"),
                runtime.get("tokens_total", 0),
                runtime.get("tokens_prompt"),
                runtime.get("tokens_completion"),
                1 if cache.get("cache_eligible") else 0,
                cache.get("stable_prefix_hash", ""),
                cache.get("stable_prefix_share", 0),
                runtime.get("transport_status", "ok"),
                retention.get("retention_history_hits", 0),
                retention.get("retention_memory_hits", 0),
                runtime.get("finish_reason", "stop"),
                runtime.get("prompt_cache_hit_tokens"),
                runtime.get("prompt_cache_miss_tokens"),
                1 if runtime.get("token_usage_available") else 0,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 持久化失败不阻塞主流程


def get_llm_runtime_history(hours: int = 24, limit: int = 500) -> list[dict]:
    """读取最近 N 小时的 LLM runtime 历史记录."""
    try:
        _ensure_llm_runtime_table()
        conn = sqlite3.connect(str(_DB_PATH))
        cutoff = datetime.now(timezone.utc).isoformat()
        rows = conn.execute(
            """SELECT created_at_utc, session_id, path, latency_ms,
                      tokens_total, cache_eligible, stable_prefix_hash,
                      stable_prefix_share, transport_status,
                      retention_history_hits, retention_memory_hits
               FROM llm_runtime_log
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                "created_at_utc": r[0],
                "session_id": r[1],
                "path": r[2],
                "latency_ms": r[3],
                "tokens_total": r[4],
                "cache_eligible": bool(r[5]),
                "stable_prefix_hash": r[6],
                "stable_prefix_share": r[7],
                "transport_status": r[8],
                "retention_history_hits": r[9],
                "retention_memory_hits": r[10],
            }
            for r in rows
        ]
    except Exception:
        return []


def record_llm_observability(obs: dict, session_id: str = "") -> None:
    """供 agent / coach_bridge 调用，写入缓冲 + 持久化."""
    if not obs or not isinstance(obs, dict):
        return
    with _OBS_BUFFER_LOCK:
        _OBS_BUFFER.append({
            "path": obs.get("runtime", {}).get("path", "?"),
            "latency_ms": obs.get("runtime", {}).get("latency_ms", 0),
            "tokens_total": obs.get("runtime", {}).get("tokens_total", 0),
            "cache_eligible": obs.get("cache", {}).get("cache_eligible", False),
            "stable_prefix_share": obs.get("cache", {}).get("stable_prefix_share", 0),
            "transport_status": obs.get("runtime", {}).get("transport_status", "?"),
        })
    # Phase 37: 同时持久化到 SQLite
    persist_llm_observability(obs, session_id=session_id)


@lru_cache(maxsize=1)
def _cached_config() -> dict:
    """读取 coach_defaults.yaml，带 try/except 保护和 LRU 缓存."""
    try:
        import yaml
    except ImportError:
        _logger.error("pyyaml not installed, returning empty config")
        return {}
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if not isinstance(cfg, dict):
            _logger.error("coach_defaults.yaml parsed to non-dict: %s", type(cfg).__name__)
            return {}
        return cfg
    except FileNotFoundError:
        _logger.error("coach_defaults.yaml not found at %s", _CONFIG_PATH)
        return {}
    except PermissionError:
        _logger.error("Permission denied reading %s", _CONFIG_PATH)
        return {}
    except Exception:
        _logger.exception("Unexpected error loading coach_defaults.yaml")
        return {}


def _invalidate_cache() -> None:
    """清除 YAML 缓存（测试或配置热加载时使用）."""
    _cached_config.cache_clear()


class DashboardAggregator:
    """聚合 TTM 雷达 + SDT 能量环 + 学习进度数据.

    Phase 32: 接受 session_id 参数，所有 get_* 方法共享一个 SessionPersistence 实例。
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._persistence = None

    @property
    def persistence(self):
        if self._persistence is None:
            from src.coach.persistence import SessionPersistence
            self._persistence = SessionPersistence(self.session_id)
        return self._persistence

    def get_ttm_radar(self) -> dict[str, Any]:
        """从 persistence 读取真实 TTM 阶段和 skill_masteries."""
        try:
            from src.coach.ttm import STAGES
            profile = self.persistence.get_profile()
            ttm_stage = profile.get("ttm_stage", "contemplation")
            stage_scores: dict[str, float] = {}
            if profile.get("skill_masteries"):
                masteries = profile["skill_masteries"]
                avg_mastery = sum(masteries.values()) / max(len(masteries), 1)
                for i, stage in enumerate(STAGES):
                    stage_scores[stage] = max(0.0, min(1.0, avg_mastery * (0.5 + i * 0.1)))
            else:
                stage_scores = {s: 0.5 for s in STAGES}
            return {**stage_scores, "current_stage": ttm_stage}
        except Exception:
            _logger.exception("TTM radar aggregation failed")
            return {s: 0.0 for s in ["precontemplation", "contemplation",
                     "preparation", "action", "maintenance"]}

    def get_sdt_rings(self) -> dict[str, float]:
        """从 persistence 读取真实 SDT 三轴评分."""
        try:
            profile = self.persistence.get_profile()
            return {
                "autonomy": profile.get("autonomy", 0.5),
                "competence": profile.get("competence", 0.5),
                "relatedness": profile.get("relatedness", 0.5),
            }
        except Exception:
            _logger.exception("SDT rings aggregation failed")
            return {"autonomy": 0.5, "competence": 0.5, "relatedness": 0.5}

    def get_progress(self) -> dict[str, Any]:
        """从 persistence 读取真实学习进度."""
        try:
            profile = self.persistence.get_profile()
            return {
                "total_sessions": 1,
                "total_turns": profile.get("total_turns", 0),
                "no_assist_avg": None,
                "last_active_utc": None,
                "difficulty_level": profile.get("difficulty_level", "medium"),
                "topics_covered": profile.get("topics_covered", []),
                "skills": profile.get("skill_masteries", {}),
            }
        except Exception:
            _logger.exception("Progress aggregation failed")
            return {"total_sessions": 1, "total_turns": 0}

    def get_mastery_snapshot(self) -> dict | None:
        """返回当前技能掌握度快照 + 最后活动时间."""
        try:
            profile = self.persistence.get_profile()
            masteries = profile.get("skill_masteries", {})
            if not masteries:
                return None
            last_active = None
            try:
                row = self.persistence.db.execute(
                    "SELECT MAX(created_at) FROM profile_history WHERE session_id = ?",
                    (self.session_id,),
                ).fetchone()
                if row and row[0]:
                    last_active = row[0]
            except Exception:
                pass
            return {
                "skills": {k: round(float(v), 4) for k, v in masteries.items()},
                "total_skills": len(masteries),
                "last_active_utc": last_active,
            }
        except Exception:
            return None

    def get_review_queue(self) -> list[dict] | None:
        """从 BKT retention 计算待复习技能列表."""
        try:
            from src.coach.flow import BKTEngine
            skills = self.persistence.get_skills_with_recency()
            if not skills:
                return None
            bkt = BKTEngine()
            items = []
            for skill, data in skills.items():
                ret = bkt.estimate_retention(data["mastery"], data["days_elapsed"])
                if ret < 0.6:
                    items.append({
                        "skill": skill,
                        "retention": round(ret, 4),
                        "mastery": data["mastery"],
                        "days_elapsed": data["days_elapsed"],
                    })
            items.sort(key=lambda x: x["retention"])
            return items[:5] if items else None
        except Exception:
            return None

    @staticmethod
    def get_llm_runtime_summary() -> dict[str, Any] | None:
        """Phase 36+37: 返回最近 LLM runtime 聚合统计 (含分位数)."""
        with _OBS_BUFFER_LOCK:
            records = list(_OBS_BUFFER)
        if not records:
            return None
        n = len(records)
        paths = {"http_sync": 0, "ws_stream": 0}
        cache_eligible_count = 0
        latencies = []
        tokens_list = []
        statuses: dict[str, int] = {}
        for r in records:
            p = r.get("path", "?")
            if p in paths:
                paths[p] += 1
            if r.get("cache_eligible"):
                cache_eligible_count += 1
            lat = r.get("latency_ms", 0)
            if lat > 0:
                latencies.append(lat)
            tok = r.get("tokens_total", 0)
            if tok > 0:
                tokens_list.append(tok)
            s = r.get("transport_status", "?")
            statuses[s] = statuses.get(s, 0) + 1
        result: dict[str, Any] = {
            "sample_size": n,
            "path_distribution": paths,
            "cache_eligible_rate": round(cache_eligible_count / n, 4),
            "transport_status_distribution": statuses,
        }
        if latencies:
            latencies_sorted = sorted(latencies)
            n_lat = len(latencies_sorted)
            result["avg_latency_ms"] = round(sum(latencies_sorted) / n_lat, 1)
            result["p50_latency_ms"] = round(latencies_sorted[n_lat // 2], 1)
            result["p95_latency_ms"] = round(latencies_sorted[int(n_lat * 0.95)], 1)
            result["p99_latency_ms"] = round(latencies_sorted[int(n_lat * 0.99)], 1)
            result["max_latency_ms"] = round(latencies_sorted[-1], 1)
        if tokens_list:
            result["avg_tokens_total"] = round(sum(tokens_list) / len(tokens_list), 1)
        if records:
            shares = [r.get("stable_prefix_share", 0) for r in records if r.get("stable_prefix_share", 0) > 0]
            if shares:
                result["avg_stable_prefix_share"] = round(sum(shares) / len(shares), 4)
        return result

    @staticmethod
    def get_session_llm_summary(session_id: str) -> dict[str, Any] | None:
        """Phase 37: 返回指定 session 的 LLM 调用统计."""
        try:
            _ensure_llm_runtime_table()
            import sqlite3
            conn = sqlite3.connect(str(_DB_PATH))
            rows = conn.execute(
                """SELECT path, latency_ms, tokens_total, cache_eligible,
                          transport_status, created_at_utc
                   FROM llm_runtime_log
                   WHERE session_id = ?
                   ORDER BY id DESC LIMIT 100""",
                (session_id,),
            ).fetchall()
            conn.close()
            if not rows:
                return None
            latencies = [r[1] for r in rows if r[1] > 0]
            tokens = [r[2] for r in rows if r[2] > 0]
            cache_hits = sum(1 for r in rows if r[3])
            return {
                "session_id": session_id,
                "total_calls": len(rows),
                "cache_eligible_rate": round(cache_hits / len(rows), 4) if rows else 0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "avg_tokens": round(sum(tokens) / len(tokens), 1) if tokens else 0,
                "first_call_utc": rows[-1][5] if rows else None,
                "last_call_utc": rows[0][5] if rows else None,
            }
        except Exception:
            return None
