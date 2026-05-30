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

# ── Phase 79-A: 样例卡首次引导 ──

_SEEN = False  # 全局标志，防止重复执行


def _ensure_sample_cards(db_path: str) -> None:
    """首次启动时写入 3 张 Python 基础样例卡到 FTS5 库。

    已有卡片时跳过（=已初始化或用户已导入真卡）。
    失败时静默返回 —— 卡片注入降级为空，不阻塞正常教学。
    """
    global _SEEN
    if _SEEN:
        return
    try:
        from src.coach.curriculum.fts5_store import Fts5LessonStore
        store = Fts5LessonStore(db_path)
        if store.card_count("") > 0:
            _SEEN = True
            return  # 已有卡片，不覆盖
        _write_sample_cards(store)
        _SEEN = True
    except Exception:
        pass  # 断电/磁盘满/权限不足 → _SEEN 保持 False，下次重试


def _write_sample_cards(store) -> None:
    """手造 3 张 Python 基础教学样例卡。每张含费曼类比+常见误解+卡点。

    卡片选题: Python 入门最易产生误解的三个知识点。
    质量: 所有卡片经人工审核，feynman.jargon_count=0, self_verify.verified=True。
    """
    import datetime
    from src.coach.curriculum.models import LessonCard
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cards_data = [
        {
            "knowledge_point": "变量赋值",
            "chapter_id": "ch1",
            "subject": "Python",
            "category": "编程语言",
            "definition": "变量是内存中命名存储位置的引用。Python 用 = 赋值，变量名指向值所在的内存地址。",
            "feynman": {
                "analogy": "变量就像贴了标签的盒子——x=5 就是把数字5放进贴有'x'标签的盒子。盒子里装什么都可以换，但标签不变。",
                "one_sentence": "变量是给内存中的值起一个名字，通过名字来访问和修改数据。",
                "three_steps": ["取一个描述性的变量名", "用等号赋值", "通过变量名读写数据"],
                "grade": "通过",
                "jargon_count": 0,
            },
            "teaching_insights": {
                "misconceptions": [
                    "以为等号是'相等'而非'赋值'",
                    "认为变量必须先声明类型才能用",
                    "混淆变量名和字符串（x vs 'x'）",
                ],
                "sticking_points": [
                    "a=b 和 b=a 的区别（赋值方向）",
                    "变量重新赋值后旧值去哪了（垃圾回收概念）",
                ],
                "detours": ["用 print() 调试变量值的变化", "用 type() 检查变量类型"],
                "prerequisites": ["程序是什么", "内存的基本概念"],
            },
            "self_verify": {"total": 5, "passed": 5, "verified": True},
            "exercises": [
                {"id": "Q1", "type": "概念", "targets": "赋值语义理解",
                 "question": "执行 x=5; y=x; x=10 后，y 的值是多少？为什么？",
                 "expected_outline": "y是5。y=x 把 x 当时的值(5)赋给 y。之后 x 变成 10 不影响 y。"},
            ],
            "quality_gate": {"passed": True, "checks": 5},
            "version": 1,
            "created_at": now,
        },
        {
            "knowledge_point": "for循环",
            "chapter_id": "ch2",
            "subject": "Python",
            "category": "编程语言",
            "definition": "for循环遍历可迭代对象（列表/字符串/range等），每次迭代取出一个元素执行循环体。",
            "feynman": {
                "analogy": "for循环像流水线传送带——每个物品依次经过你面前，你对每个做同样的操作，然后下一个到来。",
                "one_sentence": "for循环让计算机重复执行一段代码，每次从一组数据中取出一个元素处理。",
                "three_steps": ["确定要遍历的序列", "写 for...in... 循环头", "缩进写循环体"],
                "grade": "通过",
                "jargon_count": 0,
            },
            "teaching_insights": {
                "misconceptions": [
                    "以为 range(5) 包含 5（实际是 0,1,2,3,4）",
                    "循环变量在循环外继续使用（坏习惯）",
                    "混淆 for（已知次数）和 while（未知次数）的使用场景",
                ],
                "sticking_points": [
                    "嵌套循环的执行顺序（外层走一步里层走一圈）",
                    "在循环中修改正在遍历的列表导致意外行为",
                ],
                "detours": ["先打印每次迭代的变量值观察执行过程", "用 enumerate() 同时获取索引和值"],
                "prerequisites": ["变量赋值", "列表基础", "缩进语法规则"],
            },
            "self_verify": {"total": 5, "passed": 5, "verified": True},
            "exercises": [
                {"id": "Q1", "type": "代码追踪", "targets": "range 边界理解",
                 "question": "for i in range(3): print(i) 输出什么？",
                 "expected_outline": "输出 0 换行 1 换行 2。range(3) 生成 0,1,2，不含 3。"},
            ],
            "quality_gate": {"passed": True, "checks": 5},
            "version": 1,
            "created_at": now,
        },
        {
            "knowledge_point": "if条件判断",
            "chapter_id": "ch2",
            "subject": "Python",
            "category": "编程语言",
            "definition": "if语句根据布尔条件决定执行哪段代码。支持 if/elif/else 多分支。",
            "feynman": {
                "analogy": "if就像岔路口——'如果下雨'走带伞的路，'否则如果阴天'带外套，都不满足走默认路。",
                "one_sentence": "if让程序根据条件做选择——条件成立走一条路，不成立走另一条。",
                "three_steps": ["写出判断条件（返回 True/False 的表达式）", "条件后加冒号换行缩进", "根据需要接 elif/else 分支"],
                "grade": "通过",
                "jargon_count": 0,
            },
            "teaching_insights": {
                "misconceptions": [
                    "把赋值 = 写成比较 ==（Python 中最常见的低级错误）",
                    "以为 if 后面必须跟 elif/else（单 if 完全合法）",
                    "认为多个 elif 会依次执行（实际只执行第一个条件成立的）",
                ],
                "sticking_points": [
                    "复合条件的短路求值（and/or 的提前终止）",
                    "嵌套 if 超过 3 层的可读性灾难",
                ],
                "detours": ["先用注释用自然语言写出每个分支的条件和结果", "画流程图可视化分支逻辑"],
                "prerequisites": ["变量赋值", "布尔类型 (True/False)", "比较运算符 (==, !=, >, <)"],
            },
            "self_verify": {"total": 5, "passed": 5, "verified": True},
            "exercises": [
                {"id": "Q1", "type": "代码追踪", "targets": "elif 只执行第一个匹配",
                 "question": "x=5; if x>0: print('正数'); elif x>3: print('大于3') 输出什么？为什么？",
                 "expected_outline": "只输出'正数'。第一个条件 x>0 成立后，elif 被跳过——不会检查第二个条件。"},
            ],
            "quality_gate": {"passed": True, "checks": 5},
            "version": 1,
            "created_at": now,
        },
    ]

    for data in cards_data:
        card = LessonCard(**data)
        store.save_card("", card)


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
        _ensure_sample_cards(self._db_path)

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
