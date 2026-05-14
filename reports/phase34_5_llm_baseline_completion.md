# Phase 34.5 — LLM Baseline 正式收口：最终验收

## 1. 文档目的

本文件是 Phase 34.5 的正式 completion 归档。
Phase 34.5 已完成：将 Phase 34 的 LLM snapshot 收口为正式可回归的 pre-refactor baseline。

---

## 2. 执行摘要

| 子阶段 | 名称 | 产物 | 判定 |
|--------|------|------|------|
| S34.5.1 | 范围锁定与 baseline 定义 | `llm_baseline_manifest.json` | GO |
| S34.5.2 | baseline 波动带确认 | `llm_baseline_band.json` | GO |
| S34.5.3 | 上下文路径指纹归档 | `llm_context_fingerprint.json` | GO |
| S34.5.4 | 验证与正式收口 | 本文件 | GO |

---

## 3. 产物清单

| 产物 | 路径 | 状态 |
|------|------|------|
| Manifest | `reports/experience_audit/llm_baseline_manifest.json` | 落盘 |
| Band | `reports/experience_audit/llm_baseline_band.json` | 落盘 |
| Fingerprint | `reports/experience_audit/llm_context_fingerprint.json` | 落盘 |
| Execution Plan | `reports/phase34_5_llm_baseline_execution_plan.md` | 落盘 |
| Completion | `reports/phase34_5_llm_baseline_completion.md` | 本文件 |

---

## 4. LLM Baseline 正式语义

### baseline 定义

- **名称**：LLM Baseline (Pre-Refactor)
- **语义角色**：Phase 35 上下文路径重构前的正式 before-state 锚点
- **与 rules baseline 的关系**：并列锚点。Rules baseline (12.31) = 规则引擎性能地板；LLM baseline (14.59 ± 0.26) = 当前 LLM 增强状态
- **用途**：Phase 35 改动后的 after-state 将与本 baseline 的均值 ± 波动带做对比

### baseline band

| 指标 | 值 |
|------|-----|
| 样本数 | 5 runs (升级触发：Run 2/3 llm_generated < 1.0) |
| Mean overall | 14.59 / 20 |
| Range | [14.20, 14.80] |
| Std | 0.256 |
| Phase 35 回归阈值 | < 14.20 (低于 band minimum) |
| llm_generated rate | 0.973 mean (73/75 turns) |
| Breakpoint probes | 25/25 (5 runs × 5 probes) |

### context path 指纹

- **System prompt**：monolithic 单模板（~3500 chars）
- **Sync/Stream 路径**：7 项差异已归档
- **关键风险点**：Stream 路径缺少 context_summary、progress_summary、memory_snippets、covered_topics；且每次浪费一次 agent.act() 调用仅用于提取元数据

---

## 5. 必须确认项

| 确认项 | 状态 |
|--------|------|
| rules baseline 与 LLM baseline 语义边界未混淆 | ✅ manifest 明确标注并列关系 |
| 当前 baseline 已被明确定义为 pre-refactor anchor | ✅ purpose 字段明确 |
| 波动带不是单次 snapshot | ✅ 5 runs, range=0.60 |
| context fingerprint 已完整记录 sync/stream 差异 | ✅ 7 divergent + 5 shared |
| 本阶段没有偷跑 Phase 35 重构 | ✅ 0 行源码修改 |
| key 安全未破 | ✅ 只在运行时注入 env var |

---

## 6. 边界合规

| 约束 | 状态 |
|------|------|
| 未修改 contracts/** | ✅ |
| 未修改 src/inner/** | ✅ |
| 未修改 src/middle/** | ✅ |
| 未修改 src/outer/** | ✅ |
| 未修改 provider / model / base_url | ✅ |
| 未修改 Phase 32 scoring 维度 | ✅ |
| 未修改 mainline 代码 | ✅ |
| 未实装 Context Caching / 分层注入 / retention | ✅ |

---

## 7. 全量回归

```
python -m pytest tests/ -q
1408 passed, 5 skipped in 105.36s
0 failed
```

---

## 8. 风险记录

| 风险 | 缓解 |
|------|------|
| LLM 输出存在固有波动（std=0.256） | 已建立 5-run band，Phase 35 可对比波动区间 |
| Stream 路径 context 不完整 | Fingerprint 已归档，Phase 35 将统一两条路径 |
| 单次 run 的 llm_generated 可能 < 1.0 (2/5 runs) | 已记录为正常波动，非阻塞 |
| DEEPSEEK_API_KEY 在会话间丢失（重启） | 设计如此（key 不落盘），Phase 35 启动时需重新注入 |

---

## 9. Phase 35 输入摘要

Phase 35 可在以下 before-state 上启动：

1. **数值锚点**：overall 14.59 ± 0.26, range [14.20, 14.80]
2. **结构锚点**：monolithic system prompt / 5-block context_summary / sync-stream 7项差异
3. **配置锚点**：provider=openai / model=deepseek-chat / base_url=https://api.deepseek.com/v1 / scoring=Phase 32 dimensions
4. **已知问题** (fingerprint 中发现，供 Phase 35 修复)：
   - Stream 路径 context 严重不完整（缺 4 个注入项）
   - Stream 路径 dry-run agent.act() 浪费
   - Difficulty 逻辑在两路径中代码重复
   - System prompt 为 monolithic 单体结构

---

## 10. 最终结论

**Phase 34.5 判定：GO** ✅

当前 LLM 链路已正式锁定为 Phase 35 重构前的 pre-refactor baseline。
Phase 35 拥有完整的 before-state：数值 band + 结构 fingerprint + 配置快照。

---

**此文档由 Claude Code 在 Phase 34.5 完结后生成。**
**生成时间**: 2026-05-14T06:55:00Z
**基线版本**: V19.5 + Phase 34.5 baseline freeze
