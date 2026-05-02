"""Step 4: L3 冲突仲裁器测试 — 低/中/高冲突、边界值、主导层、审计映射、非法输入、集成冒烟。"""

import os
import tempfile
import pytest
from src.inner.resolver import DisagreementResolver
from src.inner.resolver.config import (
    LOW_CONFLICT_THRESHOLD,
    HIGH_CONFLICT_THRESHOLD,
    RESOLVER_POLICY_VERSION,
)
from src.inner.ledger import EventStore


# ── helpers ─────────────────────────────────────────────────────

def _make_l0(state="engaged", dwell_time=5.0):
    return {"state": state, "dwell_time": dwell_time}


def _make_l1(correction="none", magnitude=0.1):
    return {"correction": correction, "magnitude": magnitude}


def _make_l2(feasible=True, block_reason=""):
    return {"feasible": feasible, "block_reason": block_reason}


def _make_uv(l0=0.1, l1=0.1, l2=0.1):
    return {"l0": l0, "l1": l1, "l2": l2}


@pytest.fixture
def resolver():
    return DisagreementResolver()


# ═══════════════════════════════════════════════════════════════
# 1) 低冲突 → normal
# ═══════════════════════════════════════════════════════════════

class TestLowConflict:
    """低冲突场景：所有层输出一致 → normal。"""

    def test_all_layers_agree(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.1, 0.1, 0.1),
        )
        assert r["disagreement_score"] < LOW_CONFLICT_THRESHOLD
        assert r["resolver_action"] == "normal"
        assert r["meta_conflict_alert_flag"] == 0

    def test_low_uncertainty_all_agree(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("stable"),
            residual_l1=_make_l1("stable", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.0, 0.0, 0.05),
        )
        assert r["disagreement_score"] < 0.2
        assert r["resolver_action"] == "normal"

    def test_intervention_intensity_unchanged_low_conflict(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.1, 0.1, 0.1),
        )
        # base intensity for engaged + low mag + feasible → "minimal"
        assert r["intervention_intensity"] == "minimal"


# ═══════════════════════════════════════════════════════════════
# 2) 中冲突 → deescalate
# ═══════════════════════════════════════════════════════════════

class TestMidConflict:
    """中冲突 [0.3, 0.7)：降一级干预。"""

    def test_l2_blocks_with_reason(self, resolver):
        # L2 阻断但 block_reason 不与 L0 状态直接冲突 → 中冲突
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("none", 0.0),    # L1 不冲突
            feasibility_l2=_make_l2(False, "other_action_blocked"),
            uncertainty_vector=_make_uv(0.3, 0.3, 0.3),
        )
        assert LOW_CONFLICT_THRESHOLD <= r["disagreement_score"] < HIGH_CONFLICT_THRESHOLD
        assert r["resolver_action"] == "deescalate"

    def test_deescalate_reduces_intensity(self, resolver):
        # base intensity should be "full" (not feasible), deescalate → "reduced"
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("push", 0.3),
            feasibility_l2=_make_l2(False, "blocked"),
            uncertainty_vector=_make_uv(0.2, 0.3, 0.2),
        )
        # base: full (not feasible), mid conflict → deescalate full → reduced
        assert r["intervention_intensity"] == "reduced"

    def test_none_dominant_with_medium_conflict(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("deteriorating"),
            residual_l1=_make_l1("improving", 0.5),
            feasibility_l2=_make_l2(False),
            uncertainty_vector=_make_uv(0.3, 0.3, 0.3),
        )
        assert r["disagreement_score"] >= LOW_CONFLICT_THRESHOLD
        # equal uncertainty 0.3 each → none（合约枚举）
        assert r["dominant_layer"] == "none"


# ═══════════════════════════════════════════════════════════════
# 3) 高冲突 → minimal_conservative
# ═══════════════════════════════════════════════════════════════

class TestHighConflict:
    """高冲突 >=0.7：最小干预保守策略。"""

    def test_all_signals_conflict_high_uncertainty(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("critical"),
            residual_l1=_make_l1("improving", 0.9),
            feasibility_l2=_make_l2(False, "critical_action_not_safe"),
            uncertainty_vector=_make_uv(0.9, 0.8, 0.9),
        )
        assert r["disagreement_score"] >= HIGH_CONFLICT_THRESHOLD
        assert r["resolver_action"] == "minimal_conservative"
        assert r["intervention_intensity"] == "minimal"
        assert r["meta_conflict_alert_flag"] == 1

    def test_high_conflict_resolved_state_is_conservative_hold(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("critical"),
            residual_l1=_make_l1("push_action", 0.9),
            feasibility_l2=_make_l2(False, "not_safe"),
            uncertainty_vector=_make_uv(0.9, 0.9, 0.9),
        )
        assert r["resolved_state"]["status"] == "conservative_hold"
        assert "critical" in r["resolved_state"]["description"]

    def test_high_conflict_always_minimal_intensity(self, resolver):
        """高冲突下无论基础干预多高，最终都是 minimal。"""
        r = resolver.resolve(
            state_l0=_make_l0("critical"),
            residual_l1=_make_l1("massive_correction", 0.95),
            feasibility_l2=_make_l2(False, "blocked"),
            uncertainty_vector=_make_uv(1.0, 1.0, 1.0),
        )
        assert r["disagreement_score"] >= HIGH_CONFLICT_THRESHOLD
        assert r["intervention_intensity"] == "minimal"


# ═══════════════════════════════════════════════════════════════
# 4) disagreement_score 边界值
# ═══════════════════════════════════════════════════════════════

class TestDisagreementScoreBoundaries:
    """disagreement_score 边界：0、阈值精确值、1。"""

    def test_score_zero_when_all_agree(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("stable"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.0, 0.0, 0.0),
        )
        assert r["disagreement_score"] == 0.0

    def test_score_at_low_threshold_boundary(self, resolver):
        """0.29 → low, 0.30 → mid（合约定义 0.3 起进入 mid）。"""
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("push", 0.4),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.29, 0.3, 0.28),
        )
        score = r["disagreement_score"]
        if score < LOW_CONFLICT_THRESHOLD:
            assert r["resolver_action"] == "normal"
        else:
            assert r["resolver_action"] in ("deescalate", "minimal_conservative")

    def test_score_at_high_threshold_boundary(self, resolver):
        """接近 0.7 的边界行为。"""
        r = resolver.resolve(
            state_l0=_make_l0("critical"),
            residual_l1=_make_l1("improving", 0.9),
            feasibility_l2=_make_l2(False, "blocked"),
            uncertainty_vector=_make_uv(0.7, 0.7, 0.8),
        )
        assert r["disagreement_score"] >= 0.5  # 至少中冲突

    def test_score_is_clamped_to_one(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("critical"),
            residual_l1=_make_l1("improving", 1.0),
            feasibility_l2=_make_l2(False, "blocked"),
            uncertainty_vector=_make_uv(1.0, 1.0, 1.0),
        )
        assert 0.0 <= r["disagreement_score"] <= 1.0


# ═══════════════════════════════════════════════════════════════
# 5) dominant_layer 判定（含 MIXED）
# ═══════════════════════════════════════════════════════════════

class TestDominantLayer:
    """dominant_layer: 不确定性最低的层主导，平局 → MIXED。"""

    def test_l0_dominates(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("stable"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.1, 0.5, 0.6),
        )
        assert r["dominant_layer"] == "L0"

    def test_l2_dominates(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("stable"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.5, 0.5, 0.1),
        )
        assert r["dominant_layer"] == "L2"

    def test_mixed_when_tie(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("stable"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.3, 0.3, 0.3),
        )
        assert r["dominant_layer"] == "none"

    def test_mixed_when_l0_l1_tie(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("stable"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.2, 0.2, 0.5),
        )
        assert r["dominant_layer"] == "none"


# ═══════════════════════════════════════════════════════════════
# 6) 审计字段映射
# ═══════════════════════════════════════════════════════════════

class TestAuditMapping:
    """to_audit_fields: meta_conflict_score / track_disagreement_level / meta_conflict_alert_flag。"""

    def test_audit_fields_map_correctly(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("critical"),
            residual_l1=_make_l1("improving", 0.9),
            feasibility_l2=_make_l2(False, "blocked"),
            uncertainty_vector=_make_uv(0.9, 0.9, 0.9),
        )
        af = resolver.to_audit_fields(r)
        assert af["meta_conflict_score"] == r["disagreement_score"]
        assert af["track_disagreement_level"] == r["disagreement_score"]
        assert af["meta_conflict_alert_flag"] == 1

    def test_audit_fields_zero_flag_for_low_conflict(self, resolver):
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("none", 0.0),
            feasibility_l2=_make_l2(True),
            uncertainty_vector=_make_uv(0.0, 0.0, 0.0),
        )
        af = resolver.to_audit_fields(r)
        assert af["meta_conflict_alert_flag"] == 0


# ═══════════════════════════════════════════════════════════════
# 7) 非法输入处理
# ═══════════════════════════════════════════════════════════════

class TestInvalidInput:
    """非法输入 → TypeError 或 ValueError。"""

    def test_non_dict_input_raises_type_error(self, resolver):
        with pytest.raises(TypeError):
            resolver.resolve(
                state_l0="not_a_dict",
                residual_l1=_make_l1(),
                feasibility_l2=_make_l2(),
                uncertainty_vector=_make_uv(),
            )

    def test_missing_uncertainty_key_raises(self, resolver):
        with pytest.raises(ValueError, match="missing key"):
            resolver.resolve(
                state_l0=_make_l0(),
                residual_l1=_make_l1(),
                feasibility_l2=_make_l2(),
                uncertainty_vector={"l0": 0.1, "l1": 0.1},
            )

    def test_out_of_range_uncertainty_raises(self, resolver):
        with pytest.raises(ValueError, match="must be float in"):
            resolver.resolve(
                state_l0=_make_l0(),
                residual_l1=_make_l1(),
                feasibility_l2=_make_l2(),
                uncertainty_vector={"l0": 1.5, "l1": 0.1, "l2": 0.1},
            )

    def test_none_uncertainty_raises(self, resolver):
        with pytest.raises(TypeError):
            resolver.resolve(
                state_l0=_make_l0(),
                residual_l1=_make_l1(),
                feasibility_l2=_make_l2(),
                uncertainty_vector=None,
            )


# ═══════════════════════════════════════════════════════════════
# 8) Step 1/2 集成冒烟
# ═══════════════════════════════════════════════════════════════

class TestIntegrationSmoke:
    """与 Ledger + Audit 的最小集成：仲裁结果可写入审计字段。"""

    def test_resolver_output_can_feed_audit_fields(self):
        """仲裁输出 → to_audit_fields → 结构合法。"""
        resolver = DisagreementResolver()
        r = resolver.resolve(
            state_l0=_make_l0("engaged"),
            residual_l1=_make_l1("push", 0.4),
            feasibility_l2=_make_l2(False, "blocked"),
            uncertainty_vector=_make_uv(0.5, 0.4, 0.3),
        )
        af = resolver.to_audit_fields(r)
        assert 0.0 <= af["meta_conflict_score"] <= 1.0
        assert 0.0 <= af["track_disagreement_level"] <= 1.0
        assert af["meta_conflict_alert_flag"] in (0, 1)

    def test_resolver_output_keys_are_stable(self, resolver):
        """输出字段名和类型稳定（合约对齐）。"""
        r = resolver.resolve(
            state_l0=_make_l0(),
            residual_l1=_make_l1(),
            feasibility_l2=_make_l2(),
            uncertainty_vector=_make_uv(),
        )
        required_keys = {
            "resolved_state", "intervention_intensity", "resolver_action",
            "resolver_reason_code", "disagreement_score", "dominant_layer",
            "resolver_policy_version", "meta_conflict_alert_flag",
        }
        assert set(r.keys()) == required_keys
        assert r["resolver_policy_version"] == RESOLVER_POLICY_VERSION
        assert isinstance(r["disagreement_score"], float)
        assert isinstance(r["meta_conflict_alert_flag"], int)
        # 合约要求 resolved_state 为 object
        assert isinstance(r["resolved_state"], dict)
        assert "status" in r["resolved_state"]
        # 合约要求 dominant_layer ∈ {L0, L1, L2, none}
        assert r["dominant_layer"] in ("L0", "L1", "L2", "none")

    def test_ledger_still_works(self):
        """Step 1 不受影响。"""
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
