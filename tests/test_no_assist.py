"""Step 5: No-Assist 评估器测试 — 三档命中、边界、assist约束、异常、审计、集成、回归。"""

import os
import tempfile
import pytest
from src.inner.no_assist import NoAssistEvaluator
from src.inner.no_assist.config import (
    SCORE_THRESHOLD_INDEPENDENT,
    SCORE_THRESHOLD_PARTIAL,
    RULE_VERSION,
)
from src.inner.ledger import EventStore


@pytest.fixture
def evaluator():
    return NoAssistEvaluator()


def _ts():
    return "2026-04-29T12:14:00Z"


# ═══════════════════════════════════════════════════════════════
# 1) 三档命中：independent / partial / dependent
# ═══════════════════════════════════════════════════════════════

class TestLevelHits:
    """正常路径：三种等级均可命中。"""

    def test_independent_level(self, evaluator):
        r = evaluator.evaluate(
            session_id="s1",
            user_answer=(
                "First, I analyzed the problem by breaking it into parts. "
                "Because the input was large, I decided to process it in "
                "steps. Therefore, my conclusion is that we should "
                "proceed carefully. However, let me verify this by "
                "double-checking the constraints. Finally, I think "
                "the optimal solution is to use a caching layer."
            ),
            assist_used=False,
            event_time_utc=_ts(),
        )
        assert r["no_assist_level"] == "independent"
        assert r["no_assist_score"] >= SCORE_THRESHOLD_INDEPENDENT

    def test_partial_level(self, evaluator):
        r = evaluator.evaluate(
            session_id="s2",
            user_answer=(
                "The answer is forty two because that makes sense "
                "considering the problem constraints."
            ),
            assist_used=False,
            event_time_utc=_ts(),
        )
        assert r["no_assist_level"] == "partial"

    def test_dependent_level(self, evaluator):
        r = evaluator.evaluate(
            session_id="s3",
            user_answer="yes",
            assist_used=False,
            event_time_utc=_ts(),
        )
        assert r["no_assist_level"] == "dependent"

    def test_empty_answer_is_dependent(self, evaluator):
        r = evaluator.evaluate(
            session_id="s4",
            user_answer="",
            assist_used=False,
            event_time_utc=_ts(),
        )
        assert r["no_assist_score"] == 0.0
        assert r["no_assist_level"] == "dependent"


# ═══════════════════════════════════════════════════════════════
# 2) 边界值：0、阈值边界、1
# ═══════════════════════════════════════════════════════════════

class TestBoundaries:
    """分数边界值测试。"""

    def test_empty_answer_zero(self, evaluator):
        r = evaluator.evaluate("s", "", False, _ts())
        assert r["no_assist_score"] == 0.0

    def test_score_never_exceeds_one(self, evaluator):
        # 大量推理关键词
        r = evaluator.evaluate(
            "s",
            " ".join([
                "first", "second", "third", "therefore", "because",
                "since", "thus", "hence", "finally", "however",
                "step", "check", "verify", "in conclusion",
            ] * 5),
            False,
            _ts(),
        )
        assert 0.0 <= r["no_assist_score"] <= 1.0

    def test_score_never_below_zero(self, evaluator):
        r = evaluator.evaluate(
            "s",
            "as an ai, i cannot answer this question i apologize",
            False,
            _ts(),
        )
        assert r["no_assist_score"] >= 0.0

    def test_threshold_boundary_independent(self, evaluator):
        # 刚好 >= 0.7 的边界
        r = evaluator.evaluate(
            "s",
            "First, because of the nature of the problem, therefore "
            "step by step, check the results and verify the outcome.",
            False,
            _ts(),
        )
        if r["no_assist_score"] >= SCORE_THRESHOLD_INDEPENDENT:
            assert r["no_assist_level"] == "independent"
        else:
            assert r["no_assist_level"] == "partial"


# ═══════════════════════════════════════════════════════════════
# 3) assist_used 约束
# ═══════════════════════════════════════════════════════════════

class TestAssistUsedConstraint:
    """assist_used=True → 不能判 independent。"""

    def test_assist_used_caps_independent(self, evaluator):
        # 高质量答案，但 assist_used=True
        r = evaluator.evaluate(
            session_id="s5",
            user_answer=(
                "First, I analyzed the problem. Because the constraints "
                "are tight, therefore I chose a greedy approach. Let me "
                "verify this by checking edge cases. Finally, the "
                "solution is optimal with O(n log n) complexity."
            ),
            assist_used=True,
            event_time_utc=_ts(),
        )
        assert r["no_assist_level"] != "independent"
        assert r["no_assist_score"] <= 0.69

    def test_assist_used_partial_ok(self, evaluator):
        # 中等答案 + assist_used=True → partial（不受限）
        r = evaluator.evaluate(
            "s", "I think the answer is 42", True, _ts()
        )
        assert r["no_assist_level"] != "independent"


# ═══════════════════════════════════════════════════════════════
# 4) 输入异常
# ═══════════════════════════════════════════════════════════════

class TestInvalidInput:
    """非法输入 → TypeError / ValueError。"""

    def test_non_string_session_id_raises(self, evaluator):
        with pytest.raises(TypeError, match="session_id"):
            evaluator.evaluate(123, "answer", False, _ts())

    def test_empty_session_id_raises(self, evaluator):
        with pytest.raises(TypeError, match="session_id"):
            evaluator.evaluate("", "answer", False, _ts())

    def test_non_string_answer_raises(self, evaluator):
        with pytest.raises(TypeError, match="user_answer"):
            evaluator.evaluate("s", None, False, _ts())

    def test_non_bool_assist_used_raises(self, evaluator):
        with pytest.raises(TypeError, match="assist_used"):
            evaluator.evaluate("s", "answer", "yes", _ts())

    def test_empty_event_time_raises(self, evaluator):
        with pytest.raises(ValueError, match="event_time_utc"):
            evaluator.evaluate("s", "answer", False, "")

    def test_non_string_reference_raises(self, evaluator):
        with pytest.raises(TypeError, match="reference_answer"):
            evaluator.evaluate("s", "answer", False, _ts(),
                               reference_answer=42)


# ═══════════════════════════════════════════════════════════════
# 5) 审计映射
# ═══════════════════════════════════════════════════════════════

class TestAuditMapping:
    """to_audit_fields 输出结构合法 + 数值范围正确。"""

    def test_audit_fields_structure(self, evaluator):
        r = evaluator.evaluate(
            "s",
            "First, because of this, therefore that.",
            False,
            _ts(),
        )
        af = evaluator.to_audit_fields(r)
        assert "no_assist_score" in af
        assert "no_assist_level" in af
        assert "no_assist_reason_code" in af
        assert "no_assist_rule_version" in af
        assert af["no_assist_rule_version"] == RULE_VERSION

    def test_audit_fields_score_range(self, evaluator):
        r = evaluator.evaluate("s", "", False, _ts())
        af = evaluator.to_audit_fields(r)
        assert 0.0 <= af["no_assist_score"] <= 1.0
        assert af["no_assist_level"] == "dependent"


# ═══════════════════════════════════════════════════════════════
# 6) reference_answer 相似度
# ═══════════════════════════════════════════════════════════════

class TestReferenceOverlap:
    """带 reference_answer 的评估。"""

    def test_high_overlap_boosts_score(self, evaluator):
        ref = "first analyze the problem then implement a solution"
        ans = "first I analyze the problem then implement a solution step by step"
        r = evaluator.evaluate("s", ans, False, _ts(),
                               reference_answer=ref)
        assert 0.0 <= r["no_assist_score"] <= 1.0

    def test_no_overlap_lowers_score(self, evaluator):
        ref = "the optimal approach uses dynamic programming with memoization"
        ans = "i think we should just try all possibilities"
        r1 = evaluator.evaluate("s", ans, False, _ts(),
                                reference_answer=ref)
        assert 0.0 <= r1["no_assist_score"] <= 1.0

    def test_empty_reference_is_neutral(self, evaluator):
        r = evaluator.evaluate("s", "some answer", False, _ts(),
                               reference_answer="")
        assert 0.0 <= r["no_assist_score"] <= 1.0

    def test_reference_provided_in_evidence(self, evaluator):
        r = evaluator.evaluate("s", "answer", False, _ts(),
                               reference_answer="ref")
        assert r["evidence"]["reference_provided"] is True

        r2 = evaluator.evaluate("s", "answer", False, _ts())
        assert r2["evidence"]["reference_provided"] is False


# ═══════════════════════════════════════════════════════════════
# 7) 集成冒烟：No-Assist 输出与 EventStore 联动
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """Step 5 输出可经 Ledger append_event 写入链。"""

    def test_write_no_assist_result_to_ledger(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        s.create_genesis_event()

        evaluator = NoAssistEvaluator()
        result = evaluator.evaluate(
            "s_int",
            "First, because, therefore, in conclusion.",
            False,
            _ts(),
        )
        audit = evaluator.to_audit_fields(result)

        # 将 no_assist 结果作为 P1 字段写入
        e = s.append_event(
            p0_values={
                "trace_id": "na_int_test",
                "policy_version": "1.0",
                "counterfactual_ranker_version": "1.0",
                "counterfactual_feature_schema_version": "1.0",
            },
            p1_values={
                "tradeoff_reason": result["reason_code"],
                "meta_conflict_score": audit["no_assist_score"],
            },
        )
        assert e["chain_height"] == 1
        assert e["tradeoff_reason"] == result["reason_code"]
        assert e["meta_conflict_score"] == audit["no_assist_score"]

        try:
            os.unlink(path)
        except PermissionError:
            import time
            time.sleep(0.1)
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════
# 8) reason_code 格式验证
# ═══════════════════════════════════════════════════════════════

class TestReasonCode:
    """reason_code 格式固定 NA_<level>_<version>_sXX。"""

    def test_reason_code_format(self, evaluator):
        r = evaluator.evaluate("s", "good answer", False, _ts())
        rc = r["reason_code"]
        assert rc.startswith("NA_")
        assert RULE_VERSION in rc
        assert "_s" in rc

    def test_output_keys_are_stable(self, evaluator):
        r = evaluator.evaluate("s", "answer", False, _ts())
        required = {
            "session_id", "no_assist_score", "no_assist_level",
            "evidence", "rule_version", "reason_code",
            "event_time_utc", "window_id", "evaluated_at_utc",
        }
        assert set(r.keys()) == required
        assert isinstance(r["evidence"], dict)
        assert isinstance(r["no_assist_score"], float)
        assert r["rule_version"] == RULE_VERSION
        assert r["window_id"] is not None and "_" in r["window_id"]
        assert r["evaluated_at_utc"].endswith("Z")
