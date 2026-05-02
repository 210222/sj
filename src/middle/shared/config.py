"""M1: 中圈共享配置常量。

将 config/parameters.yaml 的中圈参数代码化，
供 M2-M6 统一导入，避免硬编码散落。

────────────────────────────────────────────────────
版本分叉规则（schema vs config version）：
────────────────────────────────────────────────────

  MIDDLE_SCHEMA_VERSION（constants.py）:
    当且仅当以下情况必须升版：
      - 新增/删除/重命名枚举值
      - TypedDict key 集合变更（增/删/改名）
      - 跨模块接口类型漂移
      - P0/P1 字段分类变更
    影响范围：所有依赖模块（M2-M6）必须同步升级。

  MIDDLE_CONFIG_VERSION（本文件）:
    当且仅当以下情况必须升版：
      - 修改任何阈值/权重/窗口数值
      - 新增/删除配置常量
      - 调整整数下限（如 L0_MIN_SAMPLES）
    影响范围：仅消费该配置的模块，其他模块不受影响。

  两者可以独立升版，互不绑定。
  若同时涉及 schema 和 config 变更，两者必须同时升版。
────────────────────────────────────────────────────
"""

from typing import Final

# ── 中圈配置版本号 ─────────────────────────────────────────────
MIDDLE_CONFIG_VERSION: Final[str] = "middle_v1.0.0"

# ── L0 HBSSM 状态估计（config/parameters.yaml § state_estimation）───
L0_DWELL_MIN_SECONDS: Final[float] = 300.0
L0_SWITCH_PENALTY: Final[float] = 0.15
L0_HYSTERESIS_ENTRY: Final[float] = 0.70
L0_HYSTERESIS_EXIT: Final[float] = 0.50
L0_MIN_SAMPLES: Final[int] = 3

# ── L1 扰动残差 ────────────────────────────────────────────────
L1_SHOCK_THRESHOLD: Final[float] = 0.5
L1_MEMORY_DECAY_RATE: Final[float] = 0.05
L1_TREND_MIN_WINDOWS: Final[int] = 3

# ── L2 COM-B 行为可行性 ────────────────────────────────────────
L2_CAPABILITY_MIN: Final[float] = 0.3
L2_OPPORTUNITY_MIN: Final[float] = 0.3
L2_MOTIVATION_MIN: Final[float] = 0.3

# ── 双轨决策（config/parameters.yaml § decision）───────────────
DECISION_WEIGHT_TRANSFER: Final[float] = 0.40
DECISION_WEIGHT_CREATIVITY: Final[float] = 0.40
DECISION_WEIGHT_INDEPENDENCE: Final[float] = 0.20
DECISION_MAX_DELTA_PER_UPDATE: Final[float] = 0.05
DECISION_MIN_WEIGHT: Final[float] = 0.20
DECISION_UPDATE_WINDOW_DAYS: Final[int] = 14

# ── 双轨分歧处理 ───────────────────────────────────────────────
DECISION_LRM_WEIGHT: Final[float] = 0.6
DECISION_ROBUST_WEIGHT: Final[float] = 0.4
DECISION_CONFLICT_ESCALATE: Final[float] = 0.7

# ── 语义安全 ───────────────────────────────────────────────────
SEMANTIC_SAFETY_MIN_SCORE: Final[float] = 0.5
SEMANTIC_SAFETY_BLOCK_THRESHOLD: Final[float] = 0.3
