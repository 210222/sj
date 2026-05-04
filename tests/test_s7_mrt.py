"""S7.1 MRT 微随机实验框架测试。"""

import pytest
from src.coach.mrt import MRTConfig, MRTExperiment, BayesianEstimator


class TestMRTConfig:
    def test_default_config(self):
        cfg = MRTConfig()
        assert cfg.randomization_rate == 0.2
        assert cfg.window_hours == 24
        assert "challenge" in cfg.eligible_action_types

    def test_from_dict(self):
        cfg = MRTConfig.from_dict({"randomization_rate": 0.5})
        assert cfg.randomization_rate == 0.5


class TestMRTExperiment:
    def test_eligible_action_types(self):
        exp = MRTExperiment()
        assert exp.eligible("challenge") is True
        assert exp.eligible("suggest") is False

    def test_assign_returns_control_for_ineligible(self):
        exp = MRTExperiment()
        result = exp.assign("suggest", trace_id="t1")
        assert result.is_variant is False
        assert result.variant_id is None

    def test_assign_returns_assignment(self):
        exp = MRTExperiment()
        result = exp.assign("challenge", trace_id="t2")
        assert result.trace_id == "t2"
        assert result.window_id == exp.current_window_id()
        assert result.is_variant in (True, False)

    def test_window_stats(self):
        exp = MRTExperiment()
        for i in range(10):
            exp.assign("challenge", trace_id=f"t{i}")
        stats = exp.window_stats()
        assert stats["total_assignments"] == 10
        assert stats["variant_count"] + stats["control_count"] == 10

    def test_window_rate_bound(self):
        exp = MRTExperiment(
            MRTConfig.from_dict({"randomization_rate": 0.5}))
        for i in range(100):
            exp.assign("challenge", trace_id=f"t{i}")
        stats = exp.window_stats()
        assert stats["variant_rate"] <= 0.5 + 0.05


class TestBayesianEstimator:
    def test_estimate_binary_positive_effect(self):
        est = BayesianEstimator()
        result = est.estimate_binary(
            variant_successes=8, variant_total=10,
            control_successes=4, control_total=10,
        )
        assert result["effect_size"] > 0
        assert "ci_95" in result
        assert "posterior_overlap" in result
        assert result["variant_n"] == 10

    def test_estimate_binary_no_effect(self):
        est = BayesianEstimator()
        result = est.estimate_binary(
            variant_successes=5, variant_total=10,
            control_successes=5, control_total=10,
        )
        assert abs(result["effect_size"]) < 0.15

    def test_posterior_overlap_range(self):
        est = BayesianEstimator()
        result = est.estimate_binary(2, 10, 2, 10)
        assert 0 <= result["posterior_overlap"] <= 1.0
