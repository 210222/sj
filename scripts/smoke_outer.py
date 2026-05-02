#!/usr/bin/env python
"""外圈冒烟测试 — 验证 8 字段 schema、错误分层、fallback 稳定性。

在容器启动后或本地直接运行：
    python scripts/smoke_outer.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.outer.api import run_orchestration
from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS


PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def smoke():
    print("=== Outer A Smoke Test ===\n")

    # 1. Happy path
    print("--- Happy Path ---")
    r = run_orchestration(
        "smoke-001", "2026-04-29T14:00:00.000Z",
        {"engagement": 0.85, "stability": 0.80, "volatility": 0.10},
        {"goal_clarity": 0.85, "resource_readiness": 0.80,
         "risk_pressure": 0.10, "constraint_conflict": 0.10},
    )
    check("8 field schema", set(r.keys()) == set(OUTPUT_SCHEMA_KEYS),
          f"extra={set(r.keys()) - set(OUTPUT_SCHEMA_KEYS)} "
          f"missing={set(OUTPUT_SCHEMA_KEYS) - set(r.keys())}")
    check("allowed is bool", isinstance(r["allowed"], bool))
    check("final_intensity is str", isinstance(r["final_intensity"], str))
    check("window_id contains underscore", "_" in r["window_id"])
    check("evaluated_at_utc is ISO8601",
          r["evaluated_at_utc"].endswith("Z") and "T" in r["evaluated_at_utc"])
    check("happy path returns SEM_ reason",
          r["reason_code"].startswith("SEM_"),
          f"got {r['reason_code']}")

    # 2. Error layering: invalid input
    print("\n--- Invalid Input ---")
    r2 = run_orchestration(
        "", "2026-04-29T14:00:00.000Z",
        {"engagement": 0.5, "stability": 0.5, "volatility": 0.5},
        {"goal_clarity": 0.5, "resource_readiness": 0.5,
         "risk_pressure": 0.5, "constraint_conflict": 0.5},
    )
    check("empty trace → ORCH_INVALID_INPUT",
          r2["reason_code"] == "ORCH_INVALID_INPUT",
          f"got {r2['reason_code']}")
    check("fallback schema still 8 fields",
          set(r2.keys()) == set(OUTPUT_SCHEMA_KEYS))
    check("fallback allowed=False", r2["allowed"] is False)

    # 3. Error layering: pipeline error
    print("\n--- Pipeline Error ---")
    r3 = run_orchestration(
        "smoke-003", "2026-04-29T14:00:00.000Z",
        {"engagement": 2.0, "stability": 0.5, "volatility": 0.5},
        {"goal_clarity": 0.5, "resource_readiness": 0.5,
         "risk_pressure": 0.5, "constraint_conflict": 0.5},
    )
    check("bad L0 → ORCH_PIPELINE_ERROR",
          r3["reason_code"] == "ORCH_PIPELINE_ERROR",
          f"got {r3['reason_code']}")
    check("pipeline error schema still 8 fields",
          set(r3.keys()) == set(OUTPUT_SCHEMA_KEYS))

    # 4. Reason code layering integrity
    print("\n--- Reason Code Layering ---")
    r4 = run_orchestration("t", "", {"e": 0.5, "s": 0.5, "v": 0.5},
                           {"g": 0.5, "r": 0.5, "p": 0.5, "c": 0.5})
    check("empty time → ORCH_INVALID_INPUT",
          r4["reason_code"] == "ORCH_INVALID_INPUT",
          f"got {r4['reason_code']}")

    # Summary
    total = PASS + FAIL
    print(f"\n{'='*40}")
    print(f"Smoke complete: {PASS}/{total} passed, {FAIL} failed")
    print(f"{'='*40}")

    return FAIL == 0


if __name__ == "__main__":
    ok = smoke()
    sys.exit(0 if ok else 1)
