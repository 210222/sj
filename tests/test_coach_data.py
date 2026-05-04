"""S2.2 MemoryStore 测试 — Entity + Fact CRUD + 异常路径。"""

import os
import tempfile
import time
import pytest
from src.coach.data import MemoryStore


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="coach_test_mem_")
    os.close(fd)
    s = MemoryStore(db_path=path)
    s.create_tables()
    yield s
    try:
        os.unlink(path)
    except PermissionError:
        time.sleep(0.1)
        os.unlink(path)


class TestCreateTables:
    def test_create_tables_idempotent(self, store):
        store.create_tables()  # 第二次不应抛异常

    def test_entity_table_exists(self, store):
        row = store._connect().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entity_profiles'"
        ).fetchone()
        assert row is not None

    def test_facts_table_exists(self, store):
        row = store._connect().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='facts'"
        ).fetchone()
        assert row is not None


class TestEntityUpsertGet:
    def test_upsert_new_entity(self, store):
        store.upsert_entity("u1", timeline=["2026-05-01T10:00:00Z:start"])
        e = store.get_entity("u1")
        assert e is not None
        assert e["entity_id"] == "u1"

    def test_get_nonexistent_entity(self, store):
        assert store.get_entity("ghost") is None

    def test_partial_update_device_only(self, store):
        store.upsert_entity("u2", timeline=["a"])
        store.upsert_entity("u2", device_id="dev_1")
        e = store.get_entity("u2")
        assert e["device_id"] == "dev_1"
        assert "a" in e["timeline"]  # unchanged

    def test_update_tags(self, store):
        store.upsert_entity("u3")
        store.upsert_entity("u3", session_tags=["programming", "debugging"])
        e = store.get_entity("u3")
        assert "programming" in e["session_tags"]


class TestFactCRUD:
    def test_insert_and_get(self, store):
        store.insert_fact("f1", "擅长Python", 0.8, context_scope="domain:programming")
        f = store.get_fact("f1")
        assert f is not None
        assert f["claim"] == "擅长Python"
        assert f["confidence"] == 0.8

    def test_query_by_context_scope(self, store):
        store.insert_fact("f_a", "擅长Python", 0.8, context_scope="domain:programming")
        store.insert_fact("f_b", "擅长写作", 0.6, context_scope="domain:writing")
        results = store.query_facts(context_scope="domain:programming")
        assert len(results) == 1
        assert results[0]["fact_id"] == "f_a"

    def test_query_by_source_tag(self, store):
        store.insert_fact("fs", "claim", 0.5, source_tag="user_history")
        results = store.query_facts(source_tag="user_history")
        assert len(results) == 1

    def test_confidence_clamp_high(self, store):
        store.insert_fact("fc", "overconfident", 1.5)
        f = store.get_fact("fc")
        assert f["confidence"] == 1.0

    def test_confidence_clamp_low(self, store):
        store.insert_fact("fn", "underconfident", -0.3)
        f = store.get_fact("fn")
        assert f["confidence"] == 0.0

    def test_query_returns_latest_first(self, store):
        store.insert_fact("f1", "older", 0.5)
        time.sleep(0.1)
        store.insert_fact("f2", "newer", 0.5)
        results = store.query_facts()
        assert results[0]["fact_id"] == "f2"


class TestLifecycle:
    def test_update_valid(self, store):
        store.insert_fact("fl", "claim", 0.5)
        store.update_fact_lifecycle("fl", "archived")
        f = store.get_fact("fl")
        assert f["lifecycle_status"] == "archived"
        # archived 不在默认 active 查询中
        assert len(store.query_facts()) == 0

    def test_update_invalid_raises(self, store):
        store.insert_fact("fi", "claim", 0.5)
        with pytest.raises(ValueError, match="lifecycle_status"):
            store.update_fact_lifecycle("fi", "deleted")

    def test_update_frozen(self, store):
        store.insert_fact("ff", "claim", 0.5)
        store.update_fact_lifecycle("ff", "frozen")
        assert store.get_fact("ff")["lifecycle_status"] == "frozen"


class TestExpire:
    def test_expire_archives_expired(self, store):
        store.insert_fact("fe", "ephemeral", 0.5, ttl_seconds=1)
        time.sleep(2)
        n = store.expire_facts()
        assert n >= 1
        f = store.get_fact("fe")
        assert f["lifecycle_status"] == "archived"

    def test_no_ttl_not_affected(self, store):
        store.insert_fact("fn", "persistent", 0.5)  # no ttl
        n = store.expire_facts()
        f = store.get_fact("fn")
        assert f["lifecycle_status"] == "active"


class TestErrorFallback:
    def test_bad_db_path_read(self):
        s = MemoryStore(db_path="/nonexistent/path/db.sqlite")
        # 建表/查询 应降级不崩溃
        results = s.query_facts()
        assert results == []

    def test_get_entity_fallback(self, store):
        """正常路径"""
        assert store.get_entity("nonexistent") is None
