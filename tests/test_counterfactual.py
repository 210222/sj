"""S5.1 情境反事实仿真测试 — 8 tests。"""

import pytest
from src.coach.counterfactual import CounterfactualSimulator


class TestCounterfactualBasics:
    def test_simulator_initialized(self):
        sim = CounterfactualSimulator()
        assert sim is not None

    def test_simulate_returns_required_keys(self):
        sim = CounterfactualSimulator()
        result = sim.simulate({"action_type": "suggest", "payload": {}})
        for key in ("risk_flagged", "risk_score", "hypotheses",
                     "baseline_score", "recommendation"):
            assert key in result, f"Missing key: {key}"

    def test_default_returns_proceed(self):
        sim = CounterfactualSimulator()
        result = sim.simulate({"action_type": "suggest", "payload": {}})
        assert result["recommendation"] == "proceed"


class TestHypotheses:
    def test_three_hypotheses_generated(self):
        sim = CounterfactualSimulator()
        result = sim.simulate({"action_type": "challenge", "payload": {}})
        assert len(result["hypotheses"]) == 3

    def test_hypotheses_have_required_fields(self):
        sim = CounterfactualSimulator()
        result = sim.simulate({"action_type": "probe", "payload": {}})
        for h in result["hypotheses"]:
            assert "name" in h
            assert "delta_score" in h
            assert "risk_flagged" in h

    def test_worst_case_lowest_delta(self):
        sim = CounterfactualSimulator()
        result = sim.simulate({"action_type": "challenge", "payload": {}})
        hyps = {h["name"]: h for h in result["hypotheses"]}
        assert hyps["worst_case"]["delta_score"] < hyps["best_case"]["delta_score"]


class TestRiskScoring:
    def test_high_risk_action_flagged(self):
        sim = CounterfactualSimulator(
            {"simulation": {"deterioration_threshold": 0.1}}
        )
        action = {"action_type": "challenge", "payload": {"intensity": "high"}}
        result = sim.simulate(action)
        # worst_case: baseline=0.5, adj=-0.3 → 0.2, delta=-0.3, threshold=0.1
        assert result["hypotheses"][1]["name"] == "worst_case"
        assert result["hypotheses"][1]["risk_flagged"]

    def test_risk_score_in_range(self):
        sim = CounterfactualSimulator()
        result = sim.simulate({"action_type": "suggest", "payload": {}})
        assert 0.0 <= result["risk_score"] <= 1.0
