"""LLM 配置读取 + API Key 安全管理.

API Key 只从环境变量读取，不写入任何文件/日志/数据库。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class LLMConfigError(Exception):
    """LLM 配置错误."""


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    timeout_s: float = 30.0
    max_retries: int = 2
    temperature: float = 0.7
    max_tokens: int = 2000
    fallback_to_rules: bool = False
    enabled: bool = True

    @classmethod
    def from_yaml(cls, cfg: dict) -> "LLMConfig":
        llm_cfg = cfg.get("llm", {})
        if not llm_cfg.get("enabled", False):
            return cls(enabled=False)

        api_key_env = llm_cfg.get("api_key_env", "DEEPSEEK_API_KEY")
        api_key = os.getenv(api_key_env, "")
        if not api_key:
            raise LLMConfigError(
                f"LLM enabled but API key not found in env var {api_key_env}"
            )

        return cls(
            provider=llm_cfg.get("provider", "openai"),
            model=llm_cfg.get("model", "deepseek-chat"),
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
            api_key=api_key,
            timeout_s=float(llm_cfg.get("timeout_s", 30)),
            max_retries=int(llm_cfg.get("max_retries", 2)),
            temperature=float(llm_cfg.get("temperature", 0.7)),
            max_tokens=int(llm_cfg.get("max_tokens", 2000)),
            fallback_to_rules=bool(llm_cfg.get("fallback_to_rules", False)),
            enabled=True,
        )
