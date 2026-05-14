# Phase 36 — DeepSeek Context Caching 实证化 + 运行时可观测性：最终验收

## 1. 文档目的

本文件是 Phase 36 的正式 completion 归档。
Phase 36 已将 Phase 35 的 stable-prefix 设计，从"结构上应该有效"提升为"运行时可证、审计可复现、后续优化可比较"的正式证据链。

---

## 2. 执行摘要

| 子阶段 | 名称 | 核心交付 | 判定 |
|--------|------|----------|------|
| S36.1 | Runtime Instrumentation | 6 文件修改，34 observability 字段，3 dataclass 组 | GO |
| S36.2 | API/Admin/Dashboard Surfaces | 7 文件修改，3 endpoint，环形缓冲 | GO |
| S36.3 | Empirical Validation | 7 新 evidence 文件，5 新测试 | GO |
| S36.4 | Gate Verify and Close | 2 targeted 测试文件，completion 文档 | GO |

---

## 3. 产物清单

### 元提示词

| 文件 | 状态 |
|------|------|
| `meta_prompts/coach/260_phase36_orchestrator.xml` | 落盘 |
| `meta_prompts/coach/261_s36_1_runtime_instrumentation.xml` | 落盘 |
| `meta_prompts/coach/262_s36_2_api_admin_dashboard_surfaces.xml` | 落盘 |
| `meta_prompts/coach/263_s36_3_experience_audit_empirical_validation.xml` | 落盘 |
| `meta_prompts/coach/264_s36_4_gate_verify_close.xml` | 落盘 |

### 报告

| 文件 | 状态 |
|------|------|
| `reports/phase36_cache_observability_execution_plan.md` | 落盘 |
| `reports/phase36_cache_observability_completion.md` | 本文件 |

### Experience Audit Evidence（新增 7 个文件）

| Per-Run (3) | Cross-Run (4) |
|------|------|
| `llm_runtime_turns.json` — per-turn observability（20 fields × N turns）| `llm_cache_observability_manifest.json` — 定义与方法 |
| `llm_cache_evidence.json` — cache-eligible rate, prefix stability | `llm_cache_empirical_band.json` — cache-eligible 波动带 |
| `llm_observability_summary.json` — latency/token/path 聚合 | `llm_runtime_observability_summary.json` — 跨 run 汇总 |
| | `llm_prefix_stability_report.json` — prefix hash 稳定性 |

---

## 4. 新增 Observability 字段清单

### Cache Eligibility（11 字段）

```
cache_eligible, cache_eligibility_reason, stable_prefix_hash,
stable_prefix_chars, stable_prefix_lines, stable_prefix_share,
action_contract_hash, policy_layer_hash, context_layer_hash,
context_fingerprint, prefix_shape_version
```

### Runtime Call（15 字段）

```
path, streaming, request_started_at_utc, latency_ms,
first_chunk_latency_ms, stream_duration_ms, finish_reason,
response_model, tokens_total, tokens_prompt, tokens_completion,
token_usage_available, retry_count, timeout_s, transport_status
```

### Retention Observability（8 字段）

```
retention_history_hits, retention_memory_hits, retention_duplicate_dropped,
retention_budget_history_limit, retention_budget_memory_limit,
retention_progress_included, retention_context_summary_included, session_scoped
```

---

## 5. 实证证据总结

### Prefix Stability

| 指标 | 值 |
|------|-----|
| Unique prefix hashes across 2 runs | **1** |
| Stable across all runs | **True** |
| Hash value | `15620410...` |
| Interpretation | Stable prefix content is identical across runs — DeepSeek Context Caching 的结构条件已满足 |

### Cache Eligibility

| 指标 | 值 |
|------|-----|
| cache_eligible_rate | **1.0** (100%) |
| avg_stable_prefix_share | **0.4434** (44.3%) |
| Threshold | 400 chars / 15% share → 远超阈值 |
| Interpretation | 每次 LLM 调用都满足结构性缓存条件 |

### Runtime Performance

| 指标 | 值 |
|------|-----|
| avg_latency_ms | ~3700ms |
| avg_tokens_total | ~1250 |
| path_distribution | http_sync (primary) |
| transport_status | 100% "ok" |

### Sync / Stream Parity

| 维度 | 状态 |
|------|------|
| context_meta 同源 | ✅ 同一 `build_coach_context()` |
| schemas 共用 | ✅ `LLMObservability` / `CacheObservability` / `RuntimeObservability` |
| HTTP endpoint | ✅ `POST /api/v1/chat` → `llm_observability` |
| WS endpoint | ✅ `coach_stream_end` → `llm_observability` |
| Dashboard | ✅ `llm_runtime_summary` 聚合 |
| Admin | ✅ `GET /api/v1/admin/llm/runtime` |

---

## 6. 理论可命中 vs 实证证据（明确区分）

| 层次 | 内容 | 证据类型 |
|------|------|----------|
| **理论可命中** | stable_prefix ≥ 400 chars, share ≥ 15%, 跨 run hash 不变 | 结构性证据 |
| **实证支持** | 2 repeated runs, prefix hash stable, cache_eligible_rate=100% | repeated-run 实证 |
| **未知** | DeepSeek 内部是否真正命中缓存、cache-hit rate | Provider 内部，不在本阶段 scope |

Phase 36 **没有**声称"DeepSeek 已返回 cache-hit"。我们声称的是：
> 当前 LLM 上下文的结构性条件已满足 DeepSeek Context Caching 的理论要求，
> 且 repeated-run 实证支持该结构在运行中保持稳定。

---

## 7. Drift 检查清单

| 检查项 | 状态 |
|--------|------|
| provider/model/base_url 未变 | ✅ |
| scoring 维度未变 | ✅ |
| breakpoint probes 未变 | ✅ 25/25 passed across all runs |
| contracts/** 未动 | ✅ |
| src/inner/** 未动 | ✅ |
| src/middle/** 未动 | ✅ |
| src/outer/** 未动 | ✅ |
| sync/stream observability 一致 | ✅ |
| 已有 audit artifact 兼容 | ✅ scoring.json / all_turns.json / LATEST.json 完好 |
| stable_prefix_hash 同结构下稳定 | ✅ 1 unique hash across 2 runs |
| stream_end 含 path/latency/finish | ✅ |
| llm_generated=True 时 runtime evidence 不缺失 | ✅ |
| key 未写入仓库文件 | ✅ |

---

## 8. 全量回归

```
python -m pytest tests/ -q
1449 passed, 5 skipped in 96.47s
0 failed
```

新增测试：`test_phase36_llm_observability.py`（17 tests）+ `test_phase36_stream_runtime_parity.py`（7 tests）+ 扩展 `test_experience_audit.py`（5 tests）= **+29 tests**

---

## 9. 错误边界

| 修改面 | 文件数 | 风险等级 |
|------|--------|----------|
| src/coach/llm/ | 4 files | 中 — 核心 LLM 路径 |
| api/ | 5 files | 中 — API schema + endpoints |
| run_experience_audit.py | 1 file | 低 — 只新增 evidence 输出 |
| tests/ | 3 files | 低 — 只新增测试 |

所有修改均通过全量回归（1449 pass），0 行触及冻结层。

---

## 10. 最终结论

**Phase 36 判定：GO** ✅

### Phase 36 完成的三件事

1. **Runtime Instrumentation**：每次 sync/stream LLM 调用都产出结构化 runtime evidence（34 字段）
2. **API/Admin/Dashboard Surfaces**：HTTP/WS/admin/dashboard 共享同一套 observability 语义
3. **Empirical Validation**：repeated runs 实证了 stable-prefix 的稳定性 + cache-eligibility 的 100% 达标率

### Phase 37+ 可用的基础

- `llm_cache_observability_manifest.json` — cache 定义锚点
- `llm_cache_empirical_band.json` — cache-eligible 波动带
- `llm_prefix_stability_report.json` — prefix 稳定性量化结论
- `llm_runtime_observability_summary.json` — latency/token 汇总
- 每次 audit run 自动产出 3 个 per-run evidence 文件
- 环形缓冲 + dashboard/admin 端点提供实时 LLM runtime 可见性

---

**此文档由 Claude Code 在 Phase 36 完结后生成。**
**生成时间**: 2026-05-14T11:15:00Z
**基线版本**: V19.5 + Phase 36 cache observability freeze
