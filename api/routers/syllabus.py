"""大纲路由 — POST /api/v1/syllabus/search 搜索生成课程大纲."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    ErrorResponse,
    SyllabusSearchRequest,
    SyllabusSearchResponse,
)
from api.services.syllabus_service import search_syllabus

router = APIRouter(tags=["syllabus"])


@router.post(
    "/syllabus/search",
    response_model=SyllabusSearchResponse,
    responses={429: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def search_syllabus_endpoint(req: SyllabusSearchRequest, request: Request):
    """搜索生成课程大纲。调用 DeepSeek 联网搜索 + JSON 格式化。

    失败时返回分类模板兜底（needs_review=True）。
    """
    # Rate limit: 5/min per IP
    limiter = get_rate_limiter()
    client_key = f"syllabus:{request.client.host if request.client else 'unknown'}"
    if not limiter.is_allowed(client_key, limit=5, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Too many syllabus requests"},
        )

    # 创建 LLM 客户端
    try:
        from src.coach.llm.config import LLMConfig, LLMConfigError
        from src.coach.llm.client import LLMClient
        from src.coach.agent import CoachAgent
        cfg = CoachAgent._cfg()
        llm_config = LLMConfig.from_yaml(cfg)
        if not llm_config.enabled:
            raise HTTPException(
                status_code=503,
                detail={"error": "LLM_DISABLED", "detail": "LLM is not enabled in config"},
            )
        if not llm_config.search_enabled:
            raise HTTPException(
                status_code=503,
                detail={"error": "SEARCH_DISABLED", "detail": "LLM search is not enabled in config"},
            )
        client = LLMClient(llm_config)
    except HTTPException:
        raise
    except LLMConfigError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "CONFIG_ERROR", "detail": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "LLM_INIT_FAILED", "detail": str(e)},
        )

    # 搜索大纲
    try:
        result = search_syllabus(
            subject=req.subject,
            llm_client=client,
            level=req.level,
            category=req.category,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "SYLLABUS_SEARCH_FAILED", "detail": str(e)},
        )

    return SyllabusSearchResponse(
        syllabus=result,
        source=result.get("source", "llm_search"),
        needs_review=result.get("needs_review", False),
    )
