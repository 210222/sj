"""S0.2 集成测试 — pipeline 执行后审计输出验证。"""

import pytest
from src.outer.orchestration.pipeline import run_pipeline, _get_ledger


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


@pytest.fixture(autouse=True)
def reset_ledger_singleton():
    import src.outer.orchestration.pipeline as mod
    mod._LEDGER_STORE = None


class TestAuditRunsAfterLedgerWrite:
    """pipeline 输出中包含 audit_level 字段。"""

    def test_audit_level_present(self):
        r = run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "audit_level" in r
        assert r["audit_level"] in {"pass", "p1_warn", "p1_freeze", "p0_block"}

    def test_audit_level_is_valid(self):
        valid = {"pass", "p1_warn", "p1_freeze", "p0_block"}
        for i in range(3):
            r = run_pipeline(
                f"t{i}", _ts(14, i),
                {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
                {"goal_clarity": 0.7, "resource_readiness": 0.7,
                 "risk_pressure": 0.2, "constraint_conflict": 0.2},
            )
            assert r["audit_level"] in valid

    def test_first_run_audits_self(self):
        """第一次 run 时 window 中只有一条事件，应有 audit_level。"""
        r = run_pipeline(
            "t_first", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "audit_level" in r
        assert isinstance(r["audit_level"], str)


class TestAuditEmptyWindowDoesNotCrash:
    """审计空窗口时返回 pass。"""

    def test_audit_with_no_events_returns_pass(self):
        from src.outer.orchestration.pipeline import _run_audit_on_current_window
        store = _get_ledger()
        result = _run_audit_on_current_window(store, "nonexistent_window")
        assert result["audit_level"] == "pass"
        assert result.get("insufficient_data") is True


class TestAuditFailureDoesNotCrashPipeline:
    """审计失败时 pipeline 仍正常返回。"""

    def test_audit_failure_does_not_crash(self, monkeypatch):
        def _failing_audit(store, window_id):
            raise RuntimeError("Simulated audit failure")

        monkeypatch.setattr(
            "src.outer.orchestration.pipeline._run_audit_on_current_window",
            _failing_audit,
        )
        r = run_pipeline(
            "t_fail", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "safety_result" in r
        assert "audit_level" in r
