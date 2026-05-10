"""自适应降级限流中间件 — 滑动窗口 + 429 响应."""

from __future__ import annotations

import time

from api.config import DEFAULT_RATE_LIMIT, DEFAULT_RATE_WINDOW_S


class RateLimiter:
    """滑动窗口内存限流器."""

    def __init__(self) -> None:
        # key → list[timestamp_ms]
        self._windows: dict[str, list[float]] = {}

    def is_allowed(
        self,
        key: str,
        limit: int = DEFAULT_RATE_LIMIT,
        window_s: int = DEFAULT_RATE_WINDOW_S,
    ) -> bool:
        """检查 key 在当前窗口内是否允许."""
        now = time.time()
        cutoff = now - window_s
        window = self._windows.setdefault(key, [])
        # 清理过期条目
        window[:] = [ts for ts in window if ts > cutoff]
        if len(window) < limit:
            window.append(now)
            return True
        return False

    def remaining(
        self,
        key: str,
        limit: int = DEFAULT_RATE_LIMIT,
        window_s: int = DEFAULT_RATE_WINDOW_S,
    ) -> int:
        """返回窗口内剩余额度."""
        now = time.time()
        cutoff = now - window_s
        window = self._windows.setdefault(key, [])
        window[:] = [ts for ts in window if ts > cutoff]
        return max(0, limit - len(window))

    def reset(self, key: str) -> None:
        """重置 key 的限流窗口."""
        self._windows.pop(key, None)


# 全局单例
_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
