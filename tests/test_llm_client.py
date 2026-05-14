"""Phase 10 — LLM 客户端单元测试."""

import json
import os
import pytest

from src.coach.llm.config import LLMConfig, LLMConfigError
from src.coach.llm.schemas import LLMResponse, LLMOutputValidator
from src.coach.llm.prompts import build_coach_context


class TestLLMConfig:
    def test_disabled_when_llm_not_in_cfg(self):
        cfg = LLMConfig.from_yaml({})
        assert cfg.enabled is False

    def test_disabled_when_enabled_false(self):
        cfg = LLMConfig.from_yaml({"llm": {"enabled": False}})
        assert cfg.enabled is False

    def test_raises_when_enabled_but_no_api_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(LLMConfigError, match="API key not found"):
            LLMConfig.from_yaml({
                "llm": {"enabled": True, "api_key_env": "DEEPSEEK_API_KEY"}
            })

    def test_loads_config_when_key_present(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
        cfg = LLMConfig.from_yaml({"llm": {"enabled": True}})
        assert cfg.enabled is True
        assert cfg.api_key == "sk-test-key"
        assert cfg.model == "deepseek-chat"

    def test_custom_config_values(self, monkeypatch):
        monkeypatch.setenv("LLM_KEY", "sk-xxx")
        cfg = LLMConfig.from_yaml({
            "llm": {
                "enabled": True,
                "api_key_env": "LLM_KEY",
                "model": "deepseek-reasoner",
                "temperature": 0.5,
                "max_tokens": 1000,
                "timeout_s": 15,
                "max_retries": 1,
            }
        })
        assert cfg.model == "deepseek-reasoner"
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 1000
        assert cfg.timeout_s == 15


class TestLLMResponse:
    def test_to_payload_parses_json(self):
        resp = LLMResponse(
            content='{"statement": "Python 的 for 循环用来遍历序列", "question": "你理解了吗？"}'
        )
        payload = resp.to_payload()
        assert isinstance(payload, dict)
        assert payload["statement"] == "Python 的 for 循环用来遍历序列"

    def test_to_payload_fallback_to_statement(self):
        resp = LLMResponse(content="纯文本回复，非 JSON")
        payload = resp.to_payload()
        assert payload["statement"] == "纯文本回复，非 JSON"

    def test_to_payload_empty_json_fallback(self):
        resp = LLMResponse(content='{"invalid": "json"}')
        payload = resp.to_payload()
        assert "invalid" in payload


class TestLLMOutputValidator:
    def test_valid_payload(self):
        valid, errors = LLMOutputValidator.validate(
            {"statement": "这是一个有效的回复"}
        )
        assert valid is True
        assert len(errors) == 0

    def test_missing_statement(self):
        valid, errors = LLMOutputValidator.validate({"question": "你好"})
        assert valid is False
        assert any("statement" in e for e in errors)

    def test_empty_statement(self):
        valid, errors = LLMOutputValidator.validate({"statement": ""})
        assert valid is False

    def test_not_a_dict(self):
        valid, errors = LLMOutputValidator.validate("not a dict")
        assert valid is False

    def test_valid_with_extras(self):
        valid, errors = LLMOutputValidator.validate({
            "statement": "答案",
            "question": "追问",
            "step": "第一步",
        })
        assert valid is True


class TestPrompts:
    def test_build_coach_context_has_required_fields(self):
        ctx = build_coach_context(
            intent="focus",
            action_type="scaffold",
            ttm_stage="preparation",
            sdt_profile={"autonomy": 0.6, "competence": 0.7, "relatedness": 0.5},
            user_message="教我 Python",
        )
        assert "system" in ctx
        assert "user_message" in ctx
        assert "action_type" in ctx
        assert ctx["action_type"] == "scaffold"

    def test_system_prompt_contains_coach_framework(self):
        ctx = build_coach_context(
            intent="test", action_type="probe",
            user_message="考考我"
        )
        prompt = ctx["system"]
        assert "教练引擎" in prompt
        assert "认知主权" in prompt
        assert "TTM" in prompt

    def test_default_values_when_null(self):
        ctx = build_coach_context(
            intent="test", action_type="suggest",
            ttm_stage=None, sdt_profile=None,
        )
        assert "contemplation" in ctx["system"]

    def test_all_action_types_in_strategies(self):
        from src.coach.llm.prompts import ACTION_STRATEGIES
        for atype in ["suggest", "challenge", "probe", "reflect",
                       "scaffold", "defer", "pulse", "excursion"]:
            assert atype in ACTION_STRATEGIES, f"missing {atype}"

    def test_all_ttm_stages_in_explanations(self):
        from src.coach.llm.prompts import TTM_EXPLANATIONS
        for stage in ["precontemplation", "contemplation", "preparation",
                       "action", "maintenance", "relapse"]:
            assert stage in TTM_EXPLANATIONS
