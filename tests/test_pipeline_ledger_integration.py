"""S0.1 集成测试 — pipeline 执行后账本写入验证。"""

import pytest
from src.outer.orchestration.pipeline import run_pipeline, _get_ledger
from src.inner.ledger.event_store import GENESIS_PREV_HASH


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


@pytest.fixture(autouse=True)
def reset_ledger_singleton():
    """每个测试重置 ledger 单例，确保独立。"""
    import src.outer.orchestration.pipeline as mod
    mod._LEDGER_STORE = None


class TestLedgerHasEventAfterPipeline:
    """执行 pipeline 后 EventStore 中能查到对应事件。"""

    def test_ledger_has_event_after_pipeline(self):
        r = run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert r["safety_result"]["allowed"] is True

        store = _get_ledger()
        latest = store.get_latest_event()
        assert latest is not None
        assert latest["chain_height"] >= 1

    def test_ledger_event_has_trace_id(self):
        run_pipeline(
            "trace_abc", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        store = _get_ledger()
        latest = store.get_latest_event()
        assert latest["trace_id"] == "trace_abc"

    def test_ledger_chain_integrity(self):
        run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        store = _get_ledger()
        result = store.verify_chain_integrity()
        assert result["valid"] is True, f"Chain integrity failed: {result.get('failures', [])}"

    def test_multiple_pipeline_runs_append_to_chain(self):
        run_pipeline("t1", _ts(14),
                     {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
                     {"goal_clarity": 0.7, "resource_readiness": 0.7,
                      "risk_pressure": 0.2, "constraint_conflict": 0.2})
        run_pipeline("t2", _ts(15),
                     {"engagement": 0.6, "stability": 0.6, "volatility": 0.3},
                     {"goal_clarity": 0.6, "resource_readiness": 0.6,
                      "risk_pressure": 0.3, "constraint_conflict": 0.3})

        store = _get_ledger()
        latest = store.get_latest_event()
        assert latest is not None
        assert latest["chain_height"] >= 2
        assert store.verify_chain_integrity()["valid"] is True


class TestLedgerWriteFailureDoesNotCrashPipeline:
    """模拟写入失败仍返回正常 8 字段输出。"""

    def test_write_failure_does_not_crash_pipeline(self, monkeypatch):
        def _failing_append(self, p0, p1, event_time_utc=None, window_id=None):
            raise RuntimeError("Simulated disk full")

        monkeypatch.setattr(
            "src.inner.ledger.event_store.EventStore.append_event",
            _failing_append,
        )
        r = run_pipeline(
            "t_fail", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "safety_result" in r
        assert "stage_markers" in r
        assert r["safety_result"]["allowed"] is True
