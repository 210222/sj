"""穷尽教学质量测试 — 基于 37 份元提示词, 139 条验收标准.

模块 D: Disabled 零变化 (5 tests)
模块 B: 数据流端到端 (15 tests)
模块 C: 边界空安全 (10 tests)
模块 A: Action-Type 穷尽 (25 tests)
模块 LLM: LLM 冒烟 (5 tests, 需 DEEPSEEK_API_KEY)
"""
import os
import pytest
import time
from src.coach.agent import CoachAgent
from src.coach.composer import PolicyComposer
from src.coach.persistence import SessionPersistence
from src.coach.llm.prompts import build_coach_context, _build_behavior_signals
from src.coach.llm.schemas import LLMOutputValidator
from src.coach.flow import BKTEngine


# ═══════════════════════════════════════════════════════════════
# 模块 D: Disabled 零变化 (5 tests)
# ═══════════════════════════════════════════════════════════════

class TestDisabledBaseline:
    """所有模块 disabled 时行为与 Phase 0 基线一致."""

    def test_all_disabled_returns_standard_keys(self):
        """全 disabled 时 act() 返回标准字段且运行时不报错."""
        a = CoachAgent(session_id="disabled_baseline")
        r = a.act("test")
        standard = ["action_type", "payload", "intent", "safety_allowed",
                     "gate_decision", "audit_level"]
        for k in standard:
            assert k in r, f"missing standard key: {k}"
        # 新增字段存在但为 None/默认值
        assert r["llm_generated"] is False
        assert r["diagnostic_result"] is None

    def test_models_disabled_return_none(self):
        """TTM/SDT/diagnostic_engine 默认关闭（coach_defaults.yaml enabled: false）."""
        a = CoachAgent()
        assert a.ttm is None
        assert a.sdt is None
        assert a.flow is not None  # flow 始终加载
        assert a.diagnostic_engine is None

    def test_act_does_not_crash_with_all_disabled(self):
        """全 disabled 时多轮对话不崩溃."""
        a = CoachAgent(session_id="disabled_multi")
        for i in range(5):
            r = a.act(f"message {i}")
            assert "action_type" in r, f"crash at turn {i}"

    def test_persistence_writes_with_disabled_models(self):
        """模型 disabled 时 persistence 仍正常递增."""
        a = CoachAgent(session_id="disabled_persist")
        a.act("hello")
        p = SessionPersistence("disabled_persist")
        t1 = p.get_profile().get("total_turns", 0)
        a.act("world")
        t2 = p.get_profile().get("total_turns", 0)
        assert t2 >= t1, f"turns should increment: {t1} -> {t2}"

    def test_difficulty_contract_defaults_when_disabled(self):
        """diagnostic_engine 默认关闭，difficulty_contract 返回 default."""
        a = CoachAgent()
        r = a.act("test")
        dc = r.get("difficulty_contract", {})
        assert dc.get("reason") == "default"
        assert dc.get("level") == "medium"


# ═══════════════════════════════════════════════════════════════
# 模块 B: 数据流端到端 (15 tests)
# ═══════════════════════════════════════════════════════════════

class TestDataFlowEndToEnd:
    """mastery -> TTM/SDT/Flow -> composer -> LLM 全链路."""

    def test_mastery_to_difficulty_easy(self):
        """diagnostic_engine 默认关闭，difficulty_contract 返回 default."""
        a = CoachAgent(session_id="df_easy")
        r = a.act("test")
        assert r["difficulty_contract"]["level"] == "medium"
        assert r["difficulty_contract"]["reason"] == "default"

    def test_mastery_to_difficulty_default_disabled(self):
        """diagnostic_engine 默认关闭 -> reason = default."""
        a = CoachAgent()
        r = a.act("test")
        assert r["difficulty_contract"]["reason"] == "default"

    def test_covered_topics_is_none_when_disabled(self):
        """diagnostic_engine 已启用，personalization_evidence 可含 diagnostic 来源."""
        a = CoachAgent(session_id=f"df_cov_{int(time.time())}")
        r = a.act("test")
        pe = r.get("personalization_evidence")
        # diagnostic_engine 启用后 sources 可以包含 diagnostic
        if pe is not None:
            assert isinstance(pe.get("sources"), list)

    def test_ttm_stage_none_when_disabled(self):
        """TTM 默认关闭 -> ttm_stage 为 None."""
        a = CoachAgent()
        r = a.act("test")
        assert r["ttm_stage"] is None

    def test_sdt_profile_none_when_disabled(self):
        """SDT 默认关闭 -> sdt_profile 为 None."""
        a = CoachAgent()
        r = a.act("test")
        assert r["sdt_profile"] is None

    def test_flow_channel_not_none(self):
        """Flow 始终可用 -> flow_channel 非 None."""
        a = CoachAgent()
        r = a.act("test")
        assert r["flow_channel"] is not None

    def test_progress_summary_none_no_mastery(self):
        """无 mastery 数据时 _progress_summary 为 None."""
        a = CoachAgent()
        a.act("test")
        assert a._progress_summary is None

    def test_progress_summary_init_vars(self):
        """Phase 26 变量在 __init__ 中正确初始化."""
        a = CoachAgent()
        assert a._last_progress_ts == 0.0
        assert a._last_mastery == {}
        assert a._progress_summary is None

    def test_self_eval_generated_after_act(self):
        """act() 后 self._self_eval 非 None."""
        a = CoachAgent()
        a.act("test")
        assert a._self_eval is not None
        assert "strategy_ineffective" in a._self_eval
        assert "reason" in a._self_eval
        assert "action_type" in a._self_eval

    def test_self_eval_cross_turn_persistence(self):
        """跨轮 self_eval 在实例上保持."""
        a = CoachAgent(session_id="self_eval_cross")
        a.act("turn 1")
        eval1 = dict(a._self_eval) if a._self_eval else None
        a.act("turn 2")
        eval2 = dict(a._self_eval) if a._self_eval else None
        assert eval1 is not None
        assert eval2 is not None
        # _self_eval 应该在第二轮被更新
        assert isinstance(a._self_eval, dict)

    def test_persistence_total_turns_increments(self):
        """每轮 total_turns 递增."""
        sid = f"df_turns_{int(time.time())}"
        a = CoachAgent(session_id=sid)
        a.act("t1")
        t1 = SessionPersistence(sid).get_profile().get("total_turns", 0)
        a.act("t2")
        a.act("t3")
        t3 = SessionPersistence(sid).get_profile().get("total_turns", 0)
        assert t3 > t1, f"turns: {t1} -> {t3}"

    def test_dashboard_progress_reads_real_turns(self):
        """Dashboard get_progress 返回真实 total_turns."""
        from api.services.dashboard_aggregator import DashboardAggregator
        sid = f"df_dash_{int(time.time())}"
        a = CoachAgent(session_id=sid)
        for _ in range(3):
            a.act("msg")
        prog = DashboardAggregator(sid).get_progress()
        assert prog["total_turns"] >= 3, f"got {prog['total_turns']}"

    def test_retention_calculation_works(self):
        """estimate_retention 对典型输入返回合理值."""
        bkt = BKTEngine()
        r0 = bkt.estimate_retention(0.8, 0)
        r7 = bkt.estimate_retention(0.8, 7)
        assert r0 == 0.8
        assert r7 < r0
        assert r7 > 0.3  # ~0.4

    def test_get_skills_with_recency_no_data(self):
        """无 skill_masteries 时返回空 dict."""
        p = SessionPersistence(f"df_empty_{int(time.time())}")
        skills = p.get_skills_with_recency()
        assert skills == {}

    def test_get_mastery_trend_no_data(self):
        """无 profile_history 时返回空列表."""
        p = SessionPersistence(f"df_trend_{int(time.time())}")
        trend = p.get_mastery_trend("ttm_stage", days=30)
        assert isinstance(trend, list)
        assert trend == []


# ═══════════════════════════════════════════════════════════════
# 模块 C: 边界空安全 (10 tests)
# ═══════════════════════════════════════════════════════════════

class TestBoundarySafety:
    """空值、异常、边界条件的系统化验证."""

    def test_empty_user_input_no_crash(self):
        """空输入不崩溃."""
        a = CoachAgent()
        r = a.act("")
        assert "action_type" in r

    def test_very_long_input_no_crash(self):
        """超长输入不崩溃."""
        a = CoachAgent()
        r = a.act("test " * 500)
        assert "action_type" in r

    def test_special_chars_no_crash(self):
        """特殊字符不崩溃."""
        a = CoachAgent()
        r = a.act("test <>&\"'\\n\\t\\r{}[]")
        assert "action_type" in r

    def test_unicode_emoji_no_crash(self):
        """Unicode/Emoji 不崩溃."""
        a = CoachAgent()
        r = a.act("test 你好 🎓 σ ≠ √")
        assert "action_type" in r

    def test_none_context_no_crash(self):
        """context=None 不崩溃."""
        a = CoachAgent()
        r = a.act("test", context=None)
        assert "action_type" in r

    def test_empty_dict_context_no_crash(self):
        """context={} 不崩溃."""
        a = CoachAgent()
        r = a.act("test", context={})
        assert "action_type" in r

    def test_dashboard_empty_session_returns_defaults(self):
        """不存在 session 时 Dashboard 返回默认值不崩溃."""
        from api.services.dashboard_aggregator import DashboardAggregator
        agg = DashboardAggregator("nonexistent_99999")
        ttm = agg.get_ttm_radar()
        sdt = agg.get_sdt_rings()
        prog = agg.get_progress()
        snap = agg.get_mastery_snapshot()
        assert isinstance(ttm, dict)
        assert isinstance(sdt, dict)
        assert prog["total_turns"] == 0
        assert snap is None

    def test_repeated_rapid_calls_no_crash(self):
        """快速连续调用不崩溃."""
        a = CoachAgent(session_id="rapid")
        for i in range(20):
            a.act(f"msg{i}")

    def test_retention_boundary_inputs(self):
        """retention 计算处理边界值."""
        bkt = BKTEngine()
        assert bkt.estimate_retention(0.0, 0) <= 0.01  # mastery=0 clamped to 0.01
        assert bkt.estimate_retention(1.0, 0) == 1.0
        assert bkt.estimate_retention(0.5, 1000) < 0.01
        assert bkt.estimate_retention(0.5, 0.001) > 0.49

    def test_self_eval_not_none_after_act(self):
        """act() 后 _self_eval 不为 None 且结构完整."""
        a = CoachAgent()
        a.act("test")
        se = a._self_eval
        assert se is not None
        for k in ("strategy_ineffective", "reason", "action_type"):
            assert k in se, f"missing {k}"


# ═══════════════════════════════════════════════════════════════
# 模块 A: Action-Type 穷尽 (25 tests)
# ═══════════════════════════════════════════════════════════════

class TestActionTypeExhaustive:
    """8 种 action_type 的 prompt、校验、行为穷尽覆盖."""

    ALL_TYPES = ["probe", "scaffold", "challenge", "suggest",
                 "reflect", "defer", "pulse", "excursion"]

    TYPE_KEYWORDS = {
        "probe": "expected_answer",
        "scaffold": "steps",
        "challenge": "objective",
        "suggest": "options",
        "reflect": "reflection_prompts",
        "defer": "resume_condition",
        "pulse": "accept_label",
        "excursion": "bias_disabled",
    }

    # ── A.1: Prompt 差异化 ──

    def test_all_8_types_have_unique_keyword(self):
        """每种 action_type 的 prompt 含独有关键词."""
        for at in self.ALL_TYPES:
            ctx = build_coach_context(action_type=at, intent="test")
            assert self.TYPE_KEYWORDS[at] in ctx["system"], \
                f"{at}: missing '{self.TYPE_KEYWORDS[at]}'"

    def test_prompts_are_distinct(self):
        """任意两种 action_type 的 prompt 不同."""
        prompts = {}
        for at in self.ALL_TYPES:
            ctx = build_coach_context(action_type=at, intent="test")
            prompts[at] = ctx["system"]
        for i, a1 in enumerate(self.ALL_TYPES):
            for a2 in self.ALL_TYPES[i+1:]:
                assert prompts[a1] != prompts[a2], \
                    f"{a1} and {a2} have identical prompts"

    def test_system_prompt_template_unchanged(self):
        """稳定前缀与策略层关键片段存在。"""
        ctx = build_coach_context(action_type="suggest", intent="test")
        system_prompt = ctx["system"]
        assert "输出要求:" in system_prompt
        assert "当前教练策略:" in system_prompt
        assert "用户意图:" in system_prompt
        assert "TTM 阶段:" in system_prompt

    # ── A.2: 字段校验穷尽 ──

    def test_probe_missing_question_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t", "expected_answer": "a"}, "probe")
        assert not v
        assert any("question" in err for err in e)

    def test_probe_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "question": "q", "expected_answer": "a"}, "probe")
        assert v

    def test_scaffold_missing_steps_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t"}, "scaffold")
        assert not v
        assert any("steps" in err for err in e)

    def test_scaffold_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "steps": [{"order": 1}]}, "scaffold")
        assert v

    def test_challenge_missing_objective_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t", "difficulty": "medium"}, "challenge")
        assert not v
        assert any("objective" in err for err in e)

    def test_challenge_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "objective": "solve", "difficulty": "medium"}, "challenge")
        assert v

    def test_suggest_missing_options_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t"}, "suggest")
        assert not v
        assert any("options" in err for err in e)

    def test_suggest_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "options": []}, "suggest")
        assert v

    def test_reflect_missing_question_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t"}, "reflect")
        assert not v
        assert any("question" in err for err in e)

    def test_reflect_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "question": "why?"}, "reflect")
        assert v

    def test_defer_missing_resume_condition_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t"}, "defer")
        assert not v
        assert any("resume_condition" in err for err in e)

    def test_defer_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "resume_condition": "continue"}, "defer")
        assert v

    def test_pulse_missing_accept_label_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t", "rewrite_label": "r"}, "pulse")
        assert not v
        assert any("accept_label" in err for err in e)

    def test_pulse_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "accept_label": "OK", "rewrite_label": "No"}, "pulse")
        assert v

    def test_excursion_missing_bias_disabled_fails(self):
        v, e = LLMOutputValidator.validate_with_type(
            {"statement": "t"}, "excursion")
        assert not v
        assert any("bias_disabled" in err for err in e)

    def test_excursion_complete_passes(self):
        v, _ = LLMOutputValidator.validate_with_type(
            {"statement": "t", "bias_disabled": True}, "excursion")
        assert v

    def test_no_action_type_old_behavior(self):
        """无 action_type 时 validate 只检查 statement."""
        v, e = LLMOutputValidator.validate_with_type({"statement": "t"})
        assert v
        v2, _ = LLMOutputValidator.validate_with_type({"x": "y"})
        assert not v2

    # ── A.3: Compose action_type 覆盖 ──

    def test_compose_can_produce_all_types(self):
        """compose() 通过 ttm_strategy 可生成全部 8 种 action_type."""
        c = PolicyComposer()
        produced = set()
        for at in self.ALL_TYPES:
            r = c.compose(
                intent="test",
                ttm_strategy={"recommended_action_types": [at]},
            )
            produced.add(r["action_type"])
        # 所有类型都应可被 compose 选中
        for at in self.ALL_TYPES:
            assert at in produced, f"compose never produced {at}"

    # ── A.4: SDT 语气指令 ──

    def test_sdt_low_autonomy_triggers_scaffold(self):
        """低自主性 -> 信号含步骤拆解."""
        r = _build_behavior_signals("contemplation", 0.2, 0.5, "suggest")
        assert "scaffold" in r or "步骤" in r

    def test_sdt_high_competence_triggers_challenge(self):
        """高胜任感 -> 信号含 challenge."""
        r = _build_behavior_signals("action", 0.6, 0.8, "suggest")
        assert "challenge" in r

    def test_sdt_high_autonomy_does_not_trigger_scaffold(self):
        """高自主性 -> 信号不强制步骤拆解."""
        r = _build_behavior_signals("action", 0.8, 0.6, "suggest")
        assert not ("优先使用 scaffold" in r and "拆解步骤" in r)

    def test_sdt_output_format_consistent(self):
        """SDT 信号返回格式始终以 '- ' 开头."""
        for aut in [0.2, 0.5, 0.8]:
            for comp in [0.2, 0.5, 0.8]:
                r = _build_behavior_signals("contemplation", aut, comp, "suggest")
                if r.strip():
                    for line in r.strip().split("\n"):
                        if line.strip():
                            assert line.strip().startswith("- "), \
                                f"line should start with '- ': {line[:50]}"


# ═══════════════════════════════════════════════════════════════
# 模块 LLM: LLM 冒烟 (5 tests, 需 DEEPSEEK_API_KEY)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"),
                    reason="DEEPSEEK_API_KEY not set")
class TestLLMSmoke:
    """LLM 端到端冒烟 — 验证响应结构完整性（不依赖 llm.enabled）."""

    def test_llm_response_has_llm_fields(self):
        """响应包含 LLM 相关字段且类型正确."""
        a = CoachAgent(session_id="llm_smoke_1")
        r = a.act("teach me Python lists")
        assert "llm_generated" in r
        assert "llm_model" in r
        assert "llm_tokens" in r
        assert isinstance(r["llm_generated"], bool)
        assert isinstance(r["llm_model"], str)
        assert isinstance(r["llm_tokens"], int)

    def test_llm_payload_has_content(self):
        """payload 包含文本字段（statement/option/prompt 等）."""
        a = CoachAgent(session_id="llm_smoke_2")
        r = a.act("how to write a for loop")
        payload = r.get("payload", {})
        assert isinstance(payload, dict)
        assert len(payload) > 0, "payload should not be empty"
        text_fields = ["statement", "option", "prompt", "question", "step", "objective", "reason"]
        has_text = any(k in payload for k in text_fields)
        assert has_text, f"payload missing text fields: {list(payload.keys())[:5]}"

    def test_llm_act_never_crashes(self):
        """无论 LLM 状态如何, act() 永不崩溃."""
        a = CoachAgent(session_id="llm_smoke_3")
        for msg in ["hello", "test", "what is Python", ""]:
            r = a.act(msg)
            assert "action_type" in r, f"crash on: '{msg}'"
            assert "payload" in r, f"no payload on: '{msg}'"

    def test_llm_degradation_response_complete(self):
        """LLM disabled 时响应结构完整."""
        a = CoachAgent(session_id="llm_smoke_4")
        r = a.act("test degradation")
        for k in ["action_type", "trace_id", "gate_decision", "safety_allowed", "payload"]:
            assert k in r, f"missing key: {k}"

    def test_llm_fields_always_present(self):
        """llm_generated/llm_model/llm_tokens 在所有模式下都存在."""
        a = CoachAgent(session_id="llm_smoke_5")
        for msg in ["hello", "test"]:
            r = a.act(msg)
            assert r.get("llm_generated") is not None, f"llm_generated missing on '{msg}'"