"""Evidence Ledger 数据库层 — SQLite append-only event store."""

import sqlite3
import os
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_hash      TEXT    NOT NULL UNIQUE,
    prev_hash       TEXT    NOT NULL,
    chain_height    INTEGER NOT NULL CHECK(chain_height >= 0),

    -- P0 fields (blocking)
    trace_id        TEXT    NOT NULL,
    policy_version  TEXT    NOT NULL,
    counterfactual_ranker_version        TEXT NOT NULL,
    counterfactual_feature_schema_version TEXT NOT NULL,

    -- P1 fields (monitored)
    objective_weights_snapshot           TEXT DEFAULT NULL,
    tradeoff_reason                      TEXT DEFAULT NULL,
    protected_metric_guardrail_hit       INTEGER DEFAULT 0,
    used_fact_ids                        TEXT DEFAULT NULL,
    ignored_fact_ids_with_reason          TEXT DEFAULT NULL,
    degradation_path                     TEXT DEFAULT NULL,
    counterfactual_policy_rank           INTEGER DEFAULT NULL,
    assignment_features                  TEXT DEFAULT NULL,
    eligibility_rule_id                  TEXT DEFAULT NULL,
    meta_conflict_score                  REAL DEFAULT NULL,
    track_disagreement_level             REAL DEFAULT NULL,
    meta_conflict_alert_flag             INTEGER DEFAULT 0,

    -- Window fields
    event_time_utc         TEXT    NOT NULL,
    window_id              TEXT    NOT NULL,
    window_schema_version  TEXT    NOT NULL DEFAULT '1.0.0'

);

-- 索引
CREATE INDEX IF NOT EXISTS idx_events_chain_height ON events(chain_height);
CREATE UNIQUE INDEX IF NOT EXISTS uq_events_chain_height ON events(chain_height);
CREATE INDEX IF NOT EXISTS idx_events_event_hash  ON events(event_hash);
CREATE INDEX IF NOT EXISTS idx_events_window_id   ON events(window_id);
CREATE INDEX IF NOT EXISTS idx_events_trace_id    ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_event_time  ON events(event_time_utc);

-- 触发器：禁止 UPDATE
CREATE TRIGGER IF NOT EXISTS trg_events_no_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(FAIL, 'events table is append-only: UPDATE not allowed');
END;

-- 触发器：禁止 DELETE
CREATE TRIGGER IF NOT EXISTS trg_events_no_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(FAIL, 'events table is append-only: DELETE not allowed');
END;
"""


class LedgerDB:
    """SQLite 数据库连接管理 + schema 初始化。"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def initialize(self) -> None:
        """创建数据库文件、表结构和触发器。"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def is_initialized(self) -> bool:
        """检查数据库是否已初始化。"""
        if not os.path.exists(self.db_path):
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
