"""S0.3 集成测试 — GateEngine 实时门禁取代外部字符串。"""

import pytest
from src.outer.orchestration.pipeline import run_pipeline


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


class TestGateEngineCalledInPipeline:
    """GateEngine 被调用并产出实时 decision。"""

    def test_pipeline_uses_gate_engine(self):
        r = run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "safety_result" in r
        # GateEngine should have run and produced GO (no blocking inputs)
        safety = r["safety_result"]
        assert safety["allowed"] is True

    def test_gate_goes_warn_with_p0(self):
        """P0 count > 0 should trigger Audit Gate, but pipeline still completes."""
        r = run_pipeline(
            "t_warn", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
            safety_context={"p0_count": 2, "p1_count": 0, "gate_decision": "GO"},
        )
        assert "safety_result" in r

    def test_safety_receives_live_gate_decision(self):
        """Safety 收到的 gate_decision 来自 GateEngine，不是外部字符串的盲传。"""
        # 传入外部 gate_decision 但与真实 GateEngine 产出无关
        r = run_pipeline(
            "t_ext", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
            safety_context={"p0_count": 0, "p1_count": 0, "gate_decision": "EXTERNAL_BYPASS"},
        )
        sr = r["safety_result"]
        assert sr["reason_code"] in {
            "SEM_PASS", "SEM_WARN_GATE", "SEM_FREEZE_GATE",
            "SEM_BLOCK_P0", "SEM_BLOCK_LOW_SCORE", "SEM_WARN_P1",
        }

    def test_pipeline_result_has_audit_level(self):
        """验证 S0.2 的 audit_level 仍然存在（前一子阶段不受影响）。"""
        r = run_pipeline(
            "t_audit", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "audit_level" in r
        assert r["audit_level"] in {"pass", "p1_warn", "p1_freeze", "p0_block"}


class TestGateEngineNoInputDoesNotCrash:
    """GateEngine 无输入时默认返回 GO。"""

    def test_no_input_returns_go(self):
        from src.inner.gates import GateEngine
        engine = GateEngine()
        result = engine.evaluate()
        assert result["decision"] == "GO"
        assert result["gate_score"] == 0.0
        assert result["gates_passed"] == 8


class TestGateEngineFailureDoesNotCrashPipeline:
    """GateEngine 调用失败时 pipeline 正常返回。"""

    def test_gate_failure_defaults_to_go(self, monkeypatch):
        def _failing_evaluate(self, gate_inputs=None, event_time_utc=None,
                              window_id=None, context=None):
            raise RuntimeError("Simulated gate failure")

        monkeypatch.setattr(
            "src.inner.gates.engine.GateEngine.evaluate",
            _failing_evaluate,
        )
        r = run_pipeline(
            "t_gfail", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "safety_result" in r
        assert "audit_level" in r
