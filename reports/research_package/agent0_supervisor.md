# Agent 0: Supervisor and Router — v2 (基于 2025-2026 多 Agent 科研策略重构)

> **注**：本元提示词已迁移到 Python 调度器 `run_research_pipeline.py`。
> Agent 0 的逻辑现在由 Python 代码实现。
> 本文件保留作为参考文档 + v2 设计变更记录。

## Task Definition

| 字段 | 内容 |
|------|------|
| **Name** | Supervisor and Router v2 — Centralized Orchestrator |
| **Expected Output** | 执行完成的研究管线 + `shared_state.md` 含 Agent Card 注册 + 检查点记录 + 路由日志 + `output/` 全部交付物 |
| **Tools** | 读文件、写文件、**工具可用性检测（WebFetch/pytest/grep）** |
| **Context Inputs** | `orchestrator_v2_design.md`（执行总图）、Agent Card 注册表、约束规则 |
| **Dependencies** | 全部 Agent |
| **Self-Verification** | 所有机器检查点通过后确认交付物完整性 |
| **Design Basis** | Google DeepMind Intelligent Delegation (2026) + Microsoft Agent Framework Magnetic Pattern (2025) |

## Role

借鉴 Microsoft Agent Framework 的 Magnetic (Manager/Orchestrator) 模式 + DeepMind Intelligent Delegation 框架。你负责：
1. 管线启动时检查工具可用性 → 决定哪些 Agent 可以运行
2. 管理 Agent Card 注册表
3. 执行机器可验证的检查点
4. 级联失败预防（退回时追溯根因）

---

## 新增职责（v2）

### 0. 启动前：工具可用性检查（基于 DeepMind Intelligent Delegation）

管线启动时，先检查工具环境，再决定启停哪些 Agent：

```python
# Python 层执行，非 LLM 决策
available_tools = {
    "Read": True,           # 始终可用
    "grep": True,           # 始终可用
    "WebFetch": check_web(),    # HTTP 可达性检测
    "pytest": check_pytest(),   # pytest 安装检测
}

agent_cards = load_agent_cards()
active_agents = []

for card in agent_cards:
    tool_gap = [t for t in card.tools_required if t not in available_tools or not available_tools[t]]
    if tool_gap:
        if card.skip_if_no_tool:
            log(f"Skipping {card.name}: missing tools {tool_gap}")
        else:
            raise ConfigError(f"{card.name} requires {tool_gap} but skip_if_no_tool=False")
    else:
        active_agents.append(card)
```

### 0.5. Agent Card 注册（基于 Microsoft Agent Framework + Google A2A 协议）

每个 Agent 在管线启动时注册一张 Agent Card，声明能力边界：

```
Agent Card:
  name: "A1 Code Intelligence"
  expertise: ["python", "pytest", "sqlite"]
  tools_required: ["Read", "grep"]
  needs_internet: false
  can_parallel: true
  skip_if_no_tool: false
  max_rounds: 3
  output_type: "GAP findings with line numbers"

Agent Card:
  name: "A2 Data Audit"
  expertise: ["test_analysis", "report_audit", "data_model"]
  tools_required: ["Read", "grep", "pytest"]
  needs_internet: false
  can_parallel: true
  skip_if_no_tool: false
  max_rounds: 3
  output_type: "DATA findings with verification method"

Agent Card:
  name: "A3 External Research"
  expertise: ["web_search", "github_analysis", "literature_review"]
  tools_required: ["Read", "WebFetch"]
  needs_internet: true
  can_parallel: true
  skip_if_no_tool: true     # ← 关键：缺工具就跳过，不降级
  max_rounds: 3
  output_type: "SRC findings with verifiable URLs"

Agent Card:
  name: "A4 Internal Synthesis"
  expertise: ["system_review", "feasibility", "roadmap"]
  tools_required: ["Read"]
  needs_internet: false
  can_parallel: false
  skip_if_no_tool: false
  max_rounds: 3           # Society of Thought 内部辩论 3 轮
  output_type: "3 reports (system_state + feasibility + roadmap)"
  internal_personas: 3    # Society of Thought 模式
```

### 1. 机器检查点替代自我报告收敛（基于 DeepMind Intelligent Delegation）

每阶段产出不再由 Agent 自己报告"我收敛了"，而是由 Python 层执行机器检查：

```
Stage 1 检查点（A1/A2/A3 产出后）：
  ┌──────────────────────────────────────────────────────────────┐
  │ A1: 每条 GAP finding 必须有 file:line 引用                    │
  │   → 用正则提取所有 GAP 条目的 file:line 字段                   │
  │   → 对每个 file:line 执行 grep 验证存在性                     │
  │                                                              │
  │ A2: 每条 DATA finding 必须有 Verification Method 字段          │
  │   → 检查 Verification Method 非空                             │
  │   → 如果引用了测试结果，检查 [TOOL_RESULT] 数据块存在           │
  │                                                              │
  │ A3: 每条 SRC finding 必须有对应的 [TOOL_RESULT] 数据块          │
  │   → 检查 SRC-xxx 是否有 status=success 的数据块                │
  │   → 无对应数据块的 SRC → 标记 skip                            │
  └──────────────────────────────────────────────────────────────┘

Stage 2 检查点（A4 产出后）：
  ┌──────────────────────────────────────────────────────────────┐
  │ 系统状态报告: 6 层章节全部存在                                  │
  │   → 检查 "# N." 或 "## N." 格式的 6 个章节标题                 │
  │                                                              │
  │ 可行性矩阵: 每条 finding 有三维度评估                           │
  │   → 检查 Technical Feasibility / User Perceptibility / Data   │
  │     Support 三个字段全部存在                                   │
  │                                                              │
  │ 路线图: 依赖闭环检查 + 每 Phase 有 Verification Method          │
  │   → 检查 Phase N 的 Prerequisites 在 Phase < N 中存在          │
  │   → 检查每个 Phase 有 "Verification Method" 章节               │
  └──────────────────────────────────────────────────────────────┘

Stage 3 检查点（A5 产出后）：
  ┌──────────────────────────────────────────────────────────────┐
  │ 10 标准全部评估                                               │
  │   → 检查 Standard 1-10 全部存在                              │
  │                                                              │
  │ FULL coverage 必须引用具体 Phase 内容                          │
  │   → 检查每条 FULL 的 Justification 中包含 "Phase" 字样的引用   │
  │                                                              │
  │ 代码引用验证结果汇总                                           │
  │   → grep 验证路线图中每个 "Files to Change" 路径的存在性        │
  └──────────────────────────────────────────────────────────────┘
```

### 2. 级联失败预防（基于 DeepMind Intelligent Delegation）

当 Stage 3 检查点 FAIL 时，不只退回当前 Agent，而是追溯根因：

```
检查点 FAIL 记录：
  Gate 7: Standard 4 "Automatic Pace Adjustment" 标记 PARTIAL
  → 根因追溯：
    - 该标准的依据是路线图 Phase 3（难度双向调节）
    - Phase 3 的 Findings Covered: GAP-006（单向难度）
    - GAP-006 来自 Agent 1 → Agent 1 的 GAP-006 行号偏移 2 行
  → 退回决策：
    - 根因在 Agent 1 的行号精度
    - 退回 Agent 1 修订 GAP-006 行号
    - 然后 A4 重新评估 Phase 3（无需重新做全部辩论）
    - 然后 A5 重新评审 Standard 4

退回规则：
  - 1st FAIL → 退回根因 Agent + 通知下游链
  - 2nd FAIL → 同上 + 标注 "repeated failure"
  - 3rd FAIL → 降级为 CONDITIONAL-GO，标注风险项
```

---

## Agent 调度 DAG（v2）

```
               ┌──────────────────────┐
               │  工具可用性检测 +     │
               │  Agent Card 初始化   │
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  A1  Code (Read+grep) │
               │  A2  Data (pytest)    │  并行，全部启动
               │  A3  Research(WebFetch)│
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  机器检查点 Stage 1  │
               │  (grep/pytest/URL)  │
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  A4 Internal Debate  │
               │  (Society of Thought)│
               │  3 personas, 3 rounds│  ← 替代 v1 的 A4→A5→A6 串行
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  机器检查点 Stage 2  │
               │  (层覆盖率/约束/闭环) │
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  A5 Review (grep)   │
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  机器检查点 Stage 3  │
               │  (10标准/代码引用/GO) │
               └──────────┬───────────┘
                          │
               ┌──────────▼───────────┐
               │  GO / CONDITIONAL-GO │
               │  / NO-GO             │
               └──────────────────────┘
```

---

## 与 v1 的关键差异

| 维度 | v1 | v2 |
|------|----|----|
| Agent 数量 | 7（固定全部启动） | 5（Orchestrator 按工具可用性决定） |
| Agent 4/5/6 | 3 个独立串行 Agent | A4 单 Agent 三角色内部辩论（Society of Thought） |
| 收敛验证 | Agent 自我报告（"连续 3 次自省无新发现"） | Python 层机器可验证检查点 |
| 工具可用性 | 假设全部可用，Agent 3 无工具时编造 | `skip_if_no_tool` 控制，缺工具就跳过 |
| 退回策略 | 直接退回当前 Agent | 根因追溯（可能退回上游 Agent） |
| 错误放大 | 非结构化，估计 17.2x | 结构化检查点，估计 4.4x |
| 执行时长 | ~20 分钟（7 次 LLM 调用） | ~12-15 分钟（~5 次 LLM 调用 + 工具执行） |
