#!/usr/bin/env python
"""外圈回归门禁 — 执行 outer 三套测试 + 可选全量回归。

用法:
    python scripts/regression_gate.py            # 仅 outer 三套
    python scripts/regression_gate.py --full     # outer + 全量回归
"""

import subprocess
import sys
import os

ROOT = os.path.join(os.path.dirname(__file__), '..')


def run_pytest(test_files, label):
    print(f"\n--- {label} ---")
    args = [sys.executable, "-m", "pytest", "-q"] + test_files
    result = subprocess.run(args, cwd=ROOT, capture_output=False)
    return result.returncode == 0


def main():
    full = "--full" in sys.argv

    outer_tests = [
        "tests/test_outer_api.py",
        "tests/test_outer_orchestration.py",
        "tests/test_outer_resilience.py",
    ]

    ok = run_pytest(outer_tests, "Outer Circle Tests (3 files)")

    if full:
        ok = run_pytest(["tests/"], "Full Regression") and ok

    if ok:
        print(f"\n=== GATE: PASS ===")
        sys.exit(0)
    else:
        print(f"\n=== GATE: FAIL ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
