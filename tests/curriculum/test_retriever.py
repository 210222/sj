"""Phase 77: LessonCardRetriever unit tests — FTS5 search + jieba tokenization + bm25 ranking."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.coach.curriculum.fts5_store import Fts5LessonStore, DDL
from src.coach.curriculum.models import LessonCard
from src.coach.curriculum.retriever import LessonCardRetriever, SearchResult


# ── fixtures ──

def _make_card(kp, ch, subject, category, definition, feynman_sentence, feynman_analogy,
               misconceptions=None, sticking_points=None, prerequisites=None):
    return LessonCard(
        knowledge_point=kp,
        chapter_id=ch,
        subject=subject,
        category=category,
        definition=definition,
        feynman={
            "one_sentence": feynman_sentence,
            "analogy": feynman_analogy,
            "three_steps": [],
            "uncertain_markers": [],
            "grade": "A",
            "jargon_count": 1,
        },
        self_verify={"verified": True},
        teaching_insights={
            "misconceptions": misconceptions or [],
            "sticking_points": sticking_points or [],
            "prerequisites": prerequisites or [],
        },
        exercises=[],
        quality_gate={"passed": True, "checks": 5},
        version=1,
        created_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def populated_retriever():
    """创建临时 db，写入 4 张卡片，返回 retriever。"""
    db = tempfile.mktemp(suffix=".db")
    store = Fts5LessonStore(db_path=db)

    cards = [
        _make_card("变量赋值", "ch1", "Python", "编程基础",
                   "变量赋值是将值绑定到变量名的操作", "盒子贴标签", "变量是贴了标签的盒子",
                   misconceptions=["等号是赋值不是相等", "必须先赋值再使用"],
                   sticking_points=["类型转换", "命名规则"],
                   prerequisites=["数据类型"]),
        _make_card("for循环", "ch2", "Python", "控制流",
                   "for循环遍历可迭代对象中的每个元素", "一个个取出来处理", "像排队点名",
                   misconceptions=["循环变量在循环外可访问", "忘记缩进"],
                   sticking_points=["range边界", "break和continue"],
                   prerequisites=["变量", "序列类型"]),
        _make_card("函数定义", "ch3", "Python", "函数",
                   "用def定义函数，封装可复用逻辑", "配方", "函数像一道菜的配方",
                   misconceptions=["参数和返回值混淆", "不写return默认None"],
                   sticking_points=["参数传递", "作用域"],
                   prerequisites=["变量", "控制流"]),
        _make_card("列表操作", "ch3", "Python", "数据结构",
                   "列表是可变的序列容器，支持索引切片", "数组队列", "列表像一排抽屉",
                   misconceptions=["索引从0开始不是1", "列表和元组的区别"],
                   sticking_points=["切片边界", "列表推导式"],
                   prerequisites=["变量", "for循环"]),
    ]
    for c in cards:
        store.save_card("", c)
    store.close()

    retriever = LessonCardRetriever(db_path=db)
    yield retriever, db
    try:
        Path(db).unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def empty_retriever():
    """没有任何卡片的检索器。"""
    db = tempfile.mktemp(suffix=".db")
    store = Fts5LessonStore(db_path=db)
    store.close()
    retriever = LessonCardRetriever(db_path=db)
    yield retriever, db
    try:
        Path(db).unlink(missing_ok=True)
    except Exception:
        pass


# ── tests ──

class TestLessonCardRetrieverSearch:
    """search() 核心检索功能。"""

    def test_exact_kp_match(self, populated_retriever):
        retriever, _ = populated_retriever
        results = retriever.search("变量赋值", top_n=5)
        assert len(results) >= 1
        assert results[0].knowledge_point == "变量赋值"

    def test_partial_cn_match(self, populated_retriever):
        """搜索'变量'应命中'变量赋值'。"""
        retriever, _ = populated_retriever
        results = retriever.search("变量")
        assert len(results) >= 1
        kps = {r.knowledge_point for r in results}
        assert "变量赋值" in kps

    def test_cn_group_match_cycle(self, populated_retriever):
        """搜索'循环'应命中'for循环'。"""
        retriever, _ = populated_retriever
        results = retriever.search("循环")
        assert len(results) >= 1
        assert results[0].knowledge_point == "for循环"

    def test_english_term_match(self, populated_retriever):
        """搜索'for'应命中'for循环'。"""
        retriever, _ = populated_retriever
        results = retriever.search("for")
        assert len(results) >= 1
        assert results[0].knowledge_point == "for循环"

    def test_multi_word_cn_query(self, populated_retriever):
        """搜索'变量 定义'应命中包含'变量'或'定义'的卡片。"""
        retriever, _ = populated_retriever
        results = retriever.search("变量 定义")
        assert len(results) >= 2  # 变量赋值 + 函数定义

    def test_definition_content_match(self, populated_retriever):
        """搜索定义中的词'遍历'应命中 for循环。"""
        retriever, _ = populated_retriever
        results = retriever.search("遍历")
        assert len(results) >= 1
        assert results[0].knowledge_point == "for循环"

    def test_misconception_content_match(self, populated_retriever):
        """搜索误解中的词'缩进'应命中 for循环。"""
        retriever, _ = populated_retriever
        results = retriever.search("缩进")
        assert len(results) >= 1
        assert results[0].knowledge_point == "for循环"

    def test_empty_db_returns_empty(self, empty_retriever):
        retriever, _ = empty_retriever
        results = retriever.search("变量")
        assert results == []

    def test_no_match_returns_empty(self, populated_retriever):
        """完全不相关的 ASCII 查询不应命中中文卡片。"""
        retriever, _ = populated_retriever
        results = retriever.search("xyznonexistent12345")
        assert results == []

    def test_top_n_limit(self, populated_retriever):
        """top_n=2 应截断结果。"""
        retriever, _ = populated_retriever
        results = retriever.search("Python")
        assert len([r for r in results if r.score != 0.0]) <= 5
        results = retriever.search("Python", top_n=2)
        assert len(results) <= 2


class TestSearchResultFields:
    """返回的 SearchResult 各字段正确赋值。"""

    def test_result_has_required_fields(self, populated_retriever):
        retriever, _ = populated_retriever
        results = retriever.search("变量")
        assert len(results) >= 1
        r = results[0]
        assert r.knowledge_point
        assert r.chapter_id
        assert r.subject
        assert r.category
        assert isinstance(r.score, float)
        assert r.source_label == "[卡片参考]"

    def test_snippet_contains_highlight(self, populated_retriever):
        retriever, _ = populated_retriever
        results = retriever.search("变量赋值")
        assert len(results) >= 1
        # FTS5 snippet 用 <b> 标记高亮
        assert "<b>" in results[0].snippet

    def test_card_field_is_serialized_dict(self, populated_retriever):
        retriever, _ = populated_retriever
        results = retriever.search("变量赋值")
        assert len(results) >= 1
        card = results[0].card
        assert isinstance(card, dict)
        assert "knowledge_point" in card
        assert "feynman" in card

    def test_results_ordered_by_score(self, populated_retriever):
        """同 query 下 score 低的（更相关）排前面。"""
        retriever, _ = populated_retriever
        results = retriever.search("变量")  # 只命中变量赋值 (kp 列权重 5.0)
        scores = [r.score for r in results]
        assert scores == sorted(scores), "Results should be sorted by score ascending (bm25: lower=better)"


class TestBuildFtsQuery:
    """_build_fts_query() 中文分词 → FTS5 MATCH 语法。"""

    def test_single_word_wrapped_in_quotes(self):
        retriever = LessonCardRetriever(db_path=":memory:")
        q = retriever._build_fts_query("变量")
        assert '"变量"' in q

    def test_multi_word_or_join(self):
        retriever = LessonCardRetriever(db_path=":memory:")
        q = retriever._build_fts_query("变量 循环")
        assert "OR" in q
        assert '"变量"' in q
        assert '"循环"' in q

    def test_english_word_not_split(self):
        retriever = LessonCardRetriever(db_path=":memory:")
        q = retriever._build_fts_query("for")
        assert '"for"' in q
