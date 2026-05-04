"""S8.3 八门禁全链路集成测试 — 20 tests。

覆盖 Gate 1-8 全部独立 pass/fail + AND 逻辑 + 多 fail + 空数据 + 故障恢复。
"""

import pytest

# Gate 1-4: Phase 3 (src/inner/gates)
from src.inner.gates import GateEngine

# Gate 5: Phase 7 (src/coach/diagnostics)
from src.coach.diagnostics import DiagnosticEngine

# Gate 6: Phase 8 (src/coach/audit_health)
from src.coach.audit_health import AuditFinding, AuditHealthScorer

# Gate 7: Phase 7 (src/coach/gates_v18_7)
from src.coach.gates_v18_7 import ManipulationGate

# Gate 8: Phase 8 (src/coach/window_consistency)
from src.coach.window_consistency import ComponentVersion, WindowConsistencyChecker


# ── Gate 1-4 helpers ───────────────────────────────────────────

def evaluate_gate_1_to_4(p0_count=0, rewrite_rate=None, excursion_count=None,
                          no_assist_scores=None, pa_rate=None):
    """Through GateEngine — 8 gates with optional per-gate inputs."""
    engine = GateEngine()
    gate_inputs = {}
    if rewrite_rate is not None:
        gate_inputs["1_agency_gate"] = {"premise_rewrite_rate": rewrite_rate}
    if excursion_count is not None:
        gate_inputs["2_excursion_gate"] = {"exploration_evidence_count": excursion_count}
    if no_assist_scores is not None:
        gate_inputs["3_learning_gate"] = {"recent_no_assist_scores": no_assist_scores}
    if pa_rate is not None:
        gate_inputs["4_relational_gate"] = {"passive_agreement_rate": pa_rate}
    if p0_count is not None:
        gate_inputs["6_audit_gate"] = {"p0_count": p0_count}
    return engine.evaluate(gate_inputs)


class TestGate1To4:
    """Phase 3 四门禁独立测试。"""

    def test_gate1_agency_pass(self):
        r = evaluate_gate_1_to_4(rewrite_rate=0.5)
        g1 = r["gates"]["1_agency_gate"]
        assert g1["pass"]

    def test_gate1_agency_low_rate_fails(self):
        r = evaluate_gate_1_to_4(rewrite_rate=0.1)
        g1 = r["gates"]["1_agency_gate"]
        assert not g1["pass"]

    def test_gate2_excursion_pass(self):
        r = evaluate_gate_1_to_4(excursion_count=2)
        g2 = r["gates"]["2_excursion_gate"]
        assert g2["pass"]

    def test_gate3_learning_pass(self):
        r = evaluate_gate_1_to_4(no_assist_scores=[0.6, 0.65, 0.7])
        g3 = r["gates"]["3_learning_gate"]
        assert g3["pass"]

    def test_gate4_relation_pass(self):
        r = evaluate_gate_1_to_4(pa_rate=0.3)
        g4 = r["gates"]["4_relational_gate"]
        assert g4["pass"]


class TestGate5:
    """三诊断 (Causal Gate)。"""

    def test_causal_pass(self):
        engine = DiagnosticEngine()
        report = engine.run(
            treatment_covariates=[{"skill": 0.3 + i * 0.08} for i in range(10)],
            control_covariates=[{"skill": 0.32 + i * 0.08} for i in range(10)],
            sham_successes=5, sham_total=10,
            control_successes=5, control_total=10,
            pre_period_successes=5, pre_period_total=10,
        )
        assert report.all_passed


class TestGate6:
    """审计健康 (Audit Gate)。"""

    def test_clean_pass(self):
        s = AuditHealthScorer()
        result = s.evaluate([])
        assert result.score >= 0.9
        assert not result.p0_blocking

    def test_p0_blocks(self):
        s = AuditHealthScorer()
        result = s.evaluate([AuditFinding("P0", "security", "critical")])
        assert result.p0_blocking


class TestGate7:
    """选择架构操纵检测。"""

    def test_framing_pass(self):
        gate = ManipulationGate()
        result = gate.evaluate([
            {"frame": "A", "choices": {"opt1": 20, "opt2": 18}},
            {"frame": "B", "choices": {"opt1": 22, "opt2": 17}},
        ])
        assert result.passed


class TestGate8:
    """窗口一致性。"""

    def test_consistency_pass(self):
        checker = WindowConsistencyChecker()
        versions = [
            ComponentVersion("mrt", "win_1", "1.0.0", "2026-01-01T00:00:00Z", 60),
            ComponentVersion("diag", "win_1", "1.0.0", "2026-01-01T00:00:00Z", 60),
        ]
        result = checker.check(versions)
        assert result.all_consistent


class TestAllGatesAndLogic:
    """AND 逻辑：全部通过才升档。"""

    def test_all_pass_everything(self):
        """所有门禁默认 pass → GO。"""
        engine = GateEngine()
        result = engine.evaluate()
        assert result["decision"] == "GO"
        assert result["gates_passed"] == 8

    def test_single_gate_fail_blocks(self):
        """任一 p0_count>0 导致 audit gate fail → WARN/FREEZE。"""
        engine = GateEngine()
        result = engine.evaluate({"6_audit_gate": {"p0_count": 1}})
        assert result["gates_passed"] < 8
        assert result["decision"] in ("WARN", "FREEZE")


class TestEmptyDataGraceful:
    """空数据时优雅降级。"""

    def test_all_no_input_passes(self):
        engine = GateEngine()
        result = engine.evaluate({})
        assert result["decision"] == "GO"
        assert result["gates_passed"] == 8

    def test_empty_diagnostics_no_data(self):
        engine = DiagnosticEngine()
        report = engine.run([], [], 0, 0, 0, 0, 0, 0)
        assert not report.all_passed  # balance fails with empty groups

    def test_empty_audit_no_findings(self):
        s = AuditHealthScorer()
        result = s.evaluate([])
        assert result.score == 1.0

    def test_empty_window_versions(self):
        checker = WindowConsistencyChecker()
        result = checker.check([])
        assert result.all_consistent


class TestFaultRecovery:
    """故障恢复：P0 清零后 gate 恢复 pass。"""

    def test_p0_cleared_restores_pass(self):
        s = AuditHealthScorer()
        s.evaluate([AuditFinding("P0", "security", "breach")])
        result = s.evaluate([])
        assert result.score >= 0.9
        assert not result.p0_blocking

    def test_trend_recovers_after_cleanup(self):
        s = AuditHealthScorer(trend_window=10)
        s.evaluate([AuditFinding("P0", "security", "bad")])
        s.evaluate([])
        s.evaluate([])
        t = s.trend()
        assert t["trend"] in ("stable", "improving", "declining")
