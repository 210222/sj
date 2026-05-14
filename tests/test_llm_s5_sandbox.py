"""Phase 10 S5 — 代码沙箱测试."""

import pytest
from src.coach.llm.sandbox import CodeSandbox, FORBIDDEN_MODULES


class TestCodeSandbox:
    def test_simple_code_executes(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("print('hello world')")
        assert result.success is True
        assert "hello world" in result.stdout
        assert result.exit_code == 0
        assert result.duration_ms > 0

    def test_code_with_syntax_error(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("if True print('missing colon')")
        assert result.success is False
        assert result.exit_code != 0

    def test_code_with_runtime_error(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("x = 1/0")
        assert result.success is False

    def test_timeout_handling(self):
        s = CodeSandbox(timeout_s=1)
        result = s.execute("import time; time.sleep(10)")
        assert result.success is False
        assert "超时" in result.error

    def test_math_module_allowed(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("import math; print(math.pi)")
        assert result.success is True
        assert "3.14" in result.stdout

    def test_os_module_blocked(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("import os; print(os.getcwd())")
        assert result.success is False
        assert any("os" in m for m in result.blocked_modules)

    def test_subprocess_blocked(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("import subprocess")
        assert result.success is False

    def test_empty_code(self):
        s = CodeSandbox(timeout_s=5)
        result = s.execute("")
        assert result.success is True
        assert result.exit_code == 0


class TestForbiddenModules:
    def test_all_dangerous_modules_blocked(self):
        for mod in ["os", "subprocess", "socket", "shutil",
                     "ctypes", "multiprocessing", "importlib"]:
            assert mod in FORBIDDEN_MODULES, f"{mod} should be forbidden"

    def test_safe_modules_allowed(self):
        for mod in ["math", "json", "collections", "itertools", "random"]:
            assert CodeSandbox.is_safe_module(mod) is True

    def test_dangerous_submodules(self):
        assert CodeSandbox.is_safe_module("os.path") is False
        assert CodeSandbox.is_safe_module("subprocess.Popen") is False
