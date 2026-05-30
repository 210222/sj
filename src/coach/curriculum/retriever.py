"""LessonCardRetriever — FTS5 语义检索备课卡片。Phase 77。

CLI 入口: python -m src.coach.curriculum.retriever query "变量"
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

try:
    import jieba
    _JIEBA_OK = True
except ImportError:
    _JIEBA_OK = False


@dataclass
class SearchResult:
    knowledge_point: str
    chapter_id: str
    subject: str
    category: str
    snippet: str
    score: float
    card: dict
    source_label: str = "[卡片参考]"


class LessonCardRetriever:
    """FTS5 关键词检索备课卡片。jieba 分词查询 + bm25 加权排序。"""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_dir = str(
                Path(__file__).resolve().parent.parent.parent.parent
                / "data"
            )
            db_path = str(Path(db_dir) / "lesson_cards.db")
        self._db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Return a read-only connection. Currently creates a new connection per
        query — sufficient for CLI and single-shot use. When this retriever is
        wired into the coaching hot path, consider connection pooling or reusing
        the Fts5LessonStore connection."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA read_uncommitted=ON")
        return conn

    def search(self, query: str, top_n: int = 5) -> list[SearchResult]:
        """FTS5关键词检索。jieba分词→MATCH→bm25排序。"""
        conn = self._get_conn()
        try:
            fts_query = self._build_fts_query(query)
            bm25_weights = "0.0, 5.0, 3.0, 1.0, 1.0, 1.0, 1.0, 1.0"

            sql = f"""
                SELECT lc.knowledge_point, lc.chapter_id, lc.subject, lc.category,
                       snippet(lesson_cards_fts, 0, '<b>', '</b>', '...', 40) AS snippet,
                       bm25(lesson_cards_fts, {bm25_weights}) AS score,
                       lc.card_json
                FROM lesson_cards_fts
                JOIN lesson_cards lc ON lc.rowid = lesson_cards_fts.rowid
                WHERE lesson_cards_fts MATCH ?
                ORDER BY score
                LIMIT ?
            """
            rows = conn.execute(sql, (fts_query, top_n)).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

        results = []
        for row in rows:
            try:
                card = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                card = {}
            results.append(SearchResult(
                knowledge_point=row[0],
                chapter_id=row[1],
                subject=row[2],
                category=row[3],
                snippet=row[4],
                score=float(row[5]) if row[5] else 0.0,
                card=card,
            ))
        return results

    def _build_fts_query(self, query: str) -> str:
        """构建 FTS5 MATCH 查询字符串。jieba分词→双引号短语→OR连接。"""
        if _JIEBA_OK:
            words = [w.strip() for w in jieba.cut(query) if len(w.strip()) >= 1]
        else:
            words = list(query.replace(" ", ""))
        # FTS5 MATCH: 每个词用双引号包裹（tokenize=simple 下精确短语匹配）
        return " OR ".join(f'"{w}"' for w in words) if words else query


# ── CLI 入口 ──

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3 or sys.argv[1] != "query":
        print("用法: python -m src.coach.curriculum.retriever query \"关键词\"")
        sys.exit(1)

    query = sys.argv[2]
    retriever = LessonCardRetriever()
    results = retriever.search(query, top_n=5)

    print(f"搜索: {query} → {len(results)} 条结果\n")
    for r in results:
        print(f"  [{r.score:.2f}] {r.knowledge_point} ({r.chapter_id}/{r.subject})")
        print(f"        {r.snippet[:120]}")
        print()
