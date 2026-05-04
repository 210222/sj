"""S3.1 V18.8 主权确认脉冲测试。"""

import pytest
from src.coach import CoachAgent
from src.coach.agent import _INTENSITY_MAP


class TestPulseDisabledByDefault:
    def test_pulse_disabled_high_action_not_intercepted(self):
        agent = CoachAgent(session_id="test_s3_1_disabled")
        result = agent.act("给我一个挑战")
        assert result["action_type"] == "challenge"

    def test_pulse_disabled_low_action(self):
        agent = CoachAgent(session_id="test_s3_1_disabled_low")
        result = agent.act("给个建议")
        assert result["action_type"] in ("suggest", "challenge", "probe",
                                          "reflect", "scaffold")


class TestPremiseRewriteRate:
    def test_rate_zero_initially(self):
        agent = CoachAgent(session_id="test_rate_zero")
        assert agent._get_premise_rewrite_rate() == 0.0

    def test_rate_with_only_accepts(self):
        agent = CoachAgent(session_id="test_rate_accept")
        agent._pulse_history = [
            {"outcome": "accept", "trace_id": "t1", "ts": 1},
            {"outcome": "accept", "trace_id": "t2", "ts": 2},
        ]
        assert agent._get_premise_rewrite_rate() == 0.0

    def test_rate_computed_correctly(self):
        agent = CoachAgent(session_id="test_rate_mixed")
        agent._pulse_history = [
            {"outcome": "accept", "trace_id": "t1", "ts": 1},
            {"outcome": "rewrite", "trace_id": "t2", "ts": 2},
            {"outcome": "accept", "trace_id": "t3", "ts": 3},
        ]
        assert agent._get_premise_rewrite_rate() == pytest.approx(0.3333, abs=0.001)

    def test_pending_not_counted(self):
        agent = CoachAgent(session_id="test_rate_pending")
        agent._pulse_history = [
            {"outcome": "accept", "trace_id": "t1", "ts": 1},
            {"outcome": "pending", "trace_id": "t2", "ts": 2},
        ]
        assert agent._get_premise_rewrite_rate() == 0.0


class TestPulseInjection:
    def test_should_insert_pulse_disabled(self):
        agent = CoachAgent(session_id="test_inject_disabled")
        # 默认 enabled=false
        assert not agent._should_insert_pulse({"action_type": "challenge"})

    def test_should_insert_pulse_enabled_high_intensity(self, monkeypatch):
        agent = CoachAgent(session_id="test_inject_enabled")
        monkeypatch.setitem(agent._cfg(), "sovereignty_pulse",
                            {"enabled": True, "high_intensity_threshold": 0.7,
                             "max_pulse_rounds": 3, "pulse_cooldown_turns": 5})
        assert agent._should_insert_pulse({"action_type": "challenge"})

    def test_low_intensity_no_pulse(self, monkeypatch):
        agent = CoachAgent(session_id="test_inject_low")
        monkeypatch.setitem(agent._cfg(), "sovereignty_pulse",
                            {"enabled": True, "high_intensity_threshold": 0.7,
                             "max_pulse_rounds": 3, "pulse_cooldown_turns": 5})
        assert not agent._should_insert_pulse({"action_type": "suggest"})
        assert not agent._should_insert_pulse({"action_type": "defer"})

    def test_pulse_itself_not_trigger_pulse(self):
        assert _INTENSITY_MAP["pulse"] == 0.0
        assert _INTENSITY_MAP["excursion"] == 0.0


class TestPulseCooldown:
    def test_within_cooldown_blocked(self, monkeypatch):
        agent = CoachAgent(session_id="test_cooldown")
        monkeypatch.setitem(agent._cfg(), "sovereignty_pulse",
                            {"enabled": True, "high_intensity_threshold": 0.7,
                             "max_pulse_rounds": 3, "pulse_cooldown_turns": 5})
        agent._pulse_round_count = 1  # simulate a prior pulse
        agent._turns_since_last_pulse = 2
        assert not agent._should_insert_pulse({"action_type": "challenge"})


class TestMaxPulseRounds:
    def test_reaches_limit_blocked(self, monkeypatch):
        agent = CoachAgent(session_id="test_max")
        monkeypatch.setitem(agent._cfg(), "sovereignty_pulse",
                            {"enabled": True, "high_intensity_threshold": 0.7,
                             "max_pulse_rounds": 3, "pulse_cooldown_turns": 5})
        agent._pulse_round_count = 3
        assert not agent._should_insert_pulse({"action_type": "challenge"})
