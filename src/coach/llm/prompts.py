"""LLM 提示词模板 — 按 action_type 分模板.

每个模板根据教练上下文动态构建，注入 TTM 阶段 + SDT 动机 + 用户画像。
"""

from __future__ import annotations

import hashlib

_STABLE_SYSTEM_PREFIX = """你是 Coherence 认知主权保护系统的教练引擎。

你的任务是帮助用户学习，同时保护他们的认知主权。

输出要求:
1. 用中文回复
2. 只输出 JSON，不输出其他文字
3. JSON 必须包含 \"statement\" 字段（你的主要回复）。statement 第一句必须自然引用用户上一轮消息的关键内容，然后从上一轮教学内容继续推进。禁止\"好的我们开始吧\"等机械开场白
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

个性化指令:
- 引用用户上一条消息中提到的具体内容
- 使用\"你刚才说的...\"、\"你提到的...\"等引用语
- 确认用户理解后再推进

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
""",
    "suggest": """
【建议模式 - 输出要求】
你需要提供多个选项供用户选择，而不是给出单一答案。
JSON 必须包含以下字段:
- "statement": 你的建议概述
- "options": 数组（2-4 项），每项含 label/description
- "alternatives": 替代方案简要列表
- "question": 引导用户选择的追问
""",
    "reflect": """
【反思模式 - 输出要求】
你需要引导用户自我反思他们的学习过程或理解。
JSON 必须包含以下字段:
- "statement": 反思引导语
- "question": 反思性问题（开放式，不能是/否作答）
- "context_ids": 引用的上文消息 ID 列表
- "reflection_prompts": 引导反思的角度列表（2-3 项）
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

    terminal_checklist = _render_terminal_checklist(action_type)

    system_parts = [stable_prefix]
    if action_contract:
        system_parts.append(action_contract)
    system_parts.append(policy_layer)
    system_parts.append(context_layer)
    if terminal_checklist:
        system_parts.append(terminal_checklist)
    system_prompt = "\n\n".join(part for part in system_parts if part)

    # Phase 36: cache-eligibility evidence
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

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
    signals.append("- 引用用户之前的学习内容：使用'你刚才学的...'、'之前你提到...'等句式建立连续性")

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
