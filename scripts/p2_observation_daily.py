#!/usr/bin/env python
"""P2 每日观测：执行 release_gate / runtime_healthcheck / rollback_verify 并产生日报。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "reports", "p2_observation")
DAILY_DIR = os.path.join(REPORT_DIR, "daily")

try:
    import yaml
    policy_path = os.path.join(ROOT, "config", "release_policy.yaml")
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    WINDOW_DAYS = int(policy["release_policy"]["observation_policy"]["window_days"])
except Exception:
    WINDOW_DAYS = 3


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_json_script(label, cmd, out_path):
    result = subprocess.run(cmd, cwd=ROOT)
    if not os.path.exists(out_path):
        raise RuntimeError(f"{label} did not produce JSON output: {out_path}")
    return result.returncode == 0, _load_json(out_path)


def _next_day_index(date_utc):
    if not os.path.exists(DAILY_DIR):
        return 1
    today_file = f"p2_day_{date_utc}.json"
    files = [f for f in os.listdir(DAILY_DIR) if f.startswith("p2_day_") and f.endswith(".json")]
    if today_file in files:
        return len(files)
    return len(files) + 1


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(DAILY_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_utc = now.strftime("%Y%m%d")
    timestamp = now.isoformat()

    day_index = _next_day_index(date_utc)

    rg_path = os.path.join(DAILY_DIR, f"release_gate_{date_utc}.json")
    hc_path = os.path.join(DAILY_DIR, f"runtime_healthcheck_{date_utc}.json")
    rb_path = os.path.join(DAILY_DIR, f"rollback_verify_{date_utc}.json")

    p0_detected = False
    p1_detected = False
    release_gate_passed = False
    healthcheck_passed = False
    rollback_verify_passed = False
    error_message = ""

    try:
        release_gate_passed, rg = _run_json_script(
            "release_gate",
            [sys.executable, "scripts/release_gate.py", "--json", rg_path],
            rg_path,
        )
        healthcheck_passed, hc = _run_json_script(
            "runtime_healthcheck",
            [sys.executable, "scripts/runtime_healthcheck.py", "--json", hc_path],
            hc_path,
        )
        rollback_verify_passed, rb = _run_json_script(
            "rollback_verify",
            [sys.executable, "scripts/rollback_verify.py", "--json", rb_path],
            rb_path,
        )

        if not release_gate_passed or rg.get("final") != "PASS":
            p1_detected = True
        if not healthcheck_passed or not hc.get("healthcheck_passed", False):
            p1_detected = True
        if not rollback_verify_passed or rb.get("final") != "PASS":
            p1_detected = True

    except Exception as exc:
        p0_detected = True
        error_message = str(exc)

    final_decision = "NO_GO" if (p0_detected or p1_detected) else "GO"

    daily_report = {
        "stage": "p2_observation_daily",
        "day_index": day_index,
        "date_utc": date_utc,
        "release_gate_passed": release_gate_passed,
        "healthcheck_passed": healthcheck_passed,
        "rollback_verify_passed": rollback_verify_passed,
        "p0_detected": p0_detected,
        "p1_detected": p1_detected,
        "final_decision": final_decision,
        "timestamp_utc": timestamp,
    }

    if error_message:
        daily_report["error_message"] = error_message

    daily_path = os.path.join(DAILY_DIR, f"p2_day_{date_utc}.json")
    with open(daily_path, "w", encoding="utf-8") as f:
        json.dump(daily_report, f, indent=2, ensure_ascii=False)

    # ── Visual summary ──
    _print_visual_summary(day_index, WINDOW_DAYS, release_gate_passed,
                          healthcheck_passed, rollback_verify_passed,
                          p0_detected, p1_detected, final_decision)

    print(json.dumps(daily_report, indent=2, ensure_ascii=False))
    sys.exit(0 if final_decision == "GO" else 1)


def _print_visual_summary(day_index, window_days, gate_ok, health_ok, rollback_ok,
                          p0, p1, decision):
    pct = min(100, int(day_index / window_days * 100))
    filled = max(1, int(day_index / window_days * 20))
    bar = "#" * filled + "-" * (20 - filled)
    pending = window_days - day_index
    if p0:
        status_line = "当前判定: NO_GO (P0 detected)"
    elif p1:
        status_line = "当前判定: NO_GO (P1 detected)"
    elif pending > 0:
        status_line = f"当前判定: GO (pending {pending} more day(s))"
    else:
        status_line = "当前判定: GO (observation complete)"

    target_date = datetime.now(timezone.utc)
    if pending > 0:
        from datetime import timedelta
        target_date = target_date + timedelta(days=pending)

    print()
    print("=" * 50)
    print(f"  P2 Day {day_index}/{window_days}  {bar}  {pct}%")
    print(f"  Gate: {'PASS' if gate_ok else 'FAIL'}  "
          f"Health: {'PASS' if health_ok else 'FAIL'}  "
          f"Rollback: {'PASS' if rollback_ok else 'FAIL'}")
    print(f"  P0: {1 if p0 else 0}  P1: {1 if p1 else 0}  {status_line}")
    print(f"  目标结束: {target_date.strftime('%Y-%m-%d')}")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()
