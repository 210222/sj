# Phase 9 — 深度思考：从后端引擎到交互产品

**编制日期**: 2026-05-05
**当前基线**: 1219 tests pass, Phase 10 S1-S5 GO, LLM 模式已启用 (DeepSeek)
**前置**: Phase 0-8 Coach 轨全部 GO + Phase 10 LLM 引擎已启用

---

## 0. 为什么需要这篇思考文档

Phase 9 是 Coherence 系统从"引擎"到"产品"的关键一跃。在此之前，所有交付都是 Python 后端模块——治理逻辑、教练算法、安全护栏、LLM 生成。用户通过 curl 或测试脚本与系统交互。

Phase 9 的目标是：**让真正的终端用户通过浏览器和手机使用这个系统**。

这不是简单的"加个前端"。Phase 9 涉及：
- 前端与后端的通信协议设计（REST + WebSocket）
- 行为科学理论（TTM/SDT）从后端算法到前端 UI 的具象化
- 认知主权保护（脉冲确认、远足模式）的交互设计
- 治理可视化的"信息透明度 vs 认知过载"平衡
- 多租户骨架（IAM）与单用户现状的渐进式演进

这 5 个问题彼此纠缠，每一个都有多解。本文档逐一拆解，给出推荐方案及理由。

---

## 1. 核心矛盾分析

### 1.1 治理透明 vs 用户认知过载

系统有 8 道安全门禁（Agency/Excursion/Learning/Relational/Causal/Audit/Framing/Window），每一道都在后端实时裁决。后端自然可以记录全部细节。但问题：

- 向 C 端用户展示 8 道门禁 → 认知过载，用户不是安全工程师
- 完全不展示 → 黑箱，违背"认知主权"的核心价值
- 只展示"通过/未通过" → 信息太少，用户无法理解为什么被阻断

**决策**: 三层信息模型

| 层级 | 受众 | 粒度 | 组件 |
|------|------|------|------|
| L1: 宏观健康 | 所有用户 | 三色盾牌（绿/黄/红） | GateShieldBadge |
| L2: 趋势洞察 | 主动用户 | 雷达图 + 能量环（无技术术语） | TTMStageCard + SDTEnergyRings |
| L3: 完整流水线 | 管理员/审计 | 8 门禁流水线 + 下钻裁决详情 | GatePipeline + AuditLogViewer |

**关键约束**: L1 和 L2 中不得出现 gate/pipeline/audit/P0/P1/block 等技术术语。被阻断时的提示必须是 AI 教练的拟人化话术，而非系统级错误码。

### 1.2 脉冲确认的强度与频率矛盾

脉冲确认（Pulse Confirmation）是认知主权保护的核心机制——每次 HIGH 强度动作前弹出"接受/改写"选项。但设计文档明确指出了"脉搏确认疲劳"隐患：

- 每次阻断 → 用户被迫做决策 → 决策疲劳
- 疲劳后用户可能机械点击"接受" → 主权保护形同虚设
- 但完全去掉阻断 → 系统变成无约束的 AI 黑箱

**决策**: 自适应降级三态

| 状态 | 条件 | 前端行为 | 后端计算 |
|------|------|---------|---------|
| hard | 窗口内脉冲 < 2 次 | 阻断式 PulsePanel（Slide-to-Confirm） | PulseService.should_block() → True |
| soft | 窗口内脉冲 ≥ 2 次 | 珊瑚糖色高亮标记，不阻断流程 | should_block() → False |
| none | 非 HIGH 强度动作 | 正常对话，无脉冲 UI | 不触发脉冲事件 |

**窗口**: 10 分钟/每 session，跨窗口重置。

这个设计的微妙之处：`soft` 并不等于"关闭脉冲"，而是"降级为旁路提示"。用户仍然能看到脉冲存在，只是不需要强制决策。这样既解决了疲劳问题，又不完全丢失主权保护。

### 1.3 TTM 状态驱动的 UI 动态性

后端每轮对话都会更新 TTM 阶段检测。Phase 4 的 TTMStateMachine 已经输出了用户倾向性评分（前意向→维持 5 维向量）。Phase 9 需要将这个状态向量映射到 UI 外观。

但存在一个棘手问题：**TTM 阶段检测需要至少 5 轮交互才有置信度**。新用户在最初 5 轮交互中，TTM 阶段为 `unknown`。

**决策**: 新用户默认态

```
TTM 阶段 = unknown → UI 映射为 "precontemplation" 主题
→ 极简界面，suggest_only 输入模式，pulse 禁用
→ 待 5 轮后 TTM 有置信度，渐进式切换到对应 UI
```

这个设计隐含的原则：**宁保守，不冒进**。新用户默认给最少干扰的界面，随着系统对用户的理解加深再逐步开放功能。

### 1.4 WebSocket 连接的生命周期管理

Phase 10 S3 实现了流式 LLM 推送。Phase 9 的 WebSocket 需要承载：用户消息推送、LLM 流式响应、脉冲事件推送、心跳保活。

一个关键问题：**WebSocket 连接中断时，正在进行的 LLM 流式生成怎么办？**

**决策**: 服务端不等待 WS 重连

```
用户 WS 断开 → 服务端继续完成 LLM 生成 → 结果写入内存缓存 (TTL 30s)
→ 用户重连后，检查是否有未消费的流式结果
→ 超过 TTL 则丢弃，用户需重新发送消息
```

这不是最优体验（最优是做持久化队列+断点续传），但对于单用户本地运行的场景，这个设计在复杂度与体验之间取得了合理平衡。

### 1.5 IAM 骨架的边界

Phase 9 第一天不实现真正的多租户。用户目前是单用户本地运行。但状态管理不能采用 session-only 的无 token 架构——因为：

1. 未来多租户扩展时，改造成本极高
2. 前端状态树如果没有 token 根节点，本地存储的管理会混乱
3. 审计日志需要有 identity 锚点

**决策**: 匿名 token + 状态树，不露出登录 UI

```
会话创建 (POST /api/v1/session):
  1. 服务端签发 UUID4 匿名 token（存入 IAMSkeleton._tokens dict）
  2. 返回 { session_id, token, ttm_stage, sdt_scores }
  3. 前端将 token 存入 sessionStorage
  4. 后续请求通过 Authorization header 携带 token

状态树:
  _state_tree[token][session_id] = { ... }
```

**不做的**: 密码认证、OAuth、JWT、Keycloak、RBAC 角色映射这些留到真正的多租户版本。

---

## 2. 架构决策记录 (ADR)

### ADR-1: 前端框架

**问题**: React vs Vue vs Svelte?

**推荐**: React 18 + TypeScript + Vite

**理由**:
- 生态系统最成熟，组件库（@testing-library/react, vitest）完备
- TypeScript 与后端 Python 的类型系统形成互补——API 合约通过 TS 类型保证前端消费一致性
- Vite 的 HMR 在开发体验上显著优于 CRA
- 团队后续 Flutter 移动端开发时，React 的设计模式（组件化、props 单向流）与 Flutter 的 Widget 树有概念对应

### ADR-2: 状态管理

**问题**: Redux / Zustand / Jotai / React Context?

**推荐**: React Context + useReducer，不引入外部状态库

**理由**:
- 单用户系统的状态树规模有限
- 8 个核心状态字段（session, token, ttmStage, messages, pulse, excursion, gates, adminMode）可以用一个 useReducer 管理
- 引入 Redux 等库带来的 boilerplate 在此场景下是纯负债
- 后续如果需要，可以无缝升级到 Zustand

### ADR-3: WebSocket 消息协议

**问题**: 消息格式如何设计以同时支持流式响应和脉冲事件？

**推荐**: 带 `type` 字段的 JSON 消息，共 5 种类型

```typescript
type WSMessageType = 
  | 'user_message'    // 客户端 → 服务端：用户输入
  | 'coach_response'  // 服务端 → 客户端：完整 DSL 响应
  | 'coach_chunk'     // 服务端 → 客户端：流式片段（Phase 10 S3）
  | 'pulse_event'     // 服务端 → 客户端：脉冲确认事件
  | 'pulse_decision'  // 客户端 → 服务端：接受/改写决策
  | 'error'           // 服务端 → 客户端：错误消息
  | 'ping'            // 双向：心跳
```

### ADR-4: 色彩系统实施策略

**问题**: CSS-in-JS / Tailwind / CSS Modules?

**推荐**: CSS 变量（`:root` 级）+ 纯 CSS 文件

**理由**:
- 色彩系统的核心需求是"运行时色温切换" + "WCAG AA 验证"
- CSS 变量天然支持运行时替换，色温偏移只需修改 `--color-warmth-shift`
- 不引入 Tailwind 等工具链可以保持零运行时依赖
- 与 React 组件通过 `className` / `style={{}}` 引用 CSS 变量的模式兼容

### ADR-5: 数据获取模式

**问题**: React Query / SWR / 手动 fetch?

**推荐**: 手动 axios + 自定义 hooks（useWebSocket / useCoachState / useAdaptivePulse）

**理由**:
- 数据获取场景简单（聊天 POST、WebSocket 流、定期轮询仪表盘）
- React Query 的缓存/重试/乐观更新在此场景下大部分用不上
- 自定义 hooks 的实现清晰可见，易于调试

---

## 3. 子阶段分解（细化版）

### S9.1 — API 服务层 (3天 → ~1200 行 Python + ~50 测试)

**现有 api/ 目录**: 已存在 Phase 10 扩展后的 12 个文件（含 LLM 路由）。
**策略**: 不做 api/ 大重构，在现有基础上加 PulseService、dashboard_aggregator、增强 IAM。

| 子任务 | 关键文件 | 风险 |
|--------|---------|------|
| 9.1.1 PulseService | api/services/pulse_service.py | 时间窗口的并发边界条件 |
| 9.1.2 仪表盘聚合 | api/services/dashboard_aggregator.py | CoachBridge 的 TTM/SDT 读取 |
| 9.1.3 IAM 骨架 | api/middleware/auth.py | token 存储纯内存，无持久化 |
| 9.1.4 增强路由 | routers/dashboard.py, admin.py | 数据格式与前端期望的匹配 |
| 9.1.5 API 测试 | tests/test_api_*.py | 限流测试的 timing 敏感性 |

**关键测试场景**:
- PulseService 3 次脉冲 → 前 2 次 hard，第 3 次 soft
- 10 分钟窗口重置后恢复 hard
- IAM 匿名 token 签发 + 验证 + 过期
- dashboard 聚合数据与 CoachBridge 输出的一致性

### S9.2 — Web 前端核心框架 (4天 → ~45 源文件 + ~30 测试)

**关键组件分解**:

| 组件 | 状态 | 复杂度 | 数据源 |
|------|------|--------|--------|
| ChatBubble + ChatInput | 纯展示 | 低 | useCoachState.messages |
| PulsePanel | 交互核心 | 高 | useAdaptivePulse → blocking_mode |
| ExcursionOverlay | 视觉核心 | 中 | useCoachState.excursion |
| TTMStageCard | 数据可视化 | 中 | GET /dashboard/user → ttm_radar |
| SDTEnergyRings | 数据可视化+动画 | 高 | GET /dashboard/user → sdt_rings |
| GateShieldBadge | 状态聚合 | 低 | GET /admin/gates/status → overall |

**TTM 状态驱动 UI 的关键路径**:

```
useCoachState.ttmStage 
  → stateMachine.ts TTM_UI_MAP[ttmStage] 
  → 切换 theme CSS 变量
  → 切换 inputMode (suggest_only / reflect_first / scaffold / checkin / explore / recover)
  → 切换 pulseMode (disabled / gentle / commitment / high_frequency / milestone / none)
```

### S9.3 — 治理仪表盘 (2天 → ~15 源文件 + ~20 测试)

**管理员视图的布局**:

```
┌─────────────────────────────────────────────────┐
│ [全局概览] [实时监控] [阻断违规] [风险评估]  │
├─────────────────────────────────────────────────┤
│ 左上: GatePipeline (8 门禁流水线)                │
│   ├ Gate 1: Agency    ─ ● PASS                  │
│   ├ Gate 2: Excursion ─ ⚠ WARN                  │
│   └ ... (每个可下钻展开)                          │
│ 右上: RiskDashboard                             │
│   ├ HIGH: 2                                     │
│   ├ MEDIUM: 1                                   │
│   └ LOW: 0                                      │
│ 下方: AuditLogViewer (分页表格)                  │
└─────────────────────────────────────────────────┘
```

**用户 vs 管理员的数据流隔离**:

```
管理员请求 → GET /admin/gates/status → 返回完整 8 门禁数据
用户请求   → GET /dashboard/user → 返回 TTM + SDT + progress（无门禁数据）

后端保证: admin 路由检查 token 是否为管理员，否则 403
前端保证: 非管理员看不到 GatePipeline 导航项
```

### S9.4 — 无障碍与降级联调 (1天 → ~3 源文件 + ~10 测试)

**WCAG AA 验证计划**:

| 前景 | 背景 | 预期对比度 | 场景 |
|------|------|-----------|------|
| #6E5B4E (深摩卡) | #F5F1EA (暖白) | ≥ 4.5:1 | 正文文本 |
| #AFC7E2 (柔和蓝) | #F5F1EA (暖白) | ≥ 3:1 | CTA 按钮 (大文本) |
| #9CB59B (鼠尾草绿) | #F5F1EA (暖白) | ≥ 3:1 | 成功状态 (大组件) |
| #FEDDD8 (珊瑚糖) | #F5F1EA (暖白) | ≥ 3:1 | 警告背景 |

**色温适配时序**:

```
20:00-06:00 → 夜间模式 → CSS 变量暖色偏移 +5%
06:00-20:00 → 日间模式 → 基准色温
```

**自适应降级全链路**:

```
后端 PulseService.should_block() 
  → 决定 blocking_mode 
  → 通过 WebSocket 推送 pulse_event (含 blocking_mode)
  → 前端 useAdaptivePulse 消费 blocking_mode
  → 决定 PulsePanel 渲染为阻断式 (hard) 或旁路提示 (soft)
```

---

## 4. 数据流全面图

### 4.1 正常对话流

```
用户输入 → POST /api/v1/chat
  → CoachBridge.chat(message, session_id)
    → CoachAgent.act(message, context)
      → Composer.action_type (规则引擎)
      → LLM 内容生成 (Phase 10, 若启用)
      → DSL Builder → 5-field packet
      → S2 安全过滤 (Phase 10)
      → S3 脉冲注入 (如果需要)
      → Gate 门禁裁决
      → TTM/SDT/Flow 更新
      → Memory 存储
    → 返回 result dict (含 LLM 元数据)
  → CoachBridge 封装 → 返回 HTTP JSON
  → 前端 ChatBubble 渲染
```

### 4.2 脉冲确认流

```
服务端检测到 HIGH 强度动作
  → PulseService.should_block(session_id)
    → 计数 < 2 → hard 模式
    → WebSocket 推送 pulse_event { pulse_id, blocking_mode: 'hard' }
    → 前端 PulsePanel 渲染 Slide-to-Confirm 毛玻璃面板
    → 用户选择 "接受" 或 "改写"
    → POST /api/v1/pulse/respond { pulse_id, decision }
    → 服务端记录决策，继续对话流
```

### 4.3 流式 LLM 推送流 (Phase 10 S3)

```
WebSocket 连接已建立
  → 用户发送 user_message
  → 服务端调用 CoachBridge.chat_stream()
    → LLMClient.generate_stream() 
    → 每收到 chunk → WebSocket 推送 coach_chunk
    → LLM 生成完成 → S2 安全校验
    → 校验通过 → WebSocket 推送 coach_stream_end (含完整 payload)
    → 校验失败 → WebSocket 推送 safety_override
```

---

## 5. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 现有 api/ 代码与 S9.1 产生冲突 | 中 | 高 | S9.1 明确只新增不修改已有 api/ 文件 |
| 前端 npm 依赖版本冲突 | 高 | 中 | Vite 模板项目初始化解耦，最小化依赖 |
| TTM 阶段 unknown 的 UI 空白态 | 中 | 中 | 默认映射到 precontemplation 主题 |
| WebSocket 与 HTTP 的 token 同步 | 低 | 中 | WS 握手时通过 query param 传递 token |
| PulseService 内存数据重启丢失 | 高 | 低 | 单用户场景，重启后脉冲计数重置可接受 |
| 设计文档色彩矩阵 Hex 码偏离 | 低 | 中 | theme.ts 写死后锁定为常量，不做动态调色 |

---

## 6. 第二阶段（移动端 Flutter）的前置条件

Phase 9 第二阶段 (Flutter 移动端) 有以下硬性前提：

1. `contracts/api_contract.json` 已冻结 → API 接口不再变更
2. WebSocket 消息协议已稳定 → 5 种消息类型的 schema 不再修改
3. 色彩系统的 CSS 变量已稳定 → Flutter ThemeData 的映射关系已确定
4. 第一阶段的前端组件通过验收 → React 组件可作为 Flutter Widget 的设计参考

**第二阶段的独立性**: 一旦 api_contract.json 冻结，移动端开发可以不依赖第一阶段的 React 代码——只需要 API 合约和 WebSocket 协议定义。

---

## 7. 测试策略

### 7.1 测试金字塔（新增 ~110 测试）

```
       /\
      /  \         10 降级集成测试 (test_api_pulse_degradation.py)
     /    \
    / API  \       50 API 集成测试 (test_api_*.py)
   /────────\
  / Frontend \     30 组件测试 (vitest + @testing-library/react)
 /────────────\
/  WCAG AA    \   10 对比度自动验证 (contrastCheck.test.ts)
/──────────────\
    + 10 工具函数测试
```

### 7.2 关键测试场景

**API 层**:
- 每个路由的正常路径和错误路径
- 限流阈值击中/恢复/窗口重置
- WebSocket 推流 + 超时断开
- PulseService 的计数和窗口重置
- IAM token 签发和验证

**前端组件**:
- PulsePanel 的正常/软降级/无脉冲三种状态渲染
- TTMStageCard 的 6 种 TTM 阶段渲染
- ExcursionOverlay 的开启/关闭切换
- GateShieldBadge 的三色渲染
- useAdaptivePulse 的计数逻辑

**无障碍**:
- 所有 11 种颜色的对比度计算
- 每个 (前景, 背景) 组合的 WCAG AA 判定
- 夜间/日间色温偏移的正确性

---

## 8. 实施顺序与依赖

```
S9.1 API 服务层
  │
  ├── S9.2.1 前端脚手架 + 色彩系统 (可并行)
  │
  ├── S9.2.2 聊天组件 (依赖 S9.1 的 chat/ws 路由)
  │
  ├── S9.2.3 仪表盘组件 (依赖 S9.1 的 dashboard/user 路由)
  │
  ├── S9.3 治理仪表盘 (依赖 S9.1 的 admin/gates 路由 + S9.2 脚手架)
  │
  └── S9.4 无障碍 + 降级 (依赖 S9.1-S9.3 全部完成)
```

实际上 S9.2.1（脚手架+色彩系统）可以与 S9.1 并行，其余子阶段严格串行。

---

## 9. 总结

Phase 9 的核心挑战不是"写前端代码"，而是在三个相互矛盾的需求之间找到平衡：

1. **治理透明度** vs **认知过载** → 三层信息模型（盾牌/雷达/流水线）
2. **主权保护强度** vs **交互流畅性** → 自适应脉冲降级（hard→soft→none）
3. **多租户准备** vs **当前简单性** → 匿名 token + 状态树，不露登录界面

这三个平衡决策奠定了 Phase 9 的全部架构走向。
