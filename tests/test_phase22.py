"""Phase 22: Action-Type 行为差异化验证。

验证 8 种 action_type 的 prompt 内容可区分、校验逻辑正确。
不需要 DEEPSEEK_API_KEY（不调 LLM）。
"""
from src.coach.llm.prompts import build_coach_context
from src.coach.llm.schemas import LLMOutputValidator


class TestPromptDifferentiation:
    """8 种 action_type 的 prompt 内容必须各不相同."""

    ACTION_TYPES = [
        "probe", "scaffold", "challenge", "suggest",
        "reflect", "defer", "pulse", "excursion",
    ]

    UNIQUE_KEYWORDS = {
        "probe": "expected_answer",
        "scaffold": "step",
        "challenge": "objective",
        "suggest": "options",
        "reflect": "reflection_prompts",
        "defer": "resume_condition",
        "pulse": "accept_label",
        "excursion": "bias_disabled",
    }

    def test_all_types_have_unique_keywords(self):
        for atype in self.ACTION_TYPES:
            ctx = build_coach_context(action_type=atype, intent="python")
            prompt = ctx["system"]
            keyword = self.UNIQUE_KEYWORDS[atype]
            assert keyword in prompt, f"{atype}: 应包含 '{keyword}'"

    def test_suggest_includes_options(self):
        ctx = build_coach_context(action_type="suggest", intent="python")
        assert "options" in ctx["system"]

    def test_scaffold_includes_steps(self):
        ctx = build_coach_context(action_type="scaffold", intent="python")
        assert "steps" in ctx["system"]


class TestOutputValidation:
    """Action-Type 特定字段校验."""

    def test_probe_missing_expected_answer_fails(self):
        valid, errors = LLMOutputValidator.validate_with_type(
            {"statement": "test"}, "probe")
        assert not valid
        assert any("expected_answer" in e for e in errors)

    def test_probe_with_expected_answer_passes(self):
        valid, errors = LLMOutputValidator.validate_with_type(
            {"statement": "test", "question": "?", "expected_answer": "ans"}, "probe")
        assert valid, f"expected pass, got {errors}"

    def test_scaffold_missing_steps_fails(self):
        valid, errors = LLMOutputValidator.validate_with_type(
            {"statement": "test"}, "scaffold")
        assert not valid
        assert any("steps" in e for e in errors)

    def test_scaffold_with_steps_passes(self):
        valid, errors = LLMOutputValidator.validate_with_type(
            {"statement": "test", "steps": []}, "scaffold")
        assert valid, f"expected pass, got {errors}"

    def test_challenge_missing_objective_fails(self):
        valid, errors = LLMOutputValidator.validate_with_type(
            {"statement": "test"}, "challenge")
        assert not valid
        assert any("objective" in e for e in errors)

    def test_no_action_type_uses_old_behavior(self):
        valid, errors = LLMOutputValidator.validate_with_type(
            {"statement": "test"})
        assert valid
