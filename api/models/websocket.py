"""WebSocket 消息类型枚举."""

from __future__ import annotations

from enum import Enum
from typing import Any


class WSMessageType(str, Enum):
    USER_MESSAGE = "user_message"
    COACH_RESPONSE = "coach_response"
    COACH_CHUNK = "coach_chunk"
    COACH_STREAM_END = "coach_stream_end"
    SAFETY_OVERRIDE = "safety_override"
    PULSE_EVENT = "pulse_event"
    PULSE_DECISION = "pulse_decision"
    PULSE_TIMEOUT = "pulse_timeout"
    EXCURSION_EVENT = "excursion_event"
    ERROR = "error"


# 服务端 → 客户端消息格式
WSMessage = dict[str, Any]
