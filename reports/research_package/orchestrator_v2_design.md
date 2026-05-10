# Coherence Research Pipeline v2 — 基于 2025-2026 多 Agent 科研策略重构

## 设计基础

本设计基于 2025-2026 年五项同行评审的多 Agent 系统研究成果：

| 研究 | 机构 | 核心发现 | 本设计的对应改动 |
|------|------|---------|----------------|
| "Towards a Science of Scaling Agent Systems" (Dec 2025) | Google Research + DeepMind + MIT | 多 Agent 串行任务平均降低 3.5% 性能，最差降低 70%。非结构化系统错误放大 **17.2 倍** | 合并串行 Agent (A4→A5→A6)，减少串行链长度 |
| "Society of Thought" (Jan 2026, arXiv:2601.10825) | Google + UChicago + Santa Fe Institute | 单 Agent 内部多角色辩论使准确率翻倍 (27.1%→54.8%) | 用内部辩论替代多 Agent 串行评审 |
| "Heterogeneous Scientific Foundation Model Collaboration" — Eywa (Apr 2026, arXiv:2604.27351) | UIUC | 跨模态异构（LLM + 领域模型）优于同构多 LLM。**Token 消耗降低 ~30%** | Agent 专业化 + 工具绑定不依赖 LLM 自省 |
| "Intelligent Delegation" (Feb 2026) | Google DeepMind | 可验证任务完成 + 级联失败预防 + 信任机制 | 机器可验证检查点替代自我报告收敛 |
| Microsoft Agent Framework (Oct 2025) | Microsoft | 5 种编排模式：Sequential/Concurrent/GroupChat/Handoff/Magnetic | Centralized Orchestrator + Agent Card 模式 |

---

## 架构变更

### 当前（v1）：7 Agent 串行为主

```
A1 → A2 → A3 → A4 → A5 → A6 → A7
串行     串行     串行     串行
```

Google/MIT 问题：串行多 Agent 链在非分解式任务中降低高达 70% 性能。

### 重构（v2）：5 Agent，内部辩论替代串行

```
                    ┌─ A1 Code (Read+grep) ─┐
Orchestrator ─→ 并行 ── A2 Data (Read+pytest) ──→ A4 Internal Synthesis ─→ A5 Review
                    └─ A3 External (WebFetch) ─┘   (Society of Thought)    (grep verify)
       ↑                                              ↑                       ↑
   智能分配 Agent                                 3 internal personas     代码引用验证
   判断串/并/跳过                                而不是 3 个独立 LLM      可验证检查点
```

---

## 具体改动

### 改动 1：新增 Centralized Orchestrator（基于 DeepMind Intelligent Delegation + Microsoft Magnetic Pattern）

**解决的问题**：当前管线总是启动全部 7 个 Agent，不管研究问题的复杂度。Google/MIT 发现：当单 Agent 能解决时，加更多 Agent 反而有害。

**设计**：Orchestrator 在管线启动时读取研究问题，决定：
1. 这次需要几个 Agent？
2. 哪些可以并行？哪些必须串行？
3. 有没有 Agent 可以跳过？

**Agent Card 协议**（基于 Google A2A 协议 + Microsoft Magnetic）：

每个 Agent 在管线启动时注册一张 Agent Card，声明自己的能力边界：

```
Agent Card:
  name: "A1 Code Intelligence"
  expertise: ["python", "pytest", "sqlite"]
  tools_required: ["Read", "grep"]
  needs_internet: false
  can_parallel: true
  estimated_tokens: 8000
  output_type: "GAP findings with line numbers"
  
Agent Card:
  name: "A3 External Research"
  expertise: ["web_search", "github_analysis", "literature_review"]
  tools_required: ["WebFetch"]
  needs_internet: true
  can_parallel: true
  skip_if_no_tool: true
  output_type: "SRC findings with verifiable URLs"
```

Orchestrator 根据 Agent Card 决定启停规则：
- 如果 `WebFetch` 工具不可用 → **跳过 A3**（不降级）
- 如果研究问题只需代码审计 → 只启动 A1
- 如果只需外部调研 → 只启动 A3

### 改动 2：合并 A4+A5+A6 为单 Agent 内部辩论（基于 Google Society of Thought）

**解决的问题**：Google/MIT 证明串行多 Agent 平均降低 3.5% 性能。当前 A4→A5→A6 是完全串行链。Google Society of Thought 证明单 Agent 内部辩论准确率翻倍。

**设计**：A4 Internal Synthesis 是一个单 Agent，内部运行 3 个角色（persona）：

```
Persona 1: Synthesizer
  职责：将 A1/A2/A3 的发现组织为 6 层系统状态报告
  倾向：包容性——尽量纳入所有发现
  约束：每条发现必须引用来源 ID

Persona 2: Feasibility Checker
  职责：评估每条发现的技术可行性、约束合规性
  倾向：保守性——严格检查约束违规
  约束：P0 项必须全部通过约束检查

Persona 3: Roadmap Designer
  职责：按依赖关系组织 Phase 路线图
  倾向：结构性——关注依赖闭环和验证方法
  约束：依赖闭环检查必须通过
```

**执行流程**（基于 Society of Thought 论文的内部辩论机制）：

```
1. Synthesizer 写出 6 层报告草稿
2. Feasibility Checker 审阅 → 对不可行的发现标注 NOT-FEASIBLE
3. Synthesizer 根据反馈修订（删除或标注风险）
4. Roadmap Designer 读取修订后的报告 → 设计 Phase 结构
5. Feasibility Checker 检查依赖闭环 → 发现问题 → 退回
6. Roadmap Designer 修订 Phase 结构
7. 重复直到收敛或达到 max_rounds=3
8. 收敛后输出：系统状态报告 + 可行性矩阵 + 路线图（3 份文档一次生成）
```

**为什么这样比 3 个独立 Agent 更好**（依据 Google/MIT 实证）：
- 避免串行链中的错误放大（17.2 倍→4.4 倍）
- 内部辩论使准确率翻倍（Society of Thought 实证）
- Token 消耗降低（上下文共享，不重复加载配置约束）
- 依赖闭环检查在单上下文内完成，不需要跨 Agent 传递

### 改动 3：工具接入架构化而非可选（基于 UIUC Eywa 异构设计）

**解决的问题**：当前工具是"可选"的，Agent 3 在无工具时降级为 first_principles（幻觉来源）。UIUC Eywa 证明：跨模态异构（工具 + LLM 配合）优于纯 LLM。

**设计**：工具集成变为架构层面的不可选项：

```
Pipeline 启动时：
  检查可用工具清单 → 写入 Agent Card 的 tools_required 字段
  
  如果 A3 的 tools_required 包含 WebFetch 但不可用：
    → 跳过 A3，不在管线中执行
    → 标注 "A3 skipped: WebFetch unavailable"
    → 不降级为 first_principles
    
  如果 A2 的 pytest 工具可用但测试命令失败：
    → 将失败信息作为有效发现注入（"测试体系存在已知失败"）
    → 不忽略，不重试
```

### 改动 4：可验证检查点替代自我报告收敛（基于 DeepMind Intelligent Delegation）

**解决的问题**：当前 Agent 的收敛条件是"连续 3 次自省无新发现"——完全由 LLM 自我报告，无外部验证。DeepMind Intelligent Delegation 要求"可验证任务完成"。

**设计**：每阶段产出通过机器检查后才进入下一阶段：

```
Stage 1 产出 → 机器检查：
  - A1 的 GAP finding → 每条有 file:line 引用？→ grep 验证存在
  - A2 的 DATA finding → Verification Method 字段非空？
  - A3 的 SRC finding → 每条有 [TOOL_RESULT] 对应？→ 数据块存在性检查
  
Stage 2 产出 → 机器检查：
  - 报告所有 6 层覆盖？→ 章节标题存在性检查
  - 每条缺口标注来源 ID？→ GAP/DATA/SRC ID 正则检查
  - P0 项全部通过约束检查？→ constraint checklist 扫描
  
Stage 3 产出 → 机器检查：
  - 全部 10 标准评估？→ 标准编号完整检查
  - 代码引用验证？→ grep 实际执行
  - Coverage 有 FULL 时必须引用具体 Phase 内容？→ Phase 引用存在性检查
```

**检查失败的 Agent → 退回 + 指定根因**（基于 DeepMind 级联失败预防）：

```
检查失败 → Orchestrator 创建退回路由：
  - 如果 A3 的 WebFetch 数据缺失 → 跳过 A3（不退回，不补数据）
  - 如果 A4 报告缺少某一层 → 退回 A4，指定"第 4 层评估层缺失"
  - 如果 A5 代码引用 FAIL → 退回 A5，指定"Phase 1 的 agent.py:570 不存在"
  
退回限制：每阶段最多 2 轮退回。2 轮后未通过 → 降级为 CONDITIONAL-GO，标注风险项。
```

---

## 变更影响汇总

| 维度 | v1（当前） | v2（重构后） | 依据 |
|------|-----------|------------|------|
| Agent 总数 | 7 | **5** | Google/MIT：多 Agent 串行降低性能 |
| 串行链长度 | A4→A5→A6 三级串行 | **A4 单 Agent 内部辩论** | Google Society of Thought：内部辩论准确率翻倍 |
| 工具接入 | 可选，无工具就编造 | **缺少工具就跳过，不编造** | UIUC Eywa：工具 + LLM 异构优于纯 LLM |
| 收敛验证 | 自我报告 | **机器可验证检查点** | DeepMind Intelligent Delegation |
| Agent 启停 | 每次都启动全部 7 个 | **Orchestrator 按需启停** | DeepMind Intelligent Delegation + Microsoft Magnetic |
| 外部搜索 | first_principles 降级（幻觉源头） | **不可用时跳过，不降级** | 自研：降级策略直接导致 arXiv 虚假 ID |
| 错误放大 | 非结构化，17.2 倍级 | **结构化检查点，4.4 倍级** | Google/MIT 实证 |
| Token 消耗 | 7 次 LLM 调用，上下文不共享 | **~5 次，A4 内部共享上下文** | UIUC Eywa 测算：~30% 降低 |

---

## 元提示词更新需求

| 文件 | 改动 |
|------|------|
| `agent3_research.md` | 已更新（WebFetch 注入） |
| `agent2_data_audit.md` | 已更新（pytest 注入） |
| `agent7_review.md` | 已更新（grep 验证） |
| **新增**: `agent4_synthesis.md` | **重写为 Society of Thought 内部辩论格式** |
| **新增**: `orchestrator_v2.md` | **新增 Centralized Orchestrator 设计文档** |
| **删除**: `agent5_feasibility.md` | 功能合并到 A4 内部辩论的 Persona 2 |
| **删除**: `agent6_roadmap.md` | 功能合并到 A4 内部辩论的 Persona 3 |
| **修改**: `agent0_supervisor.md` | 加入 Agent Card + 可验证检查点逻辑 |
