"""S3.2 V18.8 模型外远足权测试。"""

import copy
import pytest
from src.coach import CoachAgent
from src.coach.composer import PolicyComposer
import src.coach.agent as agent_mod

_ORIG_CFG = None


@pytest.fixture(autouse=True)
def _save_restore_cfg():
    global _ORIG_CFG
    if _ORIG_CFG is None:
        _ORIG_CFG = copy.deepcopy(agent_mod._coach_cfg)
    yield
    agent_mod._coach_cfg.clear()
    agent_mod._coach_cfg.update(copy.deepcopy(_ORIG_CFG))


class TestExcursionDisabledByDefault:
    def test_no_excursion_without_enable(self):
        agent = CoachAgent(session_id="test_ex_disabled")
        result = agent.act("给个建议")
        assert not agent._excursion_active

    def test_excursion_command_ignored_when_disabled(self):
        agent = CoachAgent(session_id="test_ex_ignored")
        agent.act("/excursion")
        assert not agent._excursion_active


class TestExcursionCommand:
    def test_excursion_command_detected_when_enabled(self):
        agent = CoachAgent(session_id="test_ex_cmd")
        agent_mod._coach_cfg["excursion"] = {
            "enabled": True, "command_prefix": "/excursion", "duration_turns": 3
        }
        agent._detect_excursion_command("/excursion")
        assert agent._excursion_active
        assert agent._excursion_remaining == 3

    def test_excursion_with_arguments(self):
        agent = CoachAgent(session_id="test_ex_args")
        agent_mod._coach_cfg["excursion"] = {
            "enabled": True, "command_prefix": "/excursion", "duration_turns": 3
        }
        agent._detect_excursion_command("/excursion 探索数学领域")
        assert agent._excursion_active

    def test_excursion_duration_decrements(self):
        agent = CoachAgent(session_id="test_ex_dur")
        agent_mod._coach_cfg["excursion"] = {
            "enabled": True, "command_prefix": "/excursion", "duration_turns": 2
        }
        agent._detect_excursion_command("/excursion")
        assert agent._excursion_active
        assert agent._excursion_remaining == 2
        agent._detect_excursion_command("随便说点什么")  # turn 2
        assert agent._excursion_active
        assert agent._excursion_remaining == 1
        agent._detect_excursion_command("再随便说说")    # turn 3
        assert not agent._excursion_active  # expired


class TestExcursionComposer:
    def test_excursion_mode_forces_action_type(self):
        c = PolicyComposer()
        action = c.compose(intent="给我一个挑战", excursion_mode=True)
        assert action["action_type"] == "excursion"
        assert action["domain_passport"]["evidence_level"] == "low"
        assert action["domain_passport"]["source_tag"] == "hypothesis"

    def test_normal_mode_unchanged(self):
        c = PolicyComposer()
        action = c.compose(intent="测测你的水平")
        assert action["action_type"] == "probe"
        assert action["domain_passport"]["evidence_level"] == "medium"
