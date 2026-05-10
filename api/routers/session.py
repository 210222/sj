"""会话路由 — POST /api/v1/session 创建/恢复会话."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from api.middleware.auth import get_iam
from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    ErrorResponse,
)
from api.services.coach_bridge import CoachBridge

router = APIRouter(tags=["session"])


@router.post(
    "/session",
    response_model=CreateSessionResponse,
    responses={429: {"model": ErrorResponse}},
)
async def create_session(req: CreateSessionRequest, request: Request):
    """创建或恢复会话，返回 TTM 阶段 + SDT 评分."""
    limiter = get_rate_limiter()
    client_key = f"session:{request.client.host if request.client else 'unknown'}"
    if not limiter.is_allowed(client_key, limit=10, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Too many session requests"},
        )

    iam = get_iam()
    token = req.token if req.token and iam.validate_token(req.token) else iam.issue_anonymous_token()
    session_id = req.session_id or __import__("uuid").uuid4().hex[:16]

    # 初始化状态树
    iam.update_session_state(token, session_id, {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ttm_stage": None,
    })

    ttm_stage = CoachBridge.get_ttm_stage(session_id)
    sdt_scores = CoachBridge.get_sdt_scores(session_id)

    return CreateSessionResponse(
        session_id=session_id,
        token=token,
        ttm_stage=ttm_stage,
        sdt_scores=sdt_scores,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
