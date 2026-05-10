"""Phase 23: 间隔重复验证。"""
import time
from src.coach.flow import BKTEngine


class TestRetention:
    def setup_method(self):
        self.bkt = BKTEngine()

    def test_day0_equals_mastery(self):
        r = self.bkt.estimate_retention(0.8, 0)
        assert r == 0.8

    def test_retention_decays(self):
        r0 = self.bkt.estimate_retention(0.8, 0)
        r7 = self.bkt.estimate_retention(0.8, 7)
        r14 = self.bkt.estimate_retention(0.8, 14)
        assert r0 > r7 > r14, f"retention should decay: {r0} > {r7} > {r14}"

    def test_low_mastery_decays_fast(self):
        low = self.bkt.estimate_retention(0.3, 3)
        high = self.bkt.estimate_retention(0.9, 3)
        assert low < high

    def test_boundary_zero_mastery(self):
        r = self.bkt.estimate_retention(0.0, 7)
        # mastery=0.0 is clamped to 0.01 minimum, so retention ≈ 0.005
        assert r < 0.01, f"near-zero mastery should give near-zero retention, got {r}"

    def test_boundary_negative_days(self):
        r = self.bkt.estimate_retention(0.8, -1)
        assert r == 0.8

    def test_half_life_parameter(self):
        r7 = self.bkt.estimate_retention(0.8, 7, half_life=14)
        assert r7 > 0.5  # longer half-life = slower decay

    def test_near_threshold(self):
        r = self.bkt.estimate_retention(0.85, 5)
        # 5 days at half_life=7: 0.85*0.5^(5/7) ≈ 0.52
        assert r < 0.6, f"should be below review threshold, got {r}"
