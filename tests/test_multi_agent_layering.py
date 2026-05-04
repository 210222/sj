"""S6.6 多智能体分层测试 — 11 tests。"""

import pytest
from src.coach.handlers import (
    ProbeHandler, ChallengeHandler, ReflectHandler,
    ScaffoldHandler, BaseHandler, HandlerRegistry,
)
from src.coach.composer import PolicyComposer
from src.coach import CoachAgent


class TestHandlers:
    def test_probe_handler(self):
        h = ProbeHandler()
        assert h.can_handle("probe") is True
        assert h.can_handle("challenge") is False
        payload = h.handle("probe", {"intent": "math", "skill_level": "intermediate"})
        assert "prompt" in payload
        assert payload["expected_skill"] == "intermediate"

    def test_challenge_handler(self):
        h = ChallengeHandler()
        result = h.handle("challenge", {"objective": "Solve equation"})
        assert result["objective"] == "Solve equation"

    def test_reflect_handler(self):
        h = ReflectHandler()
        result = h.handle("reflect", {"question": "What?"})
        assert result["question"] == "What?"

    def test_scaffold_handler(self):
        h = ScaffoldHandler()
        result = h.handle("scaffold", {"step": 2})
        assert result["step"] == 2


class TestHandlerRegistry:
    def test_route_probe(self):
        reg = HandlerRegistry()
        handler = reg.get_handler("probe")
        assert isinstance(handler, ProbeHandler)

    def test_route_challenge(self):
        reg = HandlerRegistry()
        handler = reg.get_handler("challenge")
        assert isinstance(handler, ChallengeHandler)

    def test_route_unknown_returns_none(self):
        reg = HandlerRegistry()
        assert reg.get_handler("nonexistent") is None

    def test_register_custom_handler(self):
        reg = HandlerRegistry()

        class CustomHandler(BaseHandler):
            def can_handle(self, at): return at == "custom"
            def handle(self, at, ctx): return {"custom": True}

        reg.register(CustomHandler())
        assert reg.get_handler("custom") is not None


class TestComposerManager:
    def test_compose_with_ceo_strategy(self):
        composer = PolicyComposer()
        strategy = {
            "macro_strategy": "advance",
            "suggested_action_type": "challenge",
            "intent": "growth",
        }
        result = composer.compose_with_ceo(strategy, {"objective": "Level up"})
        assert result["action_type"] == "challenge"
        assert result["meta"]["ceo_strategy"] == "advance"

    def test_compose_fallback_to_context(self):
        composer = PolicyComposer()
        result = composer.compose_with_ceo(None, {"action_type": "probe"})
        assert result["action_type"] == "probe"

    def test_compose_always_has_required_fields(self):
        composer = PolicyComposer()
        result = composer.compose_with_ceo(None, {})
        for key in ("action_type", "payload", "intent",
                     "domain_passport", "trace_id"):
            assert key in result, f"Missing key: {key}"
