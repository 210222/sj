"""外圈 fallback 策略。

任何异常统一生成合法 8 字段输出，绝不让调用方收到裸异常。
"""

from datetime import datetime, timezone
from src.inner.clock import get_window_30min, format_utc


def generate_fallback(
    trace_id: str = "unknown",
    event_time_utc: str | None = None,
    reason: str = "ORCH_FALLBACK",
) -> dict:
    """生成稳定 fallback 输出，schema 与正常输出一致。

    Args:
        trace_id: 原始或降级后的追溯 ID。
        event_time_utc: 原始或当前时间。
        reason: fallback 原因标识。

    Returns:
        固定 8 字段 dict。
    """
    if not event_time_utc:
        event_time_utc = format_utc(datetime.now(timezone.utc))

    try:
        window_id = get_window_30min(event_time_utc)
    except Exception:
        event_time_utc = format_utc(datetime.now(timezone.utc))
        try:
            window_id = get_window_30min(event_time_utc)
        except Exception:
            window_id = f"FALLBACK_{format_utc(datetime.now(timezone.utc))[:10]}"

    return {
        "allowed": False,
        "final_intensity": "none",
        "audit_level": "p0_block",
        "reason_code": reason,
        "trace_id": str(trace_id),
        "event_time_utc": str(event_time_utc),
        "window_id": str(window_id),
        "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
    }
