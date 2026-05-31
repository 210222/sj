"""进度追踪服务 — prepare_chapter 异步执行 + 状态轮询."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class PrepProgress:
    task_id: str
    state: str = "running"       # running | done | error
    kps: dict[str, str] = field(default_factory=dict)  # kp_name → status
    result: dict | None = None   # {kp_name: LessonCard|None}
    error: str | None = None
    started_at: float = 0.0
    finished_at: float | None = None


class PrepService:
    """内存进度追踪。单用户系统，重启丢失可接受。

    限制: _tasks 是进程级内存 dict。uvicorn 多 worker (--workers > 1) 下
    POST 和 GET 可能命中不同进程 → 进度不可见。当前默认单 worker，无影响。
    """

    def __init__(self):
        self._tasks: dict[str, PrepProgress] = {}
        self._lock = threading.Lock()

    def start(self, task_id: str) -> PrepProgress:
        with self._lock:
            # 如果同 task_id 已在运行，返回现有任务（幂等）
            existing = self._tasks.get(task_id)
            if existing and existing.state == "running":
                return existing
            progress = PrepProgress(
                task_id=task_id,
                started_at=time.time(),
            )
            self._tasks[task_id] = progress
            return progress

    def update_kp(self, task_id: str, kp_name: str, status: str):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].kps[kp_name] = status

    def mark_done(self, task_id: str, result: dict):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].state = "done"
                self._tasks[task_id].result = result
                self._tasks[task_id].finished_at = time.time()

    def mark_error(self, task_id: str, error: str):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].state = "error"
                self._tasks[task_id].error = error
                self._tasks[task_id].finished_at = time.time()

    def get(self, task_id: str) -> PrepProgress | None:
        with self._lock:
            return self._tasks.get(task_id)


# 模块级单例
_prep_service: PrepService | None = None


def get_prep_service() -> PrepService:
    global _prep_service
    if _prep_service is None:
        _prep_service = PrepService()
    return _prep_service
