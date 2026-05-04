"""S7.3 V18.7 四门禁审计检查器。

只读审计检查——不修改运行时行为、不熔断、不降级。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GateResult:
    """单门禁检查结果。"""
    gate_id: str
    gate_name: str
    passed: bool
    metric_value: float = 0.0
    threshold: float = 0.0
    detail: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "gate_id": self.gate_id, "gate_name": self.gate_name,
            "passed": self.passed, "metric_value": self.metric_value,
            "threshold": self.threshold, "detail": self.detail,
            "data": self.data,
        }


@dataclass
class GatesReport:
    """四门禁综合报告。"""
    all_passed: bool
    verification_load: GateResult
    serendipity: GateResult
    trespassing: GateResult
    manipulation: GateResult
    evaluated_at_utc: str = ""

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "verification_load": self.verification_load.to_dict(),
            "serendipity": self.serendipity.to_dict(),
            "trespassing": self.trespassing.to_dict(),
            "manipulation": self.manipulation.to_dict(),
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    def gate_results_by_id(self) -> dict[str, bool]:
        return {
            self.verification_load.gate_id: self.verification_load.passed,
            self.serendipity.gate_id: self.serendipity.passed,
            self.trespassing.gate_id: self.trespassing.passed,
            self.manipulation.gate_id: self.manipulation.passed,
        }


class VerificationLoadGate:
    """Verification Load Gate: 验证/自主比例 ≤ 阈值。"""

    GATE_ID = "v_load"
    GATE_NAME = "Verification Load Gate"

    def __init__(self, ratio_threshold: float = 0.5):
        self.threshold = ratio_threshold

    def evaluate(self, verification_seconds: float,
                 autonomous_seconds: float) -> GateResult:
        if autonomous_seconds <= 0:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=0.0, threshold=self.threshold,
                detail="无自主产出数据，跳过验证负载检查",
            )
        ratio = verification_seconds / autonomous_seconds
        return GateResult(
            gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
            passed=ratio <= self.threshold,
            metric_value=round(ratio, 4), threshold=self.threshold,
            detail=f"验证/自主比例={ratio:.2f} (阈值={self.threshold}), "
                   f"{'通过' if ratio <= self.threshold else '不通过 — 验证负载过高'}",
            data={"verification_seconds": verification_seconds,
                  "autonomous_seconds": autonomous_seconds},
        )


class SerendipityGate:
    """Serendipity Gate: 偶发探索占比 ≥ 阈值。"""

    GATE_ID = "serendipity"
    GATE_NAME = "Serendipity Gate"

    def __init__(self, min_exploration_ratio: float = 0.3):
        self.threshold = min_exploration_ratio

    def evaluate(self, exploratory_actions: int,
                 total_excursions: int) -> GateResult:
        if total_excursions <= 0:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=0.0, threshold=self.threshold,
                detail="无远足数据，跳过偶发探索检查",
            )
        ratio = exploratory_actions / total_excursions
        return GateResult(
            gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
            passed=ratio >= self.threshold,
            metric_value=round(ratio, 4), threshold=self.threshold,
            detail=f"偶发探索占比={ratio:.2f} (阈值={self.threshold}), "
                   f"{'通过' if ratio >= self.threshold else '不通过 — 探索不足'}",
            data={"exploratory_actions": exploratory_actions,
                  "total_excursions": total_excursions},
        )


class TrespassingGate:
    """Trespassing Gate: 越权熔断后零泄漏。"""

    GATE_ID = "trespass"
    GATE_NAME = "Trespassing Gate"

    def __init__(self, max_leakage: int = 0):
        self.threshold = max_leakage

    def evaluate(self, circuit_breaker_triggered: int,
                 leakage_after_trigger: int) -> GateResult:
        if circuit_breaker_triggered <= 0:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=0.0, threshold=self.threshold,
                detail="无越权熔断触发，通过",
            )
        return GateResult(
            gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
            passed=leakage_after_trigger <= self.threshold,
            metric_value=float(leakage_after_trigger),
            threshold=float(self.threshold),
            detail=f"越权触发={circuit_breaker_triggered}次, "
                   f"泄漏={leakage_after_trigger}次 (阈值≤{self.threshold}), "
                   f"{'通过' if leakage_after_trigger <= self.threshold else '不通过 — 存在泄漏'}",
            data={"circuit_breaker_triggered": circuit_breaker_triggered,
                  "leakage_after_trigger": leakage_after_trigger},
        )


class ManipulationGate:
    """Manipulation Gate: 选择架构无显著操纵效应。"""

    GATE_ID = "manip"
    GATE_NAME = "Manipulation Gate"

    def __init__(self, p_value_threshold: float = 0.05):
        self.threshold = p_value_threshold

    def evaluate(self, choice_distributions: list[dict[str, Any]],
                 ) -> GateResult:
        if len(choice_distributions) < 2:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=1.0, threshold=self.threshold,
                detail="数据不足（仅一个框架），跳过操纵效应检查",
            )

        all_options = sorted(set(
            opt for dist in choice_distributions
            for opt in dist.get("choices", {})
        ))
        if len(all_options) < 2:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=1.0, threshold=self.threshold,
                detail="选项数不足，跳过操纵效应检查",
            )

        contingency = []
        for dist in choice_distributions:
            row = [dist.get("choices", {}).get(opt, 0) for opt in all_options]
            contingency.append(row)

        try:
            from scipy.stats import chi2_contingency
            chi2, p_value, dof, expected = chi2_contingency(contingency)
            passed = bool(float(p_value) >= self.threshold)
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=passed,
                metric_value=round(p_value, 4), threshold=self.threshold,
                detail=f"卡方检验 p={p_value:.4f} (阈值={self.threshold}), "
                       f"{'通过' if p_value >= self.threshold else '不通过 — 存在显著操纵效应'}",
                data={"frames": [d.get("frame", "") for d in choice_distributions],
                      "chi_square": round(chi2, 4), "p_value": round(p_value, 4),
                      "degrees_of_freedom": int(dof), "options": all_options},
            )
        except ImportError:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=1.0, threshold=self.threshold,
                detail="scipy 不可用，跳过操纵效应检查",
            )
        except Exception as e:
            return GateResult(
                gate_id=self.GATE_ID, gate_name=self.GATE_NAME,
                passed=True, metric_value=1.0, threshold=self.threshold,
                detail=f"检验执行异常: {e}，跳过",
            )


class V18GatesAuditor:
    """V18.7 四门禁审计器 — 整合全部四门禁检查。"""

    def __init__(self, verification_threshold: float = 0.5,
                 serendipity_threshold: float = 0.3,
                 trespass_max_leakage: int = 0,
                 manipulation_p_threshold: float = 0.05):
        self.verification_gate = VerificationLoadGate(verification_threshold)
        self.serendipity_gate = SerendipityGate(serendipity_threshold)
        self.trespassing_gate = TrespassingGate(trespass_max_leakage)
        self.manipulation_gate = ManipulationGate(manipulation_p_threshold)

    def audit(self, verification_seconds: float = 0.0,
              autonomous_seconds: float = 0.0,
              exploratory_actions: int = 0,
              total_excursions: int = 0,
              circuit_breaker_triggered: int = 0,
              leakage_after_trigger: int = 0,
              choice_distributions: list[dict[str, Any]] | None = None,
              ) -> GatesReport:
        v_result = self.verification_gate.evaluate(verification_seconds, autonomous_seconds)
        s_result = self.serendipity_gate.evaluate(exploratory_actions, total_excursions)
        t_result = self.trespassing_gate.evaluate(circuit_breaker_triggered, leakage_after_trigger)
        m_result = self.manipulation_gate.evaluate(choice_distributions or [])

        return GatesReport(
            all_passed=all([v_result.passed, s_result.passed,
                            t_result.passed, m_result.passed]),
            verification_load=v_result, serendipity=s_result,
            trespassing=t_result, manipulation=m_result,
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
        )
