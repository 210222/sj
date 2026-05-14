"""仪表盘路由 — GET /api/v1/dashboard/user."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    ErrorResponse,
    ProgressData,
    SDTRingsData,
    TTMRadarData,
    UserDashboardResponse,
)
from api.services.dashboard_aggregator import DashboardAggregator

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard/user",
    response_model=UserDashboardResponse,
    responses={429: {"model": ErrorResponse}},
)
async def get_user_dashboard(
    session_id: str = Query(..., description="会话 ID"),
    request: Request = None,  # noqa: ARG001 — 用于中间件注入
):
    """获取用户仪表盘数据：TTM 雷达 + SDT 环 + 进度."""
    limiter = get_rate_limiter()
    key = f"dashboard:{session_id}"
    if not limiter.is_allowed(key, limit=10, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Dashboard rate limit exceeded"},
        )

    agg = DashboardAggregator(session_id)
    ttm_data = agg.get_ttm_radar()
    sdt_data = agg.get_sdt_rings()
    progress_data = agg.get_progress()

    # Phase 29 P2-7: mastery_snapshot
    snap = None
    try:
        snap = agg.get_mastery_snapshot()
    except Exception:
        pass

    # Phase 36+37: LLM runtime observability (global + session)
    llm_runtime = DashboardAggregator.get_llm_runtime_summary()
    session_llm = DashboardAggregator.get_session_llm_summary(session_id)

    return UserDashboardResponse(
        session_id=session_id,
        ttm_radar=TTMRadarData(**ttm_data),
        sdt_rings=SDTRingsData(**sdt_data),
        progress=ProgressData(**progress_data),
        mastery_snapshot=snap,
        review_queue=agg.get_review_queue(),
        llm_runtime_summary=llm_runtime,
        session_llm_summary=session_llm,
    )
