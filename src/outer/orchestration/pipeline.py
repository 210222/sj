"""外圈编排管道：L0→L1→L2→Decision→Safety→Ledger。

只负责调用顺序与数据传递，不写业务策略。
内部 stage_markers 用于失败定位，不对外暴露。
"""

import json
import logging

from src.middle.state_l0 import L0Estimator
from src.middle.state_l1 import L1Estimator
from src.middle.state_l2 import L2Estimator
from src.middle.decision import DecisionEngine
from src.middle.semantic_safety import SemanticSafetyEngine

from src.inner.clock import get_window_30min
from src.inner.ledger import EventStore
from src.inner.audit.auditor import generate_audit_report
from src.inner.gates import GateEngine

_logger = logging.getLogger(__name__)

# 模块实例（无状态，全局复用）
_L0 = L0Estimator()
_L1 = L1Estimator()
_L2 = L2Estimator()
_DECISION = DecisionEngine()
_SAFETY = SemanticSafetyEngine()
_GATE_ENGINE = GateEngine()

_LEDGER_STORE: EventStore | None = None

# 阶段标记顺序
STAGE_ORDER = ["l0_done", "l1_done", "l2_done", "decision_done", "safety_done"]


def _get_ledger() -> EventStore:
    """延迟初始化账本（单例）。"""
    global _LEDGER_STORE
    if _LEDGER_STORE is None:
        _LEDGER_STORE = EventStore("data/coherence.db")
        _LEDGER_STORE.initialize()
        if _LEDGER_STORE.get_latest_event() is None:
            _LEDGER_STORE.create_genesis_event()
    return _LEDGER_STORE


def _conflict_level_to_score(level: str) -> float:
    return {"low": 0.1, "mid": 0.5, "high": 0.9}.get(level, 0.0)


def _commit_to_ledger(
    trace_id: str,
    event_time_utc: str,
    window_id: str,
    l0_result: dict,
    l1_result: dict,
    l2_result: dict,
    decision_result: dict,
    safety_result: dict,
) -> None:
    """将管线执行数据映射为 P0/P1 字段，写入哈希链账本。"""
    try:
        store = _get_ledger()
        p0 = {
            "trace_id": trace_id,
            "policy_version": "coach_pipeline_v1.0.0",
            "counterfactual_ranker_version": "pipeline_v1.0.0",
            "counterfactual_feature_schema_version": "1.0.0",
        }
        p1 = {
            "tradeoff_reason": json.dumps({
                "l0_state": l0_result.get("state"),
                "l0_confidence": l0_result.get("confidence"),
                "l1_correction": l1_result.get("correction"),
                "l2_feasible": l2_result.get("feasible"),
                "decision_intensity": decision_result.get("intensity"),
                "decision_conflict_level": decision_result.get("conflict_level"),
                "safety_allowed": safety_result.get("allowed"),
            }),
            "meta_conflict_score": _conflict_level_to_score(
                decision_result.get("conflict_level", "low")
            ),
            "meta_conflict_alert_flag": 0 if safety_result.get("allowed", True) else 1,
        }
        store.append_event(p0, p1, event_time_utc=event_time_utc, window_id=window_id)
    except Exception:
        _logger.warning("Ledger write failed — continuing pipeline", exc_info=True)


def _run_audit_on_current_window(store: EventStore, window_id: str) -> dict:
    """对当前窗口事件执行实时审计，返回 audit_level。"""
    try:
        events = store.get_events_in_window(window_id)
        if not events:
            return {"audit_level": "pass", "insufficient_data": True}
        report = generate_audit_report(events)
        # 取 per_event 中最严重的 audit_level
        level_order = {"pass": 0, "p1_warn": 1, "p1_freeze": 2, "p0_block": 3}
        worst = "pass"
        for entry in report.get("per_event", []):
            if level_order.get(entry.get("audit_level"), 0) > level_order[worst]:
                worst = entry["audit_level"]
        return {"audit_level": worst, "report": report, "insufficient_data": False}
    except Exception:
        _logger.warning("Audit failed — degrading to pass", exc_info=True)
        return {"audit_level": "pass", "insufficient_data": True}


def _dsl_to_l0_signals(dsl_packet: dict) -> dict:
    """coach 模式：从 DSL 包中提取 L0 信号。"""
    dp = dsl_packet.get("domain_passport", {})
    evidence_map = {"high": 0.8, "medium": 0.5, "low": 0.3, "none": 0.1}
    level = evidence_map.get(dp.get("evidence_level", "medium"), 0.5)
    return {"engagement": level, "stability": level, "volatility": 0.5}


def _dsl_to_l2_signals(dsl_packet: dict) -> dict:
    """coach 模式：从 DSL 包中提取 L2 信号。"""
    atype = dsl_packet.get("action_type", "suggest")
    # 不同 action_type 对资源/清晰度的要求不同
    if atype == "challenge":
        feasibility = 0.5
    elif atype == "defer":
        feasibility = 0.9
    else:
        feasibility = 0.7
    return {
        "goal_clarity": feasibility,
        "resource_readiness": feasibility,
        "risk_pressure": 0.3,
        "constraint_conflict": 0.3,
    }


def run_pipeline(
    trace_id: str,
    event_time_utc: str,
    l0_signals: dict,
    l2_signals: dict,
    safety_context: dict | None = None,
    mode: str = "legacy",
    dsl_packet: dict | None = None,
) -> dict:
    """执行外圈编排主链。

    Args:
        trace_id: 追溯 ID。
        event_time_utc: ISO 8601 UTC 事件时间。
        l0_signals: {"engagement": float, "stability": float, "volatility": float}
        l2_signals: {"goal_clarity": float, "resource_readiness": float,
                     "risk_pressure": float, "constraint_conflict": float}
        safety_context: 可选 {"p0_count": int, "p1_count": int, "gate_decision": str}
        mode: "legacy" (default, Phase 0 原逻辑) 或 "coach" (DSL 模式)
        dsl_packet: coach 模式下的 DSL 动作包

    Returns:
        dict with keys: safety_result, stage_markers, audit_level.
        coach 模式额外包含: sanitized_dsl, coach_trace.
    """
    # ── coach 模式：从 DSL 包提取信号 ─────────────────────────
    if mode == "coach" and dsl_packet is not None:
        l0_signals = _dsl_to_l0_signals(dsl_packet)
        l2_signals = _dsl_to_l2_signals(dsl_packet)
        if not event_time_utc:
            from datetime import datetime, timezone
            event_time_utc = (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            )

    sctx = safety_context or {}
    stage_markers = {k: False for k in STAGE_ORDER}
    last_stage = None

    try:
        # L0: 状态估计
        last_stage = "l0"
        l0_result = _L0.estimate(trace_id, event_time_utc, l0_signals)
        stage_markers["l0_done"] = True

        # L1: 扰动残差
        last_stage = "l1"
        l1_result = _L1.estimate(
            trace_id, event_time_utc,
            {"value": l0_result["confidence"], "history": []},
        )
        stage_markers["l1_done"] = True

        # L2: 行为可行性
        last_stage = "l2"
        l2_result = _L2.estimate(trace_id, event_time_utc, l2_signals)
        stage_markers["l2_done"] = True

        # Decision: 三路融合
        last_stage = "decision"
        decision_result = _DECISION.decide(
            trace_id, event_time_utc,
            {"state": l0_result["state"], "confidence": l0_result["confidence"]},
            {"correction": l1_result["correction"],
             "magnitude": l1_result["magnitude"]},
            {"feasible": l2_result["feasible"],
             "block_reason": l2_result["block_reason"]},
            {
                "l0": 1.0 - l0_result["confidence"],
                "l1": l1_result["shock_score"],
                "l2": l2_result["uncertainty"],
            },
        )
        stage_markers["decision_done"] = True

        # S0.3 — GateEngine 实时门禁（取代外部传入字符串）
        try:
            gate_inputs = {
                "6_audit_gate": {
                    "p0_count": sctx.get("p0_count", 0),
                },
            }
            gate_result = _GATE_ENGINE.evaluate(
                gate_inputs, event_time_utc=event_time_utc,
            )
            live_gate_decision = gate_result["decision"]
        except Exception:
            _logger.warning("GateEngine failed — defaulting to GO", exc_info=True)
            live_gate_decision = "GO"

        # Safety: 语义闸门
        last_stage = "safety"
        safety_result = _SAFETY.evaluate(
            trace_id, event_time_utc,
            {"intensity": decision_result["intensity"],
             "reason_code": decision_result["reason_code"]},
            {
                "p0_count": sctx.get("p0_count", 0),
                "p1_count": sctx.get("p1_count", 0),
                "gate_decision": live_gate_decision,
            },
        )
        stage_markers["safety_done"] = True

        # S0.1 — 管线数据写入哈希链账本（写失败不阻塞）
        window_id = safety_result.get("window_id", get_window_30min(event_time_utc))
        _commit_to_ledger(
            trace_id, event_time_utc, window_id,
            l0_result, l1_result, l2_result,
            decision_result, safety_result,
        )

        # S0.2 — 实时审计（失败降级为 pass，不阻断管线）
        try:
            audit_result = _run_audit_on_current_window(_get_ledger(), window_id)
            pipeline_audit_level = audit_result.get("audit_level", "pass")
        except Exception:
            _logger.warning("Audit failed — degrading to pass", exc_info=True)
            pipeline_audit_level = "pass"

        # ── 构建返回结果 ────────────────────────────────────────
        result = {
            "safety_result": safety_result,
            "stage_markers": stage_markers,
            "audit_level": pipeline_audit_level,
        }

        # coach 模式：附加 sanitized_dsl + coach_trace（包含管线内部估算结果）
        if mode == "coach" and dsl_packet is not None:
            try:
                result["sanitized_dsl"] = (
                    dsl_packet if safety_result["allowed"] else None
                )
                result["coach_trace"] = {
                    "mode": "coach",
                    "dsl_action_type": dsl_packet.get("action_type"),
                    "safety_allowed": safety_result["allowed"],
                    "gate_decision": live_gate_decision,
                    "audit_level": pipeline_audit_level,
                    # 管线内部估算结果——供 CoachAgent 更新状态追踪
                    "l0_state": l0_result.get("state"),
                    "l0_confidence": l0_result.get("confidence"),
                    "l1_correction": l1_result.get("correction"),
                    "l1_magnitude": l1_result.get("magnitude"),
                    "l2_feasible": l2_result.get("feasible"),
                    "l2_uncertainty": l2_result.get("uncertainty"),
                }
            except Exception:
                _logger.warning(
                    "Coach trace build failed — using fallback", exc_info=True
                )
                result["sanitized_dsl"] = None
                result["coach_trace"] = {
                    "mode": "coach",
                    "dsl_action_type": dsl_packet.get("action_type"),
                    "safety_allowed": safety_result.get("allowed", True),
                    "gate_decision": live_gate_decision,
                    "audit_level": pipeline_audit_level,
                    "l0_state": l0_result.get("state"),
                    "l0_confidence": l0_result.get("confidence"),
                    "l1_correction": l1_result.get("correction"),
                    "l1_magnitude": l1_result.get("magnitude"),
                    "l2_feasible": l2_result.get("feasible"),
                    "l2_uncertainty": l2_result.get("uncertainty"),
                }

        return result

    except Exception:
        raise RuntimeError(
            f"Pipeline failed at stage '{last_stage}': "
            f"markers={stage_markers}"
        )

