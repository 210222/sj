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


@dataclass
class DiagramProviderConfig:
    provider: str = "gemini"
    proxy: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""
    deepseek_mm_model: str = "deepseek-multimodal"
    deepseek_mm_api_key: str = ""
    deepseek_mm_base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.2
    max_tokens: int = 1000
    timeout_s: float = 15.0
    max_retries: int = 1

    @property
    def enabled(self) -> bool:
        if self.provider == "none": return False
        if self.provider == "gemini": return bool(self.gemini_api_key)
        if self.provider == "deepseek_multimodal": return bool(self.deepseek_mm_api_key)
        return False

    @classmethod
    def from_yaml(cls, cfg: dict) -> "DiagramProviderConfig":
        dc = cfg.get("diagram", {})
        g = dc.get("gemini", {})
        dm = dc.get("deepseek_multimodal", {})
        return cls(
            provider=dc.get("provider", "gemini"),
            proxy=dc.get("proxy", ""),
            gemini_model=g.get("model", "gemini-2.5-flash"),
            gemini_api_key=os.getenv(g.get("api_key_env", "GEMINI_API_KEY"), ""),
            deepseek_mm_model=dm.get("model", "deepseek-multimodal"),
            deepseek_mm_api_key=os.getenv(dm.get("api_key_env", "DEEPSEEK_API_KEY"), ""),
            deepseek_mm_base_url=dm.get("base_url", "https://api.deepseek.com/v1"),
            temperature=dc.get("temperature", 0.2), max_tokens=dc.get("max_tokens", 1000),
            timeout_s=dc.get("timeout_s", 15.0), max_retries=dc.get("max_retries", 1),
        )
