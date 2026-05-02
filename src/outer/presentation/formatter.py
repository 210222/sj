"""外圈统一输出格式化器。

将编排链路结果格式化为固定的 8 字段输出 schema。
成功/失败路径必须返回相同结构。
"""

from datetime import datetime, timezone
from src.inner.clock import get_window_30min, format_utc

OUTPUT_SCHEMA_KEYS = [
    "allowed", "final_intensity", "audit_level",
    "reason_code", "trace_id", "event_time_utc",
    "window_id", "evaluated_at_utc",
]


def format_output(
    safety_result: dict,
    trace_id: str,
    event_time_utc: str,
) -> dict:
    """将 Safety 输出格式化为外圈统一 schema。

    Args:
        safety_result: SemanticSafetyEngine.evaluate() 的返回值。
        trace_id: 原始追溯 ID。
        event_time_utc: 原始事件时间。

    Returns:
        固定 8 字段 dict。
    """
    window_id = get_window_30min(event_time_utc)
    return {
        "allowed": bool(safety_result.get("allowed", False)),
        "final_intensity": str(
            safety_result.get("sanitized_output", {}).get("intensity", "none")
        ),
        "audit_level": str(safety_result.get("audit_level", "p0_block")),
        "reason_code": str(safety_result.get("reason_code", "ORCH_ERROR")),
        "trace_id": str(trace_id),
        "event_time_utc": str(event_time_utc),
        "window_id": str(window_id),
        "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
    }
