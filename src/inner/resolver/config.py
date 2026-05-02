"""Step 4: L3 冲突仲裁器 — 可配置阈值与权重。"""

# 冲突分级阈值（合约定义：low < 0.3, mid [0.3, 0.7), high >= 0.7）
LOW_CONFLICT_THRESHOLD = 0.3
HIGH_CONFLICT_THRESHOLD = 0.7

# disagreement_score 合成权重（规则法，总和=1.0）
WEIGHT_STATE_INCONSISTENCY = 0.40   # L0/L1/L2 状态标签不一致度
WEIGHT_FEASIBILITY_CONFLICT = 0.35  # L2 可行性冲突度
WEIGHT_UNCERTAINTY = 0.25           # 不确定性水平

# 策略版本号
RESOLVER_POLICY_VERSION = "resolver_v1.0.0"
