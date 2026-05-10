"""Phase 12 — FallbackEngine: LLM 不可用时的结构化教学模板库.

目标: 将 LLM OFF 质量从 2.8/24 提升到 12+/24.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict

# ── 鼓励语库 (4 级 20 句) ──────────────────────────────────

_ENCOURAGEMENT = {
    "strong": [
        "太棒了，你已经理解得很到位了！",
        "非常好！这个思路是正确的！",
        "没错，就是这样！你已经掌握了核心概念！",
        "厉害！你的理解完全正确！",
        "太厉害了，能看到你进步很大！",
    ],
    "medium": [
        "做得不错，继续保持！",
        "方向是对的，再深入一点就更好了。",
        "很好，你已经抓住关键了。",
        "不错，这个理解有道理。",
        "很棒，继续往下探索吧！",
    ],
    "gentle": [
        "没关系，这个概念确实需要时间消化。",
        "不着急，慢慢来，先理解基础。",
        "每个人学到这里都会卡一下，很正常。",
        "别灰心，卡壳是学习的一部分。",
        "慢慢来，重要的是理解而不是速度。",
    ],
    "try_more": [
        "你可以试试看，不用怕出错！",
        "动手写一下试试，错了也没关系。",
        "敲一下代码看看结果，实践是最好的学习。",
        "试一下吧，错误信息是最好的老师。",
        "不用怕报错，每次报错都是一次学习。",
    ],
}


def pick_encouragement(level: str = "medium") -> str:
    """随机选择一句鼓励语."""
    pool = _ENCOURAGEMENT.get(level, _ENCOURAGEMENT["medium"])
    return random.choice(pool)


# ── 教学模板库 ──────────────────────────────────────────────

_TEMPLATES: dict[str, dict] = {
    # ── scaffold 模板 ──
    "python_variable": {
        "statement": "变量就像一个带标签的盒子。你把数据放进去，标签就是变量名。比如 `age = 18` 就把数字 18 存进了名为 age 的变量里。之后你用 `age` 就能拿到那个值 18。",
        "steps": [
            {"order": 1, "action": "给变量起一个名字，比如 age、name、score", "expected": "变量名要见名知意"},
            {"order": 2, "action": "用等号 = 把值赋给变量: age = 18", "expected": "Python 中 = 是赋值不是等于"},
            {"order": 3, "action": "用变量名来使用里面的值: print(age)", "expected": "输出 18"},
        ],
        "question": "你想试试创建一个存有你名字的变量吗？可以试下 `name = '你的名字'` 然后 `print(name)`",
    },
    "python_loop": {
        "statement": "for 循环用来遍历一个序列里的每个元素。比如你有一个颜色列表 colors = ['red', 'blue', 'green']，用 `for c in colors: print(c)` 就能逐个打印出 red、blue、green。",
        "steps": [
            {"order": 1, "action": "创建一个列表: colors = ['red', 'blue', 'green']", "expected": "方括号创建列表"},
            {"order": 2, "action": "写 for 循环头: for color in colors:", "expected": "冒号不能少"},
            {"order": 3, "action": "在循环体里处理每个元素: print(color)", "expected": "每次循环 color 取一个值"},
        ],
        "question": "试试遍历你自己的列表：创建一个 3 个数字的列表，用 for 循环把每个数字乘以 2 打印出来。",
    },
    "python_function": {
        "statement": "函数是一段可以重复使用的代码。用 `def` 关键字定义，给函数起个名字，括号里放参数，然后缩进写函数体。比如 `def greet(name): print(f'Hello, {name}!')`，调用时 `greet('小明')` 就会打印 Hello, 小明!",
        "steps": [
            {"order": 1, "action": "用 def 定义函数: def add(a, b):", "expected": "def 是 define 的缩写"},
            {"order": 2, "action": "写函数体: return a + b", "expected": "缩进表示这是函数的一部分"},
            {"order": 3, "action": "调用函数: result = add(3, 5)", "expected": "result 的值为 8"},
        ],
        "question": "写一个函数叫 multiply，接受两个参数，返回它们的乘积。试试看！",
    },
    "python_string": {
        "statement": "字符串就是文本数据，用引号括起来。Python 支持单引号 'hello' 和双引号 \"hello\"，效果一样。字符串有很多有用的方法：`.upper()` 转大写、`.lower()` 转小写、`.split()` 切分、`len()` 获取长度。",
        "steps": [
            {"order": 1, "action": "创建字符串: text = 'Hello World'", "expected": "用引号括起来"},
            {"order": 2, "action": "转大写: text.upper() → 'HELLO WORLD'", "expected": ".upper() 不改变原字符串"},
            {"order": 3, "action": "切片取子串: text[0:5] → 'Hello'", "expected": "左闭右开 [0:5) 取前 5 个字符"},
        ],
        "question": "试试用 `.split()` 把一句话按空格切分成单词列表。",
    },
    "python_list": {
        "statement": "列表是 Python 中最常用的数据结构，可以存放多个元素。用方括号创建：`nums = [1, 2, 3, 4, 5]`。用索引访问：`nums[0]` 是第一个元素。用 `len(nums)` 获取长度。可以添加元素 `nums.append(6)`，可以删除 `nums.pop()`。",
        "steps": [
            {"order": 1, "action": "创建列表: fruits = ['apple', 'banana', 'orange']", "expected": "方括号，元素间用逗号分隔"},
            {"order": 2, "action": "用索引访问: fruits[0] → 'apple', fruits[-1] → 'orange'", "expected": "索引从 0 开始，-1 是最后一个"},
            {"order": 3, "action": "遍历列表: for f in fruits: print(f)", "expected": "逐个打印水果名"},
        ],
        "question": "创建一个你最爱吃的 5 种食物列表，然后分别打印出来。",
    },

    # ── suggest 模板 ──
    "python_beginner": {
        "statement": "学 Python 建议从基础语法开始，然后逐步深入：变量 → 数据类型 → 条件判断 → 循环 → 函数 → 类。每学完一个概念就动手写代码练习，不要只看不练。推荐用 Jupyter Notebook 或 VS Code 来边学边写。",
        "option": ["从变量开始学", "我已经会基础了，想学进阶", "帮我选一个适合的练习"],
        "question": "你现在学到哪了？",
    },
    "python_dict": {
        "statement": "字典是 Python 中存储键值对的数据结构。用花括号创建：`student = {'name': '小明', 'age': 18}`。用键访问值：`student['name']` 返回 '小明'。可以添加新键值对 `student['grade'] = 90`，也可以修改现有值 `student['age'] = 19`。",
        "steps": [
            {"order": 1, "action": "创建字典: scores = {'math': 95, 'english': 88}", "expected": "键和值用冒号分隔"},
            {"order": 2, "action": "访问值: scores['math'] → 95", "expected": "用键名作为索引"},
            {"order": 3, "action": "添加新键值: scores['history'] = 92", "expected": "自动添加新条目"},
        ],
        "question": "创建一个存有你 3 门功课成绩的字典，然后用 for 循环打印出每一门课的分数。",
    },
    "data_structures_intro": {
        "statement": "数据结构是组织和存储数据的方式。常见的有数组/列表（顺序存储）、链表（链式存储）、栈（后进先出）、队列（先进先出）、树（层级结构）、哈希表（键值对）。每种结构有不同的适用场景——数组查询快，链表插入快。",
        "option": ["从数组/列表开始学", "先了解时间复杂度", "比较不同结构的优劣"],
        "question": "你想从哪个数据结构开始？",
    },
    "general_learning": {
        "statement": "学习新知识有几个被研究证明有效的方法：1) 间隔重复 — 不要一次性学太久；2) 主动回忆 — 合上书回想刚才学了什么；3) 费曼技巧 — 假装教给别人；4) 交替练习 — 不要只练同一类题。试试把这几个方法用起来！",
        "option": ["想试试费曼技巧", "帮我制定学习计划", "给我一个练习"],
        "question": "你觉得哪种方法适合你？",
    },

    # ── reflect 模板 ──
    "confirm_understanding": {
        "statement": "你说得对！{}, 让我确认一下我的理解是否正确。{}的核心是{}，也就是说{}。这样理解对吗？",
        "question": "能用你自己的话再解释一遍吗？教别人是最好的学习方法。",
    },
    "check_confusion": {
        "statement": "我注意到你在 {} 这里可能有些困惑。这个概念确实容易混淆——很多人都会在这里卡住。我们来拆解一下：它和 {} 的主要区别是什么？",
        "question": "你觉得最让你困惑的是哪一点？",
    },

    # ── challenge 模板 ──
    "fix_bug": {
        "statement": "来看这段代码，里面有一个 bug，你能找出来吗？\n```python\n{}\n```\n提示：{}\n",
        "question": "运行一下看看会报什么错？根据错误信息来定位问题。",
    },
    "write_code": {
        "statement": "来试试这个挑战：写一段代码来实现{}。要求：{}\n\n先思考一下需要哪几步，然后动手写。写完了跑一下看看结果。",
        "steps": [
            {"order": 1, "action": "先想清楚输入和输出是什么", "expected": ""},
            {"order": 2, "action": "写出大致逻辑框架", "expected": ""},
            {"order": 3, "action": "逐步填充细节", "expected": ""},
        ],
        "question": "写完了吗？有什么地方卡住的？",
    },

    # ── probe 模板 ──
    "python_quiz": {
        "statement": "来检测一下你对 {} 的掌握程度。",
        "question": "请用自己的话解释 {} 是什么，并给出一个具体例子。正确答案应该包含：{}。",
        "expected_answer": "{}",
    },
    "concept_check": {
        "statement": "在继续之前，让我确认一下你是否理解了前面的内容。",
        "question": "{} 和 {} 有什么区别？请各举一个例子。",
        "expected_answer": "两者区别的核心是{}",
    },
}


# ── 话题→模板映射 ─────────────────────────────────────────

_TOPIC_MAP = {
    "variable": "python_variable", "variables": "python_variable", "var ": "python_variable",
    "loop": "python_loop", "for ": "python_loop", "while": "python_loop",
    "function": "python_function", "func": "python_function", "def ": "python_function",
    "string": "python_string",
    "list": "python_list", "array": "python_list", "data structure": "data_structures_intro",
    "beginner": "python_beginner", "start": "python_beginner", "learn": "python_beginner",
    "bug": "fix_bug", "error": "fix_bug", "fix": "fix_bug",
    "challenge": "write_code", "practice": "write_code", "exercise": "write_code",
    "quiz": "python_quiz", "test": "python_quiz",
    "why": "check_confusion", "confused": "check_confusion", "understand": "confirm_understanding",
    "difference": "concept_check", "compare": "concept_check",
    "how to": "python_function", "teach me": "python_beginner", "explain": "python_variable",
    "create": "python_list", "debug": "fix_bug", "dict": "python_dict",
    "python ": "python_beginner", "code": "python_function", "class": "python_function",
    # 精确子话题 — 必须排在通用 "python " 之前（长度优先）
    "python list": "python_list", "python loop": "python_loop", "python dict": "python_dict",
    "python function": "python_function", "python variable": "python_variable",
    "python string": "python_string",
}


def _detect_topic(user_input: str) -> str:
    """从用户输入中检测话题关键词."""
    text = user_input.lower()
    for keyword, template in sorted(_TOPIC_MAP.items(), key=lambda x: -len(x[0])):
        if keyword in text:
            return template
    return "general_learning"


# ── FallbackEngine ─────────────────────────────────────────

class FallbackEngine:
    """LLM 不可用时的教学模板引擎."""

    def __init__(self):
        self._turn_count: int = 0
        self._prev_topic: str = ""
        self._user_last_said: str = ""
        self._used_encouragements: list[str] = []

    def generate(
        self,
        action_type: str,
        user_input: str,
        previous_payload: dict | None = None,
        difficulty: str = "medium",
    ) -> dict:
        """根据 action_type 和用户输入生成模板 payload.

        Phase 14: difficulty 参数控制教学深度.
        """
        self._turn_count += 1
        topic = _detect_topic(user_input)

        # 上下文感知: 引用上一轮
        if previous_payload:
            prev_stmt = previous_payload.get("statement", "")
            prev_q = previous_payload.get("question", "")
            if prev_q and self._turn_count > 1:
                self._prev_topic = prev_q[:50]

        template_name = topic
        if action_type not in ("scaffold", "suggest", "reflect", "challenge", "probe"):
            template_name = "general_learning"

        # 查找最佳模板
        template = _TEMPLATES.get(template_name) or _TEMPLATES.get("general_learning")
        payload = dict(template)  # shallow copy

        # Phase 12.2: 上下文变量替换
        user_said_snippet = user_input[:50] if user_input else ""
        for key in ("statement", "question", "expected_answer"):
            if key in payload and "{}" in str(payload[key]):
                payload[key] = str(payload[key]).format(
                    user_said_snippet,  # {0} for first {}
                    self._prev_topic or "这个概念",  # {1}
                    self._prev_topic or "核心原理",  # {2}
                    "概念定义 + 应用场景 + 注意事项",  # {3}
                )
            elif key in payload and "{user_said}" in str(payload[key]):
                payload[key] = str(payload[key]).replace("{user_said}", user_said_snippet)

        # Phase 12.3: 鼓励语注入
        if self._turn_count % 3 == 0:
            enc = pick_encouragement("strong")
        elif self._turn_count == 1:
            enc = pick_encouragement("try_more")
        else:
            enc = pick_encouragement("medium")
        payload["statement"] = (payload.get("statement", "") + " " + enc).strip()

        self._user_last_said = user_input[:100]
        self._prev_topic = topic

        return payload
