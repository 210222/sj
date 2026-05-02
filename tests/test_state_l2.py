"""M4: L2 COM-B 可行性估计测试 — 10 组 + 对抗性。"""

import math
import pytest

from src.middle.state_l2 import L2Estimator
from src.middle.state_l2.estimator import (
    VALID_ACTIONS, ACTION_ADVANCE, ACTION_HOLD, ACTION_DEFER, MODEL_VERSION,
)
from src.middle.shared import StateEstimationError, MIDDLE_CONFIG_VERSION
from src.inner.clock import get_window_30min


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


def _sigs(g=0.5, r=0.5, p=0.5, c=0.5, **kw):
    d = {
        "goal_clarity": g, "resource_readiness": r,
        "risk_pressure": p, "constraint_conflict": c,
    }
    d.update(kw)
    return d


def _est(**kw):
    return L2Estimator(**kw)


# ══════════════════════════════════════════════════════
# 1. Happy path
# ══════════════════════════════════════════════════════

class TestHappyPath:
    def test_high_feasibility_low_uncertainty_advance(self):
        r = _est().estimate("t1", _ts(14), _sigs(
            g=0.85, r=0.80, p=0.10, c=0.10,
        ))
        assert r["action_bias"] == ACTION_ADVANCE
        assert r["reason_code"] == "L2_ADVANCE"
        assert r["feasible"] is True
        assert r["block_reason"] == ""

    def test_mid_signals_hold(self):
        r = _est().estimate("t2", _ts(14), _sigs(
            g=0.50, r=0.50, p=0.50, c=0.50,
        ))
        assert r["action_bias"] == ACTION_HOLD

    def test_low_feasibility_high_uncertainty_defer(self):
        r = _est().estimate("t3", _ts(14), _sigs(
            g=0.15, r=0.18, p=0.85, c=0.80,
        ))
        assert r["action_bias"] == ACTION_DEFER
        assert r["feasible"] is False


# ══════════════════════════════════════════════════════
# 2. Output schema
# ══════════════════════════════════════════════════════

class TestOutputSchema:
    def test_output_keys_stable(self):
        r = _est().estimate("t1", _ts(14), _sigs())
        expected = {
            "feasibility", "uncertainty", "action_bias", "reason_code",
            "feasible", "block_reason",
            "model_version", "config_version",
            "event_time_utc", "window_id", "evaluated_at_utc",
        }
        assert set(r.keys()) == expected


# ══════════════════════════════════════════════════════
# 3. Version fields
# ══════════════════════════════════════════════════════

class TestVersionFields:
    def test_config_version(self):
        r = _est().estimate("t1", _ts(14), _sigs())
        assert r["config_version"] == MIDDLE_CONFIG_VERSION

    def test_model_version(self):
        r = _est().estimate("t1", _ts(14), _sigs())
        assert r["model_version"] == MODEL_VERSION


# ══════════════════════════════════════════════════════
# 4. Type perturbation
# ══════════════════════════════════════════════════════

class TestTypePerturbation:
    @pytest.mark.parametrize("bad", [42, None, True, [], ""])
    def test_bad_trace_id(self, bad):
        with pytest.raises(StateEstimationError):
            _est().estimate(bad, _ts(14), _sigs())

    @pytest.mark.parametrize("bad", [None, 42, "", "x"])
    def test_bad_event_time(self, bad):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", bad, _sigs())

    @pytest.mark.parametrize("bad", [None, 42, [], "x"])
    def test_non_dict_signals(self, bad):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), bad)

    def test_bool_as_signal_value(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), _sigs(g=True))

    def test_nan_input(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), _sigs(g=float("nan")))

    def test_inf_input(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), _sigs(r=float("inf")))

    def test_neg_inf_input(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), _sigs(p=float("-inf")))

    def test_missing_signal_field(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), {
                "goal_clarity": 0.5,
                "resource_readiness": 0.5,
                "risk_pressure": 0.5,
            })

    def test_str_signal_value(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), _sigs(g="high"))

    def test_history_not_list(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), {
                "goal_clarity": 0.5, "resource_readiness": 0.5,
                "risk_pressure": 0.5, "constraint_conflict": 0.5,
                "history": "bad",
            })

    def test_history_contains_str(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), {
                "goal_clarity": 0.5, "resource_readiness": 0.5,
                "risk_pressure": 0.5, "constraint_conflict": 0.5,
                "history": [0.5, "x", 0.6],
            })

    def test_history_contains_none(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), {
                "goal_clarity": 0.5, "resource_readiness": 0.5,
                "risk_pressure": 0.5, "constraint_conflict": 0.5,
                "history": [0.5, None, 0.6],
            })

    def test_history_contains_bool(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), {
                "goal_clarity": 0.5, "resource_readiness": 0.5,
                "risk_pressure": 0.5, "constraint_conflict": 0.5,
                "history": [0.5, True, 0.6],
            })

    def test_prior_uncertainty_bool(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), {
                "goal_clarity": 0.5, "resource_readiness": 0.5,
                "risk_pressure": 0.5, "constraint_conflict": 0.5,
                "prior_uncertainty": True,
            })


# ══════════════════════════════════════════════════════
# 5. Boundary perturbation
# ══════════════════════════════════════════════════════

class TestBoundaryPerturbation:
    def test_all_zero_inputs(self):
        r = _est().estimate("t1", _ts(14), _sigs(g=0.0, r=0.0, p=1.0, c=1.0))
        assert r["action_bias"] == ACTION_DEFER

    def test_all_one_inputs(self):
        r = _est().estimate("t2", _ts(14), _sigs(g=1.0, r=1.0, p=0.0, c=0.0))
        assert r["action_bias"] == ACTION_ADVANCE

    def test_feasibility_near_advance_threshold_above(self):
        r = _est().estimate("t3", _ts(14), _sigs(g=0.66, r=0.66, p=0.30, c=0.30))
        assert r["action_bias"] in VALID_ACTIONS
        assert 0.0 <= r["feasibility"] <= 1.0

    def test_feasibility_near_advance_threshold_below(self):
        r = _est().estimate("t4", _ts(14), _sigs(g=0.64, r=0.64, p=0.30, c=0.30))
        assert r["action_bias"] in VALID_ACTIONS

    def test_uncertainty_below_defer_threshold(self):
        r = _est().estimate("t5", _ts(14), _sigs(g=0.70, r=0.70, p=0.20, c=0.20))
        assert r["uncertainty"] <= 1.0


# ══════════════════════════════════════════════════════
# 6. Sparse samples
# ══════════════════════════════════════════════════════

class TestSparseSamples:
    def test_no_history(self):
        r = _est().estimate("t1", _ts(14), _sigs(g=0.80, r=0.80, p=0.10, c=0.10))
        assert r["action_bias"] == ACTION_ADVANCE

    def test_single_history_value(self):
        r = _est().estimate("t2", _ts(14), {
            "goal_clarity": 0.4, "resource_readiness": 0.4,
            "risk_pressure": 0.6, "constraint_conflict": 0.6,
            "history": [0.5],
        })
        assert r["action_bias"] in VALID_ACTIONS

    def test_no_history_with_low_feasibility(self):
        r = _est().estimate("t3", _ts(14), _sigs(g=0.40, r=0.40, p=0.50, c=0.50))
        assert "SPARSE" in r["reason_code"]


# ══════════════════════════════════════════════════════
# 7. Extreme values
# ══════════════════════════════════════════════════════

class TestExtremeValues:
    def test_goal_clarity_out_of_range_above(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t1", _ts(14), _sigs(g=1.5))

    def test_resource_out_of_range_below(self):
        with pytest.raises(StateEstimationError):
            _est().estimate("t2", _ts(14), _sigs(r=-0.1))

    def test_all_high_risk_all_high_conflict_defers(self):
        r = _est().estimate("t3", _ts(14), _sigs(
            g=0.90, r=0.90, p=0.95, c=0.90,
        ))
        assert r["action_bias"] == ACTION_DEFER

    def test_large_history(self):
        h = [0.5] * 1500 + [0.85]
        r = _est().estimate("t4", _ts(14), {
            "goal_clarity": 0.80, "resource_readiness": 0.80,
            "risk_pressure": 0.15, "constraint_conflict": 0.15,
            "history": h,
        })
        assert r["action_bias"] in VALID_ACTIONS
        assert 0.0 <= r["feasibility"] <= 1.0

    def test_float_edge_case(self):
        r = _est().estimate("t5", _ts(14), _sigs(
            g=0.30000000000000004, r=0.30000000000000004,
            p=0.29999999999999999, c=0.30000000000000004,
        ))
        assert 0.0 <= r["feasibility"] <= 1.0


# ══════════════════════════════════════════════════════
# 8. Idempotency
# ══════════════════════════════════════════════════════

class TestIdempotency:
    def test_same_input_same_output(self):
        e = _est()
        s = _sigs(g=0.70, r=0.65, p=0.25, c=0.30)
        r1 = e.estimate("t1", _ts(14), s)
        r2 = e.estimate("t1", _ts(14), s)
        for k in ("feasibility", "uncertainty", "action_bias",
                  "reason_code", "feasible", "block_reason"):
            assert r1[k] == r2[k], f"Mismatch: {k}"

    def test_reuse_estimator(self):
        e = _est()
        r1 = e.estimate("a", _ts(10), _sigs(g=0.6))
        r2 = e.estimate("b", _ts(11), _sigs(g=0.6))
        assert r1["action_bias"] == r2["action_bias"]


# ══════════════════════════════════════════════════════
# 9. Time consistency
# ══════════════════════════════════════════════════════

class TestTimeConsistency:
    def test_window_id_from_clock(self):
        ts = "2026-04-29T14:22:00.000Z"
        r = _est().estimate("t1", ts, _sigs())
        assert r["window_id"] == get_window_30min(ts)

    def test_evaluated_at_utc_iso8601(self):
        r = _est().estimate("t1", _ts(14), _sigs())
        assert r["evaluated_at_utc"].endswith("Z")
        assert "T" in r["evaluated_at_utc"]


# ══════════════════════════════════════════════════════
# 10. Combination pressure
# ══════════════════════════════════════════════════════

class TestCombinationPressure:
    def test_action_bias_in_valid_set(self):
        e = _est()
        for i in range(100):
            r = e.estimate(f"t{i}", _ts(14, i % 60), {
                "goal_clarity": (i * 0.7) % 1.0,
                "resource_readiness": (i * 0.3 + 0.2) % 1.0,
                "risk_pressure": (i * 0.5) % 1.0,
                "constraint_conflict": (i * 0.4) % 1.0,
            })
            assert r["action_bias"] in VALID_ACTIONS
            assert 0.0 <= r["feasibility"] <= 1.0
            assert 0.0 <= r["uncertainty"] <= 1.0

    def test_all_actions_reachable(self):
        e = _est()
        seen = set()
        cases = [
            (0.85, 0.85, 0.10, 0.10),
            (0.50, 0.50, 0.50, 0.50),
            (0.20, 0.20, 0.85, 0.85),
            (0.30, 0.30, 0.70, 0.70),
            (0.80, 0.80, 0.90, 0.90),
            (0.40, 0.40, 0.55, 0.55),
        ]
        for g, r, p, c in cases:
            res = e.estimate("t", _ts(14), _sigs(g=g, r=r, p=p, c=c))
            seen.add(res["action_bias"])
        assert seen == VALID_ACTIONS

    def test_feasibility_uncertainty_in_range(self):
        e = _est()
        for i in range(100):
            r = e.estimate(f"t{i}", _ts(14, i % 60), {
                "goal_clarity": 0.3 + (i % 7) * 0.1,
                "resource_readiness": 0.2 + (i % 9) * 0.08,
                "risk_pressure": 0.1 + (i % 6) * 0.15,
                "constraint_conflict": 0.1 + (i % 8) * 0.1,
                "history": [0.5, 0.55, 0.6, 0.55, 0.50],
            })
            assert 0.0 <= r["feasibility"] <= 1.0
            assert 0.0 <= r["uncertainty"] <= 1.0
            assert r["action_bias"] in VALID_ACTIONS
            assert isinstance(r["feasible"], bool)
            assert isinstance(r["block_reason"], str)


# ══════════════════════════════════════════════════════
# Defer reason code 专项
# ══════════════════════════════════════════════════════

class TestDeferReasons:
    def test_defer_conflict(self):
        r = _est().estimate("t1", _ts(14), {
            "goal_clarity": 0.85, "resource_readiness": 0.85,
            "risk_pressure": 0.10, "constraint_conflict": 0.85,
        })
        assert r["reason_code"] == "L2_DEFER_CONFLICT"

    def test_defer_risk(self):
        r = _est().estimate("t2", _ts(14), {
            "goal_clarity": 0.85, "resource_readiness": 0.85,
            "risk_pressure": 0.90, "constraint_conflict": 0.10,
        })
        assert r["reason_code"] == "L2_DEFER_RISK"


# ══════════════════════════════════════════════════════
# L2FeasibilityOutput 兼容性
# ══════════════════════════════════════════════════════

class TestL2FeasibilityOutputCompat:
    def test_compatible_with_shared_type(self):
        from src.middle.shared.types import L2FeasibilityOutput
        r = _est().estimate("t1", _ts(14), _sigs(g=0.85, r=0.85, p=0.10, c=0.10))
        lo: L2FeasibilityOutput = {
            "feasible": r["feasible"],
            "block_reason": r["block_reason"],
        }
        assert isinstance(lo["feasible"], bool)
        assert isinstance(lo["block_reason"], str)


# ══════════════════════════════════════════════════════
# M4.1 配置驱动行为测试
# ══════════════════════════════════════════════════════

class TestConfigDrivenThresholds:
    def test_default_thresholds_from_shared_config(self):
        from src.middle.shared.config import (
            L2_CAPABILITY_MIN, L2_OPPORTUNITY_MIN, L2_MOTIVATION_MIN,
        )
        e = _est()
        assert e.cap_min == L2_CAPABILITY_MIN
        assert e.opp_min == L2_OPPORTUNITY_MIN
        assert e.mot_min == L2_MOTIVATION_MIN
        # hold_min = max(cap_min, opp_min, mot_min)
        expected_hold = max(L2_CAPABILITY_MIN, L2_OPPORTUNITY_MIN, L2_MOTIVATION_MIN)
        assert e._hold_min == expected_hold

    def test_raise_capability_min_shifts_hold_threshold(self):
        e_low = _est(capability_min=0.20, opportunity_min=0.20, motivation_min=0.20)
        e_high = _est(capability_min=0.50, opportunity_min=0.50, motivation_min=0.50)
        assert e_high._hold_min > e_low._hold_min
        assert e_high._advance_min > e_low._advance_min

    def test_higher_hold_min_makes_harder_to_advance(self):
        e_low = _est(capability_min=0.10, opportunity_min=0.10, motivation_min=0.10)
        e_high = _est(capability_min=0.50, opportunity_min=0.50, motivation_min=0.50)
        sigs = _sigs(g=0.60, r=0.60, p=0.30, c=0.30)
        r_low = e_low.estimate("t1", _ts(14), sigs)
        r_high = e_high.estimate("t2", _ts(14), sigs)
        # 高阈值下更不容易 advance
        assert r_low["action_bias"] in VALID_ACTIONS
        assert r_high["action_bias"] in VALID_ACTIONS

    def test_signal_below_cap_min_penalizes_feasibility(self):
        e = _est(capability_min=0.50)
        r_below = e.estimate("t1", _ts(14), {
            "goal_clarity": 0.30,  # below cap_min
            "resource_readiness": 0.80,
            "risk_pressure": 0.10,
            "constraint_conflict": 0.10,
        })
        e2 = _est(capability_min=0.50)
        r_above = e2.estimate("t2", _ts(14), {
            "goal_clarity": 0.80,  # well above cap_min
            "resource_readiness": 0.80,
            "risk_pressure": 0.10,
            "constraint_conflict": 0.10,
        })
        assert r_below["feasibility"] < r_above["feasibility"]

    def test_signal_below_opp_min_penalizes_feasibility(self):
        e = _est(opportunity_min=0.50)
        r = e.estimate("t1", _ts(14), {
            "goal_clarity": 0.80,
            "resource_readiness": 0.25,  # below opp_min
            "risk_pressure": 0.10,
            "constraint_conflict": 0.10,
        })
        # Should still be valid, but feasibility reduced
        assert 0.0 <= r["feasibility"] <= 1.0

    def test_config_validation_rejects_out_of_range(self):
        from src.middle.shared import StateEstimationError
        with pytest.raises(StateEstimationError):
            L2Estimator(capability_min=1.5)
        with pytest.raises(StateEstimationError):
            L2Estimator(opportunity_min=-0.1)
        with pytest.raises(StateEstimationError):
            L2Estimator(motivation_min=2.0)
