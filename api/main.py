"""FastAPI 应用入口 — CORS + 路由注册 + 全局异常处理 + 生命周期管理."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import CORS_ORIGINS
from api.models.schemas import ErrorResponse, HealthResponse
from api.routers import admin, chat, code_executor, config_router, dashboard, excursion, pulse, session

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动预热 + 优雅关闭."""
    # startup: 预热导入，验证后端可用
    _logger.info("Coherence API starting up...")
    try:
        from api.services.coach_bridge import _import_coach_agent
        _import_coach_agent()
        _logger.info("CoachAgent import verified OK")
    except Exception as e:
        _logger.warning("CoachAgent not available at startup: %s", e)

    try:
        from api.services.dashboard_aggregator import _cached_config
        _cached_config()
        _logger.info("coach_defaults.yaml loaded OK")
    except Exception as e:
        _logger.warning("coach_defaults.yaml not available at startup: %s", e)

    yield

    # shutdown: 清理资源
    _logger.info("Coherence API shutting down...")
    from api.services.coach_bridge import _executor
    _executor.shutdown(wait=True, cancel_futures=True)
    _logger.info("CoachBridge thread pool shut down")


app = FastAPI(
    title="Coherence Coach API",
    description="认知主权保护系统 — Coach 教练引擎 RESTful API",
    version="9.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理器 ──

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理异常，返回统一 JSON 格式."""
    _logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "detail": "An unexpected error occurred",
            "reason_code": "ORCH_PIPELINE_ERROR",
        },
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404,
        content={"error": "NOT_FOUND", "detail": f"Route not found: {request.url.path}"},
    )


# 路由注册
app.include_router(session.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(pulse.router, prefix="/api/v1")
app.include_router(excursion.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(code_executor.router, prefix="/api/v1")
app.include_router(config_router.router, prefix="/api/v1")


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """健康检查端点."""
    return HealthResponse()
