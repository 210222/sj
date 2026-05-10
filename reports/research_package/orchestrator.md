# Coherence Research Package — Orchestrator

> **v2 已发布**：`orchestrator_v2_design.md` 包含 2025-2026 科研策略重构。
> 基于 Google/MIT "Towards a Science of Scaling Agent Systems"、Google "Society of Thought"、
> UIUC Eywa、DeepMind Intelligent Delegation、Microsoft Agent Framework 五项研究成果。
>
> 核心变更（7 Agent → 5 Agent）：
> - A4 (Synthesis) + A5 (Feasibility) + A6 (Roadmap) 合并为单个 Agent 内部三角色辩论
> - 所有 Agent 接入工具执行（WebFetch/pytest/grep），缺工具则跳过
> - 机器可验证检查点替代自我报告收敛
> - Centralized Orchestrator 按工具可用性智能启停 Agent
>
> **当前生效版本：v2**。以下为 v1 原始文档（保留作为设计演化记录）。

## 核心范式：连续并行自我进化

## 关键设计

### 1. 每个 Agent = 自我进化的研究者

每个 Agent 的元提示词结构不再是"读 A → 做 B → 输出 C"。而是：

```
初始提示词（起点）
  → Agent 开始工作
  → 产出初步发现
  → 自我反思："我的分析方法是否完整？是否遗漏了什么？"
  → 修改自己的分析框架
  → 基于新框架重新分析
  → 产出更深入的发现
  → 重复直到收敛
  → 最终输出
```

每个 Agent 在 shared_state.md 中记录自己的迭代历史（iteration log），让 Agent 4 和 Agent 0 可以看到结论是如何演化的，而不是只看最终版本。

### 2. 所有 Agent 从一开始就全部启动

没有"Phase 1 → Phase 2"的顺序。所有 Agent（1-7）在管线启动时同时开始：

```
T0: 全部 Agent 同时启动
    Agent 1 开始读 agent.py
    Agent 2 开始读 reports
    Agent 3 开始搜索
    Agent 4 等待发现出现（预计 T+5 分钟后开始综述）
    Agent 5 等待发现出现（预计 T+5 分钟后开始可行性评估）
    Agent 6 等待可行性数据
    Agent 7 等待路线图草稿

T+5min: shared_state.md 开始有发现
    Agent 4 开始逐条写入综述
    Agent 5 开始逐条评估可行性

T+15min: 发现池收敛（Agent 1/2/3 达到自我收敛条件）
    Agent 4 完成综述
    Agent 5 完成可行性矩阵
    Agent 6 开始设计路线图

T+20min: Agent 6 输出路线图草稿
    Agent 7 开始评审

T+25min: 评审完成 → GO / 修订
```

关键点：**Agent 4 和 Agent 5 不需要等 Agent 1/2/3 全部完成——它们逐条处理进入 shared_state.md 的发现。**

### 3. 自我收敛条件

每个 Agent 不能无限迭代下去。收敛条件（写在每个 Agent 的 meta-prompt 中）：

```
连续 3 次自检未发现新缺口 → 收敛
或
同一个 file 区域连续 2 次迭代未找到新发现 → 收敛
或
Agent 自我评估："在当前分析路径上继续迭代的边际收益已低于阈值" → 收敛
```

收敛后 Agent 标记自己的工作状态为 `converged`，但 Agent 0 仍可以因为下游退回而重新激活它。

### 4. 共享状态是自适应对齐机制

Agent 1 在迭代中如果读到 Agent 2 的发现，自然调整自己的分析方向：

```
场景:
Agent 1 在第三轮迭代中发现 DIAG-003（diagnostic_engine 的结果没有被 compose 消费）
同时 Agent 2 在 shared_state.md 中写了 DATA-005（dashboard 不显示 mastery 历史）
→ Agent 1 在第四轮迭代中自然补充：不仅找到"没被消费"的证据，还检查了 persistence 是否保存了 mastery
```

### 5. 发现关联关系（借鉴 EIG 图结构）

发现之间的关联关系必须显式标注。Agent 在写入 finding 时，如果发现与 shared_state.md 中已有其他 Agent 的 finding 有关联，必须标注关系：

```
GAP-001 | diagnostic_engine → compose | BROKEN
  Related: [DATA-003: CONFIRMS, SRC-005: PREREQUISITE]
  Status: confirmed
  Evidence: agent.py:467-484

DATA-003 | dashboard → no mastery history | GAP
  Related: [GAP-001: CONFIRMS]
  Status: confirmed
  Evidence: dashboard_aggregator.py:50-55

SRC-005 | MATHia real-time knowledge tracing | INSIGHT
  Related: [GAP-001: PREREQUISITE]
  Status: draft
  Source: carnegielearning.com/mathia
```

关系类型:
- CONFIRMS: 另一条发现支持本发现
- CONTRADICTS: 另一条发现与本发现矛盾
- PREREQUISITE: 本发现需要另一条发现前置解决
- EXTENDS: 另一条发现补充/扩展了本发现

Agent 4 综述时直接按关联关系组织内容，不需要自己推断关联。

不需要 Agent 4 回头去"交叉验证"——在输入端就自然对齐了。

### 6. 结构化辩论（借鉴 AgenticSciML）

Agent 1/2/3 各自收敛后，不直接传给 Agent 4。增加一轮结构化辩论。

执行流程：
```
Agent 1 收敛 → 标记 findings 为 "draft_final"
Agent 2 收敛 → 标记 findings 为 "draft_final"
Agent 3 收敛 → 标记 findings 为 "draft_final"

辩论轮:
  Agent 1 读 Agent 2 的 draft_final → 输出 CRITIQUE
  Agent 2 读 Agent 1 的 draft_final → 输出 CRITIQUE
  Agent 3 可选参与（外部来源，辩论影响较小）

收到 critique 的 Agent:
  审视每条 critique → 确认或修改 finding → 标记 "final"
  如果 critique 导致重大修改（新增或删除 finding），需要额外一次收敛检查

CRITIQUE 格式:
  CRITIQUE | GAP-003 | Agent 2 → Agent 1
  Type: agree / disagree / need_clarification
  Rationale: [一段话，直接指出问题]

辩论的目的不是"赢"，而是让每条 finding 在进入综述前至少被另一个不同视角的 Agent 审视过一次。
```

### 7. Agent 回顾与优化（借鉴 FlowForge）

管线全部完成后，增加 Agent 回顾步骤。为下一次执行改进 meta-prompt 做准备。

回顾由 Agent 0 在 Agent 7 输出后执行：
```
读取 shared_state.md 中的所有修订日志和 critique 记录 →
汇总每个 Agent 的表现 →
输出 agent_retrospective.md
```

回顾记录表：
```markdown
## Agent Performance Review

| Agent | Findings | Revised | Critiqued | In Roadmap | Improvement |
|-------|----------|---------|-----------|------------|-------------|
| A1    | 7        | 1       | 2         | 4          | 行号精度需要提升 |
| A2    | 6        | 0       | 1         | 5          | — |
| A3    | 12       | 0       | 0         | 3          | GitHub 搜索需更具体 |
| A4    | —        | —       | —         | —          | 综述完整 |
```


## 依赖图

```
依赖规则:
  Agent X → Agent Y 表示"Y 需要看 X 的发现才能工作"——但不等待，逐条消费

Agent 1 ──────────────────────────────→ shared_state.md
Agent 2 ──────────────────────────────→ shared_state.md
Agent 3 ──────────────────────────────→ shared_state.md
Agent 4 ─── reads findings → 逐条综述 ─→ output/report
Agent 5 ─── reads findings → 逐条评估 ─→ output/feasibility
Agent 6 ─── reads feasibility → 路线图 ─→ output/roadmap
Agent 7 ─── reads roadmap → 评审 ──→ output/review
```

唯一的硬串行：Agent 6 开始标注路线图前，需要 Agent 5 的可行性矩阵达到 `converged`。

## Convergence Check

Agent 0 定期检查 shared_state.md 中各 Agent 的状态：

```
检查间隔: 每 3 分钟或每次 shared_state.md 有更新
检查内容:
  - Agent 1/2/3 是否全部 marked "converged"？
  - Agent 4 是否已经逐条处理完所有 findings？
  - Agent 5 的可行性矩阵覆盖率是否达到 >80% findings？

当全部满足时 → 通知 Agent 6 开始设计路线图
```
