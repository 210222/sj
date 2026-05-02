#!/usr/bin/env python
"""回滚验证 — 回滚后最小验收：smoke + outer tests。

用法:
    python scripts/rollback_verify.py
    python scripts/rollback_verify.py --json reports/rollback_result.json
"""

import subprocess
import sys
import os
import json
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    json_out = None
    if "--json" in sys.argv:
        idx = sys.argv.index("--json")
        if idx + 1 < len(sys.argv):
            json_out = sys.argv[idx + 1]

    results = {
        "stage": "rollback_verify",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "steps": {},
        "final": "PASS",
    }

    all_pass = True

    # Step 1: Smoke
    print("=== Rollback Verify: Smoke ===\n")
    r = subprocess.run(
        [sys.executable, "scripts/smoke_outer.py"], cwd=ROOT,
    )
    ok = r.returncode == 0
    results["steps"]["smoke"] = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
        print("[ROLLBACK] Smoke FAIL — rollback may be incomplete")

    # Step 2: Outer tests
    print("\n=== Rollback Verify: Outer Tests ===\n")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "tests/test_outer_api.py",
         "tests/test_outer_orchestration.py",
         "tests/test_outer_resilience.py"],
        cwd=ROOT,
    )
    ok = r.returncode == 0
    results["steps"]["outer_tests"] = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False

    results["final"] = "PASS" if all_pass else "FAIL"

    print(f"\n=== Rollback Verify: {results['final']} ===")
    for step, status in results["steps"].items():
        print(f"  [{status}] {step}")

    if json_out:
        with open(json_out, 'w') as f:
            json.dump(results, f, indent=2)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
