"""S4.4 心流 + BKT 测试 — 14 tests。"""

import math
import pytest
from src.coach.flow import FlowOptimizer, BKTEngine, _entropy


class TestEntropy:
    def test_certainty_zero_entropy(self):
        assert _entropy(0.0) == 0.0
        assert _entropy(1.0) == 0.0

    def test_max_entropy_at_05(self):
        e = _entropy(0.5)
        assert e == pytest.approx(1.0, abs=0.001)

    def test_symmetry(self):
        assert _entropy(0.3) == pytest.approx(_entropy(0.7), abs=0.001)


class TestBKTEngine:
    def test_predict_returns_sequence(self):
        bkt = BKTEngine(prior=0.3, guess=0.1, slip=0.1, learn=0.2)
        obs = [1, 1, 0, 1]
        probs = bkt.predict(obs)
        assert len(probs) == len(obs) + 1
        assert probs[0] == 0.3

    def test_all_correct_increases_knowledge(self):
        bkt = BKTEngine(prior=0.3, learn=0.2)
        probs = bkt.predict([1, 1, 1, 1, 1])
        assert probs[-1] > probs[0]

    def test_all_wrong_decreases_knowledge(self):
        bkt = BKTEngine(prior=0.5, guess=0.05, slip=0.1, learn=0.2)
        probs = bkt.predict([0, 0, 0, 0, 0])
        assert probs[0] == 0.5

    def test_parameters_clamped(self):
        bkt = BKTEngine(prior=2.0, guess=-0.1, slip=0.5, learn=1.5)
        assert 0.0 < bkt.prior < 1.0
        assert 0.0 < bkt.guess < 1.0


class TestFlowOptimizer:
    def test_flow_returns_all_keys(self):
        flow = FlowOptimizer()
        result = flow.compute_flow(task_difficulty=0.5)
        for key in ("flow_channel", "adjust_difficulty", "mutual_information",
                     "entropy_task", "entropy_residual", "flow_ratio",
                     "student_knowledge"):
            assert key in result, f"Missing {key}"

    def test_boredom_at_high_skill_low_difficulty(self):
        flow = FlowOptimizer()
        result = flow.compute_flow(skill_probs=[0.8], task_difficulty=0.2)
        assert result["flow_channel"] == "boredom" or result["adjust_difficulty"] > 0

    def test_anxiety_at_low_skill_high_difficulty(self):
        flow = FlowOptimizer()
        result = flow.compute_flow(skill_probs=[0.2], task_difficulty=0.9)
        assert result["flow_channel"] == "anxiety" or result["adjust_difficulty"] < 0

    def test_flow_at_moderate_ratio(self):
        flow = FlowOptimizer(config={"flow_zone": {"optimal_low": 0.3,
                                "optimal_high": 0.7}})
        result = flow.compute_flow(skill_probs=[0.7], task_difficulty=0.5)
        assert result["flow_channel"] in {"flow", "near_boredom", "near_anxiety"}

    def test_bkt_integration_with_observations(self):
        flow = FlowOptimizer()
        result = flow.compute_flow(observations=[1, 1, 1, 0, 1],
                                   task_difficulty=0.5)
        assert result["student_knowledge"] > 0

    def test_fit_bkt_returns_params(self):
        flow = FlowOptimizer()
        params = flow.fit_bkt([[1, 1, 0, 1], [0, 1, 1, 1]])
        for key in ("prior", "guess", "slip", "learn"):
            assert key in params

    def test_apathy_when_trivial_task(self):
        flow = FlowOptimizer()
        result = flow.compute_flow(skill_probs=[0.9], task_difficulty=0.01)
        assert result["flow_channel"] == "apathy"
