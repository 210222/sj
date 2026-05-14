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
from datetime import datetime, timezone

from src.coach.llm.config import LLMConfig
from src.coach.llm.schemas import (
    LLMResponse, LLMObservability,
    CacheObservability, RuntimeObservability, RetentionObservability,
)

_logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM API 调用失败."""


class LLMClient:
    """LLM API 客户端."""

    def __init__(self, config: LLMConfig):
        self._cfg = config
        if not config.enabled or not config.api_key:
            raise LLMError("LLM not configured — check llm config section")
        self._last_stream_observability: LLMObservability | None = None

    @staticmethod
    def build_messages(coach_context: dict) -> list[dict]:
        """统一构造 sync/stream 共用的消息数组。"""
        system_prompt = coach_context.get("system", "")
        user_message = coach_context.get("user_message", "")
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def generate(self, coach_context: dict) -> LLMResponse:
        """根据教练上下文生成教学内容.

        Args:
            coach_context: prompts.build_coach_context() 的输出

        Returns:
            LLMResponse: 包含生成的 payload + 元数据 + observability

        Raises:
            LLMError: API 调用失败时
        """
        messages = self.build_messages(coach_context)
        context_meta = coach_context.get("context_meta", {})

        body = {
            "model": self._cfg.model,
            "messages": messages,
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_tokens,
            "response_format": {"type": "json_object"},
        }

        # Phase 36: runtime timing
        t_start = time.time()
        request_started_at_utc = datetime.now(timezone.utc).isoformat()
        retry_count = 0
        transport_status = "ok"

        last_error = None
        for attempt in range(self._cfg.max_retries + 1):
            try:
                result = self._call_api(body)
                latency_ms = (time.time() - t_start) * 1000.0

                result.observability = self._build_sync_observability(
                    context_meta=context_meta,
                    latency_ms=latency_ms,
                    request_started_at_utc=request_started_at_utc,
                    finish_reason=result.finish_reason,
                    response_model=result.model,
                    tokens_total=result.tokens_used,
                    retry_count=retry_count,
                    transport_status=transport_status,
                    usage=result.usage,
                )
                return result
            except LLMError as e:
                last_error = e
                if attempt < self._cfg.max_retries:
                    retry_count = attempt + 1
                    transport_status = "retry"
                    wait = 2 ** attempt
                    _logger.warning(
                        "LLM retry %d/%d after %.1fs: %s",
                        attempt + 1, self._cfg.max_retries, wait, e)
                    time.sleep(wait)
        raise last_error or LLMError("max retries exceeded")

    def _build_sync_observability(
        self, *, context_meta: dict, latency_ms: float,
        request_started_at_utc: str, finish_reason: str, response_model: str,
        tokens_total: int, retry_count: int, transport_status: str,
        usage: dict | None = None,
    ) -> LLMObservability:
        """构造 sync path 的 runtime observability."""
        cache_obs = CacheObservability(
            cache_eligible=context_meta.get("cache_eligible", False),
            cache_eligibility_reason=context_meta.get("cache_eligibility_reason", ""),
            stable_prefix_hash=context_meta.get("stable_prefix_hash", ""),
            stable_prefix_chars=context_meta.get("stable_prefix_chars", 0),
            stable_prefix_lines=context_meta.get("stable_prefix_lines", 0),
            stable_prefix_share=context_meta.get("stable_prefix_share", 0.0),
            action_contract_hash=context_meta.get("action_contract_hash", ""),
            policy_layer_hash=context_meta.get("policy_layer_hash", ""),
            context_layer_hash=context_meta.get("context_layer_hash", ""),
            context_fingerprint=context_meta.get("context_fingerprint", ""),
            prefix_shape_version=context_meta.get("prefix_shape_version", "1.0.0"),
        )
        # Phase 37: extract real token breakdown + cache telemetry from provider
        u = usage or {}
        has_full = "prompt_tokens" in u
        runtime_obs = RuntimeObservability(
            path="http_sync",
            streaming=False,
            request_started_at_utc=request_started_at_utc,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            response_model=response_model,
            tokens_total=u.get("total_tokens", tokens_total),
            tokens_prompt=u.get("prompt_tokens") if has_full else None,
            tokens_completion=u.get("completion_tokens") if has_full else None,
            token_usage_available=has_full,
            prompt_cache_hit_tokens=u.get("prompt_cache_hit_tokens") if "prompt_cache_hit_tokens" in u else None,
            prompt_cache_miss_tokens=u.get("prompt_cache_miss_tokens") if "prompt_cache_miss_tokens" in u else None,
            retry_count=retry_count,
            timeout_s=self._cfg.timeout_s,
            transport_status=transport_status,
        )
        return LLMObservability(cache=cache_obs, runtime=runtime_obs)

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
            usage=usage if usage else None,
        )

    async def generate_stream(
        self, coach_context: dict) -> AsyncGenerator[str, None]:
        """流式生成教学内容，逐 chunk 产出文本片段.

        Observability 在流结束后存储到 self._last_stream_observability，
        调用方在循环结束后读取。

        Args:
            coach_context: prompts.build_coach_context() 的输出

        Yields:
            str: 每个 SSE delta 的 content 文本片段
        """
        context_meta = coach_context.get("context_meta", {})
        t_start = time.time()
        request_started_at_utc = datetime.now(timezone.utc).isoformat()
        first_chunk_at: float | None = None

        body = {
            "model": self._cfg.model,
            "messages": self.build_messages(coach_context),
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
            nonlocal first_chunk_at
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
                            if first_chunk_at is None:
                                first_chunk_at = time.time()
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
        stream_end = time.time()
        stream_duration_ms = (stream_end - t_start) * 1000.0
        first_chunk_latency_ms = (
            (first_chunk_at - t_start) * 1000.0
            if first_chunk_at else None
        )

        # Phase 36: store stream observability for caller
        cache_obs = CacheObservability(
            cache_eligible=context_meta.get("cache_eligible", False),
            cache_eligibility_reason=context_meta.get("cache_eligibility_reason", ""),
            stable_prefix_hash=context_meta.get("stable_prefix_hash", ""),
            stable_prefix_chars=context_meta.get("stable_prefix_chars", 0),
            stable_prefix_lines=context_meta.get("stable_prefix_lines", 0),
            stable_prefix_share=context_meta.get("stable_prefix_share", 0.0),
            action_contract_hash=context_meta.get("action_contract_hash", ""),
            policy_layer_hash=context_meta.get("policy_layer_hash", ""),
            context_layer_hash=context_meta.get("context_layer_hash", ""),
            context_fingerprint=context_meta.get("context_fingerprint", ""),
            prefix_shape_version=context_meta.get("prefix_shape_version", "1.0.0"),
        )
        runtime_obs = RuntimeObservability(
            path="ws_stream",
            streaming=True,
            request_started_at_utc=request_started_at_utc,
            latency_ms=stream_duration_ms,
            first_chunk_latency_ms=first_chunk_latency_ms,
            stream_duration_ms=stream_duration_ms,
            finish_reason="stop",
            response_model=self._cfg.model,
            tokens_total=0,
            tokens_prompt=None,
            tokens_completion=None,
            token_usage_available=False,
            retry_count=0,
            timeout_s=self._cfg.timeout_s,
            transport_status="ok",
        )
        self._last_stream_observability = LLMObservability(
            cache=cache_obs,
            runtime=runtime_obs,
        )

        for chunk in chunks:
            yield chunk
            await asyncio.sleep(0)  # 让出事件循环
