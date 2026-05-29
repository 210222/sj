"""费曼自述阶段: 比喻解释 + 一句话 + 三步拆解 + 代码检测."""

import json
import logging
import re

_logger = logging.getLogger(__name__)

FEYNMAN_SYSTEM = """你是 {subject} 教师，正在备课 "{kp}"。

用费曼学习法检验自己——如果你不能用简单的比喻向12岁小孩讲清楚，说明你没有真正理解。

规则（缺一条 = 不通过）

1. 用比喻解释，零术语。如果必须用术语，先定义它。
   正确: "变量像贴标签。盒子是内存，标签是变量名。age=25是把25放进盒子。"
   错误: "变量是内存地址的符号引用，赋值将右值绑定到左值标识符。"

2. 一句话归纳核心。格式: "一句话：________"
   正确: "一句话：极限 = 无限接近但从不到达。"
   错误: "一句话：极限是微积分的基础概念，在数学分析中很重要。"（这是"重要性"不是"核心"）

3. 拆成三个最小步骤。每步一句话，可独立理解，无逻辑跳跃。

4. 标注每一个不确定。任何时间感到"这个比喻不够精确""这个边界我没把握"→ 必须标注[不确定]。
   格式: [不确定] 位置描述: 为什么不精确 / 还需要搞清楚什么
   [不确定] 不是失败——它告诉你在教这个知识前还有什么要深挖。

消化阶段参考:
  定义: {definition}
  常见误解: {misconceptions}
  容易卡住: {sticking_points}
  常见弯路: {detours}

输出 JSON:
{{
  "analogy": "零术语比喻解释（100-200字）",
  "one_sentence": "一句话核心归纳",
  "three_steps": ["步骤1", "步骤2", "步骤3"],
  "uncertain_markers": [
    {{"location": "在比喻的哪部分", "issue": "为什么不精确", "whats_needed": "还需要搞清楚什么"}}
  ],
  "grade": "通过 或 不通过"
}}

只输出 JSON。"""

FEYNMAN_USER = """请对 {subject} 的 "{kp}" 做费曼自述。参考消化阶段的信息，但必须用自己的理解和比喻。"""

JARGON_DB = {
    "编程语言": ["变量", "赋值", "引用", "内存", "类型", "函数", "参数", "返回",
                 "对象", "类", "实例", "指针", "静态", "动态", "编译", "解释",
                 "作用域", "循环", "条件", "迭代", "递归", "模块", "导入"],
    "数学": ["函数", "极限", "导数", "积分", "矩阵", "向量", "定理", "证明",
             "收敛", "发散", "无穷", "域", "集合", "映射", "变换", "特征值"],
    "语言学习": ["时态", "语态", "从句", "主语", "谓语", "宾语", "定语", "状语",
                 "虚拟语气", "倒装", "省略", "冠词", "介词", "连词"],
}
HOLLOW_PATTERNS = [
    re.compile(r"是.*的基础"), re.compile(r"在.*中很重要"),
    re.compile(r"是.*的核心概念"), re.compile(r"理解.*的关键"),
    re.compile(r"掌握.*的前提"),
]


def feynman_self_explain(kp_name: str, digested, llm_client,
                         subject: str = "", category: str = "") -> "FeynmanCard":
    """费曼自述 + 代码层检测。"""
    from src.coach.curriculum.models import FeynmanCard

    system = FEYNMAN_SYSTEM.replace("{subject}", subject or kp_name)
    system = system.replace("{kp}", kp_name)
    system = system.replace("{definition}", digested.definition)
    system = system.replace("{misconceptions}", ", ".join(digested.misconceptions))
    system = system.replace("{sticking_points}", ", ".join(digested.sticking_points))
    system = system.replace("{detours}", ", ".join(digested.detours))

    user = FEYNMAN_USER.replace("{subject}", subject or kp_name)
    user = user.replace("{kp}", kp_name)

    raw = llm_client.search(system, user)
    if isinstance(raw, str):
        raw = json.loads(raw)

    card = FeynmanCard(
        knowledge_point=kp_name,
        analogy=str(raw.get("analogy", "")),
        one_sentence=str(raw.get("one_sentence", "")),
        three_steps=[str(s) for s in raw.get("three_steps", [])],
        uncertain_markers=list(raw.get("uncertain_markers", [])),
        grade=str(raw.get("grade", "不通过")),
        jargon_count=0,
    )

    card = feynman_code_check(card, category)
    return card


def feynman_code_check(card: "FeynmanCard", category: str = "") -> "FeynmanCard":
    """四道防线: 术语 + 空话 + 跳跃 + 不确定追问。"""
    jargon_list = JARGON_DB.get(category, [])
    # 排除知识点本身的词——教"变量"不能禁止说"变量"
    kp_words = set(card.knowledge_point.replace("赋值", "").replace("定义", ""))
    jargon_filtered = [j for j in jargon_list if j not in kp_words and j not in card.knowledge_point]
    found = [j for j in jargon_filtered if j in card.analogy]
    card.jargon_count = len(found)
    # 仅在术语密集(>2)且无定义标记时才判不通过
    has_definition = any(marker in card.analogy for marker in ["指的是", "就是", "像", "可以理解为", "好比", "相当于"])
    if len(found) > 2 and not has_definition:
        card.grade = "不通过"
        _logger.warning(f"Feynman jargon dense without definition ({category}): {found}")

    for pat in HOLLOW_PATTERNS:
        if pat.search(card.one_sentence):
            card.grade = "不通过"
            _logger.warning(f"Feynman hollow one_sentence: {card.one_sentence[:60]}")

    if len(card.three_steps) < 3:
        card.grade = "不通过"

    if len(card.uncertain_markers) == 0 and card.grade == "通过":
        _logger.warning(f"Feynman zero uncertainty for {card.knowledge_point} — possible performance")
        card.uncertain_markers.append({
            "location": "自动检测",
            "issue": "零 [不确定] 标注——可能是表演性理解",
            "whats_needed": "强制追问: 比喻在什么条件下失效？有没有不敢100%确定的边界case？"
        })

    return card
