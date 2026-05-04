"""S5.2 跨轨一致性检查测试 — 8 tests。"""

import pytest
from src.coach.cross_track import CrossTrackChecker


class TestCrossTrackBasic:
    def test_checker_initialized(self):
        c = CrossTrackChecker()
        assert c is not None

    def test_consistent_match(self):
        c = CrossTrackChecker()
        result = c.check("suggest", "L0")
        assert result["consistent"]
        assert result["severity"] == "none"

    def test_inconsistent_mismatch(self):
        c = CrossTrackChecker()
        result = c.check("suggest", "L1")
        assert not result["consistent"]


class TestSeverity:
    def test_adjacent_layer_medium(self):
        c = CrossTrackChecker()
        r = c.check("suggest", "L1")
        assert r["severity"] == "medium"

    def test_skip_layer_high(self):
        c = CrossTrackChecker()
        r = c.check("suggest", "L2")
        assert r["severity"] == "high"

    def test_unknown_type_skipped(self):
        c = CrossTrackChecker()
        r = c.check("unknown_action", "L0")
        assert r["consistent"]


class TestBatchAndSummary:
    def test_batch_check(self):
        c = CrossTrackChecker()
        results = c.check_batch([("suggest", "L0"), ("challenge", "L0")])
        assert len(results) == 2

    def test_summary_counts(self):
        c = CrossTrackChecker()
        results = c.check_batch([("suggest", "L0"), ("challenge", "L0")])
        s = c.summary(results)
        assert s["total"] == 2
        assert s["consistent"] == 1
