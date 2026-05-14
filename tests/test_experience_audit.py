"""Phase 32-A: 体验审计管道基线测试."""
import pytest
from run_experience_audit import (
    _generate_run_id, _get_git_hash, _extract_payload_text,
    AuditState, score_turn, score_all_turns,
)


class TestRunIdentity:
    def test_run_id_unique(self):
        r1 = _generate_run_id()
        r2 = _generate_run_id()
        assert r1 != r2
        assert r1.startswith("run_")

    def test_git_hash_nonempty(self):
        h = _get_git_hash()
        assert len(h) > 0


class TestPayloadExtraction:
    def test_statement_field(self):
        assert _extract_payload_text({"statement": "hello"}) == "hello"

    def test_fallback_through_12_fields(self):
        assert _extract_payload_text({"text": "found"}) == "found"
        assert _extract_payload_text({"message": "found"}) == "found"
        assert _extract_payload_text({"content": "found"}) == "found"
        assert _extract_payload_text({"response": "found"}) == "found"
        assert _extract_payload_text({"feedback": "found"}) == "found"

    def test_empty_payload_returns_empty(self):
        assert _extract_payload_text({}) == ""

    def test_priority_order(self):
        p = {"statement": "first", "text": "second"}
        assert _extract_payload_text(p) == "first"


class TestAuditState:
    def test_record_probe_pass(self):
        a = AuditState("test_run")
        a.record_probe("p1", True, "ok")
        assert a.probes["p1"]["passed"] is True

    def test_record_probe_fail(self):
        a = AuditState("test_run")
        a.record_probe("p1", False, "bad")
        assert "p1" in a.breakpoints_detected

    def test_to_dict(self):
        a = AuditState("r1")
        a.record_probe("p1", True)
        d = a.to_dict()
        assert d["run_id"] == "r1"
        assert "probes" in d


class TestScoring:
    def test_score_turn_referentiality_chinese(self):
        t = {"payload_statement": "列表(list)是Python中用于存储多个元素的数据结构",
             "action_type": "scaffold", "user": "教列表"}
        prev = {"user": "教列表", "payload_statement": "", "action_type": "scaffold"}
        s = score_turn(t, prev)
        assert s["引用性"] > 0, f"Chinese referentiality should match: {s}"

    def test_score_turn_stability_not_length_based(self):
        t = {"payload_statement": "好", "action_type": "suggest", "user": "好"}
        s_long = score_turn(t, None)
        t2 = {"payload_statement": "这是Python中列表(list)的详细说明。" * 10,
              "action_type": "scaffold", "user": "教列表"}
        s_short = score_turn(t2, None)
        # 长文本不应单纯因长度得高分
        assert s_short["稳定性"] <= 4

    def test_score_all_turns_produces_dimensions(self):
        turns = {
            "test": [
                {"turn": 1, "user": "hello", "action_type": "suggest",
                 "payload_statement": "你好，想学什么？", "llm_generated": False},
                {"turn": 2, "user": "Python", "action_type": "scaffold",
                 "payload_statement": "Python是解释型语言，第一步：安装。",
                 "llm_generated": False},
            ]
        }
        result = score_all_turns(turns)
        assert "test" in result
        assert "dimensions" in result["test"]
        for d in ["引用性", "连续性", "无空转", "稳定性", "推进感"]:
            assert d in result["test"]["dimensions"]

    def test_failure_cases_collected(self):
        turns = {
            "test": [
                {"turn": 1, "user": "hello", "action_type": "suggest",
                 "payload_statement": "", "llm_generated": False},
            ]
        }
        result = score_all_turns(turns)
        assert "failure_cases" in result["test"]


class TestPhase36Evidence:
    """Phase 36: observability evidence extraction and artifact generation."""
    import tempfile

    def test_extract_obs_metrics_empty(self):
        from run_experience_audit import _extract_obs_metrics
        rows = _extract_obs_metrics({})
        assert rows == []

    def test_extract_obs_metrics_with_observability(self):
        from run_experience_audit import _extract_obs_metrics
        all_turns = {
            "test_profile": [
                {"turn": 1, "user": "hello", "llm_generated": True,
                 "llm_observability": {
                     "cache": {"cache_eligible": True, "stable_prefix_hash": "abc", "context_fingerprint": "def", "stable_prefix_share": 0.44},
                     "runtime": {"path": "http_sync", "streaming": False, "latency_ms": 123.4, "tokens_total": 100, "transport_status": "ok"},
                     "retention": {"retention_history_hits": 2, "retention_memory_hits": 1, "retention_duplicate_dropped": 0},
                 }},
            ]
        }
        rows = _extract_obs_metrics(all_turns)
        assert len(rows) == 1
        r = rows[0]
        assert r["profile"] == "test_profile"
        assert r["cache_eligible"] is True
        assert r["stable_prefix_hash"] == "abc"
        assert r["latency_ms"] == 123.4
        assert r["tokens_total"] == 100
        assert r["retention_history_hits"] == 2

    def test_extract_obs_metrics_skips_non_llm(self):
        from run_experience_audit import _extract_obs_metrics
        all_turns = {
            "test": [
                {"turn": 1, "user": "hello", "llm_generated": False},  # no observability
                {"turn": 2, "user": "hi", "llm_generated": True,
                 "llm_observability": {
                     "cache": {"cache_eligible": False, "stable_prefix_hash": "xyz", "context_fingerprint": "uvw", "stable_prefix_share": 0.1},
                     "runtime": {"path": "http_sync", "streaming": False, "latency_ms": 50, "tokens_total": 30, "transport_status": "ok"},
                     "retention": {"retention_history_hits": 0, "retention_memory_hits": 0, "retention_duplicate_dropped": 0},
                 }},
            ]
        }
        rows = _extract_obs_metrics(all_turns)
        assert len(rows) == 1  # only turn 2
        assert rows[0]["turn"] == 2

    def test_per_run_evidence_generates_3_files(self):
        import tempfile, os, json
        from run_experience_audit import _generate_per_run_evidence
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            run_dir = Path(tmpdir)
            all_turns = {
                "p1": [
                    {"turn": 1, "user": "hi", "llm_generated": True,
                     "llm_observability": {
                         "cache": {"cache_eligible": True, "stable_prefix_hash": "aaa", "context_fingerprint": "bbb", "stable_prefix_share": 0.5},
                         "runtime": {"path": "http_sync", "streaming": False, "latency_ms": 100, "tokens_total": 50, "transport_status": "ok"},
                         "retention": {"retention_history_hits": 1, "retention_memory_hits": 0, "retention_duplicate_dropped": 0},
                     }},
                ]
            }
            scoring = {"p1": {"avg_score": 14.0, "dimensions": {}, "failure_cases": []}}
            _generate_per_run_evidence(all_turns, scoring, run_dir, "test_run")
            for fname in ["llm_runtime_turns.json", "llm_cache_evidence.json", "llm_observability_summary.json"]:
                assert (run_dir / fname).exists(), f"{fname} should exist"

    def test_cache_evidence_prefix_stability(self):
        import tempfile, json
        from run_experience_audit import _generate_per_run_evidence
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            run_dir = Path(tmpdir)
            # All turns share same prefix hash → stable
            all_turns = {
                "p1": [
                    {"turn": i, "user": str(i), "llm_generated": True,
                     "llm_observability": {
                         "cache": {"cache_eligible": True, "stable_prefix_hash": "same_hash_123", "context_fingerprint": "cfp" + str(i), "stable_prefix_share": 0.44},
                         "runtime": {"path": "http_sync", "streaming": False, "latency_ms": 100, "tokens_total": 50, "transport_status": "ok"},
                         "retention": {"retention_history_hits": 1, "retention_memory_hits": 0, "retention_duplicate_dropped": 0},
                     }}
                    for i in range(3)
                ]
            }
            scoring = {"p1": {"avg_score": 14.0, "dimensions": {}, "failure_cases": []}}
            _generate_per_run_evidence(all_turns, scoring, run_dir, "test_stable")
            ce = json.loads((run_dir / "llm_cache_evidence.json").read_text(encoding="utf-8"))
            assert ce["prefix_hash_is_stable"] is True
            assert ce["unique_prefix_hashes"] == 1
