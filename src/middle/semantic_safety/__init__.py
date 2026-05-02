"""M6: 语义安全层。

对中圈决策结果做最终语义闸门：P0 硬阻断 + P1/gate 联合降级 + safety_score 阈值。
"""

from .engine import SemanticSafetyEngine

__all__ = ["SemanticSafetyEngine"]
