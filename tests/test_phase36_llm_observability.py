"""Phase 36 targeted: LLM observability field completeness and consistency."""

import json
import os
import pytest


class TestCacheObservability:
    """验证 CacheObservability dataclass 字段完整性."""

    def test_cache_observability_all_fields_present(self):
        from src.coach.llm.schemas import CacheObservability
        obs = CacheObservability(cache_eligible=True, stable_prefix_hash="abc")
        d = obs.to_dict()
        required = [
            "cache_eligible", "cache_eligibility_reason", "stable_prefix_hash",
            "stable_prefix_chars", "stable_prefix_lines", "stable_prefix_share",
            "action_contract_hash", "policy_layer_hash", "context_layer_hash",
            "context_fingerprint", "prefix_shape_version",
        ]
        for key in required:
            assert key in d, f"missing {key}"

    def test_cache_observability_defaults(self):
        from src.coach.llm.schemas import CacheObservability
        obs = CacheObservability()
        d = obs.to_dict()
        assert d["cache_eligible"] is False
        assert d["prefix_shape_version"] == "1.0.0"
        assert d["stable_prefix_hash"] == ""

    def test_to_dict_rounds_share(self):
        from src.coach.llm.schemas import CacheObservability
        obs = CacheObservability(stable_prefix_share=0.123456789)
        d = obs.to_dict()
        assert d["stable_prefix_share"] == 0.1235  # 4 decimal places


class TestRuntimeObservability:
    """验证 RuntimeObservability dataclass 字段完整性."""

    def test_runtime_observability_all_fields_present(self):
        from src.coach.llm.schemas import RuntimeObservability
        obs = RuntimeObservability(path="http_sync", latency_ms=100.5)
        d = obs.to_dict()
        required = [
            "path", "streaming", "request_started_at_utc", "latency_ms",
            "first_chunk_latency_ms", "stream_duration_ms", "finish_reason",
            "response_model", "tokens_total", "tokens_prompt", "tokens_completion",
            "token_usage_available", "retry_count", "timeout_s", "transport_status",
        ]
        for key in required:
            assert key in d, f"missing {key}"

    def test_runtime_stream_nullable_fields(self):
        from src.coach.llm.schemas import RuntimeObservability
        obs = RuntimeObservability(path="ws_stream", streaming=True)
        d = obs.to_dict()
        assert d["first_chunk_latency_ms"] is None
        assert d["stream_duration_ms"] is None
        assert d["tokens_prompt"] is None
        assert d["tokens_completion"] is None


class TestRetentionObservability:
    """验证 RetentionObservability 字段完整性."""

    def test_retention_observability_all_fields(self):
        from src.coach.llm.schemas import RetentionObservability
        obs = RetentionObservability(
            retention_history_hits=3,
            retention_memory_hits=2,
            retention_duplicate_dropped=1,
            retention_budget_history_limit=12,
            retention_budget_memory_limit=6,
            retention_progress_included=True,
            retention_context_summary_included=False,
            session_scoped=True,
        )
        d = obs.to_dict()
        assert d["retention_history_hits"] == 3
        assert d["retention_memory_hits"] == 2
        assert d["retention_duplicate_dropped"] == 1


class TestLLMObservability:
    """验证 LLMObservability 复合对象."""

    def test_full_observability_to_dict(self):
        from src.coach.llm.schemas import (
            LLMObservability, CacheObservability,
            RuntimeObservability, RetentionObservability,
        )
        full = LLMObservability(
            cache=CacheObservability(cache_eligible=True),
            runtime=RuntimeObservability(path="http_sync"),
            retention=RetentionObservability(retention_history_hits=1),
        )
        d = full.to_dict()
        assert "cache" in d
        assert "runtime" in d
        assert "retention" in d
        assert d["cache"]["cache_eligible"] is True
        assert d["runtime"]["path"] == "http_sync"
        assert d["retention"]["retention_history_hits"] == 1

    def test_llmresponse_with_observability(self):
        from src.coach.llm.schemas import (
            LLMResponse, LLMObservability, CacheObservability, RuntimeObservability,
        )
        obs = LLMObservability(
            cache=CacheObservability(cache_eligible=True),
            runtime=RuntimeObservability(path="http_sync"),
        )
        resp = LLMResponse(content='{"statement":"test"}', model="test", observability=obs)
        assert resp.observability is not None
        assert resp.observability.cache.cache_eligible is True

    def test_llmresponse_without_observability(self):
        from src.coach.llm.schemas import LLMResponse
        resp = LLMResponse(content="test")
        assert resp.observability is None


class TestContextMetaCacheFields:
    """验证 build_coach_context() context_meta 包含 Phase 36 字段."""

    def test_context_meta_has_cache_eligible(self):
        from src.coach.llm.prompts import build_coach_context
        ctx = build_coach_context(
            intent="learn", action_type="scaffold",
            ttm_stage="action", user_message="test cache",
        )
        meta = ctx["context_meta"]
        required = [
            "cache_eligible", "cache_eligibility_reason", "stable_prefix_hash",
            "stable_prefix_lines", "stable_prefix_share", "action_contract_hash",
            "policy_layer_hash", "context_layer_hash", "context_fingerprint",
            "prefix_shape_version",
        ]
        for key in required:
            assert key in meta, f"missing context_meta.{key}"

    def test_stable_prefix_hash_stable_across_user_inputs(self):
        from src.coach.llm.prompts import build_coach_context
        ctx1 = build_coach_context(
            intent="learn", action_type="scaffold",
            ttm_stage="action", user_message="hello world",
        )
        ctx2 = build_coach_context(
            intent="learn", action_type="scaffold",
            ttm_stage="action", user_message="completely different message",
        )
        # Same intent/action_type/stage → same stable prefix → same hash
        assert ctx1["context_meta"]["stable_prefix_hash"] == \
            ctx2["context_meta"]["stable_prefix_hash"]

    def test_context_fingerprint_same_for_same_params(self):
        from src.coach.llm.prompts import build_coach_context
        ctx1 = build_coach_context(
            intent="learn", action_type="scaffold",
            user_message="message A",
        )
        ctx2 = build_coach_context(
            intent="learn", action_type="scaffold",
            user_message="message A",
        )
        # Same params → same full system prompt → same fingerprint
        assert ctx1["context_meta"]["context_fingerprint"] == \
            ctx2["context_meta"]["context_fingerprint"]

    def test_context_fingerprint_differs_with_different_action_type(self):
        from src.coach.llm.prompts import build_coach_context
        ctx1 = build_coach_context(
            intent="learn", action_type="scaffold",
            user_message="test",
        )
        ctx2 = build_coach_context(
            intent="learn", action_type="probe",
            user_message="test",
        )
        # Different action_type → different action_contract → different fingerprint
        assert ctx1["context_meta"]["context_fingerprint"] != \
            ctx2["context_meta"]["context_fingerprint"]

    def test_cache_eligible_true_for_scaffold(self):
        from src.coach.llm.prompts import build_coach_context
        ctx = build_coach_context(
            intent="learn", action_type="scaffold",
            ttm_stage="action", user_message="test",
        )
        assert ctx["context_meta"]["cache_eligible"] is True
        assert ctx["context_meta"]["stable_prefix_share"] > 0.15


class TestRetentionBundleObservability:
    """验证 build_retention_bundle() 返回 retention_observability."""

    def test_retention_bundle_has_observability(self):
        from src.coach.llm.memory_context import build_retention_bundle
        from src.coach.memory import SessionMemory
        m = SessionMemory()
        bundle = build_retention_bundle(
            session_memory=m, session_id="test_ret_obs",
            user_query="hello", history=[],
        )
        obs = bundle.get("retention_observability")
        assert obs is not None
        assert "retention_history_hits" in obs
        assert "retention_memory_hits" in obs
        assert "retention_duplicate_dropped" in obs
        assert "retention_budget_history_limit" in obs
        assert "retention_budget_memory_limit" in obs
        assert "retention_progress_included" in obs
        assert "retention_context_summary_included" in obs
        assert "session_scoped" in obs

    def test_retention_duplicate_dropped_computed(self):
        from src.coach.llm.memory_context import build_retention_bundle
        from src.coach.memory import SessionMemory
        m = SessionMemory()
        # 3 history items, but limit=2 → 1 should be dropped
        history = [
            {"data": {"user_input": "a", "action_type": "suggest"}, "ts": 1.0},
            {"data": {"user_input": "b", "action_type": "scaffold"}, "ts": 2.0},
            {"data": {"user_input": "c", "action_type": "probe"}, "ts": 3.0},
        ]
        bundle = build_retention_bundle(
            session_memory=m, session_id="test_dup",
            user_query="test", history=history,
            limit_history=2, limit_memory=3,
        )
        obs = bundle["retention_observability"]
        assert obs["retention_budget_history_limit"] == 2
        assert obs["retention_history_hits"] <= 2


class TestDashboardAggregatorBuffer:
    """验证 observability 缓冲和聚合."""

    def test_record_and_retrieve(self):
        from api.services.dashboard_aggregator import (
            record_llm_observability, DashboardAggregator,
        )
        obs = {
            "cache": {"cache_eligible": True, "stable_prefix_share": 0.44},
            "runtime": {"path": "http_sync", "latency_ms": 500.0, "tokens_total": 200, "transport_status": "ok"},
            "retention": {},
        }
        record_llm_observability(obs)
        summary = DashboardAggregator.get_llm_runtime_summary()
        assert summary is not None
        assert summary["sample_size"] >= 1
        assert summary["cache_eligible_rate"] >= 0.0

    def test_record_none_does_not_crash(self):
        from api.services.dashboard_aggregator import record_llm_observability
        record_llm_observability(None)
        record_llm_observability({})

    def test_summary_path_distribution(self):
        from api.services.dashboard_aggregator import (
            record_llm_observability, DashboardAggregator,
        )
        for _ in range(2):
            record_llm_observability({
                "cache": {"cache_eligible": True, "stable_prefix_share": 0.5},
                "runtime": {"path": "http_sync", "latency_ms": 100, "tokens_total": 50, "transport_status": "ok"},
                "retention": {},
            })
        summary = DashboardAggregator.get_llm_runtime_summary()
        assert summary["path_distribution"]["http_sync"] >= 2
