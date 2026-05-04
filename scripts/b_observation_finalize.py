#!/usr/bin/env python
"""B 轨观测期汇总：聚合 B 轨窗口日报并输出 GO/NO_GO。窗口天数从 release_policy.yaml 读取，默认 3。"""

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "reports", "b_observation")
DAILY_DIR = os.path.join(REPORT_DIR, "daily")
SUMMARY_PATH = os.path.join(REPORT_DIR, "b_observation_summary.json")

try:
    import yaml
    policy_path = os.path.join(ROOT, "config", "release_policy.yaml")
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    WINDOW_DAYS = int(policy["release_policy"]["observation_policy"]["window_days"])
except Exception:
    WINDOW_DAYS = 3


def _load_daily_reports():
    if not os.path.exists(DAILY_DIR):
        return []
    files = sorted(
        f for f in os.listdir(DAILY_DIR)
        if f.startswith("b_day_") and f.endswith(".json")
    )
    reports = []
    for name in files:
        path = os.path.join(DAILY_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            reports.append(json.load(f))
    return reports[-WINDOW_DAYS:]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reports = _load_daily_reports()

    p0_count = sum(1 for r in reports if r.get("b_p0_detected", False))
    p1_count = sum(1 for r in reports if r.get("b_p1_detected", False))
    days_collected = len(reports)

    all_days_passed = (
        days_collected == WINDOW_DAYS
        and p0_count == 0
        and p1_count == 0
    )

    final_decision = "GO" if all_days_passed else "NO_GO"

    summary = {
        "b_stage": "b_observation_finalize",
        "b_window_days": WINDOW_DAYS,
        "b_days_collected": days_collected,
        "b_p0_count": p0_count,
        "b_p1_count": p1_count,
        "b_all_days_passed": all_days_passed,
        "b_version_prerequisites_met": all_days_passed,
        "b_final_decision": final_decision,
        "b_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # ── Visual summary ──
    print()
    print("=" * 50)
    print(f"  B P2 观测汇总  ({WINDOW_DAYS}-day window)")
    bar_filled = min(WINDOW_DAYS, days_collected)
    bar = "#" * bar_filled + "-" * (WINDOW_DAYS - bar_filled)
    print(f"  Days: {bar}  {days_collected}/{WINDOW_DAYS}")
    print(f"  P0: {p0_count}  P1: {p1_count}")
    if final_decision == "GO":
        print(f"  B最终判定: GO — B 版准入条件满足")
    elif days_collected < WINDOW_DAYS:
        print(f"  B最终判定: NO_GO — 仅 {days_collected}/{WINDOW_DAYS} 天，不足窗口")
    else:
        reasons = []
        if p0_count > 0:
            reasons.append(f"P0={p0_count}")
        if p1_count > 0:
            reasons.append(f"P1={p1_count}")
        print(f"  B最终判定: NO_GO — {', '.join(reasons)}")
    print("=" * 50)
    print()

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    sys.exit(0 if final_decision == "GO" else 1)


if __name__ == "__main__":
    main()
