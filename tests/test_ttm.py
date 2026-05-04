"""S4.2 TTM 状态机测试 — 12 tests。"""

import pytest
from src.coach.ttm import TTMStateMachine, STAGES, STAGE_STRATEGY_MAP


class TestTTMBasics:
    def test_stages_loaded_from_contract(self):
        ttm = TTMStateMachine()
        assert ttm.STAGES == ["precontemplation", "contemplation",
                               "preparation", "action", "maintenance"]

    def test_default_stage_precontemplation(self):
        ttm = TTMStateMachine()
        assert ttm._current_stage == "precontemplation"


class TestTTMAssess:
    def test_low_cognitive_scores_precontemplation(self):
        ttm = TTMStateMachine()
        result = ttm.assess({
            "cognitive_indicators": [0.1, 0.2],
            "behavioral_indicators": [0.0],
        })
        assert result["current_stage"] == "precontemplation"

    def test_high_behavioral_scores_action(self):
        ttm = TTMStateMachine()
        result = ttm.assess({
            "cognitive_indicators": [0.7, 0.8],
            "behavioral_indicators": [0.8, 0.9, 0.85, 0.9, 0.95],
        })
        assert result["current_stage"] == "action"

    def test_assess_returns_strategy(self):
        ttm = TTMStateMachine()
        result = ttm.assess({
            "cognitive_indicators": [0.5],
            "behavioral_indicators": [0.1],
        })
        assert "recommended_strategy" in result
        assert "recommended_action_types" in result["recommended_strategy"]

    def test_assess_returns_all_keys(self):
        ttm = TTMStateMachine()
        result = ttm.assess({"cognitive_indicators": [0.5]})
        for key in ("current_stage", "confidence", "valid_transitions",
                     "recommended_strategy", "next_stage_candidates"):
            assert key in result, f"Missing key: {key}"


class TestTTMTransition:
    def test_valid_adjacent_forward(self):
        ttm = TTMStateMachine()
        ttm._current_stage = "contemplation"
        assert ttm.validate_transition("preparation")

    def test_invalid_jump(self):
        ttm = TTMStateMachine()
        ttm._current_stage = "precontemplation"
        assert not ttm.validate_transition("action")

    def test_transition_to_executes(self):
        ttm = TTMStateMachine()
        ttm._current_stage = "contemplation"
        result = ttm.transition_to("preparation")
        assert result["success"]
        assert ttm._current_stage == "preparation"
        assert result["from_stage"] == "contemplation"

    def test_invalid_transition_returns_false(self):
        ttm = TTMStateMachine()
        ttm._current_stage = "precontemplation"
        result = ttm.transition_to("action")
        assert not result["success"]
        assert "Invalid transition" in result["reason"]


class TestTTMStrategy:
    def test_strategy_for_stage(self):
        ttm = TTMStateMachine()
        s = ttm.get_strategy("precontemplation")
        assert "recommended_action_types" in s
        assert "avoid_action_types" in s

    def test_strategy_changes_per_stage(self):
        ttm = TTMStateMachine()
        pc = ttm.get_strategy("precontemplation")
        act = ttm.get_strategy("action")
        assert pc["recommended_action_types"] != act["recommended_action_types"]
