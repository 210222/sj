"""S9.4 全链路自适应降级集成测试.

API PulseService → WebSocket → 前端 useAdaptivePulse 一致性验证。
"""

import time

import pytest

from api.services.pulse_service import PulseService, get_pulse_service


class TestAdaptiveDegradationChain:
    """自适应降级全链路 — 3 次脉冲 → 2 次阻断 + 1 次降级."""

    def test_first_two_pulses_block_third_degraded(self):
        ps = PulseService()
        sid = "degradation-chain-1"

        # pulse 1 — should block (hard mode, count 0 < 2)
        assert ps.should_block(sid) is True
        ps.record_pulse(sid, "accept")
        assert ps.get_blocking_mode(sid) == "hard"

        # pulse 2 — should still block (hard mode, count 1 < 2)
        assert ps.should_block(sid) is True
        ps.record_pulse(sid, "accept")
        assert ps.get_blocking_mode(sid) == "soft"

        # pulse 3 — should NOT block (soft mode, count 2 >= 2)
        assert ps.should_block(sid) is False
        assert ps.get_blocking_mode(sid) == "soft"

    def test_blocking_mode_matches_should_block(self):
        """get_blocking_mode 与 should_block 语义一致."""
        ps = PulseService()
        sid = "consistency-check"

        # 初始
        assert ps.get_blocking_mode(sid) == "hard"
        assert ps.should_block(sid) is True

        # 两次脉冲后
        ps.record_pulse(sid, "accept")
        ps.record_pulse(sid, "rewrite")
        assert ps.get_blocking_mode(sid) == "soft"
        assert ps.should_block(sid) is False

    def test_soft_degradation_still_logs(self):
        """降级为 soft 后仍记录脉冲事件（不丢失审计链）."""
        ps = PulseService()
        sid = "audit-trail"

        ps.record_pulse(sid, "accept")
        ps.record_pulse(sid, "rewrite")
        assert ps.pulse_count(sid) == 2

        # 第三次脉冲 — 降级但记录
        ps.record_pulse(sid, "accept")
        assert ps.pulse_count(sid) == 3
        assert ps.get_blocking_mode(sid) == "soft"

    def test_window_resets_after_10_minutes(self):
        """10 分钟窗口过期后恢复 hard 模式."""
        ps = PulseService()
        sid = "window-reset"

        # 填充到降级
        ps.record_pulse(sid, "accept")
        ps.record_pulse(sid, "accept")
        assert ps.get_blocking_mode(sid) == "soft"

        # 手动篡改时间戳使其过期
        old_ts = time.time() - (10 * 60 + 1)
        ps._pulse_log[sid] = [old_ts]
        # 修剪后恢复 hard
        assert ps.get_blocking_mode(sid) == "hard"
        assert ps.should_block(sid) is True

    def test_different_sessions_independent(self):
        """不同 session 的脉冲计数独立."""
        ps = PulseService()
        ps.record_pulse("session-a", "accept")
        ps.record_pulse("session-a", "accept")

        # session-a 已降级
        assert ps.get_blocking_mode("session-a") == "soft"

        # session-b 仍为 hard
        assert ps.get_blocking_mode("session-b") == "hard"
        assert ps.should_block("session-b") is True


class TestDegradationBackendFrontendConsistency:
    """验证 PulseService 行为与前端 useAdaptivePulse 预期一致."""

    def test_max_blocking_constant_matches(self):
        """PULSE_MAX_BLOCKING 与前端常量一致."""
        from api.config import PULSE_MAX_BLOCKING
        assert PULSE_MAX_BLOCKING == 2, (
            "PULSE_MAX_BLOCKING must be 2 — must match frontend "
            "useAdaptivePulse.ts PULSE_MAX_BLOCKING"
        )

    def test_window_minutes_constant_matches(self):
        """PULSE_WINDOW_MINUTES 与前端常量一致."""
        from api.config import PULSE_WINDOW_MINUTES
        assert PULSE_WINDOW_MINUTES == 10, (
            "PULSE_WINDOW_MINUTES must be 10 — must match frontend "
            "useAdaptivePulse.ts PULSE_WINDOW_MS"
        )

    def test_hard_mode_means_blocking(self):
        """hard = 应展示 PulsePanel 阻断式."""
        ps = PulseService()
        ps.record_pulse("test", "accept")
        assert ps.get_blocking_mode("test") == "hard"
        assert ps.should_block("test") is True

    def test_soft_mode_means_non_blocking(self):
        """soft = 旁路软提示，不阻断."""
        ps = PulseService()
        ps.record_pulse("test", "accept")
        ps.record_pulse("test", "accept")
        assert ps.get_blocking_mode("test") == "soft"
        assert ps.should_block("test") is False


class TestGlobalPulseServiceSingleton:
    """全局 PulseService 单例测试."""

    def test_get_pulse_service_returns_singleton(self):
        ps1 = get_pulse_service()
        ps2 = get_pulse_service()
        assert ps1 is ps2

    def test_singleton_state_shared(self):
        ps = get_pulse_service()
        ps.record_pulse("singleton-test", "accept")
        ps2 = get_pulse_service()
        assert ps2.pulse_count("singleton-test") == 1
        # cleanup
        ps._pulse_log.pop("singleton-test", None)
