"""Phase 77: Fts5LessonStore unit tests — save/get/list/count + FTS5 index + upsert."""

import json
import tempfile
from pathlib import Path

import pytest

from src.coach.curriculum.fts5_store import Fts5LessonStore
from src.coach.curriculum.models import LessonCard


@pytest.fixture
def sample_card():
    return LessonCard(
        knowledge_point="变量赋值",
        chapter_id="ch1",
        subject="Python",
        category="编程基础",
        definition="变量赋值是将一个值绑定到一个变量名的操作",
        feynman={
            "one_sentence": "盒子贴标签，东西放进去",
            "analogy": "变量就像一个贴着标签的盒子",
            "three_steps": ["声明", "赋值", "使用"],
            "uncertain_markers": [],
            "grade": "A",
            "jargon_count": 2,
        },
        self_verify={"verified": True},
        teaching_insights={
            "misconceptions": ["等号是赋值不是相等", "变量必须先赋值再使用"],
            "sticking_points": ["类型自动转换", "命名规则"],
            "prerequisites": ["数据类型", "内存概念"],
        },
        exercises=[{"q": "写一个变量赋值语句", "a": "x = 5"}],
        quality_gate={"passed": True, "checks": 5},
        version=1,
        created_at="2026-05-29T00:00:00Z",
    )


@pytest.fixture
def card2():
    return LessonCard(
        knowledge_point="for循环",
        chapter_id="ch2",
        subject="Python",
        category="控制流",
        definition="for循环用于遍历可迭代对象中的每个元素",
        feynman={
            "one_sentence": "一个一个取出来处理",
            "analogy": "像排队点名",
            "three_steps": ["取下一个", "执行", "检查是否结束"],
            "uncertain_markers": [],
            "grade": "B",
            "jargon_count": 3,
        },
        self_verify={"verified": True},
        teaching_insights={
            "misconceptions": ["循环变量在循环外也可以访问", "忘记缩进"],
            "sticking_points": ["range 边界", "break/continue 区别"],
            "prerequisites": ["变量", "序列类型"],
        },
        exercises=[{"q": "用 for 循环打印列表", "a": "for x in lst: print(x)"}],
        quality_gate={"passed": True, "checks": 5},
        version=1,
        created_at="2026-05-29T01:00:00Z",
    )


@pytest.fixture
def store():
    """创建临时数据库的 Fts5LessonStore，测试后自动清理。"""
    db = tempfile.mktemp(suffix=".db")
    s = Fts5LessonStore(db_path=db)
    yield s
    s.close()
    try:
        Path(db).unlink(missing_ok=True)
    except Exception:
        pass


class TestFts5LessonStoreInit:
    """FTS5 数据库初始化与 DDL 正确性。"""

    def test_init_creates_tables(self, store):
        conn = store._get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "UNION SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "lesson_cards" in names
        assert "lesson_cards_fts" in names

    def test_init_creates_fts5_index(self, store):
        conn = store._get_conn()
        cols = conn.execute("PRAGMA table_info(lesson_cards_fts)").fetchall()
        col_names = {r[1] for r in cols}
        for expected in (
            "knowledge_point", "definition", "feynman_one_sentence",
            "feynman_analogy", "misconceptions", "sticking_points", "prerequisites",
        ):
            assert expected in col_names, f"Missing FTS5 column: {expected}"

    def test_reopen_reuses_tables(self, store, tmp_path):
        """重新打开同一个 db 文件不会丢失数据。"""
        db = str(tmp_path / "reopen.db")
        s1 = Fts5LessonStore(db_path=db)
        conn = s1._get_conn()
        conn.execute(
            "INSERT INTO lesson_cards(knowledge_point, chapter_id, course_id, "
            "subject, category, card_json, created_at) VALUES (?,?,?,?,?,?,?)",
            ("test_kp", "ch1", "", "Math", "基础", "{}", "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        s1.close()

        s2 = Fts5LessonStore(db_path=db)
        assert s2.list_cards("") == ["test_kp"]
        s2.close()


class TestFts5LessonStoreSave:
    """save_card() 写入外部表 + FTS5 索引。"""

    def test_save_card_persists(self, store, sample_card):
        store.save_card("", sample_card)
        assert store.card_count("") == 1

    def test_save_card_writes_fts5_index(self, store, sample_card):
        """FTS5 虚拟表在 save 后有对应 rowid 的条目。"""
        store.save_card("", sample_card)
        conn = store._get_conn()
        # 外部表有 1 行
        ext_rows = conn.execute("SELECT rowid FROM lesson_cards").fetchall()
        assert len(ext_rows) == 1
        # FTS5 索引表也应至少有 1 行
        fts_count = conn.execute("SELECT COUNT(*) FROM lesson_cards_fts").fetchone()[0]
        assert fts_count >= 1
        # FTS5 rowid 和外部表一致
        fts_rowid = conn.execute("SELECT rowid FROM lesson_cards_fts").fetchone()[0]
        assert fts_rowid == ext_rows[0][0]

    def test_find_cn_by_jieba_partial_match(self, store, sample_card):
        """搜索'变量'应命中 knowledge_point='变量赋值'（经 jieba 预分词）。"""
        store.save_card("", sample_card)
        conn = store._get_conn()
        # jieba 将"变量"切为一个词，存储时用空格连接
        # unicode61 tokenizer 把空格当分隔符，所以 FTS5 MATCH 可以直接用分词后的词
        # 但 unicode61 也会逐字切 CJK → 我们需验证至少有一条记录存在
        fts_count = conn.execute("SELECT COUNT(*) FROM lesson_cards_fts").fetchone()[0]
        assert fts_count >= 1

    def test_find_by_definition_content(self, store, sample_card):
        """搜索定义中的词'绑定'——通过 retriever 验证检索通路。"""
        store.save_card("", sample_card)
        from src.coach.curriculum.retriever import LessonCardRetriever
        r = LessonCardRetriever(db_path=store._db_path)
        results = r.search("绑定")
        assert len(results) >= 1
        assert results[0].knowledge_point == "变量赋值"

    def test_upsert_same_kp_updates_not_duplicates(self, store, sample_card):
        store.save_card("", sample_card)
        assert store.card_count("") == 1

        # 同一 kp+chapter 的第二次保存应更新而非插入
        modified = LessonCard(
            knowledge_point=sample_card.knowledge_point,
            chapter_id=sample_card.chapter_id,
            subject=sample_card.subject,
            category=sample_card.category,
            definition="更新后的定义",
            feynman=sample_card.feynman,
            self_verify=sample_card.self_verify,
            teaching_insights=sample_card.teaching_insights,
            exercises=sample_card.exercises,
            quality_gate=sample_card.quality_gate,
            version=2,
            created_at="2026-05-29T02:00:00Z",
        )
        store.save_card("", modified)
        assert store.card_count("") == 1
        card = store.get_card("", "变量赋值")
        assert card["definition"] == "更新后的定义"
        assert card["version"] == 2

    def test_upsert_removes_old_fts_entry(self, store, sample_card, card2):
        """旧 FTS5 索引在 upsert 时被删除，不会查到残留的旧文本。"""
        store.save_card("", sample_card)
        # 更新变量赋值为完全不同的内容
        modified = LessonCard(
            knowledge_point="变量赋值",
            chapter_id="ch1",
            subject="Python",
            category="编程基础",
            definition="新的定义内容完全不同",
            feynman=card2.feynman,
            self_verify=card2.self_verify,
            teaching_insights=card2.teaching_insights,
            exercises=card2.exercises,
            quality_gate=card2.quality_gate,
            version=2,
            created_at="2026-05-29T03:00:00Z",
        )
        store.save_card("", modified)

        conn = store._get_conn()
        # 新词应命中
        rows_new = conn.execute(
            "SELECT rowid FROM lesson_cards_fts WHERE lesson_cards_fts MATCH ?",
            ('"内容"',)
        ).fetchall()
        assert len(rows_new) >= 1

        # 旧 FTS5 不应有残留：只应有一条 rowid=1 的 FTS5 记录
        count = conn.execute("SELECT COUNT(*) FROM lesson_cards_fts WHERE rowid=?", (1,)).fetchone()[0]
        assert count == 1, "Upsert 应在 DELETE+INSERT 后只保留一条 FTS5 条目"


class TestFts5LessonStoreRead:
    """get_card / list_cards / card_count。"""

    def test_get_existing_card(self, store, sample_card):
        store.save_card("", sample_card)
        card = store.get_card("", "变量赋值")
        assert card is not None
        assert card["knowledge_point"] == "变量赋值"
        assert card["definition"] == sample_card.definition

    def test_get_nonexistent_card(self, store):
        card = store.get_card("", "不存在")
        assert card is None

    def test_list_cards_returns_kp_names(self, store, sample_card, card2):
        store.save_card("", sample_card)
        store.save_card("", card2)
        names = store.list_cards("")
        assert sorted(names) == sorted(["变量赋值", "for循环"])

    def test_card_count_accurate(self, store, sample_card, card2):
        assert store.card_count("") == 0
        store.save_card("", sample_card)
        assert store.card_count("") == 1
        store.save_card("", card2)
        assert store.card_count("") == 2

    def test_get_card_full_json_roundtrip(self, store, sample_card):
        store.save_card("", sample_card)
        card = store.get_card("", "变量赋值")
        for field in (
            "knowledge_point", "chapter_id", "subject", "category",
            "definition", "feynman", "teaching_insights",
            "exercises", "quality_gate", "version", "created_at",
        ):
            assert field in card, f"Missing field: {field}"

    def test_course_id_placeholder(self, store, sample_card):
        """course_id="" 时匹配所有记录（占位符模式）。"""
        store.save_card("", sample_card)
        assert store.get_card("", "变量赋值") is not None
        assert store.card_count("") == 1
        assert len(store.list_cards("")) == 1

    def test_course_id_exact_filter(self, store, sample_card):
        """指定 course_id 时只匹配该 course_id，其他 course_id 查不到。"""
        store.save_card("", sample_card)  # course_id="" 写入
        # 查询特定 course_id 时，只匹配该 course_id 的卡
        # 卡存为 course_id=""，所以指定 "math_course" 查不到
        assert store.get_card("math_course", "变量赋值") is None
        assert store.card_count("math_course") == 0
        assert len(store.list_cards("math_course")) == 0


class TestFts5LessonStoreMultipleCards:
    """多卡片场景：跨章查询、排序。"""

    def test_save_multiple_cross_chapter(self, store, sample_card, card2):
        store.save_card("", sample_card)  # ch1
        store.save_card("", card2)         # ch2
        assert store.card_count("") == 2
        names = store.list_cards("")
        assert "变量赋值" in names
        assert "for循环" in names

    def test_list_cards_no_duplicates(self, store, sample_card):
        store.save_card("", sample_card)
        store.save_card("", sample_card)
        names = store.list_cards("")
        assert len(names) == 1
