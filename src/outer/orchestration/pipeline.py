"""外圈编排管道：L0→L1→L2→Decision→Safety。

只负责调用顺序与数据传递，不写业务策略。
内部 stage_markers 用于失败定位，不对外暴露。
"""

from src.middle.state_l0 import L0Estimator
from src.middle.state_l1 import L1Estimator
from src.middle.state_l2 import L2Estimator
from src.middle.decision import DecisionEngine
from src.middle.semantic_safety import SemanticSafetyEngine


# 模块实例（无状态，全局复用）
_L0 = L0Estimator()
_L1 = L1Estimator()
_L2 = L2Estimator()
_DECISION = DecisionEngine()
_SAFETY = SemanticSafetyEngine()

# 阶段标记顺序
STAGE_ORDER = ["l0_done", "l1_done", "l2_done", "decision_done", "safety_done"]


def run_pipeline(
    trace_id: str,
    event_time_utc: str,
    l0_signals: dict,
    l2_signals: dict,
    safety_context: dict | None = None,
) -> dict:
    """执行外圈编排主链。

    Args:
        trace_id: 追溯 ID。
        event_time_utc: ISO 8601 UTC 事件时间。
        l0_signals: {"engagement": float, "stability": float, "volatility": float}
        l2_signals: {"goal_clarity": float, "resource_readiness": float,
                     "risk_pressure": float, "constraint_conflict": float}
        safety_context: 可选 {"p0_count": int, "p1_count": int, "gate_decision": str}

    Returns:
        dict with keys: safety_result, stage_markers (internal use only)
    """
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

        # Safety: 语义闸门
        last_stage = "safety"
        safety_result = _SAFETY.evaluate(
            trace_id, event_time_utc,
            {"intensity": decision_result["intensity"],
             "reason_code": decision_result["reason_code"]},
            {
                "p0_count": sctx.get("p0_count", 0),
                "p1_count": sctx.get("p1_count", 0),
                "gate_decision": sctx.get("gate_decision", "GO"),
            },
        )
        stage_markers["safety_done"] = True

        return {
            "safety_result": safety_result,
            "stage_markers": stage_markers,
        }

    except Exception:
        raise RuntimeError(
            f"Pipeline failed at stage '{last_stage}': "
            f"markers={stage_markers}"
        )

