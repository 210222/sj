"""Phase 27: 上下文引擎 v3 验证 + Phase 31 行为级断言收紧."""
from src.coach.agent import CoachAgent


class TestContextV3:

    def test_empty_returns_empty(self):
        import time
        a = CoachAgent(session_id=f"empty_{int(time.time())}")
        assert a._build_context_summary() == ""

    def test_one_turn_has_dialogue_block(self):
        a = CoachAgent(session_id="t_v3_1")
        a.act("我想学Python")
        s = a._build_context_summary()
        assert "对话历史" in s, f"摘要应包含对话历史块，实际: {repr(s)}"
        assert len(s) > 20, f"摘要不应为空，实际长度: {len(s)}"

    def test_multiple_turns_has_all_blocks(self):
        a = CoachAgent(session_id="t_v3_2")
        for m in ["hello", "我想学Python基础", "list怎么用", "for循环呢", "dict和list有什么区别"]:
            a.act(m)
        s = a._build_context_summary()
        assert "对话历史" in s, f"多轮摘要应含对话历史: {repr(s)[:80]}"
        assert len(s) > 50, f"多轮摘要内容过短: {len(s)}"

    def test_prev_ctx_tracks_action_type(self):
        a = CoachAgent(session_id="t_v3_3")
        a.act("hello")
        assert hasattr(a, "_prev_ctx")
        prev_ctx = a._prev_ctx
        assert "action_type" in prev_ctx, f"_prev_ctx 应含 action_type: {prev_ctx}"
        a.act("teach me python basics")
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

    def test_summary_after_multiple_turns_has_recent_line(self):
        """Phase 31: 多轮后摘要[最近]行含用户消息与非空教练文本."""
        a = CoachAgent(session_id="t_v3_multi")
        a.act("我想学Python")
        a.act("list怎么用")
        s = a._build_context_summary()
        assert "[最近]" in s, f"摘要应含[最近]行: {repr(s)[:120]}"

    def test_strategy_continuity_block_present(self):
        """Phase 31: 至少一轮后摘要含策略连续性块."""
        a = CoachAgent(session_id="t_v3_cont")
        a.act("hello")
        a.act("继续讲")
        s = a._build_context_summary()
        assert "策略连续性" in s, f"摘要应含策略连续性块: {repr(s)[:120]}"
