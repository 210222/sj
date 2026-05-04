"""S6.3 MAPE-K Plan + Execute 测试 — 13 tests。"""

import pytest
from src.mapek.plan import Plan
from src.mapek.execute import Execute


class TestPlan:
    def test_generate_returns_required_keys(self):
        p = Plan()
        report = {"trends": [], "anomalies": [], "confidence": 0.0}
        result = p.generate(report)
        for key in ("target_action_type", "intensity", "resource_budget",
                     "horizon_steps", "conflicts", "confidence"):
            assert key in result

    def test_many_anomalies_selects_probe(self):
        p = Plan()
        report = {"trends": [], "anomalies": [{"i": 1}, {"i": 2}, {"i": 3}],
                  "confidence": 0.8}
        result = p.generate(report)
        assert result["target_action_type"] == "probe"

    def test_falling_trend_selects_scaffold(self):
        p = Plan()
        report = {"trends": [{"metric": "score", "direction": "falling",
                              "older_avg": 10, "recent_avg": 5}],
                  "anomalies": [], "confidence": 0.6}
        result = p.generate(report)
        assert result["target_action_type"] == "scaffold"

    def test_rising_trend_selects_challenge(self):
        p = Plan()
        report = {"trends": [{"metric": "score", "direction": "rising",
                              "older_avg": 5, "recent_avg": 10}],
                  "anomalies": [], "confidence": 0.6}
        result = p.generate(report)
        assert result["target_action_type"] == "challenge"

    def test_equal_falling_rising_selects_scaffold(self):
        p = Plan()
        report = {"trends": [
            {"metric": "score", "direction": "rising", "older_avg": 5, "recent_avg": 10},
            {"metric": "engagement", "direction": "falling", "older_avg": 10, "recent_avg": 5},
        ], "anomalies": [], "confidence": 0.5}
        result = p.generate(report)
        # falling(1) >= rising(1) → scaffold, not challenge
        assert result["target_action_type"] == "scaffold"

    def test_intensity_scales_with_anomalies(self):
        p = Plan()
        assert p._compute_intensity([], 0.2) == "low"
        assert p._compute_intensity([{"i": 1}], 0.6) == "medium"
        assert p._compute_intensity([{"i": 1}, {"i": 2}, {"i": 3}], 0.8) == "high"

    def test_conflict_detected_on_probe_to_challenge_high(self):
        p = Plan()
        # 注入先前策略: probe at high → 验证切换到 challenge@high 时触发冲突
        p._current_strategy = {"target_action_type": "probe", "intensity": "high"}
        conflicts = p._resolve_conflicts("challenge", "high")
        assert len(conflicts) > 0
        assert conflicts[0]["type"] == "action_type_switch"

    def test_no_conflict_with_same_action_type_direct(self):
        p = Plan()
        p._current_strategy = {"target_action_type": "suggest", "intensity": "high"}
        conflicts = p._resolve_conflicts("suggest", "high")
        assert len(conflicts) == 0

    def test_no_conflict_at_low_intensity(self):
        p = Plan()
        p._current_strategy = {"target_action_type": "probe", "intensity": "low"}
        conflicts = p._resolve_conflicts("challenge", "low")
        assert len(conflicts) == 0

    def test_no_conflict_same_type_across_generate_calls(self):
        p = Plan()
        p.generate({"trends": [], "anomalies": [], "confidence": 0.0})
        result = p.generate({"trends": [], "anomalies": [], "confidence": 0.0})
        assert len(result["conflicts"]) == 0

    def test_empty_report_graceful(self):
        p = Plan()
        result = p.generate({})
        assert result["target_action_type"] in ("suggest", "probe", "challenge", "scaffold")


class TestExecute:
    def test_dispatch_returns_all_targets(self):
        e = Execute()
        result = e.dispatch({"target_action_type": "suggest", "intensity": "low"})
        for tgt in ("CoachAgent", "Ledger", "Audit", "ExternalAPI"):
            assert tgt in result["results"]

    def test_all_success_on_valid_plan(self):
        e = Execute()
        result = e.dispatch({"target_action_type": "suggest", "intensity": "low"})
        assert result["all_success"] is True

    def test_history_tracks_executions(self):
        e = Execute()
        e.dispatch({"target_action_type": "probe", "intensity": "medium"})
        assert len(e.history()) == 1
        e.dispatch({"target_action_type": "challenge", "intensity": "high"})
        assert len(e.history()) == 2

    def test_dispatch_empty_plan_graceful(self):
        e = Execute()
        result = e.dispatch({})
        assert "results" in result
        assert result["all_success"] is True
