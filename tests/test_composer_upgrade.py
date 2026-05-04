"""S4.5 Composer 三模型融合集成测试。"""

import pytest
from src.coach.composer import PolicyComposer
from src.coach import CoachAgent


class TestComposerTTM:
    def test_avoided_action_redirected(self):
        c = PolicyComposer()
        ttm_strategy = {
            "recommended_action_types": ["reflect", "suggest"],
            "avoid_action_types": ["challenge", "probe"],
        }
        action = c.compose(intent="给我一个挑战", ttm_strategy=ttm_strategy)
        # challenge is avoided → should redirect to reflect
        assert action["action_type"] == "reflect"

    def test_not_avoided_unchanged(self):
        c = PolicyComposer()
        ttm_strategy = {
            "recommended_action_types": ["reflect"],
            "avoid_action_types": ["challenge"],
        }
        action = c.compose(intent="测测你的水平", ttm_strategy=ttm_strategy)
        # probe is not avoided
        assert action["action_type"] == "probe"


class TestComposerSDT:
    def test_low_autonomy_redirects_to_reflect(self):
        c = PolicyComposer()
        sdt = {"advice": {"adjust_autonomy_support": True, "adjust_difficulty": "maintain"}}
        action = c.compose(intent="教教我", sdt_profile=sdt)
        # scaffold/suggest → reflect when low autonomy
        assert action["action_type"] == "reflect"

    def test_low_competence_lowers_difficulty(self):
        c = PolicyComposer()
        sdt = {"advice": {"adjust_difficulty": "lower"}}
        action = c.compose(intent="给我一个挑战", sdt_profile=sdt)
        assert action["payload"]["difficulty"] == "low"


class TestComposerFlow:
    def test_flow_increases_difficulty(self):
        c = PolicyComposer()
        flow = {"adjust_difficulty": 0.2}
        action = c.compose(intent="给我一个挑战", flow_result=flow)
        assert action["payload"]["difficulty"] == "high"

    def test_flow_no_effect_when_no_difficulty_slot(self):
        c = PolicyComposer()
        flow = {"adjust_difficulty": 0.2}
        action = c.compose(intent="给个建议", flow_result=flow)
        # suggest has no difficulty slot
        assert action["action_type"] == "suggest"


class TestCoachAgentPhase4:
    def test_agent_returns_phase4_fields(self):
        agent = CoachAgent(session_id="test_s4_5")
        result = agent.act("给个建议")
        # Phase 4 fields present (may be None when models disabled)
        for key in ("ttm_stage", "sdt_profile", "flow_channel"):
            assert key in result, f"Missing Phase 4 key: {key}"

    def test_models_disabled_by_default(self):
        """默认配置下三模型均为 None。"""
        agent = CoachAgent(session_id="test_s4_5_disabled")
        assert agent.ttm is None
        assert agent.sdt is None
        assert agent.flow is None
