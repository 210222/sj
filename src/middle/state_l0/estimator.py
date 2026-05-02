"""M2: L0 HBSSM 状态估计器 — 规则法版。

输入信号 → 复合分 → 滞回判定 → state + dwell_time + confidence。
所有时间走 src.inner.clock，所有常量/类型走 src.middle.shared。
"""

from datetime import datetime, timezone

from src.inner.clock import get_window_30min, format_utc, parse_utc
from src.middle.shared.config import (
    L0_DWELL_MIN_SECONDS,
    L0_SWITCH_PENALTY,
    L0_HYSTERESIS_ENTRY,
    L0_HYSTERESIS_EXIT,
    L0_MIN_SAMPLES,
    MIDDLE_CONFIG_VERSION,
)
from src.middle.shared.exceptions import StateEstimationError
from src.middle.shared.types import L0StateOutput

# ── 合法状态标签 ──────────────────────────────────────────────
STATE_ENGAGED = "engaged"
STATE_STABLE = "stable"
STATE_TRANSIENT = "transient"
STATE_VOLATILE = "volatile"

VALID_STATES = frozenset([STATE_ENGAGED, STATE_STABLE, STATE_TRANSIENT, STATE_VOLATILE])

# 状态→复合分阈值（不含滞回）
STATE_THRESHOLDS = {
    STATE_ENGAGED: L0_HYSTERESIS_ENTRY,
    STATE_STABLE: 0.50,
    STATE_TRANSIENT: 0.30,
    STATE_VOLATILE: 0.0,
}

# 状态降级顺序（高→低）
_DOWNGRADE_ORDER = [STATE_ENGAGED, STATE_STABLE, STATE_TRANSIENT, STATE_VOLATILE]

MODEL_VERSION = "l0_v1.0.0"

# 内部信号默认权重
_DEFAULT_WEIGHTS = {"engagement": 0.4, "stability": 0.35, "volatility": 0.25}


class L0Estimator:
    """L0 HBSSM 状态估计器。

    输入：trace_id, event_time_utc, signals, context
    输出：L0StateOutput + 可审计字段
    """

    MODEL_VERSION = MODEL_VERSION

    def __init__(
        self,
        dwell_min_seconds: float | None = None,
        switch_penalty: float | None = None,
        hysteresis_entry: float | None = None,
        hysteresis_exit: float | None = None,
        min_samples: int | None = None,
    ):
        self.dwell_min = (
            dwell_min_seconds if dwell_min_seconds is not None
            else L0_DWELL_MIN_SECONDS
        )
        self.switch_penalty = (
            switch_penalty if switch_penalty is not None
            else L0_SWITCH_PENALTY
        )
        self.h_entry = (
            hysteresis_entry if hysteresis_entry is not None
            else L0_HYSTERESIS_ENTRY
        )
        self.h_exit = (
            hysteresis_exit if hysteresis_exit is not None
            else L0_HYSTERESIS_EXIT
        )
        self.min_samples = (
            min_samples if min_samples is not None else L0_MIN_SAMPLES
        )

    # ── 公开入口 ───────────────────────────────────────────────

    def estimate(
        self,
        trace_id: str,
        event_time_utc: str,
        signals: dict,
        context: dict | None = None,
    ) -> dict:
        """执行 L0 状态估计。

        Args:
            trace_id: 追溯 ID。
            event_time_utc: ISO 8601 UTC 事件时间。
            signals: {"engagement": float, "stability": float,
                      "volatility": float}，值域 [0,1]。
            context: 可选上下文。可含:
                - prev_state: 前序状态标签
                - state_start_time_utc: 当前状态开始时间
                - sample_count: 本窗口有效样本数（用于样本门槛门控）

        Returns:
            {"state": str, "dwell_time": float, "confidence": float,
             "reason_code": str, "model_version": str,
             "config_version": str,
             "event_time_utc": str, "window_id": str,
             "evaluated_at_utc": str}

        Raises:
            StateEstimationError: 输入不合法。
        """
        ctx = context or {}
        self._validate_inputs(trace_id, event_time_utc, signals)

        composite = self._compute_composite(signals)
        prev_state = ctx.get("prev_state")
        state_start = ctx.get("state_start_time_utc")
        sample_count = ctx.get("sample_count")

        # 滞回判定
        state, reason = self._determine_state(composite, prev_state)

        # 驻留时间
        dwell_time = self._compute_dwell(state, prev_state, state_start, event_time_utc)

        # 置信度
        confidence = self._compute_confidence(composite, state, signals)

        # 样本门槛门控
        low_samples = (
            sample_count is not None
            and isinstance(sample_count, int)
            and sample_count < self.min_samples
        )
        if low_samples:
            confidence = min(confidence, 0.30)
            reason = f"{reason}_LOW_SAMPLES"

        # 窗口
        window_id = get_window_30min(event_time_utc)

        result = {
            "state": state,
            "dwell_time": dwell_time,
            "confidence": confidence,
            "reason_code": reason,
            "model_version": self.MODEL_VERSION,
            "config_version": MIDDLE_CONFIG_VERSION,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
        }
        return result

    # ── 内部方法 ───────────────────────────────────────────────

    def _validate_inputs(self, trace_id: str, event_time_utc: str,
                         signals: dict) -> None:
        if not isinstance(trace_id, str) or not trace_id:
            raise StateEstimationError("trace_id must be a non-empty string")
        if not isinstance(event_time_utc, str) or not event_time_utc:
            raise StateEstimationError("event_time_utc must be a non-empty string")
        try:
            parse_utc(event_time_utc)
        except (ValueError, Exception) as e:
            raise StateEstimationError(f"Invalid event_time_utc: {e}") from e
        if not isinstance(signals, dict):
            raise StateEstimationError("signals must be a dict")

        for key in ("engagement", "stability", "volatility"):
            val = signals.get(key)
            if val is None:
                raise StateEstimationError(
                    f"Missing required signal '{key}'"
                )
            if not isinstance(val, (int, float)):
                raise StateEstimationError(
                    f"Signal '{key}' must be numeric, got {type(val).__name__}"
                )
            if val < 0.0 or val > 1.0:
                raise StateEstimationError(
                    f"Signal '{key}' out of [0,1]: {val}"
                )

    def _compute_composite(self, signals: dict) -> float:
        w = _DEFAULT_WEIGHTS
        inv_volatility = 1.0 - signals["volatility"]
        composite = (
            w["engagement"] * signals["engagement"]
            + w["stability"] * signals["stability"]
            + w["volatility"] * inv_volatility
        )
        return max(0.0, min(1.0, composite))

    def _determine_state(self, composite: float,
                         prev_state: str | None) -> tuple[str, str]:
        """滞回状态判定。

        Returns:
            (state, reason_code)
        """
        # 无前序状态 → 直接映射
        if prev_state is None or prev_state not in VALID_STATES:
            state = self._map_composite_to_state(composite)
            return state, f"L0_{state.upper()}_INIT"

        # 检查是否应上行
        next_higher = self._next_higher_state(prev_state)
        if next_higher is not None:
            next_threshold = STATE_THRESHOLDS[next_higher]
            if composite >= next_threshold + self.switch_penalty:
                return next_higher, f"L0_{next_higher.upper()}_UP"

        # 检查是否应下行
        current_threshold = STATE_THRESHOLDS[prev_state]
        exit_margin = (L0_HYSTERESIS_ENTRY - L0_HYSTERESIS_EXIT) * 0.5
        if composite < current_threshold - exit_margin:
            next_lower = self._next_lower_state(prev_state)
            if next_lower is not None:
                return next_lower, f"L0_{next_lower.upper()}_DOWN"

        # 维持当前状态
        return prev_state, f"L0_{prev_state.upper()}_HOLD"

    def _map_composite_to_state(self, composite: float) -> str:
        if composite >= STATE_THRESHOLDS[STATE_ENGAGED]:
            return STATE_ENGAGED
        elif composite >= STATE_THRESHOLDS[STATE_STABLE]:
            return STATE_STABLE
        elif composite >= STATE_THRESHOLDS[STATE_TRANSIENT]:
            return STATE_TRANSIENT
        return STATE_VOLATILE

    def _next_higher_state(self, state: str) -> str | None:
        order = _DOWNGRADE_ORDER
        idx = order.index(state)
        return order[idx - 1] if idx > 0 else None

    def _next_lower_state(self, state: str) -> str | None:
        order = _DOWNGRADE_ORDER
        idx = order.index(state)
        return order[idx + 1] if idx < len(order) - 1 else None

    def _compute_dwell(self, state: str, prev_state: str | None,
                       state_start: str | None,
                       event_time_utc: str) -> float:
        """计算当前状态驻留时间（秒）。"""
        if prev_state == state and state_start:
            try:
                start_dt = parse_utc(state_start)
                event_dt = parse_utc(event_time_utc)
                dwell = (event_dt - start_dt).total_seconds()
                return max(0.0, dwell)
            except (ValueError, Exception):
                pass
        return 0.0

    def _compute_confidence(self, composite: float, state: str,
                            signals: dict) -> float:
        """基于到最近阈值的距离计算置信度 [0,1]."""
        threshold = STATE_THRESHOLDS.get(state, 0.0)

        # 到当前状态阈值的距离
        if state == STATE_VOLATILE:
            # volatile: 距离越远（composite越低）越确信
            distance = 0.30 - composite
        else:
            distance = composite - threshold

        # 信号一致性
        vals = [signals.get(k, 0.5) for k in ("engagement", "stability")]
        consistency = 1.0 - max(vals) + min(vals)  # max-min spread
        consistency = max(0.0, min(1.0, consistency))

        confidence = 0.5 + 0.5 * (distance / 0.3) + 0.2 * consistency
        return max(0.0, min(1.0, confidence))
