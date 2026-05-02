"""M1: 中圈共享常量与枚举定义（跨模块单一真源）。"""

from typing import Final

# ── 中圈版本 ──────────────────────────────────────────────────
MIDDLE_SCHEMA_VERSION: Final[str] = "middle_v1.0.0"

# ── resolver 合约枚举 ─────────────────────────────────────────
INTERVENTION_INTENSITIES: Final[tuple[str, ...]] = (
    "full",
    "reduced",
    "minimal",
    "none",
)

DOMINANT_LAYERS: Final[tuple[str, ...]] = (
    "L0",
    "L1",
    "L2",
    "none",
)

CONFLICT_LEVELS: Final[tuple[str, ...]] = (
    "low",
    "mid",
    "high",
)

# ── audit 合约枚举 ────────────────────────────────────────────
AUDIT_LEVELS: Final[tuple[str, ...]] = (
    "pass",
    "p1_warn",
    "p1_freeze",
    "p0_block",
)

# ── gates 合约枚举 ────────────────────────────────────────────
GATE_DECISIONS: Final[tuple[str, ...]] = (
    "GO",
    "WARN",
    "FREEZE",
)

# ── no_assist 合约枚举 ───────────────────────────────────────
NO_ASSIST_LEVELS: Final[tuple[str, ...]] = (
    "independent",
    "partial",
    "dependent",
)

# ── 内圈只读桥接（不重定义） ───────────────────────────────────
from src.inner.audit import P0_FIELDS, P1_FIELDS  # noqa: E402
from src.inner.clock import WINDOW_SCHEMA_VERSION  # noqa: E402
