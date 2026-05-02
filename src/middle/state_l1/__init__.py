"""M3: L1 Shock/Memory/Trend 扰动残差层。

规则法实现——Shock 检测 + Memory 衰减 + Trend 方向 → correction + magnitude。
"""

from .estimator import L1Estimator

__all__ = ["L1Estimator"]
