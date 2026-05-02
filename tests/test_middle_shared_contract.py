"""M1: 合约一致性测试 — 枚举对齐、类型形状、跨合约比对。"""

import json
import pytest

from src.middle.shared import (
    MIDDLE_SCHEMA_VERSION,
    INTERVENTION_INTENSITIES,
    DOMINANT_LAYERS,
    CONFLICT_LEVELS,
    AUDIT_LEVELS,
    GATE_DECISIONS,
    NO_ASSIST_LEVELS,
    P0_FIELDS,
    P1_FIELDS,
    WINDOW_SCHEMA_VERSION,
    L0StateOutput,
    L1ResidualOutput,
    L2FeasibilityOutput,
    UncertaintyVector,
)
from src.inner.audit import P0_FIELDS as INNER_P0_FIELDS
from src.inner.audit import P1_FIELDS as INNER_P1_FIELDS
from src.inner.clock import WINDOW_SCHEMA_VERSION as INNER_WINDOW_SCHEMA_VERSION


class TestMiddleSharedConstants:
    def test_middle_schema_version(self):
        assert MIDDLE_SCHEMA_VERSION == "middle_v1.0.0"

    def test_intervention_intensities(self):
        assert INTERVENTION_INTENSITIES == (
            "full", "reduced", "minimal", "none"
        )

    def test_dominant_layers(self):
        assert DOMINANT_LAYERS == ("L0", "L1", "L2", "none")

    def test_conflict_levels(self):
        assert CONFLICT_LEVELS == ("low", "mid", "high")

    def test_audit_levels(self):
        assert AUDIT_LEVELS == (
            "pass", "p1_warn", "p1_freeze", "p0_block"
        )

    def test_gate_decisions(self):
        assert GATE_DECISIONS == ("GO", "WARN", "FREEZE")

    def test_no_assist_levels(self):
        assert NO_ASSIST_LEVELS == (
            "independent", "partial", "dependent"
        )

    def test_bridge_p0_fields_from_inner(self):
        assert P0_FIELDS == INNER_P0_FIELDS

    def test_bridge_p1_fields_from_inner(self):
        assert P1_FIELDS == INNER_P1_FIELDS

    def test_bridge_window_schema_version_from_inner(self):
        assert WINDOW_SCHEMA_VERSION == INNER_WINDOW_SCHEMA_VERSION


class TestMiddleSharedTypes:
    def test_l0_state_output_shape(self):
        v: L0StateOutput = {"state": "engaged", "dwell_time": 12.5}
        assert v["state"] == "engaged"
        assert v["dwell_time"] == 12.5

    def test_l1_residual_output_shape(self):
        v: L1ResidualOutput = {"correction": "decrease", "magnitude": 0.4}
        assert v["correction"] == "decrease"
        assert v["magnitude"] == 0.4

    def test_l2_feasibility_output_shape(self):
        v: L2FeasibilityOutput = {"feasible": True, "block_reason": ""}
        assert v["feasible"] is True
        assert v["block_reason"] == ""

    def test_uncertainty_vector_shape(self):
        v: UncertaintyVector = {"l0": 0.1, "l1": 0.2, "l2": 0.3}
        assert 0 <= v["l0"] <= 1
        assert 0 <= v["l1"] <= 1
        assert 0 <= v["l2"] <= 1

    def test_typeddict_key_sets_are_stable(self):
        assert set(L0StateOutput.__annotations__.keys()) == {"state", "dwell_time"}
        assert set(L1ResidualOutput.__annotations__.keys()) == {"correction", "magnitude"}
        assert set(L2FeasibilityOutput.__annotations__.keys()) == {"feasible", "block_reason"}
        assert set(UncertaintyVector.__annotations__.keys()) == {"l0", "l1", "l2"}


class TestEnumUniqueness:
    def test_intervention_intensities_unique(self):
        assert len(set(INTERVENTION_INTENSITIES)) == len(INTERVENTION_INTENSITIES)

    def test_audit_levels_unique(self):
        assert len(set(AUDIT_LEVELS)) == len(AUDIT_LEVELS)

    def test_gate_decisions_unique(self):
        assert len(set(GATE_DECISIONS)) == len(GATE_DECISIONS)

    def test_no_duplicate_enum_values_within_sets(self):
        for s in [
            INTERVENTION_INTENSITIES, DOMINANT_LAYERS, CONFLICT_LEVELS,
            AUDIT_LEVELS, GATE_DECISIONS, NO_ASSIST_LEVELS,
        ]:
            assert len(set(s)) == len(s), f"Duplicates within {s}"


class TestCrossContractAlignment:
    def test_resolver_related_sets(self):
        assert "minimal" in INTERVENTION_INTENSITIES
        assert "none" in DOMINANT_LAYERS
        assert "high" in CONFLICT_LEVELS

    def test_audit_gate_no_assist_sets(self):
        assert "p0_block" in AUDIT_LEVELS
        assert "FREEZE" in GATE_DECISIONS
        assert "dependent" in NO_ASSIST_LEVELS

    def test_enums_against_contracts(self):
        contracts_dir = "D:/Claudedaoy/coherence/contracts"
        with open(f"{contracts_dir}/resolver.json", encoding="utf-8") as f:
            resolver = json.load(f)

        contract_intensities = set(
            resolver["outputs"]["intervention_intensity"]["enum"]
        )
        assert set(INTERVENTION_INTENSITIES) == contract_intensities

        contract_dominant = set(
            resolver["required_fields"]["dominant_layer"]["enum"]
        )
        assert set(DOMINANT_LAYERS) == contract_dominant

        expected_audit = {"pass", "p1_warn", "p1_freeze", "p0_block"}
        assert set(AUDIT_LEVELS) == expected_audit

        expected_gate = {"GO", "WARN", "FREEZE"}
        assert set(GATE_DECISIONS) == expected_gate

    def test_intervention_intensity_downgrade_order(self):
        order = ["full", "reduced", "minimal", "none"]
        assert list(INTERVENTION_INTENSITIES) == order

    def test_known_cross_set_overlap_only_none(self):
        all_values = []
        for s in [
            INTERVENTION_INTENSITIES, DOMINANT_LAYERS, CONFLICT_LEVELS,
            AUDIT_LEVELS, GATE_DECISIONS, NO_ASSIST_LEVELS,
        ]:
            all_values.extend(s)
        dupes = [v for v in set(all_values) if all_values.count(v) > 1]
        assert dupes == ["none"]
