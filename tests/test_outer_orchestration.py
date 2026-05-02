"""外圈编排测试 — 管道可执行性、幂等性、阶段标记、失败定位。"""

import pytest
from src.outer.orchestration import run_pipeline
from src.outer.orchestration.pipeline import STAGE_ORDER


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


class TestPipelineExecution:
    def test_pipeline_returns_stage_markers(self):
        r = run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "safety_result" in r
        assert "stage_markers" in r
        assert all(r["stage_markers"].values())

    def test_pipeline_safety_result_has_expected_keys(self):
        r = run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        sr = r["safety_result"]
        assert "allowed" in sr
        assert "audit_level" in sr

    def test_pipeline_with_p0_block(self):
        r = run_pipeline(
            "t2", _ts(14),
            {"engagement": 0.85, "stability": 0.85, "volatility": 0.10},
            {"goal_clarity": 0.85, "resource_readiness": 0.85,
             "risk_pressure": 0.10, "constraint_conflict": 0.10},
            safety_context={"p0_count": 1, "p1_count": 0, "gate_decision": "GO"},
        )
        assert r["safety_result"]["allowed"] is False
        assert r["safety_result"]["audit_level"] == "p0_block"

    def test_pipeline_low_signals(self):
        r = run_pipeline(
            "t3", _ts(14),
            {"engagement": 0.1, "stability": 0.1, "volatility": 0.9},
            {"goal_clarity": 0.1, "resource_readiness": 0.1,
             "risk_pressure": 0.9, "constraint_conflict": 0.9},
        )
        assert "allowed" in r["safety_result"]


class TestIdempotency:
    def test_same_input_same_output(self):
        l0 = {"engagement": 0.6, "stability": 0.6, "volatility": 0.3}
        l2 = {"goal_clarity": 0.6, "resource_readiness": 0.6,
              "risk_pressure": 0.3, "constraint_conflict": 0.3}
        r1 = run_pipeline("t1", _ts(14), l0, l2)
        r2 = run_pipeline("t1", _ts(14), l0, l2)
        for k in ("allowed", "audit_level", "safety_score"):
            assert r1["safety_result"][k] == r2["safety_result"][k], f"Mismatch on {k}"

    def test_stage_markers_all_true_on_success(self):
        l0 = {"engagement": 0.6, "stability": 0.6, "volatility": 0.3}
        l2 = {"goal_clarity": 0.6, "resource_readiness": 0.6,
              "risk_pressure": 0.3, "constraint_conflict": 0.3}
        r = run_pipeline("t1", _ts(14), l0, l2)
        assert r["stage_markers"] == {k: True for k in STAGE_ORDER}


class TestFailureLocalization:
    def test_bad_l0_signals_raises_with_stage_info(self):
        with pytest.raises(RuntimeError, match=r"failed at stage"):
            run_pipeline(
                "t1", _ts(14),
                {"engagement": 2.0, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": 0.5, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )

    def test_bad_l2_signals_raises_with_stage_info(self):
        with pytest.raises(RuntimeError, match=r"failed at stage"):
            run_pipeline(
                "t1", _ts(14),
                {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": -0.1, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )

    def test_stage_markers_partial_on_failure(self):
        try:
            run_pipeline(
                "t1", _ts(14),
                {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
                {"goal_clarity": 0.7, "resource_readiness": 0.7,
                 "risk_pressure": 0.2, "constraint_conflict": 0.2},
                safety_context={"p0_count": 0, "p1_count": 0,
                                "gate_decision": "INVALID"},
            )
        except RuntimeError as e:
            msg = str(e)
            assert "stage" in msg
            assert "markers" in msg
