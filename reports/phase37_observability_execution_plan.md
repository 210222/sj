# Phase 37 — 观测与审计补齐：执行计划（治理层补齐）

## 1. 文档目的
Phase 37 代码已在 Phase 36 收尾时同步实现。本文件为治理层补齐。

## 2. 权威 XML
- `283_phase37_orchestrator.xml`
- `284_s37_1_cost_sqlite.xml`
- `285_s37_2_audit_reports.xml`
- `286_s37_3_regression_close.xml`

## 3. 执行顺序
S37.1 cost_usd + SQLite → S37.2 audit reports → S37.3 regression

## 4. 代码实现面
| 交付 | 位置 |
|------|------|
| cost_usd | `src/coach/llm/schemas.py` RuntimeObservability |
| SQLite 持久化 | `api/services/dashboard_aggregator.py` persist_llm_observability() |
| 90 天清理 | `api/services/dashboard_aggregator.py` _cleanup_old_observability() |
| 评分趋势 | `run_experience_audit.py` _generate_score_trends() |
| 回归告警 | `run_experience_audit.py` _generate_regression_alerts() |
| 失败热力图 | `run_experience_audit.py` _generate_failure_patterns() |
