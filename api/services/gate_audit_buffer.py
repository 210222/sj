"""GateRingBuffer — 内存环形缓冲区，存储 pipeline 8 门禁状态 + 审计日志.

线程安全 (threading.Lock)，最近 200 条 gate 记录。
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from typing import Any

_BUFFER_SIZE = 200


class GateRingBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._records: deque[dict[str, Any]] = deque(maxlen=_BUFFER_SIZE)

    def record(self, *, session_id: str, trace_id: str, action_type: str,
               safety_allowed: bool, gate_decision: str, audit_level: str,
               premise_rewrite_rate: float) -> None:
        """记录一轮 pipeline 结果."""
        now_utc = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        severity_from_gate = {"BLOCK": "P0", "FREEZE": "P0", "WARN": "P1"}.get(gate_decision, "")
        if severity_from_gate:
            severity = severity_from_gate
        elif "p0" in str(audit_level).lower():
            severity = "P0"
        elif "p1" in str(audit_level).lower():
            severity = "P1"
        else:
            severity = "pass"
        summary = f"[{action_type}] gate={gate_decision} safety={'ok' if safety_allowed else 'blocked'} audit={audit_level}"
        with self._lock:
            self._records.append({
                "event_id": str(uuid.uuid4())[:12],
                "timestamp_utc": now_utc,
                "severity": severity,
                "summary": summary,
                "session_id": session_id,
                "trace_id": trace_id,
                "action_type": action_type,
                "safety_allowed": safety_allowed,
                "gate_decision": gate_decision,
                "audit_level": audit_level,
                "premise_rewrite_rate": premise_rewrite_rate,
            })

    def get_latest_gates(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """返回 8 门禁最新状态."""
        with self._lock:
            if not self._records:
                return _empty_gates()
            # 优先找指定 session 的最新记录
            source = self._records
            if session_id:
                filtered = [r for r in source if r["session_id"] == session_id]
                if filtered:
                    source = filtered
            latest = source[-1]
            return _build_gates(latest)

    def get_audit_logs(self, page: int = 1, severity: str = "all",
                       page_size: int = 50) -> dict[str, Any]:
        """返回审计日志分页."""
        with self._lock:
            source = list(self._records)
        source.reverse()  # 最新在前
        if severity and severity != "all":
            source = [r for r in source if r.get("severity", "") == severity]
        total = len(source)
        start = (page - 1) * page_size
        logs = source[start:start + page_size]
        return {"logs": logs, "total": total, "page": page, "page_size": page_size}


# ── 单例 ──────────────────────────────────────────────────────────────────

_buffer: GateRingBuffer | None = None


def get_gate_buffer() -> GateRingBuffer:
    global _buffer
    if _buffer is None:
        _buffer = GateRingBuffer()
    return _buffer


# ── 8 门禁判定 ────────────────────────────────────────────────────────────

def _empty_gates() -> list[dict[str, Any]]:
    return [
        {"id": 1, "name": "Agency Gate", "status": "not_implemented", "metric": "premise_rewrite_rate"},
        {"id": 2, "name": "Excursion Gate", "status": "not_implemented", "metric": "exploration_evidence_count"},
        {"id": 3, "name": "Learning Gate", "status": "not_implemented", "metric": "no_assist_trajectory"},
        {"id": 4, "name": "Relational Gate", "status": "not_implemented", "metric": "compliance_signal_score"},
        {"id": 5, "name": "Causal Gate", "status": "not_implemented", "metric": "causal_diagnostics_triple"},
        {"id": 6, "name": "Audit Gate", "status": "not_implemented", "metric": "audit_health"},
        {"id": 7, "name": "Framing Gate", "status": "not_implemented", "metric": "framing_audit_pass"},
        {"id": 8, "name": "Window Gate", "status": "not_implemented", "metric": "window_schema_version_consistency"},
    ]


def _build_gates(r: dict[str, Any]) -> list[dict[str, Any]]:
    safety = r["safety_allowed"]
    gate = r["gate_decision"]
    audit = r["audit_level"]
    return [
        # 1. Agency Gate: safety_allowed
        {"id": 1, "name": "Agency Gate", "status": "pass" if safety else "warn",
         "metric": "premise_rewrite_rate", "detail": {"safety_allowed": safety}},
        # 2. Excursion Gate: gate_decision
        {"id": 2, "name": "Excursion Gate",
         "status": "pass" if gate in ("GO", "go") else ("warn" if gate in ("WARN", "warn") else "block"),
         "metric": "exploration_evidence_count", "detail": {"gate_decision": gate}},
        # 3. Learning Gate: audit_level
        {"id": 3, "name": "Learning Gate",
         "status": "pass" if str(audit).lower() == "pass" else ("warn" if "p1" in str(audit).lower() else "block"),
         "metric": "no_assist_trajectory", "detail": {"audit_level": audit}},
        # 4. Relational Gate: safety_allowed + gate_decision 联合
        {"id": 4, "name": "Relational Gate",
         "status": "pass" if (safety and gate in ("GO", "go")) else "warn",
         "metric": "compliance_signal_score",
         "detail": {"safety_allowed": safety, "gate_decision": gate}},
        # 5-8: 未实现
        {"id": 5, "name": "Causal Gate", "status": "not_implemented", "metric": "causal_diagnostics_triple"},
        {"id": 6, "name": "Audit Gate", "status": "not_implemented", "metric": "audit_health"},
        {"id": 7, "name": "Framing Gate", "status": "not_implemented", "metric": "framing_audit_pass"},
        {"id": 8, "name": "Window Gate", "status": "not_implemented", "metric": "window_schema_version_consistency"},
    ]
