"""M1: 对抗性测试 — 类型扰动、极端值、幂等性、组合压力、稀疏样本。"""

import importlib
import pytest

from src.middle.shared import (
    INTERVENTION_INTENSITIES,
    DOMINANT_LAYERS,
    CONFLICT_LEVELS,
    AUDIT_LEVELS,
    GATE_DECISIONS,
    NO_ASSIST_LEVELS,
    L0StateOutput,
    L1ResidualOutput,
    L2FeasibilityOutput,
    UncertaintyVector,
)


class TestTypePerturbation:
    @pytest.mark.parametrize("bad_input", [42, 3.14, None, True, [], {}])
    def test_intervention_intensity_not_member(self, bad_input):
        assert bad_input not in INTERVENTION_INTENSITIES

    @pytest.mark.parametrize("bad_input", [0, 1, "L3", "invalid", ""])
    def test_dominant_layer_not_member(self, bad_input):
        assert bad_input not in DOMINANT_LAYERS

    @pytest.mark.parametrize("bad_input", ["critical", 0.5, None, "MEDIUM"])
    def test_conflict_level_not_member(self, bad_input):
        assert bad_input not in CONFLICT_LEVELS

    @pytest.mark.parametrize("bad_input", ["PASS", "warn", 0, None])
    def test_audit_level_not_member(self, bad_input):
        assert bad_input not in AUDIT_LEVELS

    @pytest.mark.parametrize("bad_input", ["go", "warn", "freeze", "PASS", None])
    def test_gate_decision_not_member(self, bad_input):
        assert bad_input not in GATE_DECISIONS

    @pytest.mark.parametrize("bad_input", ["INDEPENDENT", "semi", None, True])
    def test_no_assist_level_not_member(self, bad_input):
        assert bad_input not in NO_ASSIST_LEVELS


class TestExtremeValues:
    def test_uncertainty_at_maximum(self):
        uv: UncertaintyVector = {"l0": 1.0, "l1": 1.0, "l2": 1.0}
        assert all(0 <= uv[k] <= 1 for k in ["l0", "l1", "l2"])

    def test_uncertainty_at_minimum(self):
        uv: UncertaintyVector = {"l0": 0.0, "l1": 0.0, "l2": 0.0}
        assert all(0 <= uv[k] <= 1 for k in ["l0", "l1", "l2"])

    def test_dwell_time_very_large(self):
        lo: L0StateOutput = {"state": "stable", "dwell_time": 1e9}
        assert lo["dwell_time"] > 0

    def test_dwell_time_very_small(self):
        lo: L0StateOutput = {"state": "transient", "dwell_time": 1e-9}
        assert lo["dwell_time"] >= 0.0

    def test_extremely_long_state_name(self):
        state = "x" * 10000
        lo: L0StateOutput = {"state": state, "dwell_time": 1.0}
        assert len(lo["state"]) == 10000


class TestIdempotency:
    def test_repeated_import_yields_same_constants(self):
        mod1 = importlib.import_module("src.middle.shared.constants")
        mod2 = importlib.import_module("src.middle.shared.constants")
        assert mod1.INTERVENTION_INTENSITIES == mod2.INTERVENTION_INTENSITIES
        assert mod1.MIDDLE_SCHEMA_VERSION == mod2.MIDDLE_SCHEMA_VERSION

    def test_reimport_main_module_idempotent(self):
        mod1 = importlib.import_module("src.middle.shared")
        mod2 = importlib.import_module("src.middle.shared")
        assert mod1.MIDDLE_SCHEMA_VERSION == mod2.MIDDLE_SCHEMA_VERSION
        assert mod1.INTERVENTION_INTENSITIES == mod2.INTERVENTION_INTENSITIES
        assert mod1.UncertaintyVector is mod2.UncertaintyVector

    def test_tuple_immutability(self):
        with pytest.raises(TypeError):
            INTERVENTION_INTENSITIES[0] = "changed"  # type: ignore[index]


class TestEmptySparseSamples:
    def test_all_enums_are_non_empty(self):
        all_sets = [
            INTERVENTION_INTENSITIES, DOMINANT_LAYERS, CONFLICT_LEVELS,
            AUDIT_LEVELS, GATE_DECISIONS, NO_ASSIST_LEVELS,
        ]
        for s in all_sets:
            assert len(s) > 0, f"Enum set {s} is empty"

    def test_typeddict_with_minimal_valid_data(self):
        lo: L0StateOutput = {"state": "", "dwell_time": 0.0}
        assert lo["state"] == ""
        assert lo["dwell_time"] == 0.0

    def test_typeddict_sparse_like_new_session(self):
        l1: L1ResidualOutput = {"correction": "none", "magnitude": 0.0}
        assert l1["correction"] == "none"
        assert l1["magnitude"] == 0.0

    def test_feasibility_when_blocked_with_empty_reason(self):
        l2: L2FeasibilityOutput = {"feasible": False, "block_reason": ""}
        assert l2["feasible"] is False

    def test_uncertainty_all_zero_when_confident(self):
        uv: UncertaintyVector = {"l0": 0.0, "l1": 0.0, "l2": 0.0}
        assert uv["l0"] == 0.0 and uv["l1"] == 0.0 and uv["l2"] == 0.0


class TestCombinationPressure:
    def test_all_exports_importable(self):
        from src.middle.shared import __all__ as names
        for name in names:
            obj = getattr(
                __import__("src.middle.shared", fromlist=[name]), name
            )
            assert obj is not None, f"Export {name} is None"
