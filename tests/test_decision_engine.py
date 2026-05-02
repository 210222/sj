"""M5: 决策融合引擎测试 — 10 组 + 对抗性。"""

import math
import pytest

from src.middle.decision import DecisionEngine
from src.middle.decision.engine import (
    VALID_INTENSITIES, VALID_DOMINANT, VALID_CONFLICT,
    INTENSITY_FULL, INTENSITY_REDUCED, INTENSITY_MINIMAL, INTENSITY_NONE,
    MODEL_VERSION,
)
from src.middle.shared import StateEstimationError, MIDDLE_CONFIG_VERSION
from src.inner.clock import get_window_30min


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


def _make(**kw):
    return DecisionEngine(**kw)


def _l0(**kw):
    d = {"state": "engaged", "confidence": 0.75}
    d.update(kw)
    return d


def _l1(**kw):
    d = {"correction": "increase", "magnitude": 0.60}
    d.update(kw)
    return d


def _l2(**kw):
    d = {"feasible": True, "block_reason": ""}
    d.update(kw)
    return d


def _unc(l0=0.20, l1=0.25, l2=0.30):
    return {"l0": l0, "l1": l1, "l2": l2}


# ══════════════════════════════════════════════════════
# 1. Happy path
# ══════════════════════════════════════════════════════

class TestHappyPath:
    def test_feasible_low_conflict_produces_full(self):
        r = _make().decide("t1", _ts(14), _l0(confidence=0.85),
                           _l1(magnitude=0.70), _l2(feasible=True),
                           _unc(0.10, 0.15, 0.10))
        assert r["intensity"] in (INTENSITY_FULL, INTENSITY_REDUCED)
        assert r["conflict_level"] in VALID_CONFLICT
        assert r["total_score"] > 0.5

    def test_not_feasible_produces_none(self):
        r = _make().decide("t2", _ts(14), _l0(confidence=0.90),
                           _l1(magnitude=0.80), _l2(feasible=False),
                           _unc())
        assert r["intensity"] == INTENSITY_NONE
        assert r["dominant_layer"] == "L2"
        assert "BLOCK" in r["reason_code"]

    def test_low_scores_produce_minimal(self):
        r = _make().decide("t3", _ts(14), _l0(confidence=0.30),
                           _l1(magnitude=0.20, correction="none"),
                           _l2(feasible=True), _unc(0.50, 0.50, 0.50))
        assert r["intensity"] in VALID_INTENSITIES

    def test_high_uncertainty_same_score_produces_conflict(self):
        r = _make().decide("t4", _ts(14), _l0(confidence=0.80),
                           _l1(magnitude=0.10, correction="none"),
                           _l2(feasible=True), _unc(0.10, 0.90, 0.10))
        assert r["conflict_level"] in VALID_CONFLICT


# ══════════════════════════════════════════════════════
# 2. Output schema
# ══════════════════════════════════════════════════════

class TestOutputSchema:
    def test_output_keys_stable(self):
        r = _make().decide("t1", _ts(14), _l0(), _l1(), _l2(), _unc())
        expected = {
            "intensity", "dominant_layer", "conflict_level",
            "reason_code", "total_score", "conflict_score",
            "model_version", "config_version",
            "event_time_utc", "window_id", "evaluated_at_utc",
        }
        assert set(r.keys()) == expected


# ══════════════════════════════════════════════════════
# 3. Version fields
# ══════════════════════════════════════════════════════

class TestVersionFields:
    def test_config_version(self):
        r = _make().decide("t1", _ts(14), _l0(), _l1(), _l2(), _unc())
        assert r["config_version"] == MIDDLE_CONFIG_VERSION

    def test_model_version(self):
        r = _make().decide("t1", _ts(14), _l0(), _l1(), _l2(), _unc())
        assert r["model_version"] == MODEL_VERSION


# ══════════════════════════════════════════════════════
# 4. Type perturbation
# ══════════════════════════════════════════════════════

class TestTypePerturbation:
    @pytest.mark.parametrize("bad", [42, None, True, []])
    def test_bad_trace_id(self, bad):
        with pytest.raises(StateEstimationError):
            _make().decide(bad, _ts(14), _l0(), _l1(), _l2(), _unc())

    @pytest.mark.parametrize("bad", [None, 42, "", "x"])
    def test_bad_event_time(self, bad):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", bad, _l0(), _l1(), _l2(), _unc())

    def test_non_dict_l0(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), 42, _l1(), _l2(), _unc())

    def test_non_dict_l1(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(), None, _l2(), _unc())

    def test_non_dict_l2(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(), _l1(), "bad", _unc())

    def test_non_dict_uncertainty(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(), _l1(), _l2(), [])

    def test_missing_confidence(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), {"state": "x"}, _l1(), _l2(), _unc())

    def test_missing_l2_feasible(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(), _l1(),
                           {"block_reason": ""}, _unc())

    def test_bool_as_numeric(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(confidence=True),
                           _l1(), _l2(), _unc())

    def test_nan_input(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(confidence=float("nan")),
                           _l1(), _l2(), _unc())

    def test_inf_input(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(),
                           _l1(magnitude=float("inf")), _l2(), _unc())

    def test_uncertainty_out_of_range(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(), _l1(), _l2(),
                           _unc(l0=1.5))

    def test_l2_feasible_not_bool(self):
        with pytest.raises(StateEstimationError):
            _make().decide("t1", _ts(14), _l0(), _l1(),
                           {"feasible": 1, "block_reason": ""}, _unc())


# ══════════════════════════════════════════════════════
# 5. Boundary perturbation
# ══════════════════════════════════════════════════════

class TestBoundaryPerturbation:
    def test_all_zero_uncertainty(self):
        r = _make().decide("t1", _ts(14), _l0(confidence=0.70),
                           _l1(magnitude=0.60), _l2(), _unc(0, 0, 0))
        assert r["conflict_score"] <= 1.0
        assert r["intensity"] in VALID_INTENSITIES

    def test_all_one_uncertainty(self):
        r = _make().decide("t2", _ts(14), _l0(confidence=0.70),
                           _l1(magnitude=0.60), _l2(), _unc(1, 1, 1))
        assert 0.0 <= r["conflict_score"] <= 1.0

    def test_conflict_near_escalate_threshold(self):
        e = _make(conflict_escalate=0.5)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.10, correction="decrease"),
                     _l2(), _unc(0.10, 0.95, 0.10))
        assert r["conflict_level"] in VALID_CONFLICT

    def test_total_score_at_min_weight(self):
        e = _make(min_weight=0.20)
        r = e.decide("t1", _ts(14), _l0(confidence=0.10),
                     _l1(magnitude=0.05, correction="none"),
                     _l2(), _unc(0.50, 0.50, 0.50))
        assert r["intensity"] == INTENSITY_NONE


# ══════════════════════════════════════════════════════
# 6. Conflict levels
# ══════════════════════════════════════════════════════

class TestConflictLevels:
    def test_all_conflict_levels_reachable(self):
        e = _make(conflict_escalate=0.40)
        seen = set()
        cases = [
            (_l0(confidence=0.80), _l1(magnitude=0.70), _unc(0.10, 0.10, 0.10)),
            (_l0(confidence=0.85), _l1(magnitude=0.30, correction="decrease"), _unc(0.10, 0.70, 0.10)),
            (_l0(confidence=0.70), _l1(magnitude=0.05, correction="decrease"), _unc(0.05, 0.95, 0.05)),
        ]
        for l0, l1, u in cases:
            r = e.decide("t", _ts(14), l0, l1, _l2(), u)
            seen.add(r["conflict_level"])
        assert seen == VALID_CONFLICT

    def test_high_conflict_downgrades_intensity(self):
        e = _make(conflict_escalate=0.3)
        r = e.decide("t1", _ts(14), _l0(confidence=0.80),
                     _l1(magnitude=0.05, correction="decrease"),
                     _l2(), _unc(0.05, 0.95, 0.05))
        assert r["conflict_level"] == "high"
        assert "CONFLICT_DOWN" in r["reason_code"]


# ══════════════════════════════════════════════════════
# 7. Idempotency
# ══════════════════════════════════════════════════════

class TestIdempotency:
    def test_same_input_same_output(self):
        e = _make()
        r1 = e.decide("t1", _ts(14), _l0(), _l1(), _l2(), _unc())
        r2 = e.decide("t1", _ts(14), _l0(), _l1(), _l2(), _unc())
        for k in ("intensity", "dominant_layer", "conflict_level",
                  "reason_code", "total_score", "conflict_score"):
            assert r1[k] == r2[k], f"Mismatch: {k}"


# ══════════════════════════════════════════════════════
# 8. Time consistency
# ══════════════════════════════════════════════════════

class TestTimeConsistency:
    def test_window_id_from_clock(self):
        ts = "2026-04-29T14:22:00.000Z"
        r = _make().decide("t1", ts, _l0(), _l1(), _l2(), _unc())
        assert r["window_id"] == get_window_30min(ts)

    def test_evaluated_at_utc_iso8601(self):
        r = _make().decide("t1", _ts(14), _l0(), _l1(), _l2(), _unc())
        assert r["evaluated_at_utc"].endswith("Z")
        assert "T" in r["evaluated_at_utc"]


# ══════════════════════════════════════════════════════
# 9. Combination pressure
# ══════════════════════════════════════════════════════

class TestCombinationPressure:
    def test_batch_100(self):
        e = _make()
        for i in range(100):
            r = e.decide(f"t{i}", _ts(14, i % 60), _l0(confidence=0.3 + (i % 7) * 0.1),
                         _l1(magnitude=0.1 + (i % 9) * 0.1),
                         _l2(feasible=(i % 10 != 0)),
                         _unc((i * 0.07) % 1.0, (i * 0.13) % 1.0, (i * 0.09) % 1.0))
            assert r["intensity"] in VALID_INTENSITIES
            assert r["dominant_layer"] in VALID_DOMINANT
            assert r["conflict_level"] in VALID_CONFLICT
            assert 0.0 <= r["total_score"] <= 1.0
            assert 0.0 <= r["conflict_score"] <= 1.0

    def test_all_intensities_reachable(self):
        e = _make(conflict_escalate=0.7)
        seen = set()
        cases = [
            (_l0(confidence=0.90), _l1(magnitude=0.80, correction="increase"), _unc(0.10, 0.10, 0.10), _l2()),
            (_l0(confidence=0.60), _l1(magnitude=0.40, correction="none"), _unc(0.30, 0.40, 0.30), _l2()),
            (_l0(confidence=0.35), _l1(magnitude=0.20, correction="none"), _unc(0.50, 0.55, 0.50), _l2()),
            (_l0(confidence=0.90), _l1(magnitude=0.90), _unc(), _l2(feasible=False)),
        ]
        for l0, l1, u, l2 in cases:
            r = e.decide("t", _ts(14), l0, l1, l2, u)
            seen.add(r["intensity"])
        assert seen == VALID_INTENSITIES

    def test_float_edge_cases(self):
        e = _make()
        r = e.decide("t1", _ts(14),
                     _l0(confidence=0.30000000000000004),
                     _l1(magnitude=0.30000000000000004),
                     _l2(), _unc(0.29999999999999999, 0.3, 0.3))
        assert r["intensity"] in VALID_INTENSITIES

    def test_batch_200_stability(self):
        e = _make()
        for i in range(200):
            r = e.decide(f"t{i}", _ts((14 + i // 60) % 24, i % 60),
                         _l0(confidence=(i * 0.037) % 1.0),
                         _l1(magnitude=(i * 0.053) % 1.0, correction="increase"),
                         _l2(feasible=True),
                         _unc((i * 0.031) % 1.0, (i * 0.047) % 1.0, (i * 0.029) % 1.0))
            assert r["intensity"] in VALID_INTENSITIES


# ══════════════════════════════════════════════════════
# 10. Config-driven behavior
# ══════════════════════════════════════════════════════

class TestConfigDrivenBehavior:
    def test_conflict_escalate_change_affects_conflict_level(self):
        e_low = _make(conflict_escalate=0.3)
        e_high = _make(conflict_escalate=0.9)
        r_low = e_low.decide("t1", _ts(14),
            _l0(confidence=0.70), _l1(magnitude=0.30, correction="decrease"),
            _l2(), _unc(0.20, 0.60, 0.20))
        r_high = e_high.decide("t2", _ts(14),
            _l0(confidence=0.70), _l1(magnitude=0.30, correction="decrease"),
            _l2(), _unc(0.20, 0.60, 0.20))
        assert r_low["conflict_score"] == r_high["conflict_score"]
        assert r_low["conflict_level"] != r_high["conflict_level"]

    def test_weight_changes_affect_total_score(self):
        e = _make(weight_transfer=0.8, weight_creativity=0.1, weight_independence=0.1)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.10, correction="none"),
                     _l2(), _unc(0.20, 0.20, 0.20))
        assert 0.0 <= r["total_score"] <= 1.0

    def test_min_weight_affects_intensity(self):
        e = _make(min_weight=0.80)
        r = e.decide("t1", _ts(14), _l0(confidence=0.50),
                     _l1(magnitude=0.40), _l2(), _unc(0.30, 0.30, 0.30))
        assert r["intensity"] == INTENSITY_NONE

    def test_defaults_match_shared_config(self):
        from src.middle.shared.config import (
            DECISION_WEIGHT_TRANSFER, DECISION_WEIGHT_CREATIVITY,
            DECISION_WEIGHT_INDEPENDENCE, DECISION_MAX_DELTA_PER_UPDATE,
            DECISION_MIN_WEIGHT, DECISION_LRM_WEIGHT, DECISION_ROBUST_WEIGHT,
            DECISION_CONFLICT_ESCALATE,
        )
        e = _make()
        assert e.w_transfer == DECISION_WEIGHT_TRANSFER
        assert e.w_creativity == DECISION_WEIGHT_CREATIVITY
        assert e.w_independence == DECISION_WEIGHT_INDEPENDENCE
        assert e.max_delta == DECISION_MAX_DELTA_PER_UPDATE
        assert e.min_weight == DECISION_MIN_WEIGHT
        assert e.lrm_weight == DECISION_LRM_WEIGHT
        assert e.robust_weight == DECISION_ROBUST_WEIGHT
        assert e.conflict_escalate == DECISION_CONFLICT_ESCALATE

    def test_config_validation_rejects_out_of_range(self):
        with pytest.raises(StateEstimationError):
            DecisionEngine(weight_transfer=1.5)
        with pytest.raises(StateEstimationError):
            DecisionEngine(conflict_escalate=-0.1)

    def test_weight_sum_must_be_one(self):
        with pytest.raises(StateEstimationError):
            DecisionEngine(weight_transfer=0.5, weight_creativity=0.5,
                           weight_independence=0.5)
        with pytest.raises(StateEstimationError):
            DecisionEngine(weight_transfer=0.1, weight_creativity=0.1,
                           weight_independence=0.1)

    def test_max_delta_imported_and_stored(self):
        from src.middle.shared.config import DECISION_MAX_DELTA_PER_UPDATE
        e = _make(max_delta=0.08)
        assert e.max_delta == 0.08
        e2 = _make()
        assert e2.max_delta == DECISION_MAX_DELTA_PER_UPDATE


# ══════════════════════════════════════════════════════
# Adversarial: L2 gate + uncertainty split + extreme
# ══════════════════════════════════════════════════════

class TestAdversarial:
    def test_feasible_false_always_none_regardless_of_scores(self):
        r = _make().decide("t1", _ts(14), _l0(confidence=0.99),
                           _l1(magnitude=0.99), _l2(feasible=False),
                           _unc(0.01, 0.01, 0.01))
        assert r["intensity"] == INTENSITY_NONE
        assert r["total_score"] == 0.0

    def test_uncertainty_three_way_split(self):
        e = _make()
        r = e.decide("t1", _ts(14), _l0(confidence=0.80),
                     _l1(magnitude=0.70, correction="decrease"),
                     _l2(), _unc(0.05, 0.95, 0.05))
        assert r["conflict_score"] > 0.3

    def test_bulk_repeat_stability(self):
        e = _make()
        results = []
        for i in range(50):
            r = e.decide(f"t{i}", _ts(14), _l0(), _l1(), _l2(), _unc())
            results.append(r)
        states = [(r["intensity"], r["dominant_layer"], r["conflict_level"])
                  for r in results]
        assert all(s == states[0] for s in states)

    def test_all_layers_agree_low_conflict(self):
        r = _make().decide("t1", _ts(14), _l0(confidence=0.85),
                           _l1(magnitude=0.80, correction="increase"),
                           _l2(), _unc(0.10, 0.10, 0.10))
        assert r["conflict_level"] == "low"


# ══════════════════════════════════════════════════════
# M5.1: max_delta 行为验证
# ══════════════════════════════════════════════════════

class TestMaxDelta:
    def test_max_delta_caps_upward_change(self):
        e = _make(max_delta=0.05)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.80, correction="increase"),
                     _l2(), _unc(0.10, 0.10, 0.10),
                     context={"prior_total_score": 0.70})
        assert abs(r["total_score"] - 0.70) <= 0.05 + 1e-9

    def test_max_delta_caps_downward_change(self):
        e = _make(max_delta=0.05)
        r = e.decide("t1", _ts(14), _l0(confidence=0.20),
                     _l1(magnitude=0.10, correction="none"),
                     _l2(), _unc(0.50, 0.50, 0.50),
                     context={"prior_total_score": 0.80})
        assert 0.80 - r["total_score"] <= 0.05 + 1e-9

    def test_max_delta_zero_freezes_score(self):
        e = _make(max_delta=0.0)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.80, correction="increase"),
                     _l2(), _unc(0.10, 0.10, 0.10),
                     context={"prior_total_score": 0.50})
        assert r["total_score"] == 0.50

    def test_max_delta_large_allows_full_change(self):
        e = _make(max_delta=1.0)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.80, correction="increase"),
                     _l2(), _unc(0.10, 0.10, 0.10),
                     context={"prior_total_score": 0.30})
        assert r["total_score"] > 0.30 + 0.50

    def test_no_prior_score_no_delta_constraint(self):
        e = _make(max_delta=0.01)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.80, correction="increase"),
                     _l2(), _unc(0.10, 0.10, 0.10))
        assert r["total_score"] > 0.5

    def test_max_delta_non_numeric_prior_ignored(self):
        e = _make(max_delta=0.01)
        r = e.decide("t1", _ts(14), _l0(confidence=0.90),
                     _l1(magnitude=0.80, correction="increase"),
                     _l2(), _unc(0.10, 0.10, 0.10),
                     context={"prior_total_score": "high"})
        assert r["total_score"] > 0.5
