"""M2: L0 HBSSM 状态估计层。

滞回状态稳定性模型（Hysteresis-Based State Stability Model）。
规则法实现——输入信号 → 复合分 → 滞回状态判定 → L0StateOutput。
"""

from .estimator import L0Estimator

__all__ = ["L0Estimator"]
