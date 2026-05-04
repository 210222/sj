"""持久化会话记忆（SQLite + FTS5）。

Letta 参考: sessions 表对应 Recall Storage（短期），facts 表对应 Archival Storage（长期）。
Phase 6 升级为向量搜索。
"""

import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from src.coach.data import MemoryStore

_logger = logging.getLogger(__name__)

# ── DDL ──────────────────────────────────────────────────────────────

SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    rowid           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    turn_index      INTEGER NOT NULL,
    intent          TEXT NOT NULL DEFAULT 'general',
    action_type     TEXT NOT NULL DEFAULT 'suggest',
    user_input      TEXT NOT NULL DEFAULT '',
    safety_allowed  INTEGER NOT NULL DEFAULT 1,
    created_at_utc  TEXT NOT NULL,
    UNIQUE(session_id, turn_index)
);
"""

SESSIONS_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
    session_id, intent, action_type, user_input,
    content=sessions,
    content_rowid=rowid
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class SessionMemory:
    """持久化会话记忆 — SQLite sessions 表 + FTS5 全文搜索。

    兼容 Phase 1：store()/recall() 签名不变、返回格式不变。
    """

    def __init__(self, recall_limit: int = 5, db_path: str = "data/coherence.db"):
        self._recall_limit = recall_limit
        self._db_path = db_path
        self._facts = MemoryStore(db_path)
        self._facts.create_tables()
        self._init_db(db_path)

    def _init_db(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SESSIONS_TABLE_SQL)
            try:
                conn.executescript(SESSIONS_FTS_SQL)
            except sqlite3.OperationalError:
                _logger.warning("FTS5 not available — recall falls back to LIKE")
            conn.commit()
        except Exception:
            _logger.warning("SessionMemory: _init_db failed", exc_info=True)
        finally:
            conn.close()

    # ── 核心接口（与 Phase 1 兼容）───────────────────────────────────

    def store(self, session_id: str, turn_data: dict) -> None:
        """写 sessions 表 + FTS5 自动同步索引。

        Args:
            session_id: 会话 ID
            turn_data: {"intent": str, "action_type": str,
                        "user_input": str, "safety_allowed": bool}
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_index), -1) + 1 AS nxt FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            turn_index = row["nxt"]

            conn.execute(
                """INSERT INTO sessions
                   (session_id, turn_index, intent, action_type, user_input, safety_allowed, created_at_utc)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    turn_index,
                    turn_data.get("intent", "general"),
                    turn_data.get("action_type", "suggest"),
                    turn_data.get("user_input", ""),
                    1 if turn_data.get("safety_allowed", True) else 0,
                    _utc_now(),
                ),
            )
            conn.commit()
        except Exception:
            _logger.warning("SessionMemory: store failed", exc_info=True)
        finally:
            conn.close()

    def recall(self, intent: str, user_state: dict | None = None,
               limit: int | None = None) -> list[dict]:
        """FTS5 关键词搜索 → 与 Phase 1 同格式的召回列表。

        Returns:
            [{"intent": str, "data": {..}, "ts": float}, ...]
        """
        if limit is None:
            limit = self._recall_limit

        conn = self._connect()
        try:
            if not intent or intent.lower() == "general":
                rows = conn.execute(
                    """SELECT session_id, turn_index, intent, action_type, user_input,
                              safety_allowed, created_at_utc
                       FROM sessions
                       ORDER BY created_at_utc DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            else:
                # 优先 FTS5 MATCH；不可用或空结果回退 LIKE（中文分词 compatible）
                rows: list = []
                fts_ok = False
                try:
                    rows_fts = conn.execute(
                        """SELECT s.session_id, s.turn_index, s.intent, s.action_type,
                                  s.user_input, s.safety_allowed, s.created_at_utc
                           FROM sessions s
                           JOIN sessions_fts sf ON s.rowid = sf.rowid
                           WHERE sessions_fts MATCH ?
                           ORDER BY rank LIMIT ?""",
                        (intent, limit),
                    ).fetchall()
                    fts_ok = True
                    if rows_fts:
                        rows = list(rows_fts)
                except sqlite3.OperationalError:
                    pass  # FTS5 不可用

                # FTS5 不可用或返回空 → LIKE 降级
                if not fts_ok or not rows:
                    rows = conn.execute(
                        """SELECT session_id, turn_index, intent, action_type,
                                  user_input, safety_allowed, created_at_utc
                           FROM sessions
                           WHERE intent LIKE ? OR user_input LIKE ?
                           ORDER BY created_at_utc DESC LIMIT ?""",
                        (f"%{intent}%", f"%{intent}%", limit),
                    ).fetchall()

            results = []
            for row in rows:
                d = dict(row)
                results.append({
                    "intent": d.get("intent", "general"),
                    "data": {
                        "action_type": d.get("action_type", "suggest"),
                        "user_input": d.get("user_input", ""),
                        "safety_allowed": bool(d.get("safety_allowed", 1)),
                        "turn_index": d.get("turn_index"),
                        "session_id": d.get("session_id"),
                    },
                    "ts": _parse_utc_to_ts(d.get("created_at_utc", "")),
                })
            return results
        except Exception:
            _logger.warning("SessionMemory: recall failed", exc_info=True)
            return []
        finally:
            conn.close()

    # ── Phase 2 新增 ────────────────────────────────────────────────

    def promote_to_fact(self, session_id: str, turn_index: int, claim: str,
                        confidence: float = 0.7, ttl: int | None = None,
                        scope: str = "general") -> str:
        """将一轮对话提升为持久事实（写入 facts 表）。

        Letta 对应: ArchivalStorage.insert() — 短期→长期记忆转化。

        Raises:
            ValueError: turn 不存在。
        """
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT * FROM sessions WHERE session_id=? AND turn_index=?""",
                (session_id, turn_index),
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"Turn not found: session={session_id}, turn={turn_index}"
                )
        finally:
            conn.close()

        fact_id = f"fact_{uuid.uuid4().hex[:12]}"
        self._facts.insert_fact(fact_id, claim, confidence, ttl, scope, "user_history")
        return fact_id

    # ── 内部 ────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        return conn


def _parse_utc_to_ts(utc_str: str) -> float:
    """ISO 8601 → epoch float。解析失败返回当前时间。"""
    try:
        return datetime.fromisoformat(utc_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time()


# ── Phase 6: 向量记忆升级 (Letta 精简版) ──────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent


class ArchivalMemory:
    """长期档案记忆：基于 SQLite FTS5 的语义搜索。

    使用 FTS5 虚拟表做全文搜索，轻量替代向量嵌入。
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(ROOT / "data" / "coherence.db")
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_archive
                USING fts5(content, source_tag, metadata)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS archive_meta (
                    rowid INTEGER PRIMARY KEY,
                    memory_id TEXT UNIQUE,
                    timestamp_utc TEXT,
                    lifecycle_status TEXT DEFAULT 'active',
                    confidence REAL DEFAULT 0.5
                )
            """)
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def store(self, content: str, source_tag: str = "general",
              metadata: str = "{}", confidence: float = 0.5) -> str:
        memory_id = f"arch_{uuid.uuid4().hex[:12]}"
        now = _utc_now()
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO memory_archive (content, source_tag, metadata) "
                "VALUES (?, ?, ?)",
                (content, source_tag, metadata),
            )
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO archive_meta "
                "(rowid, memory_id, timestamp_utc, lifecycle_status, confidence) "
                "VALUES (?, ?, ?, 'active', ?)",
                (row_id, memory_id, now, confidence),
            )
            conn.commit()
        except Exception:
            _logger.warning("ArchivalMemory.store failed", exc_info=True)
        finally:
            conn.close()
        return memory_id

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """FTS5 MATCH 语义搜索。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT b.memory_id, m.content, m.source_tag,
                          m.metadata, b.confidence, b.timestamp_utc
                   FROM memory_archive m
                   JOIN archive_meta b ON m.rowid = b.rowid
                   WHERE m.content MATCH ? AND b.lifecycle_status = 'active'
                   ORDER BY b.confidence DESC LIMIT ?""",
                (query, limit),
            ).fetchall()
            return [
                {
                    "memory_id": r["memory_id"], "content": r["content"],
                    "source_tag": r["source_tag"], "metadata": r["metadata"],
                    "confidence": r["confidence"], "timestamp": r["timestamp_utc"],
                }
                for r in rows
            ]
        except Exception:
            return []
        finally:
            conn.close()

    def archive_memory(self, memory_id: str) -> bool:
        """软删除：标记为 archived。"""
        conn = sqlite3.connect(self._db_path)
        try:
            c = conn.execute(
                "UPDATE archive_meta SET lifecycle_status = 'archived' "
                "WHERE memory_id = ?", (memory_id,),
            )
            conn.commit()
            return c.rowcount > 0
        except Exception:
            return False
        finally:
            conn.close()

    def stats(self) -> dict:
        """返回档案记忆统计。"""
        conn = sqlite3.connect(self._db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM archive_meta").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM archive_meta "
                "WHERE lifecycle_status = 'active'"
            ).fetchone()[0]
            return {"total": total, "active": active, "archived": total - active}
        except Exception:
            return {"total": 0, "active": 0, "archived": 0}
        finally:
            conn.close()


class WorkingMemory:
    """工作记忆：当前会话上下文缓存。

    临时存储当前会话的数据。短生命周期，超容量自动裁剪。
    """

    def __init__(self, capacity: int = 50):
        self._store: dict[str, list[dict]] = {}
        self._capacity = capacity

    def set(self, key: str, value: Any) -> None:
        if key not in self._store:
            self._store[key] = []
        self._store[key].append({"value": value, "timestamp": _utc_now()})
        if len(self._store[key]) > self._capacity:
            self._store[key] = self._store[key][-self._capacity:]

    def get(self, key: str, default: Any = None) -> Any:
        items = self._store.get(key, [])
        if not items:
            return default
        return items[-1]["value"]

    def get_all(self, key: str) -> list[dict]:
        return list(self._store.get(key, []))

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def size(self) -> int:
        return sum(len(v) for v in self._store.values())


class ReflectiveMemoryManager:
    """反思性记忆管理：定期置信度衰减 + 过期归档 + 低置信度清理。

    Letta Sleep-time Agent 的精简实现。
    """

    def __init__(self, archival_memory: ArchivalMemory,
                 decay_rate: float = 0.05,
                 low_confidence_threshold: float = 0.1,
                 archive_after_runs: int = 10):
        self._archival = archival_memory
        self._decay_rate = decay_rate
        self._low_conf_threshold = low_confidence_threshold
        self._archive_after = archive_after_runs
        self._run_count = 0

    def run(self) -> dict:
        """执行一次 RMM 整理循环。"""
        self._run_count += 1
        result = {"decayed": 0, "archived": 0, "cleaned": 0}
        if self._run_count < self._archive_after:
            return result

        result["decayed"] = self._decay_all()
        result["archived"] = self._archive_expired()
        result["cleaned"] = self._cleanup_low_confidence()
        self._run_count = 0
        return result

    def _decay_all(self) -> int:
        try:
            conn = sqlite3.connect(self._archival._db_path)
            try:
                c = conn.execute(
                    "UPDATE archive_meta SET confidence = "
                    "MAX(0.0, confidence - ?) WHERE lifecycle_status = 'active'",
                    (self._decay_rate,),
                )
                conn.commit()
                return c.rowcount
            finally:
                conn.close()
        except Exception:
            return 0

    def _archive_expired(self) -> int:
        try:
            conn = sqlite3.connect(self._archival._db_path)
            try:
                c = conn.execute(
                    "UPDATE archive_meta SET lifecycle_status = 'archived' "
                    "WHERE lifecycle_status = 'active' AND confidence < ?",
                    (self._low_conf_threshold,),
                )
                conn.commit()
                return c.rowcount
            finally:
                conn.close()
        except Exception:
            return 0

    def _cleanup_low_confidence(self) -> int:
        try:
            conn = sqlite3.connect(self._archival._db_path)
            try:
                # 先获取待删除的 rowid 列表，同步清理 FTS5
                stale = conn.execute(
                    "SELECT rowid FROM archive_meta "
                    "WHERE lifecycle_status = 'archived' AND confidence < 0.05"
                ).fetchall()
                row_ids = [r[0] for r in stale]
                if row_ids:
                    conn.execute(
                        "DELETE FROM archive_meta "
                        "WHERE lifecycle_status = 'archived' AND confidence < 0.05"
                    )
                    for rid in row_ids:
                        conn.execute(
                            "DELETE FROM memory_archive WHERE rowid = ?", (rid,)
                        )
                conn.commit()
                return len(row_ids)
            finally:
                conn.close()
        except Exception:
            return 0
