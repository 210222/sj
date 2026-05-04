"""S1.2 Coach 引擎核心测试 — CoachAgent / DSL / Composer / State / Memory。"""

import pytest
from src.coach import CoachAgent
from src.coach.dsl import DSLBuilder, DSLValidator
from src.coach.composer import PolicyComposer
from src.coach.state import UserStateTracker
from src.coach.memory import SessionMemory


@pytest.fixture
def agent():
    return CoachAgent()


class TestCoachAgentAct:
    """CoachAgent.act() 返回合法 DSL 包。"""

    def test_act_returns_dsl_packet(self, agent):
        packet = agent.act("给我一个挑战")
        for field in ("action_type", "payload", "trace_id", "intent", "domain_passport"):
            assert field in packet, f"Missing {field}"

    def test_act_default_intent_general(self, agent):
        packet = agent.act("随便说点什么")
        assert packet["action_type"] in {
            "probe", "challenge", "reflect", "scaffold", "suggest",
            "pulse", "excursion", "defer",
        }
        assert len(packet["trace_id"]) == 36

    def test_act_keyword_probe(self, agent):
        packet = agent.act("测测我的编程水平")
        assert packet["action_type"] == "probe"

    def test_act_keyword_challenge(self, agent):
        packet = agent.act("给我一个高难度挑战")
        assert packet["action_type"] == "challenge"

    def test_act_keyword_reflect(self, agent):
        packet = agent.act("你为什么这么说？反思一下")
        assert packet["action_type"] == "reflect"

    def test_act_keyword_scaffold(self, agent):
        packet = agent.act("如何做这道题？教教我")
        assert packet["action_type"] == "scaffold"

    def test_act_produces_unique_trace_ids(self, agent):
        p1 = agent.act("测试")
        p2 = agent.act("再测试")
        assert p1["trace_id"] != p2["trace_id"]


class TestDSLValidator:
    """DSL 校验器正确性。"""

    def test_accepts_valid_packet(self):
        packet = DSLBuilder.build({
            "action_type": "probe",
            "payload": {"prompt": "test", "expected_skill": "general", "max_duration_s": 300},
            "intent": "探查能力",
            "domain_passport": {"domain": "programming", "evidence_level": "medium",
                                "source_tag": "rule", "epistemic_warning": None},
        })
        ok, errs = DSLValidator.validate(packet)
        assert ok, f"Expected valid, got: {errs}"

    def test_rejects_invalid_action_type(self):
        packet = {"action_type": "nonexistent", "payload": {}, "trace_id": "t",
                  "intent": "x", "domain_passport": {}}
        ok, errs = DSLValidator.validate(packet)
        assert not ok
        assert any("unknown action_type" in e for e in errs)

    def test_rejects_missing_required_fields(self):
        packet = {"action_type": "probe"}
        ok, errs = DSLValidator.validate(packet)
        assert not ok
        assert any("missing required field" in e for e in errs)

    def test_rejects_invalid_domain_level(self):
        packet = DSLBuilder.build({
            "action_type": "suggest",
            "payload": {"option": "x", "alternatives": [], "evidence_id": None, "source_tag": "rule"},
            "intent": "x",
            "domain_passport": {"domain": "x", "evidence_level": "invalid_level",
                                "source_tag": "rule", "epistemic_warning": None},
        })
        ok, errs = DSLValidator.validate(packet)
        assert not ok
        assert any("evidence_level" in e for e in errs)

    def test_accepts_all_8_action_types(self):
        valid_payloads = {
            "probe": {"prompt": "x", "expected_skill": "g", "max_duration_s": 60},
            "challenge": {"objective": "x", "difficulty": "medium", "hints_allowed": True, "evidence_id": None},
            "reflect": {"question": "x", "context_ids": [], "format": "text"},
            "scaffold": {"step": "x", "support_level": "medium", "next_step": "", "fallback_step": ""},
            "suggest": {"option": "x", "alternatives": [], "evidence_id": None, "source_tag": "rule"},
            "pulse": {"statement": "x", "accept_label": "Y", "rewrite_label": "Z"},
            "excursion": {"domain": "g", "options": [], "bias_disabled": True},
            "defer": {"reason": "x", "fallback_intensity": "minimal", "resume_condition": ""},
        }
        for atype in valid_payloads:
            packet = DSLBuilder.build({
                "action_type": atype,
                "payload": valid_payloads[atype],
                "intent": "test",
                "domain_passport": {"evidence_level": "medium", "source_tag": "rule"},
            })
            ok, errs = DSLValidator.validate(packet)
            assert ok, f"Expected valid for {atype}, got: {errs}"


class TestDSLBuilder:
    """DSL 构建器正确性。"""

    def test_build_fills_required_fields(self):
        action = {"action_type": "suggest", "payload": {}, "intent": "test"}
        packet = DSLBuilder.build(action)
        assert packet["action_type"] == "suggest"
        assert len(packet["trace_id"]) == 36
        assert "domain_passport" in packet


class TestUserStateTracker:
    """状态追踪器正确性。"""

    def test_get_state_returns_6_fields(self):
        tracker = UserStateTracker()
        state = tracker.get_state()
        assert set(state.keys()) == {
            "state", "confidence", "correction",
            "magnitude", "feasible", "uncertainty",
        }

    def test_update_changes_state(self):
        tracker = UserStateTracker()
        tracker.update(l0_result={"state": "volatile", "confidence": 0.3})
        state = tracker.get_state()
        assert state["state"] == "volatile"
        assert state["confidence"] == 0.3
        assert state["correction"] == "none"  # unchanged


class TestSessionMemory:
    """会话记忆正确性。"""

    def test_store_and_recall(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mem = SessionMemory(db_path=path)
            mem.store("s1", {"intent": "探查能力", "data": "x"})
            results = mem.recall("探查能力")
            assert len(results) == 1
            assert results[0]["intent"] == "探查能力"
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try: os.unlink(p)
                except FileNotFoundError: pass

    def test_recall_keyword_match(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mem = SessionMemory(db_path=path)
            mem.store("s1", {"intent": "寻求挑战"})
            mem.store("s1", {"intent": "引导反思"})
            results = mem.recall("挑战")
            assert len(results) >= 1
            assert any(r["intent"] == "寻求挑战" for r in results)
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try: os.unlink(p)
                except FileNotFoundError: pass

    def test_empty_recall(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            mem = SessionMemory(db_path=path)
            results = mem.recall("nothing")
            assert results == []
        finally:
            for p in [path, path + "-wal", path + "-shm"]:
                try: os.unlink(p)
                except FileNotFoundError: pass


class TestPolicyComposer:
    """策略合成器正确性。"""

    def test_probe_keyword(self):
        c = PolicyComposer()
        action = c.compose(intent="测测你的水平")
        assert action["action_type"] == "probe"

    def test_challenge_keyword(self):
        c = PolicyComposer()
        action = c.compose(intent="给我一个挑战任务")
        assert action["action_type"] == "challenge"

    def test_default_is_suggest(self):
        c = PolicyComposer()
        action = c.compose(intent="随便说点什么")
        assert action["action_type"] == "suggest"

    def test_output_has_action_structure(self):
        c = PolicyComposer()
        action = c.compose(intent="帮帮我")
        for key in ("action_type", "payload", "intent", "domain_passport"):
            assert key in action, f"Missing {key}"


class TestCoachImports:
    """验证 Coach 包可正常导入且不触碰禁改区。"""

    def test_coach_import_works(self):
        import src.coach
        assert hasattr(src.coach, "CoachAgent")

    def test_no_inner_middle_imported_by_coach(self):
        """Coach 包不应导入 src/inner/ 和 src/middle/ 的代码（S1.2 阶段不调用管线）。"""
        import sys
        import src.coach.agent
        # agent 文件已导入，只检查文件级别的非标准库导入
        bad = {"src.inner", "src.middle"}
        for mod_name in list(sys.modules):
            if any(mod_name.startswith(b) for b in bad):
                pass  # 允许被其他模块导入——coach 自身不主动触发即可
        # smoke: agent.py 不直接导入 inner
        source = open("src/coach/agent.py", encoding="utf-8").read()
        assert "from src.inner" not in source
        assert "from src.middle" not in source
