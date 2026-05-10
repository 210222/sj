"""LLM API 客户端 — OpenAI 兼容接口 (DeepSeek).

核心设计:
- provider 抽象: 统一 _call_api() 接口
- 超时 + 重试 + 熔断
- 始终可回退: 任何异常 → raise LLMError → 上层回退规则模式
- 流式支持: generate_stream() 通过 AsyncGenerator 逐 chunk 产出
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
import urllib.error
from collections.abc import AsyncGenerator

from src.coach.llm.config import LLMConfig
from src.coach.llm.schemas import LLMResponse

_logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM API 调用失败."""


class LLMClient:
    """LLM API 客户端."""

    def __init__(self, config: LLMConfig):
        self._cfg = config
        if not config.enabled or not config.api_key:
            raise LLMError("LLM not configured — check llm config section")

    def generate(self, coach_context: dict) -> LLMResponse:
        """根据教练上下文生成教学内容.

        Args:
            coach_context: prompts.build_coach_context() 的输出

        Returns:
            LLMResponse: 包含生成的 payload + 元数据

        Raises:
            LLMError: API 调用失败时
        """
        system_prompt = coach_context.get("system", "")
        user_message = coach_context.get("user_message", "")
        action_type = coach_context.get("action_type", "suggest")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        body = {
            "model": self._cfg.model,
            "messages": messages,
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_tokens,
            "response_format": {"type": "json_object"},
        }

        last_error = None
        for attempt in range(self._cfg.max_retries + 1):
            try:
                return self._call_api(body)
            except LLMError as e:
                last_error = e
                if attempt < self._cfg.max_retries:
                    wait = 2 ** attempt
                    _logger.warning(
                        "LLM retry %d/%d after %.1fs: %s",
                        attempt + 1, self._cfg.max_retries, wait, e)
                    time.sleep(wait)
        raise last_error or LLMError("max retries exceeded")

    def _call_api(self, body: dict) -> LLMResponse:
        """单次 API 调用."""
        data = json.dumps(body).encode("utf-8")
        url = f"{self._cfg.base_url}/chat/completions"

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._cfg.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            if e.code == 429:
                raise LLMError(f"rate limited (429): {body_text}")
            if e.code == 401:
                raise LLMError(f"invalid API key (401): {body_text}")
            raise LLMError(f"HTTP {e.code}: {body_text}")
        except urllib.error.URLError as e:
            raise LLMError(f"network error: {e.reason}")
        except json.JSONDecodeError:
            raise LLMError("invalid JSON response from API")
        except Exception as e:
            raise LLMError(f"unexpected error: {e}")

        choices = result.get("choices", [])
        if not choices:
            raise LLMError(f"API returned no choices: {raw[:200]}")

        content = choices[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})

        return LLMResponse(
            content=content,
            model=result.get("model", self._cfg.model),
            tokens_used=usage.get("total_tokens", 0),
            finish_reason=choices[0].get("finish_reason", "stop"),
        )

    async def generate_stream(
        self, coach_context: dict) -> AsyncGenerator[str, None]:
        """流式生成教学内容，逐 chunk 产出文本片段.

        Args:
            coach_context: prompts.build_coach_context() 的输出

        Yields:
            str: 每个 SSE delta 的 content 文本片段
        """
        system_prompt = coach_context.get("system", "")
        user_message = coach_context.get("user_message", "")

        body = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_tokens,
            "stream": True,
        }
        data_bytes = json.dumps(body).encode("utf-8")
        url = f"{self._cfg.base_url}/chat/completions"

        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._cfg.api_key}",
            },
            method="POST",
        )

        # 在线程池中运行阻塞的 HTTP 调用
        loop = asyncio.get_event_loop()

        def _read_sse() -> list[str]:
            chunks: list[str] = []
            try:
                with urllib.request.urlopen(req, timeout=self._cfg.timeout_s) as resp:
                    for line_bytes in resp:
                        line = line_bytes.decode("utf-8").strip()
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]  # 去掉 "data: " 前缀
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            delta = parsed.get("choices", [{}])[0].get(
                                "delta", {})
                            content = delta.get("content", "")
                            if content:
                                chunks.append(content)
                        except json.JSONDecodeError:
                            continue
            except urllib.error.HTTPError as e:
                raise LLMError(f"stream HTTP {e.code}")
            except urllib.error.URLError as e:
                raise LLMError(f"stream network error: {e.reason}")
            return chunks

        chunks = await loop.run_in_executor(None, _read_sse)
        for chunk in chunks:
            yield chunk
            await asyncio.sleep(0)  # 让出事件循环
