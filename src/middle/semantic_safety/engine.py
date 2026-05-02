"""M6: 语义安全引擎 — 规则法版。

P0 硬阻断 → P1/gate 联合降级 → safety_score 阈值判定
→ allowed + audit_level + sanitized_output。
所有常量/类型/异常走 src.middle.shared，所有时间走 src.inner.clock。
"""

import math
from datetime import datetime, timezone

from src.inner.clock import get_window_30min, format_utc, parse_utc
from src.middle.shared.config import (
    SEMANTIC_SAFETY_MIN_SCORE,
    SEMANTIC_SAFETY_BLOCK_THRESHOLD,
    MIDDLE_CONFIG_VERSION,
)
from src.middle.shared.constants import (
    AUDIT_LEVELS,
    GATE_DECISIONS,
    INTERVENTION_INTENSITIES,
)
from src.middle.shared.exceptions import StateEstimationError

# ── 审计等级 ─────────────────────────────────────────────────
AUDIT_PASS = "pass"
AUDIT_P1_WARN = "p1_warn"
AUDIT_P1_FREEZE = "p1_freeze"
AUDIT_P0_BLOCK = "p0_block"

MODEL_VERSION = "sem_safety_v1.0.0"

# 强度降级顺序
_INTENSITY_ORDER = ["full", "reduced", "minimal", "none"]


def _downgrade_intensity(current: str, steps: int = 1) -> str:
    if current not in _INTENSITY_ORDER:
        return "none"
    idx = _INTENSITY_ORDER.index(current)
    new_idx = min(len(_INTENSITY_ORDER) - 1, idx + steps)
    return _INTENSITY_ORDER[new_idx]


class SemanticSafetyEngine:
    """语义安全闸门引擎。

    输入：trace_id, event_time_utc, candidate, context
    输出：allowed + safety_score + audit_level + sanitized_output + 审计字段
    """

    MODEL_VERSION = MODEL_VERSION

    def __init__(
        self,
        min_score: float | None = None,
        block_threshold: float | None = None,
    ):
        self.min_score = (
            min_score if min_score is not None
            else SEMANTIC_SAFETY_MIN_SCORE
        )
        self.block_threshold = (
            block_threshold if block_threshold is not None
            else SEMANTIC_SAFETY_BLOCK_THRESHOLD
        )
        self._validate_config()

    def _validate_config(self) -> None:
        if not (0.0 <= self.block_threshold < self.min_score <= 1.0):
            raise StateEstimationError(
                f"Invalid thresholds: block_threshold={self.block_threshold}, "
                f"min_score={self.min_score}. Require 0 <= block < min <= 1"
            )

    # ── 主入口 ───────────────────────────────────────────────

    def evaluate(
        self,
        trace_id: str,
        event_time_utc: str,
        candidate: dict,
        context: dict | None = None,
    ) -> dict:
        """执行语义安全评估。

        Args:
            trace_id: 追溯 ID。
            event_time_utc: ISO 8601 UTC。
            candidate:
                - intensity: str — full/reduced/minimal/none
                - reason_code: str
                可选: text, action_plan, metadata
            context:
                - p0_count: int/float — P0 字段缺失数
                - p1_count: int/float — P1 字段缺失数
                - gate_decision: str — GO/WARN/FREEZE
                可选: risk_flags: list[str]

        Returns:
            {"allowed": bool, "safety_score": float,
             "audit_level": str, "reason_code": str,
             "sanitized_output": dict,
             "model_version": str, "config_version": str,
             "event_time_utc": str, "window_id": str,
             "evaluated_at_utc": str}
        """
        self._validate_raw_context(context)
        ctx = context or {}
        self._validate_inputs(trace_id, event_time_utc, candidate, ctx)

        p0_count = ctx.get("p0_count", 0)
        p1_count = ctx.get("p1_count", 0)
        gate_decision = ctx.get("gate_decision", "GO")
        risk_flags = ctx.get("risk_flags", [])

        # 1. P0 硬阻断
        if p0_count > 0:
            sanitized = self._sanitize(candidate, AUDIT_P0_BLOCK)
            return self._make_result(
                False, 0.0, AUDIT_P0_BLOCK, "SEM_BLOCK_P0",
                sanitized, event_time_utc,
            )

        # 2. 计算 safety_score
        safety_score = self._compute_safety(
            candidate, p1_count, gate_decision, risk_flags
        )

        # 3. 阈值判定 audit_level
        if safety_score < self.block_threshold:
            audit_level = AUDIT_P0_BLOCK
            reason = "SEM_BLOCK_LOW_SCORE"
            allowed = False
        elif safety_score < self.min_score:
            if gate_decision == "FREEZE":
                audit_level = AUDIT_P1_FREEZE
                reason = "SEM_FREEZE_GATE"
            else:
                audit_level = AUDIT_P1_FREEZE if p1_count > 0 else AUDIT_P1_WARN
                reason = "SEM_WARN_P1" if p1_count > 0 else "SEM_WARN"
            allowed = False
        else:
            # score >= min_score
            if p1_count > 0 or gate_decision == "WARN":
                audit_level = AUDIT_P1_WARN
                reason = "SEM_WARN_P1" if p1_count > 0 else "SEM_WARN_GATE"
                allowed = True
            elif gate_decision == "FREEZE":
                audit_level = AUDIT_P1_FREEZE
                reason = "SEM_FREEZE_GATE"
                allowed = False
            else:
                audit_level = AUDIT_PASS
                reason = "SEM_PASS"
                allowed = True

        # 4. sanitized_output
        sanitized = self._sanitize(candidate, audit_level)

        return self._make_result(
            allowed, safety_score, audit_level, reason,
            sanitized, event_time_utc,
        )

    # ── 安全分计算 ───────────────────────────────────────────

    def _compute_safety(
        self,
        candidate: dict,
        p1_count: float,
        gate_decision: str,
        risk_flags: list[str],
    ) -> float:
        base = 0.85

        # P1 惩罚：每个 P1 缺失扣 0.12
        p1_penalty = p1_count * 0.12

        # Gate 惩罚
        if gate_decision == "FREEZE":
            gate_penalty = 0.35
        elif gate_decision == "WARN":
            gate_penalty = 0.15
        else:
            gate_penalty = 0.0

        # 风险标记惩罚
        risk_penalty = len(risk_flags) * 0.08

        # 强度相关调整
        intensity = candidate.get("intensity", "none")
        if intensity == "none":
            intensity_bonus = 0.05  # 保守策略略安全
        elif intensity == "full":
            intensity_bonus = -0.05  # 激进策略略降安全
        else:
            intensity_bonus = 0.0

        score = base - p1_penalty - gate_penalty - risk_penalty + intensity_bonus
        return max(0.0, min(1.0, score))

    # ── 输出清洗 ─────────────────────────────────────────────

    def _sanitize(self, candidate: dict, audit_level: str) -> dict:
        out = dict(candidate)

        if audit_level == AUDIT_P0_BLOCK:
            # 阻断：最安全降级
            out["intensity"] = "none"
            out["reason_code"] = "SEM_BLOCKED"
            out.pop("action_plan", None)
            out.pop("metadata", None)
            out["_safety_audit"] = audit_level
        elif audit_level == AUDIT_P1_FREEZE:
            # 冻结：降一级强度，清除敏感字段
            cur = out.get("intensity", "none")
            out["intensity"] = _downgrade_intensity(cur, 1)
            out.pop("metadata", None)
            out["_safety_audit"] = audit_level
        elif audit_level == AUDIT_P1_WARN:
            # 告警：保留但标记
            out["_safety_audit"] = audit_level
        else:
            # pass：原样返回
            out["_safety_audit"] = audit_level

        return out

    # ── 结果包装 ─────────────────────────────────────────────

    def _make_result(
        self,
        allowed: bool,
        safety_score: float,
        audit_level: str,
        reason_code: str,
        sanitized_output: dict,
        event_time_utc: str,
    ) -> dict:
        if audit_level not in AUDIT_LEVELS:
            raise StateEstimationError(
                f"Internal: audit_level '{audit_level}' not in AUDIT_LEVELS"
            )
        window_id = get_window_30min(event_time_utc)
        return {
            "allowed": allowed,
            "safety_score": safety_score,
            "audit_level": audit_level,
            "reason_code": reason_code,
            "sanitized_output": sanitized_output,
            "model_version": self.MODEL_VERSION,
            "config_version": MIDDLE_CONFIG_VERSION,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
        }

    def _validate_raw_context(self, context) -> None:
        if context is not None and not isinstance(context, dict):
            raise StateEstimationError(
                f"context must be dict or None, got {type(context).__name__}"
            )

    # ── 输入校验 ─────────────────────────────────────────────

    def _validate_inputs(self, trace_id: str, event_time_utc: str,
                         candidate: dict, context: dict) -> None:
        if not isinstance(trace_id, str) or not trace_id:
            raise StateEstimationError("trace_id must be a non-empty string")
        if not isinstance(event_time_utc, str) or not event_time_utc:
            raise StateEstimationError("event_time_utc must be a non-empty string")
        try:
            parse_utc(event_time_utc)
        except (ValueError, Exception) as e:
            raise StateEstimationError(f"Invalid event_time_utc: {e}") from e
        if not isinstance(candidate, dict):
            raise StateEstimationError("candidate must be a dict")
        if not isinstance(context, dict):
            raise StateEstimationError("context must be a dict")

        # candidate 校验
        intensity = candidate.get("intensity")
        if intensity is None:
            raise StateEstimationError("candidate missing 'intensity'")
        if not isinstance(intensity, str):
            raise StateEstimationError(
                f"intensity must be str, got {type(intensity).__name__}"
            )
        if intensity not in INTERVENTION_INTENSITIES:
            raise StateEstimationError(
                f"intensity '{intensity}' not in {INTERVENTION_INTENSITIES}"
            )
        if "reason_code" not in candidate:
            raise StateEstimationError("candidate missing 'reason_code'")
        if not isinstance(candidate["reason_code"], str):
            raise StateEstimationError(
                f"reason_code must be str, got {type(candidate['reason_code']).__name__}"
            )

        # context 数值校验
        for key in ("p0_count", "p1_count"):
            val = context.get(key, 0)
            if isinstance(val, bool):
                raise StateEstimationError(
                    f"{key} is bool, numeric required"
                )
            if not isinstance(val, (int, float)):
                raise StateEstimationError(
                    f"{key} must be numeric, got {type(val).__name__}"
                )
            if math.isnan(val) or math.isinf(val):
                raise StateEstimationError(f"{key} is NaN or Inf")
            if val < 0:
                raise StateEstimationError(f"{key} must be >= 0, got {val}")

        gate = context.get("gate_decision", "GO")
        if not isinstance(gate, str):
            raise StateEstimationError(
                f"gate_decision must be str, got {type(gate).__name__}"
            )
        if gate not in GATE_DECISIONS:
            raise StateEstimationError(
                f"gate_decision '{gate}' not in {GATE_DECISIONS}"
            )

        risk_flags = context.get("risk_flags", [])
        if not isinstance(risk_flags, list):
            raise StateEstimationError("risk_flags must be a list")
        for i, flag in enumerate(risk_flags):
            if not isinstance(flag, str):
                raise StateEstimationError(
                    f"risk_flags[{i}] must be str, got {type(flag).__name__}"
                )
