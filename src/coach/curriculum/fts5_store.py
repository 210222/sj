"""Fts5LessonStore — FTS5 全文搜索备课卡片存储。Phase 77。"""

import json
import logging
import sqlite3
from pathlib import Path

from src.coach.curriculum.store import AbstractLessonStore

try:
    import jieba
    def _tokenize(text: str) -> str:
        return " ".join(jieba.cut(text))
except ImportError:
    def _tokenize(text: str) -> str:
        return text

_logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS lesson_cards (
    rowid INTEGER PRIMARY KEY,
    knowledge_point TEXT NOT NULL,
    chapter_id TEXT NOT NULL DEFAULT '',
    course_id TEXT NOT NULL DEFAULT '',
    -- ↑ placeholder: fixed to "" until the session↔course binding layer is built (separate Phase)
    subject TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    card_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS lesson_cards_fts
USING fts5(
    knowledge_point,
    definition,
    feynman_one_sentence,
    feynman_analogy,
    misconceptions,
    sticking_points,
    prerequisites,
    tokenize='porter unicode61'
);
"""


class Fts5LessonStore(AbstractLessonStore):
    """FTS5 full-text search store for lesson cards. Implements AbstractLessonStore.

    Division of labour with memory.py FTS5:
      - memory.py ArchivalMemory → "what the student said" (conversation history)
      - this module              → "what to teach" (lesson card keyword search)
    Each manages its own SQLite connection and FTS5 virtual table.
    Results merged into context_layer will be disambiguated via source_label.

    Phase 77.1 upgrade path: ChromaLessonStore (semantic vector search)."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_dir = str(
                Path(__file__).resolve().parent.parent.parent.parent
                / "data"
            )
            Path(db_dir).mkdir(parents=True, exist_ok=True)
            db_path = str(Path(db_dir) / "lesson_cards.db")
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(DDL)
        conn.commit()

    # ── AbstractLessonStore 实现 ──

    def save_card(self, course_id: str, card) -> None:
        conn = self._get_conn()
        data = {
            "knowledge_point": card.knowledge_point,
            "chapter_id": card.chapter_id,
            "subject": card.subject,
            "category": card.category,
            "definition": card.definition,
            "feynman": card.feynman,
            "self_verify": card.self_verify,
            "teaching_insights": card.teaching_insights,
            "exercises": card.exercises,
            "quality_gate": card.quality_gate,
            "version": card.version,
            "created_at": card.created_at,
        }
        card_json = json.dumps(data, ensure_ascii=False)
        fi = card.feynman if isinstance(card.feynman, dict) else {}
        ti = card.teaching_insights if isinstance(card.teaching_insights, dict) else {}

        # 检查是否已有同 kp+chapter 的记录
        existing = conn.execute(
            "SELECT rowid FROM lesson_cards WHERE knowledge_point=? AND chapter_id=?",
            (card.knowledge_point, card.chapter_id)
        ).fetchone()

        if existing:
            rowid = existing[0]
            conn.execute(
                "UPDATE lesson_cards SET card_json=?, created_at=? WHERE rowid=?",
                (card_json, card.created_at, rowid)
            )
            conn.execute("DELETE FROM lesson_cards_fts WHERE rowid=?", (rowid,))
        else:
            conn.execute(
                "INSERT INTO lesson_cards(knowledge_point, chapter_id, course_id, subject, category, card_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (card.knowledge_point, card.chapter_id, course_id or "",
                 card.subject, card.category, card_json, card.created_at)
            )
            rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # NOTE: _tokenize() resolves to jieba.cut() at import time.
        # DDL uses tokenize='porter unicode61' which segments CJK character-by-character.
        # Under this tokenizer, jieba preprocessing has no effect on the token stream
        # (spaces don't alter unicode61 output). Retained because switching to a custom
        # jieba tokenizer (Phase 77.1) makes this preprocessing necessary, and the
        # overhead (~ms) is negligible on the card-creation cold path.

        # 写入 FTS5 索引（jieba 分词后用空格连接，配合 tokenize=simple）
        conn.execute(
            "INSERT INTO lesson_cards_fts(rowid, knowledge_point, definition, "
            "feynman_one_sentence, feynman_analogy, misconceptions, sticking_points, prerequisites) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rowid,
             _tokenize(card.knowledge_point), _tokenize(card.definition),
             _tokenize(fi.get("one_sentence", "")), _tokenize(fi.get("analogy", "")),
             _tokenize(", ".join(ti.get("misconceptions", []))),
             _tokenize(", ".join(ti.get("sticking_points", []))),
             _tokenize(", ".join(ti.get("prerequisites", []))))
        )
        conn.commit()

    def get_card(self, course_id: str, knowledge_point: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT card_json FROM lesson_cards WHERE knowledge_point=? AND (course_id=? OR ?='')",
            (knowledge_point, course_id, course_id)
        ).fetchone()
        if row:
            return json.loads(row[0])
        return None

    def list_cards(self, course_id: str) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT knowledge_point FROM lesson_cards WHERE course_id=? OR ?=''",
            (course_id, course_id)
        ).fetchall()
        return [r[0] for r in rows]

    def card_count(self, course_id: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM lesson_cards WHERE course_id=? OR ?=''",
            (course_id, course_id)
        ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
