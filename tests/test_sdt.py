"""S4.3 SDT 动机评估测试 — 8 tests。"""

import pytest
from src.coach.sdt import SDTAssessor, SDTProfile


class TestSDTProfile:
    def test_profile_clamps_range(self):
        p = SDTProfile(1.5, -0.1, 0.5)
        assert p.autonomy == 1.0
        assert p.competence == 0.0
        assert p.relatedness == 0.5

    def test_to_dict(self):
        p = SDTProfile(0.8, 0.6, 0.7, {"hint": "increase autonomy"})
        d = p.to_dict()
        assert d["autonomy"] == 0.8
        assert "hint" in d["advice"]


class TestSDTAssessor:
    def test_default_neutral_when_no_data(self):
        sdt = SDTAssessor()
        p = sdt.assess({})
        assert p.autonomy == 0.5
        assert p.competence == 0.5
        assert p.relatedness == 0.5

    def test_high_autonomy_from_rewrites(self):
        sdt = SDTAssessor()
        p = sdt.assess({"rewrite_rate": 0.8, "excursion_use_count": 3,
                        "initiation_rate": 0.7})
        assert p.autonomy > 0.5

    def test_low_autonomy(self):
        sdt = SDTAssessor()
        p = sdt.assess({"rewrite_rate": 0.0, "excursion_use_count": 0,
                        "initiation_rate": 0.1})
        assert p.autonomy < 0.5

    def test_high_competence(self):
        sdt = SDTAssessor()
        p = sdt.assess({"no_assist_scores": [0.8, 0.9, 0.85],
                        "task_completion_rate": 0.9, "difficulty_trend": 0.5})
        assert p.competence > 0.5

    def test_low_competence_generates_advice(self):
        sdt = SDTAssessor({"thresholds": {"competence_low": 0.5}})
        p = sdt.assess({"no_assist_scores": [0.1, 0.2],
                        "task_completion_rate": 0.3})
        assert "lower" in p.advice.get("adjust_difficulty", "")

    def test_advice_dominant_needs(self):
        sdt = SDTAssessor()
        p = sdt.assess({"rewrite_rate": 0.0, "no_assist_scores": [0.1],
                        "session_count": 0})
        assert len(p.advice["dominant_needs"]) >= 1
