#!/usr/bin/env python
"""C-track weekly summary: reads last 7 daily reports, outputs trend and GO/WARN/NO_GO."""

import json, os, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_DIR = os.path.join(ROOT, "reports", "c_observation", "daily")
SUMMARY_PATH = os.path.join(ROOT, "reports", "c_observation", "weekly_summary.json")
WINDOW_DAYS = 7


def main():
    sys.stdout.reconfigure(encoding='utf-8')

    if not os.path.exists(DAILY_DIR):
        print("No daily reports directory")
        sys.exit(1)

    files = sorted([f for f in os.listdir(DAILY_DIR) if f.startswith("c_day_") and f.endswith(".json")])
    reports = []
    for name in files[-WINDOW_DAYS:]:
        with open(os.path.join(DAILY_DIR, name), encoding='utf-8') as f:
            reports.append(json.load(f))

    days_collected = len(reports)
    go_days = sum(1 for r in reports if r.get("c_final_decision") == "GO")
    no_go_days = days_collected - go_days
    p0_count = sum(1 for r in reports if r.get("c_p0_detected", False))
    p1_count = sum(1 for r in reports if r.get("c_p1_detected", False))
    sd_count = sum(1 for r in reports if r.get("c_schema_drift", False))
    rd_count = sum(1 for r in reports if r.get("c_reason_code_drift", False))

    if p0_count > 0 or sd_count > 0 or rd_count > 0:
        weekly_decision = "NO_GO"
    elif p1_count > 0:
        weekly_decision = "WARN"
    else:
        weekly_decision = "GO"

    summary = {
        "c_window_days": WINDOW_DAYS,
        "c_days_collected": days_collected,
        "c_go_days": go_days,
        "c_no_go_days": no_go_days,
        "c_p0_count": p0_count,
        "c_p1_count": p1_count,
        "c_schema_drift_count": sd_count,
        "c_reason_code_drift_count": rd_count,
        "c_availability_rate": round(go_days / max(days_collected, 1), 4),
        "c_weekly_decision": weekly_decision,
        "c_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    sys.exit(0 if weekly_decision == "GO" else 1)


if __name__ == "__main__":
    main()
