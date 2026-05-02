"""M3: L1 Shock/Memory/Trend 残差估计测试 — 单元测试 + 对抗性测试。"""

import pytest
import math

from src.middle.state_l1 import L1Estimator
from src.middle.state_l1.estimator import (
    VALID_CORRECTIONS, CORRECTION_INCREASE, CORRECTION_DECREASE,
    CORRECTION_NONE, MODEL_VERSION,
)
from src.middle.shared import StateEstimationError, MIDDLE_CONFIG_VERSION
from src.inner.clock import get_window_30min


def _ts(h=12, m=0, s=0):
    return f"2026-04-29T{h:02d}:{m:02d}:{s:02d}.000Z"


def _make(**kw):
    return L1Estimator(**kw)


# ═══════════════════════════════════════════════════════════════
# 正常路径
# ═══════════════════════════════════════════════════════════════

class TestHappyPath:
    def test_no_shock_no_trend_gives_none(self):
        e = _make()
        r = e.estimate("t1", _ts(14), {
            "value": 0.55,
            "history": [0.50, 0.52, 0.54, 0.53, 0.55],
        })
        assert r["correction"] == CORRECTION_NONE
        assert r["reason_code"] == "L1_NONE"
        assert 0.0 <= r["magnitude"] <= 1.0

    def test_shock_up_gives_increase(self):
        e = _make(shock_threshold=0.3)
        r = e.estimate("t2", _ts(14), {
            "value": 0.90,
            "history": [0.50, 0.52, 0.51, 0.53, 0.50],
        })
        assert r["correction"] == CORRECTION_INCREASE
        assert "SHOCK_UP" in r["reason_code"]
        assert r["shock_score"] > 0.5

    def test_shock_down_gives_decrease(self):
        e = _make(shock_threshold=0.3)
        r = e.estimate("t3", _ts(14), {
            "value": 0.10,
            "history": [0.50, 0.52, 0.51, 0.53, 0.50],
        })
        assert r["correction"] == CORRECTION_DECREASE
        assert "SHOCK_DOWN" in r["reason_code"]

    def test_trend_up_gives_increase(self):
        e = _make()
        r = e.estimate("t4", _ts(14), {
            "value": 0.65,
            "history": [0.30, 0.38, 0.45, 0.52, 0.60],
        })
        assert r["correction"] == CORRECTION_INCREASE
        assert "TREND_UP" in r["reason_code"]

    def test_trend_down_gives_decrease(self):
        e = _make()
        r = e.estimate("t5", _ts(14), {
            "value": 0.35,
            "history": [0.70, 0.62, 0.55, 0.48, 0.40],
        })
        assert r["correction"] == CORRECTION_DECREASE
        assert "TREND_DOWN" in r["reason_code"]

    def test_output_keys_are_stable(self):
        e = _make()
        r = e.estimate("t6", _ts(14), {
            "value": 0.5,
            "history": [0.5, 0.5, 0.5],
        })
        expected = {
            "correction", "magnitude", "shock_score", "memory_effect",
            "trend_score", "reason_code", "model_version", "config_version",
            "event_time_utc", "window_id", "evaluated_at_utc",
        }
        assert set(r.keys()) == expected

    def test_config_version_output(self):
        e = _make()
        r = e.estimate("t7", _ts(14), {
            "value": 0.5, "history": [0.5, 0.5, 0.5],
        })
        assert r["config_version"] == MIDDLE_CONFIG_VERSION

    def test_model_version_output(self):
        e = _make()
        r = e.estimate("t8", _ts(14), {
            "value": 0.5, "history": [0.5, 0.5, 0.5],
        })
        assert r["model_version"] == MODEL_VERSION


# ═══════════════════════════════════════════════════════════════
# Memory 衰减测试
# ═══════════════════════════════════════════════════════════════

class TestMemoryDecay:
    def test_memory_accumulates_with_shock(self):
        e = _make(memory_decay_rate=0.2)
        r = e.estimate("t1", _ts(14), {
            "value": 0.9,
            "history": [0.3, 0.3, 0.3, 0.3, 0.3],
            "memory_state": 0.5,
        })
        assert r["memory_effect"] > 0.3

    def test_memory_decays_without_shock(self):
        e = _make(memory_decay_rate=0.1)
        r = e.estimate("t2", _ts(14), {
            "value": 0.50,
            "history": [0.48, 0.50, 0.52, 0.50, 0.49],
            "memory_state": 0.8,
        })
        assert r["memory_effect"] < 0.8

    def test_memory_decay_is_monotonic(self):
        e = _make(memory_decay_rate=0.1)
        mem = 1.0
        prev = 1.0
        for i in range(10):
            r = e.estimate(f"t{i}", _ts(14, i), {
                "value": 0.5,
                "history": [0.5, 0.5, 0.5, 0.5, 0.5],
                "memory_state": mem,
            })
            mem = r["memory_effect"]
            assert mem <= prev
            prev = mem

    def test_zero_initial_memory(self):
        e = _make()
        r = e.estimate("t3", _ts(14), {
            "value": 0.5,
            "history": [0.5, 0.5, 0.5, 0.5, 0.5],
            "memory_state": 0.0,
        })
        assert r["memory_effect"] == 0.0

    def test_none_memory_state_treated_as_zero(self):
        e = _make()
        r = e.estimate("t4", _ts(14), {
            "value": 0.5,
            "history": [0.5, 0.5, 0.5, 0.5, 0.5],
            "memory_state": None,
        })
        assert r["memory_effect"] == 0.0


# ═══════════════════════════════════════════════════════════════
# 类型扰动
# ═══════════════════════════════════════════════════════════════

class TestTypePerturbation:
    @pytest.mark.parametrize("bad", [42, None, True, [], ""])
    def test_bad_trace_id(self, bad):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate(bad, _ts(14), {"value": 0.5, "history": []})

    @pytest.mark.parametrize("bad", [None, 42, "", "not-a-time"])
    def test_bad_event_time(self, bad):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", bad, {"value": 0.5, "history": []})

    @pytest.mark.parametrize("bad", [None, 42, [], "x"])
    def test_non_dict_signals(self, bad):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), bad)

    def test_missing_value_key(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {"history": [0.5]})

    def test_non_numeric_value(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {"value": "high", "history": []})

    def test_history_not_list(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {"value": 0.5, "history": "bad"})

    def test_history_element_not_numeric(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {"value": 0.5, "history": [0.5, "x"]})

    def test_non_numeric_memory_state(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {
                "value": 0.5, "history": [], "memory_state": "high"
            })


# ═══════════════════════════════════════════════════════════════
# 边界扰动
# ═══════════════════════════════════════════════════════════════

class TestBoundaryPerturbation:
    def test_shock_at_threshold_exact(self):
        e = _make(shock_threshold=0.5)
        r = e.estimate("t1", _ts(14), {
            "value": 0.75,
            "history": [0.50, 0.50, 0.50, 0.50, 0.50],
        })
        assert r["shock_score"] == 0.5

    def test_shock_just_above_threshold(self):
        e = _make(shock_threshold=0.5)
        r = e.estimate("t2", _ts(14), {
            "value": 0.76,
            "history": [0.50, 0.50, 0.50, 0.50, 0.50],
        })
        assert r["shock_score"] > 0.5

    def test_shock_just_below_threshold(self):
        e = _make(shock_threshold=0.5)
        r = e.estimate("t3", _ts(14), {
            "value": 0.74,
            "history": [0.50, 0.50, 0.50, 0.50, 0.50],
        })
        assert r["shock_score"] < 0.5

    def test_value_at_zero(self):
        e = _make()
        r = e.estimate("t4", _ts(14), {
            "value": 0.0,
            "history": [0.0, 0.0, 0.0, 0.0, 0.0],
        })
        assert r["correction"] == CORRECTION_NONE
        assert r["magnitude"] >= 0.0

    def test_value_at_one(self):
        e = _make()
        r = e.estimate("t5", _ts(14), {
            "value": 1.0,
            "history": [1.0, 1.0, 1.0, 1.0, 1.0],
        })
        assert "correction" in r


# ═══════════════════════════════════════════════════════════════
# 稀疏样本
# ═══════════════════════════════════════════════════════════════

class TestSparseSamples:
    def test_empty_history_gives_zero_shock(self):
        e = _make()
        r = e.estimate("t1", _ts(14), {
            "value": 0.80,
            "history": [],
        })
        assert r["shock_score"] == 0.0
        assert r["trend_score"] == 0.0

    def test_insufficient_windows_gives_no_trend(self):
        e = _make(trend_min_windows=5)
        r = e.estimate("t2", _ts(14), {
            "value": 0.60,
            "history": [0.50, 0.55, 0.60],
        })
        assert r["trend_score"] == 0.0

    def test_single_history_value(self):
        e = _make()
        r = e.estimate("t3", _ts(14), {
            "value": 0.5,
            "history": [0.5],
        })
        assert r["shock_score"] == 0.0

    def test_history_with_memory_not_provided(self):
        e = _make()
        r = e.estimate("t4", _ts(14), {
            "value": 0.5,
            "history": [0.5, 0.5, 0.5],
        })
        assert "memory_effect" in r


# ═══════════════════════════════════════════════════════════════
# 极端值
# ═══════════════════════════════════════════════════════════════

class TestExtremeValues:
    def test_value_out_of_range_above(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t1", _ts(14), {"value": 1.5, "history": []})

    def test_value_out_of_range_below(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t2", _ts(14), {"value": -0.1, "history": []})

    def test_history_value_out_of_range(self):
        e = _make()
        with pytest.raises(StateEstimationError):
            e.estimate("t3", _ts(14), {"value": 0.5, "history": [0.5, 2.0]})

    def test_very_long_history(self):
        e = _make()
        h = [0.5] * 1000 + [0.95]
        r = e.estimate("t4", _ts(14), {
            "value": 0.95,
            "history": h,
        })
        assert r["shock_score"] > 0.0
        assert r["trend_score"] > 0.0

    def test_all_signals_at_extremes(self):
        e = _make(shock_threshold=0.3)
        r = e.estimate("t5", _ts(14), {
            "value": 0.0,
            "history": [1.0, 1.0, 1.0, 1.0, 1.0],
            "memory_state": 1.0,
        })
        assert r["correction"] == CORRECTION_DECREASE
        assert r["shock_score"] > 0.9

    def test_max_shock_score_clamped(self):
        e = _make(shock_threshold=0.1)
        r = e.estimate("t6", _ts(14), {
            "value": 1.0,
            "history": [0.0, 0.0, 0.0],
        })
        assert r["shock_score"] <= 1.0


# ═══════════════════════════════════════════════════════════════
# 幂等性
# ═══════════════════════════════════════════════════════════════

class TestIdempotency:
    def test_same_input_same_output(self):
        e = _make()
        sigs = {
            "value": 0.7,
            "history": [0.5, 0.5, 0.5, 0.5, 0.5],
            "memory_state": 0.3,
        }
        r1 = e.estimate("t1", _ts(14), sigs)
        r2 = e.estimate("t1", _ts(14), sigs)
        for k in ("correction", "magnitude", "shock_score",
                  "memory_effect", "trend_score", "reason_code"):
            assert r1[k] == r2[k], f"Mismatch on {k}"

    def test_reuse_estimator(self):
        e = _make()
        sigs_a = {"value": 0.6, "history": [0.5, 0.5, 0.5, 0.5, 0.5]}
        sigs_b = {"value": 0.7, "history": [0.5, 0.5, 0.5, 0.5, 0.5]}
        r1 = e.estimate("a", _ts(14), sigs_a)
        r2 = e.estimate("b", _ts(14), sigs_b)
        assert r1["window_id"] is not None
        assert r2["window_id"] is not None


# ═══════════════════════════════════════════════════════════════
# 时间一致性
# ═══════════════════════════════════════════════════════════════

class TestTimeConsistency:
    def test_window_id_from_clock(self):
        e = _make()
        ts = "2026-04-29T14:22:00.000Z"
        r = e.estimate("t1", ts, {
            "value": 0.5, "history": [0.5, 0.5, 0.5],
        })
        assert r["window_id"] == get_window_30min(ts)

    def test_evaluated_at_utc_is_iso8601(self):
        e = _make()
        r = e.estimate("t1", _ts(14), {
            "value": 0.5, "history": [0.5, 0.5, 0.5],
        })
        assert r["evaluated_at_utc"].endswith("Z")
        assert "T" in r["evaluated_at_utc"]


# ═══════════════════════════════════════════════════════════════
# 组合压力
# ═══════════════════════════════════════════════════════════════

class TestCombinationPressure:
    def test_all_corrections_reachable(self):
        e = _make(shock_threshold=0.3)
        corrections_seen = set()
        cases = [
            (0.90, [0.3, 0.3, 0.3, 0.3, 0.3]),  # shock_up
            (0.10, [0.7, 0.7, 0.7, 0.7, 0.7]),  # shock_down
            (0.60, [0.3, 0.38, 0.45, 0.52, 0.58]),  # trend_up
            (0.35, [0.7, 0.62, 0.55, 0.48, 0.42]),  # trend_down
            (0.55, [0.5, 0.52, 0.5, 0.53, 0.51]),  # none
        ]
        for val, hist in cases:
            r = e.estimate("t", _ts(14), {"value": val, "history": hist})
            corrections_seen.add(r["correction"])
        assert corrections_seen == VALID_CORRECTIONS

    def test_batch_consistent(self):
        e = _make()
        for i in range(30):
            val = 0.3 + (i % 7) * 0.1
            r = e.estimate(f"t{i}", _ts(14, i % 60), {
                "value": val,
                "history": [0.3, 0.35, 0.4, 0.45, 0.5],
            })
            assert r["correction"] in VALID_CORRECTIONS
            assert 0.0 <= r["magnitude"] <= 1.0

    def test_magnitude_in_range(self):
        e = _make()
        for i in range(50):
            val = (i % 10) / 10.0
            r = e.estimate(f"t{i}", _ts(14, i % 60), {
                "value": val,
                "history": [0.3, 0.4, 0.5, 0.4, 0.3],
            })
            assert 0.0 <= r["magnitude"] <= 1.0

    def test_shock_trumps_trend(self):
        e = _make(shock_threshold=0.2)
        r = e.estimate("t1", _ts(14), {
            "value": 0.95,
            "history": [0.3, 0.4, 0.5, 0.6, 0.7],
        })
        assert "SHOCK_UP" in r["reason_code"]


# ═══════════════════════════════════════════════════════════════
# 配置可覆盖性
# ═══════════════════════════════════════════════════════════════

class TestConfigOverride:
    def test_custom_thresholds(self):
        e = _make(shock_threshold=0.7, memory_decay_rate=0.2, trend_min_windows=5)
        assert e.shock_threshold == 0.7
        assert e.decay_rate == 0.2
        assert e.trend_min_windows == 5

    def test_defaults_match_shared(self):
        from src.middle.shared.config import (
            L1_SHOCK_THRESHOLD, L1_MEMORY_DECAY_RATE, L1_TREND_MIN_WINDOWS,
        )
        e = _make()
        assert e.shock_threshold == L1_SHOCK_THRESHOLD
        assert e.decay_rate == L1_MEMORY_DECAY_RATE
        assert e.trend_min_windows == L1_TREND_MIN_WINDOWS


# ═══════════════════════════════════════════════════════════════
# 异常上下文
# ═══════════════════════════════════════════════════════════════

class TestExceptionContext:
    def test_error_carries_message(self):
        try:
            e = _make()
            e.estimate("t1", _ts(14), {"value": 2.0, "history": []})
        except StateEstimationError as exc:
            assert "out of [0,1]" in str(exc)

    def test_error_is_middleware_error(self):
        from src.middle.shared.exceptions import MiddlewareError
        assert issubclass(StateEstimationError, MiddlewareError)


# ═══════════════════════════════════════════════════════════════
# M3.1 微补丁：构造函数参数合法性校验
# ═══════════════════════════════════════════════════════════════

class TestInitValidation:
    def test_shock_threshold_zero_raises(self):
        with pytest.raises(StateEstimationError):
            L1Estimator(shock_threshold=0.0)

    def test_shock_threshold_negative_raises(self):
        with pytest.raises(StateEstimationError):
            L1Estimator(shock_threshold=-0.5)

    def test_memory_decay_rate_negative_raises(self):
        with pytest.raises(StateEstimationError):
            L1Estimator(memory_decay_rate=-0.1)

    def test_memory_decay_rate_above_one_raises(self):
        with pytest.raises(StateEstimationError):
            L1Estimator(memory_decay_rate=1.5)

    def test_memory_decay_rate_bounds_are_ok(self):
        e0 = L1Estimator(memory_decay_rate=0.0)
        e1 = L1Estimator(memory_decay_rate=1.0)
        assert e0.decay_rate == 0.0
        assert e1.decay_rate == 1.0

    def test_trend_min_windows_zero_raises(self):
        with pytest.raises(StateEstimationError):
            L1Estimator(trend_min_windows=0)

    def test_trend_min_windows_negative_raises(self):
        with pytest.raises(StateEstimationError):
            L1Estimator(trend_min_windows=-1)

    def test_default_construction_is_valid(self):
        e = L1Estimator()
        assert e.shock_threshold > 0
        assert 0 <= e.decay_rate <= 1
        assert e.trend_min_windows >= 1
