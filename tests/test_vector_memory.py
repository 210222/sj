"""S6.5 向量记忆升级测试 — 13 tests。"""

import os
import tempfile
import pytest
from src.coach.memory import ArchivalMemory, WorkingMemory, ReflectiveMemoryManager


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    for p in [path, path + "-wal", path + "-shm"]:
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


class TestArchivalMemory:
    def test_store_and_search(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        mid = am.store("User prefers Python over JavaScript",
                       source_tag="user_history")
        results = am.search("Python")
        assert len(results) >= 1
        assert results[0]["source_tag"] == "user_history"

    def test_search_empty_for_no_match(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        am.store("Rust is fast", source_tag="fact")
        results = am.search("Python")
        assert len(results) == 0

    def test_archive_memory(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        mid = am.store("Temporary note", source_tag="scratch")
        assert am.archive_memory(mid) is True
        results = am.search("Temporary")
        assert len(results) == 0

    def test_stats(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        am.store("Fact A", source_tag="rule")
        am.store("Fact B", source_tag="hypothesis")
        s = am.stats()
        assert s["total"] == 2
        assert s["active"] == 2


class TestWorkingMemory:
    def test_set_and_get(self):
        wm = WorkingMemory()
        wm.set("current_intent", "exploration")
        assert wm.get("current_intent") == "exploration"

    def test_get_default(self):
        wm = WorkingMemory()
        assert wm.get("nonexistent", "default_val") == "default_val"

    def test_get_all_history(self):
        wm = WorkingMemory(capacity=10)
        wm.set("score", 1)
        wm.set("score", 2)
        all_items = wm.get_all("score")
        assert len(all_items) == 2
        assert all_items[-1]["value"] == 2

    def test_clear(self):
        wm = WorkingMemory()
        wm.set("key1", "val1")
        wm.set("key2", "val2")
        wm.clear()
        assert wm.size() == 0

    def test_capacity_cap(self):
        wm = WorkingMemory(capacity=3)
        for i in range(10):
            wm.set("key", i)
        assert len(wm.get_all("key")) == 3


class TestRMM:
    def test_run_returns_counts(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        rmm = ReflectiveMemoryManager(am, archive_after_runs=1)
        am.store("Test fact", confidence=0.5)
        result = rmm.run()
        assert "decayed" in result
        assert "archived" in result
        assert "cleaned" in result


class TestWorkingMemoryExtras:
    def test_keys(self):
        wm = WorkingMemory()
        wm.set("a", 1)
        wm.set("b", 2)
        assert set(wm.keys()) == {"a", "b"}


class TestRMMExtras:
    def test_archive_after_runs_skips_early(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        rmm = ReflectiveMemoryManager(am, archive_after_runs=5)
        am.store("Test fact", confidence=0.5)
        result = rmm.run()
        assert result["decayed"] == 0

    def test_decay_reduces_confidence_in_db(self, tmp_db):
        am = ArchivalMemory(db_path=tmp_db)
        rmm = ReflectiveMemoryManager(am, decay_rate=0.1, archive_after_runs=1)
        mid = am.store("Test", confidence=0.9)
        rmm.run()
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        c = conn.execute(
            "SELECT confidence FROM archive_meta WHERE memory_id = ?", (mid,)
        ).fetchone()
        conn.close()
        assert c[0] <= 0.8
