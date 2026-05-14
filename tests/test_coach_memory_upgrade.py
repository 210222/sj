"""S2.3 SessionMemory SQLite + FTS5 升级测试。"""

import os
import tempfile
import time
import pytest
from src.coach.memory import SessionMemory


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="coach_mem_test_")
    os.close(fd)
    yield path
    # cleanup
    try:
        os.unlink(path)
    except PermissionError:
        pass
    # also remove WAL/SHM
    for ext in ("-wal", "-shm"):
        try:
            os.unlink(path + ext)
        except FileNotFoundError:
            pass


class TestPersistAndRecall:
    def test_store_and_recall_persistent(self, db_path):
        m1 = SessionMemory(db_path=db_path)
        m1.store("s1", {"intent": "学习Python", "action_type": "scaffold",
                         "user_input": "教我Python", "safety_allowed": True})
        # 新实例应能召回
        m2 = SessionMemory(db_path=db_path)
        results = m2.recall("Python")
        assert len(results) >= 1
        assert results[0]["intent"] == "学习Python"

    def test_recall_signature_unchanged(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {"intent": "挑战", "action_type": "challenge",
                        "user_input": "给我个难题"})
        results = m.recall("挑战")
        assert isinstance(results, list)
        assert len(results) >= 1
        r = results[0]
        assert "intent" in r
        assert "data" in r
        assert "ts" in r

    def test_empty_db_recall(self, db_path):
        m = SessionMemory(db_path=db_path)
        results = m.recall("nothing")
        assert results == []


class TestFTS5OrFallback:
    def test_recall_fts_keyword_chinese(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {"intent": "学习Python编程", "user_input": "如何调试Python代码"})
        results = m.recall("编程")
        assert len(results) >= 1

    def test_recall_general_returns_recent(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {"intent": "first"})
        time.sleep(0.1)
        m.store("s1", {"intent": "second"})
        results = m.recall("general", limit=2)
        assert len(results) == 2
        # 最新在前
        assert results[0]["intent"] == "second"

    def test_recall_limit_respected(self, db_path):
        m = SessionMemory(db_path=db_path)
        for i in range(10):
            m.store("s1", {"intent": f"test_{i}"})
        results = m.recall("general", limit=3)
        assert len(results) == 3


class TestAIResponseRoundtrip:
    """Phase 31: ai_response 端到端闭环."""

    def test_store_and_recall_ai_response(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {
            "intent": "学习Python",
            "action_type": "scaffold",
            "user_input": "for循环怎么用",
            "ai_response": "for循环遍历可迭代对象，每次取一个元素",
        })
        results = m.recall("general")
        assert len(results) >= 1
        data = results[0]["data"]
        assert "ai_response" in data
        assert len(data["ai_response"]) > 10

    def test_ai_response_defaults_empty(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {"intent": "test", "user_input": "hello"})
        results = m.recall("general")
        data = results[0]["data"]
        assert data["ai_response"] == ""

    def test_ai_response_new_instance_reads_back(self, db_path):
        m1 = SessionMemory(db_path=db_path)
        m1.store("s1", {
            "intent": "反思",
            "action_type": "reflect",
            "user_input": "我不太明白",
            "ai_response": "让我们换个角度——把这个概念想象成...",
        })
        m2 = SessionMemory(db_path=db_path)
        results = m2.recall("反思")
        data = results[0]["data"]
        assert data["ai_response"] == "让我们换个角度——把这个概念想象成..."


class TestPromoteToFact:
    def test_promote_creates_fact(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {"intent": "学习Python", "action_type": "scaffold"})
        fact_id = m.promote_to_fact("s1", 0, "用户需要Python学习支持", 0.8, 3600,
                                    "domain:programming")
        assert fact_id.startswith("fact_")
        assert len(fact_id) == 17  # fact_ + 12 hex

    def test_promote_nonexistent_turn_raises(self, db_path):
        m = SessionMemory(db_path=db_path)
        with pytest.raises(ValueError, match="Turn not found"):
            m.promote_to_fact("ghost_session", 999, "claim")

    def test_promote_to_fact_then_query(self, db_path):
        m = SessionMemory(db_path=db_path)
        m.store("s1", {"intent": "反思"})
        fid = m.promote_to_fact("s1", 0, "用户有反思习惯", 0.9, scope="general")
        fact = m._facts.get_fact(fid)
        assert fact is not None
        assert fact["claim"] == "用户有反思习惯"
        assert fact["confidence"] == 0.9
