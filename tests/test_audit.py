"""Step 2 审计测试 — 合约对齐版。
覆盖: P0_BLOCK / P1_WARN / P1_FREEZE / PASS、批量统计、阈值分支、
       空边界、Step1 集成、合约字段完整性。
"""

import os
import tempfile
import pytest
from src.inner.audit import (
    AuditClassifier,
    P0_FIELDS,
    P1_FIELDS,
    compute_batch_stats,
    generate_audit_report,
)
from src.inner.ledger import EventStore


# ── helpers ─────────────────────────────────────────────────────

def _p0_full(trace_id="t1", policy_version="1.0",
             crv="1.0", cfsv="1.0"):
    return {
        "trace_id": trace_id,
        "policy_version": policy_version,
        "counterfactual_ranker_version": crv,
        "counterfactual_feature_schema_version": cfsv,
    }


def _p1_all_filled():
    """全部 12 个 P1 字段非 None。"""
    return {
        "objective_weights_snapshot": "{}",
        "tradeoff_reason": "test",
        "protected_metric_guardrail_hit": 0,
        "used_fact_ids": "[]",
        "ignored_fact_ids_with_reason": "[]",
        "degradation_path": "none",
        "counterfactual_policy_rank": 1,
        "assignment_features": "{}",
        "eligibility_rule_id": "rule_1",
        "meta_conflict_score": 0.0,
        "track_disagreement_level": 0.0,
        "meta_conflict_alert_flag": 0,
    }


def _make_event(**overrides):
    """构造一条 P0 齐全、P1 全 NULL 的模拟事件。"""
    event = {
        "id": 1,
        "trace_id": "trace-1",
        "policy_version": "1.0",
        "counterfactual_ranker_version": "1.0",
        "counterfactual_feature_schema_version": "1.0",
        "event_time_utc": "2026-04-29T12:00:00.000Z",
        "window_id": "2026-04-29T12:00_2026-04-29T12:30",
        "window_schema_version": "1.0.0",
    }
    event.update(overrides)
    for f in P1_FIELDS:
        if f not in event:
            event[f] = None
    return event


@pytest.fixture
def classifier():
    return AuditClassifier()


# ═══════════════════════════════════════════════════════════════
# 1) 缺任一 P0 → audit_level = "p0_block"
# ═══════════════════════════════════════════════════════════════

class TestP0Block:
    """P0 缺失 → p0_block（合约枚举）。"""

    def test_missing_trace_id_yields_p0_block(self, classifier):
        event = _make_event(trace_id="")
        r = classifier.classify(event)
        assert r["p0_pass"] is False
        assert "trace_id" in r["missing_p0_fields"]

    def test_missing_policy_version(self, classifier):
        r = classifier.classify(_make_event(policy_version=""))
        assert "policy_version" in r["missing_p0_fields"]

    def test_missing_crv(self, classifier):
        r = classifier.classify(_make_event(counterfactual_ranker_version=""))
        assert "counterfactual_ranker_version" in r["missing_p0_fields"]

    def test_missing_cfsv(self, classifier):
        r = classifier.classify(_make_event(counterfactual_feature_schema_version=""))
        assert "counterfactual_feature_schema_version" in r["missing_p0_fields"]

    def test_multiple_p0_missing(self, classifier):
        r = classifier.classify(_make_event(trace_id="", policy_version=""))
        assert r["p0_pass"] is False
        assert len(r["missing_p0_fields"]) == 2

    def test_none_trace_id(self, classifier):
        r = classifier.classify(_make_event(trace_id=None))
        assert r["p0_pass"] is False

    def test_report_level_is_p0_block(self):
        events = [_make_event(trace_id=""), _make_event(**_p1_all_filled())]
        report = generate_audit_report(events)
        assert report["per_event"][0]["audit_level"] == "p0_block"
        assert report["per_event"][1]["audit_level"] == "pass"


# ═══════════════════════════════════════════════════════════════
# 2) 仅缺 P1 → 由批量阈值决定 p1_warn / p1_freeze / pass
# ═══════════════════════════════════════════════════════════════

class TestP1Levels:
    """P1 缺失 + 批量阈值 → 合约 audit_level。"""

    def test_single_p1_missing_flagged(self, classifier):
        filled = _p1_all_filled()
        del filled["tradeoff_reason"]
        r = classifier.classify(_make_event(**filled))
        assert r["has_p1_issue"] is True
        assert "tradeoff_reason" in r["missing_p1_fields"]

    def test_report_p1_warn_at_high_rate(self):
        """2 events: genesis (P1 all null) + 1 filled (PASS). P1 rate = 1/2 > 30% → p1_freeze"""
        events = [
            _make_event(),                          # P1 all null → has_p1_issue
            _make_event(**_p1_all_filled()),        # PASS
        ]
        report = generate_audit_report(events)
        # P1 rate = 1/2 = 0.5 > 3% → batch level = p1_freeze
        assert report["per_event"][0]["audit_level"] == "p1_freeze"

    def test_report_pass_at_low_rate(self):
        """99 filled + 1 with P1 issue → P1 rate = 1% → not > warn → pass"""
        events = [_make_event(**_p1_all_filled()) for _ in range(99)]
        events.append(_make_event())  # this one has P1 nulls
        report = generate_audit_report(events)
        assert report["per_event"][-1]["audit_level"] == "pass"

    def test_p1_issue_has_empty_p0_list(self, classifier):
        r = classifier.classify(_make_event())
        assert r["p0_pass"] is True
        assert r["missing_p0_fields"] == []


# ═══════════════════════════════════════════════════════════════
# 3) P0/P1 都齐全 → pass
# ═══════════════════════════════════════════════════════════════

class TestPass:
    """全部字段齐全 → audit_level = pass。"""

    def test_all_fields_pass(self, classifier):
        r = classifier.classify(_make_event(**_p1_all_filled()))
        assert r["p0_pass"] is True
        assert r["has_p1_issue"] is False
        assert r["missing_p0_fields"] == []
        assert r["missing_p1_fields"] == []

    def test_report_level_is_pass(self):
        events = [_make_event(**_p1_all_filled()) for _ in range(5)]
        report = generate_audit_report(events)
        for pe in report["per_event"]:
            assert pe["audit_level"] == "pass"

    def test_batch_classify(self, classifier):
        events = [_make_event(**_p1_all_filled()) for _ in range(3)]
        results = classifier.classify_batch(events)
        assert all(r["p0_pass"] for r in results)
        assert all(not r["has_p1_issue"] for r in results)


# ═══════════════════════════════════════════════════════════════
# 4) 批量统计正确（合约口径：any P1 null / total）
# ═══════════════════════════════════════════════════════════════

class TestBatchStats:
    """compute_batch_stats 合约口径。"""

    def test_empty_list(self):
        s = compute_batch_stats([])
        assert s["total_events"] == 0
        assert s["p0_incident_count"] == 0
        assert s["p1_incident_count"] == 0
        assert s["p1_rate_ratio"] == 0.0

    def test_mixed_events(self):
        events = [
            _make_event(**_p1_all_filled()),           # 0: no P1 null
            _make_event(trace_id=""),                   # 1: P0 block, P1 all null
            _make_event(),                              # 2: P1 all null
            _make_event(**_p1_all_filled()),           # 3: no P1 null
            _make_event(tradeoff_reason="ok"),          # 4: some P1 still null
            _make_event(policy_version=""),             # 5: P0 block, P1 all null
        ]
        s = compute_batch_stats(events)
        assert s["total_events"] == 6
        assert s["p0_incident_count"] == 2
        # any P1 null: indices 1,2,4,5 → 4 events
        assert s["p1_incident_count"] == 4
        assert abs(s["p1_rate_ratio"] - 4 / 6) < 0.001

    def test_all_pass(self):
        events = [_make_event(**_p1_all_filled()) for _ in range(10)]
        s = compute_batch_stats(events)
        assert s["p0_incident_count"] == 0
        assert s["p1_incident_count"] == 0
        assert s["p1_rate_ratio"] == 0.0

    def test_rate_uses_any_null_not_level_counting(self):
        """验证 P1 率使用显式 any-null 逻辑，而非间接计数。"""
        events = [
            _make_event(tradeoff_reason="ok"),  # has_p1_issue=True (11 null fields)
            _make_event(tradeoff_reason="ok"),  # same
        ]
        s = compute_batch_stats(events)
        # 两个事件都有 any P1 null → p1_incident_count = 2
        assert s["p1_incident_count"] == 2
        assert s["p1_rate_ratio"] == 1.0


# ═══════════════════════════════════════════════════════════════
# 5) 阈值分支：1% / 3% 边界精确
# ═══════════════════════════════════════════════════════════════

class TestThresholdBranches:
    """evaluate_threshold 返回合约枚举。"""

    def test_zero_is_pass(self, classifier):
        assert classifier.evaluate_threshold(0.0) == "pass"

    def test_one_percent_is_pass(self, classifier):
        # 1% 不触发（严格大于 1%）
        assert classifier.evaluate_threshold(0.01) == "pass"

    def test_just_above_warn(self, classifier):
        assert classifier.evaluate_threshold(0.01001) == "p1_warn"

    def test_below_freeze(self, classifier):
        assert classifier.evaluate_threshold(0.025) == "p1_warn"

    def test_three_percent_is_warn(self, classifier):
        # 3% 不触发 freeze（严格大于 3%）
        assert classifier.evaluate_threshold(0.03) == "p1_warn"

    def test_just_above_freeze(self, classifier):
        assert classifier.evaluate_threshold(0.03001) == "p1_freeze"

    def test_far_above_freeze(self, classifier):
        assert classifier.evaluate_threshold(0.50) == "p1_freeze"

    def test_custom_thresholds(self):
        c = AuditClassifier(warn_threshold=0.05, freeze_threshold=0.10)
        assert c.evaluate_threshold(0.04) == "pass"
        assert c.evaluate_threshold(0.06) == "p1_warn"
        assert c.evaluate_threshold(0.11) == "p1_freeze"


# ═══════════════════════════════════════════════════════════════
# 6) 空输入边界
# ═══════════════════════════════════════════════════════════════

class TestEmptyInput:
    """空列表各函数行为。"""

    def test_classify_batch_empty(self, classifier):
        assert classifier.classify_batch([]) == []

    def test_compute_batch_stats_empty(self):
        s = compute_batch_stats([])
        assert s["total_events"] == 0

    def test_generate_report_empty(self):
        report = generate_audit_report([])
        assert report["batch_stats"]["total_events"] == 0
        assert report["per_event"] == []


# ═══════════════════════════════════════════════════════════════
# 7) Step 1 EventStore 集成 + 合约字段完整性
# ═══════════════════════════════════════════════════════════════

REQUIRED_CONTRACT_FIELDS = {
    "audit_id", "event_id", "p0_pass", "p0_missing_fields",
    "p1_null_fields", "p1_null_rate_window", "audit_time_utc",
    "window_id", "audit_level",
}

VALID_AUDIT_LEVELS = {"pass", "p1_warn", "p1_freeze", "p0_block"}


class TestLedgerIntegration:
    """与 EventStore 集成 + 合约字段校验。"""

    @pytest.fixture
    def store(self):
        fd, path = tempfile.mkstemp(suffix=".db", prefix="coherence_int_")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        yield s
        try:
            os.unlink(path)
        except PermissionError:
            import time
            time.sleep(0.1)
            os.unlink(path)

    def test_genesis_classifies_p1_issue(self, store):
        store.create_genesis_event()
        event = store.get_latest_event()
        r = AuditClassifier().classify(event)
        assert r["p0_pass"] is True
        assert r["has_p1_issue"] is True

    def test_filled_event_classifies_pass(self, store):
        store.create_genesis_event()
        store.append_event(_p0_full("t1"), p1_values=_p1_all_filled())
        event = store.get_latest_event()
        r = AuditClassifier().classify(event)
        assert r["p0_pass"] is True
        assert r["has_p1_issue"] is False

    def test_report_has_all_contract_fields(self, store):
        """generate_audit_report 每条 per_event 包含全部合约字段。"""
        store.create_genesis_event()
        store.append_event(_p0_full("t1"), p1_values=_p1_all_filled())
        events = store.get_events_in_window(
            store.get_latest_event()["window_id"]
        )
        report = generate_audit_report(events)
        assert len(report["per_event"]) == 2

        for pe in report["per_event"]:
            assert set(pe.keys()) == REQUIRED_CONTRACT_FIELDS, \
                f"Missing: {REQUIRED_CONTRACT_FIELDS - set(pe.keys())}"
            assert pe["audit_level"] in VALID_AUDIT_LEVELS
            assert isinstance(pe["audit_id"], str) and len(pe["audit_id"]) == 36
            assert isinstance(pe["p0_pass"], bool)
            assert isinstance(pe["p0_missing_fields"], list)
            assert isinstance(pe["p1_null_fields"], list)
            assert isinstance(pe["p1_null_rate_window"], float)
            assert pe["audit_time_utc"].endswith("Z")
            assert isinstance(pe["window_id"], str) and len(pe["window_id"]) > 0

    def test_integration_full_report_audit_levels(self, store):
        """集成测试：合约 audit_level 判定正确。"""
        store.create_genesis_event()
        store.append_event(_p0_full("t1"), p1_values=_p1_all_filled())
        store.append_event(_p0_full("t2"))
        store.append_event(_p0_full("t3"), p1_values=_p1_all_filled())

        events = store.get_events_in_window(
            store.get_latest_event()["window_id"]
        )
        report = generate_audit_report(events)

        # genesis: P1 all null + batch P1 rate = 2/4 = 50% > 3% → p1_freeze
        assert report["per_event"][0]["audit_level"] == "p1_freeze"
        # t1: PASS
        assert report["per_event"][1]["audit_level"] == "pass"
        # t2: P1 all null + batch = p1_freeze
        assert report["per_event"][2]["audit_level"] == "p1_freeze"
        # t3: PASS
        assert report["per_event"][3]["audit_level"] == "pass"

        # batch stats
        assert report["batch_stats"]["total_events"] == 4
        assert report["batch_stats"]["p0_incident_count"] == 0
        assert report["batch_stats"]["p1_incident_count"] == 2
