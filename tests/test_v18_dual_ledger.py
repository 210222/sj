"""S3.3 V18.8 双账本测试。"""

import os
import tempfile
import pytest
from src.coach import CoachAgent
from src.coach.data import MemoryStore


class TestEventTagsTable:
    def test_tag_event_inserts_row(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            s = MemoryStore(db_path=path)
            s.create_tables()
            s.tag_event("t1", "trace_abc", "performance", session_id="s1",
                        action_type="challenge", no_assist_score=0.8)
            results = s.query_events_by_type("performance")
            assert len(results) >= 1
            assert results[0]["tag_id"] == "t1"
            assert results[0]["ledger_type"] == "performance"
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try: os.unlink(p)
                except FileNotFoundError: pass

    def test_learning_type_separate(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            s = MemoryStore(db_path=path)
            s.create_tables()
            s.tag_event("tl", "trace_learn", "learning", no_assist_score=0.6)
            s.tag_event("tp", "trace_perf", "performance", no_assist_score=0.8)
            assert len(s.query_events_by_type("learning")) == 1
            assert len(s.query_events_by_type("performance")) == 1
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try: os.unlink(p)
                except FileNotFoundError: pass

    def test_invalid_ledger_type_raises(self):
        s = MemoryStore(db_path=":memory:")
        with pytest.raises(ValueError, match="ledger_type"):
            s.tag_event("tx", "tx", "invalid_type")

    def test_get_type_stats(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            s = MemoryStore(db_path=path)
            s.create_tables()
            s.tag_event("t1", "t1", "performance", no_assist_score=0.9)
            s.tag_event("t2", "t2", "performance", no_assist_score=0.7)
            s.tag_event("t3", "t3", "learning", no_assist_score=0.5)
            s.tag_event("t4", "t4", "learning", no_assist_score=0.3)
            stats = s.get_type_stats()
            assert stats["performance"]["count"] == 2
            assert stats["learning"]["count"] == 2
            assert stats["performance"]["avg_score"] == pytest.approx(0.8)
            assert stats["learning"]["avg_score"] == pytest.approx(0.4)
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try: os.unlink(p)
                except FileNotFoundError: pass


class TestAssistRetraction:
    def test_assist_level_defaults_normal(self):
        agent = CoachAgent(session_id="test_al_default")
        assert agent.composer.assist_level == "normal"

    def test_record_no_assist(self):
        agent = CoachAgent(session_id="test_no_assist")
        agent.record_no_assist(0.7)
        assert agent._no_assist_scores == [0.7]

    def test_retraction_applies_when_perf_high_learn_low(self):
        """perf avg > 0.7且 learning avg < 0.5 → assist reduced。"""
        agent = CoachAgent(session_id="test_retraction")
        s = agent.memory._facts
        s.tag_event("tp1", "tp1", "performance", session_id=agent.session_id,
                     no_assist_score=0.8)
        s.tag_event("tp2", "tp2", "performance", session_id=agent.session_id,
                     no_assist_score=0.9)
        s.tag_event("tp3", "tp3", "performance", session_id=agent.session_id,
                     no_assist_score=0.85)
        s.tag_event("tl1", "tl1", "learning", session_id=agent.session_id,
                     no_assist_score=0.3)
        s.tag_event("tl2", "tl2", "learning", session_id=agent.session_id,
                     no_assist_score=0.2)
        s.tag_event("tl3", "tl3", "learning", session_id=agent.session_id,
                     no_assist_score=0.25)
        agent._check_assist_retraction()
        assert agent.composer.assist_level == "reduced"
        assert agent._assist_retraction_applied
