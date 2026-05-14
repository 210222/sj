"""Phase 10 — LLM Agent 集成测试."""

import os
import pytest

from src.coach.agent import CoachAgent


class TestLLMDisabledByDefault:
    """LLM 默认关闭 — 确保现有行为不变."""

    def test_agent_act_default_does_not_use_llm(self):
        agent = CoachAgent(session_id="test-llm-off")
        result = agent.act("hello", context={"session_id": "test-llm-off"})
        assert "action_type" in result
        assert result.get("llm_generated") is False
        # 规则模式应产出正常 DSL 包
        assert result.get("trace_id") is not None

    def test_agent_act_rule_mode_has_intent(self):
        agent = CoachAgent(session_id="test-intent")
        result = agent.act("help me learn Python loops")
        assert result.get("intent") in ("scaffold", "general")
        assert result.get("action_type") is not None


class TestLLMFallback:
    """LLM 失败时回退规则模式."""

    def test_llm_config_invalid_no_key(self):
        agent = CoachAgent(session_id="test-fallback")
        # 配置了 LLM enabled 但无 API Key 时，不应崩溃
        result = agent.act("hello")
        assert result.get("action_type") is not None
        # 规则模式下正常工作
        assert isinstance(result.get("payload"), dict)



    def test_context_meta_exists_and_marks_layers(self):
        from src.coach.llm.prompts import build_coach_context
        ctx = build_coach_context(
            intent="scaffold",
            action_type="scaffold",
            user_message="teach me Python loops",
            progress_summary="学习进展: 已掌握变量",
            context_summary="=== 对话历史 ===\n[最近] 用户: 教我循环",
            memory_snippets=["上轮教学[scaffold]: for 循环遍历序列"],
            covered_topics=["Python", "Loops"],
        )
        meta = ctx.get("context_meta")
        assert isinstance(meta, dict)
        assert meta.get("stable_prefix_chars", 0) > 0
        assert meta.get("context_layer_chars", 0) > 0
        assert meta.get("has_progress_summary") is True
        assert meta.get("has_context_summary") is True

    def test_context_stable_prefix_contains_output_contract(self):
        from src.coach.llm.prompts import build_coach_context
        ctx = build_coach_context(intent="test", action_type="suggest", user_message="hello")
        assert "输出要求:" in ctx["system"]
        assert "结构化教学协议:" in ctx["system"]
        assert "追问处理 (最高优先级):" in ctx["system"]

    def test_context_with_user_input(self):
        from src.coach.llm.prompts import build_coach_context
        ctx = build_coach_context(
            intent="scaffold",
            action_type="scaffold",
            ttm_stage="preparation",
            user_message="teach me Python loops",
        )
        assert ctx["user_message"] == "teach me Python loops"

    def test_context_action_type_preserved(self):
        from src.coach.llm.prompts import build_coach_context
        for atype in ["suggest", "challenge", "probe", "reflect", "scaffold"]:
            ctx = build_coach_context(intent="test", action_type=atype)
            assert ctx["action_type"] == atype
