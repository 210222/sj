"""API 层运行时配置 — 默认值可通过环境变量覆盖."""

import os

# ── CORS ──
CORS_ORIGINS: list[str] = os.getenv(
    "COHERENCE_CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

# ── 限流默认值 ──
DEFAULT_RATE_LIMIT: int = int(os.getenv("COHERENCE_RATE_LIMIT_DEFAULT", "30"))
DEFAULT_RATE_WINDOW_S: int = int(os.getenv("COHERENCE_RATE_WINDOW_S", "60"))

PULSE_RATE_LIMIT: int = int(os.getenv("COHERENCE_RATE_LIMIT_PULSE", "10"))
PULSE_RATE_WINDOW_S: int = int(os.getenv("COHERENCE_PULSE_WINDOW_S", "600"))

# ── WebSocket ──
WS_PING_INTERVAL_S: int = int(os.getenv("COHERENCE_WS_PING_INTERVAL", "30"))
WS_MAX_IDLE_S: int = int(os.getenv("COHERENCE_WS_MAX_IDLE", "300"))

# ── 自适应降级 ──
PULSE_MAX_BLOCKING: int = int(os.getenv("COHERENCE_PULSE_MAX_BLOCKING", "2"))
PULSE_WINDOW_MINUTES: int = int(os.getenv("COHERENCE_PULSE_WINDOW_MINUTES", "10"))

# ── IAM ──
TOKEN_TTL_HOURS: int = int(os.getenv("COHERENCE_TOKEN_TTL_HOURS", "24"))
ADMIN_TOKENS: set[str] = set(
    os.getenv("COHERENCE_ADMIN_TOKENS", "").split(",") if os.getenv("COHERENCE_ADMIN_TOKENS") else []
)
