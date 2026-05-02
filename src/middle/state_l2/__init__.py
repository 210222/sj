"""M4: L2 COM-B 行为可行性估计层。

规则法实现——goal_clarity/resource_readiness/risk_pressure/constraint_conflict
→ feasibility + uncertainty → action_bias (advance/hold/defer)。
"""

from .estimator import L2Estimator

__all__ = ["L2Estimator"]
