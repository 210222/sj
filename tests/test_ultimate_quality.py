"""终极测试: 配置组合 × 连续多轮对话 × 教学质量评分.

12 种关键配置 × 10 轮连续对话 = 120 次有状态交互
每个回复在 6 个质量维度上打分(0-4分) → 满分 24
"""

import yaml, sys, time, json, os, itertools, re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.coach.agent import CoachAgent

LOG = Path(__file__).resolve().parent.parent / "reports" / "ultimate_quality_test.log"
REPORT = Path(__file__).resolve().parent.parent / "reports" / "ultimate_quality_report.json"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"


def log(msg: str):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ══════════════════════════════════════════════════
# 12 种核心配置组合
# ══════════════════════════════════════════════════

CONFIG_COMBOS = [
    # 基线: 全关 (纯规则)
    ("baseline_rules", {"llm.enabled": False, "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    # 仅 LLM
    ("llm_only", {"llm.enabled": True, "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    # LLM + TTM
    ("llm_ttm", {"llm.enabled": True, "ttm.enabled": True, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    # LLM + TTM + SDT
    ("llm_ttm_sdt", {"llm.enabled": True, "ttm.enabled": True, "sdt.enabled": True, "flow.enabled": False, "diagnostic_engine.enabled": False}),
    # 全开: LLM + TTM + SDT + Flow
    ("all_behavior", {"llm.enabled": True, "ttm.enabled": True, "sdt.enabled": True, "flow.enabled": True, "diagnostic_engine.enabled": False}),
    # 全开 + 诊断引擎
    ("full_stack", {"llm.enabled": True, "ttm.enabled": True, "sdt.enabled": True, "flow.enabled": True, "diagnostic_engine.enabled": True}),
    # LLM + 诊断 (无行为模型)
    ("llm_diag", {"llm.enabled": True, "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": True}),
    # LLM + TTM + 诊断
    ("llm_ttm_diag", {"llm.enabled": True, "ttm.enabled": True, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": True}),
    # 安全全开
    ("safety_full", {"llm.enabled": True, "sovereignty_pulse.enabled": True, "excursion.enabled": True, "relational_safety.enabled": True}),
    # 行为 + 安全
    ("behavior_safety", {"llm.enabled": True, "ttm.enabled": True, "sdt.enabled": True, "sovereignty_pulse.enabled": True, "relational_safety.enabled": True}),
    # 纯规则 + 诊断
    ("rules_diag", {"llm.enabled": False, "diagnostic_engine.enabled": True}),
    # 全关 baseline 对照
    ("all_off", {"llm.enabled": False, "ttm.enabled": False, "sdt.enabled": False, "flow.enabled": False, "diagnostic_engine.enabled": False, "sovereignty_pulse.enabled": False, "excursion.enabled": False, "relational_safety.enabled": False}),
]


def apply_combo(combo: dict):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for key, val in combo.items():
        parts = key.split(".")
        d = cfg
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


# ══════════════════════════════════════════════════
# 连续 10 轮对话脚本 — 模拟真实学习场景
# ══════════════════════════════════════════════════

LEARNING_SCRIPT = [
    "我想学 Python，但是完全零基础，从哪开始",
    # coach should guide to basics
    "变量是什么，用最简单的话解释",
    # coach should explain
    "所以变量就像一个盒子，可以放不同的东西进去对吧",
    # coach should confirm + extend
    "那我怎么知道一个变量里面放的是什么类型的数据",
    # coach should introduce type()
    "type(42) 返回 int，type('hello') 返回 str — 我试了！那为什么要有不同类型",
    # coach should explain type purpose
    "所以数字可以加减，字符串可以拼接？那列表呢",
    # coach should introduce list
    "colors = ['red', 'blue'] — 我怎么取出第一个颜色",
    # coach should explain indexing
    "colors[0] 是 red！那如果我有 100 个颜色，怎么一个个处理",
    # coach should introduce for loop
    "for c in colors: print(c) — 这就叫循环对吧。那 while 循环又是什么",
    # coach should explain while vs for
    "我好像有点感觉了。能考考我今天学的东西吗",
]


# ══════════════════════════════════════════════════
# 质量评分系统 (每个维度 0-4 分, 满分 24)
# ══════════════════════════════════════════════════

def score_quality(result: dict, turn_num: int, prev_stmt: str = "") -> dict:
    """评估单轮回复的教学质量."""
    p = result.get("payload", {})
    stmt = p.get("statement", "")
    question = p.get("question", "")
    option = p.get("option", "")
    step = p.get("step", "")
    hint = p.get("hint", "")

    scores = {}

    # 1. 内容相关性 (0-4): 回复是否与用户问题相关
    stmt_lower = stmt.lower()
    if len(stmt) < 10:
        scores["relevance"] = 0
    elif len(stmt) < 30:
        scores["relevance"] = 1
    elif len(stmt) < 80:
        scores["relevance"] = 2
    elif "python" in stmt_lower or "变量" in stmt or "loop" in stmt_lower or "循环" in stmt or "列表" in stmt or "类型" in stmt or "color" in stmt_lower or "数据" in stmt:
        scores["relevance"] = 4
    else:
        scores["relevance"] = 3

    # 2. 解释清晰度 (0-4): 是否用简单语言解释
    analogy_words = ["像", "比如", "例如", "就像", "好比", "相当于", "想象", "like", "example", "e.g."]
    has_analogy = any(w in stmt for w in analogy_words)
    if has_analogy:
        scores["clarity"] = 4 if len(stmt) > 50 else 3
    elif len(stmt) > 80:
        scores["clarity"] = 3
    elif len(stmt) > 30:
        scores["clarity"] = 2
    else:
        scores["clarity"] = 1

    # 3. 互动性 (0-4): 是否提出问题/选项保持对话
    interactive_elements = 0
    if question: interactive_elements += 1
    if option: interactive_elements += 1
    if hint: interactive_elements += 1
    if step: interactive_elements += 1
    scores["interactive"] = min(4, interactive_elements * 2) if interactive_elements > 0 else 0

    # 4. 教学结构化 (0-4): 是否有步骤/分层
    if step and len(stmt) > 50:
        scores["structure"] = 4
    elif question and len(stmt) > 50:
        scores["structure"] = 3
    elif len(stmt) > 80:
        scores["structure"] = 2
    else:
        scores["structure"] = 1

    # 5. 个性化 (0-4): 是否引用用户之前说的内容
    if prev_stmt and len(prev_stmt) > 20 and len(stmt) > 30:
        # check if coach acknowledges previous turn
        ack_words = ["对", "是的", "没错", "好", "明白", "理解", "正确", "你说得对", "great", "yes", "right", "correct"]
        if any(w in stmt[:100] for w in ack_words):
            scores["personalization"] = 4
        else:
            scores["personalization"] = 2
    else:
        scores["personalization"] = 2

    # 6. 鼓励性 (0-4): 是否正向激励
    encourage_words = ["好", "棒", "不错", "太", "厉害", "进步", "继续", "试试", "可以", "great", "good", "well", "nice", "excellent", "awesome"]
    count = sum(1 for w in encourage_words if w in stmt[:150])
    if count >= 3:
        scores["encouragement"] = 4
    elif count >= 1:
        scores["encouragement"] = 3
    else:
        scores["encouragement"] = 1

    scores["total"] = sum(scores.values())
    return scores


def run_conversation(label: str, combo: dict) -> list[dict]:
    """运行一组 10 轮连续对话."""
    apply_combo(combo)
    agent = CoachAgent(session_id=f"quality-{label}")
    results = []
    prev_stmt = ""

    for i, msg in enumerate(LEARNING_SCRIPT, 1):
        t0 = time.time()
        try:
            r = agent.act(msg)
            dt = time.time() - t0
            quality = score_quality(r, i, prev_stmt)
            prev_stmt = r.get("payload", {}).get("statement", "")

            result = {
                "turn": i,
                "label": label,
                "user_msg": msg[:80],
                "ok": True,
                "action_type": r.get("action_type", "?"),
                "ttm_stage": r.get("ttm_stage"),
                "llm": r.get("llm_generated", False),
                "stmt_preview": r.get("payload", {}).get("statement", "")[:150],
                "question": r.get("payload", {}).get("question", "")[:80],
                "elapsed_s": round(dt, 2),
                "tokens": r.get("llm_tokens", 0),
                "quality": quality,
                "total_score": quality["total"],
            }
        except Exception as e:
            result = {
                "turn": i, "label": label, "user_msg": msg[:80],
                "ok": False, "error": f"{type(e).__name__}: {e}",
                "total_score": 0,
            }

        results.append(result)

        # Log detailed turn info
        log(f"\n  [{label}] Turn {i}")
        log(f"    USER: {msg[:100]}")
        if result["ok"]:
            log(f"    COACH: at={result['action_type']} llm={result['llm']} ttm={result['ttm_stage']} score={result['total_score']}/24 {result['elapsed_s']}s")
            log(f"    REPLY: {result['stmt_preview']}...")
            if result["question"]:
                log(f"    QUESTION: {result['question']}...")
            log(f"    QUALITY: rel={quality['relevance']} cla={quality['clarity']} int={quality['interactive']} str={quality['structure']} per={quality['personalization']} enc={quality['encouragement']} → {quality['total']}/24")
        else:
            log(f"    ERROR: {result['error']}")

    return results


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        original = f.read()

    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"# ULTIMATE Quality Test — {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"# 12 combos × 10 turns = 120 conversations\n\n")

    log("=" * 70)
    log("ULTIMATE QUALITY TEST: 12 Configs × 10 Continuous Turns")
    log(f"Date: {datetime.now(timezone.utc).isoformat()}")
    log("=" * 70)

    all_results = []
    combo_summaries = {}

    for label, combo in CONFIG_COMBOS:
        log(f"\n{'='*60}")
        log(f"COMBO: {label}")
        log(f"  Config: {combo}")
        log(f"{'='*60}")

        results = run_conversation(label, combo)
        all_results.extend(results)

        # Summarize this combo
        ok_count = sum(1 for r in results if r.get("ok"))
        avg_score = sum(r.get("total_score", 0) for r in results if r.get("ok")) / max(ok_count, 1)
        llm_count = sum(1 for r in results if r.get("llm"))
        actions = [r.get("action_type", "?") for r in results if r.get("ok")]
        ttms = [r.get("ttm_stage") for r in results if r.get("ok") and r.get("ttm_stage")]

        combo_summaries[label] = {
            "config": combo,
            "turns": len(results),
            "ok": ok_count,
            "llm_rate": f"{llm_count}/{ok_count}",
            "avg_quality": round(avg_score, 1),
            "action_types": dict((a, actions.count(a)) for a in set(actions)),
            "ttm_stages": dict((t, ttms.count(t)) for t in set(ttms)) if ttms else {},
            "total_tokens": sum(r.get("tokens", 0) for r in results),
            "total_time_s": round(sum(r.get("elapsed_s", 0) for r in results if r.get("ok")), 1),
        }

        log(f"\n  >> COMBO {label} SUMMARY: {ok_count}/10 ok, avg quality={avg_score:.1f}/24, llm={llm_count}/10, actions={combo_summaries[label]['action_types']}")

    # 恢复原始配置
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(original)

    # ══════════════════════════════════════════════════
    # 终极汇总
    # ══════════════════════════════════════════════════
    total = len(all_results)
    ok = sum(1 for r in all_results if r.get("ok"))
    crashed = total - ok
    avg_all = sum(r.get("total_score", 0) for r in all_results if r.get("ok")) / max(ok, 1)

    log("\n" + "=" * 70)
    log("ULTIMATE QUALITY REPORT")
    log("=" * 70)
    log(f"  Configs tested:      {len(CONFIG_COMBOS)}")
    log(f"  Total turns:         {total}")
    log(f"  Passed:              {ok}/{total}")
    log(f"  Crashed:             {crashed}")
    log(f"  Overall avg quality: {avg_all:.1f}/24")

    # Ranking by quality
    log("\n--- Quality Ranking (avg score /24) ---")
    ranked = sorted(combo_summaries.items(), key=lambda x: x[1]["avg_quality"], reverse=True)
    for i, (name, summary) in enumerate(ranked, 1):
        bar = "█" * int(summary["avg_quality"])
        log(f"  {i:2d}. {name:20s} {summary['avg_quality']:4.1f}/24 {bar} | llm={summary['llm_rate']} | {summary['action_types']}")

    # Dimension averages across all
    dim_avgs = defaultdict(list)
    for r in all_results:
        if r.get("ok") and "quality" in r:
            for dim, score in r["quality"].items():
                if dim != "total":
                    dim_avgs[dim].append(score)
    log("\n--- Dimension Averages (0-4) ---")
    for dim, scores in dim_avgs.items():
        log(f"  {dim:20s}: {sum(scores)/len(scores):.2f}")

    # LLM vs Rule comparison
    llm_results = [r for r in all_results if r.get("llm") and r.get("ok")]
    rule_results = [r for r in all_results if not r.get("llm") and r.get("ok")]
    if llm_results:
        llm_avg = sum(r["total_score"] for r in llm_results) / len(llm_results)
        log(f"\n  LLM avg quality:  {llm_avg:.1f}/24 ({len(llm_results)} turns)")
    if rule_results:
        rule_avg = sum(r["total_score"] for r in rule_results) / len(rule_results)
        log(f"  Rule avg quality: {rule_avg:.1f}/24 ({len(rule_results)} turns)")

    # TTM impact
    ttm_on = [r for r in all_results if r.get("ok") and r.get("ttm_stage")]
    ttm_off = [r for r in all_results if r.get("ok") and r.get("ttm_stage") is None]
    if ttm_on:
        log(f"\n  TTM ON avg quality:  {sum(r['total_score'] for r in ttm_on)/len(ttm_on):.1f}/24")
    if ttm_off:
        log(f"  TTM OFF avg quality: {sum(r['total_score'] for r in ttm_off)/len(ttm_off):.1f}/24")

    # Write JSON report
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now(timezone.utc).isoformat(),
            "configs_tested": len(CONFIG_COMBOS),
            "total_turns": total,
            "passed": ok,
            "crashed": crashed,
            "overall_avg_quality": round(avg_all, 1),
            "ranking": [(name, s["avg_quality"], s["llm_rate"], s["total_tokens"])
                        for name, s in ranked],
            "dimension_averages": {dim: round(sum(scores)/len(scores), 2)
                                   for dim, scores in dim_avgs.items()},
            "per_combo": combo_summaries,
        }, f, ensure_ascii=False, indent=2)

    log(f"\nReport JSON: {REPORT}")


if __name__ == "__main__":
    main()
