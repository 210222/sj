#!/usr/bin/env python
"""C-track daily observation: runs release_gate, healthcheck, rollback_verify, outputs daily report."""

import json, os, subprocess, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "reports", "c_observation", "daily")


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(REPORT_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_utc = now.strftime("%Y-%m-%d")
    timestamp = now.isoformat()

    p0_detected = False
    p1_detected = False
    release_gate_passed = False
    healthcheck_passed = False
    rollback_passed = False
    schema_drift = False
    reason_drift = False
    findings = []

    try:
        # Release gate (mandatory)
        r = subprocess.run([sys.executable, "scripts/release_gate.py"], capture_output=True, text=True, cwd=ROOT)
        release_gate_passed = "RELEASE GATE: PASS" in r.stdout
        if not release_gate_passed:
            p1_detected = True
            findings.append("release_gate failed")

        # Healthcheck (recommended)
        r = subprocess.run([sys.executable, "scripts/runtime_healthcheck.py"], capture_output=True, text=True, cwd=ROOT)
        healthcheck_passed = "healthcheck_passed" in r.stdout.lower() and "true" in r.stdout.lower()
        if not healthcheck_passed:
            p1_detected = True
            findings.append("healthcheck failed")

        # Rollback verify (recommended)
        r = subprocess.run([sys.executable, "scripts/rollback_verify.py"], capture_output=True, text=True, cwd=ROOT)
        rollback_passed = "PASS" in r.stdout and "smoke" in r.stdout
        if not rollback_passed:
            p1_detected = True
            findings.append("rollback_verify failed")

        # Schema/reason drift check via API
        sys.path.insert(0, ROOT)
        from src.outer.presentation.formatter import OUTPUT_SCHEMA_KEYS
        from src.outer.api import run_orchestration
        r1 = run_orchestration('t', '2026-04-29T14:00:00.000Z',
            {'engagement': 0.5, 'stability': 0.5, 'volatility': 0.5},
            {'goal_clarity': 0.5, 'resource_readiness': 0.5, 'risk_pressure': 0.5, 'constraint_conflict': 0.5})
        r2 = run_orchestration('', '', {'e': 0.5}, {'g': 0.5})
        schema_drift = set(r1.keys()) != set(OUTPUT_SCHEMA_KEYS)
        reason_drift = r2['reason_code'] != 'ORCH_INVALID_INPUT'
        if schema_drift:
            p0_detected = True
            findings.append("schema_drift detected")
        if reason_drift:
            p0_detected = True
            findings.append("reason_code_drift detected")

    except Exception as exc:
        p0_detected = True
        findings.append(f"execution error: {exc}")

    final_decision = "NO_GO" if (p0_detected or p1_detected) else "GO"

    daily = {
        "c_stage": "C3",
        "c_date_utc": date_utc,
        "c_release_gate_passed": release_gate_passed,
        "c_runtime_healthcheck_passed": healthcheck_passed,
        "c_rollback_verify_passed": rollback_passed,
        "c_schema_drift": schema_drift,
        "c_reason_code_drift": reason_drift,
        "c_p0_detected": p0_detected,
        "c_p1_detected": p1_detected,
        "c_findings": findings,
        "c_final_decision": final_decision,
        "c_timestamp_utc": timestamp,
    }

    report_path = os.path.join(REPORT_DIR, f"c_day_{date_utc}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(daily, f, indent=2, ensure_ascii=False)

    print(json.dumps(daily, indent=2, ensure_ascii=False))
    sys.exit(0 if final_decision == "GO" else 1)


if __name__ == "__main__":
    main()
