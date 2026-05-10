"""PulseService — 自适应降级.

单会话 10 分钟内阻断式脉冲最多 2 次。
超阈值后自动降级为"旁路软提示"。
"""

from __future__ import annotations

import time

from api.config import PULSE_MAX_BLOCKING, PULSE_WINDOW_MINUTES


class PulseService:
    """自适应降级脉冲管理."""

    def __init__(self) -> None:
        # session_id → list of pulse timestamps
        self._pulse_log: dict[str, list[float]] = {}

    def should_block(self, session_id: str) -> bool:
        """窗口内脉冲 < MAX_BLOCKING → True(阻断); ≥ → False(旁路)."""
        self._prune_window(session_id)
        return len(self._pulse_log.get(session_id, [])) < PULSE_MAX_BLOCKING

    def record_pulse(self, session_id: str, decision: str) -> None:
        """记录一次脉冲事件."""
        entry = {"ts": time.time(), "decision": decision}
        self._pulse_log.setdefault(session_id, []).append(entry["ts"])

    def get_blocking_mode(self, session_id: str) -> str:
        """返回 'hard' | 'soft' | 'none'.

        - hard: 未超阈值，应阻断并展示 PulsePanel
        - soft: 超阈值降级，旁路软提示，不阻断流程
        - none: 正常情况下非高强度动作
        """
        self._prune_window(session_id)
        pulses = self._pulse_log.get(session_id, [])
        if len(pulses) >= PULSE_MAX_BLOCKING:
            return "soft"
        return "hard"

    def pulse_count(self, session_id: str) -> int:
        """返回窗口内脉冲计数."""
        self._prune_window(session_id)
        return len(self._pulse_log.get(session_id, []))

    def _prune_window(self, session_id: str) -> None:
        """清理超出时间窗口的脉冲记录."""
        if session_id not in self._pulse_log:
            return
        cutoff = time.time() - PULSE_WINDOW_MINUTES * 60
        self._pulse_log[session_id] = [
            ts for ts in self._pulse_log[session_id] if ts > cutoff
        ]


# 全局单例
_pulse_service: PulseService | None = None


def get_pulse_service() -> PulseService:
    global _pulse_service
    if _pulse_service is None:
        _pulse_service = PulseService()
    return _pulse_service
