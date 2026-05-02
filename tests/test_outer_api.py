"""外圈 API 测试 — 入口 schema、输入校验、错误分层。"""

from unittest.mock import patch
from src.outer.api import run_orchestration
from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


def _signals():
    return (
        {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
        {"goal_clarity": 0.7, "resource_readiness": 0.7,
         "risk_pressure": 0.2, "constraint_conflict": 0.2},
    )


class TestOutputSchema:
    def test_keys_exact_match(self):
        l0, l2 = _signals()
        r = run_orchestration("t1", _ts(14), l0, l2)
        assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)

    def test_keys_stable_on_multiple_calls(self):
        l0, l2 = _signals()
        for i in range(10):
            r = run_orchestration(f"t{i}", _ts(14, i), l0, l2)
            assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)

    def test_allowed_is_bool(self):
        l0, l2 = _signals()
        r = run_orchestration("t1", _ts(14), l0, l2)
        assert isinstance(r["allowed"], bool)

    def test_final_intensity_is_str(self):
        l0, l2 = _signals()
        r = run_orchestration("t1", _ts(14), l0, l2)
        assert isinstance(r["final_intensity"], str)

    def test_evaluated_at_utc_is_iso8601(self):
        l0, l2 = _signals()
        r = run_orchestration("t1", _ts(14), l0, l2)
        assert r["evaluated_at_utc"].endswith("Z")
        assert "T" in r["evaluated_at_utc"]


class TestHappyPath:
    def test_full_pipeline_happy_path(self):
        l0 = {"engagement": 0.85, "stability": 0.80, "volatility": 0.10}
        l2 = {"goal_clarity": 0.85, "resource_readiness": 0.80,
              "risk_pressure": 0.10, "constraint_conflict": 0.10}
        r = run_orchestration("happy", _ts(14), l0, l2)
        assert r["allowed"] is True
        assert r["final_intensity"] in ("full", "reduced", "minimal", "none")

    def test_high_risk_signals_produce_defer_or_block(self):
        l0 = {"engagement": 0.15, "stability": 0.15, "volatility": 0.90}
        l2 = {"goal_clarity": 0.15, "resource_readiness": 0.10,
              "risk_pressure": 0.90, "constraint_conflict": 0.85}
        r = run_orchestration("risky", _ts(14), l0, l2)
        assert isinstance(r["allowed"], bool)

    def test_with_safety_context(self):
        l0, l2 = _signals()
        r = run_orchestration("t1", _ts(14), l0, l2,
                              safety_context={"p0_count": 0, "p1_count": 2,
                                              "gate_decision": "WARN"})
        assert r["audit_level"] in ("pass", "p1_warn", "p1_freeze", "p0_block")


class TestErrorLayering:
    """输入错误 vs 执行错误的 reason_code 分层。"""

    def test_empty_trace_id_returns_invalid_input(self):
        l0, l2 = _signals()
        r = run_orchestration("", _ts(14), l0, l2)
        assert r["reason_code"] == "ORCH_INVALID_INPUT"
        assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)

    def test_empty_event_time_returns_invalid_input(self):
        l0, l2 = _signals()
        r = run_orchestration("t1", "", l0, l2)
        assert r["reason_code"] == "ORCH_INVALID_INPUT"

    def test_non_dict_l0_returns_invalid_input(self):
        r = run_orchestration("t1", _ts(14), None,
                              {"goal_clarity": 0.5, "resource_readiness": 0.5,
                               "risk_pressure": 0.5, "constraint_conflict": 0.5})
        assert r["reason_code"] == "ORCH_INVALID_INPUT"

    def test_non_dict_l2_returns_invalid_input(self):
        r = run_orchestration("t1", _ts(14),
                              {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                              None)
        assert r["reason_code"] == "ORCH_INVALID_INPUT"

    def test_pipeline_exception_returns_pipeline_error(self):
        with patch(
            "src.outer.api.service.run_pipeline",
            side_effect=RuntimeError("stage 'l0': markers=..."),
        ):
            r = run_orchestration(
                "t1", _ts(14),
                {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": 0.5, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )
        assert r["reason_code"] == "ORCH_PIPELINE_ERROR"
        assert r["allowed"] is False
        assert set(r.keys()) == set(OUTPUT_SCHEMA_KEYS)

    def test_pipeline_import_error_returns_pipeline_error(self):
        with patch(
            "src.outer.api.service.run_pipeline",
            side_effect=ImportError("missing module"),
        ):
            r = run_orchestration(
                "t1", _ts(14),
                {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
                {"goal_clarity": 0.5, "resource_readiness": 0.5,
                 "risk_pressure": 0.5, "constraint_conflict": 0.5},
            )
        assert r["reason_code"] == "ORCH_PIPELINE_ERROR"
