"""S15 Full Exhaustive — 11 configs x 8 scenarios = 88 runs, 8-dim scoring."""

import yaml, time, json, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONFIG = ROOT / "config" / "coach_defaults.yaml"
LOG = ROOT / "reports" / "s15_full_exhaustive_log.txt"
REPORT = ROOT / "reports" / "s15_full_exhaustive_report.json"

# 11 configs
COMBOS = [
    ("all_off",      {"llm":False,"ttm":False,"sdt":False,"flow":False,"diag":False}),
    ("rules_diag",   {"llm":False,"ttm":False,"sdt":False,"flow":False,"diag":True}),
    ("llm_only",     {"llm":True, "ttm":False,"sdt":False,"flow":False,"diag":False}),
    ("llm_ttm",      {"llm":True, "ttm":True, "sdt":False,"flow":False,"diag":False}),
    ("llm_ttm_sdt",  {"llm":True, "ttm":True, "sdt":True, "flow":False,"diag":False}),
    ("full_behavior",{"llm":True, "ttm":True, "sdt":True, "flow":True, "diag":False}),
    ("llm_diag",     {"llm":True, "ttm":False,"sdt":False,"flow":False,"diag":True}),
    ("full_stack",   {"llm":True, "ttm":True, "sdt":True, "flow":True, "diag":True}),
    ("s15_person",   {"llm":True, "ttm":True, "sdt":True, "flow":True, "diag":False}),
    ("s15_diff",     {"llm":True, "ttm":True, "sdt":True, "flow":True, "diag":True}),
    ("s15_full",     {"llm":True, "ttm":True, "sdt":True, "flow":True, "diag":True}),
]

# 8 scenarios with dialogue scripts
SCENARIOS = {
    "E01_zero_basics": [
        "I want to learn Python, complete beginner",
        "What is a variable? Explain simply",
        "So a variable is like a labeled box, right?",
        "How do I check what type a variable holds?",
        "I tried type(42) and got int, type('hello') gave str",
    ],
    "E02_metaphor": [
        "I think for loops are like factory workers processing items one by one",
        "So while loops are like a conveyor belt that keeps running",
        "Then nested loops are like an assembly line inside another line",
    ],
    "E03_stuck": [
        "I am stuck on recursion again",
        "I tried writing it twice and both failed",
        "Can you explain it a different way",
        "I still don't get it, maybe I am not cut out for programming",
    ],
    "E04_diagnostic": [
        "Quiz me on what I learned",
        "Lists are mutable, tuples are immutable in Python",
    ],
    "E05_cross_session": [
        "I learned variables and loops yesterday, ready to continue today",
        "You said you would teach me functions next",
        "I wrote a function but got an error: missing 1 required positional argument",
        "Oh, I forgot to pass the argument when calling it, I see now",
    ],
    "E06_parity": [
        "Just checking if the connection works properly",
    ],
    "E07_topic_switch": [
        "We were learning Python but I suddenly want to ask about databases",
        "How do I write a SQL SELECT statement",
        "What is a JOIN in SQL",
        "OK going back to Python, how do list comprehensions work",
    ],
    "E08_no_diag": [
        "Teach me what an API is",
        "What is the difference between REST API and regular API",
        "Why is it called REST and not something else",
    ],
}


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def apply_config(**flags):
    with open(CONFIG, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f)
    for k, v in [("llm", flags.get("llm", False)), ("ttm", flags.get("ttm", False)),
                 ("sdt", flags.get("sdt", False)), ("flow", flags.get("flow", False)),
                 ("diagnostic_engine", flags.get("diag", False))]:
        c.setdefault(k, {})["enabled"] = v
    if flags.get("llm"):
        c["llm"]["fallback_to_rules"] = True
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(c, f, allow_unicode=True, default_flow_style=False)
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]


def score_response(r):
    p = r.get("payload", {})
    stmt = p.get("statement", "")
    q = p.get("question", "")
    steps = p.get("steps", [])
    pe = r.get("personalization_evidence")
    ms = r.get("memory_status")
    dc = r.get("difficulty_contract")

    s = {}
    s["relevance"] = 4 if len(stmt) > 100 else (3 if len(stmt) > 60 else (2 if len(stmt) > 20 else 1))
    s["clarity"] = (4 if len(stmt) > 50 and any(w in stmt for w in [
        "like", "example", "imagine", "box", "label"]) else
        (3 if len(stmt) > 80 else (2 if len(stmt) > 30 else 1)))
    s["interactive"] = min(4, (1 if q else 0) + (
        1 if isinstance(steps, list) and len(steps) > 0 else 0) + (1 if len(stmt) > 100 else 0))
    s["structure"] = (4 if isinstance(steps, list) and len(steps) >= 2 else
                      (3 if len(stmt) > 120 else (2 if len(stmt) > 60 else 1)))
    s["personalization"] = min(4, (1 if pe and pe.get("sources_count", 0) > 0 else 0) + (
        1 if ms and ms.get("status") == "hit" else 0))
    s["encouragement"] = (4 if any(w in stmt for w in [
        "great", "good", "nice", "excellent", "well"]) else
        (2 if len(stmt) > 30 else 1))
    s["pers_evidence_quality"] = min(4, (1 if pe else 0) + (
        1 if pe and pe.get("sources_count", 0) >= 1 else 0) + (
        1 if pe and pe.get("sources_count", 0) >= 2 else 0) + (
        1 if ms and ms.get("status") == "hit" else 0))
    s["diff_explainability"] = min(4, (1 if dc else 0) + (
        1 if dc and dc.get("reason") else 0) + (
        1 if dc and dc.get("level") else 0) + (
        1 if dc and dc.get("reason") != "default" else 0))
    s["total"] = sum(s.values())
    return s


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG, "r", encoding="utf-8") as f:
        original = f.read()

    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"# S15 Full Exhaustive — 11x8=88 runs\n\n")

    total_runs = len(COMBOS) * len(SCENARIOS)
    log("=" * 60)
    log(f"S15 FULL EXHAUSTIVE: {len(COMBOS)} configs x {len(SCENARIOS)} scenarios = {total_runs} runs")
    log(f"8 dimensions: relevance clarity interactive structure personalization encouragement pers_evidence_quality diff_explainability")
    log("=" * 60)

    all_summaries = {}
    combo_idx = 0
    for label, flags in COMBOS:
        combo_idx += 1
        log(f"\n--- [{combo_idx}/{len(COMBOS)}] {label} ---")
        t0 = time.time()

        apply_config(**flags)
        from src.coach.agent import CoachAgent

        all_scores = []
        scene_details = {}

        for scene_id, dialogs in SCENARIOS.items():
            a = CoachAgent(session_id=f"s15full-{label}-{scene_id}")
            scene_scores = []

            for i, msg in enumerate(dialogs, 1):
                r = a.act(msg)
                s = score_response(r)
                scene_scores.append(s)

            avg_s = sum(x["total"] for x in scene_scores) / max(len(scene_scores), 1)
            dims = defaultdict(list)
            for x in scene_scores:
                for k, v in x.items():
                    if k != "total":
                        dims[k].append(v)
            scene_details[scene_id] = {
                "turns": len(scene_scores),
                "avg_score": round(avg_s, 1),
                "dimensions": {d: round(sum(v) / len(v), 1) for d, v in dims.items()},
            }
            all_scores.extend(scene_scores)

            has_pers = any(x["personalization"] > 0 for x in scene_scores)
            log(f"  {scene_id}: avg={avg_s:.1f}/32 pers={'YES' if has_pers else 'no'}")

        dt = time.time() - t0
        all_avg = sum(x["total"] for x in all_scores) / max(len(all_scores), 1)
        dims_all = defaultdict(list)
        for x in all_scores:
            for k, v in x.items():
                if k != "total":
                    dims_all[k].append(v)
        new_avg = (sum(dims_all.get("pers_evidence_quality", [0])) +
                   sum(dims_all.get("diff_explainability", [0]))) / max(2 * len(all_scores), 1)

        all_summaries[label] = {
            "turns": len(all_scores),
            "avg_quality": round(all_avg, 1),
            "new_dim_avg": round(new_avg, 1),
            "dimensions": {d: round(sum(v) / len(v), 2) for d, v in dims_all.items()},
            "scenes": scene_details,
            "time_s": round(dt, 0),
        }

        # Progress bar
        pct = combo_idx / len(COMBOS) * 100
        bar = "#" * int(pct / 2) + " " * (50 - int(pct / 2))
        print(f"\r[{bar}] {pct:.0f}% | {label}: {all_avg:.1f}/32 | new={new_avg:.1f}/8",
              end="", flush=True)

    print()  # newline after progress bar

    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(original)

    # Ranking
    log("\n" + "=" * 60)
    log("S15 FULL EXHAUSTIVE RESULTS")
    log("=" * 60)
    ranked = sorted(all_summaries.items(), key=lambda x: x[1]["avg_quality"], reverse=True)
    for i, (name, s) in enumerate(ranked, 1):
        bar = "#" * int(s["avg_quality"] / 2)
        log(f"  {i:2d}. {name:16s} {s['avg_quality']:5.1f}/32 {bar} | new={s['new_dim_avg']:.1f}/8")

    # Top-3 vs S14 baseline
    s15_top3 = sum(s["avg_quality"] for _, s in ranked[:3]) / 3
    s14_baseline = 15.6
    log(f"\nS14 baseline: {s14_baseline}/24 (6 dims)")
    log(f"S15 top-3:    {s15_top3:.1f}/32 (8 dims)")
    log(f"Note: scales differ — S14=24pt(6dim), S15=32pt(8dim)")

    # New dimension breakdown
    log("\n--- New Dimension Performance ---")
    for name, s in all_summaries.items():
        dims = s["dimensions"]
        peq = dims.get("pers_evidence_quality", 0)
        de = dims.get("diff_explainability", 0)
        log(f"  {name:16s} pers_evidence={peq:.1f}/4 diff_explain={de:.1f}/4")

    report_data = {
        "test_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configs": len(COMBOS),
        "scenarios": len(SCENARIOS),
        "total_runs": total_runs,
        "s14_baseline": s14_baseline,
        "summaries": all_summaries,
        "ranking": [(n, s["avg_quality"], s["new_dim_avg"]) for n, s in ranked],
    }
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\nReport: {REPORT}")
    print(f"Log: {LOG}")


if __name__ == "__main__":
    main()
