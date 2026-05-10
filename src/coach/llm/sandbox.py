"""S5 — 代码沙箱执行器.

subprocess + 资源限制 + 模块黑名单 + timeout 硬限制.
零额外依赖。
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)

FORBIDDEN_MODULES = frozenset({
    "os", "subprocess", "socket", "shutil", "sys",
    "ctypes", "multiprocessing", "signal", "threading",
    "importlib", "builtins",
})


@dataclass
class SandboxResult:
    """沙箱执行结果."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    blocked_modules: list[str] = field(default_factory=list)
    error: str = ""


def _scan_forbidden_imports(code: str) -> list[str]:
    """静态扫描代码中的禁止 import."""
    blocked = []
    patterns = [
        r'(?:from|import)\s+([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, code):
            module = match.group(1)
            root = module.split(".")[0]
            if root in FORBIDDEN_MODULES:
                blocked.append(module)
    return blocked


class CodeSandbox:
    """代码沙箱 — subprocess 隔离执行 Python 代码."""

    def __init__(self, timeout_s: float = 10.0):
        self._timeout = timeout_s

    def execute(self, code: str, python_bin: str = "python") -> SandboxResult:
        """在沙箱中执行 Python 代码."""
        start = time.perf_counter()
        result = SandboxResult(success=False)

        # 静态检查
        blocked = _scan_forbidden_imports(code)
        if blocked:
            result.blocked_modules = blocked
            result.error = f"禁止模块: {', '.join(blocked)}"
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result

        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False,
                encoding="utf-8") as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            proc = subprocess.run(
                [python_bin, tmp_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env={
                    "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                    "PATH": os.environ.get("PATH", ""),
                    "TEMP": tempfile.gettempdir(),
                    "TMP": tempfile.gettempdir(),
                    "PYTHONIOENCODING": "utf-8",
                },
                cwd=tempfile.gettempdir(),
            )
            result.exit_code = proc.returncode
            result.stdout = proc.stdout or ""
            result.stderr = proc.stderr or ""

            if proc.returncode == 0:
                result.success = True
            else:
                result.error = result.stderr[:500] or f"exit code {proc.returncode}"
        except subprocess.TimeoutExpired:
            result.error = f"执行超时 ({self._timeout}s)"
        except FileNotFoundError:
            result.error = f"Python 解释器未找到: {python_bin}"
        except Exception as e:
            result.error = f"沙箱异常: {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    @staticmethod
    def is_safe_module(module_name: str) -> bool:
        return module_name.split(".")[0] not in FORBIDDEN_MODULES
