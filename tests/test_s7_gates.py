"""S7.3 V18.7 四门禁测试。"""

import pytest
from src.coach.gates_v18_7 import (
    VerificationLoadGate, SerendipityGate, TrespassingGate,
    ManipulationGate, V18GatesAuditor, GatesReport,
)


class TestVerificationLoadGate:
    def test_low_load_passes(self):
        gate = VerificationLoadGate(ratio_threshold=0.5)
        result = gate.evaluate(verification_seconds=30, autonomous_seconds=120)
        assert result.passed is True
        assert result.metric_value == 0.25

    def test_high_load_fails(self):
        gate = VerificationLoadGate(ratio_threshold=0.5)
        result = gate.evaluate(verification_seconds=100, autonomous_seconds=60)
        assert result.passed is False

    def test_no_autonomous_data_passes(self):
        gate = VerificationLoadGate()
        result = gate.evaluate(verification_seconds=10, autonomous_seconds=0)
        assert result.passed is True

    def test_exact_threshold(self):
        gate = VerificationLoadGate(ratio_threshold=1.0)
        result = gate.evaluate(verification_seconds=50, autonomous_seconds=50)
        assert result.passed is True


class TestSerendipityGate:
    def test_sufficient_exploration_passes(self):
        gate = SerendipityGate(min_exploration_ratio=0.3)
        result = gate.evaluate(exploratory_actions=5, total_excursions=10)
        assert result.passed is True

    def test_insufficient_exploration_fails(self):
        gate = SerendipityGate(min_exploration_ratio=0.5)
        result = gate.evaluate(exploratory_actions=2, total_excursions=10)
        assert result.passed is False

    def test_no_excursion_data_passes(self):
        gate = SerendipityGate()
        result = gate.evaluate(exploratory_actions=0, total_excursions=0)
        assert result.passed is True

    def test_exact_threshold(self):
        gate = SerendipityGate(min_exploration_ratio=0.3)
        result = gate.evaluate(exploratory_actions=3, total_excursions=10)
        assert result.passed is True


class TestTrespassingGate:
    def test_no_leakage_passes(self):
        gate = TrespassingGate(max_leakage=0)
        result = gate.evaluate(circuit_breaker_triggered=5, leakage_after_trigger=0)
        assert result.passed is True

    def test_any_leakage_fails(self):
        gate = TrespassingGate(max_leakage=0)
        result = gate.evaluate(circuit_breaker_triggered=3, leakage_after_trigger=1)
        assert result.passed is False

    def test_no_trigger_passes(self):
        gate = TrespassingGate()
        result = gate.evaluate(circuit_breaker_triggered=0, leakage_after_trigger=0)
        assert result.passed is True

    def test_zero_leakage_after_many_triggers(self):
        gate = TrespassingGate()
        result = gate.evaluate(circuit_breaker_triggered=100, leakage_after_trigger=0)
        assert result.passed is True


class TestManipulationGate:
    def test_consistent_distributions_passes(self):
        gate = ManipulationGate(p_value_threshold=0.05)
        distributions = [
            {"frame": "A", "choices": {"opt1": 20, "opt2": 18, "opt3": 22}},
            {"frame": "B", "choices": {"opt1": 22, "opt2": 17, "opt3": 21}},
        ]
        result = gate.evaluate(distributions)
        assert result.passed is True

    def test_divergent_distributions_may_fail(self):
        gate = ManipulationGate(p_value_threshold=0.05)
        distributions = [
            {"frame": "A", "choices": {"opt1": 40, "opt2": 5, "opt3": 5}},
            {"frame": "B", "choices": {"opt1": 5, "opt2": 40, "opt3": 5}},
        ]
        result = gate.evaluate(distributions)
        assert result.passed is False

    def test_single_frame_passes(self):
        gate = ManipulationGate()
        distributions = [{"frame": "A", "choices": {"opt1": 10, "opt2": 10}}]
        result = gate.evaluate(distributions)
        assert result.passed is True


class TestV18GatesAuditor:
    def test_all_gates_pass(self):
        auditor = V18GatesAuditor()
        report = auditor.audit(
            verification_seconds=30, autonomous_seconds=120,
            exploratory_actions=5, total_excursions=10,
            circuit_breaker_triggered=5, leakage_after_trigger=0,
            choice_distributions=[
                {"frame": "A", "choices": {"opt1": 20, "opt2": 18}},
                {"frame": "B", "choices": {"opt1": 22, "opt2": 17}},
            ],
        )
        assert isinstance(report, GatesReport)
        assert report.all_passed is True

    def test_verification_fails_blocks(self):
        auditor = V18GatesAuditor()
        report = auditor.audit(
            verification_seconds=100, autonomous_seconds=50,
            exploratory_actions=5, total_excursions=10,
            circuit_breaker_triggered=5, leakage_after_trigger=0,
        )
        assert report.all_passed is False
        assert report.verification_load.passed is False

    def test_trespassing_fails_blocks(self):
        auditor = V18GatesAuditor()
        report = auditor.audit(
            verification_seconds=30, autonomous_seconds=120,
            exploratory_actions=5, total_excursions=10,
            circuit_breaker_triggered=3, leakage_after_trigger=1,
        )
        assert report.all_passed is False
        assert report.trespassing.passed is False

    def test_to_dict_serializable(self):
        auditor = V18GatesAuditor()
        report = auditor.audit(
            verification_seconds=30, autonomous_seconds=120,
            exploratory_actions=5, total_excursions=10,
            circuit_breaker_triggered=0, leakage_after_trigger=0,
        )
        d = report.to_dict()
        assert d["all_passed"] is True
        assert "evaluated_at_utc" in d

    def test_gate_results_by_id(self):
        auditor = V18GatesAuditor()
        report = auditor.audit(
            verification_seconds=30, autonomous_seconds=120,
            exploratory_actions=5, total_excursions=10,
            circuit_breaker_triggered=0, leakage_after_trigger=0,
        )
        by_id = report.gate_results_by_id()
        for gid in ("v_load", "serendipity", "trespass", "manip"):
            assert gid in by_id
