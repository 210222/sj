"""LLM 输出 schema 定义 + 校验 + DSL 对齐.

LLM 生成的 payload 必须符合 DSL schema，否则回退规则模式。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)


@dataclass
class CacheObservability:
    """Prompt cache-eligibility 结构证据."""
    cache_eligible: bool = False
    cache_eligibility_reason: str = ""
    stable_prefix_hash: str = ""
    stable_prefix_chars: int = 0
    stable_prefix_lines: int = 0
    stable_prefix_share: float = 0.0
    action_contract_hash: str = ""
    policy_layer_hash: str = ""
    context_layer_hash: str = ""
    context_fingerprint: str = ""
    prefix_shape_version: str = "1.0.0"

    def to_dict(self) -> dict:
        return {
            "cache_eligible": self.cache_eligible,
            "cache_eligibility_reason": self.cache_eligibility_reason,
            "stable_prefix_hash": self.stable_prefix_hash,
            "stable_prefix_chars": self.stable_prefix_chars,
            "stable_prefix_lines": self.stable_prefix_lines,
            "stable_prefix_share": round(self.stable_prefix_share, 4),
            "action_contract_hash": self.action_contract_hash,
            "policy_layer_hash": self.policy_layer_hash,
            "context_layer_hash": self.context_layer_hash,
            "context_fingerprint": self.context_fingerprint,
            "prefix_shape_version": self.prefix_shape_version,
        }


@dataclass
class RuntimeObservability:
    """LLM 调用运行时证据."""
    # DeepSeek API 定价 ($/1M tokens)
    _PRICE_CACHE_HIT = 0.07
    _PRICE_CACHE_MISS = 0.27
    _PRICE_OUTPUT = 1.10

    path: str = ""
    streaming: bool = False
    request_started_at_utc: str = ""
    latency_ms: float = 0.0
    first_chunk_latency_ms: float | None = None
    stream_duration_ms: float | None = None
    finish_reason: str = "stop"
    response_model: str = ""
    tokens_total: int = 0
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    token_usage_available: bool = False
    prompt_cache_hit_tokens: int | None = None
    prompt_cache_miss_tokens: int | None = None
    retry_count: int = 0
    timeout_s: float = 30.0
    transport_status: str = "ok"

    @property
    def cost_usd(self) -> float | None:
        """基于真实 DeepSeek 定价和 provider 返回的 cache-hit/miss 遥测计算的成本。

        仅当 token_usage_available 且至少有一个 token 计数时返回有效值。
        """
        prompt = self.tokens_prompt
        completion = self.tokens_completion
        if prompt is None or completion is None:
            return None
        cache_hit = self.prompt_cache_hit_tokens or 0
        cache_miss = self.prompt_cache_miss_tokens or 0
        # 若 provider 未返回 cache 分解，则全部计为 cache miss
        if cache_hit == 0 and cache_miss == 0:
            cache_miss = prompt
        # 对齐取整误差
        accounted = cache_hit + cache_miss
        if accounted > 0 and accounted != prompt:
            cache_miss = max(0, prompt - cache_hit)
        return round(
            (cache_hit / 1_000_000.0) * self._PRICE_CACHE_HIT
            + (cache_miss / 1_000_000.0) * self._PRICE_CACHE_MISS
            + (completion / 1_000_000.0) * self._PRICE_OUTPUT,
            6,
        )

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "streaming": self.streaming,
            "request_started_at_utc": self.request_started_at_utc,
            "latency_ms": round(self.latency_ms, 1),
            "first_chunk_latency_ms": round(self.first_chunk_latency_ms, 1) if self.first_chunk_latency_ms is not None else None,
            "stream_duration_ms": round(self.stream_duration_ms, 1) if self.stream_duration_ms is not None else None,
            "finish_reason": self.finish_reason,
            "response_model": self.response_model,
            "tokens_total": self.tokens_total,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "token_usage_available": self.token_usage_available,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "cost_usd": self.cost_usd,
            "retry_count": self.retry_count,
            "timeout_s": self.timeout_s,
            "transport_status": self.transport_status,
        }


@dataclass
class RetentionObservability:
    """上下文保留策略执行指标."""
    retention_history_hits: int = 0
    retention_memory_hits: int = 0
    retention_duplicate_dropped: int = 0
    retention_budget_history_limit: int = 12
    retention_budget_memory_limit: int = 6
    retention_progress_included: bool = False
    retention_context_summary_included: bool = False
    session_scoped: bool = False

    def to_dict(self) -> dict:
        return {
            "retention_history_hits": self.retention_history_hits,
            "retention_memory_hits": self.retention_memory_hits,
            "retention_duplicate_dropped": self.retention_duplicate_dropped,
            "retention_budget_history_limit": self.retention_budget_history_limit,
            "retention_budget_memory_limit": self.retention_budget_memory_limit,
            "retention_progress_included": self.retention_progress_included,
            "retention_context_summary_included": self.retention_context_summary_included,
            "session_scoped": self.session_scoped,
        }


@dataclass
class LLMObservability:
    """统一的 LLM 运行时可观测性对象."""
    cache: CacheObservability = field(default_factory=CacheObservability)
    runtime: RuntimeObservability = field(default_factory=RuntimeObservability)
    retention: RetentionObservability = field(default_factory=RetentionObservability)

    def to_dict(self) -> dict:
        return {
            "cache": self.cache.to_dict(),
            "runtime": self.runtime.to_dict(),
            "retention": self.retention.to_dict(),
        }


@dataclass
class LLMResponse:
    """LLM 原始响应结构."""
    content: str
    model: str = ""
    tokens_used: int = 0
    finish_reason: str = "stop"
    observability: LLMObservability | None = None
    # Phase 37: full token breakdown + cache telemetry from provider
    usage: dict | None = None

    def to_payload(self) -> dict:
        """将 LLM 内容转为 DSL payload 字典."""
        try:
            data = json.loads(self.content)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return {"statement": self.content.strip()}


def _sha256(text: str) -> str:
    """SHA-256 hash of text, truncated to 16 hex chars for readability."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class LLMOutputValidator:
    """LLM 输出校验器 — 确保输出符合 DSL 合约."""

    REQUIRED_KEYS = {"statement"}
    VALID_KEYS = {"statement", "question", "step", "option",
                  "hint", "difficulty", "alternatives",
                  "evidence_id", "source_tag"}

    @classmethod
    def validate(cls, payload: dict) -> tuple[bool, list[str]]:
        """校验 LLM 生成的 payload. Returns (is_valid, errors)."""
        errors = []
        if not isinstance(payload, dict):
            return False, ["payload must be a dict"]

        if "statement" not in payload:
            errors.append("missing 'statement' field")
        elif not isinstance(payload["statement"], str):
            errors.append("'statement' must be a string")
        elif not payload["statement"].strip():
            errors.append("'statement' must not be empty")

        return len(errors) == 0, errors

    # Phase 22: Action-Type 特定必填字段
    ACTION_TYPE_REQUIRED_FIELDS = {
        "probe": {"question", "expected_answer"},
        "scaffold": {"steps"},
        "challenge": {"objective", "difficulty"},
        "suggest": {"options"},
        "reflect": {"question"},
        "defer": {"resume_condition"},
        "pulse": {"accept_label", "rewrite_label"},
        "excursion": {"bias_disabled"},
    }

    @classmethod
    def validate_by_action_type(cls, payload: dict, action_type: str) -> list[str]:
        """校验 action_type 特定的必填字段。

        Returns: 缺失字段名称列表（空列表 = 全部通过）
        """
        required = cls.ACTION_TYPE_REQUIRED_FIELDS.get(action_type, set())
        return [f"missing '{f}' for action_type '{action_type}'"
                for f in required if f not in payload]

    @classmethod
    def validate_with_type(cls, payload: dict, action_type: str | None = None
                           ) -> tuple[bool, list[str]]:
        """校验并附带 action_type 特定检查。"""
        is_valid, errors = cls.validate(payload)
        if action_type:
            type_errors = cls.validate_by_action_type(payload, action_type)
            errors.extend(type_errors)
        return len(errors) == 0, errors


# ── S2.1: DSL Schema Aligner ─────────────────────────────────

# 从 DSL 合约加载 action_type → slots 映射
def _load_dsl_slots() -> dict[str, set[str]]:
    from pathlib import Path
    contract_path = Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "coach_dsl.json"
    try:
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        return {a["id"]: set(a["slots"]) for a in contract.get("action_types", [])}
    except Exception:
        _logger.warning("Failed to load DSL contract, using empty slots")
        return {}

_ACTION_TYPE_SLOTS: dict[str, set[str]] = _load_dsl_slots()
_UNIVERSAL_KEYS = {"statement", "question", "hint", "difficulty", "steps", "topics"}


class LLMDSLAligner:
    """将 LLM 输出对齐到 DSL schema.

    核心逻辑:
    1. LLM 原始 payload → 提取合法字段（丢弃 DSL 不认识的字段）
    2. 校验 payload slots 与 action_type 是否匹配（来自 coach_dsl.json）
    3. 缺失 slot 用缺省值填充
    4. 返回对齐后的 payload + 对齐报告
    """

    @classmethod
    def align(cls, raw_payload: dict, action_type: str) -> tuple[dict, dict]:
        """对齐 LLM payload 到 DSL schema.

        Returns:
            (aligned_payload, alignment_report)
        """
        allowed_slots = _ACTION_TYPE_SLOTS.get(action_type, set()) | _UNIVERSAL_KEYS
        aligned: dict = {}
        dropped: list[str] = []
        filled: dict = {}

        for key, value in raw_payload.items():
            if key in allowed_slots:
                aligned[key] = value
            else:
                dropped.append(key)

        valid = len(aligned) > 0

        # 确保 statement 存在
        if "statement" not in aligned:
            # 尝试从其他文本字段迁移
            for text_key in ("question", "option", "step", "hint", "reason"):
                if text_key in aligned:
                    aligned["statement"] = aligned[text_key]
                    filled["statement"] = f"migrated_from_{text_key}"
                    break
            if "statement" not in aligned:
                aligned["statement"] = ""
                filled["statement"] = "default_empty"
                valid = False

        # Phase 11: scaffold/suggest 缺 steps 时自动生成
        if action_type in ("scaffold", "suggest") and "steps" not in aligned:
            generated = cls._generate_steps(aligned.get("statement", ""))
            if generated:
                aligned["steps"] = generated
                filled["steps"] = "auto_generated_from_statement"

        report = {
            "dropped_fields": dropped,
            "filled_slots": filled,
            "action_type": action_type,
            "allowed_slots": sorted(allowed_slots),
            "valid": valid,
        }
        return aligned, report

    @staticmethod
    def _generate_steps(statement: str) -> list[dict] | None:
        """从 statement 文本中自动提取步骤。按句子边界 + 序列标记分割。"""
        if not statement or len(statement) < 30:
            return None
        import re
        # 按序列标记分割: "1.", "第一步", "Step 1", "首先/然后/最后"
        markers = re.split(
            r'(?:(?:第)?[一二三四五六七八九十\d]+[步条个]|'
            r'(?:\d+[.\)]\s)|'
            r'(?:Step\s*\d)|'
            r'(?:step\s*\d)|'
            r'(?:First[,，\s])|(?:first[,，\s])|'
            r'(?:Then[,，\s])|(?:then[,，\s])|'
            r'(?:Next[,，\s])|(?:next[,，\s])|'
            r'(?:Finally[,，\s])|(?:finally[,，\s])|'
            r'(?:首先[,，\s])|'
            r'(?:然后[,，\s])|'
            r'(?:接下来[,，\s])|'
            r'(?:最后[,，\s])|'
            r'(?:接着[,，\s]))',
            statement)
        markers = [m.strip() for m in markers if m.strip()]
        if len(markers) < 2:
            # 尝试按句号分割
            sentences = [s.strip() for s in statement.split("。") if s.strip()]
            if len(sentences) >= 2 and len(sentences) <= 5:
                return [
                    {"order": i + 1, "action": s[:120], "expected": ""}
                    for i, s in enumerate(sentences[:4])
                ]
            return None
        result = []
        for i, text in enumerate(markers[:4]):
            cleaned = text.strip().rstrip(",，。.")
            if cleaned:
                result.append(
                    {"order": i + 1, "action": cleaned[:120], "expected": ""})
        return result if len(result) >= 2 else None


# ── S2.2: ActionType 强制 ─────────────────────────────────

def force_action_type(payload: dict, rule_action_type: str) -> dict:
    """确保 LLM payload 的 action_type 字段不被 LLM 篡改.
    移除 payload 中任何 llm_action_type 或类似的 LLM 自选字段.
    """
    payload.pop("action_type", None)
    payload.pop("llm_action_type", None)
    payload.pop("_action_type", None)
    return payload
