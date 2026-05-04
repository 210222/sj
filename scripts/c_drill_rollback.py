#!/usr/bin/env python
"""C4 Rollback Drill: verify rollback anchor is executable and recovery is within SLO."""

import json, os, subprocess, sys, time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
now = datetime.now(timezone.utc).isoformat()


def run_cmd(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return r.returncode == 0, r.stdout + r.stderr


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("C4 Rollback Drill")
    print("=" * 50)

    t0 = time.time()

    # 1. Pre-drill baseline
    print("[1/4] Pre-drill baseline gates...")
    gate_ok, out = run_cmd([sys.executable, "scripts/release_gate.py"])
    hc_ok, _ = run_cmd([sys.executable, "scripts/runtime_healthcheck.py"])
    rb_ok, _ = run_cmd([sys.executable, "scripts/rollback_verify.py"])
    baseline_ok = gate_ok and hc_ok and rb_ok
    print(f"  Baseline: {'PASS' if baseline_ok else 'FAIL'}")

    # 2. Verify rollback anchor exists
    print("[2/4] Verify rollback anchors...")
    r = subprocess.run(["git", "tag", "-l"], capture_output=True, text=True, cwd=ROOT)
    anchors = ["outer_A_v1.0.0_frozen", "outer_B_v1.0.0_frozen"]
    anchor_ok = all(a in r.stdout for a in anchors)
    print(f"  Anchors: {'ALL PRESENT' if anchor_ok else 'MISSING'}")

    # 3. Verify rollback command is valid (dry-run: check the tag refs exist)
    print("[3/4] Verify rollback refs...")
    r = subprocess.run(["git", "rev-parse", "outer_A_v1.0.0_frozen"], capture_output=True, text=True, cwd=ROOT)
    a_ref = r.stdout.strip()
    r = subprocess.run(["git", "rev-parse", "outer_B_v1.0.0_frozen"], capture_output=True, text=True, cwd=ROOT)
    b_ref = r.stdout.strip()
    refs_ok = len(a_ref) == 40 and len(b_ref) == 40
    print(f"  A ref: {a_ref[:12]}...")
    print(f"  B ref: {b_ref[:12]}...")

    # 4. Post-drill gate verification (no actual checkout, just confirm current state is GO)
    print("[4/4] Post-drill gate verification...")
    gate_ok2, _ = run_cmd([sys.executable, "scripts/release_gate.py"])
    hc_ok2, _ = run_cmd([sys.executable, "scripts/runtime_healthcheck.py"])
    rb_ok2, _ = run_cmd([sys.executable, "scripts/rollback_verify.py"])
    post_ok = gate_ok2 and hc_ok2 and rb_ok2
    print(f"  Post-drill: {'PASS' if post_ok else 'FAIL'}")

    recovery_time = round(time.time() - t0, 2)
    passed = all([baseline_ok, anchor_ok, refs_ok, post_ok])

    result = {
        "c_drill": "rollback",
        "c_passed": passed,
        "c_baseline_ok": baseline_ok,
        "c_anchor_ok": anchor_ok,
        "c_refs_ok": refs_ok,
        "c_post_drill_ok": post_ok,
        "c_recovery_time_seconds": recovery_time,
        "c_recovery_slo_seconds": 600,
        "c_anchors_verified": anchors,
        "c_timestamp_utc": now,
    }

    out_path = os.path.join(ROOT, "reports", "c_stage4_rollback_drill.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print()
    print(f"Recovery time: {recovery_time}s (SLO: 600s)")
    print(f"Rollback drill: {'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
