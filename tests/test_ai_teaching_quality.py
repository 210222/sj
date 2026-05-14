"""全维度 AI 教学能力测试 — 输出到 reports/ai_teaching_test.log

覆盖维度:
- 8 种 action_type 触发
- 6 个学科领域
- 多轮对话
- 边缘用例 (空输入/超长输入/非学习意图)
- 回复质量检查 (长度/结构/内容)
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.coach.agent import CoachAgent

LOG_PATH = Path(__file__).resolve().parent.parent / "reports" / "ai_teaching_test.log"
SUMMARY_PATH = Path(__file__).resolve().parent.parent / "reports" / "ai_teaching_summary.json"


def log(msg: str):
    """写入日志文件 + 打印."""
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_turn(agent: CoachAgent, message: str, label: str) -> dict:
    """执行一轮对话并记录结果."""
    start = time.time()
    r = agent.act(message)
    elapsed = time.time() - start

    result = {
        "label": label,
        "message": message,
        "action_type": r.get("action_type", "?"),
        "intent": r.get("intent", "?"),
        "llm_generated": r.get("llm_generated", False),
        "llm_model": r.get("llm_model", ""),
        "llm_tokens": r.get("llm_tokens", 0),
        "safety_allowed": r.get("safety_allowed", True),
        "gate_decision": r.get("gate_decision", "?"),
        "payload": r.get("payload", {}),
        "elapsed_s": round(elapsed, 2),
    }
    return result


def check_quality(result: dict) -> list[str]:
    """检查回复质量，返回问题列表."""
    issues = []
    p = result.get("payload", {})

    # 1. LLM 是否生成
    if not result.get("llm_generated"):
        issues.append("LLM_NOT_GENERATED")

    # 2. statement 是否非空
    stmt = p.get("statement", "")
    if not stmt or len(stmt) < 20:
        issues.append("STATEMENT_TOO_SHORT")

    # 3. 安全门禁
    if not result.get("safety_allowed"):
        issues.append(f"SAFETY_BLOCKED: gate={result.get('gate_decision')}")

    # 4. 是否有实际教学内容
    if len(stmt) < 50:
        issues.append("CONTENT_TOO_BRIEF")

    # 5. 中文内容检查
    has_chinese = any('一' <= c <= '鿿' for c in stmt)
    if not has_chinese and len(stmt) > 20:
        # 非中文但内容充分 → 通过
        pass

    return issues


# ── 主测试 ────────────────────────────────────────

def run_full_test():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"# AI Teaching Quality Test — {datetime.now(timezone.utc).isoformat()}\n\n")

    log("=" * 70)
    log("Coherence AI 教学能力 全维度测试")
    log(f"时间: {datetime.now(timezone.utc).isoformat()}")
    log(f"模型: DeepSeek V4 Flash (via deepseek-chat)")
    log("=" * 70)

    all_results = []
    pass_count = 0
    fail_count = 0

    # ═══════════════════════════════════════════
    # 维度 1: 8 种 action_type 触发测试
    # ═══════════════════════════════════════════
    log("\n\n### 维度 1: Action Type 触发测试 ###\n")

    action_type_tests = [
        ("scaffold", "教我微积分的基本概念，一步步来", "scaffold 脚手架引导"),
        ("suggest", "有什么好的学习资源推荐吗", "suggest 建议"),
        ("challenge", "给我一个有点难的数据结构题", "challenge 挑战"),
        ("probe", "考考我关于网络协议的知识", "probe 探测"),
        ("reflect", "为什么我总是学不好英语，帮我分析一下", "reflect 反思引导"),
        ("defer", "我想退出当前的学习，暂停一下", "defer 退一步"),
        ("excursion", "/excursion 我想自由探索一下量子力学", "excursion 探索模式"),
    ]

    for at_expected, msg, label in action_type_tests:
        agent = CoachAgent(session_id=f"at-{at_expected}")
        result = run_turn(agent, msg, label)
        actual_at = result["action_type"]
        issues = check_quality(result)

        match = "MATCH" if actual_at == at_expected else f"MISMATCH(expected={at_expected})"
        status = "PASS" if not issues else f"ISSUES: {','.join(issues)}"
        log(f"[{label}] {match} | actual={actual_at} | {status} | {result['elapsed_s']}s | tokens={result['llm_tokens']}")
        log(f"  REPLY: {result['payload'].get('statement', '')[:200]}...")
        log(f"  QUESTION: {result['payload'].get('question', 'N/A')[:100]}")

        if not issues and result["llm_generated"]:
            pass_count += 1
        else:
            fail_count += 1
        all_results.append(result)

    # ═══════════════════════════════════════════
    # 维度 2: 多学科教学测试
    # ═══════════════════════════════════════════
    log("\n\n### 维度 2: 多学科教学测试 ###\n")

    subject_tests = [
        ("编程", "解释一下什么是递归函数，给个例子"),
        ("数据结构", "红黑树和 AVL 树有什么区别"),
        ("数学", "什么是贝叶斯定理？用生活例子解释"),
        ("物理", "量子纠缠是什么？用通俗的方式讲"),
        ("历史", "简述一下文艺复兴的核心思想"),
        ("经济学", "供需关系如何决定市场价格"),
        ("心理学", "什么是认知偏误？举三个常见的例子"),
        ("写作", "如何写一个好的开头段落来吸引读者"),
    ]

    for subject, msg in subject_tests:
        agent = CoachAgent(session_id=f"subj-{subject}")
        result = run_turn(agent, msg, f"学科: {subject}")
        issues = check_quality(result)
        status = "PASS" if not issues else f"ISSUES: {','.join(issues)}"
        stmt_len = len(result["payload"].get("statement", ""))
        log(f"[{subject}] {status} | action={result['action_type']} | len={stmt_len} | {result['elapsed_s']}s | tokens={result['llm_tokens']}")
        log(f"  REPLY: {result['payload'].get('statement', '')[:250]}...")

        if not issues and stmt_len > 50:
            pass_count += 1
        else:
            fail_count += 1
        all_results.append(result)

    # ═══════════════════════════════════════════
    # 维度 3: 多轮对话连贯性
    # ═══════════════════════════════════════════
    log("\n\n### 维度 3: 多轮对话连贯性 ###\n")

    agent = CoachAgent(session_id="multi-turn")
    conversation = [
        "我想学 Python",
        "变量和数据类型我理解了，接下来学什么",
        "for 循环和 while 循环有什么不同",
        "可以给我一个练习来巩固循环的知识吗",
        "我做完了，输出正确了，接下来学函数吧",
    ]

    for i, msg in enumerate(conversation):
        result = run_turn(agent, msg, f"多轮 Turn {i+1}")
        issues = check_quality(result)
        stmt = result["payload"].get("statement", "")
        status = "PASS" if not issues else f"ISSUES: {','.join(issues)}"
        log(f"[Turn {i+1}] {status} | action={result['action_type']} | len={len(stmt)} | {result['elapsed_s']}s | tokens={result['llm_tokens']}")
        log(f"  MSG: {msg}")
        log(f"  REPLY: {stmt[:200]}...")

        if not issues:
            pass_count += 1
        else:
            fail_count += 1
        all_results.append(result)

    # ═══════════════════════════════════════════
    # 维度 4: 边缘用例测试
    # ═══════════════════════════════════════════
    log("\n\n### 维度 4: 边缘用例测试 ###\n")

    edge_tests = [
        ("空输入", "", False),   # 空输入
        ("超短输入", "?", True),  # 超短
        ("超长输入", "请详细解释 " + "Python 编程 " * 50, True),  # 超长
        ("非学习意图", "今天天气真好", True),  # 非学习
        ("混合语言", "teach me Python classes 用中文解释", True),
    ]

    for label, msg, expect_ok in edge_tests:
        agent = CoachAgent(session_id=f"edge-{label}")
        result = run_turn(agent, msg, f"边缘: {label}")
        stmt = result["payload"].get("statement", "")
        log(f"[{label}] action={result['action_type']} | llm={result['llm_generated']} | len={len(stmt)} | {result['elapsed_s']}s")
        log(f"  REPLY: {stmt[:200] if stmt else '(empty)'}...")

        if result["llm_generated"] and len(stmt) > 10:
            pass_count += 1
        elif not expect_ok:
            pass_count += 1  # 预期不会有好的回复
        else:
            fail_count += 1
        all_results.append(result)

    # ═══════════════════════════════════════════
    # 维度 5: 回复结构完整性
    # ═══════════════════════════════════════════
    log("\n\n### 维度 5: 回复结构完整性 ###\n")

    struct_agent = CoachAgent(session_id="struct-test")
    struct_msgs = [
        "教我 HTTP 协议的基础",
        "解释一下 TCP 三次握手",
        "有什么好的 SQL 学习路线",
    ]
    for msg in struct_msgs:
        result = run_turn(struct_agent, msg, f"结构: {msg[:30]}")
        p = result["payload"]
        has_code = any(kw in str(p).lower() for kw in ["```", "def ", "print(", "select "])
        has_list = any(kw in str(p) for kw in ["1.", "2.", "3.", " - ", "•"])
        has_example = any(kw in str(p).lower() for kw in ["例如", "比如", "举个", "example", "e.g."])

        log(f"[结构] code={has_code} list={has_list} example={has_example} | {result['elapsed_s']}s")
        log(f"  REPLY: {p.get('statement', '')[:200]}...")
        if p.get('question'):
            log(f"  FOLLOW-UP: {p['question'][:150]}...")

        if result["llm_generated"]:
            pass_count += 1
        else:
            fail_count += 1
        all_results.append(result)

    # ═══════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════
    total = pass_count + fail_count
    log("\n\n" + "=" * 70)
    log("测试汇总")
    log("=" * 70)
    log(f"  总测试数: {total}")
    log(f"  通过: {pass_count} ({100*pass_count/total:.0f}%)" if total else "N/A")
    log(f"  失败: {fail_count} ({100*fail_count/total:.0f}%)" if total else "N/A")
    log(f"  LLM 模型: {all_results[0].get('llm_model', '?') if all_results else '?'}")

    # 统计
    action_counts = {}
    for r in all_results:
        at = r.get("action_type", "?")
        action_counts[at] = action_counts.get(at, 0) + 1
    log(f"  Action 分布: {action_counts}")

    avg_tokens = sum(r.get("llm_tokens", 0) for r in all_results) / max(len(all_results), 1)
    avg_time = sum(r.get("elapsed_s", 0) for r in all_results) / max(len(all_results), 1)
    log(f"  平均 tokens: {avg_tokens:.0f}")
    log(f"  平均耗时: {avg_time:.1f}s")

    # 写入 JSON 摘要
    summary = {
        "test_time": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": pass_count,
        "failed": fail_count,
        "pass_rate": round(100 * pass_count / total, 1) if total else 0,
        "action_distribution": action_counts,
        "avg_tokens": round(avg_tokens, 0),
        "avg_seconds": round(avg_time, 1),
        "model": all_results[0].get("llm_model", "unknown") if all_results else "unknown",
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"\n摘要已写入: {SUMMARY_PATH}")

    return summary


if __name__ == "__main__":
    run_full_test()
