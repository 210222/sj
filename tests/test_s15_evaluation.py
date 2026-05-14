"""Phase 15 穷尽评测 — 11配置×8场景×HTTP路径×8维评分."""

import yaml, sys, time, json, subprocess, os
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "reports" / "s15_evaluation_log.txt"
REPORT = ROOT / "reports" / "s15_evaluation_report.json"
CONFIG = ROOT / "config" / "coach_defaults.yaml"

COMBOS = [
    ("all_off",      {"llm.enabled":False,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("rules_diag",   {"llm.enabled":False,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":True}),
    ("llm_only",     {"llm.enabled":True,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("llm_ttm",      {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("llm_ttm_sdt",  {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("full_behavior",{"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":False}),
    ("llm_diag",     {"llm.enabled":True,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":True}),
    ("full_stack",   {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":True}),
    ("s15_person",   {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":False}),
    ("s15_diff",     {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":False}),
    ("s15_full",     {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":True}),
]

SCENARIOS = {
    "E01_zero_basics": [
        "我想学 Python，完全零基础",
        "变量是什么？用最简单的话解释",
        "所以变量就像一个盒子标签对吧",
        "那我怎么知道变量里存的是什么类型",
        "我试了 type(42) 结果是 int，type('hello') 是 str",
    ],
    "E02_metaphor_continuity": [
        "我觉得 for 循环就像流水线工人，一个个处理产品",
        "所以 while 循环就是那种一直在转的传送带",
        "那嵌套循环就是流水线套流水线了",
    ],
    "E03_repeated_stuck": [
        "我又卡在递归上了",
        "我试了两次都没写对",
        "能不能换个方式再讲一遍",
        "还是不懂，我是不是不适合学编程",
    ],
    "E04_diagnostic_answer": [
        "来考考我吧",
        "Python 中列表和元组的区别是列表可以修改，元组不能修改",
    ],
    "E05_cross_session": [
        "我昨天学了变量和循环，今天继续",
        "上次你说要教我函数",
        "def 关键字后面是不是一定要加括号",
        "我写了一个函数但报错了，说 missing 1 required positional argument",
        "哦我知道了，调用时忘记传参数了",
    ],
    "E06_parity_check": [
        "简单测试一下连接是否正常",
    ],
    "E07_topic_switch": [
        "刚才在学 Python，但我突然想问数据库的问题",
        "SQL 的 SELECT 语句怎么写",
        "那 JOIN 又是什么",
        "好的，回到 Python，列表推导式怎么用",
    ],
    "E08_no_diagnostic": [
        "给我讲一下什么是 API",
        "REST API 和普通 API 有什么区别",
        "为什么叫 REST 不叫别的名字",
    ],
}

AGENT_SCRIPT = """
import yaml, json, time, sys
sys.path.insert(0, r"{root}")

with open(r"{config_path}", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
for k, v in {combo}.items():
    parts = k.split(".")
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {{}})
    d[parts[-1]] = v
with open(r"{config_path}", "w", encoding="utf-8") as f:
    yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

import importlib, src.coach.agent as agent_mod
importlib.reload(agent_mod)
from src.coach.agent import CoachAgent

results = []
agent = CoachAgent(session_id="{session_id}")
dialogs = {dialogs}

for i, msg in enumerate(dialogs, 1):
    t0 = time.time()
    r = agent.act(msg)
    dt = time.time() - t0
    p = r.get("payload", {{}})
    stmt = p.get("statement", "")

    # 8-dimension scoring
    s = {{}}
    s["relevance"] = 4 if len(stmt)>100 else (3 if len(stmt)>60 else (2 if len(stmt)>20 else 1))
    s["clarity"] = 4 if any(w in stmt for w in ["像","比如","例如","就像","好比","example"]) and len(stmt)>50 else (3 if len(stmt)>80 else (2 if len(stmt)>30 else 1))
    q = p.get("question","")
    steps = p.get("steps",[])
    opt = p.get("option","")
    s["interactive"] = min(4, (1 if q else 0)+(1 if isinstance(steps,list) and len(steps)>0 else 0)+(1 if opt else 0)+(1 if len(stmt)>100 else 0))
    s["structure"] = 4 if isinstance(steps,list) and len(steps)>=2 else (3 if steps or len(stmt)>120 else (2 if len(stmt)>60 else 1))
    pe = r.get("personalization_evidence")
    ms = r.get("memory_status")
    s["personalization"] = min(4, (1 if pe and pe.get("sources_count",0)>0 else 0)+(1 if ms and ms.get("status")=="hit" else 0)+(1 if any(w in stmt[:100] for w in ["你说","你刚","上次","之前"])))
    s["encouragement"] = 4 if any(w in stmt[:150] for w in ["棒","好","不错","太","厉害","进步","继续","试试"]) else (2 if len(stmt)>30 else 1)
    s["pers_evidence_quality"] = min(4, (1 if pe else 0)+(1 if pe and pe.get("sources_count",0)>=1 else 0)+(1 if pe and pe.get("sources_count",0)>=2 else 0)+(1 if ms and ms.get("status")=="hit" else 0))
    dc = r.get("difficulty_contract")
    s["diff_explainability"] = min(4, (1 if dc else 0)+(1 if dc and dc.get("reason") else 0)+(1 if dc and dc.get("level") else 0)+(1 if dc and dc.get("reason")!="default" else 0))
    s["total"] = sum(s.values())

    results.append({{
        "turn": i, "ok": True, "action_type": r.get("action_type","?"),
        "ttm_stage": r.get("ttm_stage"), "has_steps": isinstance(steps,list) and len(steps)>0,
        "llm": r.get("llm_generated",False), "elapsed_s": round(dt,2),
        "tokens": r.get("llm_tokens",0), "stmt_preview": stmt[:120],
        "quality": s, "total_score": s["total"],
        "personalization_evidence": pe,
        "memory_status": ms,
        "difficulty_contract": dc,
    }})

print(json.dumps(results, ensure_ascii=False))
"""

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f: f.write(msg+"\n")

def run_combo(label, combo):
    results = {}
    for scene_id, dialogs in SCENARIOS.items():
        combo_py = "{" + ", ".join(f'"{k}": {v}' for k,v in combo.items()) + "}"
        session_id = f"s15-{label}-{scene_id}"
        code = AGENT_SCRIPT.format(
            root=str(ROOT), config_path=str(CONFIG), combo=combo_py,
            session_id=session_id, dialogs=json.dumps(dialogs, ensure_ascii=False))

        try:
            proc = subprocess.run([sys.executable, "-c", code],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
                env={**os.environ, "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY",""),
                     "PYTHONIOENCODING": "utf-8"})
            if proc.returncode == 0 and proc.stdout.strip():
                results[scene_id] = json.loads(proc.stdout)
            else:
                results[scene_id] = {"error": (proc.stderr or "")[:300]}
        except subprocess.TimeoutExpired:
            results[scene_id] = {"error": "timeout"}
    return results

def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG, "r", encoding="utf-8") as f: original = f.read()
    with open(LOG, "w", encoding="utf-8") as f: f.write(f"# S15 Evaluation — {datetime.now(timezone.utc).isoformat()}\n\n")

    log("="*60)
    log(f"S15 EVALUATION: {len(COMBOS)} configs x {len(SCENARIOS)} scenarios = {len(COMBOS)*len(SCENARIOS)} runs")
    log(f"Scoring: 8 dimensions (6 legacy + 2 new)")
    log("="*60)

    all_summaries = {}
    for label, combo in COMBOS:
        log(f"\n--- {label} ---")
        t0 = time.time()
        scene_results = run_combo(label, combo)
        dt = time.time() - t0

        all_turns = []
        for scene_id, turns in scene_results.items():
            if isinstance(turns, list):
                all_turns.extend(turns)

        if not all_turns:
            log(f"  FAILED: no valid turns")
            all_summaries[label] = {"ok": False, "turns": 0, "avg_quality": 0, "new_dim_avg": 0}
            continue

        avg_q = sum(t.get("total_score",0) for t in all_turns) / len(all_turns)
        dims = defaultdict(list)
        for t in all_turns:
            for d,s in t.get("quality",{}).items():
                if d != "total": dims[d].append(s)

        new_dims = ["pers_evidence_quality","diff_explainability"]
        new_avg = sum(sum(dims.get(d,[0]))/max(len(dims.get(d,[])),1) for d in new_dims)

        all_summaries[label] = {
            "turns": len(all_turns), "avg_quality": round(avg_q,1),
            "new_dim_avg": round(new_avg,1),
            "dimensions": {d: round(sum(s)/len(s),2) for d,s in dims.items()},
            "time_s": round(dt,0),
        }
        log(f"  {len(all_turns)} turns | quality={avg_q:.1f}/32 | new_dims={new_avg:.1f}/8 | dims={json.dumps(all_summaries[label]['dimensions'])} | {dt:.0f}s")

    with open(CONFIG, "w", encoding="utf-8") as f: f.write(original)

    log("\n" + "="*60)
    log("S15 EVALUATION RESULTS")
    log("="*60)
    ranked = sorted([(n,s) for n,s in all_summaries.items() if s.get("ok")], key=lambda x: x[1]["avg_quality"], reverse=True)
    for i,(name,s) in enumerate(ranked,1):
        bar = "#"*int(s["avg_quality"]/2)
        log(f"  {i:2d}. {name:16s} {s['avg_quality']:5.1f}/32 {bar} | new={s['new_dim_avg']:.1f}/8")

    # S14 vs S15 comparison
    s14_baseline = 15.6
    s15_avg = sum(s["avg_quality"] for _,s in ranked[:5]) / 5
    log(f"\nS14 baseline: {s14_baseline}/24 | S15 top-5: {s15_avg:.1f}/32 | Delta: {s15_avg - s14_baseline:.1f}")

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now(timezone.utc).isoformat(),
            "configs": len(COMBOS), "scenarios": len(SCENARIOS),
            "s14_baseline": 15.6, "summaries": all_summaries,
            "ranking": [(n,s["avg_quality"],s["new_dim_avg"]) for n,s in ranked],
        }, f, ensure_ascii=False, indent=2)
    log(f"\nReport: {REPORT}")

if __name__ == "__main__":
    main()
