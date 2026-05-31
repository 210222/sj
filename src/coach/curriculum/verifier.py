"""自验证阶段: 出题/答题/判分三方隔离 + 5 道代码防御."""

import json
import logging
import random
import re

from src.coach.curriculum.feynman import JARGON_DB

_logger = logging.getLogger(__name__)

VERIFIER_Q_SYSTEM = """你是考题设计师。你的任务是找出教师理解的漏洞。

你正在审核 {subject} 的 "{kp}" 知识点。

出 3 类题目，每类 ≥ 1 题，总 ≥ 5 题

A 类 — 误解陷阱（盯着这些 misconceptions 出题）:
  {misconceptions}
  每条 misconception 必须至少有 1 道题覆盖。

B 类 — 边界推演（盯着这些 sticking_points 出题）:
  {sticking_points}
  至少 1 道题针对 sticking_points。

C 类 — 对比质疑（为什么选 A 而不是 B）:
  设计题目让教师解释设计选择，而不是只证明"选A是对的"。

题目格式硬约束:
禁止: 纯选择题/判断题/填空题
允许: 开放型问答题/"给出输出并解释原因"/"找出错误并修正"/"用比喻解释"/"对比分析"
C类题如用"选择"措辞 → 必须要求回答包含设计目标+选择理由+代价/局限三要素。

输出 JSON（只出题，不回答）:
{{
  "questions": [
    {{"id": "Q1", "type": "A", "targets": "针对哪条 misconception",
      "question": "题目文本",
      "expected_outline": "判分参考——期望的大致回答方向"}}
  ],
  "coverage": {{"total_misconceptions": N, "covered": N, "uncovered": []}}
}}

coverage.uncovered 非空 → 输出不完整，重新出题。只输出 JSON。"""

VERIFIER_A_SYSTEM = """你是被考核的 {subject} 教师。逐题诚实回答。

规则:
1. 每道题独立回答。不会就说不会。
2. 确定 → certainty: "high"。基本确定有细微不确定 → "medium"。不确定 → "low"或"uncertain"。
3. 低 certainty 时必须说明卡在哪里、需要查什么。
4. 不要用废话填充——诚实的"我卡在XX"比长篇废话更有价值。

输出 JSON:
{{"answers": [
  {{"question_id": "Q1", "answer": "你的回答",
    "certainty": "high|medium|low|uncertain",
    "uncertain_detail": "如果不确定——卡在哪"}}
]}}"""

VERIFIER_G_SYSTEM = """你是判卷人。不给同情分。

判分标准（任何一条不满足 → 不通过）:
- 回答正确且推理完整
- certainty="high"或"medium"
- 能用非术语的语言表述
- 和消化阶段的定义一致（不一致 → 消化阶段可能有问题）

不通过条件（任何一条满足 → 不通过）:
- 回答模糊、回避、答非所问
- 回答用术语解释术语
- certainty="low"或"uncertain"
- 回答"需要具体分析"但未给出分析框架

输出 JSON:
{{
  "graded": [{{"question_id": "Q1", "passed": true/false, "reason": "..."}}],
  "verified": true/false,
  "failed_topics": [],
  "deductions": [],
  "improvements": []
}}
"""

VERIFIER_D4_SYSTEM = """你是反对派评审。你的任务是找出判分可能遗漏的问题。

审查要点（高温模式，鼓励质疑）:
- 是否有术语堆砌而非真正理解？
- 推理步骤是否有跳跃或漏洞？
- 回答是否回避了题目的核心问法？
- 是否有"看起来对但实际不精确"的表述？

输出 JSON:
{{
  "issues": [
    {{"question_id": "Q1", "severity": "high|medium|low", "detail": "具体问题描述"}}
  ],
  "overall_assessment": "clean|suspicious|biased"
}}
"""

RED_FLAGS = ["从某种角度来说", "需要具体分析", "取决于具体情况",
             "总而言之", "关键在于", "既要...又要", "辩证地看"]
SELECTION_ONLY = re.compile(r"^[A-D][)）]?\s*$|^选\s*[A-D]\s*$|^答案是?\s*[A-D]\s*$")


def self_verify(kp_name: str, feynman_card, digested, llm_client,
                subject: str = "", category: str = "") -> "VerificationReport":
    """自验证: 3 个独立 LLM 调用 + 代码防御。"""
    from src.coach.curriculum.models import VerificationReport

    # Call 1: question setter
    q_system = VERIFIER_Q_SYSTEM.replace("{subject}", subject or kp_name)
    q_system = q_system.replace("{kp}", kp_name)
    q_system = q_system.replace("{misconceptions}", ", ".join(digested.misconceptions))
    q_system = q_system.replace("{sticking_points}", ", ".join(digested.sticking_points))
    q_user = f"为 {subject} 的 {kp_name} 设计自验证考题。"
    q_raw = llm_client.search(q_system, q_user)
    if isinstance(q_raw, str):
        try:
            q_raw = json.loads(q_raw)
        except json.JSONDecodeError:
            return VerificationReport(kp_name, False, 0, 0, ["出题JSON解析失败"], [], [], {})
    questions = q_raw.get("questions", [])

    # Defense 1: coverage check
    if len(questions) < 5:
        return VerificationReport(kp_name, False, len(questions), 0, ["不足5题"], [], [], {})
    types = set(q["type"] for q in questions)
    for t in ["A", "B", "C"]:
        if t not in types:
            return VerificationReport(kp_name, False, len(questions), 0, [f"缺{t}类题"], [], [], {})

    # Detect forbidden question types
    for q in questions:
        for pat, qtype in [(re.compile(r"下列(哪个|哪项|哪种).*(正确|错误|恰当)"), "纯选择题"),
                            (re.compile(r"对还是错|判断.*正确.*错误"), "判断题"),
                            (re.compile(r"填空|____"), "填空题")]:
            if pat.search(q["question"]):
                return VerificationReport(kp_name, False, len(questions), 0, [f"禁止题型: {qtype}"], [], [], {})

    # Defense 5: obfuscate questions + distractor injection
    distractors = _fetch_distractors(kp_name, n=2)
    shuffled, target_ids = _obfuscate(questions, distractors)
    a_user = f"回答以下考题:\n{json.dumps(shuffled, ensure_ascii=False, indent=2)}"

    # Call 2: exam taker
    a_system = VERIFIER_A_SYSTEM.replace("{subject}", subject or kp_name)
    a_raw = llm_client.search(a_system, a_user)
    if isinstance(a_raw, str):
        try:
            a_raw = json.loads(a_raw)
        except json.JSONDecodeError:
            return VerificationReport(kp_name, False, 0, 0, ["答题JSON解析失败"], [], [], {})
    answers = a_raw.get("answers", [])

    # Defense 2: answer quality
    for a in answers:
        for flag in RED_FLAGS:
            if flag in a.get("answer", "") and a.get("certainty") in ("high", "medium"):
                return VerificationReport(kp_name, False, 0, 0, ["废话检测"], [], [], {})
        if a.get("answer", "").count("但") > 3 and a.get("certainty") != "low":
            return VerificationReport(kp_name, False, 0, 0, ["过度转折"], [], [], {})
        if SELECTION_ONLY.match(a.get("answer", "").strip()):
            return VerificationReport(kp_name, False, 0, 0, ["只选不解释"], [], [], {})
        if re.match(r"^[A-D][)）]", a.get("answer", "")[:3]) and len(a.get("answer", "")) < 80:
            return VerificationReport(kp_name, False, 0, 0, ["选项推理不足"], [], [], {})

    # Defense 2b: Feynman cross-check — if feynman was jargon-free,
    # the answering LLM should also use minimal jargon.
    if feynman_card is not None and getattr(feynman_card, 'jargon_count', 1) == 0:
        answer_jargon = _check_answer_jargon(answers, category, kp_name)
        if len(answer_jargon) > 3:
            return VerificationReport(
                kp_name, False, 0, 0,
                [f"费曼零术语但答题用术语({len(answer_jargon)}个): {answer_jargon[:5]}"],
                [], [], {}
            )

    # Defense 5b: distractor response check
    if distractors:
        distractor_ids = {d["id"] for d in distractors}
        distractor_answers = [a for a in answers if a["question_id"] in distractor_ids]
        confident_on_distractor = [
            a for a in distractor_answers
            if a.get("certainty", "low") in ("high", "medium")
            and len(a.get("answer", "")) > 10
        ]
        if len(confident_on_distractor) >= 1:
            d_ids = ", ".join(a["question_id"] for a in confident_on_distractor)
            _logger.warning(
                "答题LLM未识别干扰题: %s (confidence on distractor %s)", kp_name, d_ids
            )
            # 不 overrule verified —— 干扰题不识别是质量警告，不是阻断条件

    target_answers = [a for a in answers if a["question_id"] in target_ids]

    # Call 3: grader
    g_user = f"判分:\n题目: {json.dumps([q for q in questions if q['id'] in target_ids], ensure_ascii=False, indent=2)}\n回答: {json.dumps(target_answers, ensure_ascii=False, indent=2)}"
    g_raw = llm_client.search(VERIFIER_G_SYSTEM, g_user)
    if isinstance(g_raw, str):
        try:
            g_raw = json.loads(g_raw)
        except json.JSONDecodeError:
            return VerificationReport(kp_name, False, 0, 0, ["判分JSON解析失败"], [], [], {})
    verified = g_raw.get("verified", False)
    failed = g_raw.get("failed_topics", [])
    passed_q = sum(1 for g in g_raw.get("graded", []) if g.get("passed", False))

    # Defense 3: grading strictness
    if verified:
        uncertain_answers = [a for a in target_answers if a.get("certainty") in ("low", "uncertain")]
        if uncertain_answers:
            verified = False
            failed.append("不确定答题但判通过")
        if not g_raw.get("improvements"):
            _logger.warning("Grader passed without improvements")

    # Defense 4: model bias detection — adversarial re-evaluation
    # Only runs when Call 3 says "pass" (catching false positives)
    d4_result = {}
    if verified:
        try:
            d4_user = f"审查:\n题目: {json.dumps([q for q in questions if q['id'] in target_ids], ensure_ascii=False, indent=2)}\n回答: {json.dumps(target_answers, ensure_ascii=False, indent=2)}"
            d4_raw = llm_client.search(
                VERIFIER_D4_SYSTEM, d4_user,
                json_mode=True, temperature=1.0
            )
            d4_result = d4_raw if isinstance(d4_raw, dict) else {}
            issues = d4_result.get("issues", [])
            high_issues = [i for i in issues if i.get("severity") == "high"]
            if len(issues) >= 3 or len(high_issues) >= 1:
                verified = False
                failed.append(
                    f"D4偏差检测: {len(issues)}个问题({len(high_issues)}个高危): "
                    + "; ".join(i.get("detail", "")[:60] for i in issues[:3])
                )
        except Exception:
            pass  # D4 失败不阻断验证流程

    return VerificationReport(
        knowledge_point=kp_name,
        verified=verified,
        total_questions=len(questions),
        passed_questions=passed_q,
        failed_topics=failed,
        call1_questions=questions,
        call2_answers=answers,
        call3_grading=g_raw,
        call4_bias_check=d4_result,
    )


def _obfuscate(questions: list, distractors: list | None = None) -> tuple[list, list]:
    """打乱顺序 + 注入干扰题，返回 (shuffled, target_ids)。

    target_ids 只包含原始题目的 ID（不包含干扰题）。
    Call 3 评分者通过 target_ids 过滤，干扰题不会被评判。
    """
    pool = list(questions)
    if distractors:
        pool.extend(distractors)
    random.shuffle(pool)
    target_ids = [q["id"] for q in questions]  # 不含干扰题 ID
    return pool, target_ids


def _fetch_distractors(kp_name: str, n: int = 2) -> list[dict]:
    """从 FTS5 中取其他知识点的练习题作为干扰题。

    返回最多 n 道题（id 重命名为 D1..Dn），无可用题时返回 []。
    """
    try:
        from src.coach.curriculum.fts5_store import Fts5LessonStore
        store = Fts5LessonStore()
        all_kps = store.list_cards("")
        # 排除当前 KP
        candidates = [k for k in all_kps if k != kp_name]
        if not candidates:
            return []
        # 随机选 1 个其他 KP，取它的 exercises
        import random as _random
        other_kp = _random.choice(candidates)
        card = store.get_card("", other_kp)
        if not card:
            return []
        exercises = card.get("exercises", [])
        if not exercises:
            return []
        # 取最多 n 道，重命名 ID
        selected = _random.sample(exercises, min(n, len(exercises)))
        distractors = []
        for i, ex in enumerate(selected):
            d = dict(ex)
            d["id"] = f"D{i+1}"          # 重命名: Q1→D1, 避免与真实题冲突
            d["_distractor"] = True       # 标记为干扰题
            distractors.append(d)
        return distractors
    except Exception:
        return []  # 任何失败 → 降级


def _check_answer_jargon(answers: list, category: str, kp_name: str) -> list[str]:
    """费曼交叉校验: 如果费曼零术语，答题也不应有术语。

    返回答题中出现的术语列表。空列表 = 通过。
    """
    jargon_list = JARGON_DB.get(category, [])
    if not jargon_list:
        return []
    # 排除知识点本身的词（教"变量"不能禁止说"变量"）
    kp_words = set(kp_name.replace("赋值", "").replace("定义", ""))
    jargon_filtered = [j for j in jargon_list
                       if j not in kp_words and j not in kp_name]

    all_text = " ".join(a.get("answer", "") for a in answers)
    return [j for j in jargon_filtered if j in all_text]
