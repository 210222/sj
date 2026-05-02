#!/usr/bin/env python
"""运行时健康检查 — 覆盖 happy / invalid input / pipeline error 三类场景。

用法:
    python scripts/runtime_healthcheck.py
    python scripts/runtime_healthcheck.py --json reports/outer_stage5_runtime_report.json
"""

import sys
import os
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.outer.api import run_orchestration
from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append({"name": name, "pass": bool(condition), "detail": detail})
    icon = "PASS" if condition else "FAIL"
    msg = f"  [{icon}] {name}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)
    return condition


def healthcheck():
    print(f"=== Runtime Healthcheck — {datetime.now(timezone.utc).isoformat()}\n")

    # Category 1: Happy path
    print("--- Happy Path ---")
    t0 = time.perf_counter()
    r = run_orchestration(
        "hc-happy", "2026-04-29T14:00:00.000Z",
        {"engagement": 0.85, "stability": 0.80, "volatility": 0.10},
        {"goal_clarity": 0.85, "resource_readiness": 0.80,
         "risk_pressure": 0.10, "constraint_conflict": 0.10},
    )
    elapsed = time.perf_counter() - t0
    check("Schema 8 fields", set(r.keys()) == set(OUTPUT_SCHEMA_KEYS))
    check("allowed is bool", isinstance(r["allowed"], bool))
    check("reason_code SEM_*", r["reason_code"].startswith("SEM_"),
          f"got {r['reason_code']}")
    check("window_id valid", "_" in r["window_id"])
    check("Response time < 5s", elapsed < 5.0, f"{elapsed:.2f}s")

    # Category 2: Invalid input
    print("\n--- Invalid Input ---")
    r2 = run_orchestration(
        "", "2026-04-29T14:00:00.000Z",
        {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
        {"goal_clarity": 0.5, "resource_readiness": 0.5,
         "risk_pressure": 0.5, "constraint_conflict": 0.5},
    )
    check("Invalid → ORCH_INVALID_INPUT",
          r2["reason_code"] == "ORCH_INVALID_INPUT",
          f"got {r2['reason_code']}")
    check("Invalid → schema intact",
          set(r2.keys()) == set(OUTPUT_SCHEMA_KEYS))
    check("Invalid → allowed=False", r2["allowed"] is False)

    # Category 3: Pipeline error
    print("\n--- Pipeline Error ---")
    r3 = run_orchestration(
        "hc-pipe-err", "2026-04-29T14:00:00.000Z",
        {"engagement": 2.0, "stability": 0.5, "volatility": 0.5},
        {"goal_clarity": 0.5, "resource_readiness": 0.5,
         "risk_pressure": 0.5, "constraint_conflict": 0.5},
    )
    check("Pipeline error → ORCH_PIPELINE_ERROR",
          r3["reason_code"] == "ORCH_PIPELINE_ERROR",
          f"got {r3['reason_code']}")
    check("Pipeline error → schema intact",
          set(r3.keys()) == set(OUTPUT_SCHEMA_KEYS))
    check("Pipeline error → allowed=False", r3["allowed"] is False)

    # Summary
    total = len(CHECKS)
    passed = sum(1 for c in CHECKS if c["pass"])
    failed = total - passed

    print(f"\n{'='*50}")
    print(f"Healthcheck: {passed}/{total} passed, {failed} failed")

    return passed == total


def main():
    ok = healthcheck()

    json_out = None
    if "--json" in sys.argv:
        idx = sys.argv.index("--json")
        if idx + 1 < len(sys.argv):
            json_out = sys.argv[idx + 1]

    report = {
        "stage": "runtime_healthcheck",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "healthcheck_passed": ok,
        "total_checks": len(CHECKS),
        "passed": sum(1 for c in CHECKS if c["pass"]),
        "failed": sum(1 for c in CHECKS if not c["pass"]),
        "failed_items": [c for c in CHECKS if not c["pass"]],
    }

    if json_out:
        with open(json_out, 'w') as f:
            json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
