"""Step 6: Eight Gates — 门禁引擎测试。

contracts/gates.json 约束验证：
- 8 道门禁 AND 逻辑
- 决策 GO / WARN / FREEZE
- gate_score ∈ [0,1]
- gate_result_schema 字段稳定
"""

import os
import tempfile
import pytest
from src.inner.gates import GateEngine
from src.inner.gates.config import (
    AGENCY_GATE_THRESHOLD,
    EXCURSION_MIN_EVIDENCE,
    GATES_RULE_VERSION,
)
from src.inner.ledger import EventStore


def _ts():
    return "2026-04-29T12:14:00Z"


@pytest.fixture
def engine():
    return GateEngine()


# ═══════════════════════════════════════════════════════════════
# 1) 默认行为：全空输入 → GO
# ═══════════════════════════════════════════════════════════════

class TestDefaultBehavior:
    """无输入时所有门禁默认通过 → GO。"""

    def test_empty_inputs_go(self, engine):
        r = engine.evaluate()
        assert r["decision"] == "GO"
        assert r["gate_score"] == 0.0
        assert r["gates_passed"] == 8
        assert r["gates_total"] == 8

    def test_default_pass_reason(self, engine):
        r = engine.evaluate()
        for g in r["gates"].values():
            assert g["pass"] is True
            assert g["reason"] == "No input provided, default pass"
            assert g["metric_value"] is None
            assert g["threshold"] is None

    def test_all_gate_ids_present(self, engine):
        r = engine.evaluate()
        expected = [
            "1_agency_gate", "2_excursion_gate", "3_learning_gate",
            "4_relational_gate", "5_causal_gate", "6_audit_gate",
            "7_framing_gate", "8_window_gate",
        ]
        assert list(r["gates"].keys()) == expected

    def test_output_keys_stable(self, engine):
        r = engine.evaluate()
        required = {
            "decision", "gate_score", "gates", "gates_passed",
            "gates_total", "reason_code", "evaluated_at_utc", "window_id",
        }
        assert set(r.keys()) == required
        assert isinstance(r["gate_score"], float)
        assert r["evaluated_at_utc"].endswith("Z")
        assert "_" in r["window_id"]


# ═══════════════════════════════════════════════════════════════
# 2) 每道门禁独立评估
# ═══════════════════════════════════════════════════════════════

class TestIndividualGates:
    """每道门禁 pass/fail 逻辑独立验证。"""

    # ── Gate 1: Agency Gate ──

    def test_agency_gate_pass(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.5}})
        g = r["gates"]["1_agency_gate"]
        assert g["pass"] is True
        assert g["metric_value"] == 0.5
        assert g["threshold"] == AGENCY_GATE_THRESHOLD

    def test_agency_gate_fail(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.1}})
        g = r["gates"]["1_agency_gate"]
        assert g["pass"] is False
        assert "0.1" in g["reason"]

    def test_agency_gate_at_threshold(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.3}})
        assert r["gates"]["1_agency_gate"]["pass"] is True

    def test_agency_gate_custom_threshold(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.25, "threshold": 0.5}})
        assert r["gates"]["1_agency_gate"]["pass"] is False

    # ── Gate 2: Excursion Gate ──

    def test_excursion_gate_pass(self, engine):
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": 3}})
        assert r["gates"]["2_excursion_gate"]["pass"] is True

    def test_excursion_gate_fail(self, engine):
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": 0}})
        assert r["gates"]["2_excursion_gate"]["pass"] is False

    def test_excursion_gate_exactly_one(self, engine):
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": 1}})
        assert r["gates"]["2_excursion_gate"]["pass"] is True

    # ── Gate 3: Learning Gate ──

    def test_learning_gate_pass_stable(self, engine):
        r = engine.evaluate({"3_learning_gate": {"recent_no_assist_scores": [0.8, 0.82, 0.81, 0.83]}})
        assert r["gates"]["3_learning_gate"]["pass"] is True

    def test_learning_gate_fail_decline(self, engine):
        r = engine.evaluate({"3_learning_gate": {"recent_no_assist_scores": [0.9, 0.8, 0.7, 0.6]}})
        assert r["gates"]["3_learning_gate"]["pass"] is False

    def test_learning_gate_exactly_max_decline(self, engine):
        """2 consecutive declines → pass (at threshold)."""
        r = engine.evaluate({"3_learning_gate": {"recent_no_assist_scores": [0.8, 0.7, 0.65, 0.7]}})
        assert r["gates"]["3_learning_gate"]["pass"] is True

    def test_learning_gate_one_point_default_pass(self, engine):
        r = engine.evaluate({"3_learning_gate": {"recent_no_assist_scores": [0.8]}})
        assert r["gates"]["3_learning_gate"]["pass"] is True

    def test_learning_gate_empty_list_default_pass(self, engine):
        r = engine.evaluate({"3_learning_gate": {"recent_no_assist_scores": []}})
        assert r["gates"]["3_learning_gate"]["pass"] is True

    # ── Gate 4: Relational Gate ──

    def test_relational_gate_pass(self, engine):
        r = engine.evaluate({
            "4_relational_gate": {
                "passive_agreement_rate": 0.1,
                "rewrite_rate_decline": 0.05,
                "self_judgment_decline": 0.1,
            }
        })
        assert r["gates"]["4_relational_gate"]["pass"] is True

    def test_relational_gate_fail_agreement(self, engine):
        r = engine.evaluate({
            "4_relational_gate": {"passive_agreement_rate": 0.5}
        })
        assert r["gates"]["4_relational_gate"]["pass"] is False

    def test_relational_gate_multi_fail(self, engine):
        r = engine.evaluate({
            "4_relational_gate": {
                "passive_agreement_rate": 0.5,
                "rewrite_rate_decline": 0.4,
                "self_judgment_decline": 0.1,
            }
        })
        assert r["gates"]["4_relational_gate"]["pass"] is False
        assert "passive_agreement_rate" in r["gates"]["4_relational_gate"]["reason"]

    # ── Gate 5: Causal Gate ──

    def test_causal_gate_pass_all_green(self, engine):
        r = engine.evaluate({
            "5_causal_gate": {
                "balance_check_pass": True,
                "negative_control_pass": True,
                "placebo_window_pass": True,
            }
        })
        assert r["gates"]["5_causal_gate"]["pass"] is True

    def test_causal_gate_fail_one_red(self, engine):
        r = engine.evaluate({
            "5_causal_gate": {
                "balance_check_pass": True,
                "negative_control_pass": False,
                "placebo_window_pass": True,
            }
        })
        assert r["gates"]["5_causal_gate"]["pass"] is False
        assert "negative_control_pass" in r["gates"]["5_causal_gate"]["reason"]

    def test_causal_gate_fail_all_red(self, engine):
        r = engine.evaluate({
            "5_causal_gate": {
                "balance_check_pass": False,
                "negative_control_pass": False,
                "placebo_window_pass": False,
            }
        })
        assert r["gates"]["5_causal_gate"]["pass"] is False

    # ── Gate 6: Audit Gate ──

    def test_audit_gate_pass(self, engine):
        r = engine.evaluate({
            "6_audit_gate": {"p0_count": 0, "p1_rate": 0.005}
        })
        assert r["gates"]["6_audit_gate"]["pass"] is True

    def test_audit_gate_fail_p0(self, engine):
        r = engine.evaluate({
            "6_audit_gate": {"p0_count": 1, "p1_rate": 0.0}
        })
        assert r["gates"]["6_audit_gate"]["pass"] is False

    def test_audit_gate_fail_p1_rate(self, engine):
        r = engine.evaluate({
            "6_audit_gate": {"p0_count": 0, "p1_rate": 0.015}
        })
        assert r["gates"]["6_audit_gate"]["pass"] is False

    # ── Gate 7: Framing Gate ──

    def test_framing_gate_pass(self, engine):
        r = engine.evaluate({"7_framing_gate": {"framing_audit_pass": True}})
        assert r["gates"]["7_framing_gate"]["pass"] is True

    def test_framing_gate_fail(self, engine):
        r = engine.evaluate({"7_framing_gate": {"framing_audit_pass": False}})
        assert r["gates"]["7_framing_gate"]["pass"] is False

    # ── Gate 8: Window Gate ──

    def test_window_gate_pass(self, engine):
        r = engine.evaluate({
            "8_window_gate": {"schema_versions": ["1.0.0", "1.0.0", "1.0.0"]}
        })
        assert r["gates"]["8_window_gate"]["pass"] is True

    def test_window_gate_fail(self, engine):
        r = engine.evaluate({
            "8_window_gate": {"schema_versions": ["1.0.0", "2.0.0", "1.0.0"]}
        })
        assert r["gates"]["8_window_gate"]["pass"] is False

    def test_window_gate_one_version_default_pass(self, engine):
        r = engine.evaluate({
            "8_window_gate": {"schema_versions": ["1.0.0"]}
        })
        assert r["gates"]["8_window_gate"]["pass"] is True


# ═══════════════════════════════════════════════════════════════
# 3) 聚合决策：GO / WARN / FREEZE
# ═══════════════════════════════════════════════════════════════

class TestAggregateDecisions:
    """gate_score 聚合逻辑。"""

    def test_go_all_pass(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.5},
            "6_audit_gate": {"p0_count": 0, "p1_rate": 0.005},
            "7_framing_gate": {"framing_audit_pass": True},
        })
        assert r["decision"] == "GO"
        assert r["gate_score"] == 0.0
        assert r["gates_passed"] == 8

    def test_warn_one_fail(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
        })
        assert r["decision"] == "WARN"
        assert r["gate_score"] == 0.125  # 1/8
        assert r["gates_passed"] == 7

    def test_warn_two_fails(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "2_excursion_gate": {"exploration_evidence_count": 0},
        })
        assert r["decision"] == "WARN"
        assert r["gate_score"] == 0.25  # 2/8
        assert r["gates_passed"] == 6

    def test_freeze_three_fails(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "2_excursion_gate": {"exploration_evidence_count": 0},
            "5_causal_gate": {"balance_check_pass": False, "negative_control_pass": False, "placebo_window_pass": False},
        })
        assert r["decision"] == "FREEZE"
        assert r["gate_score"] == 0.375  # 3/8
        assert r["gates_passed"] == 5

    def test_freeze_all_fail(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.0},
            "2_excursion_gate": {"exploration_evidence_count": 0},
            "4_relational_gate": {"passive_agreement_rate": 0.9},
            "5_causal_gate": {"balance_check_pass": False, "negative_control_pass": False, "placebo_window_pass": False},
            "6_audit_gate": {"p0_count": 3, "p1_rate": 0.05},
            "7_framing_gate": {"framing_audit_pass": False},
            "8_window_gate": {"schema_versions": ["1.0.0", "2.0.0"]},
        })
        assert r["decision"] == "FREEZE"
        assert r["gate_score"] >= 0.75  # 6+ 门禁失败
        assert r["gates_passed"] <= 1

    def test_score_bounds(self, engine):
        """gate_score 范围始终在 [0,1]。"""
        r = engine.evaluate()
        assert 0.0 <= r["gate_score"] <= 1.0

        r2 = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.0},
            "2_excursion_gate": {"exploration_evidence_count": 0},
            "3_learning_gate": {"recent_no_assist_scores": [0.9, 0.8, 0.7, 0.6]},
            "4_relational_gate": {"passive_agreement_rate": 0.9},
            "5_causal_gate": {"balance_check_pass": False, "negative_control_pass": False, "placebo_window_pass": False},
            "6_audit_gate": {"p0_count": 3, "p1_rate": 0.05},
            "7_framing_gate": {"framing_audit_pass": False},
            "8_window_gate": {"schema_versions": ["1.0.0", "2.0.0"]},
        })
        assert 0.0 <= r2["gate_score"] <= 1.0


# ═══════════════════════════════════════════════════════════════
# 4) reason_code 格式
# ═══════════════════════════════════════════════════════════════

class TestReasonCode:
    """reason_code: GATES_<DECISION>_<VERSION>_sXX。"""

    def test_reason_code_go(self, engine):
        r = engine.evaluate()
        assert r["reason_code"] == f"GATES_GO_{GATES_RULE_VERSION}_s00"

    def test_reason_code_warn(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.1}})
        assert r["reason_code"].startswith("GATES_WARN_")
        assert GATES_RULE_VERSION in r["reason_code"]
        assert "_s12" in r["reason_code"]  # 1/8 = 0.125 → s12

    def test_reason_code_freeze(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "2_excursion_gate": {"exploration_evidence_count": 0},
            "5_causal_gate": {"balance_check_pass": False, "negative_control_pass": False, "placebo_window_pass": False},
        })
        assert r["reason_code"].startswith("GATES_FREEZE_")
        assert "_s37" in r["reason_code"]  # 3/8 = 0.375 → s37


# ═══════════════════════════════════════════════════════════════
# 5) 审计字段映射
# ═══════════════════════════════════════════════════════════════

class TestAuditMapping:
    """to_audit_fields 结构合法 + 值域正确。"""

    def test_audit_fields_go(self, engine):
        r = engine.evaluate()
        af = engine.to_audit_fields(r)
        assert af["gate_decision"] == "GO"
        assert af["gate_score"] == 0.0
        assert af["gates_passed"] == 8
        assert af["gates_failed"] == 0
        assert af["gate_reason_code"] == r["reason_code"]
        assert af["gate_rule_version"] == GATES_RULE_VERSION

    def test_audit_fields_freeze(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "2_excursion_gate": {"exploration_evidence_count": 0},
            "5_causal_gate": {"balance_check_pass": False, "negative_control_pass": False, "placebo_window_pass": False},
        })
        af = engine.to_audit_fields(r)
        assert af["gate_decision"] == "FREEZE"
        assert af["gates_failed"] == 3
        assert af["gates_passed"] == 5

    def test_audit_fields_structure(self, engine):
        r = engine.evaluate()
        af = engine.to_audit_fields(r)
        expected = {
            "gate_decision", "gate_score", "gates_passed",
            "gates_failed", "gate_reason_code", "gate_rule_version",
        }
        assert set(af.keys()) == expected


# ═══════════════════════════════════════════════════════════════
# 6) 时间与窗口一致性
# ═══════════════════════════════════════════════════════════════

class TestTimeAndWindow:
    """event_time_utc 与 window_id 自动推导及一致性。"""

    def test_custom_event_time(self, engine):
        r = engine.evaluate(event_time_utc="2026-04-29T14:22:00Z")
        assert r["evaluated_at_utc"].endswith("Z")
        assert "2026-04-29T14:00" in r["window_id"]  # 22min → [14:00, 14:30)

    def test_custom_window_id(self, engine):
        r = engine.evaluate(
            event_time_utc="2026-04-29T14:22:00Z",
            window_id="2026-04-29T14:00_2026-04-29T14:30",
        )
        assert r["window_id"] == "2026-04-29T14:00_2026-04-29T14:30"

    def test_per_gate_window_id(self, engine):
        r = engine.evaluate(window_id="2026-04-29T14:00_2026-04-29T14:30")
        for g in r["gates"].values():
            assert g["window_id"] == "2026-04-29T14:00_2026-04-29T14:30"


# ═══════════════════════════════════════════════════════════════
# 7) gate_result_schema 字段一致性
# ═══════════════════════════════════════════════════════════════

class TestGateResultSchema:
    """每道门禁输出符合 gate_result_schema 合约。"""

    def test_gate_result_keys(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.5}})
        g = r["gates"]["1_agency_gate"]
        expected = {
            "gate_id", "gate_name", "pass", "metric_value",
            "threshold", "reason", "evaluated_at_utc", "window_id",
        }
        assert set(g.keys()) == expected
        assert g["gate_id"] == "1_agency_gate"
        assert isinstance(g["pass"], bool)
        assert isinstance(g["reason"], str)

    def test_gate_result_types(self, engine):
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.5},
            "2_excursion_gate": {"exploration_evidence_count": 0},
        })
        for gid, g in r["gates"].items():
            assert isinstance(g["gate_id"], str)
            assert isinstance(g["gate_name"], str)
            assert isinstance(g["pass"], bool)
            assert isinstance(g["reason"], str)
            assert g["evaluated_at_utc"].endswith("Z")
            assert "_" in g["window_id"]


# ═══════════════════════════════════════════════════════════════
# 8) 集成冒烟：GateEngine + Ledger
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """Gate 输出可经 Ledger append_event 写入链。"""

    def test_gate_result_to_ledger(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        s.create_genesis_event()

        engine = GateEngine()
        r = engine.evaluate()
        af = engine.to_audit_fields(r)

        e = s.append_event(
            p0_values={
                "trace_id": "gate_int_test",
                "policy_version": "1.0",
                "counterfactual_ranker_version": "1.0",
                "counterfactual_feature_schema_version": "1.0",
            },
            p1_values={
                "tradeoff_reason": af["gate_reason_code"],
                "degradation_path": af["gate_decision"],
                "meta_conflict_score": af["gate_score"],
            },
        )
        assert e["chain_height"] == 1
        assert e["tradeoff_reason"] == r["reason_code"]
        assert e["degradation_path"] == "GO"
        assert e["meta_conflict_score"] == 0.0

        try:
            os.unlink(path)
        except PermissionError:
            import time
            time.sleep(0.1)
            os.unlink(path)

    def test_gate_write_freeze_to_ledger(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        s.create_genesis_event()

        engine = GateEngine()
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "7_framing_gate": {"framing_audit_pass": False},
        })
        af = engine.to_audit_fields(r)
        assert af["gate_decision"] == "WARN"

        e = s.append_event(
            p0_values={
                "trace_id": "gate_warn_test",
                "policy_version": "1.0",
                "counterfactual_ranker_version": "1.0",
                "counterfactual_feature_schema_version": "1.0",
            },
            p1_values={
                "tradeoff_reason": af["gate_reason_code"],
                "degradation_path": af["gate_decision"],
                "meta_conflict_score": af["gate_score"],
            },
        )
        assert e["chain_height"] == 1
        assert e["degradation_path"] == "WARN"

        try:
            os.unlink(path)
        except PermissionError:
            import time
            time.sleep(0.1)
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════
# 9) context 参数扩展测试
# ═══════════════════════════════════════════════════════════════

class TestContextParameter:
    """context 参数传空或非 None 不影响结果。"""

    def test_context_none(self, engine):
        r1 = engine.evaluate()
        r2 = engine.evaluate(context=None)
        assert r1["decision"] == r2["decision"]
        assert r1["gates_passed"] == r2["gates_passed"]

    def test_context_with_data(self, engine):
        r = engine.evaluate(context={"extra": "data"})
        assert r["decision"] == "GO"


# ═══════════════════════════════════════════════════════════════
# 10) 回归：其他模块未受影响
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 10) 对抗性测试：类型兼容性
# ═══════════════════════════════════════════════════════════════

class TestAdversarialTypeRobustness:
    """门禁应接受合理的类型变体（float 而非 strict int）。"""

    def test_gate2_float_count_passes(self, engine):
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": 3.0}})
        assert r["gates"]["2_excursion_gate"]["pass"] is True

    def test_gate2_float_count_zero_fails(self, engine):
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": 0.0}})
        assert r["gates"]["2_excursion_gate"]["pass"] is False

    def test_gate6_float_p0_count_zero_passes(self, engine):
        r = engine.evaluate({"6_audit_gate": {"p0_count": 0.0, "p1_rate": 0.005}})
        assert r["gates"]["6_audit_gate"]["pass"] is True

    def test_gate6_float_p0_count_positive_fails(self, engine):
        r = engine.evaluate({"6_audit_gate": {"p0_count": 1.0, "p1_rate": 0.005}})
        assert r["gates"]["6_audit_gate"]["pass"] is False

    def test_gate7_int_1_passes(self, engine):
        r = engine.evaluate({"7_framing_gate": {"framing_audit_pass": 1}})
        assert r["gates"]["7_framing_gate"]["pass"] is True

    def test_gate7_int_0_fails(self, engine):
        r = engine.evaluate({"7_framing_gate": {"framing_audit_pass": 0}})
        assert r["gates"]["7_framing_gate"]["pass"] is False

    def test_gate3_equal_scores_zero_decline(self, engine):
        r = engine.evaluate({"3_learning_gate": {"recent_no_assist_scores": [0.8, 0.8, 0.8]}})
        assert r["gates"]["3_learning_gate"]["pass"] is True

    def test_gate3_alternating_no_decline(self, engine):
        """0.9→0.8→0.9→0.8→0.9: max consecutive=1."""
        r = engine.evaluate({
            "3_learning_gate": {"recent_no_assist_scores": [0.9, 0.8, 0.9, 0.8, 0.9]}
        })
        assert r["gates"]["3_learning_gate"]["pass"] is True

    def test_gate3_custom_threshold_3_with_3_declines(self, engine):
        r = engine.evaluate({
            "3_learning_gate": {
                "recent_no_assist_scores": [0.9, 0.8, 0.7, 0.6],
                "max_consecutive_decline": 3,
            }
        })
        assert r["gates"]["3_learning_gate"]["pass"] is True

    def test_gate4_exactly_at_threshold_passes(self, engine):
        """阈值边界：0.3 > 0.3 为 False → pass."""
        r = engine.evaluate({
            "4_relational_gate": {"passive_agreement_rate": 0.3}
        })
        assert r["gates"]["4_relational_gate"]["pass"] is True

    def test_gate6_p1_rate_at_warn_threshold(self, engine):
        """p1_rate=0.01: 0.01 >= 0.01 → fail."""
        r = engine.evaluate({"6_audit_gate": {"p0_count": 0, "p1_rate": 0.01}})
        assert r["gates"]["6_audit_gate"]["pass"] is False

    def test_gate6_p1_rate_just_below_threshold(self, engine):
        r = engine.evaluate({"6_audit_gate": {"p0_count": 0, "p1_rate": 0.009}})
        assert r["gates"]["6_audit_gate"]["pass"] is True

    def test_gate1_negative_rate_fails(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": -0.1}})
        assert r["gates"]["1_agency_gate"]["pass"] is False

    def test_gate8_string_versions_default_pass(self, engine):
        r = engine.evaluate({"8_window_gate": {"schema_versions": "1.0.0"}})
        assert r["gates"]["8_window_gate"]["pass"] is True


# ═══════════════════════════════════════════════════════════════
# 11) 对抗性测试：数值边界
# ═══════════════════════════════════════════════════════════════

class TestAdversarialNumericalBoundaries:
    """极端数值不应导致崩溃或越界。"""

    def test_gate1_rate_zero(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.0}})
        assert r["gates"]["1_agency_gate"]["pass"] is False

    def test_gate1_rate_one(self, engine):
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 1.0}})
        assert r["gates"]["1_agency_gate"]["pass"] is True

    def test_gate1_rate_very_large(self, engine):
        """超大值通过（视为高于阈值）。"""
        r = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 100.0}})
        assert r["gates"]["1_agency_gate"]["pass"] is True

    def test_gate2_very_large_count(self, engine):
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": 999}})
        assert r["gates"]["2_excursion_gate"]["pass"] is True

    def test_gate2_negative_count_fails(self, engine):
        """负数作为证据数未达到阈值。"""
        r = engine.evaluate({"2_excursion_gate": {"exploration_evidence_count": -5}})
        assert r["gates"]["2_excursion_gate"]["pass"] is False

    def test_gate6_p1_rate_negative(self, engine):
        """负数 p1_rate >= 0.01 为 False → pass."""
        r = engine.evaluate({"6_audit_gate": {"p0_count": 0, "p1_rate": -0.1}})
        assert r["gates"]["6_audit_gate"]["pass"] is True

    def test_gate6_p1_rate_one(self, engine):
        """100% 缺失率应触发失败。"""
        r = engine.evaluate({"6_audit_gate": {"p0_count": 0, "p1_rate": 1.0}})
        assert r["gates"]["6_audit_gate"]["pass"] is False

    def test_gate8_empty_list_default_pass(self, engine):
        r = engine.evaluate({"8_window_gate": {"schema_versions": []}})
        assert r["gates"]["8_window_gate"]["pass"] is True

    def test_gate8_none_versions_default_pass(self, engine):
        r = engine.evaluate({"8_window_gate": {"schema_versions": None}})
        assert r["gates"]["8_window_gate"]["pass"] is True

    def test_gate4_all_signals_zero(self, engine):
        r = engine.evaluate({
            "4_relational_gate": {
                "passive_agreement_rate": 0.0,
                "rewrite_rate_decline": 0.0,
                "self_judgment_decline": 0.0,
            }
        })
        assert r["gates"]["4_relational_gate"]["pass"] is True

    def test_gate4_all_signals_one(self, engine):
        """最高值全触发。"""
        r = engine.evaluate({
            "4_relational_gate": {
                "passive_agreement_rate": 1.0,
                "rewrite_rate_decline": 1.0,
                "self_judgment_decline": 1.0,
            }
        })
        assert r["gates"]["4_relational_gate"]["pass"] is False

    def test_decision_exact_boundary(self, engine):
        """2/8 = 0.25 → WARN (is <= 0.25)."""
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "2_excursion_gate": {"exploration_evidence_count": 0},
        })
        assert r["decision"] == "WARN"
        assert r["gate_score"] == 0.25

    def test_decision_just_over_boundary(self, engine):
        """3/8 = 0.375 → FREEZE (> 0.25)."""
        r = engine.evaluate({
            "1_agency_gate": {"premise_rewrite_rate": 0.1},
            "2_excursion_gate": {"exploration_evidence_count": 0},
            "5_causal_gate": {"balance_check_pass": False, "negative_control_pass": True, "placebo_window_pass": True},
        })
        assert r["decision"] == "FREEZE"
        assert r["gate_score"] == 0.375


# ═══════════════════════════════════════════════════════════════
# 12) 幂等性与无状态性
# ═══════════════════════════════════════════════════════════════

class TestIdempotency:
    """GateEngine 应为无状态：多次调用互不影响。"""

    def test_repeated_calls_same_result(self, engine):
        r1 = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.5}})
        r2 = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.5}})
        assert r1["decision"] == r2["decision"]
        assert r1["gates"]["1_agency_gate"]["pass"] == r2["gates"]["1_agency_gate"]["pass"]

    def test_independent_calls_no_crosstalk(self, engine):
        r1 = engine.evaluate({"1_agency_gate": {"premise_rewrite_rate": 0.1}})
        r2 = engine.evaluate({})
        assert r1["decision"] != r2["decision"]
        assert r2["decision"] == "GO"


# ═══════════════════════════════════════════════════════════════
# 13) 交叉验证：批量随机加压
# ═══════════════════════════════════════════════════════════════

class TestBatchStress:
    """大量组合调用验证稳定性。"""

    def test_all_256_pass_fail_combinations(self):
        """2^8 = 256 组 pass/fail 组合验证聚合逻辑不崩溃。"""
        import itertools

        engine = GateEngine()
        gate_ids = [
            "1_agency_gate", "2_excursion_gate", "3_learning_gate",
            "4_relational_gate", "5_causal_gate", "6_audit_gate",
            "7_framing_gate", "8_window_gate",
        ]
        pass_fail_pairs = [
            [{"premise_rewrite_rate": 0.5}, {"premise_rewrite_rate": 0.0}],
            [{"exploration_evidence_count": 3}, {"exploration_evidence_count": 0}],
            [{"recent_no_assist_scores": [0.8, 0.82]}, {"recent_no_assist_scores": [0.9, 0.8, 0.7]}],
            [{"passive_agreement_rate": 0.1}, {"passive_agreement_rate": 0.9}],
            [{"balance_check_pass": True, "negative_control_pass": True, "placebo_window_pass": True},
             {"balance_check_pass": False, "negative_control_pass": False, "placebo_window_pass": False}],
            [{"p0_count": 0, "p1_rate": 0.005}, {"p0_count": 1, "p1_rate": 0.05}],
            [{"framing_audit_pass": True}, {"framing_audit_pass": False}],
            [{"schema_versions": ["1.0.0", "1.0.0"]}, {"schema_versions": ["1.0.0", "2.0.0"]}],
        ]

        count = 0
        for choices in itertools.product(*pass_fail_pairs):
            gate_inputs = {}
            for gid, choice in zip(gate_ids, choices):
                gate_inputs[gid] = choice
            r = engine.evaluate(gate_inputs)
            assert 0.0 <= r["gate_score"] <= 1.0
            assert r["decision"] in ("GO", "WARN", "FREEZE")
            assert r["gates_passed"] + (8 - r["gates_passed"]) == 8
            count += 1

        assert count == 256


class TestRegression:
    """已有模块正常工作。"""

    def test_ledger_still_works(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        e = s.create_genesis_event()
        assert e["chain_height"] == 0
        try:
            os.unlink(path)
        except PermissionError:
            import time
            time.sleep(0.1)
            os.unlink(path)
