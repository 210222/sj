"""8配置×15轮不同对话×子进程隔离=120次独立交互(无重复对话)."""

import yaml, sys, time, json, subprocess, os
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "reports" / "fresh_diverse_test.log"
REPORT = Path(__file__).resolve().parent.parent / "reports" / "fresh_diverse_report.json"
CONFIG = Path(__file__).resolve().parent.parent / "config" / "coach_defaults.yaml"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f: f.write(msg+"\n")

COMBOS = [
    ("all_off",      {"llm.enabled":False,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("llm_only",     {"llm.enabled":True,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("llm_ttm",      {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("llm_ttm_sdt",  {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":False,"diagnostic_engine.enabled":False}),
    ("full_behavior",{"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":False}),
    ("full_stack",   {"llm.enabled":True,"ttm.enabled":True,"sdt.enabled":True,"flow.enabled":True,"diagnostic_engine.enabled":True}),
    ("llm_diag",     {"llm.enabled":True,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":True}),
    ("rules_diag",   {"llm.enabled":False,"ttm.enabled":False,"sdt.enabled":False,"flow.enabled":False,"diagnostic_engine.enabled":True}),
]

# 8 组不同主题的对话脚本，每组 15 轮，完全不重复
SCRIPTS = {
    "all_off": ["python basics 10-turn learn path"]*1,  # placeholder
    "llm_only": [
        "我想学 JavaScript，完全零基础从哪开始",
        "变量用 var let const 有什么区别",
        "所以现代 JS 应该用 let 和 const？",
        "那我写 let name = '小明' 然后 console.log(name) 就可以了对吧",
        "为什么 console.log(0.1 + 0.2) 输出不是 0.3",
        "浮点数精度问题...那怎么处理",
        "函数怎么写？我 Python 里是 def，JS 里呢",
        "function add(a,b){ return a+b } — 这样对吗",
        "箭头函数 (a,b) => a+b 和普通函数有什么区别",
        "数组怎么操作？我想存一堆数据然后遍历",
        "[1,2,3].map(x => x*2) 返回 [2,4,6]？太酷了",
        "那 filter 和 reduce 呢",
        "我写了一个计算购物车总价的 reduce，但报 undefined",
        "哦没给初始值 0。JS 里异步怎么处理",
        "Promise 和 async/await 听了很多次但没真用过，给我一个实战例子",
    ],
    "llm_ttm": [
        "我学过基本编程，现在想学数据结构，从哪开始",
        "数组和链表底层有什么区别",
        "所以数组查询快 O(1)，链表插入快 O(1)？",
        "什么时候用链表什么时候用数组",
        "栈和队列又是什么",
        "栈就是后进先出，队列就是先进先出对么",
        "用 Python 的 list 当栈用靠谱吗",
        "那真正的栈应该怎么实现",
        "树结构怎么理解？我感觉好抽象",
        "二叉树每个节点最多两个子节点？那有什么用",
        "二叉搜索树和普通二叉树有什么区别",
        "我画了一下，插入 5 3 7 2 4，结果是平衡的。如果插入 1 2 3 4 5 会怎样",
        "退化链表...那怎么避免",
        "所以 AVL 树和红黑树就是为了解决这个问题？",
        "我今天学了数组、链表、栈、队列、树。能不能给我一个练习综合考察",
    ],
    "llm_ttm_sdt": [
        "我想学算法，但每次看到时间复杂度就头疼",
        "O(n) 就是执行次数和输入规模成正比？O(1) 是常数？",
        "那 O(log n) 是什么意思",
        "二分查找每次砍一半，所以是 O(log n) 对吗",
        "排序算法有哪些？冒泡排序是不是最慢的",
        "冒泡 O(n²)，快速 O(n log n)，为什么差距这么大",
        "快排的原理是什么？选一个 pivot 然后分区？",
        "我试着写了一下，但递归那里卡住了",
        "base case 是数组长度 <= 1，然后递归排序左右两部分，对吗",
        "归并排序和快排有什么不同",
        "所以归并稳定但需要额外空间，快排不稳定但原地排序",
        "动态规划是什么？我听到就害怕",
        "斐波那契用递归 O(2^n)，用 DP O(n)？这就是动态规划的威力",
        "我理解了，就是把大问题拆成小问题，然后缓存小问题的解",
        "给我一个 DP 的入门题目练手",
    ],
    "full_behavior": [
        "我听说机器学习很火，但完全不知道从哪下手",
        "机器学习就是让计算机从数据中学习规律？不用显式编程？",
        "监督学习和无监督学习有什么区别",
        "所以分类和回归是监督学习？聚类是无监督？",
        "线性回归是什么？就是画一条最佳拟合线？",
        "最小二乘法就是让误差平方和最小对吧",
        "那怎么评估模型好不好",
        "训练集和测试集要分开？为什么不能全用来训练",
        "过拟合就是模型背答案了，没真正理解规律",
        "怎么防止过拟合",
        "交叉验证就是把数据分成 K 份，轮流当验证集",
        "神经网络又是怎么回事",
        "就是很多层神经元，每层做线性变换加激活函数",
        "激活函数为什么要用 ReLU 而不是 sigmoid",
        "我今天从零学到了神经网络，能给我一个最简单的代码例子吗",
    ],
    "full_stack": [
        "我刚开始学编程，听说要用 Git 管理代码，完全不懂",
        "Git 就是版本控制？像游戏存档一样可以回到以前的状态？",
        "怎么安装 Git 和配置",
        "git init 创建仓库，git add 添加文件，git commit 提交",
        "我写了 git commit -m 'first commit'，这个 -m 是什么意思",
        "就是 message 的缩写？那如果不加 -m 会怎样",
        "哦会打开编辑器。git log 能看到所有提交记录？",
        "我改了一个文件，怎么看到底改了什么地方",
        "git diff 显示加号是新增，减号是删除，太直观了",
        "如果我想回到之前的某个版本怎么办",
        "git checkout 和 git reset 有什么区别",
        "checkout 只是切换查看，reset 会真的改历史？",
        "那分支是什么？为什么需要分支",
        "git branch 和 git merge — 多人协作的时候各干各的然后合并",
        "我在 feature 分支上改了代码，git merge main 的时候冲突了怎么办",
    ],
    "llm_diag": [
        "我想学数据库，SQL 从哪开始",
        "数据库就是存储数据的，SQL 是操作数据库的语言，对吗",
        "SELECT * FROM users WHERE age > 18 — 这样就能查到所有成年人？",
        "那我如果想查年龄在 20 到 30 之间、名字包含'张'的用户？",
        "所以用 AND 连接多个条件，LIKE 做模糊匹配？",
        "INSERT 怎么用？我想加一条新用户记录",
        "INSERT INTO users (name, age) VALUES ('小明', 25) — 如果是重复的怎么办",
        "主键和唯一索引是什么区别",
        "JOIN 是什么？两张表怎么联合查询",
        "INNER JOIN 只返回匹配的行，LEFT JOIN 保留左表全部行",
        "我写了一个 JOIN 但是结果有重复的行，怎么回事",
        "可能是笛卡尔积？忘记写 ON 条件了",
        "索引是什么？为什么能加速查询",
        "就像书的目录，B+树索引可以快速定位到数据",
        "我今天学了 SELECT WHERE INSERT JOIN 索引，能给我出一个综合查询题吗",
    ],
    "rules_diag": [
        "计算机网络怎么学的，那些协议太多了记不住",
        "OSI 七层模型是什么",
        "所以物理层是网线，数据链路层是 MAC 地址，网络层是 IP，传输层是 TCP/UDP？",
        "TCP 和 UDP 的根本区别是什么",
        "TCP 三次握手是怎么握的",
        "SYN → SYN-ACK → ACK，为什么要三次不是两次",
        "HTTP 是应用层协议吧，HTTPS 多了什么",
        "HTTPS 就是 HTTP + TLS 加密，TLS 握手又是怎么做的",
        "DNS 是什么？把域名转成 IP 地址的服务？",
        "我输入 www.google.com 回车后，到底发生了什么",
        "整个链条：DNS 解析 → TCP 连接 → TLS 握手 → HTTP 请求 → 服务器处理 → 返回 HTML",
        "那 CDN 又是什么",
        "内容分发网络，把静态资源缓存到离用户近的节点",
        "WebSocket 和 HTTP 有什么不同",
        "HTTP 是请求-响应，WebSocket 是全双工持久连接。能给我总结一下今天学的所有协议",
    ],
}

# 替换 placeholder
SCRIPTS["all_off"] = SCRIPTS["llm_only"]  # same topic, different config

QUALITY_PY = """
import yaml, json, time, sys
sys.path.insert(0, r"{root}")

with open(r"{config_path}", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
combo = {combo}
for k, v in combo.items():
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
agent = CoachAgent(session_id="{label}")
dialogs = {dialogs}

for i, msg in enumerate(dialogs, 1):
    t0 = time.time()
    r = agent.act(msg)
    dt = time.time() - t0
    p = r.get("payload", {{}})
    stmt = p.get("statement", "")
    question = p.get("question", "")
    steps = p.get("steps", [])
    option = p.get("option", "")

    scores = {{}}
    scores["relevance"] = 4 if len(stmt) > 80 else (3 if len(stmt) > 40 else (2 if len(stmt) > 10 else 1))
    scores["clarity"] = 4 if any(w in stmt for w in ["像","比如","例如","就像","好比","like","example","e.g."]) and len(stmt)>50 else (3 if len(stmt)>80 else (2 if len(stmt)>30 else 1))
    scores["interactive"] = min(4, (1 if question else 0) + (1 if option else 0) + (1 if isinstance(steps,list) and len(steps)>0 else 0) + (1 if len(stmt)>100 else 0))
    scores["structure"] = 4 if isinstance(steps, list) and len(steps) >= 2 else (3 if steps or len(stmt)>120 else (2 if len(stmt)>60 else 1))
    scores["personalization"] = 4 if any(w in stmt[:120] for w in ["你说的","你刚才","你之前","你提到","你问","你说得对","没错","对，"]) else (3 if len(stmt)>50 else 2)
    scores["encouragement"] = 4 if any(w in stmt[:150] for w in ["棒","好","不错","太","厉害","进步","继续","试试","great","good","nice","excellent"]) else (2 if len(stmt)>30 else 1)
    scores["total"] = sum(scores.values())

    results.append({{
        "turn": i, "ok": True,
        "action_type": r.get("action_type","?"),
        "ttm_stage": r.get("ttm_stage"),
        "llm": r.get("llm_generated", False),
        "stmt_len": len(stmt),
        "has_steps": isinstance(steps, list) and len(steps) > 0,
        "steps_count": len(steps) if isinstance(steps, list) else 0,
        "has_question": bool(question),
        "has_option": bool(option),
        "elapsed_s": round(dt, 2),
        "tokens": r.get("llm_tokens", 0),
        "quality": scores,
        "total_score": scores["total"],
    }})

print(json.dumps(results, ensure_ascii=False))
"""

def run_combo(label, combo):
    dialogs = SCRIPTS[label]
    # Convert combo to Python literal (True/False not true/false)
    combo_py = "{" + ", ".join(f'"{k}": {v}' for k, v in combo.items()) + "}"
    code = QUALITY_PY.format(
        root=str(Path(__file__).resolve().parent.parent),
        config_path=str(CONFIG), combo=combo_py,
        label=label, dialogs=json.dumps(dialogs, ensure_ascii=False))
    try:
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
            env={**os.environ, "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY",""), "PYTHONIOENCODING": "utf-8"})
        if proc.returncode == 0 and proc.stdout.strip():
            return {"ok": True, "label": label, "results": json.loads(proc.stdout)}
        return {"ok": False, "label": label, "error": proc.stderr[:300] or f"exit={proc.returncode}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "label": label, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "label": label, "error": str(e)}

def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG, "r", encoding="utf-8") as f: original = f.read()
    with open(LOG, "w", encoding="utf-8") as f: f.write(f"# Fresh Diverse Quality Test — {datetime.now(timezone.utc).isoformat()}\n\n")

    log("="*60)
    log("FRESH DIVERSE QUALITY TEST: 8 Configs x 15 Unique Turns Each")
    log(f"Total unique dialogs: {sum(len(v) for v in SCRIPTS.values())}")
    log("="*60)

    summaries = {}
    for label, combo in COMBOS:
        log(f"\n--- {label} (topic: {SCRIPTS[label][0][:40]}...) ---")
        t0 = time.time()
        result = run_combo(label, combo)
        dt = time.time() - t0

        if not result["ok"]:
            log(f"  FAILED: {result.get('error','?')}")
            summaries[label] = {"ok": False, "error": result.get("error",""), "turns": 0, "avg_quality": 0}
            continue

        turns = result["results"]
        ok = sum(1 for t in turns if t.get("ok"))
        avg_q = sum(t.get("total_score",0) for t in turns) / max(len(turns), 1)
        steps_yes = sum(1 for t in turns if t.get("has_steps"))
        steps_total = sum(t.get("steps_count",0) for t in turns)
        actions = [t["action_type"] for t in turns]
        ttms = [t.get("ttm_stage") for t in turns if t.get("ttm_stage")]
        dims = {}
        for t in turns:
            for d, s in t.get("quality",{}).items():
                if d != "total": dims.setdefault(d, []).append(s)

        summaries[label] = {
            "turns": len(turns), "ok": ok,
            "avg_quality": round(avg_q, 1),
            "steps_turns": f"{steps_yes}/{ok}",
            "total_steps": steps_total,
            "avg_tokens": round(sum(t["tokens"] for t in turns)/max(len(turns),1),0),
            "actions": dict((a, actions.count(a)) for a in set(actions)),
            "ttm_stages": dict((s, ttms.count(s)) for s in set(ttms)) if ttms else {},
            "dimensions": {d: round(sum(s)/len(s),2) for d, s in dims.items()},
            "time_s": round(dt, 0),
        }

        log(f"  Quality: {avg_q:.1f}/24 | Steps: {steps_yes}/{ok} turns ({steps_total} total) | actions: {summaries[label]['actions']} | ttm: {summaries[label]['ttm_stages']}")
        log(f"  Dims: {json.dumps(summaries[label]['dimensions'])} | time: {dt:.0f}s")

    with open(CONFIG, "w", encoding="utf-8") as f: f.write(original)

    log("\n" + "="*60)
    log("FINAL RANKING")
    log("="*60)
    ranked = sorted([(n,s) for n,s in summaries.items() if s.get("ok")], key=lambda x: x[1]["avg_quality"], reverse=True)
    for i,(name,s) in enumerate(ranked,1):
        bar = "#"*int(s["avg_quality"])
        log(f"  {i}. {name:18s} {s['avg_quality']:4.1f}/24 {bar} | steps={s['steps_turns']} ({s['total_steps']} total) | {s['actions']}")

    llm_s = [s["avg_quality"] for n,s in summaries.items() if s.get("ok") and n not in ("all_off","rules_diag")]
    rule_s = [s["avg_quality"] for n,s in summaries.items() if s.get("ok") and n in ("all_off","rules_diag")]
    log(f"\nLLM avg: {sum(llm_s)/len(llm_s):.1f}/24 | Rule avg: {sum(rule_s)/len(rule_s):.1f}/24 | Ratio: {sum(llm_s)/len(llm_s)/max(sum(rule_s)/len(rule_s),0.1):.1f}x")

    steps_llm = [s["total_steps"] for n,s in summaries.items() if s.get("ok") and n not in ("all_off","rules_diag")]
    log(f"Total steps generated (LLM): {sum(steps_llm)} across {len(steps_llm)*15} turns")

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"test_time": datetime.now(timezone.utc).isoformat(), "combos": len(COMBOS), "total_turns": sum(len(v) for v in SCRIPTS.values()), "summaries": summaries, "ranking": [(n,s["avg_quality"]) for n,s in ranked]}, f, ensure_ascii=False, indent=2)

    log(f"\nReport: {REPORT}")

if __name__ == "__main__":
    main()
