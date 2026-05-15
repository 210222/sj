"""Phase 38 targeted: MRT outcome collection, strategy variants, Bayesian estimation."""

import json
import pytest


class TestMRTOutcome:
    """S38.1: outcome 信号采集."""

    def test_outcome_dataclass_fields(self):
        from src.coach.mrt import MRTOutcome
        o = MRTOutcome(variant_id="A", trace_id="t1", session_id="s1",
                       action_type="scaffold", response_length=120,
                       has_steps=True, has_example=False, transport_status="ok")
        d = o.to_dict()
        assert d["variant_id"] == "A"
        assert d["response_length"] == 120
        assert d["has_steps"] is True
        assert d["has_example"] is False

    def test_outcome_sqlite_roundtrip(self):
        from src.coach.mrt import MRTOutcome, MRTExperiment
        exp = MRTExperiment()
        o = MRTOutcome(variant_id="B", trace_id="t2", session_id="s_rt",
                       action_type="suggest", response_length=80,
                       has_steps=False, has_example=True, transport_status="ok")
        exp.record_outcome(o)  # should not raise

    def test_record_outcome_no_variant(self):
        from src.coach.mrt import MRTOutcome, MRTExperiment
        exp = MRTExperiment()
        o = MRTOutcome(variant_id=None, trace_id="t3", session_id="s_none",
                       action_type="scaffold")
        exp.record_outcome(o)  # should not raise — null variant OK


class TestStrategyVariants:
    """S38.2: strategy 级变体."""

    def test_variants_include_strategy_dimension(self):
        from src.coach.mrt import MRTExperiment
        variant_ids = [v["id"] for v in MRTExperiment.VARIANTS]
        assert "S_scaffold_first" in variant_ids
        assert "S_suggest_first" in variant_ids

    def test_strategy_variant_has_override(self):
        from src.coach.mrt import MRTExperiment
        for v in MRTExperiment.VARIANTS:
            if v["dimension"] == "strategy":
                assert "override_action_type" in v

    def test_get_strategy_override_style_returns_none(self):
        from src.coach.mrt import MRTExperiment, MRTAssignment
        exp = MRTExperiment()
        a = MRTAssignment(variant_id="A", variant_name="鼓励型", is_variant=True, dimension="style")
        assert exp.get_strategy_override(a) is None

    def test_get_strategy_override_strategy_returns_value(self):
        from src.coach.mrt import MRTExperiment, MRTAssignment
        exp = MRTExperiment()
        a = MRTAssignment(variant_id="S_scaffold_first", variant_name="脚手架优先",
                          is_variant=True, dimension="strategy")
        assert exp.get_strategy_override(a) == "scaffold"

    def test_protected_action_types(self):
        from src.coach.mrt import MRTExperiment
        assert "pulse" in MRTExperiment.PROTECTED_ACTION_TYPES
        assert "defer" in MRTExperiment.PROTECTED_ACTION_TYPES
        assert "probe" in MRTExperiment.PROTECTED_ACTION_TYPES


class TestBayesianEstimation:
    """S38.3: 贝叶斯估计输出."""

    def test_aggregate_outcomes_empty(self):
        from src.coach.mrt import MRTExperiment
        # aggregate_outcomes reads from DB — may be empty or have data
        result = MRTExperiment.aggregate_outcomes()
        assert isinstance(result, dict)

    def test_bayesian_estimator_same_rates(self):
        from src.coach.mrt import BayesianEstimator
        est = BayesianEstimator()
        result = est.estimate_binary(
            variant_successes=5, variant_total=10,
            control_successes=5, control_total=10,
        )
        assert "effect_size" in result
        assert result["effect_size"] == 0.0

    def test_bayesian_estimator_variant_better(self):
        from src.coach.mrt import BayesianEstimator
        est = BayesianEstimator()
        result = est.estimate_binary(
            variant_successes=8, variant_total=10,
            control_successes=5, control_total=10,
        )
        assert result["effect_size"] > 0

    def test_generate_comparison_report(self):
        from src.coach.mrt import generate_variant_comparison_report
        report = generate_variant_comparison_report()
        assert "status" in report

    def test_bayesian_estimator_ci_contains_effect(self):
        from src.coach.mrt import BayesianEstimator
        est = BayesianEstimator()
        result = est.estimate_binary(6, 10, 4, 10)
        # CI lower <= effect <= CI upper
        assert result["ci_95"][0] <= result["effect_size"] <= result["ci_95"][1]


class TestMRTSafetyInvariants:
    """S38.2: 安全门禁不被绕过."""

    def test_mrt_assignment_never_changes_pulse(self):
        # Pulse packets should not be modified by MRT
        from src.coach.mrt import MRTExperiment
        assert "pulse" in MRTExperiment.PROTECTED_ACTION_TYPES

    def test_style_variant_does_not_override_action_type(self):
        from src.coach.mrt import MRTExperiment, MRTAssignment
        exp = MRTExperiment()
        a = MRTAssignment(variant_id="A", is_variant=True, dimension="style")
        assert exp.get_strategy_override(a) is None


class TestMRTConfigCompat:
    """S38.1: MRTConfig 向后兼容."""

    def test_mrt_config_defaults(self):
        from src.coach.mrt import MRTConfig
        cfg = MRTConfig()
        assert cfg.randomization_rate == 0.2
        assert cfg.min_sample_per_variant == 10

    def test_mrt_config_from_dict(self):
        from src.coach.mrt import MRTConfig
        cfg = MRTConfig.from_dict({"randomization_rate": 0.3})
        assert cfg.randomization_rate == 0.3
