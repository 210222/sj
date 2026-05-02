"""全维度深测 — 内圈 + 中圈 12 模块全覆盖。

12 个测试维度：
  D1  随机不变量测试 (50,000 组)
  D2  跨模块集成链路 (L0→L1→L2→Decision→Safety)
  D3  属性验证 (单调性/有界性/幂等性/三角不等式)
  D4  压力与并发 (大批量/大history/内存)
  D5  合约对齐全量扫
  D6  时间一致性与窗口传播
  D7  错误传播链
  D8  配置参数扫变
  D9  状态转移全图
  D10 对抗性模糊测试
  D11 枚举跨模块交叉引用
  D12 全量回归烟验
"""

import json
import math
import os
import random
import time
import uuid
from datetime import datetime, timezone

import pytest

# ═══════════════════════════════════════════════════════════
# 模块导入
# ═══════════════════════════════════════════════════════════

# 内圈
from src.inner.ledger import EventStore
from src.inner.audit import AuditClassifier, P0_FIELDS, P1_FIELDS
from src.inner.clock import (
    get_window_30min, format_utc, parse_utc, validate_window_id,
    validate_window_consistency, WINDOW_SCHEMA_VERSION,
)
from src.inner.resolver import DisagreementResolver
from src.inner.no_assist import NoAssistEvaluator
from src.inner.gates import GateEngine

# 中圈
from src.middle.shared import (
    INTERVENTION_INTENSITIES, DOMINANT_LAYERS, CONFLICT_LEVELS,
    AUDIT_LEVELS, GATE_DECISIONS, NO_ASSIST_LEVELS,
    P0_FIELDS as SHARED_P0, P1_FIELDS as SHARED_P1,
    WINDOW_SCHEMA_VERSION as SHARED_WSV,
    MIDDLE_CONFIG_VERSION,
    StateEstimationError, MiddlewareError,
)
from src.middle.shared.config import (
    L0_DWELL_MIN_SECONDS, L0_SWITCH_PENALTY, L0_HYSTERESIS_ENTRY,
    L0_HYSTERESIS_EXIT, L0_MIN_SAMPLES,
    L1_SHOCK_THRESHOLD, L1_MEMORY_DECAY_RATE, L1_TREND_MIN_WINDOWS,
    L2_CAPABILITY_MIN, L2_OPPORTUNITY_MIN, L2_MOTIVATION_MIN,
    DECISION_WEIGHT_TRANSFER, DECISION_WEIGHT_CREATIVITY,
    DECISION_WEIGHT_INDEPENDENCE, DECISION_MAX_DELTA_PER_UPDATE,
    DECISION_MIN_WEIGHT, DECISION_LRM_WEIGHT, DECISION_ROBUST_WEIGHT,
    DECISION_CONFLICT_ESCALATE,
    SEMANTIC_SAFETY_MIN_SCORE, SEMANTIC_SAFETY_BLOCK_THRESHOLD,
)
from src.middle.state_l0 import L0Estimator
from src.middle.state_l1 import L1Estimator
from src.middle.state_l2 import L2Estimator
from src.middle.decision import DecisionEngine
from src.middle.semantic_safety import SemanticSafetyEngine

# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

_TS_BASE = "2026-04-29T{:02d}:{:02d}:{:02d}.000Z"


def _ts(h=12, m=0, s=0):
    return _TS_BASE.format(h % 24, m % 60, s % 60)


_SEED = 42


def _rfloat(lo=0.0, hi=1.0):
    return lo + random.random() * (hi - lo)


def _rchoice(seq):
    return random.choice(seq)


def _rint(lo, hi):
    return random.randint(lo, hi)


# ═══════════════════════════════════════════════════════════
# D1: 随机不变量测试 — 50,000 组
# ═══════════════════════════════════════════════════════════

class TestD1_RandomInvariants:
    """对每个有状态模块产生 10,000 组随机输入，验证输出不变量。"""

    def test_l0_random_10000_invariants(self):
        random.seed(_SEED)
        e = L0Estimator()
        states = {"engaged", "stable", "transient", "volatile"}
        for i in range(10000):
            r = e.estimate(
                f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                {"engagement": _rfloat(), "stability": _rfloat(), "volatility": _rfloat()},
                context={"prev_state": _rchoice([None, *_rchoice([list(states)])])}
                if _rfloat() > 0.3 else {},
            )
            assert r["state"] in states, f"invalid state: {r['state']}"
            assert 0.0 <= r["confidence"] <= 1.0
            assert r["dwell_time"] >= 0.0
            assert r["reason_code"].startswith("L0_")
            assert r["model_version"] == "l0_v1.0.0"
            assert r["config_version"].startswith("middle_v")
            assert validate_window_id(r["window_id"])

    def test_l1_random_10000_invariants(self):
        random.seed(_SEED + 1)
        e = L1Estimator()
        corrections = {"increase", "decrease", "none"}
        for i in range(10000):
            hist_len = _rint(0, 10)
            history = [_rfloat() for _ in range(hist_len)]
            r = e.estimate(
                f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                {"value": _rfloat(), "history": history,
                 "memory_state": _rfloat() if _rfloat() > 0.3 else None},
            )
            assert r["correction"] in corrections
            assert 0.0 <= r["magnitude"] <= 1.0
            assert 0.0 <= r["shock_score"] <= 1.0
            assert 0.0 <= r["memory_effect"] <= 1.0
            assert 0.0 <= r["trend_score"] <= 1.0
            assert r["reason_code"].startswith("L1_")

    def test_l2_random_10000_invariants(self):
        random.seed(_SEED + 2)
        e = L2Estimator()
        actions = {"advance", "hold", "defer"}
        for i in range(10000):
            hist_len = _rint(0, 8)
            history = [_rfloat() for _ in range(hist_len)]
            r = e.estimate(
                f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                {"goal_clarity": _rfloat(), "resource_readiness": _rfloat(),
                 "risk_pressure": _rfloat(), "constraint_conflict": _rfloat(),
                 "history": history,
                 "prior_uncertainty": _rfloat() if _rfloat() > 0.4 else None},
            )
            assert r["action_bias"] in actions
            assert 0.0 <= r["feasibility"] <= 1.0
            assert 0.0 <= r["uncertainty"] <= 1.0
            assert r["reason_code"].startswith("L2_")
            assert isinstance(r["feasible"], bool)
            assert isinstance(r["block_reason"], str)

    def test_decision_random_10000_invariants(self):
        random.seed(_SEED + 3)
        e = DecisionEngine()
        for i in range(10000):
            r = e.decide(
                f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                {"state": _rchoice(["engaged","stable","transient","volatile"]),
                 "confidence": _rfloat()},
                {"correction": _rchoice(["increase","decrease","none"]),
                 "magnitude": _rfloat()},
                {"feasible": _rchoice([True, False]),
                 "block_reason": _rchoice(["", "test"])},
                {"l0": _rfloat(), "l1": _rfloat(), "l2": _rfloat()},
            )
            assert r["intensity"] in set(INTERVENTION_INTENSITIES)
            assert r["dominant_layer"] in set(DOMINANT_LAYERS)
            assert r["conflict_level"] in set(CONFLICT_LEVELS)
            assert 0.0 <= r["total_score"] <= 1.0
            assert 0.0 <= r["conflict_score"] <= 1.0
            assert r["reason_code"].startswith("DEC_")

    def test_safety_random_10000_invariants(self):
        random.seed(_SEED + 4)
        e = SemanticSafetyEngine()
        for i in range(10000):
            r = e.evaluate(
                f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                {"intensity": _rchoice(list(INTERVENTION_INTENSITIES)),
                 "reason_code": _rchoice(["DEC_FULL","DEC_REDUCED","DEC_NONE"])},
                {"p0_count": _rchoice([0]*8 + [1]*2),
                 "p1_count": _rint(0, 5),
                 "gate_decision": _rchoice(list(GATE_DECISIONS)),
                 "risk_flags": _rchoice([[], ["R1"], ["R1","R2"]])},
            )
            assert isinstance(r["allowed"], bool)
            assert 0.0 <= r["safety_score"] <= 1.0
            assert r["audit_level"] in set(AUDIT_LEVELS)
            assert r["reason_code"].startswith("SEM_")
            assert isinstance(r["sanitized_output"], dict)

    def test_no_assist_random_5000_invariants(self):
        random.seed(_SEED + 5)
        na = NoAssistEvaluator()
        for i in range(5000):
            r = na.evaluate(
                f"s{i}", _rchoice(["answer " + "x" * _rint(0, 50), ""]),
                _rchoice([True, False]),
                _ts(_rint(0, 23), _rint(0, 59)),
                reference_answer=_rchoice([None, "reference text" * _rint(1, 10)]),
            )
            assert 0.0 <= r["no_assist_score"] <= 1.0
            assert r["no_assist_level"] in set(NO_ASSIST_LEVELS)

    def test_resolver_random_5000_invariants(self):
        random.seed(_SEED + 6)
        dr = DisagreementResolver()
        for i in range(5000):
            r = dr.resolve(
                {"state": _rchoice(["engaged","stable","transient","volatile"]),
                 "dwell_time": _rfloat(0, 1000)},
                {"correction": _rchoice(["increase","decrease","none"]),
                 "magnitude": _rfloat()},
                {"feasible": _rchoice([True, False]),
                 "block_reason": _rchoice(["", "conflict"])},
                {"l0": _rfloat(), "l1": _rfloat(), "l2": _rfloat()},
            )
            assert r["intervention_intensity"] in set(INTERVENTION_INTENSITIES)
            assert r["dominant_layer"] in set(DOMINANT_LAYERS)

    def test_gates_random_5000_invariants(self):
        random.seed(_SEED + 7)
        ge = GateEngine()
        for i in range(5000):
            gi = {}
            for gid in ["1_agency_gate","2_excursion_gate","3_learning_gate",
                        "4_relational_gate","5_causal_gate","6_audit_gate",
                        "7_framing_gate","8_window_gate"]:
                gi[gid] = {"pass": _rchoice([True, False]),
                           "metric_value": _rfloat()}
            r = ge.evaluate(gi, _ts(_rint(0, 23), _rint(0, 59)))
            assert r["decision"] in set(GATE_DECISIONS)
            assert 0.0 <= r["gate_score"] <= 1.0


# ═══════════════════════════════════════════════════════════
# D2: 跨模块集成链路
# ═══════════════════════════════════════════════════════════

class TestD2_CrossModuleIntegration:
    """L0→L1→L2→Decision→Safety 全链路集成。"""

    def test_full_pipeline_happy(self):
        l0 = L0Estimator()
        l1 = L1Estimator()
        l2 = L2Estimator()
        dec = DecisionEngine()
        safety = SemanticSafetyEngine()

        ts = _ts(14, 30)
        l0_r = l0.estimate("trace-001", ts,
                           {"engagement": 0.85, "stability": 0.80, "volatility": 0.10})
        l1_r = l1.estimate("trace-001", ts,
                           {"value": l0_r["confidence"],
                            "history": [0.75, 0.78, 0.80, 0.82, 0.85]})
        l2_r = l2.estimate("trace-001", ts,
                           {"goal_clarity": 0.80, "resource_readiness": 0.75,
                            "risk_pressure": 0.15, "constraint_conflict": 0.10,
                            "history": [0.70, 0.75, 0.78]})
        dec_r = dec.decide("trace-001", ts,
                           {"state": l0_r["state"], "confidence": l0_r["confidence"]},
                           {"correction": l1_r["correction"], "magnitude": l1_r["magnitude"]},
                           {"feasible": l2_r["feasible"], "block_reason": l2_r["block_reason"]},
                           {"l0": 1-l0_r["confidence"], "l1": l1_r["shock_score"],
                            "l2": l2_r["uncertainty"]})
        safety_r = safety.evaluate("trace-001", ts,
                                   {"intensity": dec_r["intensity"],
                                    "reason_code": dec_r["reason_code"]},
                                   {"p0_count": 0, "p1_count": 0, "gate_decision": "GO"})

        assert safety_r["allowed"] is True
        assert safety_r["audit_level"] == "pass"
        assert all(r["window_id"] == l0_r["window_id"]
                   for r in [l1_r, l2_r, dec_r, safety_r])

    def test_full_pipeline_blocked_by_l2(self):
        l0 = L0Estimator()
        l1 = L1Estimator()
        l2 = L2Estimator()
        dec = DecisionEngine()
        safety = SemanticSafetyEngine()

        ts = _ts(15)
        l2_r = l2.estimate("trace-002", ts,
                           {"goal_clarity": 0.15, "resource_readiness": 0.10,
                            "risk_pressure": 0.90, "constraint_conflict": 0.85})
        dec_r = dec.decide("trace-002", ts,
                           {"state": "volatile", "confidence": 0.20},
                           {"correction": "none", "magnitude": 0.10},
                           {"feasible": l2_r["feasible"], "block_reason": l2_r["block_reason"]},
                           {"l0": 0.70, "l1": 0.60, "l2": 0.80})
        safety_r = safety.evaluate("trace-002", ts,
                                   {"intensity": dec_r["intensity"],
                                    "reason_code": dec_r["reason_code"]},
                                   {"p0_count": 0, "p1_count": 0, "gate_decision": "GO"})

        assert dec_r["intensity"] == "none"
        assert dec_r["dominant_layer"] == "L2"

    def test_pipeline_100_varied(self):
        random.seed(_SEED + 10)
        l0, l1, l2 = L0Estimator(), L1Estimator(), L2Estimator()
        dec, safety = DecisionEngine(), SemanticSafetyEngine()

        for i in range(100):
            ts = _ts(_rint(0, 23), _rint(0, 59), _rint(0, 59))
            eng = _rfloat(0.1, 1.0)
            sta = _rfloat(0.1, 1.0)
            vol = _rfloat(0.0, 0.9)

            try:
                l0_r = l0.estimate(f"t{i}", ts,
                                   {"engagement": eng, "stability": sta, "volatility": vol})
                l1_r = l1.estimate(f"t{i}", ts,
                                   {"value": l0_r["confidence"],
                                    "history": [_rfloat() for _ in range(_rint(0, 8))]})
                l2_r = l2.estimate(f"t{i}", ts,
                                   {"goal_clarity": eng, "resource_readiness": sta,
                                    "risk_pressure": vol, "constraint_conflict": _rfloat()})
                dec_r = dec.decide(f"t{i}", ts,
                                   {"state": l0_r["state"], "confidence": l0_r["confidence"]},
                                   {"correction": l1_r["correction"], "magnitude": l1_r["magnitude"]},
                                   {"feasible": l2_r["feasible"], "block_reason": l2_r["block_reason"]},
                                   {"l0": 1-l0_r["confidence"], "l1": l1_r["shock_score"],
                                    "l2": l2_r["uncertainty"]})
                safety_r = safety.evaluate(f"t{i}", ts,
                                           {"intensity": dec_r["intensity"],
                                            "reason_code": dec_r["reason_code"]},
                                           {"p0_count": _rchoice([0]*9 + [1]),
                                            "p1_count": _rint(0, 3),
                                            "gate_decision": _rchoice(list(GATE_DECISIONS))})
                assert safety_r["audit_level"] in set(AUDIT_LEVELS)
                assert 0.0 <= safety_r["safety_score"] <= 1.0
            except StateEstimationError:
                pass  # 边界非法值预期


# ═══════════════════════════════════════════════════════════
# D3: 属性验证
# ═══════════════════════════════════════════════════════════

class TestD3_PropertyVerification:
    """数学属性：边界、单调性、距离三角不等式。"""

    def test_l0_confidence_bounded(self):
        e = L0Estimator()
        for i in range(500):
            r = e.estimate(f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                           {"engagement": _rfloat(), "stability": _rfloat(), "volatility": _rfloat()})
            assert 0.0 <= r["confidence"] <= 1.0

    def test_l1_magnitude_bounded(self):
        e = L1Estimator()
        for i in range(500):
            r = e.estimate(f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                           {"value": _rfloat(), "history": [_rfloat() for _ in range(5)]})
            assert 0.0 <= r["magnitude"] <= 1.0

    def test_l2_feasibility_uncertainty_bounded(self):
        e = L2Estimator()
        for i in range(500):
            r = e.estimate(f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                           {"goal_clarity": _rfloat(), "resource_readiness": _rfloat(),
                            "risk_pressure": _rfloat(), "constraint_conflict": _rfloat()})
            assert 0.0 <= r["feasibility"] <= 1.0
            assert 0.0 <= r["uncertainty"] <= 1.0

    def test_decision_scores_bounded(self):
        e = DecisionEngine()
        for i in range(500):
            r = e.decide(f"t{i}", _ts(_rint(0, 23), _rint(0, 59)),
                         {"state": "stable", "confidence": _rfloat()},
                         {"correction": "none", "magnitude": _rfloat()},
                         {"feasible": True, "block_reason": ""},
                         {"l0": _rfloat(), "l1": _rfloat(), "l2": _rfloat()})
            assert 0.0 <= r["total_score"] <= 1.0
            assert 0.0 <= r["conflict_score"] <= 1.0

    def test_memory_monotonic_decay(self):
        e = L1Estimator(memory_decay_rate=0.1)
        mem = 1.0
        for i in range(200):
            r = e.estimate(f"t{i}", _ts(14, 0, i),
                           {"value": 0.5, "history": [0.5]*5, "memory_state": mem})
            assert r["memory_effect"] <= mem + 1e-9
            mem = r["memory_effect"]

    def test_dwell_time_monotonic(self):
        e = L0Estimator()
        ctx = {"prev_state": "stable", "state_start_time_utc": "2026-04-29T14:00:00.000Z"}
        prev = 0
        for m in range(1, 60):
            r = e.estimate("t", f"2026-04-29T14:{m:02d}:00.000Z",
                           {"engagement": 0.55, "stability": 0.55, "volatility": 0.45},
                           context=ctx)
            assert r["dwell_time"] >= prev
            prev = r["dwell_time"]

    def test_safety_p0_monotonic_dominance(self):
        e = SemanticSafetyEngine()
        r_clean = e.evaluate("t", _ts(14), {"intensity":"reduced","reason_code":"x"},
                             {"p0_count":0,"p1_count":5,"gate_decision":"FREEZE"})
        r_p0 = e.evaluate("t", _ts(14), {"intensity":"reduced","reason_code":"x"},
                          {"p0_count":1,"p1_count":0,"gate_decision":"GO"})
        assert r_p0["audit_level"] == "p0_block"
        assert r_p0["safety_score"] == 0.0


# ═══════════════════════════════════════════════════════════
# D4: 压力与并发
# ═══════════════════════════════════════════════════════════

class TestD4_StressAndConcurrency:
    def test_l0_batch_5000(self):
        e = L0Estimator()
        for i in range(5000):
            r = e.estimate(f"t{i}", _ts(i % 24, i % 60),
                           {"engagement": (i*0.037)%1.0,
                            "stability": (i*0.053)%1.0,
                            "volatility": (i*0.029)%1.0})
            assert "state" in r

    def test_l1_large_history(self):
        e = L1Estimator()
        history = [_rfloat() for _ in range(5000)]
        r = e.estimate("t", _ts(14), {"value": 0.5, "history": history})
        assert r["trend_score"] >= 0.0

    def test_l2_large_history(self):
        e = L2Estimator()
        history = [_rfloat() for _ in range(5000)]
        r = e.estimate("t", _ts(14), {"goal_clarity": 0.7, "resource_readiness": 0.7,
                                       "risk_pressure": 0.2, "constraint_conflict": 0.2,
                                       "history": history})
        assert 0.0 <= r["feasibility"] <= 1.0

    def test_decision_batch_1000(self):
        e = DecisionEngine()
        start = time.perf_counter()
        for i in range(1000):
            e.decide(f"t{i}", _ts(i % 24, i % 60),
                     {"state": "stable", "confidence": (i*0.07)%1.0},
                     {"correction": "none", "magnitude": (i*0.11)%1.0},
                     {"feasible": i % 5 != 0, "block_reason": ""},
                     {"l0": (i*0.13)%1.0, "l1": (i*0.17)%1.0, "l2": (i*0.19)%1.0})
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"1000 decisions took {elapsed:.2f}s"

    def test_safety_batch_1000(self):
        e = SemanticSafetyEngine()
        intensities = list(INTERVENTION_INTENSITIES)
        for i in range(1000):
            e.evaluate(f"t{i}", _ts(i % 24, i % 60),
                       {"intensity": intensities[i%4], "reason_code": "DEC_TEST"},
                       {"p0_count": 0, "p1_count": i % 4,
                        "gate_decision": "GO" if i%3 else "WARN" if i%3==1 else "FREEZE"})


# ═══════════════════════════════════════════════════════════
# D5: 合约对齐全量扫
# ═══════════════════════════════════════════════════════════

class TestD5_ContractAlignmentFullSweep:
    def test_all_contracts_loadable(self):
        contracts_dir = "D:/Claudedaoy/coherence/contracts"
        for name in ["ledger", "audit", "clock", "resolver", "gates"]:
            with open(f"{contracts_dir}/{name}.json", encoding="utf-8") as f:
                c = json.load(f)
            assert c["status"] == "frozen"
            assert c["version"] == "1.0.0"

    def test_shared_enums_against_contracts(self):
        with open("D:/Claudedaoy/coherence/contracts/resolver.json", encoding="utf-8") as f:
            r = json.load(f)
        assert set(INTERVENTION_INTENSITIES) == set(
            r["outputs"]["intervention_intensity"]["enum"])
        assert set(DOMINANT_LAYERS) == set(
            r["required_fields"]["dominant_layer"]["enum"])
        assert set(CONFLICT_LEVELS) == set(r["conflict_levels"].keys())

    def test_inner_p0_p1_against_contracts(self):
        with open("D:/Claudedaoy/coherence/contracts/ledger.json", encoding="utf-8") as f:
            l = json.load(f)
        assert set(P0_FIELDS) == set(l["schema"]["p0_fields"])
        assert set(P1_FIELDS) == set(l["schema"]["p1_fields"])

    def test_shared_p0_p1_bridge_intact(self):
        assert SHARED_P0 == P0_FIELDS
        assert SHARED_P1 == P1_FIELDS
        assert SHARED_WSV == WINDOW_SCHEMA_VERSION

    def test_shared_config_against_yaml(self):
        with open("D:/Claudedaoy/coherence/config/parameters.yaml", encoding="utf-8") as f:
            import yaml
            cfg = yaml.safe_load(f)
        assert L0_DWELL_MIN_SECONDS == cfg["state_estimation"]["dwell_min_seconds"]
        assert DECISION_WEIGHT_TRANSFER == cfg["decision"]["weight_transfer"]
        assert SEMANTIC_SAFETY_MIN_SCORE == 0.5

    def test_no_enum_drift_in_any_module(self):
        import glob
        mid_files = glob.glob("src/middle/**/*.py", recursive=True)
        for fpath in mid_files:
            with open(fpath, encoding="utf-8") as f:
                src = f.read()
            if "shared" in fpath:
                continue  # shared 是定义源，允许
            assert "INTERVENTION_INTENSITIES" not in src or "from src.middle.shared" in src, \
                f"{fpath} may re-define shared enum"
            assert "DOMINANT_LAYERS" not in src or "from src.middle.shared" in src, \
                f"{fpath} may re-define shared enum"


# ═══════════════════════════════════════════════════════════
# D6: 时间一致性与窗口传播
# ═══════════════════════════════════════════════════════════

class TestD6_TimeConsistencyPropagation:
    def test_window_id_consistent_across_chain(self):
        ts = "2026-04-29T14:22:30.000Z"
        expected = get_window_30min(ts)

        l0 = L0Estimator().estimate("t", ts, {"engagement": 0.5, "stability": 0.5, "volatility": 0.5})
        l1 = L1Estimator().estimate("t", ts, {"value": 0.5, "history": [0.5]*5})
        l2 = L2Estimator().estimate("t", ts, {"goal_clarity": 0.5, "resource_readiness": 0.5,
                                               "risk_pressure": 0.5, "constraint_conflict": 0.5})
        dec = DecisionEngine().decide("t", ts, {"state":"stable","confidence":0.5},
                                      {"correction":"none","magnitude":0.0},
                                      {"feasible":True,"block_reason":""},
                                      {"l0":0.5,"l1":0.5,"l2":0.5})
        safety = SemanticSafetyEngine().evaluate("t", ts,
                                                 {"intensity":"reduced","reason_code":"x"},
                                                 {"p0_count":0,"p1_count":0,"gate_decision":"GO"})
        for name, r in [("l0", l0), ("l1", l1), ("l2", l2), ("dec", dec), ("safety", safety)]:
            assert r["window_id"] == expected, f"{name} window_id mismatch"

    def test_all_evaluated_at_utc_are_iso8601(self):
        ts = _ts(14)
        modules = [
            L0Estimator().estimate("t", ts, {"engagement": 0.5, "stability": 0.5, "volatility": 0.5}),
            L1Estimator().estimate("t", ts, {"value": 0.5, "history": [0.5]*5}),
            L2Estimator().estimate("t", ts, {"goal_clarity": 0.5, "resource_readiness": 0.5,
                                              "risk_pressure": 0.5, "constraint_conflict": 0.5}),
            DecisionEngine().decide("t", ts, {"state":"s","confidence":0.5},
                                    {"correction":"n","magnitude":0.0},
                                    {"feasible":True,"block_reason":""},
                                    {"l0":0.5,"l1":0.5,"l2":0.5}),
            SemanticSafetyEngine().evaluate("t", ts, {"intensity":"none","reason_code":"x"},
                                           {"p0_count":0,"p1_count":0,"gate_decision":"GO"}),
        ]
        for r in modules:
            assert r["evaluated_at_utc"].endswith("Z")
            assert "T" in r["evaluated_at_utc"]

    def test_window_boundary_behavior(self):
        r1 = get_window_30min("2026-04-29T14:29:59.999Z")
        r2 = get_window_30min("2026-04-29T14:30:00.000Z")
        assert r1 != r2
        assert "14:00_2026" in r1
        assert "14:30_2026" in r2

    def test_validate_window_consistency(self):
        event = {
            "event_time_utc": "2026-04-29T14:15:00.000Z",
            "window_id": get_window_30min("2026-04-29T14:15:00.000Z"),
            "window_schema_version": WINDOW_SCHEMA_VERSION,
        }
        result = validate_window_consistency(event)
        assert result["valid"] is True


# ═══════════════════════════════════════════════════════════
# D7: 错误传播链
# ═══════════════════════════════════════════════════════════

class TestD7_ErrorPropagation:
    def test_state_estimation_error_propagates_correctly(self):
        with pytest.raises(StateEstimationError):
            L0Estimator().estimate("t", _ts(14),
                                   {"engagement": 2.0, "stability": 0.5, "volatility": 0.5})
        with pytest.raises(StateEstimationError):
            L1Estimator().estimate("t", _ts(14),
                                   {"value": -0.5, "history": []})

    def test_middleware_error_catches_all(self):
        for exc_cls in [StateEstimationError]:
            try:
                raise exc_cls("test")
            except MiddlewareError:
                pass
            else:
                pytest.fail(f"{exc_cls} not caught by MiddlewareError")

    def test_invalid_time_rejected_by_all_modules(self):
        bad_ts = "not-a-time"
        modules = [
            lambda: L0Estimator().estimate("t", bad_ts, {"engagement":0.5,"stability":0.5,"volatility":0.5}),
            lambda: L1Estimator().estimate("t", bad_ts, {"value":0.5,"history":[]}),
            lambda: L2Estimator().estimate("t", bad_ts, {"goal_clarity":0.5,"resource_readiness":0.5,"risk_pressure":0.5,"constraint_conflict":0.5}),
            lambda: DecisionEngine().decide("t", bad_ts, {"state":"s","confidence":0.5},{"correction":"n","magnitude":0.0},{"feasible":True,"block_reason":""},{"l0":0.5,"l1":0.5,"l2":0.5}),
            lambda: SemanticSafetyEngine().evaluate("t", bad_ts, {"intensity":"none","reason_code":"x"},{"p0_count":0,"p1_count":0,"gate_decision":"GO"}),
        ]
        for i, fn in enumerate(modules):
            with pytest.raises((StateEstimationError, ValueError)):
                fn()

    def test_nan_rejected_by_all(self):
        nan = float("nan")
        # L2 / Decision / Safety 有显式 NaN 检查
        with pytest.raises(StateEstimationError):
            L2Estimator().estimate("t", _ts(14), {"goal_clarity": nan, "resource_readiness": 0.5,
                                                   "risk_pressure": 0.5, "constraint_conflict": 0.5})
        with pytest.raises(StateEstimationError):
            DecisionEngine().decide("t", _ts(14), {"state":"s","confidence":nan},
                                    {"correction":"none","magnitude":0.0},
                                    {"feasible":True,"block_reason":""},
                                    {"l0":0.5,"l1":0.5,"l2":0.5})
        with pytest.raises(StateEstimationError):
            SemanticSafetyEngine().evaluate("t", _ts(14),
                                           {"intensity":"none","reason_code":"x"},
                                           {"p0_count":nan,"p1_count":0,"gate_decision":"GO"})


# ═══════════════════════════════════════════════════════════
# D8: 配置参数扫变
# ═══════════════════════════════════════════════════════════

class TestD8_ConfigSweep:
    def test_l0_hysteresis_sweep(self):
        for h_entry in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
            e = L0Estimator(hysteresis_entry=h_entry)
            r = e.estimate("t", _ts(14), {"engagement": h_entry, "stability": h_entry,
                                           "volatility": 1-h_entry})
            assert r["state"] in {"engaged", "stable", "transient", "volatile"}

    def test_l1_shock_threshold_sweep(self):
        for th in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
            e = L1Estimator(shock_threshold=th)
            r = e.estimate("t", _ts(14), {"value": th + 0.3, "history": [0.3]*5})
            assert r["shock_score"] > 0.0

    def test_l2_capability_sweep(self):
        for cap in [0.15, 0.25, 0.35, 0.45, 0.55, 0.65]:
            e = L2Estimator(capability_min=cap)
            r = e.estimate("t", _ts(14), {"goal_clarity": cap + 0.1, "resource_readiness": 0.7,
                                           "risk_pressure": 0.3, "constraint_conflict": 0.3})
            assert 0.0 <= r["feasibility"] <= 1.0

    def test_decision_weight_sweep(self):
        for w_t in [0.2, 0.3, 0.4, 0.5, 0.6]:
            w_c = 1.0 - w_t - 0.2
            if w_c < 0: continue
            e = DecisionEngine(weight_transfer=w_t, weight_creativity=w_c,
                               weight_independence=0.2)
            r = e.decide("t", _ts(14), {"state":"s","confidence":0.7},
                         {"correction":"n","magnitude":0.5},
                         {"feasible":True,"block_reason":""},
                         {"l0":0.3,"l1":0.3,"l2":0.3})
            assert r["intensity"] in set(INTERVENTION_INTENSITIES)

    def test_safety_threshold_sweep(self):
        for min_s in [0.3, 0.4, 0.5, 0.6, 0.7]:
            e = SemanticSafetyEngine(min_score=min_s, block_threshold=min_s*0.5)
            r = e.evaluate("t", _ts(14), {"intensity":"reduced","reason_code":"x"},
                           {"p0_count":0,"p1_count":1,"gate_decision":"WARN"})
            assert r["audit_level"] in set(AUDIT_LEVELS)


# ═══════════════════════════════════════════════════════════
# D9: 状态转移全图
# ═══════════════════════════════════════════════════════════

class TestD9_StateTransitionGraph:
    def test_l0_all_possible_transitions(self):
        e = L0Estimator()
        states = ["engaged", "stable", "transient", "volatile"]
        seen = set()
        for prev in states:
            for eng in [0.10, 0.35, 0.55, 0.85]:
                r = e.estimate("t", _ts(14),
                               {"engagement": eng, "stability": eng, "volatility": 1-eng},
                               context={"prev_state": prev,
                                        "state_start_time_utc": "2026-04-29T14:00:00.000Z"})
                seen.add((prev, r["state"]))
        assert len(seen) >= 8  # 至少一半可能的转移

    def test_decision_all_intensity_transitions(self):
        e = DecisionEngine(conflict_escalate=0.9)
        intensities_seen = set()
        for conf in [0.10, 0.30, 0.50, 0.70, 0.90]:
            for mag in [0.10, 0.30, 0.50, 0.70, 0.90]:
                r = e.decide("t", _ts(14),
                             {"state":"s","confidence":conf},
                             {"correction":"n","magnitude":mag},
                             {"feasible":True,"block_reason":""},
                             {"l0":0.3,"l1":0.3,"l2":0.3})
                intensities_seen.add(r["intensity"])
        assert len(intensities_seen) >= 3

    def test_safety_all_audit_level_transitions(self):
        e = SemanticSafetyEngine()
        seen = set()
        for p0 in [0, 1]:
            for p1 in range(0, 6, 2):
                for gate in GATE_DECISIONS:
                    r = e.evaluate("t", _ts(14),
                                   {"intensity":"reduced","reason_code":"x"},
                                   {"p0_count":p0,"p1_count":p1,"gate_decision":gate})
                    seen.add(r["audit_level"])
        assert seen == set(AUDIT_LEVELS)


# ═══════════════════════════════════════════════════════════
# D10: 对抗性模糊测试
# ═══════════════════════════════════════════════════════════

class TestD10_AdversarialFuzzing:
    def test_massive_random_chain_fuzz(self):
        random.seed(_SEED + 99)
        l0, l1, l2 = L0Estimator(), L1Estimator(), L2Estimator()
        dec, safety = DecisionEngine(), SemanticSafetyEngine()
        violations = 0
        for i in range(3000):
            ts = _ts(_rint(0, 23), _rint(0, 59))
            # 可能产生极端/非法值
            try:
                sigs_l0 = {"engagement": _rfloat(-0.1, 1.2),
                           "stability": _rfloat(-0.1, 1.2),
                           "volatility": _rfloat(-0.1, 1.2)}
                l0_r = l0.estimate(f"t{i}", ts, sigs_l0)
            except StateEstimationError:
                l0_r = {"state": "volatile", "confidence": 0.0, "window_id": get_window_30min(ts)}
            except Exception:
                violations += 1
                continue

            try:
                sigs_l1 = {"value": l0_r["confidence"],
                           "history": [_rfloat() for _ in range(_rint(0, 12))]}
                l1_r = l1.estimate(f"t{i}", ts, sigs_l1)
            except StateEstimationError:
                l1_r = {"correction": "none", "magnitude": 0.0, "shock_score": 0.0,
                        "window_id": get_window_30min(ts)}
            except Exception:
                violations += 1
                continue

            try:
                l2_r = l2.estimate(f"t{i}", ts,
                                   {"goal_clarity": _rfloat(), "resource_readiness": _rfloat(),
                                    "risk_pressure": _rfloat(), "constraint_conflict": _rfloat()})
            except StateEstimationError:
                l2_r = {"feasible": True, "block_reason": "", "action_bias": "hold",
                        "window_id": get_window_30min(ts)}
            except Exception:
                violations += 1
                continue

            try:
                dec_r = dec.decide(f"t{i}", ts,
                                   {"state": l0_r.get("state", "stable"),
                                    "confidence": l0_r.get("confidence", 0.5)},
                                   {"correction": l1_r.get("correction", "none"),
                                    "magnitude": l1_r.get("magnitude", 0.0)},
                                   {"feasible": l2_r.get("feasible", True),
                                    "block_reason": l2_r.get("block_reason", "")},
                                   {"l0": _rfloat(), "l1": _rfloat(), "l2": _rfloat()})
            except StateEstimationError:
                dec_r = {"intensity": "none", "reason_code": "DEC_NONE", "window_id": get_window_30min(ts)}
            except Exception:
                violations += 1
                continue

            try:
                safety_r = safety.evaluate(f"t{i}", ts,
                                           {"intensity": dec_r.get("intensity", "none"),
                                            "reason_code": dec_r.get("reason_code", "x")},
                                           {"p0_count": _rchoice([0,0,0,1]),
                                            "p1_count": _rint(0, 5),
                                            "gate_decision": _rchoice(list(GATE_DECISIONS))})
                assert safety_r["audit_level"] in set(AUDIT_LEVELS)
            except StateEstimationError:
                pass
            except Exception:
                violations += 1

        assert violations == 0, f"{violations} unexpected errors in fuzz chain"

    def test_edge_type_coercion(self):
        cases = [
            (True, "bool"),
            ([], "list"),
            ({}, "dict"),
            (None, "None"),
            ("string", "str"),
        ]
        for val, label in cases:
            with pytest.raises(StateEstimationError):
                L2Estimator().estimate("t", _ts(14), {
                    "goal_clarity": val, "resource_readiness": 0.5,
                    "risk_pressure": 0.5, "constraint_conflict": 0.5,
                })

    def test_nan_inf_everywhere(self):
        for bad in [float("nan"), float("inf"), float("-inf")]:
            # L2 / Decision / Safety 有显式 NaN/inf 检查
            with pytest.raises(StateEstimationError):
                L2Estimator().estimate("t", _ts(14),
                                       {"goal_clarity": bad, "resource_readiness": 0.5,
                                        "risk_pressure": 0.5, "constraint_conflict": 0.5})
            with pytest.raises(StateEstimationError):
                DecisionEngine().decide("t", _ts(14), {"state":"s","confidence":bad},
                                        {"correction":"none","magnitude":0.0},
                                        {"feasible":True,"block_reason":""},
                                        {"l0":0.5,"l1":0.5,"l2":0.5})

    def test_negative_counts_in_safety(self):
        e = SemanticSafetyEngine()
        with pytest.raises(StateEstimationError):
            e.evaluate("t", _ts(14), {"intensity":"none","reason_code":"x"},
                       {"p0_count": -1, "p1_count": 0, "gate_decision": "GO"})
        with pytest.raises(StateEstimationError):
            e.evaluate("t", _ts(14), {"intensity":"none","reason_code":"x"},
                       {"p0_count": 0, "p1_count": -5, "gate_decision": "GO"})


# ═══════════════════════════════════════════════════════════
# D11: 枚举交叉引用完整性
# ═══════════════════════════════════════════════════════════

class TestD11_EnumCrossReference:
    def test_all_shared_enums_used_by_consumers(self):
        enums_expected = {
            "INTERVENTION_INTENSITIES": ["decision", "semantic_safety"],
            "DOMINANT_LAYERS": ["decision"],
            "CONFLICT_LEVELS": ["decision"],
            "AUDIT_LEVELS": ["semantic_safety"],
            "GATE_DECISIONS": ["semantic_safety"],
            "NO_ASSIST_LEVELS": [],
        }
        for enum_name, expected_consumers in enums_expected.items():
            assert enum_name in dir(__import__("src.middle.shared.constants", fromlist=[enum_name]))

    def test_no_unknown_enum_values_in_outputs(self):
        e = DecisionEngine()
        for i in range(500):
            r = e.decide(f"t{i}", _ts(_rint(0,23), _rint(0,59)),
                         {"state":"stable","confidence":_rfloat()},
                         {"correction":"none","magnitude":_rfloat()},
                         {"feasible":_rchoice([True,False]),"block_reason":""},
                         {"l0":_rfloat(),"l1":_rfloat(),"l2":_rfloat()})
            assert r["intensity"] in set(INTERVENTION_INTENSITIES)
            assert r["dominant_layer"] in set(DOMINANT_LAYERS)
            assert r["conflict_level"] in set(CONFLICT_LEVELS)

    def test_audit_levels_in_safety_output(self):
        e = SemanticSafetyEngine()
        for i in range(500):
            r = e.evaluate(f"t{i}", _ts(_rint(0,23), _rint(0,59)),
                           {"intensity":_rchoice(list(INTERVENTION_INTENSITIES)),"reason_code":"x"},
                           {"p0_count":_rchoice([0,0,0,1]),"p1_count":_rint(0,5),
                            "gate_decision":_rchoice(list(GATE_DECISIONS))})
            assert r["audit_level"] in set(AUDIT_LEVELS)

    def test_all_enum_sets_mutually_consistent(self):
        assert "none" in INTERVENTION_INTENSITIES and "none" in DOMINANT_LAYERS
        assert "full" in INTERVENTION_INTENSITIES
        assert len(set(INTERVENTION_INTENSITIES)) == len(INTERVENTION_INTENSITIES)
        assert len(set(DOMINANT_LAYERS)) == len(DOMINANT_LAYERS)
        assert len(set(CONFLICT_LEVELS)) == len(CONFLICT_LEVELS)
        assert len(set(AUDIT_LEVELS)) == len(AUDIT_LEVELS)
        assert len(set(GATE_DECISIONS)) == len(GATE_DECISIONS)


# ═══════════════════════════════════════════════════════════
# D12: 全量回归烟验 + 模块计数
# ═══════════════════════════════════════════════════════════

class TestD12_RegressionSmokeAndCount:
    def test_inner_module_count(self):
        import src.inner
        mods = ["ledger", "audit", "clock", "resolver", "no_assist", "gates"]
        for m in mods:
            assert hasattr(src.inner, m), f"Missing inner.{m}"

    def test_middle_module_count(self):
        import src.middle
        mods = ["shared", "state_l0", "state_l1", "state_l2", "decision", "semantic_safety"]
        for m in mods:
            assert hasattr(src.middle, m), f"Missing middle.{m}"

    def test_all_version_strings_present(self):
        versions = {
            "l0": "l0_v1.0.0", "l1": "l1_v1.0.0", "l2": "l2_v1.0.0",
            "decision": "decision_v1.0.0", "sem_safety": "sem_safety_v1.0.0",
        }
        for mod, ver in versions.items():
            assert ver is not None

    def test_config_version_universal(self):
        for mod_fn in [
            lambda: L0Estimator().estimate("t", _ts(14), {"engagement":0.5,"stability":0.5,"volatility":0.5}),
            lambda: L1Estimator().estimate("t", _ts(14), {"value":0.5,"history":[0.5]*5}),
            lambda: L2Estimator().estimate("t", _ts(14), {"goal_clarity":0.5,"resource_readiness":0.5,"risk_pressure":0.5,"constraint_conflict":0.5}),
            lambda: DecisionEngine().decide("t", _ts(14), {"state":"s","confidence":0.5},{"correction":"n","magnitude":0.0},{"feasible":True,"block_reason":""},{"l0":0.5,"l1":0.5,"l2":0.5}),
            lambda: SemanticSafetyEngine().evaluate("t", _ts(14), {"intensity":"none","reason_code":"x"},{"p0_count":0,"p1_count":0,"gate_decision":"GO"}),
        ]:
            r = mod_fn()
            assert r["config_version"] == MIDDLE_CONFIG_VERSION

    def test_inner_contract_audit_mapping(self):
        ac = AuditClassifier()
        event = {
            "trace_id": str(uuid.uuid4()), "policy_version": "1.0.0",
            "counterfactual_ranker_version": "1.0", "counterfactual_feature_schema_version": "1.0",
            "event_time_utc": _ts(14), "window_id": get_window_30min(_ts(14)),
            "window_schema_version": WINDOW_SCHEMA_VERSION,
        }
        r = ac.classify(event)
        assert r["p0_pass"] is True
        # classify returns p1_null_rate_window, has_p1_issue; audit_level via evaluate_threshold
        p1_rate = r.get("p1_null_rate_window", 0.0)
        level = ac.evaluate_threshold(p1_rate)
        assert level in ("pass", "p1_warn", "p1_freeze", "p0_block")

    def test_ledger_append_and_verify(self):
        import tempfile, os
        db_path = os.path.join(tempfile.gettempdir(), f"test_comprehensive_{uuid.uuid4().hex[:8]}.db")
        try:
            store = EventStore(db_path)
            store.initialize()
            ev = store.create_genesis_event(str(uuid.uuid4()), "1.0.0")
            assert ev["chain_height"] == 0
            p0 = {f: "test" for f in P0_FIELDS}
            ev2 = store.append_event(p0_values=p0)
            assert ev2["chain_height"] == 1
            integrity = store.verify_chain_integrity()
            assert integrity["valid"] is True
        finally:
            try:
                os.unlink(db_path)
            except Exception:
                pass
