"""M2: L0 HBSSM 状态估计测试 — 单元测试 + 对抗性测试。"""

import pytest
from datetime import datetime, timezone

from src.middle.state_l0 import L0Estimator
from src.middle.state_l0.estimator import (
    VALID_STATES, STATE_ENGAGED, STATE_STABLE,
    STATE_TRANSIENT, STATE_VOLATILE, MODEL_VERSION,
)
from src.middle.shared import StateEstimationError, MIDDLE_CONFIG_VERSION
from src.inner.clock import get_window_30min, format_utc


def _ts(h=12, m=0, s=0):
    return f"2026-04-29T{h:02d}:{m:02d}:{s:02d}.000Z"


def _make_estimator(**kw):
    return L0Estimator(**kw)


# ═══════════════════════════════════════════════════════════════
# 基础正常路径
# ═══════════════════════════════════════════════════════════════

class TestHappyPath:
    def test_high_engagement_gives_engaged(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.85, "stability": 0.80, "volatility": 0.10
        })
        assert r["state"] == STATE_ENGAGED
        assert r["reason_code"] == "L0_ENGAGED_INIT"
        assert 0 <= r["confidence"] <= 1
        assert r["model_version"] == MODEL_VERSION

    def test_moderate_signals_give_stable(self):
        e = _make_estimator()
        r = e.estimate("t2", _ts(14), {
            "engagement": 0.60, "stability": 0.55, "volatility": 0.30
        })
        assert r["state"] == STATE_STABLE

    def test_low_signals_give_transient(self):
        e = _make_estimator()
        r = e.estimate("t3", _ts(14), {
            "engagement": 0.35, "stability": 0.40, "volatility": 0.50
        })
        assert r["state"] == STATE_TRANSIENT

    def test_very_low_signals_give_volatile(self):
        e = _make_estimator()
        r = e.estimate("t4", _ts(14), {
            "engagement": 0.10, "stability": 0.15, "volatility": 0.90
        })
        assert r["state"] == STATE_VOLATILE
        assert r["reason_code"] == "L0_VOLATILE_INIT"

    def test_output_keys_are_stable(self):
        e = _make_estimator()
        r = e.estimate("t5", _ts(14), {
            "engagement": 0.50, "stability": 0.50, "volatility": 0.50
        })
        expected_keys = {
            "state", "dwell_time", "confidence", "reason_code",
            "model_version", "config_version",
            "event_time_utc", "window_id", "evaluated_at_utc",
        }
        assert set(r.keys()) == expected_keys


# ═══════════════════════════════════════════════════════════════
# 滞回行为测试
# ═══════════════════════════════════════════════════════════════

class TestHysteresis:
    def test_upgrade_requires_exceeding_penalty(self):
        e = _make_estimator(switch_penalty=0.15)
        ctx = {"prev_state": STATE_STABLE}
        # composite near stable→engaged border (0.70 + 0.15 penalty)
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.88, "stability": 0.88, "volatility": 0.05
        }, context=ctx)
        assert r["state"] == STATE_ENGAGED
        assert "UP" in r["reason_code"]

    def test_hold_when_not_exceeding_penalty(self):
        e = _make_estimator(switch_penalty=0.15)
        ctx = {"prev_state": STATE_STABLE}
        r = e.estimate("t2", _ts(14), {
            "engagement": 0.72, "stability": 0.72, "volatility": 0.20
        }, context=ctx)
        assert r["state"] == STATE_STABLE
        assert "HOLD" in r["reason_code"]

    def test_downgrade_when_below_exit_margin(self):
        e = _make_estimator()
        ctx = {"prev_state": STATE_ENGAGED}
        r = e.estimate("t3", _ts(14), {
            "engagement": 0.40, "stability": 0.40, "volatility": 0.80
        }, context=ctx)
        assert r["state"] != STATE_ENGAGED

    def test_unknown_prev_state_treated_as_init(self):
        e = _make_estimator()
        r = e.estimate("t4", _ts(14), {
            "engagement": 0.80, "stability": 0.80, "volatility": 0.10
        }, context={"prev_state": "unknown"})
        assert r["state"] == STATE_ENGAGED
        assert "INIT" in r["reason_code"]


# ═══════════════════════════════════════════════════════════════
# 驻留时间测试
# ═══════════════════════════════════════════════════════════════

class TestDwellTime:
    def test_dwell_zero_on_first_estimate(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.50, "stability": 0.50, "volatility": 0.50
        })
        assert r["dwell_time"] == 0.0

    def test_dwell_accumulates_when_same_state(self):
        e = _make_estimator()
        ctx = {
            "prev_state": STATE_STABLE,
            "state_start_time_utc": "2026-04-29T14:00:00.000Z",
        }
        r = e.estimate("t2", "2026-04-29T14:05:00.000Z", {
            "engagement": 0.55, "stability": 0.55, "volatility": 0.45
        }, context=ctx)
        assert r["dwell_time"] == 300.0

    def test_dwell_resets_on_state_change(self):
        e = _make_estimator()
        ctx = {
            "prev_state": STATE_ENGAGED,
            "state_start_time_utc": "2026-04-29T14:00:00.000Z",
        }
        r = e.estimate("t3", "2026-04-29T14:30:00.000Z", {
            "engagement": 0.20, "stability": 0.20, "volatility": 0.90
        }, context=ctx)
        assert r["dwell_time"] == 0.0


# ═══════════════════════════════════════════════════════════════
# 对抗性测试 1: 类型扰动
# ═══════════════════════════════════════════════════════════════

class TestTypePerturbation:
    @pytest.mark.parametrize("bad_trace", [42, None, True, [], ""])
    def test_invalid_trace_id_raises(self, bad_trace):
        e = _make_estimator()
        with pytest.raises(StateEstimationError):
            e.estimate(bad_trace, _ts(14), {
                "engagement": 0.5, "stability": 0.5, "volatility": 0.5
            })

    @pytest.mark.parametrize("bad_ts", [
        None, 42, "", "2026/04/29 14:00", "not-a-time",
    ])
    def test_invalid_event_time_raises(self, bad_ts):
        e = _make_estimator()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", bad_ts, {
                "engagement": 0.5, "stability": 0.5, "volatility": 0.5
            })

    @pytest.mark.parametrize("bad_signals", [
        None, 42, [], "signals",
    ])
    def test_non_dict_signals_raises(self, bad_signals):
        e = _make_estimator()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), bad_signals)

    def test_missing_signal_key_raises(self):
        e = _make_estimator()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {"engagement": 0.5, "stability": 0.5})

    @pytest.mark.parametrize("key", ["engagement", "stability", "volatility"])
    def test_non_numeric_signal_raises(self, key):
        e = _make_estimator()
        sigs = {"engagement": 0.5, "stability": 0.5, "volatility": 0.5}
        sigs[key] = "high"
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), sigs)


# ═══════════════════════════════════════════════════════════════
# 对抗性测试 2: 边界扰动
# ═══════════════════════════════════════════════════════════════

class TestBoundaryPerturbation:
    def test_composite_at_engaged_threshold_exact(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.70, "stability": 0.70, "volatility": 0.30
        })
        # composite ~= 0.70 → just at engaged boundary
        assert r["state"] in (STATE_ENGAGED, STATE_STABLE)

    def test_composite_just_above_stable(self):
        e = _make_estimator()
        r = e.estimate("t2", _ts(14), {
            "engagement": 0.52, "stability": 0.52, "volatility": 0.48
        })
        assert r["state"] == STATE_STABLE

    def test_composite_just_below_stable(self):
        e = _make_estimator()
        r = e.estimate("t3", _ts(14), {
            "engagement": 0.28, "stability": 0.28, "volatility": 0.72
        })
        assert r["state"] == STATE_VOLATILE

    def test_signal_at_zero(self):
        e = _make_estimator()
        r = e.estimate("t4", _ts(14), {
            "engagement": 0.0, "stability": 0.0, "volatility": 1.0
        })
        assert r["state"] == STATE_VOLATILE
        assert r["confidence"] >= 0.0

    def test_signal_at_one(self):
        e = _make_estimator()
        r = e.estimate("t5", _ts(14), {
            "engagement": 1.0, "stability": 1.0, "volatility": 0.0
        })
        assert r["state"] == STATE_ENGAGED


# ═══════════════════════════════════════════════════════════════
# 对抗性测试 3: 空样本与稀疏样本
# ═══════════════════════════════════════════════════════════════

class TestSparseSamples:
    def test_all_signals_zero(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.0, "stability": 0.0, "volatility": 1.0
        })
        assert "state" in r
        assert r["dwell_time"] == 0.0

    def test_minimal_valid_context(self):
        e = _make_estimator()
        r = e.estimate("t_min", _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        }, context={"prev_state": None})
        assert r["state"] in VALID_STATES

    def test_empty_context_is_safe(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        }, context={})
        assert r["state"] in VALID_STATES


# ═══════════════════════════════════════════════════════════════
# 对抗性测试 4: 极端值
# ═══════════════════════════════════════════════════════════════

class TestExtremeValues:
    def test_signal_out_of_range_above_raises(self):
        e = _make_estimator()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {
                "engagement": 1.5, "stability": 0.5, "volatility": 0.5
            })

    def test_signal_out_of_range_below_raises(self):
        e = _make_estimator()
        with pytest.raises(StateEstimationError):
            e.estimate("t2", _ts(14), {
                "engagement": 0.5, "stability": -0.1, "volatility": 0.5
            })

    def test_very_long_trace_id(self):
        e = _make_estimator()
        r = e.estimate("x" * 1000, _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        assert r["state"] in VALID_STATES

    def test_max_dwell_time(self):
        e = _make_estimator()
        ctx = {
            "prev_state": STATE_ENGAGED,
            "state_start_time_utc": "2026-01-01T00:00:00.000Z",
        }
        r = e.estimate("t3", _ts(14), {
            "engagement": 0.85, "stability": 0.85, "volatility": 0.10
        }, context=ctx)
        # should be very large dwell (months of seconds)
        assert r["dwell_time"] > 1_000_000


# ═══════════════════════════════════════════════════════════════
# 对抗性测试 5: 幂等性
# ═══════════════════════════════════════════════════════════════

class TestIdempotency:
    def test_same_input_same_output(self):
        e = _make_estimator()
        sigs = {"engagement": 0.60, "stability": 0.55, "volatility": 0.30}
        ctx = {"prev_state": STATE_STABLE, "state_start_time_utc": _ts(14)}
        r1 = e.estimate("t1", _ts(14), sigs, context=ctx)
        r2 = e.estimate("t1", _ts(14), sigs, context=ctx)
        assert r1["state"] == r2["state"]
        assert r1["dwell_time"] == r2["dwell_time"]
        assert r1["confidence"] == r2["confidence"]
        assert r1["reason_code"] == r2["reason_code"]

    def test_same_estimator_reuse(self):
        e = _make_estimator()
        r1 = e.estimate("a", _ts(10), {
            "engagement": 0.60, "stability": 0.55, "volatility": 0.30
        })
        r2 = e.estimate("b", _ts(20), {
            "engagement": 0.60, "stability": 0.55, "volatility": 0.30
        })
        assert r1["state"] == r2["state"]


# ═══════════════════════════════════════════════════════════════
# 对抗性测试 6: 时间一致性
# ═══════════════════════════════════════════════════════════════

class TestTimeConsistency:
    def test_window_id_from_clock(self):
        e = _make_estimator()
        ts = "2026-04-29T14:15:30.000Z"
        r = e.estimate("t1", ts, {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        expected_wid = get_window_30min(ts)
        assert r["window_id"] == expected_wid

    def test_window_id_boundary(self):
        e = _make_estimator()
        # 14:29 → [14:00, 14:30)
        r1 = e.estimate("t1", "2026-04-29T14:29:59.000Z", {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        assert "14:00_2026-04-29T14:30" in r1["window_id"]
        # 14:30 → [14:30, 15:00)
        r2 = e.estimate("t2", "2026-04-29T14:30:00.000Z", {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        assert "14:30_2026-04-29T15:00" in r2["window_id"]

    def test_evaluated_at_utc_is_iso8601(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        assert r["evaluated_at_utc"].endswith("Z")
        assert "T" in r["evaluated_at_utc"]


# ═══════════════════════════════════════════════════════════════
# 组合压力测试
# ═══════════════════════════════════════════════════════════════

class TestCombinationPressure:
    def test_state_transitions_full_cycle(self):
        e = _make_estimator()
        results = []
        prev_state = None
        start = _ts(14)
        sigs_seq = [
            (0.80, 0.75, 0.15),  # → engaged
            (0.60, 0.55, 0.30),  # → stable (downgrade)
            (0.30, 0.35, 0.60),  # → transient
            (0.10, 0.15, 0.90),  # → volatile
        ]
        for i, (eng, sta, vol) in enumerate(sigs_seq):
            ctx = {}
            if prev_state is not None:
                ctx["prev_state"] = prev_state
                ctx["state_start_time_utc"] = start
            r = e.estimate(f"t{i}", _ts(14), {
                "engagement": eng, "stability": sta, "volatility": vol
            }, context=ctx)
            results.append(r)
            prev_state = r["state"]
        assert len(results) == 4
        assert all(r["state"] in VALID_STATES for r in results)

    def test_batch_estimate_consistent(self):
        e = _make_estimator()
        batch = []
        for i in range(20):
            r = e.estimate(f"t{i}", _ts(14, i % 60), {
                "engagement": 0.4 + i * 0.02,
                "stability": 0.5,
                "volatility": 0.3,
            })
            batch.append(r)
        assert all("state" in r and "window_id" in r for r in batch)

    def test_all_state_labels_reachable(self):
        e = _make_estimator()
        states_seen = set()
        test_cases = [
            (0.85, 0.85, 0.10),
            (0.55, 0.55, 0.40),
            (0.35, 0.40, 0.60),
            (0.05, 0.10, 0.90),
        ]
        for eng, sta, vol in test_cases:
            r = e.estimate("t", _ts(14), {
                "engagement": eng, "stability": sta, "volatility": vol
            })
            states_seen.add(r["state"])
        assert states_seen == VALID_STATES

    def test_confidence_in_range(self):
        e = _make_estimator()
        for i in range(50):
            eng = (i % 10) / 10.0
            vol = ((i * 3) % 10) / 10.0
            r = e.estimate(f"t{i}", _ts(14, i % 60), {
                "engagement": eng, "stability": 0.5, "volatility": vol
            })
            assert 0.0 <= r["confidence"] <= 1.0

    def test_dwell_time_monotonic(self):
        e = _make_estimator()
        start = "2026-04-29T14:00:00.000Z"
        ctx = {
            "prev_state": STATE_STABLE,
            "state_start_time_utc": start,
        }
        sigs = {"engagement": 0.55, "stability": 0.55, "volatility": 0.45}
        times = [
            "2026-04-29T14:01:00.000Z",
            "2026-04-29T14:05:00.000Z",
            "2026-04-29T14:10:00.000Z",
        ]
        prev_dwell = 0
        for ts in times:
            r = e.estimate("t", ts, sigs, context=ctx)
            assert r["dwell_time"] >= prev_dwell
            prev_dwell = r["dwell_time"]


# ═══════════════════════════════════════════════════════════════
# 配置可覆盖性测试
# ═══════════════════════════════════════════════════════════════

class TestConfigOverride:
    def test_custom_thresholds_take_effect(self):
        e = _make_estimator(
            hysteresis_entry=0.80,
            switch_penalty=0.10,
        )
        assert e.h_entry == 0.80
        assert e.switch_penalty == 0.10

    def test_default_values_match_shared_config(self):
        from src.middle.shared.config import (
            L0_DWELL_MIN_SECONDS, L0_SWITCH_PENALTY,
            L0_HYSTERESIS_ENTRY, L0_HYSTERESIS_EXIT, L0_MIN_SAMPLES,
        )
        e = _make_estimator()
        assert e.dwell_min == L0_DWELL_MIN_SECONDS
        assert e.switch_penalty == L0_SWITCH_PENALTY
        assert e.h_entry == L0_HYSTERESIS_ENTRY
        assert e.h_exit == L0_HYSTERESIS_EXIT
        assert e.min_samples == L0_MIN_SAMPLES


# ═══════════════════════════════════════════════════════════════
# 异常上下文测试
# ═══════════════════════════════════════════════════════════════

class TestExceptionContext:
    def test_error_carries_message(self):
        try:
            e = _make_estimator()
            e.estimate("t1", _ts(14), {
                "engagement": 2.0, "stability": 0.5, "volatility": 0.5
            })
        except StateEstimationError as exc:
            assert "out of [0,1]" in str(exc)

    def test_error_is_middleware_error(self):
        from src.middle.shared.exceptions import MiddlewareError
        assert issubclass(StateEstimationError, MiddlewareError)


# ═══════════════════════════════════════════════════════════════
# M2.1 微补丁：样本门槛门控
# ═══════════════════════════════════════════════════════════════

class TestSampleCountGating:
    def test_low_sample_count_caps_confidence(self):
        e = _make_estimator(min_samples=5)
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.85, "stability": 0.85, "volatility": 0.10
        }, context={"sample_count": 2})
        assert r["confidence"] <= 0.30

    def test_low_sample_count_adds_reason_suffix(self):
        e = _make_estimator(min_samples=5)
        r = e.estimate("t2", _ts(14), {
            "engagement": 0.50, "stability": 0.50, "volatility": 0.50
        }, context={"sample_count": 1})
        assert "_LOW_SAMPLES" in r["reason_code"]

    def test_sample_at_threshold_is_ok(self):
        e = _make_estimator(min_samples=3)
        r = e.estimate("t3", _ts(14), {
            "engagement": 0.80, "stability": 0.80, "volatility": 0.10
        }, context={"sample_count": 3})
        assert "_LOW_SAMPLES" not in r["reason_code"]
        assert r["confidence"] > 0.30

    def test_sample_count_above_threshold_is_ok(self):
        e = _make_estimator(min_samples=3)
        r = e.estimate("t4", _ts(14), {
            "engagement": 0.80, "stability": 0.80, "volatility": 0.10
        }, context={"sample_count": 10})
        assert "_LOW_SAMPLES" not in r["reason_code"]

    def test_sample_count_not_provided_is_ignored(self):
        e = _make_estimator(min_samples=3)
        r = e.estimate("t5", _ts(14), {
            "engagement": 0.80, "stability": 0.80, "volatility": 0.10
        }, context={})
        assert "_LOW_SAMPLES" not in r["reason_code"]

    def test_sample_count_none_is_ignored(self):
        e = _make_estimator()
        r = e.estimate("t6", _ts(14), {
            "engagement": 0.50, "stability": 0.50, "volatility": 0.50
        }, context={"sample_count": None})
        assert "_LOW_SAMPLES" not in r["reason_code"]


# ═══════════════════════════════════════════════════════════════
# M2.1 微补丁：config_version 可追溯性
# ═══════════════════════════════════════════════════════════════

class TestConfigVersion:
    def test_config_version_in_output(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        assert r["config_version"] == MIDDLE_CONFIG_VERSION

    def test_config_version_stable_across_calls(self):
        e = _make_estimator()
        r1 = e.estimate("t1", _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        r2 = e.estimate("t2", _ts(14, 30), {
            "engagement": 0.8, "stability": 0.8, "volatility": 0.1
        })
        assert r1["config_version"] == r2["config_version"] == MIDDLE_CONFIG_VERSION

    def test_config_version_is_string(self):
        e = _make_estimator()
        r = e.estimate("t1", _ts(14), {
            "engagement": 0.5, "stability": 0.5, "volatility": 0.5
        })
        assert isinstance(r["config_version"], str)
        assert r["config_version"].startswith("middle_v")
