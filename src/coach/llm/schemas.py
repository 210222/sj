"""LLM 输出 schema 定义 + 校验 + DSL 对齐.

LLM 生成的 payload 必须符合 DSL schema，否则回退规则模式。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

_logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM 原始响应结构."""
    content: str
    model: str = ""
    tokens_used: int = 0
    finish_reason: str = "stop"

    def to_payload(self) -> dict:
        """将 LLM 内容转为 DSL payload 字典."""
        try:
            data = json.loads(self.content)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return {"statement": self.content.strip()}


class LLMOutputValidator:
    """LLM 输出校验器 — 确保输出符合 DSL 合约."""

    REQUIRED_KEYS = {"statement"}
    VALID_KEYS = {"statement", "question", "step", "option",
                  "hint", "difficulty", "alternatives",
                  "evidence_id", "source_tag"}

    @classmethod
    def validate(cls, payload: dict) -> tuple[bool, list[str]]:
        """校验 LLM 生成的 payload. Returns (is_valid, errors)."""
        errors = []
        if not isinstance(payload, dict):
            return False, ["payload must be a dict"]

        if "statement" not in payload:
            errors.append("missing 'statement' field")
        elif not isinstance(payload["statement"], str):
            errors.append("'statement' must be a string")
        elif not payload["statement"].strip():
            errors.append("'statement' must not be empty")

        return len(errors) == 0, errors

    # Phase 22: Action-Type 特定必填字段
    ACTION_TYPE_REQUIRED_FIELDS = {
        "probe": {"question", "expected_answer"},
        "scaffold": {"steps"},
        "challenge": {"objective", "difficulty"},
        "suggest": {"options"},
        "reflect": {"question"},
        "defer": {"resume_condition"},
        "pulse": {"accept_label", "rewrite_label"},
        "excursion": {"bias_disabled"},
    }

    @classmethod
    def validate_by_action_type(cls, payload: dict, action_type: str) -> list[str]:
        """校验 action_type 特定的必填字段。

        Returns: 缺失字段名称列表（空列表 = 全部通过）
        """
        required = cls.ACTION_TYPE_REQUIRED_FIELDS.get(action_type, set())
        return [f"missing '{f}' for action_type '{action_type}'"
                for f in required if f not in payload]

    @classmethod
    def validate_with_type(cls, payload: dict, action_type: str | None = None
                           ) -> tuple[bool, list[str]]:
        """校验并附带 action_type 特定检查。"""
        is_valid, errors = cls.validate(payload)
        if action_type:
            type_errors = cls.validate_by_action_type(payload, action_type)
            errors.extend(type_errors)
        return len(errors) == 0, errors


# ── S2.1: DSL Schema Aligner ─────────────────────────────────

# 从 DSL 合约加载 action_type → slots 映射
def _load_dsl_slots() -> dict[str, set[str]]:
    from pathlib import Path
    contract_path = Path(__file__).resolve().parent.parent.parent.parent / "contracts" / "coach_dsl.json"
    try:
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        return {a["id"]: set(a["slots"]) for a in contract.get("action_types", [])}
    except Exception:
        _logger.warning("Failed to load DSL contract, using empty slots")
        return {}

_ACTION_TYPE_SLOTS: dict[str, set[str]] = _load_dsl_slots()
_UNIVERSAL_KEYS = {"statement", "question", "hint", "difficulty", "steps", "topics"}


class LLMDSLAligner:
    """将 LLM 输出对齐到 DSL schema.

    核心逻辑:
    1. LLM 原始 payload → 提取合法字段（丢弃 DSL 不认识的字段）
    2. 校验 payload slots 与 action_type 是否匹配（来自 coach_dsl.json）
    3. 缺失 slot 用缺省值填充
    4. 返回对齐后的 payload + 对齐报告
    """

    @classmethod
    def align(cls, raw_payload: dict, action_type: str) -> tuple[dict, dict]:
        """对齐 LLM payload 到 DSL schema.

        Returns:
            (aligned_payload, alignment_report)
        """
        allowed_slots = _ACTION_TYPE_SLOTS.get(action_type, set()) | _UNIVERSAL_KEYS
        aligned: dict = {}
        dropped: list[str] = []
        filled: dict = {}

        for key, value in raw_payload.items():
            if key in allowed_slots:
                aligned[key] = value
            else:
                dropped.append(key)

        valid = len(aligned) > 0

        # 确保 statement 存在
        if "statement" not in aligned:
            # 尝试从其他文本字段迁移
            for text_key in ("question", "option", "step", "hint", "reason"):
                if text_key in aligned:
                    aligned["statement"] = aligned[text_key]
                    filled["statement"] = f"migrated_from_{text_key}"
                    break
            if "statement" not in aligned:
                aligned["statement"] = ""
                filled["statement"] = "default_empty"
                valid = False

        # Phase 11: scaffold/suggest 缺 steps 时自动生成
        if action_type in ("scaffold", "suggest") and "steps" not in aligned:
            generated = cls._generate_steps(aligned.get("statement", ""))
            if generated:
                aligned["steps"] = generated
                filled["steps"] = "auto_generated_from_statement"

        report = {
            "dropped_fields": dropped,
            "filled_slots": filled,
            "action_type": action_type,
            "allowed_slots": sorted(allowed_slots),
            "valid": valid,
        }
        return aligned, report

    @staticmethod
    def _generate_steps(statement: str) -> list[dict] | None:
        """从 statement 文本中自动提取步骤。按句子边界 + 序列标记分割。"""
        if not statement or len(statement) < 30:
            return None
        import re
        # 按序列标记分割: "1.", "第一步", "Step 1", "首先/然后/最后"
        markers = re.split(
            r'(?:(?:第)?[一二三四五六七八九十\d]+[步条个]|'
            r'(?:\d+[.\)]\s)|'
            r'(?:Step\s*\d)|'
            r'(?:step\s*\d)|'
            r'(?:First[,，\s])|(?:first[,，\s])|'
            r'(?:Then[,，\s])|(?:then[,，\s])|'
            r'(?:Next[,，\s])|(?:next[,，\s])|'
            r'(?:Finally[,，\s])|(?:finally[,，\s])|'
            r'(?:首先[,，\s])|'
            r'(?:然后[,，\s])|'
            r'(?:接下来[,，\s])|'
            r'(?:最后[,，\s])|'
            r'(?:接着[,，\s]))',
            statement)
        markers = [m.strip() for m in markers if m.strip()]
        if len(markers) < 2:
            # 尝试按句号分割
            sentences = [s.strip() for s in statement.split("。") if s.strip()]
            if len(sentences) >= 2 and len(sentences) <= 5:
                return [
                    {"order": i + 1, "action": s[:120], "expected": ""}
                    for i, s in enumerate(sentences[:4])
                ]
            return None
        result = []
        for i, text in enumerate(markers[:4]):
            cleaned = text.strip().rstrip(",，。.")
            if cleaned:
                result.append(
                    {"order": i + 1, "action": cleaned[:120], "expected": ""})
        return result if len(result) >= 2 else None


# ── S2.2: ActionType 强制 ─────────────────────────────────

def force_action_type(payload: dict, rule_action_type: str) -> dict:
    """确保 LLM payload 的 action_type 字段不被 LLM 篡改.
    移除 payload 中任何 llm_action_type 或类似的 LLM 自选字段.
    """
    payload.pop("action_type", None)
    payload.pop("llm_action_type", None)
    payload.pop("_action_type", None)
    return payload
