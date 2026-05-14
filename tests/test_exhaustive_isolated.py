"""穷举配置 + 连续多轮 + 配置隔离 + 教学质量评分.

每个配置组合在独立子进程中运行，确保配置真正隔离。
关注: 对话输出质量、教学引导效果、Phase 11 改进是否生效.
"""

import yaml, sys, time, json, subprocess, os
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

LOG = Path(__file__).resolve().parent.parent / "reports" / "exhaustive_isolated_test.log"
REPORT = Path(__file__).resolve().parent.parent / "reports" / "exhaustive_isolated_report.json"
CONFIG = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"

def log(msg: str):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ══════════════════════════════════════════════════
# 8 种关键配置组合
# ══════════════════════════════════════════════════

COMBOS = [
    ("all_off",      {"llm.enabled": False, "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    ("llm_only",     {"llm.enabled": True,  "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    ("llm_ttm",      {"llm.enabled": True,  "ttm.enabled": True,  "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    ("llm_ttm_sdt",  {"llm.enabled": True,  "ttm.enabled": True,  "sdt.enabled": True,  "flow.enabled": False, "diagnostic_engine.enabled": False}),
    ("full_behavior",{"llm.enabled": True,  "ttm.enabled": True,  "sdt.enabled": True,  "flow.enabled": True,  "diagnostic_engine.enabled": False}),
    ("full_stack",   {"llm.enabled": True,  "ttm.enabled": True,  "sdt.enabled": True,  "flow.enabled": True,  "diagnostic_engine.enabled": True}),
    ("llm_diag",     {"llm.enabled": True,  "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": True}),
    ("rules_diag",   {"llm.enabled": False, "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": True}),
]

# 10 轮学习对话
SCRIPT = [
    "我想学 Python，但是完全零基础",
    "变量是什么？用最简单的话说",
    "所以变量就像一个贴标签的盒子？",
    "那怎么知道变量存的是什么类型",
    "type(42)返回int，type('hello')返回str。为什么要有不同类型",
    "所以数字能算，字符串能拼。那列表是什么",
    "colors = ['red','blue','green'] 怎么取第一个",
    "colors[0]是red。要是有100个颜色怎么一个个处理",
    "for c in colors: print(c) — 这就是循环？while又是什么",
    "我好像理解了。考考我今天学的",
]


def run_combo_subprocess(label: str, combo: dict) -> dict:
    """在子进程中运行一个配置组合的完整对话."""
    script_code = f'''
import yaml, json, time, sys
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent}")

# Apply config
with open(r"{CONFIG}", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
for k, v in {combo}.items():
    parts = k.split(".")
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {{}})
    d[parts[-1]] = v
with open(r"{CONFIG}", "w", encoding="utf-8") as f:
    yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

# Reload module to pick up new config
import importlib
import src.coach.agent as agent_mod
importlib.reload(agent_mod)
from src.coach.agent import CoachAgent

results = []
agent = CoachAgent(session_id="{label}")
prev_stmt = ""
dialogs = {SCRIPT}

for i, msg in enumerate(dialogs, 1):
    t0 = time.time()
    r = agent.act(msg)
    dt = time.time() - t0
    p = r.get("payload", {{}})
    stmt = p.get("statement", "")
    question = p.get("question", "")
    steps = p.get("steps", [])
    option = p.get("option", "")

    # Quality scoring
    scores = {{}}
    scores["relevance"] = 4 if len(stmt) > 80 else (3 if len(stmt) > 40 else (2 if len(stmt) > 10 else 1))
    scores["clarity"] = 4 if any(w in stmt for w in ["像","比如","例如","就像","好比"]) and len(stmt)>50 else (3 if len(stmt)>80 else (2 if len(stmt)>30 else 1))
    scores["interactive"] = min(4, (1 if question else 0) + (1 if option else 0) + (1 if steps else 0) + (1 if len(stmt)>100 else 0))
    scores["structure"] = 4 if isinstance(steps, list) and len(steps) >= 2 else (3 if steps or len(stmt)>120 else (2 if len(stmt)>60 else 1))
    scores["personalization"] = 4 if any(w in stmt[:120] for w in ["你说的","你刚才","你之前","你提到","你问","你说得对","没错","对，"]) else (3 if prev_stmt and len(stmt)>50 else 2)
    scores["encouragement"] = 4 if any(w in stmt[:150] for w in ["棒","好","不错","太","厉害","进步","继续","试试"]) else (2 if len(stmt)>30 else 1)
    scores["total"] = sum(scores.values())

    results.append({{
        "turn": i, "ok": True,
        "action_type": r.get("action_type","?"),
        "ttm_stage": r.get("ttm_stage"),
        "llm": r.get("llm_generated", False),
        "stmt_len": len(stmt),
        "has_steps": isinstance(steps, list) and len(steps) > 0,
        "has_question": bool(question),
        "has_option": bool(option),
        "elapsed_s": round(dt, 2),
        "tokens": r.get("llm_tokens", 0),
        "quality": scores,
        "total_score": scores["total"],
    }})
    prev_stmt = stmt

print(json.dumps(results, ensure_ascii=False))
'''

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script_code],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
                 "PYTHONIOENCODING": "utf-8"},
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return {"ok": True, "label": label, "results": json.loads(proc.stdout)}
        else:
            return {"ok": False, "label": label, "error": proc.stderr[:500] or f"exit={proc.returncode}", "stdout": proc.stdout[:200]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "label": label, "error": "timeout (300s)"}
    except Exception as e:
        return {"ok": False, "label": label, "error": str(e)}


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG, "r", encoding="utf-8") as f:
        original = f.read()

    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"# Exhaustive Isolated Config Test — {datetime.now(timezone.utc).isoformat()}\n\n")

    log("=" * 70)
    log("EXHAUSTIVE ISOLATED CONFIG TEST")
    log(f"Combos: {len(COMBOS)} × 10 turns = {len(COMBOS)*10} conversations")
    log(f"Date: {datetime.now(timezone.utc).isoformat()}")
    log("=" * 70)

    all_summaries = {}

    for label, combo in COMBOS:
        log(f"\n--- COMBO: {label} ---")
        log(f"  Config: {combo}")
        t0 = time.time()

        result = run_combo_subprocess(label, combo)
        dt = time.time() - t0

        if not result["ok"]:
            log(f"  FAILED: {result.get('error', 'unknown')}")
            all_summaries[label] = {"ok": False, "error": result.get("error",""), "turns": 0, "avg_quality": 0}
            continue

        turns = result["results"]
        ok = sum(1 for t in turns if t.get("ok"))
        avg_q = sum(t.get("total_score", 0) for t in turns) / max(len(turns), 1)
        llm_count = sum(1 for t in turns if t.get("llm"))
        has_steps = sum(1 for t in turns if t.get("has_steps"))
        has_question = sum(1 for t in turns if t.get("has_question"))
        avg_tokens = sum(t.get("tokens", 0) for t in turns) / max(len(turns), 1)
        ttm_stages = [t.get("ttm_stage") for t in turns if t.get("ttm_stage")]
        actions = [t.get("action_type") for t in turns]
        dims = defaultdict(list)
        for t in turns:
            for dim, score in t.get("quality", {}).items():
                if dim != "total":
                    dims[dim].append(score)

        all_summaries[label] = {
            "turns": len(turns), "ok": ok,
            "avg_quality": round(avg_q, 1),
            "llm_rate": f"{llm_count}/{ok}",
            "has_steps": f"{has_steps}/{ok}",
            "has_question": f"{has_question}/{ok}",
            "avg_tokens": round(avg_tokens, 0),
            "ttm_stages": dict((s, ttm_stages.count(s)) for s in set(ttm_stages)) if ttm_stages else {},
            "actions": dict((a, actions.count(a)) for a in set(actions)),
            "dimensions": {d: round(sum(s)/len(s), 2) for d, s in dims.items()},
            "time_s": round(dt, 0),
        }

        log(f"  {ok}/{len(turns)} ok | avg quality: {avg_q:.1f}/24 | llm: {llm_count}/{ok}")
        log(f"  steps: {has_steps}/{ok} | questions: {has_question}/{ok} | avg tokens: {avg_tokens:.0f}")
        log(f"  actions: {all_summaries[label]['actions']}")
        log(f"  ttm: {all_summaries[label]['ttm_stages']}")
        log(f"  dimensions: {all_summaries[label]['dimensions']}")
        log(f"  time: {dt:.0f}s")

    # Restore config
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(original)

    # Final ranking
    log("\n" + "=" * 70)
    log("QUALITY RANKING")
    log("=" * 70)
    ranked = sorted(
        [(n, s) for n, s in all_summaries.items() if s.get("ok")],
        key=lambda x: x[1]["avg_quality"], reverse=True)
    for i, (name, summary) in enumerate(ranked, 1):
        bar = "█" * int(summary["avg_quality"])
        log(f"  {i}. {name:18s} {summary['avg_quality']:4.1f}/24 {bar}")
        log(f"     steps={summary['has_steps']} questions={summary['has_question']} actions={summary['actions']}")

    # LLM vs Rule comparison
    llm_combos = [s for n, s in all_summaries.items() if s.get("ok") and n not in ("all_off", "rules_diag")]
    rule_combos = [s for n, s in all_summaries.items() if s.get("ok") and n in ("all_off", "rules_diag")]
    if llm_combos:
        log(f"\n  LLM avg:  {sum(s['avg_quality'] for s in llm_combos)/len(llm_combos):.1f}/24")
    if rule_combos:
        log(f"  Rule avg: {sum(s['avg_quality'] for s in rule_combos)/len(rule_combos):.1f}/24")

    # TTM impact on steps
    ttm_on = [s for n, s in all_summaries.items() if s.get("ok") and "llm_ttm" in n or "full_" in n or "behavior" in n]
    ttm_off = [s for n, s in all_summaries.items() if s.get("ok") and n in ("llm_only", "llm_diag", "rules_diag", "all_off")]
    if ttm_on:
        log(f"\n  TTM ON avg quality:  {sum(s['avg_quality'] for s in ttm_on)/len(ttm_on):.1f}/24")
    if ttm_off:
        log(f"  TTM OFF avg quality: {sum(s['avg_quality'] for s in ttm_off)/len(ttm_off):.1f}/24")

    # Phase 11 improvements check
    log("\n--- Phase 11 Improvement Metrics ---")
    for name, summary in all_summaries.items():
        if not summary.get("ok"): continue
        steps_pct = int(summary["has_steps"].split("/")[0]) / int(summary["has_steps"].split("/")[1]) * 100
        log(f"  {name:18s}: steps={summary['has_steps']} ({steps_pct:.0f}%), questions={summary['has_question']}, quality={summary['avg_quality']}/24")

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now(timezone.utc).isoformat(),
            "combos": len(COMBOS),
            "total_turns": len(COMBOS) * 10,
            "summaries": all_summaries,
            "ranking": [(n, s["avg_quality"]) for n, s in ranked],
        }, f, ensure_ascii=False, indent=2)

    log(f"\nReport: {REPORT}")
    log(f"Log: {LOG}")


if __name__ == "__main__":
    main()
