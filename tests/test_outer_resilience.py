"""外圈韧性测试 — fallback 稳定性、坏时间处理、时间一致性。"""

from unittest.mock import patch
from src.outer.api import run_orchestration
from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS
from src.inner.clock import get_window_30min


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


class TestFallback:
    def test_fallback_on_pipeline_exception(self):
        with patch(
            "src.outer.api.service.run_pipeline",
            side_effect=RuntimeError("crash"),
        ):
            r = run_orchestration(
                "t1", _ts(14),
                {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": 0.5, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )
        assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)
        assert r["allowed"] is False
        assert r["final_intensity"] == "none"
        assert r["reason_code"] == "ORCH_PIPELINE_ERROR"

    def test_fallback_schema_stable_across_exceptions(self):
        for exc in [RuntimeError("a"), ValueError("b"), KeyError("c")]:
            with patch(
                "src.outer.api.service.run_pipeline",
                side_effect=exc,
            ):
                r = run_orchestration(
                    "t", _ts(14),
                    {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                    {"goal_clarity": 0.5, "resource_readiness": 0.5,
                     "risk_pressure": 0.5, "constraint_conflict": 0.5},
                )
            assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)

    def test_fallback_with_bad_time_no_sentinel_window(self):
        with patch(
            "src.outer.api.service.run_pipeline",
            side_effect=Exception("crash"),
        ):
            r = run_orchestration(
                "t1", "not-a-time",
                {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": 0.5, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )
        assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)
        assert "FALLBACK_WINDOW" not in r["window_id"]
        assert r["window_id"] != ""
        assert r["reason_code"] == "ORCH_PIPELINE_ERROR"

    def test_fallback_preserves_trace_id(self):
        with patch(
            "src.outer.api.service.run_pipeline",
            side_effect=Exception("crash"),
        ):
            r = run_orchestration(
                "trace-abc-123", _ts(14),
                {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": 0.5, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )
        assert r["trace_id"] == "trace-abc-123"


class TestTimeConsistency:
    def test_window_id_matches_clock(self):
        ts = "2026-04-29T14:22:30.000Z"
        r = run_orchestration(
            "t1", ts,
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert r["window_id"] == get_window_30min(ts)

    def test_evaluated_at_utc_refreshes_per_call(self):
        import time
        r1 = run_orchestration(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        time.sleep(0.1)
        r2 = run_orchestration(
            "t2", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert r1["evaluated_at_utc"] != r2["evaluated_at_utc"]
