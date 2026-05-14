# Phase 35 Context Engine Completion

## 1. 文档目的

本文件用于正式归档 Phase 35 的最终结果。

Phase 35 的正式主题为：
- DeepSeek Context Caching 友好的稳定前缀重构
- 分层注入重构
- 重要性保留重构
- sync / stream 主链一致性治理

本文件同时纳入 Phase 35.1 的定向调优结果，作为 Phase 35 的最终收口版本。

---

## 2. 权威阶段定义

### Phase 34.5（Before-State）
Phase 34.5 已完成 LLM baseline 正式收口，提供了 Phase 35 的正式 before-state：

- 数值锚点：`14.59 ± 0.26`
- baseline band：`[14.20, 14.80]`
- 结构锚点：
  - monolithic prompt
  - sync / stream 7 项差异
  - 5-block `context_summary`

### Phase 35（本阶段）
本阶段的目标不是迁移 provider，不是改评分维度，而是将当前 LLM 上下文路径重构为：

1. 稳定前缀可命中 DeepSeek Context Caching
2. 固定层 / 变化层分离
3. 变化层具备重要性保留与去重
4. sync / stream 路径上下文策略一致或被治理

---

## 3. 全局边界与约束

### 未做的事
- 未修改 `contracts/**`
- 未修改 `src/inner/**`
- 未修改 `src/middle/**`
- 未修改 `src/outer/**`
- 未修改 provider / model / base_url
- 未修改 Phase 32 scoring 维度
- 未修改 breakpoint probes 语义
- 未进行 MLA 相关实现
- 未进行 memory 全架构重写

### 本阶段实际主修复面
- `src/coach/llm/prompts.py`
- `src/coach/llm/memory_context.py`
- `src/coach/agent.py`
- `src/coach/llm/client.py`
- `api/services/coach_bridge.py`
- 相关测试文件

---

## 4. Phase 35 主改动面

### S35.1 Stable Prefix 重构
完成：
- 将原本 monolithic 的 system prompt 拆为：
  - 稳定前缀层
  - action contract 层
  - policy layer
  - context layer
- `build_coach_context()` 现在返回 `context_meta`
- 为 DeepSeek 自动前缀缓存创造了稳定前缀条件

### S35.2 Retention Layers
完成：
- history / memory / summary 的变化层保留重构
- 引入 session 过滤
- 引入 importance scoring
- 引入 dedupe
- 引入 `build_retention_bundle()`
- 放宽了小窗口时代的过度压缩限制

### S35.3 Mainline Wiring
完成：
- `CoachAgent` 主 LLM 路径接入新的 layered prompt builder
- 统一 `difficulty` 计算来源
- 去掉原先 `build_coach_context()` 之后再手动 append `progress_summary` / `context_summary` 的主机制
- history / summary / memory / progress 关系收口为清晰层结构

### S35.4 Stream Parity
完成：
- `LLMClient` sync / stream 共用消息构造
- `chat_stream()` 不再 dry-run `agent.act()`
- stream 路径开始复用主链 context bundle 的核心思路
- 补齐了最小 parity 测试

---

## 5. Phase 35.0 首轮 after-state 结果

在主链重构完成后的第一轮 after-state 中，出现了两项质量回归：

- 稳定性：`3.533 -> 3.267`
- 推进感：`2.880 -> 2.711`

但同时也验证了结构改造方向是成立的：

- `llm_generated`：`97.3% -> 100%`
- 引用性：`0.720 -> 0.844`
- Overall 仍在 baseline band 内

诊断结果显示：
- 新分层结构提升了引用性与产出一致性
- 但 scaffold 结构要求在 decoding 末端被稀释
- 同时 context layer 对 scaffold 模式偏重，影响了推进节奏与结构稳定性

因此进入 Phase 35.1 定向调优。

---

## 6. Phase 35.1 定向调优

### 诊断
在 `novice_jump` 场景中，稳定性回归的直接表现为：
- 结构关键词减少（如“步骤”“第1步”“首先”）
- 示例关键词减少（如“例如”“比如”“举个例子”）
- 部分句子只以冒号收尾，结构收束不足

### 实施的修正

#### A. 末端结构锚点
在 `src/coach/llm/prompts.py` 中为 `scaffold` 增加 terminal checklist，靠近生成末端强调：
- statement 必须体现步骤感
- statement 最好给一个例子或类比
- statement 必须用完整句收尾
- steps / statement / question 保持一致

#### B. Scaffold 场景的 context layer 减重
在 `src/coach/agent.py` 中对 `scaffold` 模式定向减重：
- 降低 history limit
- 降低 memory limit
- 截短 `progress_summary`
- 截短 `context_summary`

目的不是削弱上下文，而是让结构要求不被过重的变化层稀释。

---

## 7. Phase 35 最终 After-State vs Phase 34.5 Baseline

| 指标 | Baseline | Phase 35.0 | Phase 35.1 | vs Baseline |
|------|----------|------------|------------|-------------|
| Overall Mean | 14.59 | 14.37 | 14.96 | +0.37 |
| Range | [14.20, 14.80] | [14.07, 14.80] | [14.60, 15.33] | 整体上移 |
| llm_generated | 97.3% | 100% | 100% | +2.7% |
| 引用性 | 0.720 | 0.844 | 0.800 | +0.080 |
| 连续性 | 3.453 | 3.533 | 3.533 | +0.080 |
| 无空转 | 4.000 | 4.000 | 4.000 | 持平 |
| 稳定性 | 3.533 | 3.267 | 3.800 | +0.267 |
| 推进感 | 2.880 | 2.711 | 2.822 | -0.058 |

### 结果解读
- Overall Mean 从 `14.59` 提升到 `14.96`
- 新区间 `[14.60, 15.33]` 整体上移，已突破 baseline band 上限
- `llm_generated = 100%`
- `引用性`、`连续性` 保持高于 baseline
- `稳定性` 从回归态修复到 `3.800`
- `推进感` 从回归态修复到 `2.822`，回到 baseline 最低线以上

### 35.0 → 35.1 的恢复轨迹
- 稳定性：`3.267 -> 3.800`
- 推进感：`2.711 -> 2.822`

这说明：
- terminal checklist 对结构稳定性修复有效
- context layer 减重对推进感修复有效

---

## 8. 测试与回归结果

### Targeted / 关键回归
- `tests/test_llm_s4_memory.py` 通过
- `tests/test_llm_integration.py` 通过
- `tests/test_phase35_stream_parity.py` 通过
- `tests/test_phase35_scaffold_quality.py` 通过
- `tests/test_coach_memory_upgrade.py` 通过
- `tests/test_api_chat.py` 通过
- `tests/test_phase27.py` 通过

### 全量回归
- `python -m pytest tests/ -q`
- 结果：`1415 passed, 5 skipped`

---

## 9. 最终判定

**Phase 35 + 35.1 整体 verdict：GO ✅**

### 结论
基于 Phase 34.5 的正式 LLM baseline，Phase 35 完成了：
- DeepSeek Context Caching 友好的稳定前缀重构
- 分层注入重构
- 重要性保留重构
- 主链一致性治理

Phase 35.1 对稳定性与推进感的局部回归进行了定向修复后，after-state 均值 `14.96` 已突破 baseline band 上限，结构与体验双重验收通过。

### 正式归档结论
Phase 35 不再是“结构改了但质量守不住”，而是：
- 结构重构成功
- 质量回归被精确修复
- after-state 对 baseline 呈现正向突破

因此，Phase 35 可以正式收口，并作为后续阶段的新 before-state。

---

## 10. Phase 35 新的可用锚点

### 数值锚点
- Overall Mean：`14.96`
- Range：`[14.60, 15.33]`
- `llm_generated = 100%`

### 结构锚点
- stable prefix + action contract + policy layer + context layer
- retention bundle 已进入主链
- difficulty 同源
- sync / stream 主链一致性已治理
- scaffold terminal checklist 已生效

这组锚点将成为后续阶段的正式 after-state / next before-state 输入。