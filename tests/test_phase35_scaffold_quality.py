"""Phase 35.1 — scaffold 结构回归测试."""

from src.coach.llm.prompts import build_coach_context


class TestPhase351ScaffoldPrompt:
    def test_scaffold_terminal_checklist_present(self):
        ctx = build_coach_context(
            intent="python loops",
            action_type="scaffold",
            user_message="教我 Python for 循环",
            progress_summary="学习进展: 已掌握变量",
            context_summary="=== 对话历史 ===\n[最近] 用户: 教我 Python for 循环",
        )
        system_prompt = ctx["system"]
        assert "最终输出前自检" in system_prompt
        assert "例如" in system_prompt or "比如" in system_prompt or "举个例子" in system_prompt
        assert "第1步" in system_prompt or "首先" in system_prompt or "步骤" in system_prompt
