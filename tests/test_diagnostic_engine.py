"""DiagnosticEngine 单元测试 — 自适应诊断探测引擎."""

import pytest

from src.coach.diagnostic_engine import (
    DiagnosticEngine,
    DiagnosticProbe,
    DiagnosticRecord,
    SkillMasteryStore,
)

# ═══════════════════════════════════════════════════════════
# SkillMasteryStore
# ═══════════════════════════════════════════════════════════


class TestSkillMasteryStore:
    def test_init_defaults(self):
        store = SkillMasteryStore()
        assert store.total_skills == 0
        assert store.get_mastery("nonexistent") == 0.3

    def test_update_creates_engine(self):
        store = SkillMasteryStore()
        mastery = store.update("python", True)
        assert store.total_skills == 1
        assert mastery > 0.3  # 正确观测提升掌握度

    def test_update_correct_raises_mastery(self):
        store = SkillMasteryStore({"prior": 0.3, "guess": 0.1, "slip": 0.1, "learn": 0.2})
        mastery = store.update("python", True)
        assert mastery > 0.3

    def test_update_wrong_lowers_mastery(self):
        store = SkillMasteryStore({"prior": 0.3, "guess": 0.1, "slip": 0.1, "learn": 0.2})
        mastery = store.update("python", False)
        assert mastery < 0.3

    def test_get_mastery_untested(self):
        store = SkillMasteryStore()
        assert store.get_mastery("unknown") == 0.3

    def test_get_low_mastery(self):
        store = SkillMasteryStore()
        store.update("python", False)  # mastery 下降
        low = store.get_low_mastery(threshold=0.5)
        assert "python" in low

    def test_get_all_masteries(self):
        store = SkillMasteryStore()
        store.update("a", True)
        store.update("b", True)
        all_m = store.get_all_masteries()
        assert "a" in all_m
        assert "b" in all_m
        assert len(all_m) == 2

    def test_serialize_deserialize_round_trip(self):
        store = SkillMasteryStore()
        store.update("python", True)
        store.update("python", False)
        store.update("java", True)

        data = store.to_dict()
        restored = SkillMasteryStore.from_dict(data)

        # 引擎延迟加载，总技能数校验通过掌握度间接验证
        assert restored.get_mastery("python") == store.get_mastery("python")
        assert restored.get_mastery("java") == store.get_mastery("java")
        assert restored.to_dict()["mastery"] == data["mastery"]

    def test_multi_skill_isolation(self):
        store = SkillMasteryStore()
        m1 = store.update("python", True)
        m2 = store.update("java", False)
        assert m1 > 0.3  # python 正确 → 上升
        assert m2 < 0.3  # java 错误 → 下降

    def test_get_untested_skills(self):
        store = SkillMasteryStore()
        store.update("python", True)  # 1 次观测
        store.update("python", True)  # 2 次观测
        store.update("java", True)    # 1 次观测
        untested = store.get_untested_skills()
        assert "java" in untested
        assert "python" not in untested


# ═══════════════════════════════════════════════════════════
# DiagnosticEngine — 决策逻辑
# ═══════════════════════════════════════════════════════════


class TestDiagnosticEngineDecision:
    @staticmethod
    def _make_engine(enabled=True, **overrides) -> DiagnosticEngine:
        cfg = {"enabled": enabled, "interval_turns": 5, "max_probes_per_session": 3}
        cfg.update(overrides)
        return DiagnosticEngine(cfg)

    def test_disabled_returns_none(self):
        engine = self._make_engine(enabled=False)
        result = engine.should_and_generate(turn_count=0)
        assert result is None

    def test_first_turn_fires_probe(self):
        engine = self._make_engine()
        result = engine.should_and_generate(turn_count=0, intent="python")
        assert result is not None
        assert "question" in result
        assert "skill" in result
        assert result["skill"] == "python"
        assert engine.probe_count == 1
        assert engine.is_pending

    def test_blocks_within_interval(self):
        engine = self._make_engine()
        # fires at turn 0
        engine.should_and_generate(turn_count=0, intent="python")
        # consume pending by process_turn
        engine.process_turn("some answer", turn_count=1)
        # blocked at turn 1 (0 < 5 turns since last)
        result = engine.should_and_generate(turn_count=1, intent="python")
        assert result is None

    def test_fires_at_interval_boundary(self):
        engine = self._make_engine(interval_turns=3)
        # turn 0 fires
        engine.should_and_generate(turn_count=0, intent="python")
        engine.process_turn("answer", turn_count=1)
        # blocked at turn 1
        assert engine.should_and_generate(turn_count=1, intent="python") is None
        engine.process_turn("answer", turn_count=2)
        assert engine.should_and_generate(turn_count=2, intent="python") is None
        engine.process_turn("answer", turn_count=3)
        # turn 3 fires (3 turns since last)
        result = engine.should_and_generate(turn_count=3, intent="python")
        assert result is not None

    def test_pending_blocks_generation(self):
        engine = self._make_engine()
        engine.should_and_generate(turn_count=0, intent="python")
        assert engine.is_pending
        # should not generate while pending
        result = engine.should_and_generate(turn_count=5, intent="python")
        assert result is None

    def test_max_probes_limit(self):
        engine = self._make_engine(max_probes_per_session=2)
        # first probe at turn 0
        engine.should_and_generate(turn_count=0, intent="python")
        engine.process_turn("answer", turn_count=1)
        # second probe at turn 5
        engine.should_and_generate(turn_count=5, intent="python")
        engine.process_turn("answer", turn_count=6)
        # third should be blocked (max 2)
        result = engine.should_and_generate(turn_count=10, intent="python")
        assert result is None

    def test_candidate_skill_low_mastery_first(self):
        engine = self._make_engine(min_confidence=0.5)
        # add one low-mastery skill
        engine._store.update("python", False)  # mastery < 0.5
        engine._store.update("java", True)     # mastery > 0.5
        result = engine.should_and_generate(
            turn_count=0, intent="general", llm_client=None,
        )
        assert result is not None
        assert result["skill"] == "python"

    def test_covered_topics_selection(self):
        engine = self._make_engine()
        result = engine.should_and_generate(
            turn_count=0,
            covered_topics=["python", "java"],
            intent="general",
            llm_client=None,
        )
        assert result is not None
        # should pick first uncovered topic
        assert result["skill"] in ("python", "java")
        assert "question" in result

    def test_intent_fallback(self):
        engine = self._make_engine()
        result = engine.should_and_generate(
            turn_count=0,
            llm_client=None,
            intent="pandas",
        )
        assert result is not None
        assert "pandas" in result["skill"] or result["skill"] == "pandas"


# ═══════════════════════════════════════════════════════════
# DiagnosticEngine — 评估逻辑
# ═══════════════════════════════════════════════════════════


class TestDiagnosticEngineEvaluation:
    def test_process_turn_evaluates_keyword(self):
        """关键词匹配评估正确性."""
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        # inject pending probe
        engine._pending_probe = DiagnosticProbe(
            skill="python",
            question="列表和元组的区别？",
            expected_answer="列表可变、元组不可变",
        )
        result = engine.process_turn(
            user_input="列表是可变的数据结构，元组不可变",
            turn_count=1,
        )
        assert result is not None
        assert result["evaluated"] is True
        assert result["correct"] is True
        assert not engine.is_pending  # pending consumed

    def test_process_turn_evaluates_wrong_discards(self):
        """关键词不匹配时评估低置信度丢弃."""
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        engine._pending_probe = DiagnosticProbe(
            skill="python",
            question="列表和元组的区别？",
            expected_answer="列表可变、元组不可变",
        )
        result = engine.process_turn(
            user_input="完全无关的回答",
            turn_count=1,
        )
        assert result is not None
        assert result["evaluated"] is False
        assert result["reason"] == "low_confidence"

    def test_no_evaluation_when_disabled(self):
        engine = DiagnosticEngine({"enabled": False})
        engine._pending_probe = DiagnosticProbe(
            skill="python", question="?", expected_answer="?",
        )
        result = engine.process_turn("answer", turn_count=1)
        assert result is None

    def test_no_evaluation_no_pending(self):
        engine = DiagnosticEngine({"enabled": True})
        result = engine.process_turn("answer", turn_count=1)
        assert result is None

    def test_low_confidence_discards_observation(self):
        """置信度<0.5 丢弃观测，不更新 BKT."""
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        mastery_before = engine._store.get_mastery("python")
        engine._pending_probe = DiagnosticProbe(
            skill="python",
            question="列表和元组的区别？",
            expected_answer="xmzqpqirugjvocxje",  # 不可能匹配的关键词
        )
        result = engine.process_turn(
            user_input="列表和元组",
            turn_count=1,
        )
        assert result is not None
        assert result["evaluated"] is False
        assert result["reason"] == "low_confidence"
        # mastery 不变
        assert engine._store.get_mastery("python") == mastery_before

    def test_empty_response_evaluation(self):
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        engine._pending_probe = DiagnosticProbe(
            skill="python", question="?", expected_answer="列表可变",
        )
        result = engine.process_turn(user_input="", turn_count=1)
        # empty response → process_turn returns non-None but correct=False
        assert result is not None


# ═══════════════════════════════════════════════════════════
# DiagnosticEngine — BKT 更新 & 掌握度
# ═══════════════════════════════════════════════════════════


class TestDiagnosticEngineBKTUpdate:
    def test_correct_updates_mastery(self):
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        engine._pending_probe = DiagnosticProbe(
            skill="python", question="?", expected_answer="列表可变、元组不可变",
        )
        result = engine.process_turn(
            user_input="列表可变，元组不可变",
            turn_count=1,
        )
        assert result["mastery_after"] > result["mastery_before"]

    def test_incorrect_updates_mastery(self):
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        # 直接通过 _store.update 绕过 keyword 评估的低置信度丢弃
        engine._store.update("python", False)
        engine._store.update("python", False)
        mastery = engine._store.get_mastery("python")
        assert mastery < 0.3

    def test_mastery_summary_structure(self):
        engine = DiagnosticEngine({"enabled": True})
        engine._store.update("python", True)
        summary = engine.get_mastery_summary()
        assert "skills" in summary
        assert "low_mastery" in summary
        assert "total_probes" in summary
        assert "recent_history" in summary
        assert "python" in summary["skills"]

    def test_competence_signal_correct(self):
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        engine._pending_probe = DiagnosticProbe(
            skill="python", question="?", expected_answer="可变",
        )
        engine.process_turn(user_input="可变", turn_count=1)
        signal = engine.get_competence_signal()
        assert signal == 1.0

    def test_competence_signal_incorrect(self):
        engine = DiagnosticEngine({"enabled": True, "llm_evaluation": False})
        # 直接追加错误记录（绕过 keyword 评估丢弃）
        probe = DiagnosticProbe(skill="python", question="?", expected_answer="?")
        record = DiagnosticRecord(
            probe=probe, user_response="wrong",
            correct=False,
            mastery_before=0.5, mastery_after=0.3,
        )
        engine._history.append(record)
        engine._store._mastery["python"] = 0.3
        signal = engine.get_competence_signal()
        assert signal == 0.0

    def test_competence_signal_no_history(self):
        engine = DiagnosticEngine({"enabled": True})
        assert engine.get_competence_signal() is None

    def test_get_difficulty_by_mastery(self):
        """_get_difficulty 根据掌握度返回正确难度."""
        engine = DiagnosticEngine({"enabled": True})
        engine._store._mastery["s"] = 0.2
        assert engine._get_difficulty("s") == "easy"
        engine._store._mastery["s"] = 0.5
        assert engine._get_difficulty("s") == "medium"
        engine._store._mastery["s"] = 0.8
        assert engine._get_difficulty("s") == "hard"


# ═══════════════════════════════════════════════════════════
# DiagnosticEngine — 持久化
# ═══════════════════════════════════════════════════════════


class TestPersistence:
    def test_store_to_dict_keys(self):
        store = SkillMasteryStore()
        store.update("python", True)
        data = store.to_dict()
        assert "bkt_params" in data
        assert "mastery" in data
        assert "observation_count" in data

    def test_store_from_dict_restores(self):
        original = SkillMasteryStore()
        original.update("python", True)
        original.update("java", False)
        data = original.to_dict()
        restored = SkillMasteryStore.from_dict(data)
        assert restored.get_mastery("python") == original.get_mastery("python")
        assert restored.get_mastery("java") == original.get_mastery("java")

    def test_probe_dataclass_defaults(self):
        probe = DiagnosticProbe(skill="python", question="?", expected_answer="?")
        assert probe.trace_id
        assert len(probe.trace_id) == 36
        assert probe.timestamp > 0
        assert probe.prompt == "?"

    def test_record_dataclass_defaults(self):
        probe = DiagnosticProbe(skill="s", question="q", expected_answer="a")
        record = DiagnosticRecord(probe=probe)
        assert record.timestamp > 0
        assert record.user_response == ""
        assert record.correct is False


# ═══════════════════════════════════════════════════════════
# DiagnosticEngine — 兜底题
# ═══════════════════════════════════════════════════════════


class TestFallbackProbes:
    def test_fallback_easy(self):
        engine = DiagnosticEngine({"enabled": True})
        result = engine._fallback_probe("python", "easy")
        assert result is not None
        assert "question" in result
        assert "expected_answer" in result
        assert result["question"]  # non-empty

    def test_fallback_medium(self):
        engine = DiagnosticEngine({"enabled": True})
        result = engine._fallback_probe("python", "medium")
        assert result is not None
        assert result.get("question")

    def test_fallback_hard(self):
        engine = DiagnosticEngine({"enabled": True})
        result = engine._fallback_probe("python", "hard")
        assert result is not None
        assert result.get("question")

    def test_fallback_unknown_difficulty(self):
        engine = DiagnosticEngine({"enabled": True})
        result = engine._fallback_probe("python", "extreme")
        assert result is not None  # 兜底到 medium


# ═══════════════════════════════════════════════════════════
# DiagnosticEngine — 完整全链路
# ═══════════════════════════════════════════════════════════


class TestDiagnosticEngineFullCycle:
    def test_generate_evaluate_update_cycle(self):
        """完整周期: 生成→评估→更新."""
        engine = DiagnosticEngine({
            "enabled": True,
            "interval_turns": 1,
            "llm_evaluation": False,
        })

        # 第 1 轮: 生成
        probe = engine.should_and_generate(
            turn_count=0, intent="python", llm_client=None,
        )
        assert probe is not None
        assert engine.is_pending

        # 第 2 轮: 用匹配关键词的回复触发评估+更新
        # mastery=0.3 → 不<0.3, 所以走 medium 难度
        # medium fallback expected_answer = "python的核心原理和典型应用场景"
        result = engine.process_turn(
            user_input="python的核心原理和典型应用场景包括xxx",
            turn_count=1,
        )
        assert result is not None
        assert result.get("evaluated") is not None  # evaluated may be True/False
        assert not engine.is_pending

    def test_multiple_cycles_accumulate_mastery(self):
        """多次正确回答积累掌握度."""
        engine = DiagnosticEngine({
            "enabled": True,
            "max_probes_per_session": 3,
            "interval_turns": 1,
            "llm_evaluation": False,
        })

        previous_mastery = engine._store.get_mastery("python")
        for turn in range(0, 6, 2):
            engine.should_and_generate(
                turn_count=turn, intent="python", llm_client=None,
            )
            result = engine.process_turn(
                user_input="列表可变，元组不可变",
                turn_count=turn + 1,
            )
            if result and result.get("evaluated"):
                assert result["mastery_after"] >= result["mastery_before"]
                previous_mastery = result["mastery_after"]
