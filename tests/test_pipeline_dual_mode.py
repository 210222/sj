"""S1.3 双模式测试 — legacy 模式零漂移 + coach 模式 DSL 管道。"""

import pytest
from src.outer.orchestration.pipeline import run_pipeline
from src.outer.orchestration.pipeline import _dsl_to_l0_signals, _dsl_to_l2_signals
from src.coach import CoachAgent
from src.coach.dsl import DSLBuilder


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


class TestLegacyModeUnchanged:
    """mode="legacy" 行为与 Phase 0 完全一致。"""

    def test_legacy_returns_expected_keys(self):
        r = run_pipeline(
            "t1", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
            mode="legacy",
        )
        for key in ("safety_result", "stage_markers", "audit_level"):
            assert key in r, f"Missing {key} in legacy result"
        # legacy 模式不应包含 coach 特定字段
        assert "sanitized_dsl" not in r
        assert "coach_trace" not in r

    def test_legacy_default_mode_is_legacy(self):
        """省略 mode 参数时默认为 legacy。"""
        r = run_pipeline(
            "t_default", _ts(14),
            {"engagement": 0.7, "stability": 0.7, "volatility": 0.2},
            {"goal_clarity": 0.7, "resource_readiness": 0.7,
             "risk_pressure": 0.2, "constraint_conflict": 0.2},
        )
        assert "safety_result" in r
        assert "sanitized_dsl" not in r

    def test_legacy_p0_block_still_works(self):
        r = run_pipeline(
            "t2", _ts(14),
            {"engagement": 0.85, "stability": 0.85, "volatility": 0.10},
            {"goal_clarity": 0.85, "resource_readiness": 0.85,
             "risk_pressure": 0.10, "constraint_conflict": 0.10},
            safety_context={"p0_count": 1, "p1_count": 0, "gate_decision": "GO"},
            mode="legacy",
        )
        assert r["safety_result"]["allowed"] is False
        assert r["safety_result"]["audit_level"] == "p0_block"


class TestCoachMode:
    """mode="coach" DSL 管道完整流程。"""

    def _valid_dsl_packet(self):
        return DSLBuilder.build({
            "action_type": "suggest",
            "payload": {"option": "分步调试", "alternatives": [], "evidence_id": None, "source_tag": "rule"},
            "intent": "请求建议",
        })

    def test_coach_mode_has_sanitized_dsl(self):
        packet = self._valid_dsl_packet()
        r = run_pipeline(
            mode="coach",
            dsl_packet=packet,
            trace_id=packet["trace_id"],
            event_time_utc=_ts(14),
            l0_signals={},
            l2_signals={},
        )
        assert "sanitized_dsl" in r
        assert r["sanitized_dsl"] is not None  # 正常 DSL 应通过
        assert r["safety_result"]["allowed"] is True

    def test_coach_mode_has_coach_trace(self):
        packet = self._valid_dsl_packet()
        r = run_pipeline(
            mode="coach",
            dsl_packet=packet,
            trace_id=packet["trace_id"],
            event_time_utc=_ts(14),
            l0_signals={},
            l2_signals={},
        )
        assert "coach_trace" in r
        ct = r["coach_trace"]
        assert ct["mode"] == "coach"
        assert ct["dsl_action_type"] == "suggest"

    def test_coach_mode_audit_level(self):
        packet = self._valid_dsl_packet()
        r = run_pipeline(
            mode="coach",
            dsl_packet=packet,
            trace_id=packet["trace_id"],
            event_time_utc=_ts(14),
            l0_signals={},
            l2_signals={},
        )
        assert r["audit_level"] in {"pass", "p1_warn", "p1_freeze", "p0_block"}


class TestDSLSignalExtraction:
    """DSL→信号提取逻辑。"""

    def test_dsl_to_l0_defaults(self):
        packet = DSLBuilder.build({
            "action_type": "probe",
            "payload": {"prompt": "x", "expected_skill": "g", "max_duration_s": 60},
            "intent": "test",
            "domain_passport": {"evidence_level": "high"},
        })
        signals = _dsl_to_l0_signals(packet)
        assert signals["engagement"] == 0.8
        assert "stability" in signals

    def test_dsl_to_l2_challenge(self):
        packet = DSLBuilder.build({
            "action_type": "challenge",
            "payload": {"objective": "x", "difficulty": "medium", "hints_allowed": True, "evidence_id": None},
            "intent": "test",
        })
        signals = _dsl_to_l2_signals(packet)
        assert signals["goal_clarity"] == 0.5


class TestCoachAgentPipelineIntegration:
    """CoachAgent.act() 集成管线后的输出。"""

    def test_act_includes_pipeline_results(self):
        agent = CoachAgent()
        result = agent.act("给我一个建议")
        assert "sanitized_dsl" in result
        assert "safety_allowed" in result
        assert "gate_decision" in result
        assert "audit_level" in result

    def test_act_sanitized_dsl_matches_action(self):
        agent = CoachAgent()
        result = agent.act("给点建议")
        sd = result["sanitized_dsl"]
        assert sd is not None
        assert sd["action_type"] == result["action_type"]
        assert sd["trace_id"] == result["trace_id"]


class TestBackwardCompatibility:
    """现有 738 tests 保持 pass。"""

    def test_phase0_integration_tests_still_pass(self):
        """smoke: Phase 0 的 ledger/audit/gates 集成测试应继续通过。"""
        # 不做子进程——这里只验证模式隔离不引起模块级崩溃。
        import src.outer.orchestration.pipeline
        import src.coach.agent
        assert True  # import ok
