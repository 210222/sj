"""大纲路由 — POST /api/v1/syllabus/search 搜索生成课程大纲 + prepare 异步备课."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Request

from api.middleware.rate_limit import get_rate_limiter
from api.models.schemas import (
    ConfirmSyllabusRequest,
    ErrorResponse,
    PrepareChapterRequest,
    PrepareChapterResponse,
    PrepStatusResponse,
    SyllabusSearchRequest,
    SyllabusSearchResponse,
)
from api.services.syllabus_service import search_syllabus

router = APIRouter(tags=["syllabus"])

# 备课专用线程池（1 worker，防止并发备课互相竞争 LLM 限流）
_prep_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lesson_prep")


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


# ── Phase 82: 章节备课 ──

from api.services.prep_service import get_prep_service


def _get_prep_executor():
    return _prep_executor


def _run_prepare_task(task_id: str, chapter: dict, subject: str,
                      category: str, course_id: str):
    """在子线程中同步执行 prepare_chapter，通过 on_progress 更新进度。"""
    svc = get_prep_service()
    try:
        # 创建 LLM 客户端
        from src.coach.llm.config import LLMConfig
        from src.coach.llm.client import LLMClient
        from src.coach.agent import CoachAgent
        cfg = CoachAgent._cfg()
        llm_config = LLMConfig.from_yaml(cfg)
        client = LLMClient(llm_config)

        # 进度回调: 写入 PrepService
        def _track_progress(kp_name: str, status: str, detail: str = ""):
            svc.update_kp(task_id, kp_name, status)

        # 执行备课
        from src.coach.curriculum.orchestrator import prepare_chapter
        result = prepare_chapter(
            chapter=chapter,
            subject=subject,
            category=category,
            llm_client=client,
            course_id=course_id,
            on_progress=_track_progress,
        )
        svc.mark_done(task_id, _cards_to_dict(result))
    except Exception as e:
        svc.mark_error(task_id, str(e))


def _cards_to_dict(result: dict) -> dict:
    """将 {kp_name: LessonCard|None} 转为可 JSON 序列化的 dict。"""
    import dataclasses
    out = {}
    for kp_name, card in result.items():
        if card is None:
            out[kp_name] = None
        else:
            out[kp_name] = dataclasses.asdict(card) if dataclasses.is_dataclass(card) else card
    return out


@router.post(
    "/syllabus/prepare",
    response_model=PrepareChapterResponse,
    responses={429: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def prepare_chapter_endpoint(req: PrepareChapterRequest, request: Request):
    """异步启动章节备课。每章 18-54 次 LLM 调用，耗时 1-2 分钟。

    返回 task_id，通过 GET /syllabus/prepare/{task_id} 轮询进度。
    """
    chapter = req.chapter
    chapter_id = chapter.get("id", "unknown")
    task_id = f"{chapter_id}"

    svc = get_prep_service()

    # 幂等: 如果同 chapter 已在准备，直接返回现有任务
    existing = svc.get(task_id)
    if existing and existing.state == "running":
        return PrepareChapterResponse(task_id=task_id, state="running")

    # 异步启动：先创建进度条目，再提交执行（顺序不可交换）
    loop = asyncio.get_event_loop()
    svc.start(task_id)           # ② 先创建进度条目——子线程随后通过 task_id 更新
    loop.run_in_executor(        # ③ 再提交执行——子线程开始后进度条目已就位
        _get_prep_executor(),
        _run_prepare_task,
        task_id,
        chapter,
        req.subject,
        req.category,
        req.course_id or "",
    )
    return PrepareChapterResponse(task_id=task_id, state="running")


@router.get(
    "/syllabus/prepare/{task_id}",
    response_model=PrepStatusResponse,
)
async def get_prep_status(task_id: str):
    """查询章节备课进度。"""
    svc = get_prep_service()
    progress = svc.get(task_id)
    if progress is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "detail": f"No task found for {task_id}"},
        )
    return PrepStatusResponse(
        task_id=progress.task_id,
        state=progress.state,
        kps=progress.kps,
        result=progress.result,
        error=progress.error,
        started_at=progress.started_at,
        finished_at=progress.finished_at,
    )


# ── Phase 83-S2: 大纲确认 ──

@router.post("/syllabus/confirm")
async def confirm_syllabus(req: ConfirmSyllabusRequest, request: Request):
    """确认大纲，持久化到 session，激活章节进度追踪。"""
    limiter = get_rate_limiter()
    client_key = f"confirm:{request.client.host if request.client else 'unknown'}"
    if not limiter.is_allowed(client_key, limit=10, window_s=60):
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMITED", "detail": "Too many confirm requests"},
        )

    try:
        from src.coach.persistence import SessionPersistence
        sp = SessionPersistence(req.session_id)
        sp.save_syllabus(req.syllabus)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "SYLLABUS_CONFIRM_FAILED", "detail": str(e)},
        )
