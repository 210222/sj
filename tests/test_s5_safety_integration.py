"""S5.5 语义安全集成测试 — 3 tests。"""

import pytest
from src.coach import CoachAgent


class TestSafetyIntegration:
    def test_agent_returns_phase5_fields(self):
        agent = CoachAgent(session_id="test_s5_5")
        result = agent.act("给个建议")
        for key in ("counterfactual_result", "cross_track_result",
                     "precedent_result"):
            assert key in result, f"Missing Phase 5 key: {key}"

    def test_cross_track_in_result(self):
        agent = CoachAgent(session_id="test_s5_5_ct")
        result = agent.act("给个建议")
        ct = result.get("cross_track_result")
        assert ct is not None
        assert "consistent" in ct

    def test_safety_off_does_not_block(self):
        agent = CoachAgent(session_id="test_s5_5_off")
        result = agent.act("教教我怎么调试")
        assert result.get("counterfactual_result") is None
        assert result.get("precedent_result") is None
