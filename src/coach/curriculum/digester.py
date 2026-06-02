"""消化阶段: 搜索知识点资料 → 提取结构化教学信息."""

import json
import logging

_logger = logging.getLogger(__name__)


def _ensure_list(val):
    """Ensure val is a list of strings. Defends against LLM returning
    a string or None instead of a list for array fields."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [str(item) for item in val]
    return [str(val)]


def _classify_kp(kp_name: str, search_text: str) -> str:
    """从搜索文本和 KP 名称判定类型 — 不调 LLM, 零成本."""
    procedural_signals = [
        "安装", "配置", "下载", "搭建", "环境变量", "命令行", "终端",
        "第一步", "第二步", "打开", "点击", "选择", "设置", "IDE", "pip", "conda",
        "运行", "启动", "登录", "注册", "创建项目", "新建"
    ]
    conceptual_signals = [
        "常见误解", "误解", "原理", "底层", "机制", "区别", "对比",
        "本质", "核心概念", "理解", "误区", "概念"
    ]
    factual_signals = [
        "关键字", "语法", "规则", "保留字", "运算符", "优先级",
        "数据类型", "列表", "字典", "元组", "集合"
    ]
    text = kp_name + search_text[:1000]
    proc_score = sum(1 for s in procedural_signals if s in text)
    conc_score = sum(1 for s in conceptual_signals if s in text)
    fact_score = sum(1 for s in factual_signals if s in text)

    scores = {"procedural": proc_score, "conceptual": conc_score, "factual": fact_score}
    best = max(scores, key=scores.get)
    if scores[best] >= 2 and scores[best] >= sum(scores.values()) * 0.5:
        return best
    return "unknown"


def _pre_classify_kp(kp_name: str) -> str:
    """从 KP 名称做粗分类 — 不调 LLM, 零成本。用于选搜索 prompt。"""
    proc_kw = ["安装", "配置", "搭建", "下载", "环境", "部署", "IDE", "pip", "conda",
               "命令行", "终端", "登录", "注册", "创建", "新建", "启动", "运行"]
    fact_kw = ["关键字", "语法", "运算符", "优先级", "保留字", "数据类型",
               "列表", "字典", "元组", "集合", "字符串", "整数", "布尔"]
    for kw in proc_kw:
        if kw in kp_name:
            return "procedural"
    for kw in fact_kw:
        if kw in kp_name:
            return "factual"
    return "universal"  # v6: 默认 universal, 走 UNIVERSAL_SEARCH_SYSTEM


UNIVERSAL_SEARCH_SYSTEM = """你是教学研究员。为 {kp} 搜索教学资料。

搜索策略（根据 {kp} 性质，覆盖适用的维度）:
1. 定义（2-3个权威源交叉验证）
2. 常见误解或操作错误（至少 3 条，来自 StackOverflow/Reddit/教程评论）
3. 卡点/易混点（2-3 个具体环节）
4. 弯路或低效学习方法
5. 前置知识

关键: 不仅搜索官方文档，重点搜索学习者社区（StackOverflow/Reddit/CSDN/教程评论区）
中关于 {kp} 的实际问题和错误。输出为纯文本。"""

RETRY_SEARCH_SYSTEM = """你是教学研究员。这次搜索需要更深入。

上一轮搜索可能遗漏了 {kp} 的学习者常见错误。请专门搜索:
- StackOverflow 上关于 {kp} 的高赞问题和回答
- Reddit r/learnprogramming 或类似社区关于 {kp} 的讨论
- 教程评论区中学习者反映的实际困难
- "{kp} common mistakes" "{kp} beginner confused" 等英文搜索词

输出至少 5 条具体的错误/误解/卡点。纯文本。"""

PROCEDURAL_SEARCH_SYSTEM = """你是技术文档研究员。搜索 {kp} 的安装/配置资料。

搜索方向:
1. {kp} 在不同平台上的具体安装步骤（Windows/Mac/Linux）
2. 安装过程中常见的 3-5 个错误和解决方案
3. 版本兼容性问题和替代方案
4. 配置完成后如何验证安装成功
5. 学习 {kp} 必须的前置条件

学科: {subject}（{category}）
输出为纯文本，不要 JSON。"""

PROCEDURAL_SEARCH_USER = """请搜索 {subject} 中 "{kp}" 的安装配置资料。

重点搜索:
- 官方安装文档
- StackOverflow 上的常见安装错误
- 不同操作系统的差异

输出为纯文本摘要，列出所有找到的关键信息。"""

FACTUAL_SEARCH_SYSTEM = """你是语言规范研究员。搜索 {kp} 的语法规则资料。

搜索方向:
1. {kp} 的精确定义和语法格式（从官方文档交叉验证）
2. {kp} 与相似概念的对比区别（常见易混点）
3. {kp} 的使用场景和边界条件
4. {kp} 的记忆技巧
5. 学习 {kp} 必须的前置知识

学科: {subject}（{category}）
输出为纯文本，不要 JSON。"""

FACTUAL_SEARCH_USER = """请搜索 {subject} 中 "{kp}" 的语法规则资料。

重点搜索:
- 官方语言规范中的定义
- {kp} 与其他概念的对比区别
- 常见误用场景

输出为纯文本摘要，列出所有找到的关键信息。"""

DIGEST_SYSTEM = """你是教学研究员。根据搜索结果，提取 {kp} 的结构化教学信息。

输出 JSON（严格按此格式，不得修改结构）:

{{
  "definition": "{kp} 的精确定义（1-2句话，从搜索结果中交叉验证得出）",
  "misconceptions": [
    "误解1: 具体的错误理解内容",
    "误解2: 另一个常见错误",
    "误解3: ..."
  ],
  "sticking_points": [
    "卡点1: 学生容易卡在哪个环节",
    "卡点2: ..."
  ],
  "detours": [
    "弯路1: 初学者常走的弯路",
    "弯路2: 学了正确内容后再回头看这个内容觉得浪费时间的"
  ],
  "prerequisites": [
    "前置知识1",
    "前置知识2"
  ]
}}

约束:
- misconceptions ≥ 3 条，每条必须具体（不是"理解不深"这种泛泛描述）
- sticking_points ≥ 2 条
- detours ≥ 2 条
- 所有内容必须能从搜索结果中找到依据
- 只输出 JSON，不输出其他文字"""

PROCEDURAL_DIGEST_SYSTEM = """你是教学研究员。根据搜索结果，提取 {kp} 的结构化教学信息。

注意: {kp} 是操作型知识点（安装/配置/搭建类）。不要编造"概念误解"——操作型没有认知误解。

输出 JSON:
{{
  "knowledge_type": "procedural",
  "definition": "{kp} 的用途和必要性（1-2句话）",
  "common_errors": [
    "操作错误1: 具体的错误操作和后果",
    "操作错误2: ...",
    "操作错误3: ..."
  ],
  "environment_diffs": [
    "环境差异1: 不同平台/版本的具体差异",
    "环境差异2: ..."
  ],
  "alternatives": [
    "替代方案1: 不用这个工具/命令的替代方式"
  ],
  "prerequisites": ["前置知识1", "前置知识2"]
}}

约束:
- common_errors ≥ 1 条（操作型放宽）
- environment_diffs ≥ 1 条
- 只输出 JSON，不输出其他文字"""

FACTUAL_DIGEST_SYSTEM = """你是教学研究员。根据搜索结果，提取 {kp} 的结构化教学信息。

注意: {kp} 是事实型知识点（语法规则/关键字列表类）。不需要编造"概念误解"或"弯路"。

输出 JSON:
{{
  "knowledge_type": "factual",
  "definition": "{kp} 的精确定义和用途（1-2句话）",
  "common_confusions": [
    "易混点1: 与哪个概念容易混淆, 区别是什么",
    "易混点2: ...",
    "易混点3: ..."
  ],
  "memory_aids": [
    "记忆技巧1: 帮助记忆的规律或口诀",
    "记忆技巧2: ..."
  ],
  "prerequisites": ["前置知识1", "前置知识2"]
}}

约束:
- common_confusions ≥ 2 条（事实型放宽为 ≥ 1 条即可）
- memory_aids ≥ 1 条
- 只输出 JSON，不输出其他文字"""

DIGEST_USER = """为 {subject}（{category}）的 "{kp}" 提取教学信息。

搜索结果:
{search_text}

请提取 misconception、sticking_point、detour、prerequisite。
每个条目必须具体、可操作、有搜索依据。"""


def digest(kp_name: str, search_text: str, llm_client,
           subject: str = "", category: str = "") -> "DigestedOutput":
    """消化: 类型判定 → 选 prompt → LLM 提取结构化信息 → 字段映射 → 校验。"""
    from src.coach.curriculum.models import DigestedOutput

    kp_type = _classify_kp(kp_name, search_text)
    if kp_type == "procedural":
        system = PROCEDURAL_DIGEST_SYSTEM.replace("{kp}", kp_name)
    elif kp_type == "factual":
        system = FACTUAL_DIGEST_SYSTEM.replace("{kp}", kp_name)
    else:
        system = DIGEST_SYSTEM.replace("{kp}", kp_name)

    user = DIGEST_USER.replace("{subject}", subject or kp_name)
    user = user.replace("{category}", category)
    user = user.replace("{kp}", kp_name)
    truncated = search_text[:3000]
    if len(search_text) > 3000:
        truncated += "\n...[truncated]"
        _logger.debug("search_text truncated from %d to 3000 chars for '%s'",
                      len(search_text), kp_name)
    user = user.replace("{search_text}", truncated)

    raw = llm_client.search(system, user)
    if isinstance(raw, str):
        raw = json.loads(raw)

    # 统一字段映射
    misconceptions = _ensure_list(
        raw.get("misconceptions") or raw.get("common_errors") or raw.get("common_confusions") or []
    )
    sticking_points = _ensure_list(
        raw.get("sticking_points") or raw.get("steps") or []
    )
    detours = _ensure_list(
        raw.get("detours") or raw.get("environment_diffs") or raw.get("memory_aids") or []
    )

    _logger.debug("digest complete for '%s' (type=%s): def=%dchars, mis=%d, stick=%d, det=%d, pre=%d",
                  kp_name, kp_type, len(str(raw.get("definition", ""))),
                  len(misconceptions), len(sticking_points), len(detours),
                  len(raw.get("prerequisites") or []))
    return DigestedOutput(
        knowledge_point=kp_name,
        definition=str(raw.get("definition", "")),
        misconceptions=misconceptions,
        sticking_points=sticking_points,
        detours=detours,
        prerequisites=_ensure_list(raw.get("prerequisites")),
        knowledge_type=kp_type,
    )


def search_knowledge(kp_name: str, llm_client,
                     subject: str = "", category: str = "",
                     attempt: int = 1) -> str:
    """搜索知识点的原始教学资料。Phase 92 v6: 重试策略变化 + 默认 universal。"""
    kp_type = _pre_classify_kp(kp_name)

    if attempt >= 2:
        # 重试: 更激进的搜索策略, 专门找学习者社区
        system = RETRY_SEARCH_SYSTEM.replace("{kp}", kp_name)
    elif kp_type == "procedural":
        system = PROCEDURAL_SEARCH_SYSTEM.replace("{kp}", kp_name)
    elif kp_type == "factual":
        system = FACTUAL_SEARCH_SYSTEM.replace("{kp}", kp_name)
    else:
        system = UNIVERSAL_SEARCH_SYSTEM.replace("{kp}", kp_name)

    system = system.replace("{subject}", subject or kp_name)
    system = system.replace("{category}", category)

    # 重试轮: RETRY_SEARCH 有自己的 user prompt 模式
    if attempt >= 2:
        user = f"为 {kp_name} 做深度教学搜索（第{attempt}轮）。重点找学习者社区的实际错误和卡点。"
    elif kp_type == "procedural":
        user = PROCEDURAL_SEARCH_USER.replace("{subject}", subject or kp_name)
        user = user.replace("{kp}", kp_name)
    elif kp_type == "factual":
        user = FACTUAL_SEARCH_USER.replace("{subject}", subject or kp_name)
        user = user.replace("{kp}", kp_name)
    else:
        user = f"为 {subject or kp_name} 的 \"{kp_name}\" 搜索教学资料。覆盖全部适用维度。"

    resp = llm_client.search(system, user, json_mode=False)
    if isinstance(resp, dict):
        text = resp.get("raw_text", json.dumps(resp, ensure_ascii=False))
    else:
        text = str(resp)
    _logger.debug("search_knowledge for '%s' (type=%s, attempt=%d) returned %d chars",
                  kp_name, kp_type, attempt, len(text))
    return text
