"""Phase 48: 7 维教学能力评测引擎。

评测不是看"回复形态"，是看教练是否具备真实一对一教学能力。
核心三问：诊得准吗？讲得透吗？激得动吗？
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TeachingCapabilityReport:
    profile_id: str = ""
    turns: int = 0
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, list[str]] = field(default_factory=dict)
    total: float = 0.0
    interpretation: str = ""

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "turns": self.turns,
            "scores": self.scores,
            "evidence": self.evidence,
            "total": round(self.total, 1),
            "max_possible": 30,
            "interpretation": self.interpretation,
        }


DIAGNOSIS_KEYWORDS = {
    "probe_question": ["考考你", "测测", "检验", "你来说说", "你怎么想的",
                        "你了解过", "之前学过吗", "接触过", "听过吗", "知道吗"],
    "deep_ask": ["为什么", "你怎么理解", "如果", "换个条件", "区别是什么",
                  "你怎么想", "换成", "反过来", "对比一下", "举个例子"],
    "specific_feedback": ["你刚才说的", "你提到的", "你这里", "这个地方",
                           "你之前", "你说过", "你问的", "你的理解"],
}

INTERACTION_KEYWORDS = {
    "open_question": ["你觉得", "你怎么看", "你的想法", "你是怎么",
                       "能...吗", "说说看", "试着", "推导", "讲一下"],
    "closed_question": ["对不对", "是不是", "懂了吗", "明白了吗", "会了吗"],
    "wait_and_space": ["你先想想", "不着急", "慢慢来", "试一下"],
    "collaborative_build": ["我们一起", "把你刚才说的和我刚才说的合起来", "基于你的想法", "顺着你的思路"],
}

FEEDBACK_KEYWORDS = {
    "specific_praise": ["你刚才", "你用的方法", "你想到的", "你这个思路",
                         "做得对", "方向对了", "很好", "不错", "就是这个意思"],
    "cognitive_conflict": ["顺着你的思路", "你看这里会怎样", "如果这样呢",
                            "试试看", "自己检查一下"],
    "normalize_error": ["很正常", "没关系", "很常见", "很多人", "正好是个"],
}

EMOTION_KEYWORDS = {
    "encourage": ["你可以的", "慢慢来", "已经进步了", "再试一次",
                   "加油", "别担心", "你可以", "再想想", "不错"],
    "acknowledge_effort": ["你努力了", "你花时间", "你刚才卡住后"],
    "adjust_difficulty": ["我们换个方式", "先不管那个", "从简单的开始", "分成几步"],
}


LLM_JUDGE_PROMPT = """你是一位资深一对一教学评估专家。请根据以下教练与学生的完整对话记录，按 7 个维度评估这位 AI 教练的教学能力。每维 0-5 分。

评估维度与评分标准（参考 Bloom 2σ效应、Graesser 5步辅导框架、Chi 建构性互动、Lepper 专家辅导研究）：

1. 学情诊断(0-5)：教练是否在引入新概念前探测学生的已有理解（"你之前了解过吗"）？学生暴露错误/误解时，教练是否通过追问定位具体问题，还是泛泛带过？
2. 个性化适配(0-5)：教练是否根据学生的具体错误类型和表述调整解释方式？是否使用了贴近学生经验的例子？教学节奏是否匹配学生的掌握速度？
3. 深度互动(0-5)：教练的提问是开放型（"你觉得""你怎么看"）还是封闭型（"对不对""懂了吗"）？是否引导学生自己思考和表达？教练话语占比是否过高？
4. 即时反馈(0-5)：学生出错时，教练是直接给答案，还是用认知冲突引导（"顺着你的思路，你看这里"）？正面反馈是否具体到过程（"你刚才XX的方法很好"）而非泛泛"很好"？
5. 关系建立(0-5)：教练是否察觉学生的畏难/沮丧/沉默并调整策略？课堂氛围是安全的还是紧张的？错误是否被正常化？
6. 效果验证(0-5)：教练是否在教完概念后让学生独立输出验证（"你自己试一下""你来讲一遍"）？有无阶段性回顾和总结？
7. 沟通协作(0-5)：本次不评估，统一给 3 分。

对话记录（T=教练, S=学生）：
{transcript}

请只输出 JSON，格式：
{{"1_学情诊断": N, "evidence_1": "具体对话片段作为证据", "2_个性化适配": N, "evidence_2": "...", "3_深度互动": N, "evidence_3": "...", "4_即时反馈": N, "evidence_4": "...", "5_关系建立": N, "evidence_5": "...", "6_效果验证": N, "evidence_6": "...", "7_沟通协作": 3, "evidence_7": "不评估"}}"""


def evaluate_with_llm(transcript: list[dict], api_key: str, model: str = "deepseek-chat") -> dict:
    """Phase 52: LLM-as-judge — 用 LLM 做同行评议式教学评估."""
    import json as _j, urllib.request as _ur
    # Build transcript text
    lines = []
    for t in transcript:
        coach = t.get("coach_statement", "")[:300]
        student = t.get("student", "")[:200]
        if coach:
            lines.append(f"T{ t.get('turn','?')}: [教练] {coach}")
        if student:
            lines.append(f"S{ t.get('turn','?')}: [学生] {student}")
    transcript_text = "\n".join(lines) if lines else "（空对话记录）"
    prompt = LLM_JUDGE_PROMPT.format(transcript=transcript_text[:4000])
    body = _j.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "请按上述标准评估，只输出 JSON。"},
        ],
        "temperature": 0.1,  # Phase 53: 低温减少评分方差
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
    }).encode()
    req = _ur.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with _ur.urlopen(req, timeout=60) as resp:
            result = _j.loads(resp.read().decode())
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        scores = _j.loads(content)
        # Ensure numeric scores
        for k in list(scores.keys()):
            if k.startswith("evidence_"):
                continue
            try:
                scores[k] = float(scores[k])
            except (ValueError, TypeError):
                scores[k] = 1.0
        return scores
    except Exception:
        return {}


def evaluate_teaching_capability(
    transcript: list[dict],
    student_profile: dict,
    student_state_snapshots: list[dict] | None = None,
) -> TeachingCapabilityReport:
    """基于 7 维框架评测教练的教学能力。每维 0-5 分。"""
    report = TeachingCapabilityReport(
        profile_id=student_profile.get("profile_id", "unknown"),
        turns=len(transcript),
    )
    all_coach_text = " ".join(t.get("coach_statement", "") for t in transcript)
    all_student_text = " ".join(t.get("student", "") for t in transcript)

    # ── 维度 1: 学情诊断 (15%) ──
    diagnosis_score = 0
    diagnosis_evidence = []
    probe_count = sum(1 for kw in DIAGNOSIS_KEYWORDS["probe_question"] if kw in all_coach_text)
    deep_ask_count = sum(1 for kw in DIAGNOSIS_KEYWORDS["deep_ask"] if kw in all_coach_text)
    n = max(len(transcript), 1)
    if probe_count >= 1:
        diagnosis_score += 1
        diagnosis_evidence.append(f"探测性提问 {probe_count} 次 (rate={probe_count/n:.0%})")
    if deep_ask_count >= 2:
        diagnosis_score += 2
        diagnosis_evidence.append(f"深度追问 {deep_ask_count} 次 (rate={deep_ask_count/n:.0%})")
    if probe_count + deep_ask_count >= 3:
        diagnosis_score = min(5, diagnosis_score + 1)
    if diagnosis_score == 0:
        diagnosis_score = 1
        diagnosis_evidence.append("未检测到明确的诊断行为 — 直接教学，无前测")
    report.scores["1_学情诊断"] = diagnosis_score
    report.evidence["1_学情诊断"] = diagnosis_evidence

    # ── 维度 2: 个性化适配 (20%) ──
    adapt_score = 0
    adapt_evidence = []
    action_types = [t.get("coach_action_type", "") for t in transcript]
    unique_actions = len(set(action_types))
    if unique_actions >= 3:
        adapt_score += 2
        adapt_evidence.append(f"使用了 {unique_actions} 种不同教学策略")
    specific_refs = sum(1 for kw in DIAGNOSIS_KEYWORDS["specific_feedback"] if kw in all_coach_text)
    if specific_refs >= 1:
        adapt_score += 1
        adapt_evidence.append(f"{specific_refs} 次引用学生具体表述")
    if specific_refs >= 3:
        adapt_score += 1
        adapt_evidence.append("高频引用学生原话——深度个性化")
    life_examples = sum(1 for kw in ["比如", "就像", "举个例子", "想象一下", "好比"] if kw in all_coach_text)
    if life_examples >= 2:
        adapt_score += 1
        adapt_evidence.append(f"使用了 {life_examples} 个生活化例子")
    if student_state_snapshots and len(student_state_snapshots) >= 2:
        before = student_state_snapshots[0].get("known_concepts", {})
        after = student_state_snapshots[-1].get("known_concepts", {})
        zpd_gain = sum(after.get(k, 0) - before.get(k, 0) for k in after)
        if zpd_gain > 0.1:
            adapt_score += 1
            adapt_evidence.append(f"ZPD 验证通过: 知识状态提升 {zpd_gain:.2f}")
    adapt_score = min(5, adapt_score)
    if adapt_score == 0:
        adapt_score = 1
        adapt_evidence.append("未检测到明显个性化适配")
    report.scores["2_个性化适配"] = adapt_score
    report.evidence["2_个性化适配"] = adapt_evidence

    # ── 维度 3: 深度互动与引导 (25%) ──
    interaction_score = 0
    interaction_evidence = []
    n_ = max(len(transcript), 1)
    open_q = sum(1 for kw in INTERACTION_KEYWORDS["open_question"] if kw in all_coach_text)
    closed_q = sum(1 for kw in INTERACTION_KEYWORDS["closed_question"] if kw in all_coach_text)
    total_q = open_q + closed_q
    q_rate = total_q / n_
    if q_rate >= 0.3:
        interaction_score += 2
    elif q_rate >= 0.15:
        interaction_score += 1
    interaction_evidence.append(f"提问 {total_q}次 (开放{open_q}/封闭{closed_q}, rate={q_rate:.0%})")
    if open_q >= 2:
        interaction_score += 2
        interaction_evidence.append(f"开放型提问 {open_q} 次")
    elif open_q >= 1:
        interaction_score += 1
    if open_q > closed_q * 1.5:
        interaction_score += 1
        interaction_evidence.append("开放/封闭比 > 1.5")
    collab_count = sum(1 for kw in INTERACTION_KEYWORDS["collaborative_build"] if kw in all_coach_text)
    if collab_count >= 1:
        interaction_score += 1
        interaction_evidence.append(f"协作构建 {collab_count} 次")
    coach_chars = len(all_coach_text)
    student_chars = len(all_student_text)
    total_chars = max(coach_chars + student_chars, 1)
    if coach_chars / total_chars > 0.80:
        interaction_score = max(1, interaction_score - 1)
        interaction_evidence.append("教练占比 >80%: 过度干预")
    if student_state_snapshots:
        confused_turns = sum(1 for s in student_state_snapshots if s.get("confusion_signal"))
        if confused_turns >= 2 and open_q >= confused_turns:
            interaction_score += 1
            interaction_evidence.append(f"{confused_turns}次困惑后均有追问")
    interaction_score = min(5, interaction_score)
    if interaction_score == 0:
        interaction_score = 1
    report.scores["3_深度互动"] = interaction_score
    report.evidence["3_深度互动"] = interaction_evidence

    # ── 维度 4: 即时反馈与纠正 (20%) ──
    feedback_score = 0
    feedback_evidence = []
    praise_count = sum(1 for kw in FEEDBACK_KEYWORDS["specific_praise"] if kw in all_coach_text)
    conflict_count = sum(1 for kw in FEEDBACK_KEYWORDS["cognitive_conflict"] if kw in all_coach_text)
    normalize_count = sum(1 for kw in FEEDBACK_KEYWORDS["normalize_error"] if kw in all_coach_text)
    if praise_count >= 1:
        feedback_score += 1
        feedback_evidence.append(f"具体表扬 {praise_count} 次")
    if praise_count >= 3:
        feedback_score += 1
    if conflict_count >= 1:
        feedback_score += 1
        feedback_evidence.append(f"认知冲突引导 {conflict_count} 次")
    if normalize_count >= 1:
        feedback_score += 1
        feedback_evidence.append("容错氛围建设")
    if feedback_score < 3 and praise_count >= 1:
        feedback_score += 1
    feedback_score = min(5, feedback_score)
    if feedback_score == 0:
        feedback_score = 1
        feedback_evidence.append("反馈偏泛化")
    report.scores["4_即时反馈"] = feedback_score
    report.evidence["4_即时反馈"] = feedback_evidence

    # ── 维度 5: 关系建立与情绪赋能 (10%) ──
    emotion_score = 0
    emotion_evidence = []
    encourage_count = sum(1 for kw in EMOTION_KEYWORDS["encourage"] if kw in all_coach_text)
    effort_count = sum(1 for kw in EMOTION_KEYWORDS["acknowledge_effort"] if kw in all_coach_text)
    adjust_count = sum(1 for kw in EMOTION_KEYWORDS["adjust_difficulty"] if kw in all_coach_text)
    if encourage_count >= 1:
        emotion_score += 1
        emotion_evidence.append(f"鼓励 {encourage_count} 次")
    if encourage_count >= 3:
        emotion_score += 1
    if effort_count >= 1:
        emotion_score += 1
    if adjust_count >= 1:
        emotion_score += 2
        emotion_evidence.append(f"主动调整难度 {adjust_count} 次")
    emotion_score = min(5, emotion_score)
    if emotion_score == 0:
        emotion_score = 2
        emotion_evidence.append("未检测到明显情绪支持")
    report.scores["5_关系建立"] = emotion_score
    report.evidence["5_关系建立"] = emotion_evidence

    # ── 维度 6: 教学效果评估 (10%) ──
    effect_score = 0
    effect_evidence = []
    verify_keywords = ["你自己做", "你来讲", "你试试", "独立完成", "不看笔记", "你来说说"]
    verify_count = sum(1 for kw in verify_keywords if kw in all_coach_text)
    if verify_count >= 1:
        effect_score += 2
        effect_evidence.append(f"独立输出验证 {verify_count} 次")
    if verify_count >= 2:
        effect_score += 1
    summary_keywords = ["总结一下", "回顾一下", "我们今天学了", "到目前为止"]
    if any(kw in all_coach_text for kw in summary_keywords):
        effect_score += 1
        effect_evidence.append("有阶段性总结/回顾")
    if effect_score < 3 and verify_count >= 1:
        effect_score += 1
    effect_score = min(5, effect_score)
    if effect_score == 0:
        effect_score = 1
        effect_evidence.append("讲完即结束，无当堂效果验证")
    report.scores["6_效果验证"] = effect_score
    report.evidence["6_效果验证"] = effect_evidence

    # ── 总分 ──
    weights = {
        "1_学情诊断": 0.15, "2_个性化适配": 0.20, "3_深度互动": 0.25,
        "4_即时反馈": 0.20, "5_关系建立": 0.10, "6_效果验证": 0.10,
    }
    report.total = sum(report.scores.get(k, 0) * weights.get(k, 0) for k in weights)
    if report.total >= 4.0:
        report.interpretation = "优秀：教练具备成熟的一对一教学能力"
    elif report.total >= 3.0:
        report.interpretation = "良好：教练有基本的教学意识，可在深度互动和个性化上加强"
    elif report.total >= 2.0:
        report.interpretation = "基础：教练能完成知识传递，但在诊断、互动和反馈上需显著提升"
    else:
        report.interpretation = "待提升：教练主要靠单向输出，缺失一对一教学的核心能力"

    return report
