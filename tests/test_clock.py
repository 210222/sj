"""Step 3: 时钟与窗口一致性测试 — 覆盖 UTC 解析、窗口切分、D+N 偏移、校验、集成回归。"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from src.inner.clock import (
    WINDOW_SCHEMA_VERSION,
    parse_utc,
    format_utc,
    get_window_30min,
    get_window_30min_parts,
    get_window_biweekly,
    add_days_anchor,
    add_hours_offset,
    validate_window_id,
    validate_window_consistency,
)
from src.inner.ledger import EventStore


# ═══════════════════════════════════════════════════════════════
# UTC 解析
# ═══════════════════════════════════════════════════════════════

class TestParseUTC:
    """parse_utc: 各种 ISO 8601 输入 → UTC datetime。"""

    def test_z_suffix(self):
        dt = parse_utc("2026-04-29T12:30:00Z")
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 0
        assert dt.year == 2026 and dt.month == 4 and dt.day == 29
        assert dt.hour == 12 and dt.minute == 30

    def test_positive_offset_converts_to_utc(self):
        dt = parse_utc("2026-04-29T14:30:00+02:00")
        assert dt.hour == 12  # 14:30+02:00 = 12:30 UTC

    def test_negative_offset_converts_to_utc(self):
        dt = parse_utc("2026-04-29T08:30:00-04:00")
        assert dt.hour == 12  # 08:30-04:00 = 12:30 UTC

    def test_with_milliseconds(self):
        dt = parse_utc("2026-04-29T12:30:00.123Z")
        assert dt.microsecond == 123000

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Invalid ISO 8601"):
            parse_utc("not-a-time")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid ISO 8601"):
            parse_utc("")

    def test_date_only_raises(self):
        with pytest.raises(ValueError, match="Invalid ISO 8601"):
            parse_utc("2026-04-29")

    def test_format_utc_roundtrip(self):
        """format_utc → parse_utc 往返一致。"""
        dt = datetime(2026, 4, 29, 12, 30, 15, 123000, tzinfo=timezone.utc)
        s = format_utc(dt)
        assert s.endswith("Z")
        dt2 = parse_utc(s)
        assert dt == dt2


# ═══════════════════════════════════════════════════════════════
# 30 分钟窗口切分: [HH:00, HH:30) 和 [HH:30, HH+1:00)
# ═══════════════════════════════════════════════════════════════

class TestWindow30Min:
    """30 分钟窗口边界切分测试。"""

    def test_minute_00_to_29_in_first_half(self):
        """mm ∈ [00, 29] → [HH:00, HH:30)"""
        for minute in (0, 1, 14, 29):
            ts = f"2026-04-29T12:{minute:02d}:00Z"
            wid = get_window_30min(ts)
            assert wid == "2026-04-29T12:00_2026-04-29T12:30", \
                f"minute={minute}, got={wid}"

    def test_minute_30_to_59_in_second_half(self):
        """mm ∈ [30, 59] → [HH:30, HH+1:00)"""
        for minute in (30, 31, 45, 59):
            ts = f"2026-04-29T12:{minute:02d}:00Z"
            wid = get_window_30min(ts)
            assert wid == "2026-04-29T12:30_2026-04-29T13:00", \
                f"minute={minute}, got={wid}"

    def test_cross_hour_boundary(self):
        """12:59 → [12:30, 13:00)"""
        assert get_window_30min("2026-04-29T12:59:59Z") == \
            "2026-04-29T12:30_2026-04-29T13:00"

    def test_cross_day_boundary(self):
        """23:45 → [23:30, 00:00) next day"""
        wid = get_window_30min("2026-04-29T23:45:00Z")
        assert wid == "2026-04-29T23:30_2026-04-30T00:00"

    def test_midnight_boundary(self):
        """00:05 → [00:00, 00:30) same day"""
        wid = get_window_30min("2026-04-29T00:05:00Z")
        assert wid == "2026-04-29T00:00_2026-04-29T00:30"

    def test_seconds_dont_affect_window(self):
        """秒和毫秒不影响窗口归属。"""
        w1 = get_window_30min("2026-04-29T12:29:00Z")
        w2 = get_window_30min("2026-04-29T12:29:59Z")
        w3 = get_window_30min("2026-04-29T12:29:59.999Z")
        assert w1 == w2 == w3 == "2026-04-29T12:00_2026-04-29T12:30"

    def test_window_30min_parts(self):
        parts = get_window_30min_parts("2026-04-29T12:14:00Z")
        assert parts["window_id"] == "2026-04-29T12:00_2026-04-29T12:30"
        assert parts["window_start"] == "2026-04-29T12:00"
        assert parts["window_end"] == "2026-04-29T12:30"
        assert parts["schema_version"] == WINDOW_SCHEMA_VERSION

    def test_format_matches_contract_example(self):
        """contracts/clock.json 示例: 2026-04-29T14:00_2026-04-29T14:30"""
        wid = get_window_30min("2026-04-29T14:14:00Z")
        assert wid == "2026-04-29T14:00_2026-04-29T14:30"


# ═══════════════════════════════════════════════════════════════
# 双周窗口
# ═══════════════════════════════════════════════════════════════

class TestBiweekly:
    """双周窗口接口测试。"""

    def test_epoch_date_in_first_window(self):
        wid = get_window_biweekly("2026-01-05T00:00:00Z")
        assert wid.startswith("BIWEEK_")
        assert "2026-01-05" in wid
        assert "2026-01-19" in wid

    def test_days_after_epoch(self):
        """epoch + 14 天落入第二窗口。"""
        wid = get_window_biweekly("2026-01-19T00:00:00Z")
        assert "2026-01-19" in wid
        assert "2026-02-02" in wid

    def test_before_epoch_raises(self):
        with pytest.raises(ValueError):
            get_window_biweekly("2025-12-31T00:00:00Z")


# ═══════════════════════════════════════════════════════════════
# D+N 锚点偏移
# ═══════════════════════════════════════════════════════════════

class TestDaysOffset:
    """D+1 / D+7 锚点计算。"""

    def test_d_plus_1(self):
        result = add_days_anchor("2026-04-29T12:00:00Z", days=1)
        assert result.startswith("2026-04-30T12:00")

    def test_d_plus_7(self):
        result = add_days_anchor("2026-04-29T12:00:00Z", days=7)
        assert result.startswith("2026-05-06T12:00")

    def test_hours_offset_d_plus_1(self):
        result = add_hours_offset("2026-04-29T12:00:00Z", hours=24)
        assert result.startswith("2026-04-30T12:00")

    def test_hours_offset_d_plus_7(self):
        result = add_hours_offset("2026-04-29T12:00:00Z", hours=168)
        assert result.startswith("2026-05-06T12:00")

    def test_output_is_z_suffix(self):
        assert add_days_anchor("2026-04-29T12:00:00Z", days=3).endswith("Z")
        assert add_hours_offset("2026-04-29T12:00:00Z", hours=48).endswith("Z")


# ═══════════════════════════════════════════════════════════════
# 窗口校验
# ═══════════════════════════════════════════════════════════════

class TestWindowValidation:
    """validate_window_id + validate_window_consistency。"""

    def test_valid_window_id(self):
        assert validate_window_id("2026-04-29T12:00_2026-04-29T12:30") is True

    def test_invalid_window_id_format(self):
        assert validate_window_id("12:00_12:30") is False

    def test_non_string_window_id(self):
        assert validate_window_id(None) is False
        assert validate_window_id(123) is False

    def test_empty_window_id(self):
        assert validate_window_id("") is False

    def test_consistency_passes(self):
        event = {
            "event_time_utc": "2026-04-29T12:14:00Z",
            "window_id": "2026-04-29T12:00_2026-04-29T12:30",
            "window_schema_version": "1.0.0",
        }
        r = validate_window_consistency(event)
        assert r["valid"] is True

    def test_consistency_detects_mismatch(self):
        event = {
            "event_time_utc": "2026-04-29T12:14:00Z",
            "window_id": "2026-04-29T12:30_2026-04-29T13:00",
            "window_schema_version": "1.0.0",
        }
        r = validate_window_consistency(event)
        assert r["valid"] is False

    def test_consistency_detects_wrong_schema(self):
        event = {
            "event_time_utc": "2026-04-29T12:14:00Z",
            "window_id": "2026-04-29T12:00_2026-04-29T12:30",
            "window_schema_version": "0.9.0",
        }
        r = validate_window_consistency(event)
        assert r["valid"] is False
        assert r["window_schema_ok"] is False

    def test_consistency_empty_timestamp(self):
        r = validate_window_consistency({})
        assert r["valid"] is False
        assert "empty" in r["reason"]


# ═══════════════════════════════════════════════════════════════
# Step1 EventStore 集成：window_id 来自 clock 统一入口
# ═══════════════════════════════════════════════════════════════

class TestLedgerIntegration:
    """EventStore 产生的 window_id 必须来自 clock 统一逻辑。"""

    @pytest.fixture
    def store(self):
        fd, path = tempfile.mkstemp(suffix=".db", prefix="coherence_clk_")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        yield s
        try:
            os.unlink(path)
        except PermissionError:
            import time
            time.sleep(0.1)
            os.unlink(path)

    def test_genesis_window_id_matches_clock(self, store):
        e = store.create_genesis_event()
        from src.inner.clock import get_window_30min
        expected = get_window_30min(e["event_time_utc"])
        assert e["window_id"] == expected

    def test_append_window_id_matches_clock(self, store):
        store.create_genesis_event()
        e = store.append_event({
            "trace_id": "t1",
            "policy_version": "1",
            "counterfactual_ranker_version": "1",
            "counterfactual_feature_schema_version": "1",
        })
        from src.inner.clock import get_window_30min
        expected = get_window_30min(e["event_time_utc"])
        assert e["window_id"] == expected

    def test_explicit_custom_window_id_respected(self, store):
        """显式传入 window_id 时不被覆盖（非默认路径）。"""
        store.create_genesis_event()
        custom_wid = "2026-01-01T00:00_2026-01-01T00:30"
        e = store.append_event({
            "trace_id": "t2",
            "policy_version": "1",
            "counterfactual_ranker_version": "1",
            "counterfactual_feature_schema_version": "1",
        }, window_id=custom_wid)
        assert e["window_id"] == custom_wid

    def test_all_stored_events_pass_validation(self, store):
        """数据库中所有事件的 window_id 格式合法。"""
        store.create_genesis_event()
        for i in range(5):
            store.append_event({
                "trace_id": f"t{i}",
                "policy_version": "1",
                "counterfactual_ranker_version": "1",
                "counterfactual_feature_schema_version": "1",
            })
        events = store.get_events_in_window(
            store.get_latest_event()["window_id"]
        )
        for e in events:
            assert validate_window_id(e["window_id"]), \
                f"Invalid window_id: {e['window_id']}"
