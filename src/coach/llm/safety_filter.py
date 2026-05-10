"""S2.2 — LLM 内容安全过滤 + ActionType 强制.

职责:
1. 过滤 payload 中的 forbidden_phrases
2. 强制 action_type（规则引擎的 action_type 不可被 LLM 覆盖）
3. 返回过滤报告
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class LLMSafetyFilter:
    """LLM 内容安全过滤器."""

    @staticmethod
    def filter_payload(
        payload: dict,
        forbidden_phrases: list[str],
    ) -> tuple[dict, list[str]]:
        """递归过滤 payload 中所有文本字段的禁止短语.

        Returns:
            (filtered_payload, triggered_phrases)
        """
        triggered: list[str] = []
        filtered: dict = {}
        for key, value in payload.items():
            if isinstance(value, str):
                val = value
                for phrase in forbidden_phrases:
                    if phrase in val:
                        val = val.replace(phrase, "[已过滤]")
                        triggered.append(phrase)
                filtered[key] = val
            elif isinstance(value, dict):
                sub, sub_trig = LLMSafetyFilter.filter_payload(
                    value, forbidden_phrases)
                filtered[key] = sub
                triggered.extend(sub_trig)
            elif isinstance(value, list):
                items: list = []
                for v in value:
                    if isinstance(v, (str, dict)):
                        item, item_trig = LLMSafetyFilter.filter_payload(
                            {"_item": v}, forbidden_phrases)
                        items.append(item["_item"])
                        triggered.extend(item_trig)
                    else:
                        items.append(v)
                filtered[key] = items
            else:
                filtered[key] = value
        return filtered, triggered

    @staticmethod
    def enforce_action_type(
        payload: dict,
        rule_action_type: str,
    ) -> dict:
        """强制确保 action_type 不被 LLM 篡改.
        移除非对应当前 action_type 的字段.
        """
        from src.coach.llm.schemas import _ACTION_TYPE_SLOTS, _UNIVERSAL_KEYS

        allowed = _ACTION_TYPE_SLOTS.get(rule_action_type, set()) | _UNIVERSAL_KEYS
        cleaned: dict = {}
        dropped = []
        for key, value in payload.items():
            if key in allowed:
                cleaned[key] = value
            else:
                dropped.append(key)
        if dropped:
            _logger.debug(
                "LLMSafetyFilter dropped %d fields not allowed for action_type=%s: %s",
                len(dropped), rule_action_type, dropped)
        return cleaned
