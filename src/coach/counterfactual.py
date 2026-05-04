"""情境反事实仿真引擎 — 三假设推演 + 风险标记。

语义安全三件套第一道闸门：对每个候选 DSL 动作包生成 3 种假设历史。
"""

from dataclasses import dataclass, field


@dataclass
class CounterfactualHypothesis:
    """一条反事实假设。"""
    name: str
    description: str
    delta_score: float          # 相对于基线的变化量 [-1, 1]
    risk_flagged: bool          # 是否标记为风险
    details: dict = field(default_factory=dict)


class CounterfactualSimulator:
    """三假设反事实仿真引擎。

    simulate(action, user_context) → dict
    """

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._sim_cfg = self._config.get("simulation", {})

    def simulate(self, action: dict, user_context: dict | None = None) -> dict:
        """对 DSL 动作进行反事实仿真。

        Returns keys: risk_flagged, risk_score, hypotheses,
                      baseline_score, recommendation
        """
        ctx = user_context or {}

        # 基线得分：从 action 的证据级别或用户状态推断
        dp = action.get("domain_passport", {})
        evidence_map = {"high": 0.8, "medium": 0.5, "low": 0.3, "none": 0.1}
        baseline = evidence_map.get(dp.get("evidence_level", "medium"), 0.5)
        baseline = ctx.get("baseline_score", baseline)

        threshold = self._sim_cfg.get("deterioration_threshold", 0.3)

        # 生成假设
        raw_hypotheses = self._generate_hypotheses(action, ctx)

        # 推演
        hypotheses = [
            self._simulate_hypothesis(h, baseline, threshold)
            for h in raw_hypotheses
        ]

        # 任一假设标记风险 → 整体风险
        risk_flagged = any(h.risk_flagged for h in hypotheses)

        # 综合风险评分
        weights = self._config.get("weights", {})
        risk_score = self._compute_risk_score(hypotheses, weights)

        recommendation = self._recommend(risk_flagged, risk_score)

        return {
            "risk_flagged": risk_flagged,
            "risk_score": risk_score,
            "hypotheses": [
                {
                    "name": h.name,
                    "description": h.description,
                    "delta_score": h.delta_score,
                    "risk_flagged": h.risk_flagged,
                    "details": h.details,
                }
                for h in hypotheses
            ],
            "baseline_score": round(baseline, 4),
            "recommendation": recommendation,
        }

    # ── 内部 ──────────────────────────────────────────────────────

    @staticmethod
    def _generate_hypotheses(action: dict, ctx: dict) -> list[dict]:
        return [
            {
                "name": "best_case",
                "description": "用户未经历上次挫折（最佳历史）",
                "base_adjustment": 0.2,
                "risk_multiplier": 0.5,
            },
            {
                "name": "worst_case",
                "description": "用户当前疲劳加重（最差历史）",
                "base_adjustment": -0.3,
                "risk_multiplier": 1.5,
            },
            {
                "name": "alt_path",
                "description": "用户选择完全不同路径（替换历史）",
                "base_adjustment": -0.1,
                "risk_multiplier": 1.2,
            },
        ]

    def _simulate_hypothesis(self, hypothesis: dict, baseline: float,
                              threshold: float) -> CounterfactualHypothesis:
        adj = hypothesis["base_adjustment"]
        hypo_score = max(0.0, min(1.0, baseline + adj))
        risk = (baseline - hypo_score) > threshold
        return CounterfactualHypothesis(
            name=hypothesis["name"],
            description=hypothesis["description"],
            delta_score=round(hypo_score - baseline, 4),
            risk_flagged=risk,
            details={"hypothesis_score": round(hypo_score, 4)},
        )

    @staticmethod
    def _compute_risk_score(hypotheses: list[CounterfactualHypothesis],
                            weights: dict) -> float:
        """综合风险得分 [0,1]。

        risk_contrib = weight * (0.5 - delta_score)
        负 delta（worst_case）→ 高贡献，正 delta（best_case）→ 低贡献。
        """
        w_best = weights.get("best_case", 0.3)
        w_worst = weights.get("worst_case", 0.4)
        w_alt = weights.get("alt_path", 0.3)
        w_map = {"best_case": w_best, "worst_case": w_worst, "alt_path": w_alt}
        total = 0.0
        for h in hypotheses:
            weight = w_map.get(h.name, 0.33)
            risk_contrib = weight * (0.5 - h.delta_score)
            total += risk_contrib
        return round(max(0.0, min(1.0, total)), 4)

    @staticmethod
    def _recommend(risk_flagged: bool, risk_score: float) -> str:
        if risk_flagged and risk_score > 0.6:
            return "block"
        elif risk_flagged:
            return "caution"
        return "proceed"
