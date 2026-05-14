# Phase 36 — DeepSeek Context Caching 实证化 + 运行时可观测性：执行计划

## 1. 文档目的

本文件是 Phase 36 的执行 runbook + 验收标准。

Phase 36 的目标不是重构 prompt 结构（Phase 35 已完成），而是将 stable-prefix 设计从"结构上应该有效"提升为"运行时可证、审计可复现、后续优化可比较"的正式证据链。

---

## 2. 权威 XML 层

| 文件 | 用途 |
|------|------|
| `meta_prompts/coach/260_phase36_orchestrator.xml` | 总控编排 |
| `meta_prompts/coach/261_s36_1_runtime_instrumentation.xml` | Runtime instrumentation per call |
| `meta_prompts/coach/262_s36_2_api_admin_dashboard_surfaces.xml` | API / admin / dashboard surfaces |
| `meta_prompts/coach/263_s36_3_experience_audit_empirical_validation.xml` | Empirical validation via repeated runs |
| `meta_prompts/coach/264_s36_4_gate_verify_close.xml` | Gate verify and close |

---

## 3. 全局边界

### 禁止修改
- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `src/outer/**`
- provider / model / base_url
- Phase 32 scoring 维度与 breakpoint probes

### 禁止漂移
- 禁止把结构性 cache-eligibility 伪装成 provider-confirmed cache-hit telemetry
- 禁止 sync / stream 只改一边形成新的可观测性分叉
- 禁止覆盖已有 baseline / comparison / scoring 文件语义
- 禁止将 observability phase 扩展为 prompt redesign phase

---

## 4. 执行顺序

```
S36.1 (Runtime Instrumentation) → S36.2 (API/Admin/Dashboard) → S36.3 (Empirical Validation) → S36.4 (Gate Verify)
```

---

## 5. 子阶段详细说明

### S36.1 — Runtime Instrumentation

**目标**：为每次 sync / stream LLM 调用记录统一的 runtime evidence。

**主要修改面**：
- `src/coach/llm/client.py` — generate() / generate_stream() 附加 runtime 证据
- `src/coach/llm/schemas.py` — LLMResponse 扩展 observability 字段
- `src/coach/llm/prompts.py` — context_meta 扩展 cache-eligibility 字段
- `src/coach/agent.py` — _build_llm_context_bundle() 收集传递 observability
- `src/coach/llm/memory_context.py` — build_retention_bundle() 附加 retention 指标
- `api/services/coach_bridge.py` — chat_stream() 收集暴露 observability

**新增 observability 字段分组**：
1. **Cache eligibility**（11 字段）：cache_eligible, stable_prefix_hash, context_fingerprint, layer hashes, prefix_shape_version 等
2. **Runtime call**（15 字段）：path, streaming, latency_ms, first_chunk_latency_ms, tokens_*, transport_status 等
3. **Retention observability**（8 字段）：retention_history_hits, retention_memory_hits, retention_duplicate_dropped 等

**GO 标准**：
- sync path 每次成功调用返回 observability 核心字段
- stream path stream_end 返回同一套核心字段
- hash/latency/token 逻辑语义成立且稳定

---

### S36.2 — API / Admin / Dashboard Surfaces

**目标**：将 S36.1 的 runtime evidence 暴露到对外 API 和内部运维面。

**主要修改面**：
- `api/models/schemas.py` — ChatMessageResponse 扩展 llm_observability
- `api/models/websocket.py` — coach_stream_end event 扩展
- `api/routers/chat.py` — 返回 llm_observability
- `api/services/coach_bridge.py` — stream_end 附加 llm_observability
- `api/services/dashboard_aggregator.py` — 汇总统计
- `api/routers/dashboard.py` — 暴露聚合数据
- `api/routers/admin.py` — 暴露 LLM runtime 汇总

**设计要求**：
- 统一对象名 `llm_observability`（cache / runtime / retention 三组）
- HTTP 与 WS end-event 共享同一套核心字段
- dashboard / admin 只暴露聚合统计，不暴露全量原始 trace
- 旧字段（llm_generated / llm_model / llm_tokens）保持向后兼容

**GO 标准**：
- HTTP 与 WS 可见统一 observability 核心
- admin / dashboard 能汇总 LLM runtime 行为
- 旧消费者不因新增字段破坏兼容性

---

### S36.3 — Experience Audit Empirical Validation

**目标**：将 cache-friendly 设计从结构推断升级为 repeated runs 的证据链。

**主要修改面**：
- `run_experience_audit.py` — 扩展收集 observability；产出新 artifacts
- `tests/test_experience_audit.py` — 扩展覆盖新 artifact 生成

**Per-run evidence**（新增 3 个文件）：
- `llm_runtime_turns.json` — 每轮次的 observability 完整数据
- `llm_cache_evidence.json` — cache_eligible rate / prefix_hash 汇总
- `llm_observability_summary.json` — runtime 聚合

**Cross-run evidence**（新增 4 个文件）：
- `llm_cache_observability_manifest.json`
- `llm_cache_empirical_band.json`
- `llm_runtime_observability_summary.json`
- `llm_prefix_stability_report.json`

**关键区分**：本阶段验证的是"结构上 cache-friendly + repeated evidence 支持"，不是 provider 明确承认 hit/miss。

**GO 标准**：
- repeated runs 可生成正式 cache/latency/token observability artifacts
- prefix stability 可被报告化
- sync / stream 差异可被实证展示

---

### S36.4 — Gate Verify and Close

**目标**：完成 targeted suites + full regression + completion 收口。

**新增/扩展测试**：
- `tests/test_phase36_llm_observability.py`
- `tests/test_phase36_stream_runtime_parity.py`
- 扩展 `tests/test_experience_audit.py`
- 扩展 `tests/test_llm_client.py`

**必须验证**：
- 相同结构下 stable_prefix_hash 稳定
- suffix 变化不改变 stable_prefix_hash
- sync / stream observability 核心一致
- audit artifacts 完整
- 已有 baseline / comparison / scoring 文件未破坏

**Drift 监控**（4 类）：
1. Hard drift — 立即 NO-GO（provider/scoring/冻结层改动、sync/stream 分叉）
2. Structural drift — stable_prefix_hash 不稳定、cache_eligible 异常翻转
3. Observability drift — llm_generated=True 但 runtime evidence 缺失
4. Empirical drift — cache-eligible rate 过低、latency 恶化、token 膨胀

**GO 标准**：
- targeted suites 全绿
- repeated audit runs 产物完备
- full regression 通过
- completion 文档明确区分理论可命中与实证证据

---

## 6. 最终验收标准

### A 类：Runtime instrumentation
- [ ] sync 每次调用返回完整 observability
- [ ] stream stream_end 返回同一套 observability
- [ ] stable_prefix_hash 同结构下稳定

### B 类：API / admin / dashboard
- [ ] HTTP + WS 双向可见
- [ ] admin / dashboard 聚合可用
- [ ] 向后兼容无破坏

### C 类：Empirical validation
- [ ] per-run 3 个新 artifact 完整
- [ ] cross-run 4 个新 artifact 完整
- [ ] prefix stability 有量化报告

### D 类：最终门禁
- [ ] targeted suites 全绿
- [ ] `python -m pytest tests/ -q` 全绿
- [ ] completion 文档落盘
- [ ] 无冻结层越界

---

## 7. NO-GO 条件

1. 改了冻结层或 provider/model/base_url
2. 改了 scoring 维度或 breakpoint probes
3. sync / stream 只有一边有 observability
4. stable_prefix_hash 在同结构下不稳定
5. 已有 audit artifact 语义被破坏
6. 全量回归失败
7. key 写入仓库文件
8. completion 文档混淆"理论可命中"与"实证证据"
