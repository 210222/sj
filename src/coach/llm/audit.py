"""S2.3 — LLM 门禁阻断审计日志.

当 LLM payload 被 gate 阻断时，记录原始 payload 到审计日志。
不修改门禁逻辑 — 只读记录。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class LLMGateAuditRecord:
    """单条 LLM 门禁审计记录."""
    event_id: str
    timestamp_utc: str
    session_id: str
    trace_id: str
    gate_id: int
    gate_name: str
    gate_decision: str  # BLOCK | WARN
    action_type: str
    llm_model: str = ""
    llm_tokens: int = 0
    payload_snippet: str = ""  # payload 前 500 字符
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMGateAuditor:
    """LLM 门禁阻断审计器.

    记录 LLM 输出的 payload 在 gate 阻断时的完整上下文，
    用于后续分析哪些 LLM 输出内容触发了安全门禁。
    """

    def __init__(self, max_records: int = 200):
        self._records: list[LLMGateAuditRecord] = []
        self._max_records = max_records

    def record_block(
        self,
        session_id: str,
        trace_id: str,
        gate_id: int,
        gate_name: str,
        gate_decision: str,
        action_type: str,
        payload: dict,
        llm_model: str = "",
        llm_tokens: int = 0,
    ) -> None:
        """记录一次门禁阻断事件."""
        if gate_decision not in ("BLOCK", "FREEZE"):
            return

        payload_str = json.dumps(payload, ensure_ascii=False, default=str)
        record = LLMGateAuditRecord(
            event_id=f"llm-gate-{int(time.time() * 1000)}",
            timestamp_utc=time.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            session_id=session_id,
            trace_id=trace_id,
            gate_id=gate_id,
            gate_name=gate_name,
            gate_decision=gate_decision,
            action_type=action_type,
            llm_model=llm_model,
            llm_tokens=llm_tokens,
            payload_snippet=payload_str[:500],
            blocked_reason=f"Gate {gate_id} ({gate_name}) → {gate_decision}",
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)
        _logger.info(
            "LLM gate audit: %s — gate=%d(%s) decision=%s",
            record.event_id, gate_id, gate_name, gate_decision)

    def get_records(
        self, session_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """获取审计记录，可按 session 过滤."""
        records = self._records
        if session_id:
            records = [r for r in records if r.session_id == session_id]
        return [r.to_dict() for r in records[-limit:]]

    def clear(self) -> None:
        self._records.clear()


# 全局单例
_gate_auditor: LLMGateAuditor | None = None


def get_gate_auditor() -> LLMGateAuditor:
    global _gate_auditor
    if _gate_auditor is None:
        _gate_auditor = LLMGateAuditor()
    return _gate_auditor
