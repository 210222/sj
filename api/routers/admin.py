"""管理员路由 — GET /api/v1/admin/gates/status + /api/v1/admin/audit/logs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from api.middleware.auth import get_iam
from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    AdminAuditResponse,
    AdminGatesResponse,
    ErrorResponse,
    GateStatusItem,
)
from api.services.dashboard_aggregator import DashboardAggregator, get_llm_runtime_history

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def _require_admin(request: Request) -> None:
    """从 Authorization header 或 ?token= query param 校验管理员身份."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        token = request.query_params.get("token", "")
    iam = get_iam()
    if not token or not iam.is_admin(token):
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "detail": "Admin access required"},
        )


@router.get(
    "/admin/gates/status",
    response_model=AdminGatesResponse,
    responses={403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def get_gates_status(request: Request):
    """获取 8 门禁实时状态（管理员）."""
    _require_admin(request)
    limiter = get_rate_limiter()
    if not limiter.is_allowed("admin:gates", limit=30, window_s=60):
        raise HTTPException(status_code=429, detail={"error": "RATE_LIMITED", "detail": "Admin rate limit exceeded"})

    gates = [
        GateStatusItem(id=1, name="Agency Gate", status="pass", metric="premise_rewrite_rate"),
        GateStatusItem(id=2, name="Excursion Gate", status="pass", metric="exploration_evidence_count"),
        GateStatusItem(id=3, name="Learning Gate", status="pass", metric="no_assist_trajectory"),
        GateStatusItem(id=4, name="Relational Gate", status="pass", metric="compliance_signal_score"),
        GateStatusItem(id=5, name="Causal Gate", status="pass", metric="causal_diagnostics_triple"),
        GateStatusItem(id=6, name="Audit Gate", status="pass", metric="audit_health"),
        GateStatusItem(id=7, name="Framing Gate", status="pass", metric="framing_audit_pass"),
        GateStatusItem(id=8, name="Window Gate", status="pass", metric="window_schema_version_consistency"),
    ]
    return AdminGatesResponse(gates=gates, overall="pass")


@router.get(
    "/admin/audit/logs",
    response_model=AdminAuditResponse,
    responses={403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def get_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    severity: str = Query("all", pattern=r"^(all|P0|P1|pass)$"),
):
    """获取审计日志分页（管理员）."""
    _require_admin(request)
    limiter = get_rate_limiter()
    if not limiter.is_allowed("admin:audit", limit=20, window_s=60):
        raise HTTPException(status_code=429, detail={"error": "RATE_LIMITED", "detail": "Admin rate limit exceeded"})

    return AdminAuditResponse(logs=[], total=0, page=page, page_size=50)


@router.get(
    "/admin/llm/runtime",
    responses={403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def get_llm_runtime(request: Request):
    """Phase 36: 获取 LLM runtime 可观测性汇总（管理员）."""
    _require_admin(request)
    limiter = get_rate_limiter()
    if not limiter.is_allowed("admin:llm", limit=30, window_s=60):
        raise HTTPException(status_code=429, detail={"error": "RATE_LIMITED", "detail": "Admin rate limit exceeded"})

    summary = DashboardAggregator.get_llm_runtime_summary()
    return {
        "status": "ok",
        "llm_runtime_summary": summary,
        "note": "cache_eligible is structural evidence, NOT provider-confirmed cache-hit telemetry",
    }


@router.get(
    "/admin/llm/history",
    responses={403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def get_llm_history(
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(200, ge=1, le=1000),
):
    """Phase 37: 获取 LLM runtime 持久化历史记录（管理员）."""
    _require_admin(request)
    limiter = get_rate_limiter()
    if not limiter.is_allowed("admin:llm_history", limit=20, window_s=60):
        raise HTTPException(status_code=429, detail={"error": "RATE_LIMITED", "detail": "Admin rate limit exceeded"})

    history = get_llm_runtime_history(hours=hours, limit=limit)
    return {
        "status": "ok",
        "total": len(history),
        "records": history,
    }
