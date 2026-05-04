"""S7.2 三诊断引擎。

升档（Gate → GO）前的强制三诊断：
1. 平衡性检验 — 变体组 vs 对照组基线可比
2. 负对照排除 — 已知无效干预不应检测出"效果"
3. 安慰剂窗口 — 真实干预前窗口不应检测出效果
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DiagnosticResult:
    """单次诊断结果。"""
    name: str
    passed: bool
    metric_value: float
    threshold: float
    detail: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "detail": self.detail,
            "data": self.data,
        }


@dataclass
class DiagnosticsReport:
    """三诊断综合报告。"""
    all_passed: bool
    balance: DiagnosticResult
    negative_control: DiagnosticResult
    placebo_window: DiagnosticResult
    evaluated_at_utc: str = ""

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "balance": self.balance.to_dict(),
            "negative_control": self.negative_control.to_dict(),
            "placebo_window": self.placebo_window.to_dict(),
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    def causal_diagnostics_triple(self) -> dict:
        """返回 gate 5 (causal_gate) 所需的指标值。"""
        return {
            "all_passed": self.all_passed,
            "balance_smd": self.balance.metric_value,
            "balance_pass": self.balance.passed,
            "negative_control_overlap": self.negative_control.metric_value,
            "negative_control_pass": self.negative_control.passed,
            "placebo_effect": self.placebo_window.metric_value,
            "placebo_pass": self.placebo_window.passed,
        }


class BalanceCheck:
    """平衡性检验：标准化均值差 (SMD)。"""

    def __init__(self, smd_threshold: float = 0.25):
        self.threshold = smd_threshold

    def evaluate(self, treatment_covariates: list[dict],
                 control_covariates: list[dict]) -> DiagnosticResult:
        if not treatment_covariates or not control_covariates:
            return DiagnosticResult(
                name="balance_check", passed=False, metric_value=1.0,
                threshold=self.threshold,
                detail="样本不足：变体组或对照组为空",
            )

        covariates = list(treatment_covariates[0].keys()) if treatment_covariates else []
        smd_values = {}

        for cov in covariates:
            t_vals = [d.get(cov, 0) for d in treatment_covariates if cov in d]
            c_vals = [d.get(cov, 0) for d in control_covariates if cov in d]
            if len(t_vals) < 2 or len(c_vals) < 2:
                continue

            mean_t = sum(t_vals) / len(t_vals)
            mean_c = sum(c_vals) / len(c_vals)
            var_t = sum((x - mean_t) ** 2 for x in t_vals) / (len(t_vals) - 1)
            var_c = sum((x - mean_c) ** 2 for x in c_vals) / (len(c_vals) - 1)
            pooled_std = ((var_t + var_c) / 2) ** 0.5
            # 防止零方差放大微小差异：epsilon 为两组均值平均的 5%
            epsilon = max(abs(mean_t), abs(mean_c), 0.01) * 0.05
            denominator = max(pooled_std, epsilon)
            smd = abs(mean_t - mean_c) / denominator
            smd_values[cov] = round(smd, 4)

        max_smd = max(smd_values.values()) if smd_values else 1.0
        passed = max_smd < self.threshold

        return DiagnosticResult(
            name="balance_check", passed=passed,
            metric_value=round(max_smd, 4), threshold=self.threshold,
            detail=f"最大 SMD={max_smd:.4f} (阈值={self.threshold}), {'通过' if passed else '不通过'}",
            data={"covariates": smd_values, "n_treatment": len(treatment_covariates),
                  "n_control": len(control_covariates)},
        )


class NegativeControlCheck:
    """负对照显著性排除。"""

    def __init__(self, overlap_threshold: float = 0.8, min_events: int = 5):
        self.threshold = overlap_threshold
        self.min_events = min_events

    def evaluate(self, sham_successes: int, sham_total: int,
                 control_successes: int, control_total: int) -> DiagnosticResult:
        if sham_total < self.min_events or control_total < self.min_events:
            return DiagnosticResult(
                name="negative_control", passed=True,
                metric_value=1.0, threshold=self.threshold,
                detail=f"样本不足（sham={sham_total}, control={control_total}），跳过负对照检查",
            )

        from src.coach.mrt import BayesianEstimator
        est = BayesianEstimator()
        result = est.estimate_binary(sham_successes, sham_total,
                                      control_successes, control_total)
        overlap = result["posterior_overlap"]
        passed = overlap >= self.threshold

        return DiagnosticResult(
            name="negative_control", passed=passed,
            metric_value=round(overlap, 4), threshold=self.threshold,
            detail=f"后验重叠={overlap:.4f} (阈值={self.threshold}), "
                   f"{'通过' if passed else '不通过 — 估计流程不可信'}",
            data={"bayesian_result": result},
        )


class PlaceboWindowCheck:
    """安慰剂窗口检查。"""

    def __init__(self, window_hours: float = 2.0, p_threshold: float = 0.05):
        self.window_hours = window_hours
        self.threshold = p_threshold

    def evaluate(self, pre_period_successes: int, pre_period_total: int,
                 control_successes: int, control_total: int) -> DiagnosticResult:
        if pre_period_total < 3 or control_total < 3:
            return DiagnosticResult(
                name="placebo_window", passed=True,
                metric_value=0.0, threshold=self.threshold,
                detail="样本不足，跳过安慰剂窗口检查",
            )

        from src.coach.mrt import BayesianEstimator
        est = BayesianEstimator()
        result = est.estimate_binary(pre_period_successes, pre_period_total,
                                      control_successes, control_total)
        effect = abs(result["effect_size"])
        overlap = result["posterior_overlap"]
        passed = effect < 0.1 or overlap > 0.8

        return DiagnosticResult(
            name="placebo_window", passed=passed,
            metric_value=round(effect, 4), threshold=0.1,
            detail=f"安慰剂效应={effect:.4f}, 后验重叠={overlap:.4f}, "
                   f"{'通过' if passed else '不通过 — 存在时间混淆'}",
            data={"bayesian_result": result, "window_hours": self.window_hours},
        )


class DiagnosticEngine:
    """三诊断引擎 — 组合三种诊断并输出综合报告。"""

    def __init__(self, smd_threshold: float = 0.25, overlap_threshold: float = 0.8,
                 placebo_window_hours: float = 2.0, min_control_events: int = 5):
        self.balance = BalanceCheck(smd_threshold)
        self.negative_control = NegativeControlCheck(overlap_threshold, min_control_events)
        self.placebo = PlaceboWindowCheck(placebo_window_hours)

    def run(self, treatment_covariates: list[dict],
            control_covariates: list[dict],
            sham_successes: int = 0, sham_total: int = 0,
            control_successes: int = 0, control_total: int = 0,
            pre_period_successes: int = 0, pre_period_total: int = 0,
            ) -> DiagnosticsReport:
        balance_result = self.balance.evaluate(treatment_covariates, control_covariates)
        negative_result = self.negative_control.evaluate(
            sham_successes, sham_total, control_successes, control_total)
        placebo_result = self.placebo.evaluate(
            pre_period_successes, pre_period_total, control_successes, control_total)

        all_passed = all([
            balance_result.passed,
            negative_result.passed,
            placebo_result.passed,
        ])

        return DiagnosticsReport(
            all_passed=all_passed,
            balance=balance_result,
            negative_control=negative_result,
            placebo_window=placebo_result,
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
        )
