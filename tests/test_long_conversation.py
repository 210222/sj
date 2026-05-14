"""长时间连续多轮对话模拟 — TTM/SDT/Flow/Diagnostic 全开.

3 位用户 × 18-20 轮自然对话，验证策略自动切换。
"""

import sys, time, json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.coach.agent import CoachAgent

LOG = Path(__file__).resolve().parent.parent / "reports" / "long_conversation_test.log"


def log(msg: str):
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def turn(agent, name, msg, turn_num):
    """一轮对话，记录完整状态."""
    t0 = time.time()
    r = agent.act(msg)
    dt = time.time() - t0

    p = r.get("payload", {})
    at = r.get("action_type", "?")
    llm = r.get("llm_generated", False)
    ttm = r.get("ttm_stage", "?")
    sdt = r.get("sdt_profile", {})
    flow = r.get("flow_channel", "?")
    diag = r.get("diagnostic_probe")
    diag_res = r.get("diagnostic_result")
    tokens = r.get("llm_tokens", 0)

    # User message
    log(f"")
    log(f"--- Turn {turn_num} ---")
    log(f"USER [{name}]: {msg}")

    # Coach response
    log(f"COACH: at={at} llm={llm} ttm={ttm} flow={flow} tokens={tokens} {dt:.1f}s")
    stmt = p.get("statement", "")
    if stmt:
        log(f"  >> {stmt}")
    q = p.get("question", "")
    if q:
        log(f"  ?? {q}")
    opt = p.get("option", "")
    if opt:
        log(f"  [] {opt if isinstance(opt, str) else opt}")

    # Diagnostic
    if diag:
        log(f"  DIAG_PROBE: skill={diag.get('skill','')} q={diag.get('question','')[:80]}")
    if diag_res:
        log(f"  DIAG_RESULT: evaluated={diag_res.get('evaluated')} correct={diag_res.get('correct')} mastery={diag_res.get('skill_mastery',0):.2f}")

    # SDT
    if sdt:
        log(f"  SDT: autonomy={sdt.get('autonomy',0):.2f} competence={sdt.get('competence',0):.2f} relatedness={sdt.get('relatedness',0):.2f}")

    return r


def user_a_python_beginner():
    """用户A: 零基础学 Python — 20 轮完整学习旅程."""
    log("")
    log("=" * 60)
    log("用户A: 小明 | 零基础 Python | TTM+SDT+Flow+Diagnostic 全开")
    log("=" * 60)

    a = CoachAgent(session_id="long-a")

    dialogs = [
        "你好，我完全没学过编程，想学 Python",
        "我是做行政的，每天处理很多 Excel，听说 Python 能自动化",
        "变量是什么？用最简单的语言解释",
        "所以 x = 5 就是把 5 放进一个叫 x 的盒子里？",
        "那我试试 print(x)，但是打了 x 和 y 两个值，结果只出来一个",
        "哦我懂了，要先 print(x) 再 print(y)，有先后顺序",
        "数据类型有哪些？我 Excel 里只见过数字和文字",
        "字符串就是用引号括起来的东西对吧，那数字 123 和字符串 '123' 有什么不同",
        "数字 123 可以加减，字符串 '123' 只能拼接？",
        "对，我想试试。怎么把字符串转成数字去计算",
        "int('123') + 456 得到 579！这有什么用在实际工作中",
        "我工作中有一列数字都是文本格式的，所以可以用 int() 转",
        "列表是什么？和 Excel 的列一样吗",
        "colors = ['red', 'blue', 'green'] 然后 colors[0] 就是 red？",
        "为什么从 0 开始不是从 1 开始",
        "有点奇怪但记住了。那 colors[-1] 就是最后一个？",
        "越来越有意思了。for 循环怎么用",
        "for color in colors: print(color) — 这样就会一个个打印出来？",
        "太神奇了！那如果我有一万个数据，也能用 for 循环吗",
        "我觉得今天学了好多：变量、数据类型、列表、for 循环。能帮我总结一下吗",
    ]

    for i, msg in enumerate(dialogs, 1):
        turn(a, "小明", msg, i)

    # Summary
    log(f"\n--- 小明学习总结 ---")
    de = a.diagnostic_engine
    summary = de.get_mastery_summary() if de else {}
    log(f"  Mastery: {summary.get('skills', {})}")
    log(f"  Total probes: {de.probe_count if de else 0}")


def user_b_stuck_learner():
    """用户B: 中级卡壳 — 18 轮突破."""
    log("")
    log("=" * 60)
    log("用户B: 小红 | Python 3月经验 卡装饰器 | TTM+SDT+Flow+Diagnostic")
    log("=" * 60)

    a = CoachAgent(session_id="long-b")

    dialogs = [
        "我学 Python 三个月了，函数和类都会写，但装饰器完全搞不懂",
        "对，我看到 @something 就觉得害怕，不知道它在干什么",
        "等等，你说装饰器就是一个接受函数返回函数的函数？",
        "所以装饰器本质上就是：新函数 = 装饰器(旧函数)？",
        "能给我看一个最简单的装饰器代码吗，从零开始写",
        "我照着写了一遍，确实有效。但是 def wrapper(*args, **kwargs) 里的 *args 是什么",
        "所以 *args 就是接收任意数量的位置参数？那 **kwargs 呢",
        "明白了！所以 wrapper 用 *args **kwargs 是为了让装饰器能装饰任何函数",
        "那带参数的装饰器呢？比如 @timer(unit='ms')",
        "我试着写了一下，但是报 NameError 说变量没定义",
        "哦，原来是没有在 wrapper 里面用 nonlocal 声明变量",
        "现在真的通了。我想写一个能重试的装饰器，函数失败自动重试 3 次",
        "写好了！但我想再加一个功能：重试之间等待的时间递增",
        "完美！我现在对装饰器有真正的理解了",
        "那我之前写的那些重复代码，是不是都可以用装饰器重构",
        "太好了，我现在回去重构我的项目。对了，还有什么 Python 高级特性值得学",
        "生成器和迭代器听起来有意思，和列表有什么区别",
        "所以生成器是懒加载的，不会一次性把所有数据加载到内存？",
    ]

    for i, msg in enumerate(dialogs, 1):
        turn(a, "小红", msg, i)


def user_c_burnout_recovery():
    """用户C: 倦怠恢复 — 18 轮重新出发."""
    log("")
    log("=" * 60)
    log("用户C: 小刚 | 6月编程 倦怠期 | TTM+SDT+Flow+Diagnostic")
    log("=" * 60)

    a = CoachAgent(session_id="long-c")

    dialogs = [
        "最近完全不想写代码，打开电脑就坐在那发呆",
        "可能是刷了太多算法题，感觉永远不会变聪明",
        "你说的对，我当时学编程是因为想自己做游戏",
        "小时候玩仙剑奇侠传，一直想自己做一款 RPG",
        "但大家都说做游戏又累又没钱，不如做后端",
        "你说得对，我应该做自己感兴趣的事情。pygame 怎么开始",
        "好，我先装 pygame。pip install pygame 对吧",
        "装好了！现在怎么创建一个窗口",
        "黑窗口出来了！虽然什么都没有但好激动",
        "接下来我该做什么？画一个方块吗",
        "screen.fill((255,0,0)) 然后 update — 窗口变红了！",
        "现在怎么让这个方块动起来",
        "我加了键盘控制，方向键能移动方块了，但是移得飞快",
        "clock.tick(60) — 加了这个就好了！移动速度正常了",
        "接下来我想加一个目标点，方块走到目标点就算过关",
        "我做完了第一关！虽然很简单但真的完成了",
        "今天从不想写代码到做了个小游戏，感觉很有成就感",
        "我决定每天花半小时做这个小游戏。还有什么建议让我坚持下去",
    ]

    for i, msg in enumerate(dialogs, 1):
        turn(a, "小刚", msg, i)


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"# Long Conversation Test — {datetime.now(timezone.utc).isoformat()}\n")
        f.write("# TTM+SDT+Flow+Diagnostic ALL ENABLED\n\n")

    t0 = time.time()
    user_a_python_beginner()
    user_b_stuck_learner()
    user_c_burnout_recovery()
    total = time.time() - t0

    log(f"\n{'='*60}")
    log(f"TOTAL: 56 turns, {total:.0f}s ({total/56:.1f}s avg)")
    log(f"Full log: {LOG}")

if __name__ == "__main__":
    main()
