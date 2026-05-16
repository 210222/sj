# Phase 37 — 观测与审计补齐：完成归档

## 判定：GO ✅（于 Phase 39 全量回归中验证）

## 实际交付面

| 子阶段 | 交付 | 代码位置 |
|--------|------|---------|
| cost_usd 真实定价 | RuntimeObservability.cost_usd 计算属性 | `src/coach/llm/schemas.py` |
| SQLite 持久化 | llm_runtime_log 表 + persist_llm_observability() | `api/services/dashboard_aggregator.py` |
| 90 天清理 | _cleanup_old_observability(retention_days=90) | `api/services/dashboard_aggregator.py` |
| 评分趋势 | _generate_score_trends() | `run_experience_audit.py` |
| 回归告警 | _generate_regression_alerts() | `run_experience_audit.py` |
| 失败热力图 | _generate_failure_patterns() | `run_experience_audit.py` |

## 关键行为证据

- `cost_usd` 基于 DeepSeek 定价（cache_hit=$0.07/M, cache_miss=$0.27/M, output=$1.10/M）
- SQLite 90 天清理每 100 次写入触发一次
- audit 自动产出 score_trends.json / regression_alerts.json / failure_patterns.json

## 归档时间
2026-05-16（治理层补齐）
