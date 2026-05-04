"""S5.4 Domain Competence Passport 测试 — 10 tests。"""

import pytest
from src.coach.composer import PolicyComposer


class TestEvidenceLevel:
    def test_high_confidence_high_evidence(self):
        c = PolicyComposer()
        level = c._infer_evidence_level("programming",
                     {"confidence": 0.8, "feasible": True})
        assert level == "high"

    def test_low_confidence_low_evidence(self):
        c = PolicyComposer()
        level = c._infer_evidence_level("programming",
                     {"confidence": 0.2, "feasible": False})
        assert level == "low"

    def test_default_medium(self):
        c = PolicyComposer()
        level = c._infer_evidence_level("programming")
        assert level == "medium"


class TestPassport:
    def test_passport_has_required_keys(self):
        c = PolicyComposer()
        action = c.compose(intent="教教我怎么调试")
        p = action["domain_passport"]
        for key in ("domain", "evidence_level", "source_tag",
                     "epistemic_warning"):
            assert key in p, f"Missing passport key: {key}"

    def test_cross_domain_epistemic_warning(self):
        c = PolicyComposer()
        action = c.compose(intent="帮我写一篇关于AI的文章")
        p = action["domain_passport"]
        if p.get("epistemic_warning"):
            assert "跨越" in p["epistemic_warning"]


class TestEpistemicFusor:
    def test_low_evidence_high_confidence_triggers(self):
        c = PolicyComposer()
        payload = {"option": "你一定必须这样做", "difficulty": "high"}
        passport = {"domain": "programming", "evidence_level": "low",
                    "source_tag": "rule", "epistemic_warning": None}
        result, override = c._apply_epistemic_fusor(payload, passport, "你一定必须这样做")
        assert "_fusor_triggered" in result
        assert override == "reflect"

    def test_high_evidence_no_trigger(self):
        c = PolicyComposer()
        payload = {"option": "你一定必须这样做", "difficulty": "high"}
        passport = {"domain": "programming", "evidence_level": "high",
                    "source_tag": "rule", "epistemic_warning": None}
        result, override = c._apply_epistemic_fusor(payload, passport, "你一定必须这样做")
        assert "_fusor_triggered" not in result
        assert override is None

    def test_high_risk_domain_triggers(self):
        c = PolicyComposer()
        payload = {"option": "test", "difficulty": "high"}
        passport = {"domain": "mood", "evidence_level": "high",
                    "source_tag": "rule", "epistemic_warning": None}
        result, override = c._apply_epistemic_fusor(payload, passport, "test")
        assert "_fusor_triggered" in result
        assert override == "reflect"


class TestTransferTax:
    def test_cross_domain_reduces_difficulty(self):
        c = PolicyComposer()
        payload = {"option": "test", "difficulty": "high"}
        passport = {"domain": "programming", "evidence_level": "medium",
                    "source_tag": "rule",
                    "epistemic_warning": "此建议跨越了「writing」领域"}
        result = c._apply_transfer_tax(payload, passport)
        assert result["difficulty"] == "medium"

    def test_no_tax_within_domain(self):
        c = PolicyComposer()
        payload = {"option": "test", "difficulty": "high"}
        passport = {"domain": "programming", "evidence_level": "high",
                    "source_tag": "rule", "epistemic_warning": None}
        result = c._apply_transfer_tax(payload, passport)
        assert result["difficulty"] == "high"
