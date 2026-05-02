"""M1: 配置与异常测试 — 阈值边界、类型正确性、异常层次、YAML 一致性。"""

import importlib
import pytest

from src.middle.shared import (
    L0_DWELL_MIN_SECONDS,
    L0_SWITCH_PENALTY,
    L0_HYSTERESIS_ENTRY,
    L0_HYSTERESIS_EXIT,
    L0_MIN_SAMPLES,
    L1_SHOCK_THRESHOLD,
    L1_MEMORY_DECAY_RATE,
    L1_TREND_MIN_WINDOWS,
    L2_CAPABILITY_MIN,
    L2_OPPORTUNITY_MIN,
    L2_MOTIVATION_MIN,
    DECISION_WEIGHT_TRANSFER,
    DECISION_WEIGHT_CREATIVITY,
    DECISION_WEIGHT_INDEPENDENCE,
    DECISION_MAX_DELTA_PER_UPDATE,
    DECISION_MIN_WEIGHT,
    DECISION_UPDATE_WINDOW_DAYS,
    DECISION_LRM_WEIGHT,
    DECISION_ROBUST_WEIGHT,
    DECISION_CONFLICT_ESCALATE,
    SEMANTIC_SAFETY_MIN_SCORE,
    SEMANTIC_SAFETY_BLOCK_THRESHOLD,
    MIDDLE_CONFIG_VERSION,
    MiddlewareError,
    ContractViolationError,
    StateEstimationError,
    SemanticSafetyError,
    DecisionRejectedError,
)


class TestBoundaryPerturbation:
    def test_config_values_not_negative(self):
        all_config = [
            L0_DWELL_MIN_SECONDS, L0_SWITCH_PENALTY,
            L0_HYSTERESIS_ENTRY, L0_HYSTERESIS_EXIT,
            L1_SHOCK_THRESHOLD, L1_MEMORY_DECAY_RATE,
            L2_CAPABILITY_MIN, L2_OPPORTUNITY_MIN, L2_MOTIVATION_MIN,
            DECISION_WEIGHT_TRANSFER, DECISION_WEIGHT_CREATIVITY,
            DECISION_WEIGHT_INDEPENDENCE, DECISION_MAX_DELTA_PER_UPDATE,
            DECISION_MIN_WEIGHT, DECISION_LRM_WEIGHT, DECISION_ROBUST_WEIGHT,
            DECISION_CONFLICT_ESCALATE, SEMANTIC_SAFETY_MIN_SCORE,
            SEMANTIC_SAFETY_BLOCK_THRESHOLD,
        ]
        for val in all_config:
            assert val >= 0.0, f"Config value {val} should be >= 0"

    def test_probability_values_in_range_0_1(self):
        probs = [
            L0_SWITCH_PENALTY, L0_HYSTERESIS_ENTRY, L0_HYSTERESIS_EXIT,
            L1_SHOCK_THRESHOLD, L1_MEMORY_DECAY_RATE,
            L2_CAPABILITY_MIN, L2_OPPORTUNITY_MIN, L2_MOTIVATION_MIN,
            DECISION_LRM_WEIGHT, DECISION_ROBUST_WEIGHT,
            DECISION_CONFLICT_ESCALATE, SEMANTIC_SAFETY_MIN_SCORE,
            SEMANTIC_SAFETY_BLOCK_THRESHOLD,
        ]
        for val in probs:
            assert 0.0 <= val <= 1.0, f"Probability {val} out of [0,1]"

    def test_decision_weights_sum_near_one(self):
        total = (
            DECISION_WEIGHT_TRANSFER
            + DECISION_WEIGHT_CREATIVITY
            + DECISION_WEIGHT_INDEPENDENCE
        )
        assert abs(total - 1.0) < 1e-9

    def test_lrm_robust_weights_sum_near_one(self):
        total = DECISION_LRM_WEIGHT + DECISION_ROBUST_WEIGHT
        assert abs(total - 1.0) < 1e-9

    def test_hysteresis_entry_gt_exit(self):
        assert L0_HYSTERESIS_ENTRY > L0_HYSTERESIS_EXIT

    def test_semantic_safety_block_lt_min(self):
        assert SEMANTIC_SAFETY_BLOCK_THRESHOLD < SEMANTIC_SAFETY_MIN_SCORE

    def test_integer_configs_positive(self):
        assert isinstance(L0_MIN_SAMPLES, int) and L0_MIN_SAMPLES >= 1
        assert isinstance(L1_TREND_MIN_WINDOWS, int) and L1_TREND_MIN_WINDOWS >= 1
        assert isinstance(DECISION_UPDATE_WINDOW_DAYS, int) and DECISION_UPDATE_WINDOW_DAYS >= 1


class TestConfigTypes:
    def test_all_float_configs_are_float(self):
        float_names = [
            "L0_DWELL_MIN_SECONDS", "L0_SWITCH_PENALTY",
            "L0_HYSTERESIS_ENTRY", "L0_HYSTERESIS_EXIT",
            "L1_SHOCK_THRESHOLD", "L1_MEMORY_DECAY_RATE",
            "L2_CAPABILITY_MIN", "L2_OPPORTUNITY_MIN", "L2_MOTIVATION_MIN",
            "DECISION_WEIGHT_TRANSFER", "DECISION_WEIGHT_CREATIVITY",
            "DECISION_WEIGHT_INDEPENDENCE", "DECISION_MAX_DELTA_PER_UPDATE",
            "DECISION_MIN_WEIGHT", "DECISION_LRM_WEIGHT", "DECISION_ROBUST_WEIGHT",
            "DECISION_CONFLICT_ESCALATE", "SEMANTIC_SAFETY_MIN_SCORE",
            "SEMANTIC_SAFETY_BLOCK_THRESHOLD",
        ]
        from src.middle.shared import config
        for name in float_names:
            val = getattr(config, name)
            assert isinstance(val, float), f"{name} is {type(val)}, expected float"

    def test_all_int_configs_are_int(self):
        int_names = [
            "L0_MIN_SAMPLES", "L1_TREND_MIN_WINDOWS",
            "DECISION_UPDATE_WINDOW_DAYS",
        ]
        from src.middle.shared import config
        for name in int_names:
            val = getattr(config, name)
            assert isinstance(val, int), f"{name} is {type(val)}, expected int"

    def test_config_version_is_string(self):
        assert isinstance(MIDDLE_CONFIG_VERSION, str)
        assert len(MIDDLE_CONFIG_VERSION) > 0


class TestYamlConsistency:
    def test_config_consistency_with_yaml(self):
        with open("D:/Claudedaoy/coherence/config/parameters.yaml", encoding="utf-8") as f:
            import yaml
            cfg = yaml.safe_load(f)

        assert L0_DWELL_MIN_SECONDS == cfg["state_estimation"]["dwell_min_seconds"]
        assert L0_SWITCH_PENALTY == cfg["state_estimation"]["switch_penalty"]
        assert DECISION_WEIGHT_TRANSFER == cfg["decision"]["weight_transfer"]
        assert DECISION_WEIGHT_CREATIVITY == cfg["decision"]["weight_creativity"]
        assert DECISION_WEIGHT_INDEPENDENCE == cfg["decision"]["weight_independence"]


class TestExceptionHierarchy:
    def test_middleware_error_is_base(self):
        assert issubclass(ContractViolationError, MiddlewareError)
        assert issubclass(StateEstimationError, MiddlewareError)
        assert issubclass(SemanticSafetyError, MiddlewareError)
        assert issubclass(DecisionRejectedError, MiddlewareError)

    def test_middleware_error_is_exception(self):
        assert issubclass(MiddlewareError, Exception)

    def test_exception_can_be_raised_and_caught(self):
        with pytest.raises(ContractViolationError):
            raise ContractViolationError("enum drift detected")

    def test_exception_caught_as_base(self):
        with pytest.raises(MiddlewareError):
            raise StateEstimationError("not enough samples")

    def test_exception_carries_message(self):
        msg = "test message 测试"
        try:
            raise SemanticSafetyError(msg)
        except SemanticSafetyError as e:
            assert str(e) == msg


class TestImportIdempotency:
    def test_repeated_import_yields_same_config(self):
        cfg1 = importlib.import_module("src.middle.shared.config")
        cfg2 = importlib.import_module("src.middle.shared.config")
        assert cfg1.L0_DWELL_MIN_SECONDS == cfg2.L0_DWELL_MIN_SECONDS

    def test_repeated_import_yields_same_exceptions(self):
        exc1 = importlib.import_module("src.middle.shared.exceptions")
        exc2 = importlib.import_module("src.middle.shared.exceptions")
        assert exc1.MiddlewareError is exc2.MiddlewareError
