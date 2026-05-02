"""M1: 中圈共享配置与类型中心。

────────────────────────────────────────────────────
子域导入规范（M2-M6 及外部消费者请遵守）：
────────────────────────────────────────────────────

  按需分层导入，优先使用子域路径而非顶层 re-export：

    from src.middle.shared.constants import (...  枚举、内圈桥接)
    from src.middle.shared.types import (...      Literal 类型、TypedDict)
    from src.middle.shared.config import (...     阈值常量)
    from src.middle.shared.exceptions import (... 异常类)

  仅在需要一次性导入多子域时才用顶层包路径。

────────────────────────────────────────────────────
"""

from .constants import (
    MIDDLE_SCHEMA_VERSION,
    INTERVENTION_INTENSITIES,
    DOMINANT_LAYERS,
    CONFLICT_LEVELS,
    AUDIT_LEVELS,
    GATE_DECISIONS,
    NO_ASSIST_LEVELS,
    P0_FIELDS,
    P1_FIELDS,
    WINDOW_SCHEMA_VERSION,
)
from .types import (
    InterventionIntensity,
    DominantLayer,
    ConflictLevel,
    AuditLevel,
    GateDecision,
    NoAssistLevel,
    L0StateOutput,
    L1ResidualOutput,
    L2FeasibilityOutput,
    UncertaintyVector,
)
from .config import (
    MIDDLE_CONFIG_VERSION,
    L0_DWELL_MIN_SECONDS,
    L0_SWITCH_PENALTY,
    L0_HYSTERESIS_ENTRY,
    L0_HYSTERESIS_EXIT,
    L0_MIN_SAMPLES,
    L1_SHOCK_THRESHOLD,
    L1_MEMORY_DECAY_RATE,
    L1_TREND_MIN_WINDOWS,
    L2_CAPABILITY_MIN,
    L2_OPPORTUNITY_MIN,
    L2_MOTIVATION_MIN,
    DECISION_WEIGHT_TRANSFER,
    DECISION_WEIGHT_CREATIVITY,
    DECISION_WEIGHT_INDEPENDENCE,
    DECISION_MAX_DELTA_PER_UPDATE,
    DECISION_MIN_WEIGHT,
    DECISION_UPDATE_WINDOW_DAYS,
    DECISION_LRM_WEIGHT,
    DECISION_ROBUST_WEIGHT,
    DECISION_CONFLICT_ESCALATE,
    SEMANTIC_SAFETY_MIN_SCORE,
    SEMANTIC_SAFETY_BLOCK_THRESHOLD,
)
from .exceptions import (
    MiddlewareError,
    ContractViolationError,
    StateEstimationError,
    SemanticSafetyError,
    DecisionRejectedError,
)

__all__ = [
    "MIDDLE_SCHEMA_VERSION",
    "INTERVENTION_INTENSITIES",
    "DOMINANT_LAYERS",
    "CONFLICT_LEVELS",
    "AUDIT_LEVELS",
    "GATE_DECISIONS",
    "NO_ASSIST_LEVELS",
    "P0_FIELDS",
    "P1_FIELDS",
    "WINDOW_SCHEMA_VERSION",
    "InterventionIntensity",
    "DominantLayer",
    "ConflictLevel",
    "AuditLevel",
    "GateDecision",
    "NoAssistLevel",
    "L0StateOutput",
    "L1ResidualOutput",
    "L2FeasibilityOutput",
    "UncertaintyVector",
    "MIDDLE_CONFIG_VERSION",
    "L0_DWELL_MIN_SECONDS",
    "L0_SWITCH_PENALTY",
    "L0_HYSTERESIS_ENTRY",
    "L0_HYSTERESIS_EXIT",
    "L0_MIN_SAMPLES",
    "L1_SHOCK_THRESHOLD",
    "L1_MEMORY_DECAY_RATE",
    "L1_TREND_MIN_WINDOWS",
    "L2_CAPABILITY_MIN",
    "L2_OPPORTUNITY_MIN",
    "L2_MOTIVATION_MIN",
    "DECISION_WEIGHT_TRANSFER",
    "DECISION_WEIGHT_CREATIVITY",
    "DECISION_WEIGHT_INDEPENDENCE",
    "DECISION_MAX_DELTA_PER_UPDATE",
    "DECISION_MIN_WEIGHT",
    "DECISION_UPDATE_WINDOW_DAYS",
    "DECISION_LRM_WEIGHT",
    "DECISION_ROBUST_WEIGHT",
    "DECISION_CONFLICT_ESCALATE",
    "SEMANTIC_SAFETY_MIN_SCORE",
    "SEMANTIC_SAFETY_BLOCK_THRESHOLD",
    "MiddlewareError",
    "ContractViolationError",
    "StateEstimationError",
    "SemanticSafetyError",
    "DecisionRejectedError",
]
