"""S8.1 审计分级门禁测试。"""

import pytest
from src.coach.audit_health import AuditFinding, AuditHealthScorer


class TestAuditFinding:
    def test_p0_blocking(self):
        f = AuditFinding(severity="P0", category="security", detail="xss")
        assert f.is_blocking() is True

    def test_p1_warning(self):
        f = AuditFinding(severity="P1", category="coverage", detail="low coverage")
        assert f.is_warning() is True
        assert f.is_blocking() is False

    def test_p2_not_blocking(self):
        f = AuditFinding(severity="P2", category="quality", detail="minor")
        assert not f.is_blocking()
        assert not f.is_warning()


class TestAuditHealthScorer:
    def test_no_findings_perfect_score(self):
        s = AuditHealthScorer()
        result = s.evaluate([])
        assert result.score == 1.0
        assert result.p0_count == 0
        assert result.p0_blocking is False

    def test_p0_blocks_gate(self):
        s = AuditHealthScorer()
        result = s.evaluate([AuditFinding("P0", "security", "breach")])
        assert result.p0_blocking is True
        assert result.score < 0.5

    def test_multiple_p0_reduces_score(self):
        s = AuditHealthScorer()
        r1 = s.evaluate([AuditFinding("P0", "security", "x")])
        r2 = s.evaluate([AuditFinding("P0", "security", "x"),
                         AuditFinding("P0", "contract", "y")])
        assert r2.score < r1.score

    def test_p1_below_threshold_high_score(self):
        s = AuditHealthScorer(p1_threshold=3)
        result = s.evaluate([AuditFinding("P1", "coverage", "minor")])
        assert result.score >= 0.8
        assert result.p0_blocking is False

    def test_p1_above_threshold_block(self):
        s = AuditHealthScorer(p1_threshold=2)
        findings = [AuditFinding("P1", "quality", f"issue_{i}") for i in range(4)]
        result = s.evaluate(findings)
        assert result.p1_above_threshold is True
        assert result.score < 0.8

    def test_trend_tracking(self):
        s = AuditHealthScorer(trend_window=10)
        s.evaluate([])
        s.evaluate([AuditFinding("P1", "quality", "x")])
        s.evaluate([AuditFinding("P0", "security", "y")])
        t = s.trend()
        assert "avg_score" in t
        assert t["trend"] in ("stable", "declining", "improving")

    def test_mixed_findings(self):
        s = AuditHealthScorer(p1_threshold=3)
        findings = [
            AuditFinding("P0", "security", "critical"),
            AuditFinding("P1", "coverage", "warn1"),
            AuditFinding("P2", "quality", "minor"),
        ]
        result = s.evaluate(findings)
        assert result.p0_count == 1
        assert result.p1_count == 1
        assert result.p0_blocking is True
