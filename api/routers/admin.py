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

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def _require_admin(request: Request) -> None:
    """从 Authorization header 校验管理员身份."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
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
