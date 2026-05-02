"""M5: 双轨决策融合引擎。

融合 L0/L1/L2 + 不确定性 → intensity + dominant_layer + conflict_level。
"""

from .engine import DecisionEngine

__all__ = ["DecisionEngine"]
