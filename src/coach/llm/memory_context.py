"""S4.1 — 对话历史 + 长期记忆注入 LLM Prompt.

设计原则:
- Prompt 预算管理: 60% 上下文 / 40% 生成
- 选择性注入: 只注入 has_info=True 的轮次
- 不注入原始 LLM 输出（防记忆污染）
"""

from __future__ import annotations


def extract_recent_history(
    interaction_history: list[dict],
    limit: int = 5,
    max_chars: int = 400,
) -> list[dict]:
    """从交互历史中提取最近 N 轮，附带意图标签.

    Args:
        interaction_history: CoachAgent._interaction_history
        limit: 最大轮次数
        max_chars: 总字数上限

    Returns:
        [{"intent": "scaffold", "state": "stable", "turn": 3}, ...]
    """
    if not interaction_history:
        return []

    recent = interaction_history[-limit:]
    result: list[dict] = []
    total_chars = 0

    for i, entry in enumerate(reversed(recent)):
        intent = entry.get("intent", "general")
        if intent == "general" and entry.get("confidence", 0.5) < 0.3:
            continue  # 无信息轮次跳过

        item = {
            "intent": intent,
            "state": entry.get("state", "stable"),
            "turn": len(interaction_history) - i,
        }
        result.insert(0, item)
        total_chars += len(intent)
        if total_chars > max_chars:
            break

    return result


def extract_memory_snippets(
    session_memory,
    session_id: str,
    limit: int = 3,
    max_chars: int = 200,
) -> list[str]:
    """从会话记忆中提取相关片段用于 prompt 注入.

    Args:
        session_memory: SessionMemory 实例
        session_id: 当前会话 ID
        limit: 最大记忆条数
        max_chars: 总字数上限

    Returns:
        ["上次学到: Python循环", "感兴趣: 算法题", ...]
    """
    status = {"source": "memory", "status": "unknown"}
    try:
        raw = session_memory.recall(
            intent=None, user_state=None, limit=limit)
        if isinstance(raw, list):
            snippets = []
            total = 0
            for item in raw:
                if isinstance(item, dict):
                    text = item.get("action_type", "") or item.get(
                        "summary", "")
                else:
                    text = str(item)
                if text and text != "general":
                    snippets.append(text)
                    total += len(text)
                    if total > max_chars:
                        break
            status["status"] = "hit" if snippets else "miss"
            status["count"] = len(snippets)
            return snippets, status
        status["status"] = "miss"
        status["error"] = "recall returned non-list"
    except Exception as e:
        status["status"] = "error"
        status["error"] = str(e)[:200]
    return [], status


def format_history_for_prompt(history: list[dict]) -> str:
    """将历史记录格式化为 prompt 可用的文本，包含用户消息原文."""
    if not history:
        return "（无历史记录）"
    lines = []
    for h in history:
        data = h.get("data", {}) if isinstance(h, dict) else {}
        user_msg = data.get("user_input", "")
        intent = h.get("intent", "general")
        action = data.get("action_type", "")
        if user_msg:
            lines.append(f"- 第{h.get('turn', '?')}轮: 用户说\"{user_msg[:80]}\" (意图:{intent}, 策略:{action})")
        else:
            lines.append(f"- 第{h.get('turn', '?')}轮: {intent}")
    return "\n".join(lines)


def format_memory_for_prompt(snippets: list[str]) -> str:
    """将记忆片段格式化为 prompt 文本."""
    if not snippets:
        return "（无相关记忆）"
    return "\n".join(f"- {s}" for s in snippets)
