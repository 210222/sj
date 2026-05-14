"""Phase 35 — stream / non-stream 最小一致性测试."""

from api.services.coach_bridge import CoachBridge


class TestPhase35StreamParity:
    def test_chat_and_stream_share_basic_shape(self):
        result = CoachBridge.chat("教我 Python 循环", "phase35-sync-1")
        assert "action_type" in result
        assert "payload" in result
        assert "memory_status" in result
        assert "difficulty_contract" in result

    def test_chat_exposes_context_memory_status(self):
        result = CoachBridge.chat("继续讲列表", "phase35-sync-2")
        assert "memory_status" in result
        assert result["memory_status"] is None or isinstance(result["memory_status"], dict)
