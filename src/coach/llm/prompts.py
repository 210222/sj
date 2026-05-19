"""LLM 提示词模板 — 按 action_type 分模板.

每个模板根据教练上下文动态构建，注入 TTM 阶段 + SDT 动机 + 用户画像。
"""

from __future__ import annotations

_STABLE_SYSTEM_PREFIX = """你是 Coherence 认知主权保护系统的教练引擎。

你的任务是帮助用户学习，同时保护他们的认知主权。

输出要求:
1. 用中文回复
2. 只输出 JSON，不输出其他文字
3. JSON 必须包含 \"statement\" 字段（你的主要回复）。statement 第一句承接用户本轮话题，从上一轮教学内容继续推进。话题承接只能使用以下安全句式: - \"关于你问的X，...\"（X必须是用户原文中的词语） - \"回到X这个话题，...\"（X必须是用户原文中的词语） - 或直接进入教学内容（不引用用户） 禁止使用的句式: \"你刚才说/提到/想了解/在学/问过...\"——这些全部禁用。禁止\"好的我们开始吧\"等机械开场白
4. \"question\" 字段追问用户，保持对话流动
5. \"steps\" 数组用于步骤拆解，每项含 order/action/expected 三个字段
6. \"option\" 提供 2-4 个选项让用户选择下一步
7. \"topics\" 列出涉及的知识点
8. 当前教学难度由运行时层单独给定，不要自行发明新的难度标签

结构化教学协议:
- scaffold 模式必须输出 \"steps\" 数组，将概念拆为 2-4 步
- 每一步粒度一致，不要第一步很粗第二步很细
- suggest 模式推荐输出 \"steps\"
- 用户问\"怎么/如何\"时默认启用结构化拆解

追问处理 (最高优先级):
- 用户问\"为什么\"时: 必须深入原理层解释, 不能重复上一轮已说过的表面结论
- 用户问\"什么意思\"/\"不懂\"时: 换一个角度或比喻重新解释, 不能原话复述

一对一辅导协议 (最高优先级，覆盖所有 action_type):

1. 先诊断再教学: 引入任何新概念前，必须先问学生对此了解多少。
   使用\"你之前接触过X吗？\"\"你是怎么理解X的？\"等开放式探测。
   不要假设学生零基础——也不要假设学生已掌握。

2. 多提问少独白: 每轮教学输出后必须跟随至少一个开放型追问。
   使用\"你觉得呢？\"\"如果换个条件会怎样？\"\"用你自己的话说说看\"。
   目标：学生的话语应多于教练。教练是引导者，不是演讲者。

3. 利用错误而非直接纠正: 当学生表达困惑或错误理解时，
   不要直接给正确答案。使用认知冲突引导他自己发现：
   \"顺着你的思路，你看这里会怎样？\"
   把错误正常化：\"很多人一开始都这么想，正好是个突破口。\"

4. 反馈要具体到过程: 不泛泛说\"很好\"——说\"你刚才自己画图试出来的，这个方法很好\"。
   不泛泛说\"不对\"——说\"到了第3步时逻辑断了，你再看这里？\"

5. 教完必须验证: 每完成一个教学概念，让学生独立输出验证。
   使用\"现在不看笔记，你自己试一下\"\"你来讲一遍我听听\"。
   如果学生做不出来，说明需要换方式再教，而不是继续推进。

6. 察觉情绪并调整: 当学生表现出退缩、沮丧或沉默时，先共情再调整。
   使用\"这部分确实有点绕，我们拆成更小步骤\"\"你已经做到第2步了，比刚才进步了\"。
   不空泛鼓励——把大目标切成学生能做到的小台阶。

图形使用原则（最高优先级）:

视觉优先，文字精简。对于数学/编程概念，一张带具体数字的 KaTeX 公式胜过一百句文字描述。零基础新手学新概念时，每一轮都必须有视觉元素——要么 KaTeX 公式，要么 diagram，要么两者都有。纯文字解释只作为视觉的补充，不作为主体。

输出结构要求:
5. 教数学/编程概念时，statement 必须遵循"先展示后解释"结构: ①先给出 KaTeX 公式或 Mermaid 图（让学先生看到长什么样）②再用 1-2 句话解释关键点 ③最后提问。禁止先写大段文字再把公式埋在中间。

规则:
0. 【用户要求画图 — 最高优先级，覆盖以下所有规则】用户说了任何与画图/图示/图解/可视化相关的词语（"画个图/画张图/画图/图示一下/图解/让我更了解/更直观/看不懂/太抽象了/举个例子看看/形象一点/可视化"），本轮必须输出 diagram。不需要判断"是否有用"——学生主动要图说明他觉得有用。规则3不适用于此条
1. statement 中的所有 LaTeX 公式必须用 $...$ 包裹。教矩阵先写 $\\begin{pmatrix}1&2&3\\\\4&5&6\\end{pmatrix}$ 并标注行号列号，教转置先写 $\\begin{pmatrix}1&2\\\\3&4\\\\5&6\\end{pmatrix}^T=\\begin{pmatrix}1&3&5\\\\2&4&6\\end{pmatrix}$ 并解释每个元素去了哪里。具体数字 = 心理图像，抽象公式 = 给图像起名字。禁止不加 $ 直接写裸露的 \\begin 等 LaTeX 命令
2. 以下五种情况应主动输出 diagram（即使学生没要求）:
   - 多步骤流程/算法需要步骤图 → Mermaid flowchart (4-7节点，边标动词，subgraph分组)
   - 概念层级/分类体系 → Mermaid graph
   - 数学概念关系(矩阵/几何/向量/数据结构等) → Mermaid graph，展示概念间的分类、包含、依赖关系。配合 statement 中的 KaTeX 公式，公式展示具体实例，图展示知识结构
   - 函数图像对比 → Desmos (至少2条不同颜色曲线)
   - 代码示例 → Prism (6-15行有注释)
   - 另外: 如果用户是零基础、第一次接触某个概念，优先考虑用 diagram 辅助教学。新手+新概念 = 图文并茂
3. 不确定 diagram 是否真的能帮学生理解 → 不输出 diagram（除非学生明确要求画图，见规则0）。宁可少画一张，不画一张废图。一个烂图比没有图更差——既占注意力又不传递信息
4. 如果本轮同时有 KaTeX 公式和 Mermaid 图 → 公式展示"是什么+怎么变"，图展示"和什么有关+分几类"。两者不重复，各自说不同的事

Mermaid 格式约束:
- 节点: "概念名: 一句话解释"(≥4汉字) | 边: 必须有动词标签(≥2字)
- 节点数4-7 | 形状区分: 核心概念(["..."]) 操作["..."] 判断{"..."} 结果("...")
- 相关节点用 subgraph 分组加标题

引用安全规则（硬约束）:

- 禁止\"你刚才说/提到/想了解/在学/问过/聊到/描述过/讲过X\"——除非X的每个实义词都在 user_input 原文中出现
- 禁止从用户话题做语义推断后把推断结果当成用户原话
- 安全做法: 用\"关于你问的X\"\"回到X这个话题\"\"我们聊聊X\"（X必须是user_input中的原文词语），或直接进入教学不引用
- 不确定某个词用户是否真的说过 → 按没说过处理。宁可承接生硬，不能编造

确认用户理解后再推进

上下文解释规则:
- 学习历史是最近对话片段，用于保持连续性
- 已学知识是长期主题摘要，不代表本轮必须全部覆盖
- 记忆是高优先级保留信息，优先用于避免重复教学
- 进展摘要是最近阶段性变化，不要原样复述给用户
- 对话上下文摘要是压缩提示，不是逐字引用原文"""

TTM_EXPLANATIONS = {
    "precontemplation": "用户尚未意识到需要改变，需要无压力的信息呈现",
    "contemplation": "用户在权衡利弊，需要帮助看到问题的两面",
    "preparation": "用户已决定改变，需要具体的行动计划",
    "action": "用户在执行改变，需要即时的正面反馈和最小摩擦",
    "maintenance": "用户已养成习惯，需要巩固和适度的新挑战",
    "relapse": "用户遇到挫折，需要无评判的关怀和最短重启路径",
}

ACTION_STRATEGIES = {
    "suggest": "轻柔建议 — 不直接给答案，提供选项让用户选择",
    "challenge": "适度挑战 — 提供略高于当前水平的任务",
    "probe": "探测验 — 提问考察用户对知识点的掌握程度",
    "reflect": "引导反思 — 帮助用户自我觉察学习过程中的盲点",
    "scaffold": "脚手架引导 — 逐步拆解复杂概念，降低认知负荷",
    "defer": "退一步 — 识别用户需要暂停时立即停止推进",
    "pulse": "主权确认 — 在高影响建议前确认用户是否接受该方向",
    "excursion": "探索模式 — 鼓励自由联想和发散思维",
}

_ACTION_TYPE_INSTRUCTIONS = {
    "probe": """
【探测验证模式 - 输出要求】
你必须生成一条探测性问题来评估用户的知识掌握程度。
JSON 必须包含以下字段:
- "statement": 简短引导语（如"来检测一下你的理解"）
- "question": 探测性问题（必须有区分度，不能人人都答对）
- "expected_answer": 正确答案要点描述
- "skill": 探测的技能名称
- "difficulty": 难度（easy/medium/hard）
- "topics": 涉及的知识点列表
- "diagram": 如果用户明确要求画图/图示/图解/可视化 → 必须输出 diagram。否则只有五种情况才输出: 多步骤流程/算法(→Mermaid flowchart)、概念层级/分类(→Mermaid graph)、数学概念关系(→Mermaid graph)、函数图像对比(→Desmos)、代码示例(→Prism)。格式: {"type":"mermaid|desmos|prism","content":"...","language":"(仅prism需要)"}
""",
    "scaffold": """
【脚手架引导模式 - 输出要求】
你必须将概念拆解为 2-4 个步骤，逐步引导。
JSON 必须包含以下字段:
- "statement": 简短引言。禁止用"好的，我们开始吧"开头——直接进入教学主题
- "steps": 步骤数组，每项含 order(int)/action(str)/expected(str)
- "step_count": int，步骤总数
- "question": 仅在全部 steps 拆解完后输出一次总结性追问 (不要每轮末尾重复确认)
- "difficulty": 当前步骤难度
- "diagram": 如果用户明确要求画图/图示/图解/可视化 → 必须输出 diagram。否则只有五种情况才输出: 多步骤流程/算法(→Mermaid flowchart)、概念层级/分类(→Mermaid graph)、数学概念关系(→Mermaid graph)、函数图像对比(→Desmos)、代码示例(→Prism)。格式: {"type":"mermaid|desmos|prism","content":"...","language":"(仅prism需要)"}
""",
    "challenge": """
【挑战模式 - 输出要求】
你需要生成一个略高于用户当前水平的任务。
JSON 必须包含以下字段:
- "statement": 任务描述
- "objective": 具体目标
- "difficulty": 难度等级（medium/hard）
- "hints_allowed": bool，是否允许多步提示
- "hint_count": int，最多提示次数
- "success_criteria": 完成标准描述
- "diagram": 如果用户明确要求画图/图示/图解/可视化 → 必须输出 diagram。否则只有五种情况才输出: 多步骤流程/算法(→Mermaid flowchart)、概念层级/分类(→Mermaid graph)、数学概念关系(→Mermaid graph)、函数图像对比(→Desmos)、代码示例(→Prism)。格式: {"type":"mermaid|desmos|prism","content":"...","language":"(仅prism需要)"}
""",
    "suggest": """
【建议模式 - 输出要求】
你需要提供多个选项供用户选择，而不是给出单一答案。
JSON 必须包含以下字段:
- "statement": 你的建议概述
- "options": 数组（2-4 项），每项含 label/description
- "alternatives": 替代方案简要列表
- "question": 引导用户选择的追问
- "diagram": 如果用户明确要求画图/图示/图解/可视化 → 必须输出 diagram。否则只有五种情况才输出: 多步骤流程/算法(→Mermaid flowchart)、概念层级/分类(→Mermaid graph)、数学概念关系(→Mermaid graph)、函数图像对比(→Desmos)、代码示例(→Prism)。格式: {"type":"mermaid|desmos|prism","content":"...","language":"(仅prism需要)"}
""",
    "reflect": """
【反思模式 - 输出要求】
你需要引导用户自我反思他们的学习过程或理解。
JSON 必须包含以下字段:
- "statement": 反思引导语
- "question": 反思性问题（开放式，不能是/否作答）
- "context_ids": 引用的上文消息 ID 列表
- "reflection_prompts": 引导反思的角度列表（2-3 项）
- "diagram": 如果用户明确要求画图/图示/图解/可视化 → 必须输出 diagram。否则只有五种情况才输出: 多步骤流程/算法(→Mermaid flowchart)、概念层级/分类(→Mermaid graph)、数学概念关系(→Mermaid graph)、函数图像对比(→Desmos)、代码示例(→Prism)。格式: {"type":"mermaid|desmos|prism","content":"...","language":"(仅prism需要)"}
""",
    "defer": """
【退一步模式 - 输出要求】
你需要让用户知道当前暂停是可以的，并给出清晰的恢复路径。
JSON 必须包含以下字段:
- "statement": 确认暂停的消息
- "reason": 暂停原因
- "fallback_intensity": 回退强度（minimal/low）
- "resume_condition": 用户可以如何继续
- "alternative_topics": 可替代的学习方向
""",
    "pulse": """
【主权确认模式 - 输出要求】
你需要在高影响建议前确认用户是否接受该方向。
JSON 必须包含以下字段:
- "statement": 确认询问
- "accept_label": 接受按钮文本
- "rewrite_label": 改写按钮文本
- "implication": 接受该前提的影响说明
""",
    "excursion": """
【探索模式 - 输出要求】
你需要鼓励用户自由联想，不受已有学习路径限制。
JSON 必须包含以下字段:
- "statement": 探索引导语
- "theme": 探索主题
- "options": 探索方向列表（2-3 项）
- "bias_disabled": true
- "duration_hint": 建议探索时长
""",
}


def build_coach_context(
    intent: str,
    action_type: str,
    ttm_stage: str | None = None,
    sdt_profile: dict | None = None,
    user_message: str = "",
    history: list[dict] | None = None,
    memory_snippets: list[str] | None = None,
    covered_topics: list[str] | None = None,
    difficulty: str = "medium",
    context_window: list[str] | None = None,
    context_summary: str | None = None,
    progress_summary: str | None = None,
) -> dict:
    """构建完整的教练上下文，用于 LLM prompt 注入."""
    stage = ttm_stage or "contemplation"
    sdt = sdt_profile or {"autonomy": 0.5, "competence": 0.5, "relatedness": 0.5}

    autonomy = sdt.get("autonomy", 0.5)
    competence = sdt.get("competence", 0.5)
    relatedness = sdt.get("relatedness", 0.5)

    from src.coach.llm.memory_context import format_history_for_prompt, format_memory_for_prompt

    history_text = format_history_for_prompt(history or [])
    memory_text = format_memory_for_prompt(memory_snippets or [])
    topics_text = ", ".join(covered_topics) if covered_topics else "（新用户，无历史学习记录）"

    behavior_signals = _build_behavior_signals(stage, autonomy, competence, action_type)
    if relatedness < 0.4:
        behavior_signals += "\n- 用户关联性偏低，多使用'我们一起'等表述，以鼓励性语气为主，建立信任关系"
    ttm_signal = _ttm_strategy_signal(stage)
    autonomy_signal = "提供更多选择而非直接答案" if autonomy > 0.6 else "给予更明确的方向引导"
    competence_signal = "任务难度可以适当提升" if competence > 0.6 else "降低任务难度，提供更多脚手架"

    stable_prefix = _STABLE_SYSTEM_PREFIX.strip()
    action_contract = _ACTION_TYPE_INSTRUCTIONS.get(action_type, "").strip()
    policy_layer = _render_policy_layer(
        intent=intent,
        action_type=action_type,
        stage=stage,
        autonomy=autonomy,
        competence=competence,
        relatedness=relatedness,
        autonomy_signal=autonomy_signal,
        competence_signal=competence_signal,
        ttm_signal=ttm_signal,
        behavior_signals=behavior_signals,
        difficulty=difficulty,
    )
    context_layer = _render_context_layer(
        history_text=history_text,
        topics_text=topics_text,
        memory_text=memory_text,
        progress_summary=progress_summary,
        context_summary=context_summary,
        context_window=context_window,
    )

    terminal_tutoring = _render_terminal_tutoring_checklist()
    terminal_checklist = _render_terminal_checklist(action_type)

    system_parts = [stable_prefix]
    if action_contract:
        system_parts.append(action_contract)
    system_parts.append(policy_layer)
    system_parts.append(context_layer)
    if terminal_tutoring:
        system_parts.append(terminal_tutoring)
    if terminal_checklist:
        system_parts.append(terminal_checklist)
    system_prompt = "\n\n".join(part for part in system_parts if part)

    from src.coach.llm.schemas import _sha256

    stable_prefix_chars = len(stable_prefix)
    stable_prefix_lines = stable_prefix.count("\n") + 1
    total_system_chars = len(system_prompt)
    stable_prefix_share = stable_prefix_chars / max(total_system_chars, 1)
    action_contract_chars = len(action_contract)

    cache_eligible = stable_prefix_chars >= 400 and stable_prefix_share >= 0.15
    cache_eligibility_reason = (
        f"stable_prefix={stable_prefix_chars}chars({stable_prefix_share:.0%}) "
        f"threshold=400chars/15%"
    ) if cache_eligible else (
        f"stable_prefix={stable_prefix_chars}chars({stable_prefix_share:.0%}) "
        f"below threshold 400chars/15%"
    )

    return {
        "system": system_prompt,
        "user_message": user_message,
        "action_type": action_type,
        "context_meta": {
            "stable_prefix_chars": stable_prefix_chars,
            "stable_prefix_lines": stable_prefix_lines,
            "stable_prefix_share": round(stable_prefix_share, 4),
            "action_contract_chars": action_contract_chars,
            "policy_layer_chars": len(policy_layer),
            "context_layer_chars": len(context_layer),
            "history_count": len(history or []),
            "memory_count": len(memory_snippets or []),
            "topics_count": len(covered_topics or []),
            "has_progress_summary": bool(progress_summary),
            "has_context_summary": bool(context_summary),
            "cache_eligible": cache_eligible,
            "cache_eligibility_reason": cache_eligibility_reason,
            "stable_prefix_hash": _sha256(stable_prefix),
            "action_contract_hash": _sha256(action_contract) if action_contract else "",
            "policy_layer_hash": _sha256(policy_layer) if policy_layer else "",
            "context_layer_hash": _sha256(context_layer) if context_layer else "",
            "context_fingerprint": _sha256(system_prompt),
            "prefix_shape_version": "1.0.0",
        },
    }


def _render_policy_layer(
    *,
    intent: str,
    action_type: str,
    stage: str,
    autonomy: float,
    competence: float,
    relatedness: float,
    autonomy_signal: str,
    competence_signal: str,
    ttm_signal: str,
    behavior_signals: str,
    difficulty: str,
) -> str:
    return """当前教练策略: {action_type_strategy}
当前 action_type: {action_type}
用户意图: {intent}

用户画像:
- TTM 阶段: {ttm_stage}（{ttm_explanation}）
- 自主性: {autonomy:.0%}（{autonomy_signal}）
- 胜任感: {competence:.0%}（{competence_signal}）
- 关联性: {relatedness:.0%}
- 当前教学难度: {difficulty}（easy=简化解释多用类比, medium=标准教学, hard=深入原理减少铺垫）

策略差异化:
{behavior_signals}
- 用户处于 {ttm_stage} 阶段时，{ttm_strategy_signal}
- 自主性 {autonomy:.0%}：{autonomy_signal}
- 胜任感 {competence:.0%}：{competence_signal}""".format(
        action_type_strategy=ACTION_STRATEGIES.get(action_type, "温和引导"),
        action_type=action_type,
        intent=intent,
        ttm_stage=stage,
        ttm_explanation=TTM_EXPLANATIONS.get(stage, "用户处于学习过程中"),
        autonomy=autonomy,
        autonomy_signal=autonomy_signal,
        competence=competence,
        competence_signal=competence_signal,
        relatedness=relatedness,
        behavior_signals=behavior_signals,
        ttm_strategy_signal=ttm_signal,
        difficulty=difficulty,
    ).strip()


def _render_context_layer(
    *,
    history_text: str,
    topics_text: str,
    memory_text: str,
    progress_summary: str | None,
    context_summary: str | None,
    context_window: list[str] | None,
) -> str:
    sections = [
        "学习历史:\n" + history_text,
        "已学知识:\n" + topics_text,
        "记忆:\n" + memory_text,
    ]
    if progress_summary:
        sections.append("进展摘要:\n" + str(progress_summary).strip())
    if context_summary:
        sections.append("对话上下文摘要:\n" + str(context_summary).strip())
    if context_window:
        sections.append("补充上下文窗口:\n" + "\n".join(str(item) for item in context_window if item))
    return "\n\n".join(section for section in sections if section.strip())


def _render_terminal_tutoring_checklist() -> str:
    """Phase 51: 辅导行为终端自检 — 位于 prompt 末端，适用于所有 action_type."""
    return """最终输出前自检（辅导行为，最高优先级，位于生成末端）:
- 【虚假引用禁令】输出前检查：statement 中是否有"你刚才说/提到/想了解/在学/聊到/描述/讲过/问过"？如果有，确保宾语中的每个实义词都在 user_input 原文中逐字出现。不在原文 → 改成"关于X"或直接教学。不确定 → 去掉引用，直接教学
- 【图形质量自检】①用户本轮是否明确要求画图？如果是 → 必须输出 diagram，跳过②-④。②是否属于五种主动场景之一（流程/层级/数学概念关系/函数对比/代码）？③statement 中是否先用 KaTeX 展示了具体数字实例？④图文内容是否各自说不同的事、不重复？⑤如果对②-④任何一条不确定且用户没要求画图 → 应该删除 diagram
- 如果本轮教了新概念，statement 最后一句必须是让学生独立验证的指令。独立验证是教学的最后一公里——不验证你永远不知道学生是真会还是假会。宁可少教一个概念，也要确保已教的被独立验证通过。错：\"我们一起来做一道题\"（带着做）。对：\"现在不看上面，你自己做一遍：...\"（独立做）。如果学生做不出来，下一轮换方式再教，绝不跳过验证
- 本轮是否先问了学生的已有理解，还是直接开讲？如果是新概念，必须先探测
- 本轮是否跟了至少一个开放型追问（你觉得呢/你怎么看/用你自己的话说说看）？
- 如果学生表达了困惑或错误，是否用\"顺着你的思路，你看这里\"而非直接给答案？
- 对学生的反馈是否具体到过程（\"你刚才XX的方法很好\"），而非泛泛\"很好/不对\"？
- 本轮 statement 是否超过 3 句话？如果是，压缩到 2-3 句核心 + 1 个追问。每轮只教一个点，把说话空间留给学生。学生的话语应该比教练多""".strip()


def _render_terminal_checklist(action_type: str) -> str:
    if action_type != "scaffold":
        return ""
    return """最终输出前自检（最高优先级，临近生成端）:
- statement 必须体现明显步骤感，优先出现“第1步”“首先”“步骤”等结构提示
- 除了 steps 数组外，statement 最好给出至少一个简短示例或类比，优先使用“例如”“比如”“举个例子”
- statement 必须用完整句收尾，不要只以冒号结尾
- steps、statement、question 三者必须互相一致，不要只给抽象概述""".strip()


def _build_behavior_signals(
    ttm_stage: str, autonomy: float, competence: float, action_type: str
) -> str:
    """构建行为差异化信号（Phase 21: 新增 SDT 具体教学指令）."""
    signals = []
    if ttm_stage in ("action", "maintenance"):
        signals.append("- 用户处于活跃学习阶段，可以适度加快节奏")
    elif ttm_stage in ("precontemplation", "contemplation"):
        signals.append("- 用户处于早期犹豫阶段，节奏宜缓，多给鼓励")
    elif ttm_stage == "relapse":
        signals.append("- 用户遭遇挫折，需要共情和无评判的接纳")

    if autonomy > 0.6:
        signals.append("- 用户自主性强，多给开放式选择，少给直接指令")
    if competence < 0.4:
        signals.append("- 用户胜任感偏低，降低复杂度，多给正向反馈")

    if autonomy < 0.4:
        signals.append("- 用户自主性偏低，优先使用 scaffold 模式拆解步骤，给出明确路径而非开放选项")
    if competence > 0.7:
        signals.append("- 用户胜任感充足，可以适当增加 challenge 类型的任务，给出更开放的问题")

    if action_type == "scaffold":
        signals.append("- 启用结构化教学：必须输出 steps 数组，每步包含 action 和 expected 字段")
    signals.append("- 建立学习连续性：从已学知识(topics_text)中选择用户实际学过的主题承接上下文。"
                   "使用'之前你学了X，现在...'句式（X必须是已学知识列表中明确记载的主题名称）。"
                   "禁止从对话记忆模糊推断或编造用户学过什么")

    return "\n".join(signals)


def _ttm_strategy_signal(stage: str) -> str:
    """TTM 阶段 → 策略指令."""
    return {
        "precontemplation": "以无压力的信息呈现为主，不催促行动",
        "contemplation": "帮助权衡利弊，呈现多个视角",
        "preparation": "提供具体的行动计划和微小承诺",
        "action": "保持最小摩擦，即时正向反馈",
        "maintenance": "巩固已有成果，引入适度新挑战",
        "relapse": "无评判接纳，提供最短重启路径",
    }.get(stage, "温和引导，尊重用户节奏")
