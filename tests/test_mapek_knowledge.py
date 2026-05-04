"""S6.4 MAPE-K Knowledge 测试 — 8 tests。"""

import time
import pytest
from datetime import datetime, timezone
from src.mapek.knowledge import Knowledge


class TestKnowledgeFacts:
    def test_add_and_get_fact(self):
        k = Knowledge()
        fid = k.add_fact({"claim": "User prefers short sessions",
                          "source_tag": "user_history"})
        assert k.get_fact(fid) is not None

    def test_query_by_source_tag(self):
        k = Knowledge()
        k.add_fact({"claim": "A", "source_tag": "rule"})
        k.add_fact({"claim": "B", "source_tag": "hypothesis"})
        results = k.query_facts({"source_tag": "rule"})
        assert len(results) == 1
        assert results[0]["claim"] == "A"

    def test_update_fact(self):
        k = Knowledge()
        fid = k.add_fact({"claim": "Old claim"})
        k.update_fact(fid, {"claim": "New claim"})
        assert k.get_fact(fid)["claim"] == "New claim"

    def test_update_nonexistent_fact(self):
        k = Knowledge()
        assert k.update_fact("nonexistent", {"claim": "X"}) is False


class TestStrategyHistory:
    def test_record_and_retrieve(self):
        k = Knowledge()
        k.record_strategy({"target_action_type": "probe", "intensity": "low"})
        history = k.get_strategy_history()
        assert len(history) == 1
        assert history[0]["target_action_type"] == "probe"


class TestConfidenceManagement:
    def test_decay_reduces_confidence(self):
        k = Knowledge(confidence_decay_rate=0.1)
        fid = k.add_fact({"claim": "Test", "confidence": 0.9})
        k.decay_confidence()
        assert k.get_fact(fid)["confidence"] == 0.8

    def test_archive_expired_by_ttl(self):
        k = Knowledge()
        old = datetime.now(timezone.utc).isoformat()
        fid = k.add_fact({"claim": "Old fact", "timestamp_utc": old,
                          "ttl_seconds": 1})
        time.sleep(1.1)
        count = k.archive_expired()
        assert count >= 1
        assert k.get_fact(fid)["lifecycle_status"] == "archived"


class TestStats:
    def test_stats_counts(self):
        k = Knowledge()
        k.add_fact({"claim": "A"})
        k.add_fact({"claim": "B"})
        k.record_strategy({"action": "probe"})
        s = k.stats()
        assert s["total_facts"] == 2
        assert s["strategy_records"] == 1
