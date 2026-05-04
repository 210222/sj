"""DSL 构建器与校验器 — contracts/coach_dsl.json 对齐。"""

import json
import uuid
from pathlib import Path

_CONTRACT_PATH = Path(__file__).resolve().parent.parent.parent / "contracts" / "coach_dsl.json"

with open(_CONTRACT_PATH, encoding="utf-8") as _f:
    _CONTRACT = json.load(_f)

_ACTION_TYPE_IDS = frozenset(a["id"] for a in _CONTRACT["action_types"])
_ACTION_TYPE_SLOTS = {a["id"]: set(a["slots"]) for a in _CONTRACT["action_types"]}
_REQUIRED_FIELDS = set(_CONTRACT["required_fields"])
_VALID_DOMAIN_LEVELS = frozenset(_CONTRACT["domain_passport_levels"])
_VALID_SOURCE_TAGS = frozenset(_CONTRACT["source_tags"])


class DSLValidator:
    """DSL 动作包校验器 — 合约对齐。"""

    @staticmethod
    def validate(packet: dict) -> tuple[bool, list[str]]:
        """返回 (is_valid, errors)。"""
        errors = []

        if not isinstance(packet, dict):
            return False, ["packet must be a dict"]

        for field in _REQUIRED_FIELDS:
            if field not in packet:
                errors.append(f"missing required field: {field}")

        atype = packet.get("action_type")
        if atype is None:
            errors.append("action_type is required")
        elif atype not in _ACTION_TYPE_IDS:
            errors.append(f"unknown action_type: '{atype}'. valid: {sorted(_ACTION_TYPE_IDS)}")
        else:
            # check payload slots match
            payload = packet.get("payload", {})
            if not isinstance(payload, dict):
                errors.append(f"payload must be a dict, got {type(payload).__name__}")
            else:
                expected = _ACTION_TYPE_SLOTS.get(atype, set())
                missing = expected - set(payload.keys())
                if missing:
                    errors.append(f"payload missing slots for '{atype}': {sorted(missing)}")

        # domain_passport check
        dp = packet.get("domain_passport")
        if isinstance(dp, dict):
            level = dp.get("evidence_level")
            if level is not None and level not in _VALID_DOMAIN_LEVELS:
                errors.append(
                    f"invalid domain_passport.evidence_level: '{level}'. "
                    f"valid: {sorted(_VALID_DOMAIN_LEVELS)}"
                )
            stag = dp.get("source_tag")
            if stag is not None and stag not in _VALID_SOURCE_TAGS:
                errors.append(
                    f"invalid domain_passport.source_tag: '{stag}'. "
                    f"valid: {sorted(_VALID_SOURCE_TAGS)}"
                )

        return len(errors) == 0, errors


class DSLBuilder:
    """DSL 动作包构建器 — 合约对齐。"""

    @staticmethod
    def build(action: dict, trace_id: str | None = None) -> dict:
        """构建合法的 DSL 动作包。

        Args:
            action: dict with keys: action_type, payload, intent, domain_passport
            trace_id: optional, auto-generated UUID if None

        Returns:
            DSL packet dict with all required fields
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        atype = action.get("action_type", "suggest")
        payload = action.get("payload", {})

        if not isinstance(payload, dict):
            payload = {}

        intent = action.get("intent", "general")
        domain_passport = action.get("domain_passport", {})

        if not isinstance(domain_passport, dict):
            domain_passport = {}

        # ensure defaults for domain_passport
        domain_passport.setdefault("domain", "general")
        domain_passport.setdefault("evidence_level", "medium")
        domain_passport.setdefault("source_tag", "rule")
        domain_passport.setdefault("epistemic_warning", None)

        return {
            "action_type": atype,
            "payload": payload,
            "trace_id": trace_id,
            "intent": intent,
            "domain_passport": domain_passport,
        }
