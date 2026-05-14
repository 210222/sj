# Phase 34.5 — LLM Baseline 正式收口：执行计划

## 1. 文档目的

本文件是 Phase 34.5 的执行 runbook + 验收标准。

它不取代任何 XML 元提示词——XML 是权威指令层，本文件是人对齐层。

Phase 34.5 的目标：把 Phase 34 的 LLM snapshot 正式收口为可复跑、可比较、可回归的 LLM baseline。

---

## 2. 权威 XML 层

| 文件 | 用途 |
|------|------|
| `meta_prompts/coach/250_phase34_5_orchestrator.xml` | 总控编排 |
| `meta_prompts/coach/251_s34_5_1_scope_lock.xml` | 范围锁定与 baseline 定义 |
| `meta_prompts/coach/252_s34_5_2_baseline_band.xml` | 波动带确认 |
| `meta_prompts/coach/253_s34_5_3_context_fingerprint.xml` | 上下文路径指纹归档 |
| `meta_prompts/coach/254_s34_5_4_verify_close.xml` | 验证与正式收口 |

---

## 3. 全局边界

### 禁止修改

- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `src/outer/**`

### 禁止漂移

- 禁止修改 provider / model / base_url
- 禁止修改 Phase 32 scoring 维度与 breakpoint probes
- 禁止直接修改 src/coach/agent.py、src/coach/llm/prompts.py、src/coach/llm/memory_context.py 的主行为逻辑
- 禁止将本阶段扩展成 Phase 35 的上下文主链重构

---

## 4. 执行顺序

串行推进，未 GO 不得进入下一阶段：

```
S34.5.1 (范围锁定) → S34.5.2 (波动带) → S34.5.3 (指纹归档) → S34.5.4 (验证收口)
```

---

## 5. 子阶段详细说明

### S34.5.1 — 范围锁定与 baseline 定义

**目标**：定义 LLM baseline 的正式语义边界，产出一份 manifest 描述"这个 baseline 是什么、不是什么"。

**当前真实状态**：
- Phase 34 已产出单次 LLM 快照（run_20260513_125812_2f41dbf7）
- llm_vs_rule_comparison.json 已存在
- rules baseline (run_20260513_080304_0d62cb26) 已冻结

**主要输入**：
- Phase 34 completion 文档
- Phase 32 rules baseline
- llm_vs_rule_comparison.json

**主要输出**：
- `reports/experience_audit/llm_baseline_manifest.json`

**禁止事项**：
- 不修改 provider / model / base_url
- 不修改 scoring 维度
- 不把 rules baseline 替换为 LLM baseline

**推荐验证**：
- manifest 可被 `json.load()` 读取
- baseline_run_id 字段有明确来源
- rules baseline 与 LLM baseline 边界清晰

**GO 标准**：
- baseline 语义边界清晰
- manifest 字段完整
- Phase 35 before-state 定义清楚

---

### S34.5.2 — baseline 波动带确认

**目标**：用多次 run 证明当前 LLM 链路的表现不是一次性偶然。

**当前真实状态**：
- Phase 34 仅 1 次 run，无波动带
- DeepSeek API 已可达

**主要输入**：
- 固定命令：`python run_experience_audit.py --mode quick --use-http`
- 固定 provider / model / base_url / profiles / scoring

**主要输出**：
- `reports/experience_audit/llm_baseline_band.json`

**执行策略**：
- 默认跑 3 次，波动超阈值才扩展到 5 次
- 升级条件（任一命中即扩展到 5 次）：
  1. overall_score 极差 > 0.8
  2. 任一关键维度极差 > 0.6
  3. 任一 run 的 llm_generated rate < 1.0
  4. 任一 run 的 breakpoint probe 非全 passed
  5. 任一 run 缺少正式产物

**必须测量**：
- overall score
- 引用性 / 连续性 / 稳定性 / 推进感
- llm_generated rate
- breakpoint probes pass rate

**输出格式**：
- `llm_baseline_band.json` 必须包含：run_ids / sample_size / mean / min / max / std
- 不得只保留最佳或最新一次
- 必须记录 escalation 是否触发

**禁止事项**：
- 不修改运行命令的参数
- 不调整 prompt / context 以获取更稳定结果
- 不跳过异常的 run

**推荐验证**：
- band JSON 包含所有必填字段
- 所有 run 在同一模式下完成
- 波动带不是单次绝对值

**GO 标准**：
- 至少 3 runs 完成
- 必要时已扩展到 5 runs
- baseline 不再依赖单次绝对值

---

### S34.5.3 — 上下文路径指纹归档

**目标**：把当前 LLM prompt/context 的结构形态冻结成 before-state，不修改任何代码。

**当前真实状态**：
- build_coach_context() 在当前代码中运行
- memory_context.py / prompts.py / agent.py 构成当前上下文主链
- 存在 sync path 与 streaming path 差异

**主要输入**：
- `src/coach/agent.py`（只读）
- `src/coach/llm/prompts.py`（只读）
- `src/coach/llm/memory_context.py`（只读）
- `src/coach/memory.py`（只读）

**主要输出**：
- `reports/experience_audit/llm_context_fingerprint.json`

**必须归档的结构项**：
1. system prompt 当前是否为 monolithic
2. history 注入方式（直接注入 vs context_summary 间接注入）
3. progress_summary 注入时机（在 build_coach_context() 内还是之后追加）
4. memory_snippets 来源与 session 边界
5. covered_topics 来源
6. ai_response 截断长度
7. extract_recent_history / extract_memory_snippets 的 limit 与 max_chars
8. 主路径与 streaming 路径的 context 策略差异
9. difficulty 在 prompt 与 runtime contract 中是否同源

**禁止事项**：
- 禁止修改 src/coach/agent.py、src/coach/llm/prompts.py、src/coach/llm/memory_context.py
- 禁止把 fingerprint 写成 Phase 35 设计稿
- 禁止用"应该是什么"替代"现在是什么"

**推荐验证**：
- fingerprint 可被 `json.load()` 读取
- sync path 与 stream path 均被记录
- 所有结构描述来自实际代码读取，非主观推断

**GO 标准**：
- fingerprint 完整记录 sync/stream 差异
- 描述的是当前真实实现

---

### S34.5.4 — 验证与正式收口

**目标**：校验三份核心产物，跑通全量回归，给出最终 GO / NO-GO。

**当前真实状态**：
- manifest / band / fingerprint 已产出
- 全量回归基线：1408 passed / 5 skipped / 0 failed

**主要输入**：
- llm_baseline_manifest.json
- llm_baseline_band.json
- llm_context_fingerprint.json

**主要输出**：
- `reports/phase34_5_llm_baseline_completion.md`

**必须确认**：
1. rules baseline 与 LLM baseline 边界未混淆
2. baseline 已被明确定义为 pre-refactor anchor
3. 波动带不是单次 snapshot
4. context fingerprint 完整
5. 无 Phase 35 偷跑

**禁止事项**：
- 不跳过全量回归
- 不模糊 GO/NO-GO 结论
- 不把 completion 写成新需求

**推荐验证**：
- `python -m pytest tests/ -q` 全绿
- 所有产物文件可读且字段完整
- 无冻结层越界

**GO 标准**：
- 三份产物齐全
- 全量回归通过
- completion 文档落盘

---

## 6. 最终验收标准

### A 类：baseline 定义
- [ ] manifest 清晰
- [ ] rules baseline / LLM baseline 边界清晰

### B 类：波动带
- [ ] 至少 3 runs
- [ ] 必要时扩到 5 runs
- [ ] mean/min/max/std 齐全

### C 类：结构指纹
- [ ] sync / stream 都被记录
- [ ] 当前 prompt/context path 的关键结构被记录

### D 类：最终门禁
- [ ] `python -m pytest tests/ -q` 全绿
- [ ] 无越界
- [ ] completion 文档落盘

---

## 7. NO-GO 条件

任一命中立即 NO-GO：

1. 改了冻结层（contracts/、src/inner/、src/middle/、src/outer/）
2. 改了 provider / model / base_url
3. 偷跑了 Phase 35 重构（改 mainline prompt/context 行为）
4. 只锁 snapshot 没锁波动带
5. 只锁 run 数字，没锁 context fingerprint
6. 全量回归失败
7. key 落盘或写入仓库文件
