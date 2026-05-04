"""三层图谱数据模型：Entity 层 + Fact 层 CRUD。

与 EventStore 共用 data/coherence.db，不修改已有 ledger.events 表。
WAL 模式 + BEGIN IMMEDIATE 并发安全。
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_logger = logging.getLogger(__name__)

# ── SQL DDL ──────────────────────────────────────────────────────────

ENTITY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entity_profiles (
    entity_id       TEXT PRIMARY KEY,
    timeline        TEXT NOT NULL DEFAULT '[]',
    session_tags    TEXT NOT NULL DEFAULT '[]',
    device_id       TEXT,
    created_at_utc  TEXT NOT NULL,
    updated_at_utc  TEXT NOT NULL
);
"""

FACTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS facts (
    fact_id            TEXT PRIMARY KEY,
    claim              TEXT NOT NULL,
    evidence_ids       TEXT DEFAULT '[]',
    confidence         REAL CHECK(confidence >= 0 AND confidence <= 1),
    timestamp_utc      TEXT NOT NULL,
    ttl_seconds        INTEGER,
    context_scope      TEXT,
    reversibility_flag INTEGER DEFAULT 1 CHECK(reversibility_flag IN (0,1)),
    source_tag         TEXT,
    lifecycle_status   TEXT NOT NULL DEFAULT 'active'
                       CHECK(lifecycle_status IN ('active','frozen','archived')),
    created_at_utc     TEXT NOT NULL,
    updated_at_utc     TEXT NOT NULL
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_facts_context_scope   ON facts(context_scope);
CREATE INDEX IF NOT EXISTS idx_facts_source_tag      ON facts(source_tag);
CREATE INDEX IF NOT EXISTS idx_facts_lifecycle       ON facts(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_facts_timestamp       ON facts(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_entity_profiles_device ON entity_profiles(device_id);
"""

VALID_LIFECYCLE = frozenset({"active", "frozen", "archived"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class MemoryStore:
    """三层图谱：Entity (entity_profiles) + Fact (facts) CRUD。

    延迟初始化——首次操作时自动建表。
    """

    def __init__(self, db_path: str = "data/coherence.db"):
        self._db_path = db_path
        self._tables_ready = False

    # ── 建表 ──────────────────────────────────────────────────────

    def create_tables(self) -> None:
        """建表 + 索引（幂等）。"""
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(ENTITY_TABLE_SQL)
            conn.executescript(FACTS_TABLE_SQL)
            conn.executescript(INDEXES_SQL)
            conn.commit()
            self._tables_ready = True
        except Exception:
            _logger.warning("MemoryStore: create_tables failed", exc_info=True)
        finally:
            conn.close()

    def _ensure_tables(self) -> None:
        if not self._tables_ready:
            self.create_tables()

    # ── Entity 层 ──────────────────────────────────────────────────

    def upsert_entity(
        self,
        entity_id: str,
        timeline: list | None = None,
        session_tags: list | None = None,
        device_id: str | None = None,
    ) -> None:
        """存在即 UPDATE（仅更新非 None 字段），不存在即 INSERT。"""
        self._ensure_tables()
        now = _utc_now()
        existing = self.get_entity(entity_id)
        conn = self._connect()
        try:
            if existing:
                conn.execute(
                    """UPDATE entity_profiles
                       SET timeline       = COALESCE(?, timeline),
                           session_tags   = COALESCE(?, session_tags),
                           device_id      = COALESCE(?, device_id),
                           updated_at_utc = ?
                       WHERE entity_id = ?""",
                    (
                        json.dumps(timeline, ensure_ascii=False) if timeline is not None else None,
                        json.dumps(session_tags, ensure_ascii=False) if session_tags is not None else None,
                        device_id,
                        now,
                        entity_id,
                    ),
                )
            else:
                t = json.dumps(timeline or [], ensure_ascii=False)
                s = json.dumps(session_tags or [], ensure_ascii=False)
                conn.execute(
                    """INSERT INTO entity_profiles
                       (entity_id, timeline, session_tags, device_id, created_at_utc, updated_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (entity_id, t, s, device_id, now, now),
                )
            conn.commit()
        except Exception:
            _logger.warning("MemoryStore: upsert_entity failed", exc_info=True)
        finally:
            conn.close()

    def get_entity(self, entity_id: str) -> dict | None:
        """按 entity_id 检索，不存在返回 None。"""
        self._ensure_tables()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM entity_profiles WHERE entity_id = ?", (entity_id,)
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            _logger.warning("MemoryStore: get_entity failed", exc_info=True)
            return None
        finally:
            conn.close()

    # ── Fact 层 ────────────────────────────────────────────────────

    def insert_fact(
        self,
        fact_id: str,
        claim: str,
        confidence: float,
        ttl_seconds: int | None = None,
        context_scope: str | None = None,
        source_tag: str = "rule",
    ) -> None:
        """插入新事实。confidence clamp [0,1]，ttl_seconds 负值取绝对值。"""
        self._ensure_tables()
        confidence = max(0.0, min(1.0, confidence))
        if ttl_seconds is not None and ttl_seconds < 0:
            ttl_seconds = abs(ttl_seconds)
        now = _utc_now()
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO facts
                   (fact_id, claim, confidence, timestamp_utc, ttl_seconds,
                    context_scope, source_tag, lifecycle_status, created_at_utc, updated_at_utc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
                (fact_id, claim, confidence, now, ttl_seconds,
                 context_scope, source_tag, now, now),
            )
            conn.commit()
        except Exception:
            _logger.warning("MemoryStore: insert_fact failed", exc_info=True)
        finally:
            conn.close()

    def get_fact(self, fact_id: str) -> dict | None:
        """按 fact_id 精确检索。"""
        self._ensure_tables()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            _logger.warning("MemoryStore: get_fact failed", exc_info=True)
            return None
        finally:
            conn.close()

    def query_facts(
        self,
        context_scope: str | None = None,
        source_tag: str | None = None,
        lifecycle_status: str = "active",
        limit: int = 20,
    ) -> list[dict]:
        """多条件 AND 查询。按 timestamp_utc DESC 排序。"""
        self._ensure_tables()
        conn = self._connect()
        try:
            where = ["lifecycle_status = ?"]
            params: list = [lifecycle_status]
            if context_scope is not None:
                where.append("context_scope = ?")
                params.append(context_scope)
            if source_tag is not None:
                where.append("source_tag = ?")
                params.append(source_tag)
            sql = ("SELECT * FROM facts WHERE " + " AND ".join(where)
                   + " ORDER BY timestamp_utc DESC LIMIT ?")
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            _logger.warning("MemoryStore: query_facts failed", exc_info=True)
            return []
        finally:
            conn.close()

    def update_fact_lifecycle(self, fact_id: str, new_status: str) -> None:
        """更新生命周期。非法值抛 ValueError。"""
        if new_status not in VALID_LIFECYCLE:
            raise ValueError(
                f"lifecycle_status must be one of {sorted(VALID_LIFECYCLE)}, got '{new_status}'"
            )
        self._ensure_tables()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE facts SET lifecycle_status=?, updated_at_utc=? WHERE fact_id=?",
                (new_status, _utc_now(), fact_id),
            )
            conn.commit()
        except Exception:
            _logger.warning("MemoryStore: update_fact_lifecycle failed", exc_info=True)
        finally:
            conn.close()

    def expire_facts(self) -> int:
        """扫描 ttl_seconds NOT NULL 的记录，将已过期的归档。

        Returns: 过期记录条数。
        """
        self._ensure_tables()
        now_ts = datetime.now(timezone.utc).timestamp()
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT fact_id, timestamp_utc, ttl_seconds FROM facts
                   WHERE ttl_seconds IS NOT NULL AND lifecycle_status = 'active'"""
            ).fetchall()
            expired_ids = []
            for row in rows:
                ts = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00")).timestamp()
                if ts + row["ttl_seconds"] < now_ts:
                    expired_ids.append(row["fact_id"])
            for fid in expired_ids:
                conn.execute(
                    "UPDATE facts SET lifecycle_status='archived', updated_at_utc=? WHERE fact_id=?",
                    (_utc_now(), fid),
                )
            conn.commit()
            return len(expired_ids)
        except Exception:
            _logger.warning("MemoryStore: expire_facts failed", exc_info=True)
            return 0
        finally:
            conn.close()

    # ── V18.8 双账本：event_tags 注解表 ───────────────────────────

    def _create_event_tags_table(self, conn) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS event_tags (
                tag_id         TEXT PRIMARY KEY,
                trace_id       TEXT NOT NULL,
                ledger_type    TEXT NOT NULL CHECK(ledger_type IN ('performance','learning')),
                session_id     TEXT,
                action_type    TEXT,
                no_assist_score REAL,
                created_at_utc TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_event_tags_type ON event_tags(ledger_type);
            CREATE INDEX IF NOT EXISTS idx_event_tags_trace ON event_tags(trace_id);
        """)

    def tag_event(
        self,
        tag_id: str,
        trace_id: str,
        ledger_type: str,
        session_id: str | None = None,
        action_type: str | None = None,
        no_assist_score: float | None = None,
    ) -> None:
        """注解一个事件属于 performance 或 learning 账本。"""
        if ledger_type not in ("performance", "learning"):
            raise ValueError(f"ledger_type must be 'performance' or 'learning', got '{ledger_type}'")
        self._ensure_tables()
        conn = self._connect()
        try:
            self._create_event_tags_table(conn)
            conn.execute(
                """INSERT OR REPLACE INTO event_tags
                   (tag_id, trace_id, ledger_type, session_id, action_type, no_assist_score, created_at_utc)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tag_id, trace_id, ledger_type, session_id, action_type, no_assist_score, _utc_now()),
            )
            conn.commit()
        except Exception:
            _logger.warning("MemoryStore: tag_event failed", exc_info=True)
        finally:
            conn.close()

    def query_events_by_type(
        self,
        ledger_type: str,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """按账本类型查询事件注解。"""
        conn = self._connect()
        try:
            self._create_event_tags_table(conn)
            clauses = ["ledger_type = ?"]
            params: list = [ledger_type]
            if session_id is not None:
                clauses.append("session_id = ?")
                params.append(session_id)
            base = "SELECT * FROM event_tags WHERE " + " AND ".join(clauses)
            base += " ORDER BY created_at_utc DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(base, params).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            _logger.warning("MemoryStore: query_events_by_type failed", exc_info=True)
            return []
        finally:
            conn.close()

    def get_type_stats(self, session_id: str | None = None, limit: int = 50) -> dict:
        """统计 performance 和 learning 两账本的度量均值。

        Returns: {"performance": {"avg_score": float, "count": int},
                   "learning": {"avg_score": float, "count": int}}
        """
        stats = {
            "performance": {"avg_score": 0.0, "count": 0},
            "learning": {"avg_score": 0.0, "count": 0},
        }
        conn = self._connect()
        try:
            self._create_event_tags_table(conn)
            for lt in ("performance", "learning"):
                clauses = ["ledger_type = ?", "no_assist_score IS NOT NULL"]
                params = [lt]
                if session_id is not None:
                    clauses.append("session_id = ?")
                    params.append(session_id)
                base = "SELECT no_assist_score FROM event_tags WHERE " + " AND ".join(clauses)
                base += " ORDER BY created_at_utc DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(base, params).fetchall()
                scores = [r["no_assist_score"] for r in rows if r["no_assist_score"] is not None]
                if scores:
                    stats[lt]["avg_score"] = round(sum(scores) / len(scores), 4)
                    stats[lt]["count"] = len(scores)
        except Exception:
            _logger.warning("MemoryStore: get_type_stats failed", exc_info=True)
        finally:
            conn.close()
        return stats

    # ── 内部 ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
