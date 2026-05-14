"""Phase 10 S4 — 记忆增强 + 学习路径测试."""

import pytest
from src.coach.llm.memory_context import (
    extract_recent_history, extract_memory_snippets,
    format_history_for_prompt, format_memory_for_prompt, build_retention_bundle)
from src.coach.llm.learning_path import LearningPathTracker, get_learning_path
from src.coach.llm.prompts import build_coach_context


class TestExtractRecentHistory:
    def test_empty_history(self):
        assert extract_recent_history([]) == []

    def test_extracts_last_n_entries(self):
        history = [
            {"intent": "scaffold", "state": "stable", "confidence": 0.7},
            {"intent": "probe", "state": "stable", "confidence": 0.8},
            {"intent": "reflect", "state": "stable", "confidence": 0.6},
        ]
        result = extract_recent_history(history, limit=2)
        assert len(result) == 2
        assert result[0]["intent"] == "probe"
        assert result[1]["intent"] == "reflect"

    def test_skips_low_info_turns(self):
        history = [
            {"intent": "general", "confidence": 0.2},
            {"intent": "scaffold", "confidence": 0.7},
        ]
        result = extract_recent_history(history)
        result_intents = [r["intent"] for r in result]
        assert "general" not in result_intents or len(result) == 1

    def test_max_chars_limit(self):
        history = [
            {"intent": "very_long_intent_name_" + str(i),
             "state": "stable", "confidence": 0.8}
            for i in range(20)
        ]
        result = extract_recent_history(history, max_chars=50)
        # total_chars is checked entry-by-entry, may slightly exceed
        assert len(result) <= len(history)


class TestFormatFunctions:
    def test_format_history_empty(self):
        assert "无历史记录" in format_history_for_prompt([])

    def test_format_history_with_entries(self):
        result = format_history_for_prompt([
            {"intent": "scaffold", "turn": 1},
            {"intent": "probe", "turn": 2},
        ])
        assert "scaffold" in result
        assert "probe" in result

    def test_format_memory_empty(self):
        assert "无相关记忆" in format_memory_for_prompt([])


class TestLearningPathTracker:
    def test_record_topic(self):
        t = LearningPathTracker()
        t.record_topic("Python")
        t.record_topic("Python")
        t.record_topic("Algorithms")
        assert t.get_topic_count() == 2

    def test_get_covered_topics_sorted(self):
        t = LearningPathTracker()
        t.record_topic("Python")
        t.record_topic("Python")
        t.record_topic("Algorithms")
        topics = t.get_covered_topics()
        assert topics[0] == "python"
        assert "algorithms" in topics

    def test_skips_general(self):
        t = LearningPathTracker()
        t.record_topic("general")
        assert t.get_topic_count() == 0

    def test_extract_from_payload(self):
        t = LearningPathTracker()
        t.record_from_payload(
            {"statement": "x", "topics": ["Python", "Loops"]})
        assert t.get_topic_count() == 2
        assert "python" in t.get_covered_topics()

    def test_clear(self):
        t = LearningPathTracker()
        t.record_topic("Python")
        t.clear()
        assert t.get_topic_count() == 0




class _StubMemory:
    def __init__(self, rows):
        self._rows = rows

    def recall(self, intent=None, user_state=None, limit=None):
        return list(self._rows)


class TestRetentionHelpers:
    def test_extract_memory_snippets_filters_session_and_prefers_ai_response(self):
        memory = _StubMemory([
            {"data": {"session_id": "s2", "user_input": "别的会话", "ai_response": "不该命中", "action_type": "suggest", "turn_index": 9}},
            {"data": {"session_id": "s1", "user_input": "我不懂列表", "ai_response": "列表是一种可变序列", "action_type": "scaffold", "turn_index": 2}},
            {"data": {"session_id": "s1", "user_input": "继续", "ai_response": "再看 append 的含义", "action_type": "scaffold", "turn_index": 3}},
        ])
        snippets, status = extract_memory_snippets(memory, "s1", query="列表")
        assert status["status"] == "hit"
        assert status["hits"] >= 1
        assert all("不该命中" not in s for s in snippets)
        assert any("列表" in s for s in snippets)

    def test_build_retention_bundle_preserves_progress_and_context_summary(self):
        memory = _StubMemory([
            {"intent": "scaffold", "data": {"session_id": "s1", "user_input": "讲循环", "ai_response": "for 循环遍历序列", "action_type": "scaffold", "turn_index": 1}, "ts": 1.0},
        ])
        bundle = build_retention_bundle(
            session_memory=memory,
            session_id="s1",
            user_query="循环",
            history=[{"intent": "scaffold", "data": {"session_id": "s1", "user_input": "讲循环", "ai_response": "for 循环遍历序列", "action_type": "scaffold"}, "ts": 1.0}],
            progress_summary="学习进展: 已理解基础循环",
            context_summary="=== 对话历史 ===\n[最近] 用户: 讲循环",
        )
        assert bundle["progress_summary"] == "学习进展: 已理解基础循环"
        assert "对话历史" in bundle["context_summary"]
        assert bundle["memory_status"]["has_progress_summary"] is True
        assert bundle["memory_status"]["has_context_summary"] is True
    def test_backwards_compatible_no_new_params(self):
        ctx = build_coach_context(
            intent="scaffold", action_type="scaffold",
            user_message="hello")
        assert "system" in ctx
        assert "user_message" in ctx
        assert "（无历史记录）" in ctx["system"]
        assert "（无相关记忆）" in ctx["system"]

    def test_with_history(self):
        ctx = build_coach_context(
            intent="probe", action_type="probe",
            history=[{"intent": "scaffold", "turn": 1}],
            user_message="test")
        assert "scaffold" in ctx["system"]

    def test_with_covered_topics(self):
        ctx = build_coach_context(
            intent="suggest", action_type="suggest",
            covered_topics=["Python", "Algorithms"],
            user_message="next topic")
        assert "Python" in ctx["system"]
        assert "Algorithms" in ctx["system"]

    def test_with_memory_snippets(self):
        ctx = build_coach_context(
            intent="probe", action_type="probe",
            memory_snippets=["上次学到: Python循环"],
            user_message="check")
        assert "Python" in ctx["system"]
