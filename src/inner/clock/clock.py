"""Step 3: 统一 UTC 时钟与窗口切分。

contracts/clock.json 冻结约束：
- 所有时间计算统一 UTC，输出 ISO 8601 Z 后缀
- 30min 窗口：[HH:00, HH:30), [HH:30, HH+1:00)  前闭后开
- D+1 = +24h, D+7 = +168h
- window_id 格式: YYYY-MM-DDTHH:MM_YYYY-MM-DDTHH:MM
"""

import re
from datetime import datetime, timedelta, timezone

WINDOW_SCHEMA_VERSION = "1.0.0"

_ISO_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

_WINDOW_ID_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
)

_OUTPUT_FMT = "%Y-%m-%dT%H:%M:%S.%f"
_WINDOW_FMT = "%Y-%m-%dT%H:%M"


def parse_utc(ts: str) -> datetime:
    """将 ISO 8601 时间字符串解析为 UTC datetime。

    Args:
        ts: ISO 8601 字符串。支持 'Z' 后缀或 '+HH:MM'/'-HH:MM' 偏移。

    Returns:
        UTC datetime 对象。

    Raises:
        ValueError: 输入格式不合法。
    """
    if not isinstance(ts, str) or not _ISO_PATTERN.match(ts):
        raise ValueError(
            f"Invalid ISO 8601 timestamp: {ts!r}. "
            f"Expected format: YYYY-MM-DDTHH:MM:SS[.fff](Z|±HH:MM)"
        )
    normalized = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_utc(dt: datetime) -> str:
    """将 datetime 格式化为 ISO 8601 UTC (Z 后缀)。"""
    dt_utc = dt.astimezone(timezone.utc)
    s = dt_utc.strftime(_OUTPUT_FMT)
    return s[:-3] + "Z"


# ── 30 分钟窗口 ──────────────────────────────────────────────────

def get_window_30min(
    ts: str,
    schema_version: str = WINDOW_SCHEMA_VERSION,
) -> str:
    """返回给定时间所属的 30 分钟窗口 window_id。

    边界规则（合约定义）：
    - 前闭后开 [start, end)
    - mm ∈ [00, 30) → [HH:00, HH:30)
    - mm ∈ [30, 60) → [HH:30, HH+1:00)

    Args:
        ts: ISO 8601 UTC 时间字符串。
        schema_version: 窗口划分规则版本（用于 future-proofing）。

    Returns:
        window_id 字符串，格式: YYYY-MM-DDTHH:MM_YYYY-MM-DDTHH:MM
    """
    dt = parse_utc(ts)
    minute = dt.minute
    if minute < 30:
        start_minute = 0
    else:
        start_minute = 30
    window_start = dt.replace(minute=start_minute, second=0, microsecond=0)
    window_end = window_start + timedelta(minutes=30)
    return (
        f"{window_start.strftime(_WINDOW_FMT)}_"
        f"{window_end.strftime(_WINDOW_FMT)}"
    )


def get_window_30min_parts(ts: str) -> dict:
    """返回 30 分钟窗口的结构化信息。

    Returns:
        {"window_id": str, "window_start": str, "window_end": str,
         "schema_version": str}
    """
    dt = parse_utc(ts)
    window_id = get_window_30min(ts)
    parts = window_id.split("_")
    return {
        "window_id": window_id,
        "window_start": parts[0],
        "window_end": parts[1],
        "schema_version": WINDOW_SCHEMA_VERSION,
    }


# ── 双周窗口（占位接口） ────────────────────────────────────────

def get_window_biweekly(
    ts: str,
    epoch_start: str = "2026-01-05T00:00:00Z",
) -> str:
    """返回给定时间所属的双周窗口 window_id（合约定义接口）。

    epoch_start: 2026 年第一个周一（2026-01-05）。
    """
    dt = parse_utc(ts)
    epoch = parse_utc(epoch_start)
    days_since = (dt - epoch).days
    if days_since < 0:
        raise ValueError(f"Timestamp before biweekly epoch: {ts!r}")
    window_num = days_since // 14
    window_start = epoch + timedelta(days=window_num * 14)
    window_end = window_start + timedelta(days=14)
    fmt = "%Y-%m-%d"
    return (
        f"BIWEEK_{window_start.strftime(fmt)}_"
        f"{window_end.strftime(fmt)}"
    )


# ── D+N 锚点偏移 ────────────────────────────────────────────────

def add_days_anchor(ts: str, days: int) -> str:
    """从 event_time_utc 锚点计算 D+N 偏移后的 UTC 时间。

    Args:
        ts: event_time_utc 锚点。
        days: 偏移天数。D+1=1, D+7=7。

    Returns:
        ISO 8601 UTC 时间字符串（Z 后缀）。
    """
    dt = parse_utc(ts)
    result = dt + timedelta(days=days)
    return format_utc(result)


def add_hours_offset(ts: str, hours: int) -> str:
    """从 event_time_utc 锚点计算小时偏移后的 UTC 时间。

    Args:
        ts: event_time_utc 锚点。
        hours: 偏移小时数。D+1=24, D+7=168。
    """
    dt = parse_utc(ts)
    result = dt + timedelta(hours=hours)
    return format_utc(result)


# ── 窗口校验 ────────────────────────────────────────────────────

def validate_window_id(window_id: str) -> bool:
    """校验 window_id 格式是否合法。

    Args:
        window_id: 待校验的窗口 ID 字符串。

    Returns:
        True 如果格式匹配 YYYY-MM-DDTHH:MM_YYYY-MM-DDTHH:MM。
    """
    if not isinstance(window_id, str):
        return False
    return bool(_WINDOW_ID_RE.match(window_id))


def validate_window_consistency(event: dict) -> dict:
    """校验事件的 window_id 与其 event_time_utc 是否一致。

    Args:
        event: 包含 event_time_utc, window_id, window_schema_version 的事件 dict。

    Returns:
        {"valid": bool, "expected_window_id": str, "actual_window_id": str,
         "window_schema_ok": bool, "reason": str}
    """
    ts = event.get("event_time_utc", "")
    actual_wid = event.get("window_id", "")
    actual_schema = event.get("window_schema_version", "")

    if not ts:
        return {
            "valid": False,
            "expected_window_id": "",
            "actual_window_id": actual_wid,
            "window_schema_ok": False,
            "reason": "event_time_utc is empty",
        }

    expected_wid = get_window_30min(ts)
    schema_ok = actual_schema == WINDOW_SCHEMA_VERSION

    return {
        "valid": actual_wid == expected_wid and schema_ok,
        "expected_window_id": expected_wid,
        "actual_window_id": actual_wid,
        "window_schema_ok": schema_ok,
        "reason": (
            "window_id and schema_version match"
            if (actual_wid == expected_wid and schema_ok)
            else (
                f"window_id mismatch: expected={expected_wid}, got={actual_wid}"
                if actual_wid != expected_wid
                else f"schema_version mismatch: expected={WINDOW_SCHEMA_VERSION}, got={actual_schema}"
            )
        ),
    }
