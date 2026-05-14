"""模拟真实用户进行 AI 教学对话测试 — 输出到 reports/real_user_test.log

模拟 3 个用户画像:
- 用户A: 零基础学 Python 的初学者
- 用户B: 有基础但卡在某个概念上的进阶学习者
- 用户C: 学习动力下降、需要激励的倦怠期学生
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.coach.agent import CoachAgent

LOG_PATH = Path(__file__).resolve().parent.parent / "reports" / "real_user_test.log"


def log(msg: str):
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def user_says(name: str, text: str):
    """用户发言."""
    log(f"")
    log(f"👤 {name}: {text}")


def coach_says(name: str, result: dict):
    """教练回复."""
    p = result.get("payload", {})
    at = result.get("action_type", "?")
    llm = "🤖" if result.get("llm_generated") else "📋规则"
    tokens = result.get("llm_tokens", 0)

    stmt = p.get("statement", "")
    question = p.get("question", "")
    step = p.get("step", "")
    option = p.get("option", "")
    hint = p.get("hint", "")

    log(f"🎓 Coach [{at}] {llm} {tokens}t | {result.get('elapsed_s',0):.1f}s")
    if stmt:
        log(f"   💬 {stmt}")
    if question:
        log(f"   ❓ {question}")
    if step:
        log(f"   📋 步骤: {step}")
    if option:
        opt_str = option if isinstance(option, str) else ", ".join(option) if isinstance(option, list) else str(option)
        log(f"   🔘 选项: {opt_str}")
    if hint:
        log(f"   💡 提示: {hint}")


def talk(agent: CoachAgent, name: str, message: str) -> dict:
    """一轮对话."""
    user_says(name, message)
    start = time.time()
    r = agent.act(message)
    r["elapsed_s"] = round(time.time() - start, 1)
    coach_says(name, r)
    return r


# ══════════════════════════════════════════════════

def simulate_user_a():
    """用户A: 零基础学 Python — 10 轮对话."""
    log("")
    log("=" * 70)
    log("用户A: 小明 — 零基础, 想学 Python 找工作")
    log("=" * 70)

    a = CoachAgent(session_id="user-a-xiaoming")
    results = []

    # Turn 1: 开启学习
    r = talk(a, "小明", "你好，我想学 Python，但是完全没基础，从哪开始")

    # Turn 2: 回复教练的引导问题
    q = r.get("payload", {}).get("question", "")
    if "经验" in q or "学过" in q or "编程" in q:
        r = talk(a, "小明", "完全没接触过编程，我是做行政的，想转行")
    else:
        r = talk(a, "小明", "我连变量是什么都不知道，完全零基础")

    # Turn 3: 学习变量
    r = talk(a, "小明", "变量是什么？给我解释一下")

    # Turn 4: 确认理解
    r = talk(a, "小明", "所以变量就像一个贴了标签的盒子，里面可以放东西对吧")

    # Turn 5: 追问
    r = talk(a, "小明", "那 Python 里的变量和数学里的 x y 有什么区别")

    # Turn 6: 遇到困难
    r = talk(a, "小明", "我试了一下 print(x)，但是报错了说没定义，什么意思")

    # Turn 7: 理解错误
    r = talk(a, "小明", "哦我明白了！要先赋值才能用。那我可以给同一个变量赋不同类型的值吗")

    # Turn 8: 学新概念
    r = talk(a, "小明", "差不多了，接下来学什么？数据类型吗")

    # Turn 9: 请求练习
    r = talk(a, "小明", "可以给我一个练习来巩固吗，不要太难")

    # Turn 10: 完成反馈
    r = talk(a, "小明", "我做完了，字符串和数字都试了，感觉有点懂了")
    results.append(r)

    return results


def simulate_user_b():
    """用户B: 有基础卡壳 — 8 轮对话."""
    log("")
    log("=" * 70)
    log("用户B: 小红 — 学 Python 3 个月, 卡在装饰器")
    log("=" * 70)

    a = CoachAgent(session_id="user-b-xiaohong")
    results = []

    r = talk(a, "小红", "我学 Python 三个月了，函数和类都懂，但装饰器看了三次还是不明白")
    r = talk(a, "小红", "对，我看到那个 @符号 就觉得怕，不知道它到底干了什么")
    r = talk(a, "小红", "你刚才说装饰器就是一个接受函数返回函数的函数，能用代码演示一下吗")
    r = talk(a, "小红", "我跟着写了一遍，好像有点理解了。但是带参数的装饰器又是什么鬼")
    r = talk(a, "小红", "等等，你说 functools.wraps？我从来没用过")
    r = talk(a, "小红", "所以装饰器本质上就是语法糖？底层其实就是在做 logger = add_logging(my_function) 这件事？")
    r = talk(a, "小红", "我好像真的懂了！之前三个月没看懂的东西，现在通了。给我一个练习巩固一下")
    r = talk(a, "小红", "写完了！写了一个计时装饰器，可以统计函数运行时间。还有什么高级用法可以深入")

    results.append(r)
    return results


def simulate_user_c():
    """用户C: 倦怠期 — 6 轮对话."""
    log("")
    log("=" * 70)
    log("用户C: 小刚 — 学编程 6 个月, 最近没动力")
    log("=" * 70)

    a = CoachAgent(session_id="user-c-xiaogang")
    results = []

    r = talk(a, "小刚", "最近完全不想写代码，打开电脑就发呆，怎么办")
    r = talk(a, "小刚", "可能是因为刷了太多 LeetCode，感觉自己好笨")
    r = talk(a, "小刚", "你说的换项目方向有意思，我之前一直想做游戏，但大家都说做游戏没钱途")
    r = talk(a, "小刚", "pygame 好学吗？我是不是该先做个俄罗斯方块之类的")
    r = talk(a, "小刚", "好，我决定了，这周就做一个俄罗斯方块。你能告诉我要分几步吗")
    r = talk(a, "小刚", "第一步画窗口我已经搞定了！虽然只是一个黑窗口但很有成就感")

    results.append(r)
    return results


# ══════════════════════════════════════════════════

def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"# 真实用户模拟测试 — {datetime.now(timezone.utc).isoformat()}\n")
        f.write("# 模型: DeepSeek V4 Flash\n\n")

    log("╔══════════════════════════════════════════════╗")
    log("║   Coherence AI 教练 — 真实用户模拟测试       ║")
    log("║   3 位虚拟用户 × 多轮自然对话                ║")
    log("╚══════════════════════════════════════════════╝")

    t0 = time.time()

    results_a = simulate_user_a()
    results_b = simulate_user_b()
    results_c = simulate_user_c()

    total_time = time.time() - t0
    all_results = results_a + results_b + results_c

    # 汇总
    log("")
    log("=" * 70)
    log("模拟测试汇总")
    log("=" * 70)
    log(f"  用户数: 3")
    log(f"  总对话轮次: {len(all_results)}")
    log(f"  总耗时: {total_time:.0f}s")
    log(f"  平均每轮: {total_time/len(all_results):.1f}s")

    llm_count = sum(1 for r in all_results if r.get("llm_generated"))
    log(f"  LLM 生成率: {llm_count}/{len(all_results)} ({100*llm_count/len(all_results):.0f}%)")

    total_tokens = sum(r.get("llm_tokens", 0) for r in all_results)
    log(f"  总 tokens: {total_tokens}")

    action_counts = {}
    for r in all_results:
        at = r.get("action_type", "?")
        action_counts[at] = action_counts.get(at, 0) + 1
    log(f"  Action 分布: {action_counts}")

    blocked = sum(1 for r in all_results if not r.get("safety_allowed", True))
    log(f"  安全阻断次数: {blocked}")

    log(f"\n完整日志: {LOG_PATH}")

    # 评估
    log("")
    log("─" * 50)
    log("教学质量评估")
    log("─" * 50)

    # 检查用户A 是否成功引导零基础学习
    a_actions = [r.get("action_type") for r in results_a]
    log(f"  用户A(零基础): 10轮, 动作序列: {a_actions}")
    has_scaffold = any(a == "scaffold" for a in a_actions)
    log(f"    脚手架引导: {'✅' if has_scaffold else '❌ 未触发'}")

    # 检查用户B 是否解决了卡壳问题
    b_actions = [r.get("action_type") for r in results_b]
    log(f"  用户B(卡壳): 8轮, 动作序列: {b_actions}")

    # 检查用户C 是否被激励
    c_actions = [r.get("action_type") for r in results_c]
    log(f"  用户C(倦怠): 6轮, 动作序列: {c_actions}")


if __name__ == "__main__":
    main()
