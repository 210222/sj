"""S4.1 — 对话历史 + 长期记忆注入 LLM Prompt.

设计原则:
- Prompt 预算管理: 60% 上下文 / 40% 生成
- 选择性注入: 只注入 has_info=True 的轮次
- 不注入原始 LLM 输出（防记忆污染）
"""

from __future__ import annotations

from typing import Any


def extract_recent_history(
    interaction_history: list[dict],
    limit: int = 12,
    max_chars: int = 2400,
) -> list[dict]:
    """从交互历史中提取最近 N 轮，附带意图标签."""
    if not interaction_history:
        return []

    recent = interaction_history[-limit:]
    result: list[dict] = []
    total_chars = 0

    for i, entry in enumerate(reversed(recent)):
        intent = entry.get("intent", "general")
        if intent == "general" and entry.get("confidence", 0.5) < 0.3:
            continue

        item = {
            "intent": intent,
            "state": entry.get("state", "stable"),
            "turn": len(interaction_history) - i,
        }
        entry_chars = len(intent) + len(str(entry.get("state", "")))
        if total_chars + entry_chars > max_chars and result:
            break
        result.insert(0, item)
        total_chars += entry_chars

    return result


def extract_memory_snippets(
    session_memory,
    session_id: str,
    limit: int = 6,
    max_chars: int = 1200,
    query: str = "",
) -> tuple[list[str], dict]:
    """从会话记忆中提取高优先级片段用于 prompt 注入."""
    status = {
        "source": "memory",
        "status": "unknown",
        "hits": 0,
        "session_id": session_id,
        "query": query[:80],
    }
    try:
        raw = session_memory.recall(intent=None, user_state=None, limit=max(limit * 3, 12))
        if not isinstance(raw, list):
            status["status"] = "miss"
            status["error"] = "recall returned non-list"
            return [], status

        filtered = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            data = item.get("data", {})
            if data.get("session_id") != session_id:
                continue
            filtered.append(item)

        ranked = sorted(
            filtered,
            key=lambda item: _score_memory_item(item, query=query),
            reverse=True,
        )

        snippets: list[str] = []
        seen: set[str] = set()
        total = 0
        for item in ranked:
            text = _extract_item_text(item)
            normalized = text.lower().strip()
            if not text or normalized in seen:
                continue
            entry_len = len(text)
            if total + entry_len > max_chars and snippets:
                break
            snippets.append(text)
            seen.add(normalized)
            total += entry_len
            if len(snippets) >= limit:
                break

        status["status"] = "hit" if snippets else "miss"
        status["hits"] = len(snippets)
        status["candidates"] = len(filtered)
        return snippets, status
    except Exception as e:
        status["status"] = "error"
        status["error"] = str(e)[:200]
        return [], status


def build_retention_bundle(
    *,
    session_memory,
    session_id: str,
    user_query: str,
    history: list[dict] | None = None,
    progress_summary: str | None = None,
    context_summary: str | None = None,
    limit_history: int = 12,
    limit_memory: int = 6,
) -> dict:
    """构建变化层保留包，统一 history/memory/summary/progress 的提取与元数据."""
    raw_history = history or []
    raw_history_count = len(raw_history)
    retained_history = _select_relevant_history(
        raw_history,
        query=user_query,
        limit=limit_history,
    )
    memory_snippets, memory_status = extract_memory_snippets(
        session_memory,
        session_id,
        limit=limit_memory,
        query=user_query,
    )

    # Phase 36: retention observability
    duplicate_dropped = max(0, raw_history_count - len(retained_history))
    has_progress = bool(progress_summary)
    has_context = bool(context_summary)

    return {
        "history": retained_history,
        "memory_snippets": memory_snippets,
        "progress_summary": progress_summary or "",
        "context_summary": context_summary or "",
        "memory_status": {
            **memory_status,
            "history_hits": len(retained_history),
            "has_progress_summary": has_progress,
            "has_context_summary": has_context,
        },
        "retention_observability": {
            "retention_history_hits": len(retained_history),
            "retention_memory_hits": len(memory_snippets),
            "retention_duplicate_dropped": duplicate_dropped,
            "retention_budget_history_limit": limit_history,
            "retention_budget_memory_limit": limit_memory,
            "retention_progress_included": has_progress,
            "retention_context_summary_included": has_context,
            "session_scoped": True,
        },
    }


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
        ai_response = data.get("ai_response", "")
        if user_msg:
            line = f"- 第{h.get('turn', '?')}轮: 用户说\"{user_msg[:160]}\" (意图:{intent}, 策略:{action})"
            if ai_response:
                line += f" -> 教学摘要:{ai_response[:160]}"
            lines.append(line)
        else:
            lines.append(f"- 第{h.get('turn', '?')}轮: {intent}")
    return "\n".join(lines)


def format_memory_for_prompt(snippets: list[str]) -> str:
    """将记忆片段格式化为 prompt 文本."""
    if not snippets:
        return "（无相关记忆）"
    return "\n".join(f"- {s}" for s in snippets)


def _extract_item_text(item: dict) -> str:
    data = item.get("data", {}) if isinstance(item, dict) else {}
    ai_response = str(data.get("ai_response", "") or "").strip()
    user_input = str(data.get("user_input", "") or "").strip()
    action_type = str(data.get("action_type", "") or "").strip()
    if ai_response:
        return f"上轮教学[{action_type or 'unknown'}]: {ai_response[:240]}"
    if user_input:
        return f"用户提到: {user_input[:200]}"
    if action_type:
        return f"最近策略: {action_type}"
    return ""


def _score_memory_item(item: dict, query: str = "") -> float:
    data = item.get("data", {}) if isinstance(item, dict) else {}
    user_input = str(data.get("user_input", "") or "")
    ai_response = str(data.get("ai_response", "") or "")
    action_type = str(data.get("action_type", "") or "")
    turn_index = int(data.get("turn_index") or 0)
    score = 0.0
    if ai_response:
        score += 3.0
    if action_type and action_type != "suggest":
        score += 1.0
    if user_input:
        score += min(len(user_input) / 80.0, 1.5)
    if query:
        q = query.lower()
        for candidate in (user_input.lower(), ai_response.lower(), action_type.lower()):
            if q and q in candidate:
                score += 1.2
    score += min(turn_index / 10.0, 1.0)
    return score


def _select_relevant_history(history: list[dict], query: str, limit: int) -> list[dict]:
    if not history:
        return []
    ranked = sorted(
        history,
        key=lambda item: _score_memory_item(item, query=query),
        reverse=True,
    )
    selected: list[dict] = []
    seen: set[str] = set()
    for item in ranked:
        data = item.get("data", {}) if isinstance(item, dict) else {}
        key = (str(data.get("user_input", ""))[:80] + "|" + str(data.get("action_type", ""))).lower()
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda item: item.get("ts", 0.0))
