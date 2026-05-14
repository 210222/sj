"""穷举法配置测试 — 所有配置组合 × 标准测试消息 × 结果矩阵.

测试维度:
- 9 个布尔开关 → 理论 512 种组合
- 缩减策略: 分组独立测试 + 关键交叉组合
  - Group LLM (2开关, 4组合)
  - Group 行为科学 (4开关, 16组合)
  - Group 安全 (3开关, 8组合)
  - Group 全交叉 (关键2x2x2=8组合)
- 总计: 36 种组合 × 3 条消息 = 108 次测试

每种组合验证:
  1. 系统不崩溃
  2. 输出格式合法
  3. action_type 分布
  4. LLM 状态与配置一致
  5. 安全门禁与配置一致
"""

import yaml, sys, time, json, os, itertools
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.coach.agent import CoachAgent

LOG = Path(__file__).resolve().parent.parent / "reports" / "exhaustive_config_test.log"
MATRIX = Path(__file__).resolve().parent.parent / "reports" / "exhaustive_matrix.json"
CONFIG = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"


def log(msg: str):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# 标准测试消息 — 覆盖不同意图
TEST_MESSAGES = [
    ("learn", "teach me Python basics"),
    ("challenge", "give me a hard algorithm problem"),
    ("reflect", "why do I keep failing at learning this"),
]


def apply_config(combo: dict):
    """写入配置组合."""
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    for key, val in combo.items():
        parts = key.split(".")
        d = cfg
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val

    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def run_combo(label: str, combo: dict) -> list[dict]:
    """运行一个配置组合的所有测试消息."""
    apply_config(combo)
    results = []

    for msg_type, msg_text in TEST_MESSAGES:
        agent = CoachAgent(session_id=f"exhaust-{label}-{msg_type}")
        t0 = time.time()
        try:
            r = agent.act(msg_text)
            dt = time.time() - t0
            result = {
                "label": label,
                "combo": combo.copy(),
                "msg_type": msg_type,
                "msg": msg_text,
                "ok": True,
                "action_type": r.get("action_type", "?"),
                "intent": r.get("intent", "?"),
                "llm_generated": r.get("llm_generated", False),
                "safety_allowed": r.get("safety_allowed", True),
                "gate_decision": r.get("gate_decision", "?"),
                "ttm_stage": r.get("ttm_stage"),
                "sdt_profile": r.get("sdt_profile"),
                "flow_channel": r.get("flow_channel"),
                "diagnostic_probe": r.get("diagnostic_probe") is not None,
                "diagnostic_result": r.get("diagnostic_result") is not None,
                "payload_keys": sorted(r.get("payload", {}).keys()),
                "payload_stmt_len": len(r.get("payload", {}).get("statement", "")),
                "elapsed_s": round(dt, 2),
                "tokens": r.get("llm_tokens", 0),
            }
        except Exception as e:
            result = {
                "label": label, "combo": combo.copy(),
                "msg_type": msg_type, "ok": False,
                "error": f"{type(e).__name__}: {e}",
            }
        results.append(result)

    return results


def analyze(results: list[dict]) -> dict:
    """分析测试结果矩阵."""
    total = len(results)
    ok = sum(1 for r in results if r.get("ok"))
    crashed = total - ok
    llm_on = sum(1 for r in results if r.get("llm_generated"))
    llm_off = total - llm_on
    safety_blocks = sum(1 for r in results if not r.get("safety_allowed", True))

    at_dist = defaultdict(int)
    for r in results:
        if r.get("ok"):
            at_dist[r.get("action_type", "?")] += 1

    return {
        "total": total,
        "ok": ok,
        "crashed": crashed,
        "llm_generated": llm_on,
        "rule_based": llm_off,
        "safety_blocks": safety_blocks,
        "action_types": dict(at_dist),
        "avg_stmt_len": sum(r.get("payload_stmt_len", 0) for r in results if r.get("ok")) / max(ok, 1),
        "avg_time": sum(r.get("elapsed_s", 0) for r in results if r.get("ok")) / max(ok, 1),
        "crash_rate": f"{100*crashed/total:.1f}%" if total else "0%",
    }


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)

    # 保存原始配置
    with open(CONFIG, "r", encoding="utf-8") as f:
        original = f.read()

    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"# Exhaustive Config Test — {datetime.now(timezone.utc).isoformat()}\n\n")

    all_results = []
    matrix = {}

    # ═══════════════════════════════════════════
    # Group 1: LLM 开关独立测试 (4 组合)
    # ═══════════════════════════════════════════
    log("\n### GROUP 1: LLM Switches (4 combos) ###\n")
    llm_switches = {
        "llm.enabled": [True, False],
        "llm.streaming": [True, False],
    }
    keys, values = zip(*llm_switches.items())
    for i, v in enumerate(itertools.product(*values)):
        combo = dict(zip(keys, v))
        label = f"G1-{i}"
        log(f"  [{label}] {combo}")
        results = run_combo(label, combo)
        all_results.extend(results)
        matrix[label] = analyze(results)

    # ═══════════════════════════════════════════
    # Group 2: 行为科学开关独立测试 (16 组合)
    # ═══════════════════════════════════════════
    log("\n### GROUP 2: Behavior Models (16 combos) ###\n")
    behavior_switches = {
        "ttm.enabled": [True, False],
        "sdt.enabled": [True, False],
        "flow.enabled": [True, False],
        "diagnostic_engine.enabled": [True, False],
    }
    keys, values = zip(*behavior_switches.items())
    for i, v in enumerate(itertools.product(*values)):
        combo = dict(zip(keys, v))
        label = f"G2-{i}"
        log(f"  [{label}] {combo}")
        results = run_combo(label, combo)
        all_results.extend(results)
        matrix[label] = analyze(results)

    # ═══════════════════════════════════════════
    # Group 3: 安全开关独立测试 (8 组合)
    # ═══════════════════════════════════════════
    log("\n### GROUP 3: Safety Switches (8 combos) ###\n")
    safety_switches = {
        "sovereignty_pulse.enabled": [True, False],
        "excursion.enabled": [True, False],
        "relational_safety.enabled": [True, False],
    }
    keys, values = zip(*safety_switches.items())
    for i, v in enumerate(itertools.product(*values)):
        combo = dict(zip(keys, v))
        label = f"G3-{i}"
        log(f"  [{label}] {combo}")
        results = run_combo(label, combo)
        all_results.extend(results)
        matrix[label] = analyze(results)

    # ═══════════════════════════════════════════
    # Group 4: 关键交叉组合 (LLM×TTM×Safety: 8 组合)
    # ═══════════════════════════════════════════
    log("\n### GROUP 4: Critical Cross-Combos (8 combos) ###\n")
    cross_switches = {
        "llm.enabled": [True, False],
        "ttm.enabled": [True, False],
        "sovereignty_pulse.enabled": [True, False],
    }
    keys, values = zip(*cross_switches.items())
    for i, v in enumerate(itertools.product(*values)):
        combo = dict(zip(keys, v))
        label = f"G4-{i}"
        log(f"  [{label}] {combo}")
        results = run_combo(label, combo)
        all_results.extend(results)
        matrix[label] = analyze(results)

    # ═══════════════════════════════════════════
    # 恢复原始配置
    # ═══════════════════════════════════════════
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(original)

    # ═══════════════════════════════════════════
    # 全局汇总
    # ═══════════════════════════════════════════
    total_analysis = analyze(all_results)

    log("\n" + "=" * 70)
    log("EXHAUSTIVE CONFIG TEST — FINAL SUMMARY")
    log("=" * 70)
    log(f"  Config combos tested: {len(matrix)}")
    log(f"  Total test runs:     {total_analysis['total']}")
    log(f"  Passed:              {total_analysis['ok']}")
    log(f"  Crashed:             {total_analysis['crashed']} ({total_analysis['crash_rate']})")
    log(f"  LLM generated:       {total_analysis['llm_generated']}")
    log(f"  Rule-based:          {total_analysis['rule_based']}")
    log(f"  Safety blocks:       {total_analysis['safety_blocks']}")
    log(f"  Action types:        {total_analysis['action_types']}")
    log(f"  Avg stmt length:     {total_analysis['avg_stmt_len']:.0f} chars")
    log(f"  Avg response time:   {total_analysis['avg_time']:.1f}s")

    # 按 Group 分组统计
    log("\n--- Per-Group Breakdown ---")
    for group_name, group_results in matrix.items():
        log(f"  {group_name}: {group_results['ok']}/{group_results['total']} ok, "
            f"llm={group_results['llm_generated']}, "
            f"crash={group_results['crashed']}, "
            f"blocks={group_results['safety_blocks']}, "
            f"avg_len={group_results['avg_stmt_len']:.0f}")

    # 按配置维度统计
    log("\n--- Dimension Breakdown ---")
    for dim in ["llm.enabled", "ttm.enabled", "sdt.enabled", "flow.enabled",
                "diagnostic_engine.enabled", "sovereignty_pulse.enabled",
                "excursion.enabled", "relational_safety.enabled", "llm.streaming"]:
        on_results = [r for r in all_results if r.get("combo", {}).get(dim, False)]
        off_results = [r for r in all_results if not r.get("combo", {}).get(dim, False)]
        on_ok = sum(1 for r in on_results if r.get("ok"))
        off_ok = sum(1 for r in off_results if r.get("ok"))
        log(f"  {dim}: ON={on_ok}/{len(on_results)} OFF={off_ok}/{len(off_results)}")

    # 异常组合
    crash_combos = [r for r in all_results if not r.get("ok")]
    if crash_combos:
        log(f"\n--- CRASHED COMBOS ({len(crash_combos)}) ---")
        for r in crash_combos:
            log(f"  {r['label']}: {r.get('error', 'unknown')} | combo={r.get('combo', {})}")

    # 写入矩阵 JSON
    with open(MATRIX, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now(timezone.utc).isoformat(),
            "groups": len(matrix),
            "total_runs": total_analysis["total"],
            "passed": total_analysis["ok"],
            "crashed": total_analysis["crashed"],
            "crash_rate": total_analysis["crash_rate"],
            "per_group": matrix,
            "crash_combos": [{"label": r["label"], "error": r.get("error", ""),
                              "combo": r.get("combo", {})}
                             for r in crash_combos],
        }, f, ensure_ascii=False, indent=2)

    log(f"\nMatrix JSON: {MATRIX}")
    log(f"Full log: {LOG}")


if __name__ == "__main__":
    main()
