"""Phase 25: 教学自评 + 策略切换验证。"""
from src.coach.composer import PolicyComposer


class TestStrategySwitch:
    def setup_method(self):
        self.c = PolicyComposer()

    def test_no_self_eval_behavior_unchanged(self):
        r = self.c.compose(intent="teach python")
        assert r["action_type"] in ("scaffold", "suggest", "probe", "challenge")

    def test_self_eval_none_unchanged(self):
        r = self.c.compose(intent="teach python", self_eval=None)
        assert r["action_type"] in ("scaffold", "suggest", "probe", "challenge")

    def test_scaffold_switches_to_probe(self):
        r = self.c.compose(
            intent="teach python",
            ttm_strategy={"recommended_action_types": ["scaffold"]},
            self_eval={"strategy_ineffective": True, "reason": "mastery_not_improving"},
        )
        assert r["action_type"] == "probe", (
            f"scaffold should switch to probe, got {r['action_type']}"
        )

    def test_challenge_switches_to_scaffold(self):
        r = self.c.compose(
            intent="teach python",
            ttm_strategy={"recommended_action_types": ["challenge"]},
            self_eval={"strategy_ineffective": True, "reason": "competence_low"},
        )
        assert r["action_type"] == "scaffold", (
            f"challenge should switch to scaffold, got {r['action_type']}"
        )

    def test_not_in_switch_map_unchanged(self):
        r = self.c.compose(
            intent="teach python",
            ttm_strategy={"recommended_action_types": ["excursion"]},
            self_eval={"strategy_ineffective": True, "reason": "mastery_not_improving"},
        )
        assert r["action_type"] == "excursion", (
            "excursion not in switch map, should stay"
        )
