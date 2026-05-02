#!/usr/bin/env python
"""发布门禁 — 一键串联 smoke → outer tests → full regression。

任一步失败即非 0 退出码，输出失败摘要。
用法:
    python scripts/release_gate.py          # 三阶段全部
    python scripts/release_gate.py --skip-full  # 跳过全量回归
    python scripts/release_gate.py --json <path>  # 输出 JSON 报告
"""

import subprocess
import sys
import os
import json
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_step(cmd, label):
    print(f"\n{'='*50}")
    print(f"GATE: {label}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT)
    return result.returncode == 0


def main():
    skip_full = "--skip-full" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        idx = sys.argv.index("--json")
        if idx + 1 < len(sys.argv):
            json_out = sys.argv[idx + 1]

    results = {"stage": "release_gate", "steps": {},
               "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    all_pass = True

    # Phase 1: Smoke
    ok = run_step(f"{sys.executable} scripts/smoke_outer.py", "Phase 1: Smoke")
    results["steps"]["smoke"] = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
        print("\n[GATE] Smoke FAIL — stopping")
        return _finish(results, json_out, all_pass)

    # Phase 2: Outer tests
    ok = run_step(
        f"{sys.executable} -m pytest tests/test_outer_api.py "
        f"tests/test_outer_orchestration.py tests/test_outer_resilience.py -q",
        "Phase 2: Outer Tests"
    )
    results["steps"]["outer_tests"] = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
        print("\n[GATE] Outer tests FAIL — stopping")
        return _finish(results, json_out, all_pass)

    # Phase 3: Full regression
    if not skip_full:
        ok = run_step(
            f"{sys.executable} -m pytest tests/ -q",
            "Phase 3: Full Regression"
        )
        results["steps"]["full_regression"] = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
    else:
        results["steps"]["full_regression"] = "SKIP"

    return _finish(results, json_out, all_pass)


def _finish(results, json_out, all_pass):
    print(f"\n{'='*50}")
    for step, status in results["steps"].items():
        print(f"  [{status}] {step}")
    print(f"{'='*50}")
    results["final"] = "PASS" if all_pass else "FAIL"
    print(f"RELEASE GATE: {results['final']}")

    if json_out:
        with open(json_out, 'w') as f:
            json.dump(results, f, indent=2)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
