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


DIGEST_SEARCH_SYSTEM = """你是教学研究员。搜索 {kp} 的教学资料。

搜索方向:
1. {kp} 的准确定义（找 2-3 个权威源交叉验证）
2. 初学者在 {kp} 上最常见的 3-5 个误解
3. 学生在 {kp} 上最容易卡住的 2-3 个地方
4. 初学者在学习 {kp} 时容易走的 2-3 条弯路
5. 学习 {kp} 必须的前置知识

学科: {subject}（{category}）
输出为纯文本，不要 JSON。"""

DIGEST_SEARCH_USER = """请搜索 {subject} 中 "{kp}" 的教学资料。

重点搜索:
- 官方文档中的定义
- StackOverflow 上关于 {kp} 的高赞误区
- 教学博客中提到的常见卡点

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

DIGEST_USER = """为 {subject}（{category}）的 "{kp}" 提取教学信息。

搜索结果:
{search_text}

请提取 misconception、sticking_point、detour、prerequisite。
每个条目必须具体、可操作、有搜索依据。"""


def digest(kp_name: str, search_text: str, llm_client,
           subject: str = "", category: str = "") -> "DigestedOutput":
    """消化: 搜索 → 提取结构化信息 → 校验。"""
    from src.coach.curriculum.models import DigestedOutput

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

    _logger.debug("digest complete for '%s': def=%dchars, mis=%d, stick=%d, det=%d, pre=%d",
                  kp_name, len(str(raw.get("definition", ""))),
                  len(raw.get("misconceptions") or []),
                  len(raw.get("sticking_points") or []),
                  len(raw.get("detours") or []),
                  len(raw.get("prerequisites") or []))
    return DigestedOutput(
        knowledge_point=kp_name,
        definition=str(raw.get("definition", "")),
        misconceptions=_ensure_list(raw.get("misconceptions")),
        sticking_points=_ensure_list(raw.get("sticking_points")),
        detours=_ensure_list(raw.get("detours")),
        prerequisites=_ensure_list(raw.get("prerequisites")),
    )


def search_knowledge(kp_name: str, llm_client,
                     subject: str = "", category: str = "") -> str:
    """搜索知识点的原始教学资料。"""
    system = DIGEST_SEARCH_SYSTEM.replace("{kp}", kp_name)
    system = system.replace("{subject}", subject or kp_name)
    system = system.replace("{category}", category)
    user = DIGEST_SEARCH_USER.replace("{subject}", subject or kp_name)
    user = user.replace("{kp}", kp_name)

    resp = llm_client.search(system, user, json_mode=False)
    if isinstance(resp, dict):
        text = resp.get("raw_text", json.dumps(resp, ensure_ascii=False))
    else:
        text = str(resp)
    _logger.debug("search_knowledge for '%s' returned %d chars", kp_name, len(text))
    return text
