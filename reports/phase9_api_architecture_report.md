# Phase 9 — API 层与前端交互架构方案研究报告（完整版）

**编制日期**: 2026-05-04
**研究范围**: API 架构 × 多 LLM 模型集成 × 前端框架 × UI 设计工具 × GitHub 开源参考
**当前基线**: Coach 轨 Phase 0-8 全部 GO，1070 tests，11 份冻结合约

---

## 目录

0. [项目概念与核心理念](#0-项目概念与核心理念)
1. [现状与问题](#1-现状与问题)
2. [架构方案全景](#2-架构方案全景)
3. [API 层方案对比](#3-api-层方案对比)
4. [LLM 多模型集成方案](#4-llm-多模型集成方案)
    - 4.6 [LLM 配置段（coach_defaults.yaml 新增）](#46-llm-配置段coach_defaultsyaml-新增)
5. [通信协议方案](#5-通信协议方案)
6. [前端框架方案](#6-前端框架方案)
7. [UI 设计工具链](#7-ui-设计工具链)
8. [GitHub 开源参考对照表](#8-github-开源参考对照表)
9. [详细 API 合约设计](#9-详细-api-合约设计)
    - 9.2.1 [错误响应格式](#921-错误响应格式)
    - 9.5.1 [WebSocket 连接管理](#951-websocket-连接管理)
10. [交叉评分矩阵与最终推荐](#10-交叉评分矩阵与最终推荐)
11. [实施路线图](#11-实施路线图)
12. [成本估算](#12-成本估算)
13. [测试策略](#13-测试策略)
14. [成功标准](#14-成功标准)

---

## 0. 项目概念与核心理念

> 本章是为其他 AI 大模型（DeepSeek、Claude、GPT 等）提供的项目背景说明。
> 任何参与此项目 API 设计、前端设计、UI 设计的 AI 模型，必须先理解本章内容，
> 否则可能做出违背系统核心原则的设计决策。

### 0.1 项目是什么

**Coherence（一致性）** 是一个**自适应AI教练系统**的全栈实现。它的核心不是"聊天机器人"，而是一个**认知主权保护系统**——旨在通过 AI 辅助提升用户的学习迁移、创造性和独立思考能力，同时确保用户始终保持对系统的主导权。

项目版本号 V18.8.3，名称"认知主权保护系统"。

### 0.2 三大同权目标（系统存在的理由）

所有功能的取舍标准：

| 目标 | 含义 | 衡量方式 |
|------|------|---------|
| **学习迁移** | 用户将学到的技能应用到新场景的能力 | D7/D30/D90 迁移测试 |
| **创造性** | 发散思维和跨域联想能力 | 双周不低于基线 -3% |
| **独立思考** | 用户在无辅助下的自主表现提升 | No-Assist 评估分数趋势 |

**任何与此三目标冲突的设计决策，以三目标优先。**

### 0.3 三大同权（用户权力 — "Three Hard Rights"）

这是系统最底层的伦理设计约束，API 和前端设计**必须尊重**：

| 权力 | 含义 | 前端体现 |
|------|------|---------|
| **改写权 (Rewrite Right)** | 用户有权改写 AI 的任何前提假设 | 脉冲确认弹窗——每次 HIGH 强度动作前弹出"接受/改写"选项 |
| **远足权 (Excursion Right)** | 用户有权暂时脱离 AI 的推荐路径探索其他选项 | 远足入口按钮——触发后 AI 推荐非偏好/非最优路径 |
| **退出权 (Exit Right)** | 用户随时可以降低或退出 AI 干预 | 辅助强度指示器 + 一键降级按钮 |

### 0.4 硬红线（不可违反的设计约束）

```
1. 不输出医疗/心理诊断式权威结论
   → 前端不应显示疾病名称、诊断结论等医疗表述
2. 高风险动作必须可回退
   → 前端应提供撤销/回退操作
3. 因果只做证据排序，不做真值承诺
   → 前端不应展示"因果结论"，只展示"关联证据排序"
4. 不让用户长期沦为审核员
   → 前端设计要减少频繁的确认弹窗
5. 创造性双周不低于基线 -3%
   → 仪表盘应显示创造性趋势，触发告警
```

### 0.5 系统架构哲学

#### 治理优先 (Governance First)

系统不是"先用 AI 生成内容再过滤"，而是**先经过治理再输出**：

```
用户输入 → 意图解析 → 策略编排 → DSL 构建 → 安全校验 → 门禁验证 → 输出
                                                    ↑
                                            治理层在所有输出之前
```

**这意味着什么**：治理不是后置过滤器，而是前置约束。门禁阻断的不是"已发送的消息"，而是"将要发送的动作"。API 设计必须保持这种治理优先的顺序——不能先发送再审核。

#### 合约冻结 (Contract Freeze)

系统中有 **11 份冻结合约**，一旦 status=frozen 就不可修改。这是架构的刚性约束：

| # | 合约 | 冻结时间 | 关键内容 |
|---|------|---------|---------|
| 1 | `ledger.json` | 预冻结 | 事件账本 schema |
| 2 | `gates.json` | 预冻结 | **8 道门禁定义** |
| 3 | `coach_dsl.json` | Phase 1 | **8 种 action_type 枚举** |
| 4 | `operations_governance.json` | Phase 8 | Audit Gate + Window Gate 阈值 |

**Phase 9 不能修改任何合约**。API 可以引用合约字段，但不能变更合约定义。

#### 禁改边界 (Forbidden Zone)

```
src/inner/**  — 绝对禁止修改 (核心治理模块)
src/middle/** — 绝对禁止修改 (状态估计/决策/安全)
src/outer/**  — 绝对禁止修改 (API 占位, Phase 9 改为调用不修改)
contracts/    — 禁止修改 (只读引用)
tests/        — 只新增不修改
```

**Phase 9 策略**：`src/outer/api/` 是新增文件，不修改已有文件。`src/outer/api/service.py` 保持原样不动，新建 `src/outer/api/main.py` 等文件。

#### 组件默认 OFF (Opt-in Architecture)

所有 Coach 轨组件默认 `enabled: false`，用户主动启用：

```yaml
# config/coach_defaults.yaml
ttm:        { enabled: false }
sdt:        { enabled: false }
flow:       { enabled: false }
counterfactual: { enabled: false }
mapek:      { enabled: false }
mrt:        { enabled: false }
audit_health: { enabled: false }
window_consistency: { enabled: false }
```

**Phase 9 新增 LLM 配置段也必须默认 off**：
```yaml
llm:
  enabled: false        # ← 必须默认关闭
  provider: "deepseek"
  ...
```

### 0.6 CCA-T 教练引擎（系统的核心）

CoachAgent 是系统的核心类，在 `src/coach/agent.py` 中。它的 `act()` 方法格式：

```python
class CoachAgent:
    def act(self, user_input: str, context: dict = None) -> dict:
        """处理用户输入，返回 DSL 动作包 + 治理元数据。"""
```

**输入**：用户文本消息 + 可选的上下文

**输出**：一个包含以下信息的 dict：
- DSL 动作包 (action_type, payload, intent, trace_id)
- 治理结果 (gate_decision, audit_level, safety_allowed)
- 行为科学 (ttm_stage, sdt_profile, flow_channel)
- V18.8 运行时 (premise_rewrite_rate, assist_level, pulse_history)
- Phase 5-7 (counterfactual_result, mrt_assignment 等)

**重要**：act() 的返回值是**结构化数据**，不是自然语言文本。回复文本目前由 Python 模板填充，生硬且不自然——这正是 Phase 9 LLM 集成要解决的问题。

### 0.7 DSL 动作类型（系统能"说"什么）

CoachAgent 的输出被组织为 8 种 DSL action_type，前端需要根据不同的 action_type 选择不同的渲染组件：

| action_type | 含义 | 前端渲染方式 |
|-------------|------|-------------|
| `probe` | 无辅助探查——评估用户当前能力 | 提问框 + 输入框，无提示 |
| `challenge` | 挑战性任务——适度超出当前能力 | 任务卡片 + 难度标识 + 提示开关 |
| `reflect` | 引导反思——帮助用户自我觉察 | 引导性问题 + 可选格式提示 |
| `scaffold` | 搭建脚手架——分解复杂任务 | 步骤列表 + 支持级别指示 |
| `suggest` | 系统建议——给出推荐选项 | 建议卡片 + source_tag 标注 |
| `pulse` | **主权确认脉冲**——改写/接受选择 | **弹窗两选项 [接受] [改写]** |
| `excursion` | **模型外远足**——探索非偏好路径 | **多选项卡片 + 退出按钮** |
| `defer` | 暂缓/降级——降低干预强度 | 提示消息 + 恢复条件说明 |

特别是 `pulse` 和 `excursion` 需要特殊的弹窗/面板交互，不能简单的展示为文本气泡。

### 0.8 八门禁升档闸门（8 Gates）

系统有 8 道门禁保护升档决策。所有门禁通过才允许系统提升干预强度（AND 逻辑）：

| Gate | 名称 | 指标 | 来源 |
|------|------|------|------|
| 1 | Agency Gate | premise_rewrite_rate ≥ 阈值 | 改写/接受比例 |
| 2 | Excursion Gate | 有探索证据 | 远足使用记录 |
| 3 | Learning Gate | No-Assist 不持续下滑 | 无辅助得分趋势 |
| 4 | Relational Gate | 顺从信号 ≤ 阈值 | 被动同意率 |
| 5 | Causal Gate | 三诊断全部通过 | 平衡性/负对照/安慰剂 |
| 6 | Audit Gate | P0=0 且 P1≤阈值 | 审计健康评分 |
| 7 | Framing Gate | 选择架构无操纵效应 | chi-square 检验 |
| 8 | Window Gate | 数据版本一致 + 新鲜 | schema 一致性检查 |

**前端应展示 8 门禁状态**——用户可以看到哪些门禁通过/阻断，以及当前的升档决策 (GO/WARN/BLOCK)。

### 0.9 项目状态概要（Phase 9 启动前）

```
Coach 轨:      Phase 0-8 全部 GO
B 轨:          B1-B8 全部 GO
C 轨:          C1-C6 全部 GO
测试:          1070 passed / 0 failed
合约:          11 份全部 frozen
代码源文件:     ~50 个, ~250KB
架构分层:      内圈 → 中圈 → 外圈 → 教练引擎 → MAPE-K
当前 API:      src/outer/api/service.py (占位, 非 HTTP 服务)
当前前端:      无
```

### 0.10 关键术语表（供 AI 模型参考）

| 术语 | 解释 | 英文 |
|------|------|------|
| 认知主权 | 用户对 AI 系统的主导权和控制权 | Cognitive Sovereignty |
| CCA-T | 教练引擎核心算法 | Coach-Centric Adaptation Transformer |
| DSL 动作包 | 系统输出的结构化指令包 | Domain-Specific Language Packet |
| TTM | 阶段变化理论——用户行为改变的五阶段模型 | Transtheoretical Model |
| SDT | 自决理论——自主性/胜任感/关联性 | Self-Determination Theory |
| MRT | 微随机实验——A/B 测试的因果推断 | Micro-Randomized Trial |
| MAPE-K | 控制循环——监控/分析/规划/执行/知识 | Monitor-Analyze-Plan-Execute-Knowledge |
| Gate | 门禁——升档的 check point | Gate |
| Pulse | 主权确认脉冲——给用户的改写/接受选择 | Sovereignty Pulse |
| Excursion | 远足——脱离推荐的探索模式 | Excursion |
| Ledger | 事件账本——所有操作的不可变日志 | Event Ledger |
| 禁改边界 | 不可修改的代码区域 | Forbidden Boundary |
| 合约冻结 | 接口定义锁定不可变更 | Contract Freeze |

---

## 1. 现状与问题

### 1.1 当前系统

```
用户输入 (纯文本)
    │
    ▼
CoachAgent.act()
    ├── 意图解析 ── 基于关键词映射 (约 20 个关键词)
    ├── 策略编排 ── PolicyComposer (YAML 规则引擎)
    ├── DSL 构建 ── 8 种 action_type 的结构化动作包
    ├── 安全校验 ── pipeline (L0→L1→L2→Decision→Safety)
    ├── 八门禁 ── GateEngine 验证 (AND 逻辑)
    ├── Phase 4/5/6/7 可选组件 (TTM/SDT/心流/语义安全/MAPE-K/MRT)
    └── 返回 dict ── 结构化数据 + 固定模板回复文本
```

**核心缺陷**：
1. **回复文本是模板填充** — 生硬、重复、不自然
2. **意图解析是关键词匹配** — 无法理解复杂语义
3. **没有 HTTP 接口** — 只能 Python 进程内调用
4. **没有前端界面** — 纯代码交互
5. **没有会话持久化** — 进程重启后会话丢失

### 1.2 需要解决的关键问题

| 问题 | 严重性 | 方案涉及 |
|------|--------|---------|
| 无 HTTP API | 阻断性 | API 层设计 |
| 回复文本不自然 | 体验差 | LLM 集成 |
| 意图识别有限 | 功能弱 | LLM 增强 / 关键词+LLM 混合 |
| 无前端界面 | 阻断性 | Flutter 前端 |
| 无流式输出 | 体验差 | WebSocket / SSE |
| 会话不持久 | 功能弱 | 会话管理 + 存储 |

---

## 2. 架构方案全景

### 2.1 三种核心架构模式

#### 架构 A：CoachAgent 中心化（推荐）

```
Flutter App
    │ REST + WebSocket
    ▼
┌─────────────────────────────────────────┐
│            FastAPI 服务层                 │
│  认证 → 路由 → 会话管理 → LLM 协调        │
└──────────┬──────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼              ▼
┌──────────┐ ┌──────────┐
│CoachAgent│ │ LLM 生成 │ ← DeepSeek / Claude / GPT
│治理+门禁  │ │回复文本   │
│DSL+安全   │ │流式输出   │
└──────────┘ └──────────┘
    │              │
    └──────┬───────┘
           ▼
      CoachAgent 的输出经过 LLM 增强后返回
      LLM 输出受门禁约束 (GateEngine 二次校验)
```

**核心逻辑**：CoachAgent 产出 DSL 结构化动作 + 治理元数据 → LLM 将结构化数据转化为自然语言回复 → 门禁约束 LLM 输出。治理永远是第一道和最后一道关卡。

#### 架构 B：LLM 中心化

```
Flutter App
    │
    ▼
LLM (DeepSeek/Claude/GPT) — 主入口
    ├── 意图解析
    ├── 对话策略
    ├── 回复生成
    └── 结构化输出
         │
         ▼
    CoachAgent — 治理过滤层
         ├── 安全校验
         ├── 八门禁验证
         └── 阻断时重生成
```

**核心逻辑**：LLM 负责一切，CoachAgent 退化为"审核层"。对话质量高，但 CoachAgent 的 TTM/SDT/心流等策略逻辑与 LLM 输出可能冲突。

#### 架构 C：双引擎并行

```
用户输入 → 同时送入 CoachAgent 和 LLM
              │              │
              ▼              ▼
        DSL packet  ← ─ →  自然语言回复
        治理元数据            对话文本
              │              │
              └──────┬───────┘
                     ▼
              前端同时渲染两者
              结构化视图 + 对话气泡
```

**核心逻辑**：两者各司其职互不干扰。治理数据显示在仪表盘，对话文本显示在聊天区。简单但治理与对话脱节。

### 2.2 三架构对比

| 维度 | A: CoachAgent 中心化 | B: LLM 中心化 | C: 双引擎并行 |
|------|-------------------|--------------|-------------|
| 治理完整性 | ⭐⭐⭐⭐⭐ 完整 | ⭐⭐⭐ 部分失效 | ⭐⭐⭐⭐ 治理与对话脱节 |
| 对话质量 | ⭐⭐⭐⭐ LLM 增强 | ⭐⭐⭐⭐⭐ LLM 主导 | ⭐⭐⭐⭐ |
| 实现复杂度 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 较高 | ⭐⭐ 简单 |
| 架构稳定性 | ⭐⭐⭐⭐⭐ 已有体系不动 | ⭐⭐ 大规模重构 | ⭐⭐⭐⭐⭐ 最安全 |
| TTM/SDT 集成 | ⭐⭐⭐⭐⭐ DSL 含阶段信息 | ⭐⭐ 可能冲突 | ⭐⭐⭐ 独立展示 |
| 门禁有效性 | ⭐⭐⭐⭐⭐ 双重约束 | ⭐⭐⭐ 可能被绕过 | ⭐⭐⭐⭐ 仅仪表盘展示 |

> **结论**：架构 A 是唯一保留系统核心价值（治理/门禁/因果）的选择。B 和 C 会让 Phase 0-8 的投入大打折扣。

---

## 3. API 层方案对比

### 3.1 方案一览

| 方案 | 技术栈 | 与 CoachAgent 的亲和性 | 性能 | 生态成熟度 |
|------|--------|----------------------|------|-----------|
| **P1: FastAPI** | Python + Uvicorn | ⭐⭐⭐⭐⭐ 同进程调用 | ⭐⭐⭐⭐ 异步 | ⭐⭐⭐⭐⭐ |
| P2: Node.js BFF | Express/Fastify + Python | ⭐⭐ 跨进程 RPC | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| P3: GraphQL | Strawberry / Ariadne | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| P4: gRPC | protobuf | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 3.2 详细分析

#### P1: FastAPI — 推荐

```
优势:
  - 与 CoachAgent 同语言、同进程，零序列化开销
  - FastAPI 原生异步 + Pydantic 校验，完美匹配 REST API 需求
  - Uvicorn 已安装 (0.40.0)，零额外依赖
  - WebSocket 原生支持 (Starlette 内置)
  - SSE StreamingResponse 内置
  - 监控: Prometheus 客户端可直接集成

劣势:
  - 非前端团队首选（但本项目中无前端团队）
  - 没有 GraphQL 的按需取字段能力

参考项目:
  - ai-chat-orchestrator (fhhd11): FastAPI LLM 网关 + SSE 流式 + 多模型
  - GroqStreamChain: FastAPI + WebSocket + 实时流式
  - Verbose (pixelotes): 同栈 Flutter + FastAPI
```

#### P2: Node.js BFF

```
适用场景: 前后端分离，前端团队主导
本项目: 无前端团队，增加 Node.js 层只是额外维护负担
结论: 不推荐
```

#### P3: GraphQL

```
适用场景: 前端需要灵活查询，多数据源聚合
本项目: 单数据源 (CoachAgent)，端点固定 (chat/session/gates/metrics)
         GraphQL 的灵活性无发挥空间，且增加复杂度
结论: 不推荐
```

#### P4: gRPC

```
适用场景: 微服务间高性能通信，多语言异构系统
本项目: 单进程单服务，gRPC 严重过设计
结论: 不推荐
```

> **结论**：FastAPI 是唯一合理选择。已安装、零依赖、与 CoachAgent 同语言、全功能（REST + WebSocket + SSE + Pydantic）。

---

## 4. LLM 多模型集成方案

### 4.1 LLM 集成模式对比

| 模式 | 描述 | LLM 调用位置 | 延迟影响 |
|------|------|-------------|---------|
| M1: 回复生成 | CoachAgent 输出 DSL → LLM 生成回复文本 | API 层 (act() 之后) | +1-3s |
| M2: 意图增强 | LLM 辅助意图解析 + CoachAgent 决策 | act() 内部可选 | +0.5-1s |
| M3: 全替换 | LLM 完全替代 CoachAgent 的 NLP 部分 | act() 内部 | +2-5s |
| M4: 离线批量 | CoachAgent 全本地 → LLM 异步增强已存对话 | 后台异步 | 零（前台） |

### 4.2 LLM 供应商对比

| 供应商 | 模型 | 价格 (input/M) | 价格 (output/M) | 上下文 | 流式 | 质量 | 延迟 |
|--------|------|---------------|----------------|--------|------|------|------|
| **DeepSeek** | deepseek-chat | **$0.14** | **$0.28** | 128K | ✅ | ⭐⭐⭐⭐ | ~1.5s |
| Claude | claude-sonnet-4-6 | $3.00 | $15.00 | 200K | ✅ | ⭐⭐⭐⭐⭐ | ~2s |
| GPT | gpt-4o | $2.50 | $10.00 | 128K | ✅ | ⭐⭐⭐⭐⭐ | ~1.5s |
| 本地 | ollama (qwen2.5) | **免费** | **免费** | 32K | ✅ | ⭐⭐⭐ | ~3-10s |
| Gemini | gemini-2.0-flash | $0.10 | $0.40 | 1M | ✅ | ⭐⭐⭐⭐ | ~1s |

> **DeepSeek 成本优势**：同样是中文教练对话，DeepSeek 的成本仅为 Claude 的 **1/20**，GPT 的 **1/18**。按日均 100 次对话计算，DeepSeek ≈ $0.07/天，Claude ≈ $1.3/天。

### 4.3 DeepSeek API 集成要点

```
端点: https://api.deepseek.com/v1/chat/completions
兼容性: OpenAI SDK 兼容 (改 base_url)
Python SDK:
  from openai import OpenAI
  client = OpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com")
  
  或通过 Anthropic 兼容接口:
  base_url="https://api.deepseek.com/anthropic"
  
模型: deepseek-chat (DeepSeek-V3)
     deepseek-reasoner (DeepSeek-R1, 不支持 function calling)

最佳实践:
  - 启用 stream=True 流式输出
  - 使用连接池 (requests.Session()) 提升吞吐量
  - 指数退避重试 (初始 1s, 最大 30s)
  - temperature=0.7 (教练对话)
  - max_tokens=1024 (单次回复)
```

### 4.4 LLM 抽象层设计

```python
# src/outer/api/llm.py — LLM 供应商抽象层

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator

@dataclass
class LLMConfig:
    provider: str = "deepseek"       # deepseek | claude | openai | ollama
    api_key: str = ""
    base_url: str = ""               # 自动根据 provider 填充
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = True

class LLMProvider(ABC):
    """LLM 供应商抽象接口。"""
    
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        ...

class DeepSeekProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = config.model
    
    async def generate(self, system_prompt, messages, stream=True):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            stream=stream,
            temperature=0.7,
            max_tokens=1024,
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class ClaudeProvider(LLMProvider):
    """Claude API 实现 (Anthropic SDK)"""
    ...

class OllamaProvider(LLMProvider):
    """本地 ollama 实现"""
    ...

class LLMFactory:
    """工厂 + 自动降级。"""
    @staticmethod
    def create(config: LLMConfig) -> LLMProvider:
        providers = {
            "deepseek": DeepSeekProvider,
            "claude": ClaudeProvider,
            "ollama": OllamaProvider,
        }
        provider_cls = providers.get(config.provider)
        if not provider_cls:
            raise ValueError(f"Unknown provider: {config.provider}")
        return provider_cls(config)

class LLMService:
    """LLM 服务：自动降级 + 门禁约束。"""
    
    def __init__(self, config: LLMConfig):
        self._primary = LLMFactory.create(config)
        self._fallback = TemplateFallback()  # 模板回复降级
    
    async def generate_reply(
        self, dsl: dict, history: list[dict],
    ) -> AsyncGenerator[str, None]:
        try:
            prompt = self._build_prompt(dsl, history)
            async for chunk in self._primary.generate(prompt, ...):
                yield chunk
        except Exception as e:
            # 自动降级到模板回复
            yield self._fallback.generate(dsl)
```

### 4.5 流式输出方案

LLM 回复的流式输出有三种选择：

| 方案 | 实现 | 延迟 | 复杂度 | 推荐场景 |
|------|------|------|--------|---------|
| SSE | FastAPI StreamingResponse + EventSource | 低 | ⭐⭐ | Web 前端 |
| **WebSocket** | FastAPI WebSocket + Flutter web_socket_channel | 最低 | ⭐⭐⭐ | **Flutter 移动端** |
| Chunked HTTP | Transfer-Encoding: chunked | 中 | ⭐ | 简单场景 |

> **推荐 WebSocket**：Flutter 端 WebSocket 生态成熟（web_socket_channel），且 WebSocket 可同时处理脉冲确认的双向通信，一条连接解决所有实时需求。

### 4.6 LLM 配置段（coach_defaults.yaml 新增）

```yaml
# ── Phase 9: LLM 供应商配置 ──────────────────────────
llm:
  enabled: false                # 默认关闭，零行为漂移
  provider: "deepseek"          # deepseek | claude | openai | ollama
  api_key: ""                   # 从环境变量读取优先
  base_url: ""                  # 留空自动按 provider 填充
  model: "deepseek-chat"        # deepseek-chat | claude-sonnet-4-20241022 | ...
  temperature: 0.7
  max_tokens: 1024
  stream: true
  timeout_seconds: 30
  retry:
    max_retries: 3
    initial_delay: 1.0          # 指数退避初始秒数

# ── API 服务配置 ─────────────────────────────────────
api:
  enabled: false
  host: "127.0.0.1"
  port: 8000
  token: "coherence-dev-token"
  cors_origins: ["http://localhost:5173"]
  rate_limit:
    max_requests_per_minute: 60
```

**关键约束**：
- `llm.enabled: false` — 保证零行为漂移，用户主动配置 api_key 并设为 true 才会调用外部 API
- `api_key` 优先从环境变量 `COHERENCE_LLM_API_KEY` 读取，不在 YAML 中存储明文密钥
- `provider` 切换后只需重启服务即可切换底层 LLM，无需修改代码

---

## 5. 通信协议方案

| 方案 | 方向 | 实时性 | 适用端点 | Flutter 支持 |
|------|------|--------|---------|-------------|
| **REST HTTP** | 单向 | 请求-响应 | POST /chat, GET /session | ✅ Dio/http |
| **WebSocket** | **双向** | **实时** | 脉冲确认、远足、流式回复 | ✅ web_socket_channel |
| SSE | 服务端→客户端 | 实时 | 流式回复单向 | ⚠️ 需 eventsource 包 |

**推荐组合：REST + WebSocket**

- REST：普通对话、状态查询、指标读取
- WebSocket：脉冲确认实时弹窗、远足交互、LLM 流式文字推送、门禁状态变更推送

---

## 6. 前端框架方案

### 6.1 框架对比

| 方案 | 平台 | 成本 | 性能 | 生态 | LLM/流式支持 |
|------|------|------|------|------|-------------|
| **D1: Flutter** | iOS + Android + Web + Mac | 一套代码 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | web_socket_channel 成熟 |
| D2: React Native | iOS + Android | 一套代码 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 原生 WebSocket |
| D3: Web SPA | Web 浏览器 | 仅 Web | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | EventSource / WS |
| D4: 原生双端 | Swift + Kotlin 各一 | 两套代码 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 原生支持 |

> **结论**：已经选定 Flutter，不做变动。

### 6.2 Flutter 架构参考

从 GitHub 开源项目中提取的最佳实践：

| 参考项目 | 架构模式 | 状态管理 | 可借鉴点 |
|---------|---------|---------|---------|
| **deepseek-clone** (fakingai) | Clean Architecture 三层 | BLoC | 接口结构、流式展示、文件上传 |
| **groq-flutter-chat** (extrawest) | Feature-based Clean | BLoC + GetIt | 主题切换、消息组件 |
| **Verbose** (pixelotes) | 简单分层 | Provider | 同栈 Flutter+FastAPI 可完整参考 |

**推荐 Flutter 项目结构**：

```
mobile/
├── lib/
│   ├── main.dart
│   ├── app/
│   │   ├── app.dart            # MaterialApp + 主题
│   │   └── router.dart         # GoRouter 路由
│   ├── core/
│   │   ├── api/
│   │   │   ├── api_client.dart      # Dio HTTP 客户端
│   │   │   ├── ws_client.dart       # WebSocket 客户端
│   │   │   └── endpoints.dart       # 端点常量
│   │   ├── config/
│   │   │   └── env.dart             # 环境配置
│   │   └── theme/
│   │       ├── app_theme.dart
│   │       └── colors.dart
│   ├── features/
│   │   ├── chat/
│   │   │   ├── models/
│   │   │   │   ├── message.dart
│   │   │   │   └── chat_response.dart
│   │   │   ├── providers/
│   │   │   │   └── chat_provider.dart
│   │   │   ├── widgets/
│   │   │   │   ├── chat_bubble.dart
│   │   │   │   ├── chat_input.dart
│   │   │   │   └── streaming_text.dart
│   │   │   └── screens/
│   │   │       └── chat_screen.dart
│   │   ├── pulse/
│   │   │   ├── widgets/
│   │   │   │   └── pulse_modal.dart
│   │   │   └── providers/
│   │   │       └── pulse_provider.dart
│   │   ├── dashboard/
│   │   │   ├── widgets/
│   │   │   │   ├── ttm_stage_card.dart
│   │   │   │   ├── sdt_radar.dart
│   │   │   │   └── gate_status.dart
│   │   │   └── screens/
│   │   │       └── dashboard_screen.dart
│   │   └── settings/
│   │       ├── widgets/
│   │       └── screens/
│   │           └── settings_screen.dart
│   └── shared/
│       └── widgets/
│           ├── loading_indicator.dart
│           └── error_display.dart
├── pubspec.yaml
├── test/
└── assets/
```

**依赖选择**：

```yaml
dependencies:
  flutter:
    sdk: flutter
  # HTTP
  dio: ^5.x
  # WebSocket
  web_socket_channel: ^3.x
  # 状态管理
  flutter_riverpod: ^2.x        # 或 bloc: ^8.x
  # 路由
  go_router: ^14.x
  # 本地存储
  shared_preferences: ^2.x
  # 图表（仪表盘）
  fl_chart: ^0.x
  # Markdown 渲染
  flutter_markdown: ^0.x
```

---

## 7. UI 设计工具链

前端界面可以通过 AI 工具辅助设计，减少手动调 UI 的时间。

### 7.1 可用工具

| 工具 | 类型 | Flutter 支持 | 定价 | 适合 |
|------|------|-------------|------|------|
| **Google Stitch** | AI → UI 设计稿 | **直接导出 Flutter 代码** | 免费 (Labs) | 界面视觉设计 |
| **FlutterFlow** | AI + 可视化 | Flutter 原生 | 免费 + 付费 | 快速原型搭建 |
| **v0.dev** | AI → React 代码 | 需手动转 Flutter | 免费额度 | 参考设计灵感 |
| **ai_ui_render** | Flutter 包 | Flutter 原生 | 开源免费 | 运行时 AI 生成 UI |

### 7.2 推荐工作流

```
1. 需求描述 → Google Stitch (语音/文本 prompt)
   │  输出: Flutter 界面代码 + DESIGN.md
   ▼
2. 在 Flutter 项目中导入 Stitch 导出的组件
   │  调整: 主题色、间距、字体
   ▼
3. 连接真实 API + WebSocket
   │  替换 mock 数据为真实数据流
   ▼
4. FlutterFlow 做 A/B 测试 (可选)
   │  快速验证多个布局方案
   ▼
5. 定稿 → 手动优化细节
```

### 7.3 Stitch 具体使用场景

| 页面 | Stitch Prompt 示例 | 预期输出 |
|------|-------------------|---------|
| 对话页 | "移动端 AI 教练对话界面，气泡式布局，用户消息右对齐蓝色，AI 消息左对齐灰色带头像。底部输入框带发送按钮和快捷建议。支持 Markdown 渲染" | 对话 Scaffold + 气泡组件 |
| 脉冲弹窗 | "半透明遮罩弹窗，显示系统前提声明，两个按钮：接受(绿色)/改写(橙色)，毛玻璃效果" | PulseModal widget |
| 仪表盘 | "深色主题仪表盘，顶部 TTM 阶段进度条(5 阶段)，中部雷达图显示 SDT 三维评分，底部 8 个门禁状态圆点(绿/红)" | Dashboard scaffold |
| 远足面板 | "底部滑出面板，显示 3-4 个选项卡片，每张卡片带图标和简短描述，点击选择后自动收起" | ExcursionPanel |

### 7.4 设计参考资源

| 资源 | 链接 | 说明 |
|------|------|------|
| Flutter 官方 Design 库 | [flutter.github.io/samples](https://flutter.github.io/samples) | Material 3 组件 |
| Flutter AI Toolkit | [docs.flutter.dev/ai/ai-toolkit](https://docs.flutter.dev/ai/ai-toolkit) | 官方 AI 对话组件 |
| Google Stitch | [stitch.google](https://stitch.google) | AI UI 生成 Flutter 代码 |
| flutter_gen_ai_chat_ui | [pub.dev](https://pub.dev/packages/flutter_gen_ai_chat_ui) | 预制对话 UI 组件库 |

---

## 8. GitHub 开源参考对照表

### 8.1 后端参考

| 仓库 | Stars | 技术栈 | 借鉴点 | 对接本项目的具体价值 |
|------|-------|--------|--------|-------------------|
| [ai-chat-orchestrator](https://github.com/fhhd11/ai-chat-orchestrator) | 活跃 | FastAPI + SSE + LiteLLM | 多 LLM 网关架构、流式输出、成本追踪 | **API 层架构可直接参考** |
| [GroqStreamChain](https://github.com/The-Data-Dilemma/GroqStreamChain) | 活跃 | FastAPI + WebSocket + LangChain | WebSocket 实时流式 + 会话管理 | **WebSocket 实现参考** |
| [Verbose](https://github.com/pixelotes/verbose) | 活跃 | FastAPI + Flutter | 同栈完整项目参考 | **全栈结构参考 (同技术栈)** |
| [langchain-bot](https://github.com/benyell/langchain-bot) | — | FastAPI + LangChain + GPT-4 | SSE StreamingResponse 实现 | **流式输出后端代码** |

### 8.2 前端参考

| 仓库 | Stars | 技术栈 | 借鉴点 | 对接本项目的具体价值 |
|------|-------|--------|--------|-------------------|
| [deepseek-clone](https://github.com/fakingai/deepseek-clone) | 活跃 | Flutter Clean Architecture + BLoC | 三层架构、流式文字展示、文件上传 | **Flutter 项目结构参考** |
| [groq-flutter-chat](https://github.com/extrawest/groq-flutter-chat) | 活跃 | Flutter + BLoC + GetIt | 对话 UI 组件、主题切换 | **对话组件代码参考** |
| [FlutterClaw](https://github.com/flutterclaw/flutterclaw) | AGPL-3.0 | Flutter + 多 LLM 供应商 | 多模型切换、设备集成 | **多 LLM Provider 切换参考** |
| flutter_gen_ai_chat_ui | [pub.dev](https://pub.dev/packages/flutter_gen_ai_chat_ui) | Flutter 包 | 开箱即用对话 UI | **直接引用来加速开发** |
| ai_ui_render | [pub.dev](https://pub.dev/packages/ai_ui_render) | Flutter 包 | AI 生成 UI 运行时 | **高级: 动态 UI 渲染** |

### 8.3 设计参考

| 资源 | 类型 | 借鉴点 |
|------|------|--------|
| [Flutter AI Toolkit](https://docs.flutter.dev/ai/ai-toolkit) | 官方工具包 | 预制 AI 对话组件、流式渲染 |
| [Google Stitch](https://stitch.google) | AI UI 生成 | 提示词 → Flutter 界面代码 |
| [FlutterFlow](https://docs.flutterflow.io/designer/) | AI + 可视化 | 快速原型 + 导出 Flutter |

---

## 9. 详细 API 合约设计

### 9.1 端点总览

```
Base URL: http://localhost:8000/api/v1
Auth: Authorization: Bearer <token>

REST:
  POST   /chat           — 发送消息 (核心)
  GET    /session        — 会话状态
  GET    /gates          — 8 门禁状态
  GET    /metrics        — 系统指标 (MRT/审计)
  GET    /history        — 历史消息
  POST   /session/reset  — 重置会话
  GET    /health         — 健康检查

WebSocket:
  WS     /ws             — 实时双向通道
```

### 9.2 POST /api/v1/chat — 完整合约

```python
# Request
class ChatRequest(BaseModel):
    message: str                          # 用户消息文本
    session_id: str = "default"           # 会话 ID
    pulse_response: str | None = None     # "accept" | "rewrite" | None
    excursion_choice: str | None = None   # 远足选项
    stream: bool = False                  # 是否流式返回回复

# Response (非流式)
class ChatResponse(BaseModel):
    # ── 回复内容 ──
    reply_text: str                       # LLM 或模板生成的回复
    reply_type: str = "text"              # text | pulse_required | excursion | error
    suggestions: list[str] = []           # 快捷建议按钮 (2-3个)
    
    # ── DSL 结构化信息 ──
    action_type: str | None = None        # probe/challenge/reflect/scaffold/...
    intent: str | None = None
    dsl_packet: dict = {}
    
    # ── 治理元数据 ──
    gate_decision: str = "GO"             # GO | WARN | BLOCK
    gates_passed: int = 8
    audit_health: dict | None = None
    
    # ── 行为科学 ──
    ttm_stage: str | None = None
    sdt_profile: dict | None = None
    flow_channel: str | None = None
    
    # ── 交互状态 ──
    pulse_needed: bool = False
    pulse_statement: str | None = None
    excursion_active: bool = False
    excursion_options: list[str] | None = None
    
    # ── 会话 ──
    session_id: str
    turn_count: int
    timestamp: str
    
    # ── LLM 信息 ──
    llm_used: bool = False                # 是否使用了 LLM
    llm_provider: str | None = None       # deepseek/claude/...

# Response (流式, 通过 WebSocket)
class StreamChunk(BaseModel):
    type: str = "text"                    # text | done | pulse | error
    content: str = ""                     # 文本片段
    metadata: dict | None = None          # 最终附加的结构化数据
```

#### 9.2.1 错误响应格式

所有端点统一返回以下错误结构：

```python
class ErrorResponse(BaseModel):
    error: str                            # 错误简述
    detail: str | None = None             # 详细说明
    code: str = "INTERNAL_ERROR"          # 错误码
    timestamp: str

# HTTP 状态码映射:
# 401 → {"error": "Unauthorized", "code": "UNAUTHORIZED"}
# 422 → {"error": "Validation Error", "detail": "<field errors>", "code": "VALIDATION_ERROR"}
# 429 → {"error": "Rate Limited", "code": "RATE_LIMITED"}
# 500 → {"error": "Internal Server Error", "code": "INTERNAL_ERROR"}
# 503 → {"error": "LLM Unavailable", "code": "LLM_UNAVAILABLE"}  # LLM 超时/降级时
```

---

### 9.3 GET /api/v1/session

```python
class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    turn_count: int
    pulse_count: int
    excursion_count: int
    
    # 行为科学快照
    ttm_stage: str | None
    sdt_profile: dict | None
    assist_level: float
    
    # 指标
    premise_rewrite_rate: float
    compliance_signal_score: float
    no_assist_trend: str | None
```

### 9.4 GET /api/v1/gates

```python
class GateStatus(BaseModel):
    gate_id: str
    name: str
    status: str                 # pass | fail | disabled
    metric: str
    value: float | None

class GatesResponse(BaseModel):
    gates: list[GateStatus]
    gates_passed: int
    total_gates: int = 8
    decision: str               # GO | WARN | BLOCK
```

### 9.5 WebSocket /api/v1/ws

```
连接后, 双向 JSON 消息:

客户端 → 服务端:
  {"type": "chat", "message": "我今天不想学", "session_id": "default"}
  {"type": "pulse_response", "response": "accept"}
  {"type": "excursion_choice", "choice": "option_2"}
  {"type": "ping"}

服务端 → 客户端:
  {"type": "text", "content": "听起来今天..."}          # 流式文本片段
  {"type": "metadata", "data": {...}}                   # 最终结构化数据
  {"type": "pulse", "statement": "...", "options": [...]} # 脉冲弹窗
  {"type": "excursion", "options": [...]}                # 远足选项
  {"type": "gate_update", "gates": [...], "decision": "GO"}  # 门禁变更
  {"type": "done"}                                       # 回复完成
  {"type": "error", "message": "..."}
  {"type": "pong"}
```

#### 9.5.1 WebSocket 连接管理

```python
# 连接生命周期
# ┌──────────┐     connect      ┌──────────┐    idle 30s    ┌──────────┐
# │ DISCONN  │ ──────────────→  │ CONNECTED │ ────────────→  │ IDLE     │
# └──────────┘                  └──────────┘                 └──────────┘
#                                    │                           │
#                                    │ send ping/pong            │ close
#                                    ▼                           ▼
#                              ┌──────────┐                 ┌──────────┐
#                              │ ACTIVE   │                 │ CLOSED   │
#                              └──────────┘                 └──────────┘

# 心跳: 客户端每 15s 发送 {"type": "ping"}, 服务端回复 {"type": "pong"}
#       服务端 30s 无消息自动断开 (IDLE → CLOSED)
# 重连: Flutter 端指数退避 (1s → 2s → 4s → 8s, 上限 30s)
#       重连后自动恢复会话上下文 (session_id 不变)
# 消息顺序: WebSocket 天然保序 (TCP)，无需额外序列号
# 并发: 单 WebSocket 连接，消息串行处理
#       长回复 (LLM 流式) 期间可以接收来自客户端的 pulse_response
```

**Flutter 端重连策略实现要点**：

```dart
// 伪代码: Flutter WebSocket 重连
class WsReconnector {
  final _channel = WebSocketChannel.connect(uri);
  int _retryCount = 0;
  Timer? _heartbeatTimer;

  void _onDone() {
    if (_retryCount < 5) {
      final delay = Duration(seconds: pow(2, _retryCount).toInt());
      _retryCount++;
      Future.delayed(delay, _connect);
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer = Timer.periodic(Duration(seconds: 15), (_) {
      _channel.sink.add(jsonEncode({"type": "ping"}));
    });
  }
}
```

---

## 10. 交叉评分矩阵与最终推荐

### 10.1 各维度权重

| 维度 | 权重 | 理由 |
|------|------|------|
| 治理完整性 | 30% | 这是系统核心价值，Phase 0-8 投入所在 |
| 对话质量 | 20% | 直接影响用户体验 |
| 开发成本 | 15% | 单人项目，时间有限 |
| 运行成本 | 10% | LLM API 费用可持续性 |
| 可维护性 | 15% | 后续扩展的便利性 |
| 架构风险 | 10% | 技术选型的容错空间 |

### 10.2 方案组合评分

| 组合 | 治理 (30) | 对话 (20) | 开发 (15) | 成本 (10) | 维护 (15) | 风险 (10) | **总分** |
|------|:---------:|:---------:|:---------:|:---------:|:---------:|:---------:|:-------:|
| **A+P1+M1+DeepSeek** | **30** | **18** | **13** | **9** | **14** | **9** | **93** |
| A+P1+M1+Claude | 30 | 19 | 13 | 6 | 14 | 9 | 91 |
| A+P1+M1+本地 | 30 | 15 | 12 | 10 | 13 | 8 | 88 |
| A+P1+M1+M2综合 | 30 | 19 | 11 | 8 | 12 | 8 | 88 |
| B+P1+M3+Claude | 22 | 20 | 10 | 6 | 9 | 6 | 73 |
| C+P1+M4 | 24 | 16 | 14 | 10 | 13 | 10 | 87 |

### 10.3 最终推荐

```
架构:    A (CoachAgent 中心化)
API:     P1 (FastAPI)
LLM:     M1 (回复生成层)
供应商:  DeepSeek (默认, 可切换)
通信:    REST + WebSocket
前端:    D1 (Flutter)
UI 设计:  Google Stitch 辅助 + flutter_gen_ai_chat_ui 组件库
```

**推荐理由**：
1. CoachAgent 中心化架构保留 Phase 0-8 全部治理能力——这是与其他 AI 系统的根本区别
2. DeepSeek 提供最优性价比——中文教练对话场景下质量足够，成本仅为 Claude 的 1/20
3. LLM 作为可选回复生成层——关闭时回到纯本地模式，零依赖零成本
4. LLM 供应商抽象——今天用 DeepSeek，明天可换 Claude/GPT/本地，改配置即可
5. WebSocket 一次性解决流式输出、脉冲确认、门禁推送所有实时需求
6. Google Stitch 加速 UI 设计——从 prompt 到 Flutter 代码，减少手动调 UI 时间
7. Flutter 一阶段覆盖三端——不拆 Web→移动端两阶段

---

## 11. 实施路线图

### 11.1 子阶段划分

```
S9.1: FastAPI 骨架 (1 天)
  ├── main.py — FastAPI 应用 + CORS + 启动入口
  ├── models.py — 全部 Pydantic 请求/响应模型
  ├── auth.py — Token 认证中间件
  ├── session.py — SessionManager (CoachAgent 单例)
  └── routes.py — 路由注册

S9.2: LLM 抽象层 (1 天)
  ├── llm.py — LLMProvider 接口 + DeepSeek/Ollama/Claude 实现
  ├── llm_factory.py — 工厂 + 自动降级
  └── prompts.py — 教练系统提示词模板
  └── config 新增 llm: {enabled: false, provider: "deepseek", ...}

S9.3: POST /chat 核心端点 (1 天)
  ├── 完整 ChatRequest → CoachAgent.act() → LLM 生成 → ChatResponse
  ├── 脉冲响应处理 (pulse_response 字段)
  ├── 错误处理 + 优雅降级
  └── 测试: httpx 测试端点

S9.4: WebSocket 实时通道 (1 天)
  ├── ws.py — 连接管理 + 消息路由
  ├── 流式回复推送 (SSE-like over WS)
  ├── 脉冲确认实时弹窗
  ├── 远足选项推送
  ├── 门禁状态变更推送
  └── 测试: websockets 测试

S9.5: 数据查询端点 (0.5 天)
  ├── GET /session
  ├── GET /gates
  ├── GET /metrics
  └── GET /health

S9.6: Flutter 项目初始化 (1 天)
  ├── 项目脚手架 (推荐的目录结构)
  ├── API 客户端 (Dio)
  ├── WebSocket 客户端
  ├── 状态管理 (Riverpod providers)
  └── 路由配置

S9.7: Flutter 对话界面 (2 天)
  ├── 聊天屏幕 + 消息气泡
  ├── 流式文字显示 (打字机效果)
  ├── 输入框 + 快捷建议按钮
  ├── 脉冲弹窗组件
  └── 远足面板组件
  └── Google Stitch 辅助设计 → 导入组件

S9.8: Flutter 仪表盘 (1 天)
  ├── TTM 阶段可视化
  ├── SDT 雷达图
  ├── 8 门禁状态圆点
  └── 辅助强度指示器

S9.9: 集成测试 + 部署 (1 天)
  ├── 端到端测试 (API → CoachAgent → LLM → 前端)
  ├── Dockerfile (API 服务)
  ├── docker-compose.yml (API + ollama 可选)
  └── 启动脚本
```

### 11.2 路由命令

| 命令 | 子阶段 |
|------|--------|
| `/run_phase9_s1` | FastAPI 骨架 |
| `/run_phase9_s2` | LLM 抽象层 |
| `/run_phase9_s3` | POST /chat 端点 |
| `/run_phase9_s4` | WebSocket 实时通道 |
| `/run_phase9_s5` | 数据查询端点 |
| `/run_phase9_s6` | Flutter 项目初始化 |
| `/run_phase9_s7` | Flutter 对话界面 |
| `/run_phase9_s8` | Flutter 仪表盘 |
| `/run_phase9_s9` | 集成 + 部署 |

---

## 12. 成本估算

### 12.1 LLM API 费用

按单用户日均 100 次对话，每次回复平均 200 output tokens + 500 input tokens：

| 供应商 | 日费用 | 月费用 | 年费用 |
|--------|--------|--------|--------|
| **DeepSeek** | **$0.07** | **$2.1** | **$25** |
| Claude Sonnet | $1.30 | $39 | $468 |
| GPT-4o | $1.05 | $31.5 | $378 |
| 本地 ollama | $0 | $0 | $0 |

### 12.2 基础设施

| 项目 | 费用 | 说明 |
|------|------|------|
| FastAPI 服务 | $0 | 本地运行或任意 VPS |
| DeepSeek API | ~$2/月 | |
| Flutter 开发 | $0 | 开源工具 |
| Google Stitch | $0 (Labs) | 后期可能 $10-12/月 |
| **总计** | **~$2-14/月** | |

### 12.3 开发时间

| 子阶段 | 估计 |
|--------|------|
| S9.1-S9.2 (后端骨架 + LLM) | 2 days |
| S9.3-S9.5 (端点实现) | 2.5 days |
| S9.6-S9.8 (Flutter) | 4 days |
| S9.9 (集成) | 1 day |
| **总计** | **~9.5 天** |

---

## 13. 测试策略

| 类型 | 覆盖范围 | 工具 | 最低通过要求 |
|------|---------|------|-------------|
| API 单元测试 | 各端点输入/输出验证、认证、错误码 | pytest + httpx | 全部 pass |
| WebSocket 测试 | 连接/重连、心跳、流式推送、脉冲/远足协议 | pytest + websockets | 全部 pass |
| 集成测试 | API → SessionManager → CoachAgent.act() 全链路 | pytest | 全部 pass |
| LLM 降级测试 | LLM 超时/失败时自动回退模板回复 | pytest + mock | 全部 pass |
| 回归测试 | 1070 已有测试保持 pass | pytest -q | 1070 pass, 0 fail |
| Flutter 组件测试 | 对话气泡、脉冲弹窗、远足面板、仪表盘组件 | flutter_test | 全部 pass |
| 端到端测试 | 启动服务 → 发送消息 → 验证回复 → 停止 | pytest + subprocess | 全部 pass |

### 13.1 测试文件组织

```
tests/
├── test_phase9_api.py          # API 端点测试 (REST)
├── test_phase9_ws.py           # WebSocket 测试
├── test_phase9_llm.py          # LLM 抽象层测试 (含降级)
├── test_phase9_integration.py  # 全链路集成测试
└── test_s8_*.py                # 已有 Phase 8 测试 (不变)

mobile/test/                    # Flutter 测试
├── widget_test.dart
├── chat_bubble_test.dart
├── pulse_modal_test.dart
└── gate_status_test.dart
```

### 13.2 测试注意事项

- **不修改已有测试文件** — Phase 0-8 的 53 个测试文件保持原样
- **LLM 降级测试** — 必须在无 API key 环境下验证模板回退正常工作
- **WebSocket 并发测试** — 验证流式回复期间 pulse_response 可正常接收
- **回归检查** — 每次子阶段完成前运行 `python -m pytest tests/ -q` 确认零回归

---

## 14. 成功标准

Phase 9 全部完成后，以下标准必须满足：

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | `curl POST /api/v1/chat` 返回正确的教练响应 | 手动 curl + 自动 pytest |
| 2 | 脉冲确认通过 WebSocket 实时推送和接收 | 自动化 WebSocket 测试 |
| 3 | LLM 生成回复可用且自动降级正常 | 切换 enabled=true/false 验证 |
| 4 | Flutter 对话界面可用，显示历史消息 | 手动 + widget 测试 |
| 5 | 仪表盘展示 TTM 阶段、SDT 评分、8 门禁状态 | 手动 + widget 测试 |
| 6 | 1070 已有测试零回归 | `pytest tests/ -q` |
| 7 | 新增 API 测试全部 pass | `pytest tests/test_phase9_*.py -v` |
| 8 | 不修改任何已冻结代码 | `git diff --stat` 确认仅新增文件 |
| 9 | Dockerfile 构建成功 | `docker build .` (可选) |

---

> 完整方案已写入 `reports/phase9_api_architecture_report.md`
>
> 准备开始的话输入 `/run_phase9_s1`
