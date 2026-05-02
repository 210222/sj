"""M3: L1 Shock/Memory/Trend 残差估计器 — 规则法版。

Shock 偏离检测 → Memory 指数衰减累积 → Trend 多窗口方向 → correction + magnitude。
所有时间走 src.inner.clock，所有常量/类型走 src.middle.shared。
"""

from datetime import datetime, timezone

from src.inner.clock import get_window_30min, format_utc, parse_utc
from src.middle.shared.config import (
    L1_SHOCK_THRESHOLD,
    L1_MEMORY_DECAY_RATE,
    L1_TREND_MIN_WINDOWS,
    MIDDLE_CONFIG_VERSION,
)
from src.middle.shared.exceptions import StateEstimationError
from src.middle.shared.types import L1ResidualOutput

# ── correction 合法值 ─────────────────────────────────────────
CORRECTION_INCREASE = "increase"
CORRECTION_DECREASE = "decrease"
CORRECTION_NONE = "none"

VALID_CORRECTIONS = frozenset([CORRECTION_INCREASE, CORRECTION_DECREASE, CORRECTION_NONE])

MODEL_VERSION = "l1_v1.0.0"

_DEFAULT_WEIGHTS = {"shock": 0.6, "trend": 0.4}


class L1Estimator:
    """L1 Shock/Memory/Trend 残差估计器。

    输入：trace_id, event_time_utc, signals, context
    输出：L1ResidualOutput + 可审计字段
    """

    MODEL_VERSION = MODEL_VERSION

    def __init__(
        self,
        shock_threshold: float | None = None,
        memory_decay_rate: float | None = None,
        trend_min_windows: int | None = None,
    ):
        self.shock_threshold = (
            shock_threshold if shock_threshold is not None
            else L1_SHOCK_THRESHOLD
        )
        self.decay_rate = (
            memory_decay_rate if memory_decay_rate is not None
            else L1_MEMORY_DECAY_RATE
        )
        self.trend_min_windows = (
            trend_min_windows if trend_min_windows is not None
            else L1_TREND_MIN_WINDOWS
        )
        self._validate_config()

    def _validate_config(self) -> None:
        """禁止非法构造参数。"""
        if self.shock_threshold <= 0.0:
            raise StateEstimationError(
                f"shock_threshold must be > 0, got {self.shock_threshold}"
            )
        if not (0.0 <= self.decay_rate <= 1.0):
            raise StateEstimationError(
                f"memory_decay_rate must be in [0,1], got {self.decay_rate}"
            )
        if not isinstance(self.trend_min_windows, int) or self.trend_min_windows < 1:
            raise StateEstimationError(
                f"trend_min_windows must be int >= 1, got {self.trend_min_windows}"
            )

    # ── 公开入口 ───────────────────────────────────────────────

    def estimate(
        self,
        trace_id: str,
        event_time_utc: str,
        signals: dict,
        context: dict | None = None,
    ) -> dict:
        """执行 L1 扰动残差估计。

        Args:
            trace_id: 追溯 ID。
            event_time_utc: ISO 8601 UTC 事件时间。
            signals:
                - value: float [0,1] — 当前值
                - history: list[float] [0,1] — 近期窗口值序列
                - memory_state: float | None — 前序累积记忆 [0,1]
            context: 可选上下文（保留扩展）。

        Returns:
            {"correction": str, "magnitude": float,
             "shock_score": float, "memory_effect": float,
             "trend_score": float, "reason_code": str,
             "model_version": str, "config_version": str,
             "event_time_utc": str, "window_id": str,
             "evaluated_at_utc": str}

        Raises:
            StateEstimationError: 输入不合法。
        """
        ctx = context or {}
        self._validate_inputs(trace_id, event_time_utc, signals)

        value = signals["value"]
        history = signals.get("history", [])
        prev_memory = signals.get("memory_state", 0.0)
        if prev_memory is None:
            prev_memory = 0.0

        # 1. Shock 检测
        shock_score = self._compute_shock(value, history)

        # 2. Trend 检测
        trend_score, trend_direction = self._compute_trend(history)

        # 3. Memory 更新
        memory_effect = self._compute_memory(prev_memory, shock_score)

        # 4. Correction 判定
        correction, reason = self._determine_correction(
            shock_score, trend_score, trend_direction, value, history
        )

        # 5. Magnitude
        magnitude = self._compute_magnitude(shock_score, trend_score)

        window_id = get_window_30min(event_time_utc)

        return {
            "correction": correction,
            "magnitude": magnitude,
            "shock_score": shock_score,
            "memory_effect": memory_effect,
            "trend_score": trend_score,
            "reason_code": reason,
            "model_version": self.MODEL_VERSION,
            "config_version": MIDDLE_CONFIG_VERSION,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
        }

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

        if "value" not in signals:
            raise StateEstimationError("Missing required signal 'value'")
        val = signals["value"]
        if not isinstance(val, (int, float)):
            raise StateEstimationError(
                f"Signal 'value' must be numeric, got {type(val).__name__}"
            )
        if val < 0.0 or val > 1.0:
            raise StateEstimationError(f"Signal 'value' out of [0,1]: {val}")

        history = signals.get("history", [])
        if not isinstance(history, list):
            raise StateEstimationError("Signal 'history' must be a list")
        for i, h in enumerate(history):
            if not isinstance(h, (int, float)):
                raise StateEstimationError(
                    f"history[{i}] must be numeric, got {type(h).__name__}"
                )
            if h < 0.0 or h > 1.0:
                raise StateEstimationError(f"history[{i}] out of [0,1]: {h}")

        mem = signals.get("memory_state")
        if mem is not None and not isinstance(mem, (int, float)):
            raise StateEstimationError(
                f"memory_state must be numeric, got {type(mem).__name__}"
            )

    def _compute_shock(self, value: float, history: list[float]) -> float:
        """计算 shock 分数 [0,1]：当前值相对历史中位数的偏离。"""
        if not history:
            return 0.0
        median = self._median(history)
        deviation = abs(value - median)
        shock = deviation / self.shock_threshold if self.shock_threshold > 0 else 0.0
        return max(0.0, min(1.0, shock))

    def _compute_trend(self, history: list[float]) -> tuple[float, int]:
        """计算 trend 分数 [0,1] 与方向 (-1/0/+1)。

        需要至少 trend_min_windows 个数据点。
        """
        if len(history) < self.trend_min_windows:
            return 0.0, 0

        # 相邻差分平均值 → 斜率估计
        deltas = [history[i + 1] - history[i]
                  for i in range(len(history) - 1)]
        slope = sum(deltas) / len(deltas)

        direction = 1 if slope > 0 else (-1 if slope < 0 else 0)
        # 归一化：预期 0.2 的变化已显著
        trend_strength = abs(slope) / 0.2
        trend_score = max(0.0, min(1.0, trend_strength))
        return trend_score, direction

    def _compute_memory(self, prev_memory: float,
                        shock_score: float) -> float:
        """指数衰减更新累积记忆 [0,1]."""
        decayed = prev_memory * (1.0 - self.decay_rate)
        added = shock_score * self.decay_rate
        memory = decayed + added
        return max(0.0, min(1.0, memory))

    def _determine_correction(
        self,
        shock_score: float,
        trend_score: float,
        trend_direction: int,
        value: float,
        history: list[float],
    ) -> tuple[str, str]:
        """判定 correction 方向 + reason_code。"""
        median = self._median(history) if history else value

        # Shock 优先
        if shock_score > self.shock_threshold:
            if value > median:
                return CORRECTION_INCREASE, "L1_SHOCK_UP"
            else:
                return CORRECTION_DECREASE, "L1_SHOCK_DOWN"

        # Trend 其次
        if trend_score > 0.35:
            if trend_direction > 0:
                return CORRECTION_INCREASE, "L1_TREND_UP"
            elif trend_direction < 0:
                return CORRECTION_DECREASE, "L1_TREND_DOWN"

        return CORRECTION_NONE, "L1_NONE"

    def _compute_magnitude(self, shock_score: float,
                           trend_score: float) -> float:
        """加权合成 magnitude [0,1]."""
        w = _DEFAULT_WEIGHTS
        magnitude = shock_score * w["shock"] + trend_score * w["trend"]
        return max(0.0, min(1.0, magnitude))

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        n = len(s)
        if n % 2 == 0:
            return (s[n // 2 - 1] + s[n // 2]) / 2.0
        return s[n // 2]
