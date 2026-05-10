"""对话路由 — POST /api/v1/chat + WebSocket /api/v1/chat/ws."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from api.config import WS_MAX_IDLE_S, WS_PING_INTERVAL_S
from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ErrorResponse,
)
from api.models.websocket import WSMessageType
from api.services.coach_bridge import CoachBridge, _executor
from api.services.pulse_service import get_pulse_service

router = APIRouter(tags=["chat"])

# WebSocket 消息限流
WS_MSG_LIMIT_PER_SESSION = 20
WS_MSG_WINDOW_S = 1.0


def _should_stream() -> bool:
    """检查 LLM 流式是否启用."""
    from pathlib import Path
    import yaml
    try:
        cfg_path = Path(__file__).resolve().parent.parent.parent / \
            "config" / "coach_defaults.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        llm = cfg.get("llm", {})
        return llm.get("enabled", False) and llm.get("streaming", False)
    except Exception:
        return False


@router.post(
    "/chat",
    response_model=ChatMessageResponse,
    responses={429: {"model": ErrorResponse}},
)
async def chat(req: ChatMessageRequest, request: Request):
    """消息 → CoachAgent → DSL 响应."""
    limiter = get_rate_limiter()
    key = f"chat:{req.session_id}"
    if not limiter.is_allowed(key, limit=30, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Chat rate limit exceeded"},
        )

    # 使用 run_in_executor 避免阻塞事件循环
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        CoachBridge.chat,
        req.message,
        req.session_id,
    )

    # 如果是 pulse，记录到 PulseService
    pulse = result.get("pulse")
    if pulse:
        ps = get_pulse_service()
        blocking_mode = ps.get_blocking_mode(req.session_id)
        pulse["blocking_mode"] = blocking_mode

    return ChatMessageResponse(**result)


@router.websocket("/chat/ws")
async def chat_websocket(ws: WebSocket):
    """WebSocket 实时推流通道."""
    await ws.accept()
    last_msg_time = asyncio.get_event_loop().time()
    msg_timestamps: list[float] = []  # WS 消息级限流

    async def _send(msg_type: WSMessageType, data: dict) -> None:
        await ws.send_json({"type": msg_type.value, **data})

    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    ws.receive_text(), timeout=WS_PING_INTERVAL_S
                )
                last_msg_time = asyncio.get_event_loop().time()
            except asyncio.TimeoutError:
                await ws.send_json({"type": "ping"})
                idle = asyncio.get_event_loop().time() - last_msg_time
                if idle > WS_MAX_IDLE_S:
                    await ws.close(code=1000, reason="idle timeout")
                    return
                continue

            # WebSocket 消息级限流
            now = asyncio.get_event_loop().time()
            msg_timestamps[:] = [t for t in msg_timestamps if t > now - WS_MSG_WINDOW_S]
            if len(msg_timestamps) >= WS_MSG_LIMIT_PER_SESSION:
                await _send(WSMessageType.ERROR, {"detail": "rate limited"})
                continue
            msg_timestamps.append(now)

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(WSMessageType.ERROR, {"detail": "invalid json"})
                continue

            msg_type = msg.get("type", WSMessageType.USER_MESSAGE.value)
            session_id = msg.get("session_id", "unknown")
            content = msg.get("content", "")

            if msg_type == WSMessageType.USER_MESSAGE.value:
                # 尝试流式路径
                if _should_stream():
                    try:
                        async for event in CoachBridge.chat_stream(
                                content, session_id):
                            await ws.send_json(event)
                    except Exception:
                        await _send(WSMessageType.ERROR,
                                    {"detail": "stream failed"})
                    continue

                # 非流式路径（不变）
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    _executor,
                    CoachBridge.chat,
                    content,
                    session_id,
                )

                pulse = result.get("pulse")
                if pulse:
                    ps = get_pulse_service()
                    blocking_mode = ps.get_blocking_mode(session_id)
                    pulse["blocking_mode"] = blocking_mode
                    await _send(WSMessageType.PULSE_EVENT, pulse)

                await _send(WSMessageType.COACH_RESPONSE, {
                    "action_type": result.get("action_type"),
                    "payload": result.get("payload", {}),
                    "trace_id": result.get("trace_id"),
                    "intent": result.get("intent"),
                    "domain_passport": result.get("domain_passport"),
                    "safety_allowed": result.get("safety_allowed"),
                    "gate_decision": result.get("gate_decision"),
                    "audit_level": result.get("audit_level"),
                    "ttm_stage": result.get("ttm_stage"),
                    "sdt_profile": result.get("sdt_profile"),
                    "flow_channel": result.get("flow_channel"),
                    # Phase 10+13+15: LLM/diagnostic/personalization parity
                    "llm_generated": result.get("llm_generated"),
                    "llm_model": result.get("llm_model"),
                    "llm_tokens": result.get("llm_tokens"),
                    "diagnostic_result": result.get("diagnostic_result"),
                    "diagnostic_probe": result.get("diagnostic_probe"),
                    "personalization_evidence": result.get("personalization_evidence"),
                    "memory_status": result.get("memory_status"),
                    "difficulty_contract": result.get("difficulty_contract"),
                })

            elif msg_type == WSMessageType.PULSE_DECISION.value:
                ps = get_pulse_service()
                decision = msg.get("decision", "accept")
                ps.record_pulse(session_id, decision)
                await _send(WSMessageType.COACH_RESPONSE, {
                    "status": "ok",
                    "blocking_mode": ps.get_blocking_mode(session_id),
                })

    except WebSocketDisconnect:
        pass
