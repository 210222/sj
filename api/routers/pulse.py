"""脉冲路由 — POST /api/v1/pulse/respond 接收接受/改写决策."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    ErrorResponse,
    PulseRespondRequest,
    PulseRespondResponse,
)
from api.services.coach_bridge import CoachBridge, _executor
from api.services.pulse_service import get_pulse_service

router = APIRouter(tags=["pulse"])


@router.post(
    "/pulse/respond",
    response_model=PulseRespondResponse,
    responses={429: {"model": ErrorResponse}},
)
async def pulse_respond(req: PulseRespondRequest, request: Request):
    """接收用户的脉冲决策（接受/改写）."""
    limiter = get_rate_limiter()
    key = f"pulse:{req.session_id}"
    if not limiter.is_allowed(key, limit=30, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Pulse respond rate limit exceeded"},
        )

    ps = get_pulse_service()
    ps.record_pulse(req.session_id, req.decision)
    blocking_mode = ps.get_blocking_mode(req.session_id)

    next_action = None
    if req.decision == "accept":
        next_action = {"action_type": "suggest", "payload": {"statement": "好的，我们继续。"}}
    elif req.decision == "rewrite":
        rewrite_text = req.rewrite_content or "用户重新定义前提"
        # 使用 run_in_executor 避免阻塞事件循环
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            CoachBridge.chat,
            rewrite_text,
            req.session_id,
        )
        next_action = {"action_type": result.get("action_type"), "payload": result.get("payload", {})}

    return PulseRespondResponse(
        status="ok",
        next_action=next_action,
        blocking_mode=blocking_mode,
    )
