"""Phase 13.4 — 跨会话持久化 + 难度自适应.

SQLite 存储用户画像，支持跨会话恢复学习状态。
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "user_profiles.db"


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            session_id TEXT PRIMARY KEY,
            ttm_stage TEXT DEFAULT 'contemplation',
            autonomy REAL DEFAULT 0.5,
            competence REAL DEFAULT 0.5,
            relatedness REAL DEFAULT 0.5,
            total_turns INTEGER DEFAULT 0,
            topics_covered TEXT DEFAULT '[]',
            skill_masteries TEXT DEFAULT '{}',
            difficulty_level TEXT DEFAULT 'medium',
            last_active REAL DEFAULT 0,
            created_at REAL DEFAULT 0,
            consent_status TEXT DEFAULT 'never_asked'
        )
    """)
    conn.commit()
    # Phase 17: 旧表迁移 — 添加 consent_status 列 (若缺失)
    try:
        conn.execute("ALTER TABLE profiles ADD COLUMN consent_status TEXT DEFAULT 'never_asked'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Phase 20 S20.3: 学习目标字段迁移
    for col, col_type in [("learning_goal", "TEXT"), ("current_topic", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE profiles ADD COLUMN goal_progress REAL DEFAULT 0.0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    return conn


# Phase 20 S20.1b: 历史趋势表 DDL
PROFILE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS profile_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    field_name  TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    timestamp   REAL NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profile_history_sid ON profile_history(session_id);
CREATE INDEX IF NOT EXISTS idx_profile_history_field ON profile_history(session_id, field_name);
"""


class SessionPersistence:
    """跨会话状态持久化."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.db = _get_db()
        self._ensure_row()
        # Phase 20 S20.1b: 建 profile_history 表（幂等）
        try:
            self.db.executescript(PROFILE_HISTORY_SQL)
        except Exception:
            pass

    def _ensure_row(self):
        now = time.time()
        self.db.execute(
            "INSERT OR IGNORE INTO profiles (session_id, created_at) VALUES (?, ?)",
            (self.session_id, now))
        self.db.execute(
            "UPDATE profiles SET last_active = ? WHERE session_id = ?",
            (now, self.session_id))
        self.db.commit()

    def save_ttm_stage(self, stage: str):
        old = self.load_ttm_stage()
        self.db.execute(
            "UPDATE profiles SET ttm_stage = ? WHERE session_id = ?",
            (stage, self.session_id))
        self.db.commit()
        if old != stage:
            self.save_history_snapshot("ttm_stage", old, stage)

    def load_ttm_stage(self) -> str:
        row = self.db.execute(
            "SELECT ttm_stage FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        return row[0] if row else "contemplation"

    def save_sdt_scores(self, autonomy: float, competence: float, relatedness: float):
        old = self.load_sdt_scores()
        self.db.execute(
            "UPDATE profiles SET autonomy=?, competence=?, relatedness=? WHERE session_id=?",
            (autonomy, competence, relatedness, self.session_id))
        self.db.commit()
        if old["autonomy"] != autonomy:
            self.save_history_snapshot("autonomy", str(old["autonomy"]), str(autonomy))
        if old["competence"] != competence:
            self.save_history_snapshot("competence", str(old["competence"]), str(competence))

    def load_sdt_scores(self) -> dict:
        row = self.db.execute(
            "SELECT autonomy, competence, relatedness FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        if row:
            return {"autonomy": row[0], "competence": row[1], "relatedness": row[2]}
        return {"autonomy": 0.5, "competence": 0.5, "relatedness": 0.5}

    def save_topics(self, topics: list[str]):
        self.db.execute(
            "UPDATE profiles SET topics_covered = ? WHERE session_id = ?",
            (json.dumps(topics), self.session_id))
        self.db.commit()

    def load_topics(self) -> list[str]:
        row = self.db.execute(
            "SELECT topics_covered FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return []

    def save_difficulty(self, level: str):
        old = self.load_difficulty()
        self.db.execute(
            "UPDATE profiles SET difficulty_level = ? WHERE session_id = ?",
            (level, self.session_id))
        self.db.commit()
        if old != level:
            self.save_history_snapshot("difficulty_level", old, level)

    def load_difficulty(self) -> str:
        row = self.db.execute(
            "SELECT difficulty_level FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        return row[0] if row else "medium"

    def increment_turns(self):
        self.db.execute(
            "UPDATE profiles SET total_turns = total_turns + 1, last_active = ? WHERE session_id = ?",
            (time.time(), self.session_id))
        self.db.commit()

    def get_profile(self) -> dict:
        row = self.db.execute(
            "SELECT * FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        if not row:
            return {}
        return {
            "ttm_stage": row[1], "autonomy": row[2], "competence": row[3],
            "relatedness": row[4], "total_turns": row[5],
            "topics_covered": json.loads(row[6]) if row[6] else [],
            "skill_masteries": json.loads(row[7]) if row[7] else {},
            "difficulty_level": row[8],
            # Phase 20 S20.3: 学习目标字段（防御性读取，兼容旧行）
            "learning_goal": row[12] if len(row) > 12 and row[12] else "",
            "current_topic": row[13] if len(row) > 13 and row[13] else "",
            "goal_progress": row[14] if len(row) > 14 and row[14] else 0.0,
        }

    # ── Phase 17: 知情同意持久化 ──

    def save_consent_status(self, status: str) -> None:
        """持久化 consent_status: never_asked | consented | declined."""
        self.db.execute(
            "UPDATE profiles SET consent_status = ? WHERE session_id = ?",
            (status, self.session_id))
        self.db.commit()

    def load_consent_status(self) -> str:
        """加载跨会话的 consent_status."""
        row = self.db.execute(
            "SELECT consent_status FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        return row[0] if row and row[0] else "never_asked"

    def adjust_difficulty(self, recent_correct_rate: float) -> str:
        """根据最近正确率自适应调整难度."""
        current = self.load_difficulty()
        if recent_correct_rate > 0.8 and current != "hard":
            new = "hard" if current == "medium" else "medium"
            self.save_difficulty(new)
            return new
        elif recent_correct_rate < 0.4 and current != "easy":
            new = "easy" if current == "medium" else "medium"
            self.save_difficulty(new)
            return new
        return current

    # ── Phase 20 S20.3: 学习目标 ──

    def save_learning_goal(self, goal: str) -> None:
        old = self.load_learning_goal()
        self.db.execute(
            "UPDATE profiles SET learning_goal = ? WHERE session_id = ?",
            (goal, self.session_id))
        self.db.commit()
        if old != goal:
            self.save_history_snapshot("learning_goal", old, goal)

    def load_learning_goal(self) -> str:
        row = self.db.execute(
            "SELECT learning_goal FROM profiles WHERE session_id = ?",
            (self.session_id,)).fetchone()
        return row[0] if row and row[0] else ""

    def save_current_topic(self, topic: str) -> None:
        self.db.execute(
            "UPDATE profiles SET current_topic = ? WHERE session_id = ?",
            (topic, self.session_id))
        self.db.commit()

    def save_goal_progress(self, progress: float) -> None:
        self.db.execute(
            "UPDATE profiles SET goal_progress = ? WHERE session_id = ?",
            (max(0.0, min(1.0, progress)), self.session_id))
        self.db.commit()

    # ── Phase 20 S20.1b: 历史快照 ──

    def save_history_snapshot(self, field_name: str, old_value: str, new_value: str) -> None:
        """记录一条字段变更历史到 profile_history 表。"""
        import time
        from datetime import datetime, timezone
        self.db.execute(
            """INSERT INTO profile_history
               (session_id, field_name, old_value, new_value, timestamp, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                self.session_id,
                field_name,
                str(old_value) if old_value is not None else None,
                str(new_value) if new_value is not None else None,
                time.time(),
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            ),
        )
        self.db.commit()

    def get_mastery_trend(self, field_name: str, days: int = 30) -> list[dict]:
        """查询指定字段的历史趋势。

        Returns [{"timestamp": ..., "value": ..., "created_at": ...}, ...]
        没有数据时返回 []。
        """
        import time
        cutoff = time.time() - days * 86400
        rows = self.db.execute(
            """SELECT timestamp, new_value, created_at FROM profile_history
               WHERE session_id = ? AND field_name = ? AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (self.session_id, field_name, cutoff),
        ).fetchall()
        return [
            {"timestamp": r[0], "value": r[1], "created_at": r[2]}
            for r in rows
        ]

    # Phase 23: 间隔重复 — 技能掌握度 + 距上次活动天数
    def get_skills_with_recency(self) -> dict[str, dict]:
        """从 skill_masteries JSON 读取技能掌握度 + 距上次活动天数。

        Returns: {"python_loop": {"mastery": 0.85, "days_elapsed": 12.5}, ...}
        """
        import time
        now = time.time()
        profile = self.get_profile()
        masteries = profile.get("skill_masteries", {})
        if not masteries:
            return {}

        last_ts = now
        try:
            row = self.db.execute(
                "SELECT MAX(timestamp) FROM profile_history WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()
            if row and row[0]:
                last_ts = float(row[0])
        except Exception:
            pass

        days_elapsed = max(0.0, (now - last_ts) / 86400.0)
        result = {}
        for skill_name, mastery_val in masteries.items():
            try:
                mv = float(mastery_val)
            except (ValueError, TypeError):
                mv = 0.5
            result[skill_name] = {
                "mastery": round(max(0.0, min(1.0, mv)), 4),
                "days_elapsed": round(days_elapsed, 2),
            }
        return result
