"""S7.1 MRT 微随机实验框架。

在低风险 flow 动作上实施微随机实验，贝叶斯估计因果效应。
"""

import random
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MRTConfig:
    """MRT 实验配置，默认值来自合约。"""
    randomization_rate: float = 0.2
    window_hours: int = 24
    eligible_action_types: tuple = ("challenge", "probe", "reflect", "scaffold")
    excluded_action_types: tuple = ("suggest", "defer")
    outcome_metrics: tuple = ("engagement_score", "completion_rate", "satisfaction_rating")
    min_sample_per_variant: int = 10
    confidence_level: float = 0.95

    @classmethod
    def from_dict(cls, d: dict) -> "MRTConfig":
        return cls(
            randomization_rate=d.get("randomization_rate", 0.2),
            window_hours=d.get("window_hours", 24),
            eligible_action_types=tuple(d.get("eligible_action_types",
                ["challenge", "probe", "reflect", "scaffold"])),
            outcome_metrics=tuple(d.get("outcome_metrics",
                ["engagement_score", "completion_rate", "satisfaction_rating"])),
            min_sample_per_variant=d.get("estimation", {}).get(
                "min_sample_per_variant", 10),
        )


@dataclass
class MRTAssignment:
    """单次 MRT 变体分配结果。"""
    variant_id: str | None = None
    variant_name: str | None = None
    is_variant: bool = False
    delta: float = 0.0
    dimension: str = "style"
    trace_id: str = ""
    window_id: str = ""
    assigned_at_utc: str = ""

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "variant_name": self.variant_name,
            "is_variant": self.is_variant,
            "delta": self.delta,
            "dimension": self.dimension,
            "trace_id": self.trace_id,
            "window_id": self.window_id,
            "assigned_at_utc": self.assigned_at_utc,
        }


class MRTExperiment:
    """MRT 实验管理器。"""

    VARIANTS = [
        {"id": "A", "name": "鼓励型", "delta": 0.2, "dimension": "style"},
        {"id": "B", "name": "反思型", "delta": -0.1, "dimension": "style"},
    ]

    def __init__(self, config: MRTConfig | None = None):
        self.config = config or MRTConfig()
        self._assignments: list[MRTAssignment] = []

    def current_window_id(self) -> str:
        now = datetime.now(timezone.utc)
        epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
        elapsed_hours = (now - epoch).total_seconds() / 3600
        window_index = int(elapsed_hours // self.config.window_hours)
        return f"win_{window_index:08d}"

    def _window_assignments(self, window_id: str) -> list[MRTAssignment]:
        return [a for a in self._assignments if a.window_id == window_id]

    def _window_variant_count(self, window_id: str) -> int:
        return sum(1 for a in self._window_assignments(window_id) if a.is_variant)

    def _window_total_count(self, window_id: str) -> int:
        return len(self._window_assignments(window_id))

    def eligible(self, action_type: str) -> bool:
        return action_type in self.config.eligible_action_types

    def assign(self, action_type: str, context: dict | None = None,
               trace_id: str = "") -> MRTAssignment:
        if not self.eligible(action_type):
            return MRTAssignment(
                variant_id=None, variant_name=None, is_variant=False,
                trace_id=trace_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )

        window_id = self.current_window_id()
        total = self._window_total_count(window_id)
        variants = self._window_variant_count(window_id)
        current_rate = variants / total if total > 0 else 0

        if current_rate >= self.config.randomization_rate:
            assignment = MRTAssignment(
                variant_id=None, variant_name=None, is_variant=False,
                trace_id=trace_id, window_id=window_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        elif random.random() < self.config.randomization_rate:
            variant = random.choice(self.VARIANTS)
            assignment = MRTAssignment(
                variant_id=variant["id"],
                variant_name=variant["name"],
                is_variant=True,
                delta=variant["delta"],
                dimension=variant["dimension"],
                trace_id=trace_id,
                window_id=window_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        else:
            assignment = MRTAssignment(
                variant_id=None, variant_name=None, is_variant=False,
                trace_id=trace_id, window_id=window_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )

        self._assignments.append(assignment)
        return assignment

    def window_stats(self, window_id: str | None = None) -> dict:
        wid = window_id or self.current_window_id()
        assigns = self._window_assignments(wid)
        total = len(assigns)
        variants = sum(1 for a in assigns if a.is_variant)
        return {
            "window_id": wid,
            "total_assignments": total,
            "variant_count": variants,
            "control_count": total - variants,
            "variant_rate": round(variants / total, 4) if total > 0 else 0.0,
        }


class BayesianEstimator:
    """贝叶斯因果效应估计器。Beta-Bernoulli 共轭先验。"""

    def __init__(self, alpha_prior: float = 1.0, beta_prior: float = 1.0):
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior

    def estimate_binary(self, variant_successes: int, variant_total: int,
                        control_successes: int, control_total: int) -> dict:
        a_v = self.alpha_prior + variant_successes
        b_v = self.beta_prior + variant_total - variant_successes
        a_c = self.alpha_prior + control_successes
        b_c = self.beta_prior + control_total - control_successes

        mean_v = a_v / (a_v + b_v)
        mean_c = a_c / (a_c + b_c)
        effect = mean_v - mean_c

        var_v = (a_v * b_v) / ((a_v + b_v) ** 2 * (a_v + b_v + 1)) if (a_v + b_v) > 0 else 0
        var_c = (a_c * b_c) / ((a_c + b_c) ** 2 * (a_c + b_c + 1)) if (a_c + b_c) > 0 else 0
        se = (var_v + var_c) ** 0.5
        ci_lower = effect - 1.96 * se
        ci_upper = effect + 1.96 * se

        overlap = self._posterior_overlap(a_v, b_v, a_c, b_c)

        return {
            "method": "beta_binomial",
            "variant_mean": round(mean_v, 4),
            "control_mean": round(mean_c, 4),
            "effect_size": round(effect, 4),
            "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
            "posterior_overlap": round(overlap, 4),
            "variant_n": variant_total,
            "control_n": control_total,
        }

    @staticmethod
    def _posterior_overlap(a1, b1, a2, b2, samples: int = 10000) -> float:
        """P(treatment > control) 的贝叶斯后验概率。

        对称化: 0.5=无差异, 1.0=完全重叠。
        """
        count = 0
        for _ in range(samples):
            s1 = random.betavariate(a1, b1)
            s2 = random.betavariate(a2, b2)
            if s1 > s2:
                count += 1
        return 2.0 * min(count / samples, 1.0 - count / samples)
