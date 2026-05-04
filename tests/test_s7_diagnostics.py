"""S7.2 三诊断引擎测试。"""

import pytest
from src.coach.diagnostics import (
    BalanceCheck, NegativeControlCheck, PlaceboWindowCheck,
    DiagnosticEngine, DiagnosticsReport,
)


class TestBalanceCheck:
    def test_balanced_groups_pass(self):
        check = BalanceCheck(smd_threshold=0.25)
        treatment = [{"skill": 0.3 + i * 0.08, "engagement": 0.3 + i * 0.05}
                     for i in range(10)]
        control = [{"skill": 0.32 + i * 0.08, "engagement": 0.28 + i * 0.05}
                   for i in range(10)]
        result = check.evaluate(treatment, control)
        assert result.passed is True
        assert result.metric_value < 0.25

    def test_imbalanced_groups_fail(self):
        check = BalanceCheck(smd_threshold=0.25)
        treatment = [{"skill": 0.9 - i * 0.01, "engagement": 0.9 + i * 0.005}
                     for i in range(10)]
        control = [{"skill": 0.1 + i * 0.01, "engagement": 0.1 - i * 0.005}
                   for i in range(10)]
        result = check.evaluate(treatment, control)
        assert result.passed is False
        assert result.metric_value >= 0.25

    def test_empty_groups_returns_fail(self):
        check = BalanceCheck()
        result = check.evaluate([], [])
        assert result.passed is False

    def test_single_covariate(self):
        check = BalanceCheck()
        treatment = [{"score": 0.3 + i * 0.1} for i in range(5)]
        control = [{"score": 0.31 + i * 0.1} for i in range(5)]
        result = check.evaluate(treatment, control)
        assert result.passed is True


class TestNegativeControlCheck:
    def test_sham_no_effect_passes(self):
        check = NegativeControlCheck(overlap_threshold=0.8)
        result = check.evaluate(5, 10, 5, 10)
        assert result.passed is True

    def test_sham_large_effect_fails(self):
        check = NegativeControlCheck(overlap_threshold=0.8)
        result = check.evaluate(9, 10, 2, 10)
        assert result.passed is False

    def test_insufficient_data_skips(self):
        check = NegativeControlCheck(min_events=10)
        result = check.evaluate(1, 3, 1, 3)
        assert result.passed is True


class TestPlaceboWindowCheck:
    def test_no_pre_effect_passes(self):
        check = PlaceboWindowCheck()
        result = check.evaluate(5, 10, 5, 10)
        assert result.passed is True

    def test_large_pre_effect_fails(self):
        check = PlaceboWindowCheck()
        result = check.evaluate(9, 10, 2, 10)
        assert result.passed is False

    def test_insufficient_data_skips(self):
        check = PlaceboWindowCheck()
        result = check.evaluate(1, 2, 1, 2)
        assert result.passed is True


class TestDiagnosticEngine:
    def test_all_pass(self):
        engine = DiagnosticEngine()
        report = engine.run(
            treatment_covariates=[{"skill": 0.5 + i * 0.02} for i in range(10)],
            control_covariates=[{"skill": 0.51 + i * 0.02} for i in range(10)],
            sham_successes=5, sham_total=10,
            control_successes=5, control_total=10,
            pre_period_successes=5, pre_period_total=10,
        )
        assert isinstance(report, DiagnosticsReport)
        assert report.all_passed is True

    def test_balance_fails_blocks_all(self):
        engine = DiagnosticEngine()
        report = engine.run(
            treatment_covariates=[{"skill": 0.9 - i * 0.01} for i in range(10)],
            control_covariates=[{"skill": 0.1 + i * 0.01} for i in range(10)],
            sham_successes=5, sham_total=10,
            control_successes=5, control_total=10,
            pre_period_successes=5, pre_period_total=10,
        )
        assert report.all_passed is False

    def test_causal_diagnostics_triple_format(self):
        engine = DiagnosticEngine()
        report = engine.run(
            treatment_covariates=[{"skill": 0.5 + i * 0.02} for i in range(10)],
            control_covariates=[{"skill": 0.51 + i * 0.02} for i in range(10)],
            sham_successes=5, sham_total=10,
            control_successes=5, control_total=10,
            pre_period_successes=5, pre_period_total=10,
        )
        triple = report.causal_diagnostics_triple()
        for key in ("all_passed", "balance_smd", "balance_pass",
                     "negative_control_overlap", "negative_control_pass",
                     "placebo_effect", "placebo_pass"):
            assert key in triple, f"Missing key: {key}"

    def test_to_dict_serializable(self):
        engine = DiagnosticEngine()
        report = engine.run(
            treatment_covariates=[{"skill": 0.5 + i * 0.02} for i in range(10)],
            control_covariates=[{"skill": 0.51 + i * 0.02} for i in range(10)],
            sham_successes=5, sham_total=10,
            control_successes=5, control_total=10,
            pre_period_successes=5, pre_period_total=10,
        )
        d = report.to_dict()
        assert d["all_passed"] is True
        assert "evaluated_at_utc" in d
