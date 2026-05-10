"""S5 — 代码沙箱路由 POST /api/v1/code/execute."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import CodeExecuteRequest, CodeExecuteResponse, ErrorResponse

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["code"])


@router.post(
    "/code/execute",
    response_model=CodeExecuteResponse,
    responses={429: {"model": ErrorResponse}},
)
async def execute_code(req: CodeExecuteRequest, request: Request):
    """在沙箱中执行代码."""
    limiter = get_rate_limiter()
    key = f"code:{req.session_id}"
    if not limiter.is_allowed(key, limit=10, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Code execution rate limit exceeded"},
        )

    from src.coach.llm.sandbox import CodeSandbox

    sandbox = CodeSandbox(timeout_s=req.timeout_s)
    result = sandbox.execute(req.code)

    # S4: 结果回存到学习路径（供后续 LLM 上下文引用）
    try:
        from src.coach.llm.learning_path import get_learning_path
        tracker = get_learning_path()
        if result.success:
            tracker.record_topic("code_exec_success")
        else:
            tracker.record_topic("code_exec_error")
    except Exception:
        pass

    return CodeExecuteResponse(
        success=result.success,
        stdout=result.stdout[:10000],
        stderr=result.stderr[:5000],
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        error=result.error,
    )
