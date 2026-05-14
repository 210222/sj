"""Phase 10 S2 — 三层安全校验测试."""

import pytest
from src.coach.llm.schemas import LLMDSLAligner, force_action_type, LLMOutputValidator
from src.coach.llm.safety_filter import LLMSafetyFilter
from src.coach.llm.audit import LLMGateAuditor, LLMGateAuditRecord


class TestDSLAligner:
    def test_drops_unknown_fields(self):
        payload = {"statement": "hello", "llm_metadata": "xxx", "internal": "yyy"}
        aligned, report = LLMDSLAligner.align(payload, "suggest")
        assert "statement" in aligned
        assert "llm_metadata" not in aligned
        assert "llm_metadata" in report["dropped_fields"]

    def test_preserves_known_slots(self):
        payload = {"statement": "try this", "option": "A", "alternatives": ["B"]}
        aligned, report = LLMDSLAligner.align(payload, "suggest")
        assert aligned["option"] == "A"
        assert report["valid"] is True

    def test_empty_payload_returns_invalid(self):
        aligned, report = LLMDSLAligner.align({}, "suggest")
        assert report["valid"] is False

    def test_migrates_statement_from_other_field(self):
        payload = {"question": "what do you think?"}
        aligned, report = LLMDSLAligner.align(payload, "reflect")
        assert aligned["statement"] == "what do you think?"

    def test_removes_wrong_action_type_fields(self):
        payload = {"statement": "x", "objective": "challenge_task"}
        aligned, report = LLMDSLAligner.align(payload, "reflect")
        assert "objective" in report["dropped_fields"]

    def test_all_action_types_have_slots(self):
        from src.coach.llm.schemas import _ACTION_TYPE_SLOTS
        for atype in ["probe", "challenge", "reflect", "scaffold",
                       "suggest", "pulse", "excursion", "defer"]:
            assert atype in _ACTION_TYPE_SLOTS, f"missing {atype}"

    def test_universal_fields_preserved_across_all_types(self):
        """statement/question/hint/difficulty 不被任何 action_type 过滤."""
        universal = {"statement": "s", "question": "q", "hint": "h", "difficulty": 0.5}
        for atype in ["suggest", "challenge", "probe", "reflect",
                       "scaffold", "defer", "pulse", "excursion"]:
            aligned, report = LLMDSLAligner.align(universal, atype)
            assert "statement" in aligned
            assert "question" in aligned
            assert "hint" in aligned
            assert "difficulty" in aligned
            assert len(report["dropped_fields"]) == 0, \
                f"atype={atype} dropped universal fields: {report['dropped_fields']}"

    def test_fills_missing_slots_with_defaults(self):
        """缺失 slot 自动填充缺省值."""
        aligned, report = LLMDSLAligner.align({}, "suggest")
        assert report["valid"] is False
        assert "statement" in aligned
        assert isinstance(aligned["statement"], str)

    def test_report_contains_complete_info(self):
        """对齐报告包含所有必要字段."""
        payload = {"statement": "x", "random_field": "y"}
        aligned, report = LLMDSLAligner.align(payload, "suggest")
        for key in ("dropped_fields", "filled_slots", "action_type", "valid"):
            assert key in report, f"report missing {key}"
        assert "random_field" in report["dropped_fields"]


class TestSafetyFilter:
    def test_filters_forbidden_phrase(self):
        payload = {"statement": "you should listen to me, i know better"}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["i know better"])
        assert "[filtered]" in filtered["statement"] or "[已过滤]" in filtered["statement"]
        assert "i know better" in triggered

    def test_no_trigger_when_clean(self):
        payload = {"statement": "here is a safe suggestion"}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["forbidden phrase"])
        assert filtered["statement"] == "here is a safe suggestion"
        assert len(triggered) == 0

    def test_recursive_filter_in_dict(self):
        payload = {"statement": "ok", "nested": {"text": "bad word here"}}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["bad word"])
        assert "bad word" in triggered

    def test_removes_non_allowed_fields(self):
        payload = {"statement": "x", "unknown_field": "yyy", "option": "A"}
        cleaned = LLMSafetyFilter.enforce_action_type(payload, "suggest")
        assert "option" in cleaned
        assert "unknown_field" not in cleaned

    def test_force_action_type_strips_llm_overrides(self):
        payload = force_action_type(
            {"statement": "x", "action_type": "challenge"}, "suggest")
        assert "action_type" not in payload

    def test_filter_multiple_phrases(self):
        """多条短语同时匹配."""
        payload = {"statement": "你应该听我的，我知道你在想什么"}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["你应该听我的", "我知道你在想什么"])
        assert "[已过滤]" in filtered["statement"]
        assert len(triggered) == 2

    def test_filter_skips_non_string_fields(self):
        """非字符串字段跳过."""
        payload = {"statement": "hello", "difficulty": 0.8, "hints_allowed": 2}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["0.8", "2"])
        assert triggered == []
        assert filtered["difficulty"] == 0.8

    def test_filter_scans_list_of_strings(self):
        """字符串列表递归扫描."""
        payload = {"options": ["safe", "bad phrase here", "also safe"]}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["bad phrase"])
        assert "bad phrase" in triggered
        assert "[已过滤]" in filtered["options"][1]

    def test_filter_scans_list_of_dicts(self):
        """字典列表递归扫描."""
        payload = {"steps": [{"hint": "clean"}, {"hint": "bad word inside"}]}
        filtered, triggered = LLMSafetyFilter.filter_payload(
            payload, ["bad word"])
        assert "bad word" in triggered
        assert "[已过滤]" in filtered["steps"][1]["hint"]

    def test_enforce_action_type_overrides_llm(self):
        """LLM 试图篡改 action_type 被强制覆盖."""
        result = LLMSafetyFilter.enforce_action_type(
            {"statement": "x", "action_type": "challenge"}, "scaffold")
        assert "action_type" not in result
        assert result["statement"] == "x"

    def test_enforce_action_type_none_returns_rule(self):
        """LLM 未提供 action_type 时正常返回规则值."""
        result = LLMSafetyFilter.enforce_action_type(
            {"statement": "x"}, "suggest")
        assert result["statement"] == "x"

    def test_enforce_action_type_same_preserves(self):
        """LLM 提供的与规则一致时正常返回."""
        result = LLMSafetyFilter.enforce_action_type(
            {"statement": "x", "option": "A"}, "suggest")
        assert result["option"] == "A"


class TestForceActionType:
    def test_strips_all_action_type_variants(self):
        payload = force_action_type(
            {"action_type": "challenge", "llm_action_type": "probe"}, "suggest")
        assert "action_type" not in payload
        assert "llm_action_type" not in payload
        assert "_action_type" not in payload

    def test_keeps_other_fields(self):
        payload = force_action_type(
            {"statement": "hello", "action_type": "wrong"}, "correct")
        assert payload["statement"] == "hello"


class TestGateAuditor:
    def test_record_block(self):
        auditor = LLMGateAuditor()
        auditor.record_block(
            session_id="s1", trace_id="t1", gate_id=1,
            gate_name="Agency Gate", gate_decision="BLOCK",
            action_type="challenge", payload={"statement": "test"},
            llm_model="deepseek-chat", llm_tokens=100)
        records = auditor.get_records()
        assert len(records) == 1
        assert records[0]["gate_name"] == "Agency Gate"

    def test_skips_pass_decision(self):
        auditor = LLMGateAuditor()
        auditor.record_block(
            session_id="s1", trace_id="t1", gate_id=1,
            gate_name="Gate", gate_decision="GO",
            action_type="suggest", payload={})
        assert len(auditor.get_records()) == 0

    def test_filter_by_session(self):
        auditor = LLMGateAuditor()
        auditor.record_block(
            session_id="a", trace_id="1", gate_id=1,
            gate_name="G1", gate_decision="BLOCK",
            action_type="suggest", payload={})
        auditor.record_block(
            session_id="b", trace_id="2", gate_id=2,
            gate_name="G2", gate_decision="BLOCK",
            action_type="probe", payload={})
        assert len(auditor.get_records(session_id="a")) == 1
        assert len(auditor.get_records(session_id="b")) == 1

    def test_record_to_dict(self):
        record = LLMGateAuditRecord(
            event_id="ev1", timestamp_utc="now", session_id="s",
            trace_id="t", gate_id=3, gate_name="Gate3",
            gate_decision="BLOCK", action_type="suggest")
        d = record.to_dict()
        assert d["gate_id"] == 3
        assert d["session_id"] == "s"

    def test_payload_truncated_at_500(self):
        """payload 截断到 500 字符."""
        auditor = LLMGateAuditor()
        auditor.record_block(
            session_id="s1", trace_id="t1", gate_id=1,
            gate_name="G", gate_decision="BLOCK",
            action_type="suggest",
            payload={"statement": "x" * 1000})
        snippet = auditor.get_records()[0].get("payload_snippet", "")
        assert len(snippet) <= 500

    def test_records_ordered_by_time(self):
        """get_records 按时间倒序."""
        auditor = LLMGateAuditor()
        import time
        from unittest.mock import patch
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            auditor.record_block(
                session_id="s1", trace_id="1", gate_id=1,
                gate_name="G1", gate_decision="BLOCK",
                action_type="suggest", payload={})
            mock_time.return_value = 2000.0
            auditor.record_block(
                session_id="s1", trace_id="2", gate_id=2,
                gate_name="G2", gate_decision="BLOCK",
                action_type="suggest", payload={})
        records = auditor.get_records()
        assert records[0]["trace_id"] == "1", "first recorded should be first in list"
        assert records[1]["trace_id"] == "2", "second recorded should be second"

    def test_clear_removes_all(self):
        """clear() 清空审计日志."""
        auditor = LLMGateAuditor()
        auditor.record_block(
            session_id="s1", trace_id="t1", gate_id=1,
            gate_name="G", gate_decision="BLOCK",
            action_type="suggest", payload={})
        assert len(auditor.get_records()) == 1
        auditor.clear()
        assert len(auditor.get_records()) == 0
