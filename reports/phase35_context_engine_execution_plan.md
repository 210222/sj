# Phase 35 Context Engine Execution Plan

## 1. 文档目的

本文件是 Phase 35 的执行计划，不是最终 completion。

Phase 35 的正式主题为：
- DeepSeek Context Caching 友好的稳定前缀重构
- 分层注入重构
- 重要性保留重构
- sync / stream 主链一致性治理

本阶段基于 Phase 34.5 的正式 before-state 执行，不再是无锚点重构。

---

## 2. 权威 XML 层

- `meta_prompts/coach/255_phase35_orchestrator.xml`
- `meta_prompts/coach/256_s35_1_stable_prefix.xml`
- `meta_prompts/coach/257_s35_2_retention_layers.xml`
- `meta_prompts/coach/258_s35_3_mainline_wiring.xml`
- `meta_prompts/coach/259_s35_4_stream_parity_verify.xml`

---

## 3. 全局边界

### 3.1 禁止修改
- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `src/outer/**`

### 3.2 禁止漂移
- provider / model / base_url drift
- scoring drift
- breakpoint probe drift

### 3.3 本阶段明确不是
- MLA 设计
- provider migration
- memory 大重构
- prompt 文案优化工程

---

## 4. 执行顺序

1. S35.1 Stable Prefix 重构
2. S35.2 重要性保留与层化后缀
3. S35.3 主路径接线与 1M 窗口重标定
4. S35.4 Streaming 对齐、回归与收口

任一阶段未 GO，不得进入下一阶段。

---

## 5. 阶段执行说明

### S35.1 Stable Prefix 重构

#### 目标
让 DeepSeek 自动前缀缓存具备真实命中条件。

#### 当前真实状态
- `SYSTEM_PROMPT` 将稳定规范与高漂移变量混在一起
- `build_coach_context()` 产物在主路径中仍容易被后补上下文污染

#### 主要输入
- `src/coach/llm/prompts.py`
- `src/coach/agent.py`

#### 主要输出
- 固定前缀结构
- 漂移后缀结构
- prompt 分层元数据

#### 禁止事项
- 不改 provider / model / base_url
- 不改 response schema
- 不把 history / memory / summary 插回前缀主体中段

#### 推荐验证
- prefix stability 相关测试
- LLM integration 基础测试

#### GO 标准
- 同类请求前缀主体稳定
- 前缀与后缀边界明确

---

### S35.2 重要性保留与层化后缀

#### 目标
让变化层保留最有连续性价值的信息，而不是简单塞入最近几轮。

#### 当前真实状态
- history / memory 更偏 recency 而不是 importance
- session 边界与去重机制不足
- summary / memory / progress 存在重复注入风险

#### 主要输入
- `src/coach/llm/memory_context.py`
- `src/coach/memory.py`
- `src/coach/agent.py`

#### 主要输出
- importance scoring
- session-scoped retrieval
- dedupe
- per-layer budget
- retention bundle

#### 禁止事项
- 不把 retention 写成“加更多历史”
- 不允许 cross-session leakage

#### 推荐验证
- `tests/test_llm_s4_memory.py`
- `tests/test_coach_memory_upgrade.py`

#### GO 标准
- 第二轮能恢复第一轮教学内容
- retained context 去重并且有预算控制

---

### S35.3 主路径接线与 1M 窗口重标定

#### 目标
将新的 stable prefix / retention bundle / larger-window policy 真实接入主 LLM 路径。

#### 当前真实状态
- 主路径仍存在补丁式上下文注入历史
- difficulty 在 prompt 与 runtime contract 中容易分叉
- 多处长度与数量限制仍带小窗口思维

#### 主要输入
- `src/coach/agent.py`
- `src/coach/llm/prompts.py`
- `src/coach/llm/memory_context.py`

#### 主要输出
- 主路径统一走 layered prompt builder
- difficulty 同源
- history / summary / ai_response 放宽但仍结构化

#### 禁止事项
- 不以 free-text append 作为主机制
- 不继续沿用小窗口极限压缩默认逻辑

#### 推荐验证
- `tests/test_llm_integration.py`
- `tests/test_phase27.py`

#### GO 标准
- 主路径不再依赖补丁式上下文拼接
- prompt 与 runtime difficulty 同源

---

### S35.4 Streaming 对齐、回归与收口

#### 目标
完成 stream / non-stream 路径的一致性治理，并完成 targeted + full regression。

#### 当前真实状态
- stream 路径原先缺失多项 context 注入
- 存在 dry-run `agent.act()` 浪费
- sync / stream 不是同一套 context 组装逻辑

#### 主要输入
- `api/services/coach_bridge.py`
- `src/coach/llm/client.py`
- 相关 tests

#### 主要输出
- stream parity 或差异治理说明
- targeted tests
- full regression
- completion 文档

#### 禁止事项
- 不只修 sync 不修 stream
- 不只跑 full suite 不补 targeted suite

#### 推荐验证
- `tests/test_phase35_stream_parity.py`
- `tests/test_api_chat.py`
- `python -m pytest tests/ -q`

#### GO 标准
- stream / non-stream 一致或差异可治理
- 全量回归通过

---

## 6. 最终验收标准

### A 类：缓存
- 稳定前缀与变化后缀边界清晰
- DeepSeek 自动前缀缓存具备真实命中条件

### B 类：分层注入
- prompt 结构从 monolithic 变为 layered
- 主路径不再依赖后补 append

### C 类：重要性保留
- 第二轮稳定恢复上一轮教学内容
- session 隔离
- 去重
- per-layer budget

### D 类：主链一致性
- sync / stream 一致，或差异有治理说明

### E 类：回归
- targeted suites 全绿
- `python -m pytest tests/ -q` 全绿
- 无冻结层越界

---

## 7. NO-GO 条件

任一命中立即 NO-GO：

1. 修改 `contracts/**`
2. 修改 `src/inner/**`
3. 修改 `src/middle/**`
4. 修改 `src/outer/**`
5. provider / model / base_url 漂移
6. scoring drift
7. 只做文案优化没做结构重构
8. stream 路径未治理
9. targeted suite 未通过
10. full regression 未通过

---

## 8. 执行结论

Phase 35 必须严格按 S35.1 → S35.2 → S35.3 → S35.4 串行推进。

本阶段完成后，应形成：
- stable prefix
- retention bundle
- difficulty 同源
- sync / stream 主链一致性
- 正式 completion 归档
