"""M6: 语义安全引擎测试 — 10 组 + 对抗性。"""

import math
import pytest

from src.middle.semantic_safety import SemanticSafetyEngine
from src.middle.semantic_safety.engine import MODEL_VERSION
from src.middle.shared import StateEstimationError, MIDDLE_CONFIG_VERSION
from src.middle.shared.config import (
    SEMANTIC_SAFETY_MIN_SCORE, SEMANTIC_SAFETY_BLOCK_THRESHOLD,
)
from src.inner.clock import get_window_30min


def _ts(h=12, m=0):
    return f"2026-04-29T{h:02d}:{m:02d}:00.000Z"


def _make(**kw):
    return SemanticSafetyEngine(**kw)


def _cand(**kw):
    d = {"intensity": "reduced", "reason_code": "DEC_REDUCED"}
    d.update(kw)
    return d


def _ctx(**kw):
    d = {"p0_count": 0, "p1_count": 0, "gate_decision": "GO"}
    d.update(kw)
    return d


# ════════════════════════════════════
# 1. Happy path
# ════════════════════════════════════

class TestHappyPath:
    def test_clean_input_pass(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        assert r["allowed"] is True
        assert r["audit_level"] == "pass"
        assert r["reason_code"] == "SEM_PASS"
        assert r["safety_score"] > 0.7

    def test_pass_sanitized_keeps_candidate(self):
        r = _make().evaluate("t2", _ts(14), _cand(), _ctx())
        assert r["sanitized_output"]["intensity"] == "reduced"
        assert r["sanitized_output"]["_safety_audit"] == "pass"


# ════════════════════════════════════
# 2. P0 hard block
# ════════════════════════════════════

class TestP0Block:
    def test_p0_count_one_blocks(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx(p0_count=1))
        assert r["allowed"] is False
        assert r["audit_level"] == "p0_block"
        assert r["reason_code"] == "SEM_BLOCK_P0"
        assert r["safety_score"] == 0.0

    def test_p0_block_sanitized_has_intensity_none(self):
        r = _make().evaluate("t2", _ts(14), _cand(intensity="full"),
                             _ctx(p0_count=2))
        assert r["sanitized_output"]["intensity"] == "none"
        assert "action_plan" not in r["sanitized_output"]

    def test_p0_overrides_everything(self):
        r = _make().evaluate("t3", _ts(14), _cand(intensity="full"),
                             _ctx(p0_count=1, p1_count=0, gate_decision="GO"))
        assert r["allowed"] is False
        assert r["audit_level"] == "p0_block"


# ════════════════════════════════════
# 3. P1 degradation
# ════════════════════════════════════

class TestP1Degradation:
    def test_p1_count_lowers_safety_score(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx(p1_count=2))
        assert r["safety_score"] < 0.85
        assert r["audit_level"] in ("p1_warn", "p1_freeze")

    def test_p1_count_zero_does_not_penalize(self):
        r = _make().evaluate("t2", _ts(14), _cand(), _ctx(p1_count=0))
        assert r["safety_score"] >= 0.80


# ════════════════════════════════════
# 4. Gate linkage
# ════════════════════════════════════

class TestGateLinkage:
    def test_gate_go_is_safest(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx(gate_decision="GO"))
        assert r["safety_score"] >= 0.80

    def test_gate_warn_reduces_score(self):
        r = _make().evaluate("t2", _ts(14), _cand(), _ctx(gate_decision="WARN"))
        assert r["safety_score"] < 0.85

    def test_gate_freeze_reduces_score_more_than_warn(self):
        r_w = _make().evaluate("tw", _ts(14), _cand(), _ctx(gate_decision="WARN"))
        r_f = _make().evaluate("tf", _ts(14), _cand(), _ctx(gate_decision="FREEZE"))
        assert r_f["safety_score"] < r_w["safety_score"]

    def test_gate_freeze_triggers_freeze_audit(self):
        r = _make().evaluate("t3", _ts(14), _cand(), _ctx(gate_decision="FREEZE"))
        assert r["audit_level"] == "p1_freeze"


# ════════════════════════════════════
# 5. Output schema
# ════════════════════════════════════

class TestOutputSchema:
    def test_output_keys_stable(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        expected = {
            "allowed", "safety_score", "audit_level", "reason_code",
            "sanitized_output", "model_version", "config_version",
            "event_time_utc", "window_id", "evaluated_at_utc",
        }
        assert set(r.keys()) == expected

    def test_model_version(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        assert r["model_version"] == MODEL_VERSION

    def test_config_version(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        assert r["config_version"] == MIDDLE_CONFIG_VERSION


# ════════════════════════════════════
# 6. Type perturbation
# ════════════════════════════════════

class TestTypePerturbation:
    @pytest.mark.parametrize("bad", [42, None, True, []])
    def test_bad_trace_id(self, bad):
        with pytest.raises(StateEstimationError):
            _make().evaluate(bad, _ts(14), _cand(), _ctx())

    @pytest.mark.parametrize("bad", [None, 42, "", "x"])
    def test_bad_event_time(self, bad):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", bad, _cand(), _ctx())

    def test_non_dict_candidate(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), None, _ctx())

    def test_non_dict_context(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(), [])

    def test_candidate_missing_intensity(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), {"reason_code": "x"}, _ctx())

    def test_candidate_invalid_intensity(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(intensity="invalid"), _ctx())

    def test_candidate_missing_reason_code(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), {"intensity": "none"}, _ctx())

    def test_p0_count_bool_raises(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(), _ctx(p0_count=True))

    def test_p1_count_nan_raises(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(),
                             _ctx(p1_count=float("nan")))

    def test_p1_count_inf_raises(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(),
                             _ctx(p1_count=float("inf")))

    def test_p1_count_negative_raises(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(), _ctx(p1_count=-1))

    def test_p1_count_str_raises(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(), _ctx(p1_count="high"))

    def test_gate_decision_invalid(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(), _ctx(gate_decision="BAD"))

    def test_risk_flags_not_list(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(),
                             _ctx(risk_flags="flag"))

    def test_risk_flags_contains_non_str(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), _cand(),
                             _ctx(risk_flags=[42]))


# ════════════════════════════════════
# 7. Boundary thresholds
# ════════════════════════════════════

class TestBoundaryThresholds:
    def test_score_at_block_threshold_below(self):
        e = _make(block_threshold=0.30, min_score=0.50)
        r = e.evaluate("t1", _ts(14), _cand(intensity="none"),
                       _ctx(p1_count=5, gate_decision="FREEZE"))
        assert r["audit_level"] in ("p0_block", "p1_freeze")

    def test_score_at_min_threshold_above(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        assert r["safety_score"] >= SEMANTIC_SAFETY_MIN_SCORE


# ════════════════════════════════════
# 8. Idempotency
# ════════════════════════════════════

class TestIdempotency:
    def test_same_input_same_output(self):
        e = _make()
        r1 = e.evaluate("t1", _ts(14), _cand(),
                        _ctx(p1_count=1, gate_decision="WARN"))
        r2 = e.evaluate("t1", _ts(14), _cand(),
                        _ctx(p1_count=1, gate_decision="WARN"))
        for k in ("allowed", "safety_score", "audit_level", "reason_code"):
            assert r1[k] == r2[k], f"Mismatch: {k}"


# ════════════════════════════════════
# 9. Time consistency
# ════════════════════════════════════

class TestTimeConsistency:
    def test_window_id_from_clock(self):
        ts = "2026-04-29T14:22:00.000Z"
        r = _make().evaluate("t1", ts, _cand(), _ctx())
        assert r["window_id"] == get_window_30min(ts)

    def test_evaluated_at_utc_iso8601(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        assert r["evaluated_at_utc"].endswith("Z")
        assert "T" in r["evaluated_at_utc"]


# ════════════════════════════════════
# 10. Combination pressure
# ════════════════════════════════════

class TestCombinationPressure:
    def test_batch_100(self):
        e = _make()
        gates = ["GO", "WARN", "FREEZE"]
        intensities = ["full", "reduced", "minimal", "none"]
        for i in range(100):
            r = e.evaluate(f"t{i}", _ts(14, i % 60),
                           _cand(intensity=intensities[i % 4]),
                           _ctx(p0_count=0 if i % 10 != 5 else 1,
                                p1_count=i % 4,
                                gate_decision=gates[i % 3]))
            assert r["audit_level"] in ("pass", "p1_warn", "p1_freeze", "p0_block")
            assert 0.0 <= r["safety_score"] <= 1.0
            assert isinstance(r["allowed"], bool)
            assert isinstance(r["sanitized_output"], dict)

    def test_all_audit_levels_reachable(self):
        e = _make()
        seen = set()
        cases = [
            (_cand(), _ctx()),                                                 # pass
            (_cand(), _ctx(p0_count=1)),                                       # p0_block
            (_cand(), _ctx(p1_count=2)),                                       # p1_warn
            (_cand(intensity="reduced"), _ctx(p1_count=1, gate_decision="FREEZE")),  # p1_freeze
        ]
        for cand, ctx in cases:
            r = e.evaluate("t", _ts(14), cand, ctx)
            seen.add(r["audit_level"])
        assert seen == {"pass", "p1_warn", "p1_freeze", "p0_block"}

    def test_batch_200_stability(self):
        e = _make()
        for i in range(200):
            r = e.evaluate(f"t{i}", _ts((14 + i // 60) % 24, i % 60),
                           _cand(intensity="reduced"),
                           _ctx(p0_count=0,
                                p1_count=i % 3,
                                gate_decision="GO" if i % 5 else "WARN"))
            assert "audit_level" in r


# ════════════════════════════════════
# Config-driven behavior
# ════════════════════════════════════

class TestConfigDrivenBehavior:
    def test_min_score_affects_audit(self):
        e_low = _make(min_score=0.30, block_threshold=0.10)
        e_high = _make(min_score=0.90, block_threshold=0.60)
        ctx = _ctx(p1_count=1, gate_decision="FREEZE")
        r_low = e_low.evaluate("t1", _ts(14), _cand(), ctx)
        r_high = e_high.evaluate("t2", _ts(14), _cand(), ctx)
        assert r_low["audit_level"] != r_high["audit_level"]

    def test_block_threshold_affects_block(self):
        e = _make(block_threshold=0.60, min_score=0.80)
        r = e.evaluate("t1", _ts(14), _cand(),
                       _ctx(p1_count=5, gate_decision="FREEZE"))
        assert r["safety_score"] < e.min_score

    def test_config_rejects_invalid_thresholds(self):
        with pytest.raises(StateEstimationError):
            SemanticSafetyEngine(min_score=0.30, block_threshold=0.50)
        with pytest.raises(StateEstimationError):
            SemanticSafetyEngine(min_score=1.5)


# ════════════════════════════════════
# Adversarial
# ════════════════════════════════════

class TestAdversarial:
    def test_double_conflict_p1_plus_freeze_plus_low_score(self):
        r = _make().evaluate("t1", _ts(14), _cand(intensity="full"),
                             _ctx(p0_count=0, p1_count=7,
                                  gate_decision="FREEZE",
                                  risk_flags=["R1", "R2", "R3"]))
        assert r["audit_level"] == "p0_block"
        assert r["allowed"] is False

    def test_risk_flags_reduce_score(self):
        r_no = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        r_yes = _make().evaluate("t2", _ts(14), _cand(),
                                 _ctx(risk_flags=["F1", "F2"]))
        assert r_yes["safety_score"] < r_no["safety_score"]

    def test_large_p1_count(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx(p1_count=100))
        assert r["audit_level"] == "p0_block"

    def test_p1_float_count(self):
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx(p1_count=1.5))
        assert r["safety_score"] < 0.85

    def test_sanitized_block_removes_sensitive(self):
        r = _make().evaluate("t1", _ts(14), _cand(
            intensity="full",
            action_plan="do something",
            metadata={"key": "val"},
        ), _ctx(p0_count=1))
        s = r["sanitized_output"]
        assert s["intensity"] == "none"
        assert "action_plan" not in s
        assert "metadata" not in s
        assert s["_safety_audit"] == "p0_block"

    def test_sanitized_freeze_downgrades_intensity(self):
        r = _make().evaluate("t1", _ts(14), _cand(intensity="full"),
                             _ctx(p1_count=1, gate_decision="FREEZE"))
        s = r["sanitized_output"]
        assert s["intensity"] in ("reduced", "minimal", "none")
        assert s["_safety_audit"] in ("p1_freeze", "p1_warn")

    def test_sanitized_warn_preserves_intensity(self):
        r = _make().evaluate("t1", _ts(14), _cand(intensity="reduced"),
                             _ctx(p1_count=1))
        s = r["sanitized_output"]
        assert s["intensity"] == "reduced"
        assert s["_safety_audit"] == "p1_warn"


# ════════════════════════════════════
# M6.1: 契约严谨性补强
# ════════════════════════════════════

class TestContractRigor:
    def test_reason_code_non_string_raises(self):
        with pytest.raises(StateEstimationError):
            _make().evaluate("t1", _ts(14), {"intensity": "none", "reason_code": 42}, _ctx())
        with pytest.raises(StateEstimationError):
            _make().evaluate("t2", _ts(14), {"intensity": "none", "reason_code": None}, _ctx())

    def test_reason_code_empty_string_is_accepted(self):
        r = _make().evaluate("t1", _ts(14), {"intensity": "none", "reason_code": ""}, _ctx())
        assert "audit_level" in r

    def test_audit_level_output_is_in_audit_levels(self):
        from src.middle.shared.constants import AUDIT_LEVELS
        r = _make().evaluate("t1", _ts(14), _cand(), _ctx())
        assert r["audit_level"] in AUDIT_LEVELS
        r2 = _make().evaluate("t2", _ts(14), _cand(), _ctx(p0_count=1))
        assert r2["audit_level"] in AUDIT_LEVELS
        r3 = _make().evaluate("t3", _ts(14), _cand(),
                              _ctx(p1_count=1, gate_decision="FREEZE"))
        assert r3["audit_level"] in AUDIT_LEVELS
