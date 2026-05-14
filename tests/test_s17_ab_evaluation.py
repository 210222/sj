"""S17 A/B Evaluation — llm_only vs full_stack, 5 scenarios x 5 rounds, statistical output."""
import yaml, time, json, sys, statistics, math
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "config" / "coach_defaults.yaml"
REPORT = ROOT / "reports" / "s17_ab_report.json"

TEST_CONFIGS = [
    ("llm_only",   {"llm": True, "ttm": False, "sdt": False, "flow": False, "diag": False}),
    ("full_stack", {"llm": True, "ttm": True,  "sdt": True,  "flow": True,  "diag": True}),
]

TEST_SCENARIOS = [
    ("E01_basics", [
        "I want to learn Python, I am a complete beginner",
        "What is a variable? Explain in the simplest way",
        "So a variable is like a labeled box, right?",
        "I am stuck, how do I check the type of a variable?",
        "I tried type(42) and it returned int! type('hello') returned str",
    ]),
    ("E03_stuck", [
        "I feel like I am not making progress",
        "Every time I try to learn something new, I forget the old stuff",
        "What should I do when I get frustrated?",
        "Maybe I should just give up on this",
        "Is there a way to make learning less painful?",
    ]),
    ("E05_cross", [
        "Yesterday I learned about functions, can we review?",
        "I wrote a function but it returns None, why?",
        "Let me try: def greet(name): print('Hello', name)",
        "Oh, print displays but doesn't return a value",
        "I want to connect this to what I learned about variables",
    ]),
    ("E07_switch", [
        "I finished the Python tutorial, now I want to learn data science",
        "What is a pandas DataFrame?",
        "How is that different from a list of dictionaries?",
        "Can you show me a concrete example comparing both?",
        "OK, I see the trade-off. What about visualization?",
    ]),
    ("E08_burnout", [
        "I have been coding 12 hours a day and I am exhausted",
        "But I have a deadline, I can't stop now",
        "How do other people manage this?",
        "Maybe I should try the Pomodoro technique",
        "I tried 25 min work / 5 min break, it helped a little",
    ]),
]

with open(CONFIG, "r", encoding="utf-8") as f:
    _original_yaml = f.read()


def apply_config(llm=False, ttm=False, sdt=False, flow=False, diag=False):
    with open(CONFIG, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f)
    for k, v in [("llm", llm), ("ttm", ttm), ("sdt", sdt),
                 ("flow", flow), ("diagnostic_engine", diag)]:
        if k in c:
            c[k]["enabled"] = v
    if llm:
        c.setdefault("llm", {})["fallback_to_rules"] = True
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(c, f, allow_unicode=True, default_flow_style=False)
    for mod in list(sys.modules.keys()):
        if mod.startswith("src.coach"):
            del sys.modules[mod]


def score_response(r, config_name: str) -> dict:
    """Score a single response across 10 dimensions, max 40 points."""
    p = r.get("payload", {})
    stmt = p.get("statement", "")
    q = p.get("question", "")
    steps = p.get("steps", []) if isinstance(p.get("steps"), list) else []

    # Original 8 dimensions (from S15)
    dims = {}
    dims["relevance"] = 4 if len(stmt) > 100 else 3 if len(stmt) > 60 else 2 if len(stmt) > 20 else 1
    dims["clarity"] = (4 if (len(stmt) > 50 and any(w in stmt.lower() for w in ["like", "example", "imagine", "box", "label"]))
                       else 3 if len(stmt) > 80 else 2 if len(stmt) > 30 else 1)
    dims["interactive"] = min(4, (1 if q else 0) + (1 if len(steps) > 0 else 0) + (1 if len(stmt) > 100 else 0) + 1)
    dims["structure"] = 4 if len(steps) >= 2 else 3 if len(stmt) > 120 else 2 if len(stmt) > 60 else 1

    pe = r.get("personalization_evidence")
    mem = r.get("memory_status")
    dims["personalization"] = min(4, (1 if pe and pe.get("sources_count", 0) > 0 else 0) + (1 if mem == "hit" else 0) + 2)
    dims["encouragement"] = 4 if any(w in stmt.lower() for w in ["great", "good", "nice", "excellent", "well"]) else 2 if len(stmt) > 30 else 1
    dims["pers_evidence_quality"] = min(4, (1 if pe else 0) + (1 if pe and pe.get("sources_count", 0) >= 1 else 0) + (1 if pe and pe.get("sources_count", 0) >= 2 else 0) + (1 if mem == "hit" else 0))
    dc = r.get("difficulty_contract")
    dims["diff_explainability"] = min(4, (1 if dc else 0) + (1 if dc and dc.get("reason") else 0) + (1 if dc and dc.get("level") else 0) + (1 if dc and dc.get("reason") != "default" else 0))

    # S17-specific 2 dimensions
    sdt_p = r.get("sdt_profile")
    dims["autonomy_support"] = min(4, 1 + (1 if sdt_p and sdt_p.get("autonomy", 0.5) > 0.3 else 0) + (1 if sdt_p and sdt_p.get("competence", 0.5) > 0.3 else 0) + (1 if sdt_p and sdt_p.get("relatedness", 0.5) > 0.3 else 0))
    ttm_s = r.get("ttm_stage")
    dims["stage_awareness"] = 3 if ttm_s and ttm_s != "contemplation" else 1 if ttm_s else 0

    dims["_total"] = sum(dims.values())
    return dims


def cohens_d(control: list[float], treatment: list[float]) -> float:
    n_c, n_t = len(control), len(treatment)
    if n_c < 2 or n_t < 2:
        return 0.0
    m_c, m_t = statistics.mean(control), statistics.mean(treatment)
    var_c = statistics.variance(control) if n_c > 1 else 0.0
    var_t = statistics.variance(treatment) if n_t > 1 else 0.0
    pooled = math.sqrt(((n_c - 1) * var_c + (n_t - 1) * var_t) / (n_c + n_t - 2))
    return (m_t - m_c) / pooled if pooled > 0 else 0.0


def compute_ci(scores: list[float]) -> tuple:
    n = len(scores)
    if n < 2:
        return (scores[0] if scores else 0, scores[0] if scores else 0)
    m = statistics.mean(scores)
    se = statistics.stdev(scores) / math.sqrt(n)
    z = 1.96  # Normal approximation
    return (m - z * se, m + z * se)


def restore_yaml():
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(_original_yaml)


def main():
    results = {}
    all_dims_scores: dict = defaultdict(lambda: defaultdict(list))

    for cfg_name, cfg_params in TEST_CONFIGS:
        print(f"\n[{cfg_name}] Applying config...")
        apply_config(**cfg_params)

        from src.coach.agent import CoachAgent
        cfg_scores: list[dict] = []

        for scenario_name, messages in TEST_SCENARIOS:
            sid = f"s17-ab-{cfg_name}-{scenario_name}-{int(time.time())}"
            agent = CoachAgent(session_id=sid)
            for i, msg in enumerate(messages):
                try:
                    r = agent.act(msg)
                    s = score_response(r, cfg_name)
                    s["_scenario"] = scenario_name
                    s["_turn"] = i
                    cfg_scores.append(s)
                    for dim, val in s.items():
                        if not dim.startswith("_"):
                            all_dims_scores[cfg_name][dim].append(val)
                except Exception as e:
                    print(f"  WARN: {scenario_name} turn {i} error: {e}")

        totals = [s["_total"] for s in cfg_scores if "_total" in s]
        results[cfg_name] = {
            "turns": len(cfg_scores),
            "mean_total": round(statistics.mean(totals), 2) if totals else 0,
            "std_total": round(statistics.stdev(totals), 2) if len(totals) > 1 else 0,
            "ci95": [round(x, 2) for x in compute_ci(totals)],
            "dim_means": {},
            "scenarios": [],
        }
        for dim in sorted(all_dims_scores[cfg_name].keys()):
            vals = all_dims_scores[cfg_name][dim]
            results[cfg_name]["dim_means"][dim] = {
                "mean": round(statistics.mean(vals), 2),
                "std": round(statistics.stdev(vals), 2) if len(vals) > 1 else 0,
            }

        for s in cfg_scores:
            results[cfg_name]["scenarios"].append({
                "scenario": s.get("_scenario", "?"),
                "turn": s.get("_turn", 0),
                "total": s.get("_total", 0),
            })

    # Comparison
    cfg_names = [c[0] for c in TEST_CONFIGS]
    if len(cfg_names) == 2 and cfg_names[0] in results and cfg_names[1] in results:
        a, b = cfg_names[0], cfg_names[1]
        a_total = [s["_total"] for s in results[a].get("_raw", [])]
        comparison = {
            "mean_delta": round(results[b]["mean_total"] - results[a]["mean_total"], 2),
            "cohens_d_per_dim": {},
            "personalization_improvement_pct": 0,
        }
        for dim in all_dims_scores[a].keys():
            comparison["cohens_d_per_dim"][dim] = round(
                cohens_d(all_dims_scores[a][dim], all_dims_scores[b][dim]), 2)
        pa = results[a]["dim_means"].get("personalization", {}).get("mean", 0)
        pb = results[b]["dim_means"].get("personalization", {}).get("mean", 0)
        if pa > 0:
            comparison["personalization_improvement_pct"] = round((pb - pa) / pa * 100, 1)
        results["comparison"] = comparison

    results["metadata"] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "configs_tested": len(TEST_CONFIGS),
        "total_turns": sum(r["turns"] for r in results.values() if isinstance(r, dict) and "turns" in r),
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Console summary
    print(f"\n{'='*60}")
    print("S17 A/B EVALUATION: llm_only vs full_stack")
    print(f"{'='*60}")
    for cfg_name, _ in TEST_CONFIGS:
        r = results[cfg_name]
        print(f"[{cfg_name}] {r['turns']} turns: mean={r['mean_total']}/40, std={r['std_total']}, CI95={r['ci95']}")
    if "comparison" in results:
        c = results["comparison"]
        print(f"\nMean delta: {c['mean_delta']:+.1f} (full_stack - llm_only)")
        print(f"Personalization improvement: {c['personalization_improvement_pct']:+.1f}%")
        print(f"\nCohen's d per dimension:")
        for dim, d in sorted(c["cohens_d_per_dim"].items(), key=lambda x: -abs(x[1])):
            sig = " ***" if abs(d) > 0.8 else " **" if abs(d) > 0.5 else " *" if abs(d) > 0.2 else ""
            print(f"  {dim:25s}: {d:+.2f}{sig}")
    print(f"\nReport: {REPORT}")

    restore_yaml()


if __name__ == "__main__":
    main()
