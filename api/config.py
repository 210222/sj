"""API 层运行时配置 — 默认值可通过环境变量覆盖."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

# ── Phase 47: 跨进程文件锁，保护 config_router + agent 的并发写 ──
_LOCK_PATH = Path(__file__).resolve().parent.parent / "config" / ".yaml_write.lock"


@contextmanager
def _config_write_lock():
    """跨进程写锁。Windows 用 msvcrt，Unix 用 fcntl。"""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(_LOCK_PATH, "w")
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if sys.platform == "win32":
            import msvcrt
            try:
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()

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
