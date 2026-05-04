"""S3.4 V18.8 关系安全层测试。"""

import copy
import pytest
from src.coach import CoachAgent
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


class TestForbiddenPhrases:
    def test_filter_removes_forbidden_phrase_from_intent(self):
        agent_mod._coach_cfg["relational_safety"] = {
            "enabled": False,
            "forbidden_phrases": ["我比你更了解你"],
        }
        agent = CoachAgent(session_id="test_filt")
        result = {
            "action_type": "suggest",
            "payload": {"option": "test", "alternatives": [], "evidence_id": None, "source_tag": "rule"},
            "trace_id": "t1",
            "intent": "我比你更了解你需要什么",
            "domain_passport": {"evidence_level": "medium"},
        }
        filtered = agent._filter_forbidden(result)
        assert "[已过滤]" in filtered["intent"]
        assert "我比你更了解你" not in filtered["intent"]

    def test_filter_ignores_clean_text(self):
        agent_mod._coach_cfg["relational_safety"] = {
            "enabled": False,
            "forbidden_phrases": ["我比你更了解你"],
        }
        result = {
            "action_type": "suggest",
            "payload": {"option": "test", "alternatives": [], "evidence_id": None, "source_tag": "rule"},
            "trace_id": "t1",
            "intent": "给个学习建议",
            "domain_passport": {"evidence_level": "medium"},
        }
        filtered = CoachAgent._filter_forbidden(result)
        assert filtered["intent"] == "给个学习建议"


class TestSovereigntyReminder:
    def test_no_reminder_when_disabled(self):
        agent_mod._coach_cfg["relational_safety"] = {
            "enabled": False,
            "sovereignty_interval_turns": 3,
            "sovereignty_statement": "主权声明",
        }
        agent = CoachAgent(session_id="test_sov_disable")
        agent._turn_count = 3
        result = {"action_type": "suggest", "payload": {}, "trace_id": "t", "intent": "x"}
        result = agent._attach_sovereignty_statement(result)
        assert "sovereignty_reminder" not in result

    def test_reminder_fires_at_interval(self):
        agent_mod._coach_cfg["relational_safety"] = {
            "enabled": True,
            "sovereignty_interval_turns": 2,
            "sovereignty_statement": "你的认知主权",
        }
        agent = CoachAgent(session_id="test_sov_on")
        agent._turn_count = 2
        result = {"action_type": "suggest", "payload": {}, "trace_id": "t", "intent": "x"}
        result = agent._attach_sovereignty_statement(result)
        assert "sovereignty_reminder" in result
        assert result["sovereignty_reminder"] == "你的认知主权"

    def test_reminder_not_at_off_interval(self):
        agent_mod._coach_cfg["relational_safety"] = {
            "enabled": True,
            "sovereignty_interval_turns": 5,
        }
        agent = CoachAgent(session_id="test_sov_off")
        agent._turn_count = 3
        result = {"action_type": "suggest", "payload": {}, "trace_id": "t", "intent": "x"}
        result = agent._attach_sovereignty_statement(result)
        assert "sovereignty_reminder" not in result
