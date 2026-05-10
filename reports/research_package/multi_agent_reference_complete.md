# 多 Agent 系统设计参考全集（2025-2026）

基于 Web Search 和学术论文搜索，整理当前可参考的多 Agent 框架、设计方法论、错误处理机制和协议标准。

---

## 第一部分：主要框架对比

### 1. OpenAI Agents SDK（原 Swarm 继承者）

**定位**：轻量级多 Agent 编排框架，生产级。
**核心机制**：
- Agent + Handoff（移交）：Agent 判断任务超出自己能力范围时，主动移交给另一个 Agent
- Guardrails：输入/输出验证
- Tracing：可观测性追踪
**关键特征**：
- 无状态设计
- 仅支持 OpenAI 模型
- 不支持跨平台 Agent 通信
- MCP 协议支持
**适合**：单平台、快速编排

来源：https://arxiv.org/abs/2512.08769

---

### 2. Google ADK + A2A 协议

**定位**：企业级全栈多 Agent 框架。
**核心机制**：
- Agent Development Kit：构建、测试、评估、部署一体
- Agent2Agent (A2A) Protocol：跨平台 Agent 通信标准（2025 年 4 月发布）
- Agent Card：Agent 用 JSON 格式暴露自己的能力
- 支持状态 Agent 和复杂工作流
**A2A 协议的核心设计**：
- Agent Card：能力发现
- Task Management：任务生命周期管理
- UX Negotiation：Agent 之间协商内容格式
- Transport：HTTP + JSON + SSE
- 50+ 合作伙伴（Atlassian, Box, Cohere, Intuit, LangChain, MongoDB, Salesforce, SAP, ServiceNow）
**关键缺失**：OpenAI 和 Anthropic 不在 A2A 合作伙伴名单中
**适合**：跨平台、企业级、多供应商环境

来源：https://ar5iv.labs.arxiv.org/html/2508.10146

---

### 3. AutoGen（Microsoft）

**定位**：多 Agent 对话框架。
**核心组件**：
- GroupChatManager：管理者决定谁发言、什么时候结束
- AssistantAgent：执行任务的 Worker
- UserProxyAgent：模拟用户，可以执行代码
- max_round：防止死循环
- speaker_selection：选择下一个发言的 Agent
**适合**：群聊式多 Agent 协作

---

### 4. CrewAI

**定位**：角色驱动的多 Agent 框架。
**核心概念**：
- Crew（团队）= Agent × Task × Process
- Task：预定义任务，有 expected_output、tools、context
- Process：sequential（串行）或 hierarchical（层级）
- Delegate Work：Agent 之间可以委托任务
**核心贡献**：Task 模板格式——每个 Task 有明确的 expected_output、tools、context、dependencies

---

### 5. LangGraph（LangChain）

**定位**：有向图驱动的 Agent 状态机。
**核心概念**：
- Node（节点）：一个 Agent 或一个处理步骤
- Edge（边）：数据流方向
- State（状态）：全局共享状态，所有 Node 读写同一个 State
- Conditional Edge（条件边）：根据条件决定下一跳（如 "if revision > 2, send to final"）
**核心贡献**：图结构 + 条件边的模式，精确控制 Agent 间路由

---

### 6. MetaGPT

**定位**：模拟软件公司的多 Agent 系统（Boss → PM → Architect → Engineer → QA）。
**核心概念**：
- 每个角色的输出有严格的格式合约（如 Architect Output 必须是 RFC 格式）
- 文档共享：所有 Agent 写同一个共享文档，而不是传消息
- SOPs（Standard Operating Procedures）：每个角色的操作标准
**核心贡献**：共享文档模式——所有 Agent 写同一份文档，自然对齐

---

### 7. Semantic Kernel（Microsoft）

**定位**：AI 编排框架。
**核心组件**：
- Orchestrator：中央协调，意图路由，上下文保持
- Classifier (NLU → SLM → LLM)：成本感知的路由选择
- Agent Registry：Agent 发现和验证的目录服务
- Supervisor Agent（可选）：分解复杂任务、委托、综合结果
- Specialized Agents：领域专用 Agent
**核心贡献**：Agent Registry 的概念——一个注册表让 Agent 可以相互发现

来源：https://developer.microsoft.com/blog/designing-multi-agent-intelligence

---

### 8. AgenticSciML（2026, npj Artificial Intelligence）

**定位**：科研级多 Agent 系统（科学机器学习）。
**核心机制**：
- 10+ 专业 Agent 协作
- Structured Debate：结构化辩论机制
- Retrieval-Augmented Method Memory：检索增强的方法记忆
- Ensemble-Guided Evolutionary Search：集成引导的进化搜索
**成果**：比单 Agent 和人类设计基线高出最多 4 个数量级的误差降低
**核心贡献**：结构化辩论 + 进化搜索的组合，适合探索性问题

来源：https://www.nature.com/articles/s44387-026-00102-5

---

### 9. STORM（Stanford）

**定位**：调研与写作分离。
**流程**：
- Research Agent → 收集资料
- Outline Agent → 组织结构
- Writer Agent → 生成文章
**核心贡献**：调研（Research）和综合（Synthesis）分离，两个阶段用不同 Agent

---

### 10. TrustResearcher（WWW 2026）

**定位**：知识可追溯、透明的多 Agent 研究构思系统。
**流程**：
- Structured Knowledge Curation → Diversified Idea Generation → Multi-stage Idea Selection → Expert Panel Review
**核心特征**：暴露中间推理状态、执行日志、可配置 Agent
**核心贡献**：透明化的中间过程——所有 Agent 的中间结果都可见

来源：https://arxiv.org/abs/2510.20844

---

## 第二部分：设计方法论

### FlowForge（IEEE VIS 2025）

三层设计流程：
1. Task Planning（抽象层）——高层目标分解
2. Agent Assignment（分配层）——哪个 Agent 处理哪个子任务
3. Agent Optimization（优化层）——微调单个 Agent

核心观点：设计多 Agent 系统的过程本身也是一项需要工具支持的任务。FlowForge 提供可视化工具来辅助思考。

来源：https://ui.adsabs.harvard.edu/abs/2025arXiv250715559H/abstract

---

### Microsoft: Patterns for Scalable Multi-Agent Systems

四个核心模式：

| 挑战 | 解决方案 |
|------|---------|
| 缩小 Agent 搜索范围 | Semantic Cache-Based Retrieval（嵌入 + 相似度搜索） |
| Agent 接入 | Code-Based（Python/Semantic Kernel）或 Template-Based（YAML） |
| Agent 对象创建 | Factory Design Pattern |
| 群聊编排 | SupervisorAgent + selection + termination |

性能优化技术：
- Single-Intent Fast Path：高置信度时跳过编排层
- Chattiness Control：通过 max_iterations 控制对话深度
- LLM 参数调优：temperature=0, top_p=0 减少随机性

来源：https://devblogs.microsoft.com/ise/multi-agent-systems-at-scale/

---

### Forte Group: 设计原则（2025）

三条核心原则：
1. **共享完整的 Agent 上下文和行为轨迹**——子 Agent 必须知道前面的 Agent 做了什么
2. **每个 Agent 行为都隐含假设**——用显式的"对齐 Agent"来协调冲突优先级
3. **串行 Agent + 压缩上下文优先于并行 Agent + 碎片状态**

推荐混合模式：
- Phase 1：并行数据收集（独立的事实/选项）
- Phase 2：串行推理（统一的决策/输出）

来源：https://www.fortegrp.com/insights/designing-effective-agent-architectures-principles-for-enterprise-ai-systems

---

### 工程生命周期（arXiv:2512.08769）

9 条最佳实践：
1. 工具优先于 MCP
2. 纯函数调用
3. 单工具、单一职责 Agent
4. 外部化 Prompt 管理
5. 负责任的 AI 对齐的模型联盟设计
6. 工作流逻辑和 MCP 服务器分离
7. 容器化部署
8. KISS 原则
9. 环境感知的部署策略

来源：https://arxiv.org/abs/2512.08769

---

## 第三部分：协议标准

### MCP（Model Context Protocol，Anthropic）

**定位**：连接 LLM 到工具和数据源的低层协议。
**信息格式**：JSON-RPC
**发现机制**：手动
**主要框架**：LangChain, OpenAgents, Agno
**应用场景**：LLM-工具集成

### A2A（Agent-to-Agent Protocol，Google）

**定位**：Agent 间通信的高层协议。
**信息格式**：JSON-RPC/HTTP/SSE
**发现机制**：Agent Card（JSON 格式的能力声明）
**主要框架**：AutoGen, CrewAI, LangGraph
**应用场景**：企业级跨平台 Agent 编排

### ACP（Agent Communication Protocol）

**定位**：跨 Agent 协作协议。
**信息格式**：JSON-LD
**发现机制**：Agent Metadata + Registry
**主要框架**：AutoGen, LangGraph, CrewAI

### ANP（Agent Negotiation Protocol）

**定位**：去中心化 Agent 市场。
**信息格式**：JSON-LD + NLP
**发现机制**：JSON-LD description
**主要框架**：AGORA, CrewAI, Semantic Kernel

各协议比较表：

| 特征 | MCP | ACP | A2A | ANP | Agora |
|------|-----|-----|-----|-----|-------|
| 消息格式 | JSON-RPC | JSON-LD | JSON-RPC/HTTP/SSE | JSON-LD+NLP | PD+自然语言 |
| 发现机制 | 手动 | Agent Metadata+Registry | Agent Card | JSON-LD 描述 | 自然语言 PD |
| 主要框架 | LangChain,OpenAgents,Agno | AutoGen,LangGraph,CrewAI | AutoGen,CrewAI,LangGraph | AGORA,CrewAI,Semantic Kernel | 多 Agent 环境 |
| 应用场景 | LLM-工具集成 | 跨 Agent 协作 | 企业级 Agent 编排 | 去中心化 Agent 市场 | 多 Agent 环境 |

---

## 第四部分：错误处理与归因

### 关键统计数据

| 指标 | 数值 | 来源 |
|------|------|------|
| Agent 归因准确率（最佳方法） | ~53.5% | Who&When, ICML 2025 |
| 步骤定位准确率 | ~14.2% | Who&When, ICML 2025 |
| 改进后的归因准确率（RAFFLES） | 43%（算法数据）/ 20%（手工数据） | RAFFLES, NeurIPS 2025 |
| 改进前基线 | 16.6% / 8.8% | RAFFLES |
| 多 Agent 独立运行错误放大 | 17.2 倍 | Google Research, 2026 |
| 集中协调后错误放大 | 4.4 倍 | Google Research |
| AEGIS 数据集规模 | ~10k 标注轨迹, 6 框架, 6 领域 | AEGIS, 2025 |
| MAST 标注轨迹 | 1600+ 条, 7 框架 | MAST |

### ECHO — 分层错误归因

方法：结合分层上下文表示 + 目标分析评估 + 共识投票
目标：提高多 Agent 系统中错误归因的准确率

### CHIEF — 分层故障归因

方法：将混乱的多 Agent 轨迹转化为结构化的分层因果图
核心机制：通过逐步因果筛选的反事实归因，区分根因和传播症状

### AEGIS — 自动化错误生成与识别

方法：系统性地将可控、可追溯的错误注入成功的多 Agent 轨迹
规模：约 10k 条标注的错误轨迹
训练方法：监督微调、强化学习、对比学习三种范式

### MA-RCA — 多 Agent 根因分析

方法：协作式多 Agent 框架，专用 Agent 处理不同子任务
成果：
- 云原生平台 F1: 95.2%
- 分布式电力计量 F1: 82.8%

### MASC — 元认知自我修正

方法：实时、无监督、步骤级错误检测
核心机制：下一步执行重构 + 原型引导增强
成果：步骤级错误检测 AUC-ROC 提升最多 8.47%

来源：
- https://www.semanticscholar.org/paper/Where-Did-It-All-Go-Wrong-A-Hierarchical-Look-into-Banerjee-Nair/5d1a54a99675eef6f6630e75882a90a983e71f8d
- https://arxiv.org/html/2509.14295v1
- https://hub.baai.ac.cn/view/46417

---

## 第五部分：学术论文方向

### Knowledge Tracing 方向
- BKT（Bayesian Knowledge Tracing） - 已有实现
- DKT（Deep Knowledge Tracing） - 需要 LSTM/RNN
- Survey 2024-2025 综述

### LLM for ITS 方向
- Large Language Model for Intelligent Tutoring System
- Personalized learning path with RL
- LLM-based student modeling

### Multi-Agent Survey 方向
- LLM-Agents-Papers（GitHub, 1280 stars）: 论文合集
- Awesome-AgenticLLM-RL-Papers: 配套论文列表
- Agentic AI 综述（Future Internet, 2025）: 143 篇文献
- Multi-Agent Debate 综述（arXiv:2506.00066）: Agent 角色、通信结构、决策方法

来源：
- https://github.com/AGI-Edgerunners/LLM-Agents-Papers
- https://arxiv.org/abs/2506.00066
- https://www.mdpi.com/1999-5903/17/9/404

---

## 第六部分：应用案例分析

### 生物医学多 Agent 系统
- 肿瘤决策准确率从 30.3% 提升至 87.2%
- 临床试验匹配准确率 87.3%
- 临床医生筛选效率提升 42.6%
- 代价：15-50 倍的 Token 消耗

### 根因分析多 Agent 系统（MA-RCA）
- 云原生平台 F1: 95.2%
- 分布式电力计量 F1: 82.8%
- 引入了专用检索 Agent 和验证 Agent 来对抗幻觉

### 科学发现（PiFlow）
- 发现效率提升 31-42%
- 解决方案质量提升 12-31%
- 时间到方案速度提升 5.6 倍
- Token 消耗减少最多 27%

来源：
- https://www.mdpi.com/2409-9279/9/2/33
- https://link.springer.com/article/10.1007/s40747-025-02096-0
- https://arxiv.org/abs/2505.15047

---

## 第七部分：与当前 research_package 设计的对照

| 我们的组件 | 对应框架 | 状态 |
|-----------|---------|------|
| Agent 0 路由 | AutoGen GroupChatManager | ✅ 已实现 |
| Agent 0 退回协议 | LangGraph Conditional Edge | ✅ 已实现 |
| shared_state.md | MetaGPT 共享文档 | ✅ 已实现 |
| 调研综述分离 | STORM | ✅ 已实现 |
| Task 定义格式 | CrewAI | ✅ 已实现 |
| Agent 联合关系 | EIG 图结构 | ✅ 已实现 |
| 自省 + 外部视角 | SciSage "reflect-when-you-write" | ✅ 已实现 |
| 单/多 Agent 判断 | Google Research 发现 | ✅ 已实现 |
| **未实现** | | |
| Agent Registry | Microsoft Semantic Kernel | ❌ |
| Agent Handoff | OpenAI Swarm/Agents SDK | ❌ |
| 根因追溯退回 | ICML 2025 错误归因 | ❌ |
| 事后 Agent 优化 | FlowForge Optimization Layer | ❌ |
| A2A/MCP 协议 | Google/Anthropic | ❌ 不需要 |
| ACP/ANP 协议 | 学术标准 | ❌ 不需要 |

未实现且值得加的三项前文已讨论过。其余协议类（A2A/MCP/ACP/ANP）当前场景不需要。
