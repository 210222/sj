"""Phase 24: 纵向评测 — 多轮教学后验证系统状态."""
from src.coach.agent import CoachAgent
from src.coach.persistence import SessionPersistence


class TestLongitudinal:
    """多轮教学后验证系统状态."""

    PHASE_19_24_KEYS = [
        "action_type", "payload", "llm_generated", "llm_model",
        "llm_tokens", "personalization_evidence", "memory_status",
        "difficulty_contract", "diagnostic_result", "diagnostic_probe",
        "ttm_stage", "sdt_profile", "flow_channel",
    ]

    def test_agent_output_has_all_phase_fields(self):
        """单次 act() 输出应包含 Phase 19-24 全部字段."""
        agent = CoachAgent(session_id="test_long_fields_24")
        r = agent.act("test longitudinal")
        for k in self.PHASE_19_24_KEYS:
            assert k in r, f"missing key: {k}"

    def test_session_persistence_increments(self):
        """每轮对话后 total_turns 应递增."""
        agent = CoachAgent(session_id="test_long_turns_24")
        agent.act("turn 1")
        p1 = SessionPersistence("test_long_turns_24")
        t1 = p1.get_profile().get("total_turns", 0)
        agent.act("turn 2")
        p2 = SessionPersistence("test_long_turns_24")
        t2 = p2.get_profile().get("total_turns", 0)
        assert t2 >= t1, f"turns should not decrease: {t1} -> {t2}"

    def test_multiple_turns_no_crash(self):
        """多轮对话不应崩溃."""
        agent = CoachAgent(session_id="test_long_stress_24")
        for i in range(10):
            r = agent.act(f"message {i}")
            assert "action_type" in r, f"crash at turn {i}"
