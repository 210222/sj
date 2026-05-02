"""外圈 API 服务入口。

外部唯一入口：接收参数 → 输入校验 → 编排管道 → 格式化输出 → fallback。
输入校验失败与运行时故障通过 reason_code 区分。
"""

from src.outer.orchestration.pipeline import run_pipeline
from src.outer.presentation.formatter import format_output
from src.outer.safeguards.policies import generate_fallback


def run_orchestration(
    trace_id: str,
    event_time_utc: str,
    l0_signals: dict,
    l2_signals: dict,
    safety_context: dict | None = None,
) -> dict:
    """外圈主入口。

    Args:
        trace_id: 追溯 ID。
        event_time_utc: ISO 8601 UTC 事件时间。
        l0_signals: {"engagement": float, "stability": float, "volatility": float}
        l2_signals: {"goal_clarity": float, "resource_readiness": float,
                     "risk_pressure": float, "constraint_conflict": float}
        safety_context: 可选 {"p0_count": int, "p1_count": int, "gate_decision": str}

    Returns:
        固定 8 字段 dict: allowed, final_intensity, audit_level, reason_code,
        trace_id, event_time_utc, window_id, evaluated_at_utc
    """
    # 输入校验——失败用独立 reason_code 区分
    if not isinstance(trace_id, str) or not trace_id:
        return generate_fallback(trace_id, event_time_utc,
                                 "ORCH_INVALID_INPUT")
    if not isinstance(event_time_utc, str) or not event_time_utc:
        return generate_fallback(trace_id, event_time_utc,
                                 "ORCH_INVALID_INPUT")
    if not isinstance(l0_signals, dict) or not isinstance(l2_signals, dict):
        return generate_fallback(trace_id, event_time_utc,
                                 "ORCH_INVALID_INPUT")

    try:
        pipeline_output = run_pipeline(
            trace_id, event_time_utc, l0_signals, l2_signals,
            safety_context,
        )
        return format_output(
            pipeline_output["safety_result"], trace_id, event_time_utc,
        )
    except Exception:
        return generate_fallback(trace_id, event_time_utc, "ORCH_PIPELINE_ERROR")
