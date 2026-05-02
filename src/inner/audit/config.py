"""Step 2 审计阈值 — 来自 config/parameters.yaml 的同源常量。"""

WARN_THRESHOLD = 0.01    # P1 缺失率 > 1%  触发 ALERT
FREEZE_THRESHOLD = 0.03  # P1 缺失率 > 3%  触发 FREEZE_SCALE
