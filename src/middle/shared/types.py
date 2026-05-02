"""M1: 中圈跨模块共享类型定义（最小字段集）。"""

from typing import Literal, TypedDict


InterventionIntensity = Literal["full", "reduced", "minimal", "none"]
DominantLayer = Literal["L0", "L1", "L2", "none"]
ConflictLevel = Literal["low", "mid", "high"]
AuditLevel = Literal["pass", "p1_warn", "p1_freeze", "p0_block"]
GateDecision = Literal["GO", "WARN", "FREEZE"]
NoAssistLevel = Literal["independent", "partial", "dependent"]


class L0StateOutput(TypedDict):
    """resolver 合约最小消费字段。"""

    state: str
    dwell_time: float


class L1ResidualOutput(TypedDict):
    """resolver 合约最小消费字段。"""

    correction: str
    magnitude: float


class L2FeasibilityOutput(TypedDict):
    """resolver 合约最小消费字段。"""

    feasible: bool
    block_reason: str


class UncertaintyVector(TypedDict):
    """resolver 合约定义的不确定性向量。"""

    l0: float
    l1: float
    l2: float
