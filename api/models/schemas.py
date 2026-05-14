"""Pydantic 请求/响应模型."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ── 会话 ──

class CreateSessionRequest(BaseModel):
    session_id: str | None = None
    token: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    token: str
    ttm_stage: str | None = None
    sdt_scores: dict[str, float] | None = None
    created_at_utc: str


# ── 对话 ──

class ChatMessageRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=32000)


class ChatMessageResponse(BaseModel):
    action_type: str
    payload: dict[str, Any]
    trace_id: str
    intent: str
    domain_passport: dict[str, Any]
    safety_allowed: bool
    gate_decision: str
    audit_level: str
    premise_rewrite_rate: float
    ttm_stage: str | None = None
    sdt_profile: dict[str, Any] | None = None
    flow_channel: str | None = None
    pulse: dict[str, Any] | None = None
    # Phase 10: LLM 元数据
    llm_generated: bool | None = None
    llm_model: str | None = None
    llm_tokens: int | None = None
    llm_alignment: dict[str, Any] | None = None
    llm_safety: dict[str, Any] | None = None
    # Phase 13: 诊断引擎可见结果
    diagnostic_result: dict[str, Any] | None = None
    diagnostic_probe: dict[str, Any] | None = None
    # Phase 15: 个性化闭环固化
    personalization_evidence: dict[str, Any] | None = None
    memory_status: dict[str, Any] | None = None
    difficulty_contract: dict[str, Any] | None = None
    # Phase 16: 能力唤醒
    awakening: dict[str, Any] | None = None
    # Phase 36: LLM 运行时可观测性
    llm_observability: dict[str, Any] | None = None


# ── 脉冲 ──

class PulseRespondRequest(BaseModel):
    session_id: str
    pulse_id: str
    decision: str = Field(pattern=r"^(accept|rewrite)$")
    rewrite_content: str | None = None


class PulseRespondResponse(BaseModel):
    status: str
    next_action: dict[str, Any] | None = None
    blocking_mode: str = "hard"


# ── 远足 ──

class ExcursionEnterRequest(BaseModel):
    session_id: str


class ExcursionEnterResponse(BaseModel):
    status: str
    excursion_id: str
    theme: str = "dark"


class ExcursionExitRequest(BaseModel):
    session_id: str
    excursion_id: str


class ExcursionExitResponse(BaseModel):
    status: str


# ── 仪表盘 ──

class TTMRadarData(BaseModel):
    precontemplation: float = 0.0
    contemplation: float = 0.0
    preparation: float = 0.0
    action: float = 0.0
    maintenance: float = 0.0
    current_stage: str = "unknown"


class SDTRingsData(BaseModel):
    autonomy: float = 0.0
    competence: float = 0.0
    relatedness: float = 0.0


class ProgressData(BaseModel):
    total_sessions: int = 0
    total_turns: int = 0
    no_assist_avg: float | None = None
    last_active_utc: str | None = None


class UserDashboardResponse(BaseModel):
    session_id: str
    ttm_radar: TTMRadarData
    sdt_rings: SDTRingsData
    progress: ProgressData
    mastery_snapshot: dict | None = None  # Phase 29
    review_queue: list | None = None  # Phase 33
    llm_runtime_summary: dict[str, Any] | None = None  # Phase 36
    session_llm_summary: dict[str, Any] | None = None  # Phase 37


# ── 管理员 ──

class GateStatusItem(BaseModel):
    id: int
    name: str
    status: str  # pass | warn | block
    metric: str
    detail: dict[str, Any] | None = None


class AdminGatesResponse(BaseModel):
    gates: list[GateStatusItem]
    overall: str  # pass | warn | block


class AuditLogItem(BaseModel):
    event_id: str
    timestamp_utc: str
    severity: str
    summary: str
    trace_id: str | None = None


class AdminAuditResponse(BaseModel):
    logs: list[AuditLogItem]
    total: int
    page: int
    page_size: int


# ── 健康检查 ──

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "9.0.0"
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── 错误 ──

# ── 代码沙箱 ──

class CodeExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32000)
    session_id: str
    timeout_s: float = Field(default=10.0, ge=1.0, le=30.0)


class CodeExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    error: str = ""


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    reason_code: str | None = None
