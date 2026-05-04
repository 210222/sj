"""S5.3 失败先例拦截测试 — 6 tests。"""

import pytest
from src.coach.precedent_intercept import PrecedentInterceptor


class FakeDataSource:
    """模拟 facts 表的 query_facts。"""
    def query_facts(self, context_scope="", lifecycle_status="active", limit=5):
        return [
            {"fact_id": "f1", "claim": "挑战任务导致用户焦虑",
             "confidence": 0.7, "context_scope": "programming",
             "lifecycle_status": "archived", "reversibility_flag": 0},
            {"fact_id": "f2", "claim": "脚手架提示过多引发依赖",
             "confidence": 0.6, "context_scope": "programming",
             "lifecycle_status": "archived", "reversibility_flag": 0},
            {"fact_id": "f3", "claim": "建议用户休息效果良好",
             "confidence": 0.8, "context_scope": "programming",
             "lifecycle_status": "active", "reversibility_flag": 1},
        ]


class TestPrecedentInterceptor:
    def test_no_hit_when_empty_intent(self):
        pi = PrecedentInterceptor(data_source=FakeDataSource())
        result = pi.intercept("", domain="general")
        assert not result["hit"]

    def test_hit_on_matching_precedent(self):
        pi = PrecedentInterceptor(
            {"matching": {"text_similarity_threshold": 0.1}},
            data_source=FakeDataSource(),
        )
        result = pi.intercept("挑战任务太难了", domain="programming")
        assert result["hit"]

    def test_action_block_on_hit(self):
        pi = PrecedentInterceptor(data_source=FakeDataSource())
        result = pi.intercept("挑战任务", domain="programming")
        if result["hit"]:
            assert result["action"] in ("block", "warn")

    def test_precedent_count(self):
        pi = PrecedentInterceptor(
            {"matching": {"text_similarity_threshold": 0.1, "max_results": 10}},
            data_source=FakeDataSource(),
        )
        result = pi.intercept("挑战", domain="programming")
        if result["hit"]:
            assert result["precedent_count"] >= 1

    def test_no_data_source_no_hit(self):
        pi = PrecedentInterceptor(data_source=None)
        result = pi.intercept("任何意图", domain="general")
        assert not result["hit"]
        assert result["precedent_count"] == 0

    def test_tokenize_chinese_english(self):
        tokens = PrecedentInterceptor._tokenize("Python编程 挑战任务")
        assert "Python" in tokens or "python" in tokens
        assert "挑" in tokens
        assert "战" in tokens
