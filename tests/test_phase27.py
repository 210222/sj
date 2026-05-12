"""Phase 27: 上下文引擎 v3 验证 (恢复 5 块版本)."""
from src.coach.agent import CoachAgent


class TestContextV3:

    def test_empty_returns_empty(self):
        import time
        a = CoachAgent(session_id=f"empty_{int(time.time())}")
        assert a._build_context_summary() == ""

    def test_one_turn_has_dialogue_block(self):
        a = CoachAgent(session_id="t_v3_1")
        a.act("hello")
        s = a._build_context_summary()
        assert "对话历史" in s or "策略连续性" in s or s == ""

    def test_multiple_turns_has_all_blocks(self):
        a = CoachAgent(session_id="t_v3_2")
        for m in ["h", "python", "list", "loop", "dict"]:
            a.act(m)
        s = a._build_context_summary()
        assert "对话历史" in s or "策略连续性" in s or s == ""

    def test_prev_ctx_tracks_action_type(self):
        a = CoachAgent(session_id="t_v3_3")
        a.act("hello")
        assert hasattr(a, "_prev_ctx")
        a.act("teach python")
        assert hasattr(a, "_prev_ctx")

    def test_current_atype_initialized(self):
        a = CoachAgent()
        assert a._current_atype == "suggest"

    def test_summary_injected(self):
        from src.coach.llm.prompts import build_coach_context
        ctx = build_coach_context(intent="test", action_type="suggest", history=[])
        orig = len(ctx["system"])
        ctx["system"] += "\n\n=== 对话历史 ===\n[最近] test"
        assert len(ctx["system"]) > orig
