"""Step 6: Eight Gates — 可调阈值与配置。"""

# ── 各门禁阈值 ─────────────────────────────────────────────────

# Gate 1: Agency Gate — premise_rewrite_rate >= 此值 → pass
AGENCY_GATE_THRESHOLD = 0.3

# Gate 2: Excursion Gate — 有效探索证据数 > 0 → pass
EXCURSION_MIN_EVIDENCE = 1

# Gate 3: Learning Gate — No-Assist 允许最大连续下降次数
LEARNING_MAX_CONSECUTIVE_DECLINE = 2

# Gate 4: Relational Gate — 各信号阈值
COMPLIANCE_PASSIVE_AGREEMENT_MAX = 0.3
COMPLIANCE_REWRITE_DECLINE_MAX = 0.3
COMPLIANCE_SELF_JUDGMENT_DECLINE_MAX = 0.3

# Gate 6: Audit Gate — P0 和 P1 阈值
AUDIT_P0_MAX = 0
AUDIT_P1_WARN_THRESHOLD = 0.01

# ── 聚合决策阈值 ───────────────────────────────────────────────

# gate_score == 0.0 → GO
# 0.0 < gate_score <= WARN_MAX → WARN
# gate_score > WARN_MAX → FREEZE
GATE_WARN_SCORE_MAX = 0.25   # 最多 2/8 门禁失败

# ── 规则版本 ──────────────────────────────────────────────────

GATES_RULE_VERSION = "gates_v1.0.0"
