"""S15 Quick Evaluation — 5 configs x direct process, no subprocess."""
import yaml, time, json, importlib, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "config" / "coach_defaults.yaml"

TEST_CONFIGS = [
    ("all_off",     {"llm":False,"ttm":False,"sdt":False,"flow":False,"diag":False}),
    ("rules_diag",  {"llm":False,"ttm":False,"sdt":False,"flow":False,"diag":True}),
    ("llm_only",    {"llm":True, "ttm":False,"sdt":False,"flow":False,"diag":False}),
    ("llm_ttm_sdt", {"llm":True, "ttm":True, "sdt":True, "flow":False,"diag":False}),
    ("full_stack",  {"llm":True, "ttm":True, "sdt":True, "flow":True, "diag":True}),
]

TEST_MESSAGES = [
    "I want to learn Python, I am a complete beginner",
    "What is a variable? Explain in the simplest way",
    "So a variable is like a labeled box, right?",
    "I am stuck, how do I check the type of a variable?",
    "I tried type(42) and it returned int! type('hello') returned str",
]

with open(CONFIG, "r", encoding="utf-8") as f:
    original = f.read()


def apply_config(llm=False, ttm=False, sdt=False, flow=False, diag=False):
    with open(CONFIG, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f)
    for k, v in [("llm", llm), ("ttm", ttm), ("sdt", sdt),
                 ("flow", flow), ("diagnostic_engine", diag)]:
        c.setdefault(k, {})["enabled"] = v
    if llm:
        c["llm"]["fallback_to_rules"] = True
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(c, f, allow_unicode=True, default_flow_style=False)
    # Clear module cache so CoachAgent reads new config
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
    s["clarity"] = 4 if len(stmt) > 50 and any(
        w in stmt for w in ["like", "example", "imagine", "box", "label"]) else (
        3 if len(stmt) > 80 else (2 if len(stmt) > 30 else 1))
    s["interactive"] = min(4, (1 if q else 0) + (
        1 if isinstance(steps, list) and len(steps) > 0 else 0) + (1 if len(stmt) > 100 else 0))
    s["structure"] = 4 if isinstance(steps, list) and len(
        steps) >= 2 else (3 if len(stmt) > 120 else (2 if len(stmt) > 60 else 1))
    s["personalization"] = min(4, (1 if pe and pe.get("sources_count", 0) > 0 else 0) + (
        1 if ms and ms.get("status") == "hit" else 0))
    s["encouragement"] = 4 if any(
        w in stmt for w in ["great", "good", "nice", "excellent", "well"]) else (
        2 if len(stmt) > 30 else 1)
    s["pers_evidence_quality"] = min(4, (1 if pe else 0) + (
        1 if pe and pe.get("sources_count", 0) >= 1 else 0) + (
        1 if pe and pe.get("sources_count", 0) >= 2 else 0) + (
        1 if ms and ms.get("status") == "hit" else 0))
    s["diff_explainability"] = min(4, (1 if dc else 0) + (
        1 if dc and dc.get("reason") else 0) + (
        1 if dc and dc.get("level") else 0) + (
        1 if dc and dc.get("reason") != "default" else 0))
    # Phase 24: 纵向评测维度 (从响应 dict 推断学习效果)
    diag = r.get("diagnostic_result")
    s["mastery_progress"] = min(4, (
        2 if diag and isinstance(diag, dict) and diag.get("evaluated") else 0
    ) + (
        2 if diag and isinstance(diag, dict) and diag.get("mastery_after", 0) > 0.5 else 0
    ))
    s["knowledge_retention"] = 4 if (
        dc and isinstance(dc, dict) and dc.get("reason") == "bkt_mastery"
    ) else 0
    s["total"] = sum(v for k, v in s.items() if k != "total")
    return s


def main():
    print("=" * 60)
    print("S15 QUICK EVALUATION: 5 configs x 5 turns")
    print("=" * 60)

    all_results = {}
    for label, flags in TEST_CONFIGS:
        apply_config(**flags)
        from src.coach.agent import CoachAgent
        a = CoachAgent(session_id=f"s15-v2-{label}")
        scores = []

        for i, msg in enumerate(TEST_MESSAGES, 1):
            r = a.act(msg)
            s = score_response(r)
            scores.append(s)
            new_dims = {k: s[k] for k in [
                "pers_evidence_quality", "diff_explainability"] if k in s}
            print(
                f"  [{label:14s}] T{i}: {s['total']:2d}/32 "
                f"pers={s['personalization']}/4 new={new_dims}")

        avg = sum(x["total"] for x in scores) / len(scores)
        dims = defaultdict(list)
        for x in scores:
            for k, v in x.items():
                if k != "total":
                    dims[k].append(v)
        new_avg = (sum(dims.get("pers_evidence_quality", [0])) +
                   sum(dims.get("diff_explainability", [0]))) / max(2 * len(scores), 1)

        all_results[label] = {
            "avg": round(avg, 1),
            "new_dim_avg": round(new_avg, 1),
            "dimensions": {d: round(sum(v) / len(v), 2)
                           for d, v in dims.items()},
        }
        print(f"  >> {label}: {avg:.1f}/32 | new_dims={new_avg:.1f}/8")
        print()

    print("=" * 60)
    print("RANKING")
    ranked = sorted(all_results.items(), key=lambda x: x[1]["avg"], reverse=True)
    for i, (name, data) in enumerate(ranked, 1):
        bar = "#" * int(data["avg"] / 2)
        print(
            f"  {i}. {name:16s} {data['avg']:5.1f}/32 {bar} "
            f"| new={data['new_dim_avg']:.1f}/8")

    s15_top3 = sum(r["avg"] for _, r in ranked[:3]) / 3
    print(f"\nS14 baseline: 15.6/24")
    print(f"S15 top-3:    {s15_top3:.1f}/32")
    print(f"Delta:        {s15_top3 - 15.6:+.1f}")

    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(original)
    print("\nConfig restored.")


if __name__ == "__main__":
    main()
