"""M4: L2 COM-B 可行性估计器 — 规则法版。

输入 goal/resource/risk/conflict → base_feasibility + trend_adjust
→ uncertainty → action_bias (advance/hold/defer)。
所有常量/类型/异常走 src.middle.shared，所有时间走 src.inner.clock。
"""

import math
from datetime import datetime, timezone

from src.inner.clock import get_window_30min, format_utc, parse_utc
from src.middle.shared.config import (
    L2_CAPABILITY_MIN,
    L2_OPPORTUNITY_MIN,
    L2_MOTIVATION_MIN,
    MIDDLE_CONFIG_VERSION,
)
from src.middle.shared.exceptions import StateEstimationError

# ── action_bias 合法值 ────────────────────────────────────────
ACTION_ADVANCE = "advance"
ACTION_HOLD = "hold"
ACTION_DEFER = "defer"

VALID_ACTIONS = frozenset([ACTION_ADVANCE, ACTION_HOLD, ACTION_DEFER])

MODEL_VERSION = "l2_v1.0.0"

# 信号权重（总和=1.0）
_WEIGHTS = {
    "goal_clarity": 0.30,
    "resource_readiness": 0.30,
    "risk_pressure": 0.20,       # 取 (1-risk)
    "constraint_conflict": 0.20, # 取 (1-conflict)
}


class L2Estimator:
    """L2 COM-B 行为可行性估计器。

    判定阈值由 shared.config 的 L2_CAPABILITY_MIN / L2_OPPORTUNITY_MIN /
    L2_MOTIVATION_MIN 驱动，构造时可覆盖。

    输入：trace_id, event_time_utc, signals, context
    输出：feasibility + uncertainty + action_bias + 可审计字段
    """

    MODEL_VERSION = MODEL_VERSION

    def __init__(
        self,
        capability_min: float | None = None,
        opportunity_min: float | None = None,
        motivation_min: float | None = None,
    ):
        self.cap_min = (
            capability_min if capability_min is not None
            else L2_CAPABILITY_MIN
        )
        self.opp_min = (
            opportunity_min if opportunity_min is not None
            else L2_OPPORTUNITY_MIN
        )
        self.mot_min = (
            motivation_min if motivation_min is not None
            else L2_MOTIVATION_MIN
        )
        # 阈值由 config 驱动：hold_min = max(三个最小值)
        # advance_min = hold_min * 2 + 0.05
        self._hold_min = max(self.cap_min, self.opp_min, self.mot_min)
        self._advance_min = min(1.0, self._hold_min * 2.0 + 0.05)
        self._uncertainty_defer = 0.65
        self._uncertainty_hold_max = 0.50
        self._validate_config()

    def _validate_config(self) -> None:
        if self.cap_min < 0.0 or self.cap_min > 1.0:
            raise StateEstimationError(
                f"capability_min must be in [0,1], got {self.cap_min}"
            )
        if self.opp_min < 0.0 or self.opp_min > 1.0:
            raise StateEstimationError(
                f"opportunity_min must be in [0,1], got {self.opp_min}"
            )
        if self.mot_min < 0.0 or self.mot_min > 1.0:
            raise StateEstimationError(
                f"motivation_min must be in [0,1], got {self.mot_min}"
            )

    def estimate(
        self,
        trace_id: str,
        event_time_utc: str,
        signals: dict,
        context: dict | None = None,
    ) -> dict:
        """执行 L2 可行性估计。

        Args:
            trace_id: 追溯 ID。
            event_time_utc: ISO 8601 UTC 事件时间。
            signals:
                - goal_clarity: float [0,1]
                - resource_readiness: float [0,1]
                - risk_pressure: float [0,1]
                - constraint_conflict: float [0,1]
                可选:
                - history: list[float] — 历史 feasibility 值
                - prior_uncertainty: float | None — 上轮不确定度
            context: 可选上下文（保留扩展）。

        Returns:
            {"feasibility": float, "uncertainty": float,
             "action_bias": str, "reason_code": str,
             "feasible": bool, "block_reason": str,
             "model_version": str, "config_version": str,
             "event_time_utc": str, "window_id": str,
             "evaluated_at_utc": str}
        """
        ctx = context or {}
        self._validate_inputs(trace_id, event_time_utc, signals)

        g = signals["goal_clarity"]
        r = signals["resource_readiness"]
        p = signals["risk_pressure"]
        c = signals["constraint_conflict"]
        history = signals.get("history", [])
        prior_unc = signals.get("prior_uncertainty")

        # 1. base_feasibility
        base = (
            _WEIGHTS["goal_clarity"] * g
            + _WEIGHTS["resource_readiness"] * r
            + _WEIGHTS["risk_pressure"] * (1.0 - p)
            + _WEIGHTS["constraint_conflict"] * (1.0 - c)
        )

        # 2. trend_adjust
        trend_adj = self._compute_trend_adjust(history)

        feasibility = max(0.0, min(1.0, base + trend_adj))

        # 3. uncertainty
        uncertainty = self._compute_uncertainty(p, c, history, prior_unc)

        # 信号质量门控：任一信号低于 shared config 最小值 → 降可行度
        signal_quality_penalty = 0.0
        if g < self.cap_min:
            signal_quality_penalty += 0.10
        if r < self.opp_min:
            signal_quality_penalty += 0.10
        if (1.0 - c) < self.mot_min:
            signal_quality_penalty += 0.10
        feasibility = max(0.0, feasibility - signal_quality_penalty)

        # 4. action_bias
        action_bias, reason_code = self._determine_action(
            feasibility, uncertainty, p, c, history
        )

        # 5. resolver 兼容字段
        feasible = action_bias != ACTION_DEFER
        block_reason = reason_code if not feasible else ""

        window_id = get_window_30min(event_time_utc)

        return {
            "feasibility": feasibility,
            "uncertainty": uncertainty,
            "action_bias": action_bias,
            "reason_code": reason_code,
            "feasible": feasible,
            "block_reason": block_reason,
            "model_version": self.MODEL_VERSION,
            "config_version": MIDDLE_CONFIG_VERSION,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
        }

    # ── 校验 ─────────────────────────────────────────────────

    def _validate_inputs(self, trace_id: str, event_time_utc: str,
                         signals: dict) -> None:
        if not isinstance(trace_id, str) or not trace_id:
            raise StateEstimationError("trace_id must be a non-empty string")
        if not isinstance(event_time_utc, str) or not event_time_utc:
            raise StateEstimationError(
                "event_time_utc must be a non-empty string"
            )
        try:
            parse_utc(event_time_utc)
        except (ValueError, Exception) as e:
            raise StateEstimationError(f"Invalid event_time_utc: {e}") from e
        if not isinstance(signals, dict):
            raise StateEstimationError("signals must be a dict")

        required = [
            "goal_clarity", "resource_readiness",
            "risk_pressure", "constraint_conflict",
        ]
        for key in required:
            val = signals.get(key)
            if val is None:
                raise StateEstimationError(f"Missing required signal '{key}'")
            self._check_numeric(key, val)

        # 可选字段校验
        history = signals.get("history", [])
        if not isinstance(history, list):
            raise StateEstimationError("history must be a list")
        for i, h in enumerate(history):
            if h is None:
                raise StateEstimationError(f"history[{i}] is None")
            if isinstance(h, bool):
                raise StateEstimationError(
                    f"history[{i}] is bool, numeric required"
                )
            if not isinstance(h, (int, float)):
                raise StateEstimationError(
                    f"history[{i}] must be numeric, got {type(h).__name__}"
                )
            if h < 0.0 or h > 1.0:
                raise StateEstimationError(f"history[{i}] out of [0,1]: {h}")

        pu = signals.get("prior_uncertainty")
        if pu is not None:
            self._check_numeric("prior_uncertainty", pu)

    def _check_numeric(self, name: str, val) -> None:
        """拒绝 NaN/inf/bool/非数值/越界。"""
        if isinstance(val, bool):
            raise StateEstimationError(
                f"'{name}' is bool, numeric required"
            )
        if not isinstance(val, (int, float)):
            raise StateEstimationError(
                f"'{name}' must be numeric, got {type(val).__name__}"
            )
        if math.isnan(val) or math.isinf(val):
            raise StateEstimationError(
                f"'{name}' is NaN or Inf, not allowed"
            )
        if val < 0.0 or val > 1.0:
            raise StateEstimationError(
                f"'{name}' out of [0,1]: {val}"
            )

    # ── 内部计算 ─────────────────────────────────────────────

    def _compute_trend_adjust(self, history: list[float]) -> float:
        if len(history) < 2:
            return 0.0
        deltas = [history[i + 1] - history[i]
                  for i in range(len(history) - 1)]
        slope = sum(deltas) / len(deltas)
        return slope * 0.3  # 趋势影响系数

    def _compute_uncertainty(
        self,
        risk_pressure: float,
        constraint_conflict: float,
        history: list[float],
        prior_uncertainty: float | None,
    ) -> float:
        # 风险与冲突贡献
        risk_conflict = 0.4 * risk_pressure + 0.4 * constraint_conflict

        # 历史波动贡献
        hist_vol = 0.0
        if len(history) >= 2:
            mean = sum(history) / len(history)
            var = sum((h - mean) ** 2 for h in history) / len(history)
            hist_vol = min(1.0, math.sqrt(var) * 2.0)

        # 稀疏惩罚
        sparse = 0.0
        if len(history) < 2:
            sparse = 0.10
        if len(history) == 0:
            sparse = 0.15

        # 先验
        prior_weight = 0.0
        if prior_uncertainty is not None:
            prior_weight = prior_uncertainty * 0.15

        uncertainty = (
            0.40 * risk_conflict
            + 0.30 * hist_vol
            + 0.15 * sparse
            + 0.15 * prior_weight
        )
        return max(0.0, min(1.0, uncertainty))

    def _determine_action(
        self,
        feasibility: float,
        uncertainty: float,
        risk_pressure: float,
        constraint_conflict: float,
        history: list[float],
    ) -> tuple[str, str]:
        # 高冲突/高风险 → defer 优先
        if constraint_conflict > 0.75:
            return ACTION_DEFER, "L2_DEFER_CONFLICT"
        if risk_pressure > 0.80:
            return ACTION_DEFER, "L2_DEFER_RISK"

        # 稀疏输入 → hold
        if len(history) < 2:
            if feasibility >= self._advance_min and uncertainty < self._uncertainty_defer:
                return ACTION_ADVANCE, "L2_ADVANCE"
            return ACTION_HOLD, "L2_HOLD_SPARSE"

        # 主判定
        if uncertainty >= self._uncertainty_defer:
            return ACTION_DEFER, "L2_DEFER"
        if feasibility >= self._advance_min and uncertainty <= self._uncertainty_hold_max:
            return ACTION_ADVANCE, "L2_ADVANCE"
        if feasibility >= self._hold_min:
            return ACTION_HOLD, "L2_HOLD"
        return ACTION_DEFER, "L2_DEFER"
