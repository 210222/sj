"""远足路由 — POST /api/v1/excursion/enter|exit."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    ErrorResponse,
    ExcursionEnterRequest,
    ExcursionEnterResponse,
    ExcursionExitRequest,
    ExcursionExitResponse,
)

router = APIRouter(tags=["excursion"])


@router.post(
    "/excursion/enter",
    response_model=ExcursionEnterResponse,
    responses={429: {"model": ErrorResponse}},
)
async def enter_excursion(req: ExcursionEnterRequest, request: Request):
    """进入远足模式——全局暗调主题切换."""
    limiter = get_rate_limiter()
    key = f"excursion:enter:{req.session_id}"
    if not limiter.is_allowed(key, limit=5, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Excursion enter rate limit exceeded"},
        )

    excursion_id = uuid.uuid4().hex[:16]
    return ExcursionEnterResponse(
        status="ok",
        excursion_id=excursion_id,
        theme="dark",
    )


@router.post(
    "/excursion/exit",
    response_model=ExcursionExitResponse,
    responses={429: {"model": ErrorResponse}},
)
async def exit_excursion(req: ExcursionExitRequest, request: Request):
    """退出远足模式——恢复默认主题."""
    limiter = get_rate_limiter()
    key = f"excursion:exit:{req.session_id}"
    if not limiter.is_allowed(key, limit=10, window_s=60):  # exit 更宽松
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Excursion exit rate limit exceeded"},
        )

    return ExcursionExitResponse(status="ok")
