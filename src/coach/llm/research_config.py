"""Phase 18: 研究管线 LLM 配置（与教学 Agent 独立）."""
from __future__ import annotations

import os
import logging

_logger = logging.getLogger(__name__)


class ResearchLLMConfig:
    """研究 Agent 专用的 LLM 配置。

    与教学 Agent 共享同一 API 后端，但使用不同参数：
    - temperature: 0.2（研究需要精确性）
    - max_tokens: 4000（需要输出长 findings）
    - max_retries: 3（研究 Agent 失败成本更高）
    - timeout_s: 60（允许更长思考时间）
    """

    def __init__(
        self,
        api_key_env: str = "DEEPSEEK_API_KEY",
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
        temperature: float = 0.2,
        max_tokens: int = 16000,
        timeout_s: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_key = os.getenv(api_key_env)
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError(
                f"Research API key not found in env var {api_key_env}. "
                "Set it before running the research pipeline."
            )

    def to_chat_completion_payload(self, messages: list[dict]) -> dict:
        """构造 OpenAI 兼容的 /chat/completions 请求体."""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def to_llm_client_context(self) -> dict:
        """返回供 LLMClient.generate 使用的 context dict."""
        return {
            "system": "You are a research agent.",
            "user_message": "",
        }
