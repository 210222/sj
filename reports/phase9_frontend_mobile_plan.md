# Phase 9 — 前端与移动端界面落地方案（产品化阶段）

**编制日期**: 2026-05-04
**设计对齐源**: `前端和移动端页面设计.txt`（行为科学驱动的AI教练系统前端与移动端界面设计及项目审查深度报告）
**当前基线**: 1070 tests pass, Phase 0-8 全部 GO, 11 份冻结合约
**前置**: Phase 8（最终门禁闭环与系统签收）已完成
**工具链**: 前端 = React + TypeScript / 移动端 = Flutter（第二阶段），API 层 = FastAPI（Python）

---

## 0. 为什么需要 Phase 9

Phase 0-8 完成了 Coherence 系统的全部后端能力——CCA-T 教练引擎、行为科学模型（TTM/SDT/心流）、语义安全三件套、MAPE-K 闭环、因果稳健层、8 道门禁升档体系。但这些都停留在**Python 后端**，面向的是 API/CLI 接口。

Phase 9 的任务：将这个纯后端智能引擎转化为**面向终端用户的交互式服务产品**，通过：
1. RESTful API 层：桥接前端 ↔ 已冻结的后端引擎
2. Web 前端：行为科学驱动的 UI 组件体系
3. 移动端（第二阶段）：Flutter 跨平台沉浸式辅导
4. 治理仪表盘：8 道门禁的 RBAC 分级透明度

### 核心设计原则（来自设计文档）

| 原则 | 内容 |
|------|------|
| TTM 状态驱动 UI | 用户处于不同改变阶段 → 渲染不同 UI 组件库 |
| SDT 三需求映射 | 自主性/胜任感/关联性 → 组件级交互设计 |
| 自适应降级 | 脉搏确认防疲劳：频率阈值 → 旁路软提示 |
| RBAC 信息隔离 | 8 Gates 不对 C 端裸暴露，抽象为"健康盾牌" |
| 多租户准备 | 状态树挂载 token 下，第一天就建 IAM 骨架 |

---

## 1. 最终系统架构（完成后）

```
用户 (Web / Mobile)
    │  HTTPS / WebSocket
    ▼
┌──────────────────────────────────────────────────────────────┐
│                    API 层 (FastAPI)                            │
│  ├── /api/v1/session          — 会话管理 + 用户状态               │
│  ├── /api/v1/chat             — 对话 + CoachAgent 转发           │
│  ├── /api/v1/pulse            — 主权确认脉冲通道                   │
│  ├── /api/v1/excursion        — 远足权触发                        │
│  ├── /api/v1/dashboard        — 仪表盘聚合数据                     │
│  ├── /api/v1/admin/gates      — 8 门禁监控（管理员 RBAC）          │
│  ├── /api/v1/admin/audit      — 审计日志查询                       │
│  └── ws://.../chat            — WebSocket 实时推流                 │
└──────────────┬───────────────────────────────────────────────┘
               │ 内部调用
               ▼
┌──────────────────────────────────────────────────────────────┐
│               已冻结的 Python 后端 (src/)                        │
│  ├── CoachAgent.act()           — 教练引擎（src/coach/）         │
│  ├── 治理管线 (src/middle+outer/) — L0/L1/L2/Decision/Safety    │
│  ├── 8 道门禁 (src/inner/gates/) — GO/NO-GO 裁决                │
│  └── Ledger + Audit              — 事件账本 + 审计分级           │
└──────────────────────────────────────────────────────────────┘

        ┌───────────────────┐         ┌───────────────────┐
        │   Web 前端 (React) │         │  移动端 (Flutter)  │
        │   S9.1 → S9.3     │         │  第二阶段         │
        └───────────────────┘         └───────────────────┘
```

---

## 2. 目录结构（完成后）

```
coherence/
├── api/                          # ★ 新增：API 服务层
│   ├── __init__.py
│   ├── main.py                   # FastAPI 应用入口
│   ├── config.py                 # API 配置（CORS、认证、限流）
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── session.py            # 会话管理路由
│   │   ├── chat.py               # 对话路由（HTTP + WebSocket）
│   │   ├── pulse.py              # 主权脉冲路由
│   │   ├── excursion.py          # 远足权路由
│   │   ├── dashboard.py          # 仪表盘数据路由
│   │   └── admin.py              # 管理后台路由（RBAC）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py            # Pydantic 请求/响应模型
│   │   └── websocket.py          # WebSocket 消息模型
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py               # IAM 骨架（JWT token）
│   │   └── rate_limit.py         # 自适应降级限流
│   ├── services/
│   │   ├── __init__.py
│   │   ├── coach_bridge.py       # CoachAgent 封装适配
│   │   ├── pulse_service.py      # 脉冲频率控制（自适应降级）
│   │   └── dashboard_aggregator.py # 仪表盘数据聚合
│   └── tests/                    # API 层测试
│       ├── __init__.py
│       ├── test_session.py
│       ├── test_chat.py
│       ├── test_pulse.py
│       └── test_dashboard.py
│
├── frontend/                     # ★ 新增：Web 前端（React + TypeScript）
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/
│   │   └── assets/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                # 根组件 + 路由
│   │   ├── api/                   # API 客户端
│   │   │   ├── client.ts         # axios + WebSocket 封装
│   │   │   ├── session.ts        # 会话 API
│   │   │   ├── chat.ts           # 对话 API
│   │   │   └── dashboard.ts      # 仪表盘 API
│   │   ├── components/
│   │   │   ├── chat/              # 对话组件
│   │   │   │   ├── ChatBubble.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── PulsePanel.tsx        # 主权确认面板
│   │   │   │   └── ExcursionOverlay.tsx  # 远足模式覆盖层
│   │   │   ├── dashboard/                # 仪表盘组件
│   │   │   │   ├── TTMStageCard.tsx      # TTM 阶段展示
│   │   │   │   ├── SDTEnergyRings.tsx    # SDT 三环能量图
│   │   │   │   ├── ProgressTimeline.tsx  # 进度时间线
│   │   │   │   └── GateShieldBadge.tsx   # 门禁健康盾牌
│   │   │   ├── admin/                    # 管理后台组件
│   │   │   │   ├── GatePipeline.tsx      # 8 门禁流水线可视化
│   │   │   │   ├── AuditLogViewer.tsx    # 审计日志
│   │   │   │   └── RiskDashboard.tsx     # 风险评估
│   │   │   └── shared/                   # 共享组件
│   │   │       ├── ColorTheme.tsx        # 色彩系统
│   │   │       ├── SlideToConfirm.tsx    # 滑动确认组件
│   │   │       └── HealthShield.tsx      # 系统健康状态徽章
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useCoachState.ts
│   │   │   └── useAdaptivePulse.ts
│   │   ├── styles/
│   │   │   ├── theme.ts           # 设计文档配色矩阵
│   │   │   ├── global.css
│   │   │   └── animations.css     # 心流/状态转场动画
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   └── coach.ts
│   │   └── utils/
│   │       ├── stateMachine.ts    # TTM 阶段 → UI 组件映射
│   │       └── colorAdapt.ts     # 环境光同步适配
│   └── tests/                     # 前端测试
│       ├── setup.ts
│       └── components/
│
├── mobile/                       # ★ 第二阶段：Flutter 移动端
│   └── (占位)
│
├── contracts/
│   ├── api_contract.json         # ★ 新增：API 接口合约（S9.2 冻结）
│   └── ... (11 份已有冻结合约)
│
├── config/
│   ├── api_defaults.yaml         # ★ 新增：API 层配置
│   └── ... (已有配置)
│
└── tests/
    ├── test_api_*.py             # ★ Phase 9 API 集成测试
    └── ... (已有 1070 个测试)
```

---

## 3. 子阶段分解（严格串行，上一阶段非 GO 不得进入下一阶段）

### S9.1 — API 服务层（Backend-for-Frontend）

**目标**: 在已有冻结后端上建一层 RESTful + WebSocket API，不修改 src/ 一行代码
**预估行数**: ~1200 行 Python（api/ 包）
**新增测试**: 40-50 API 集成测试
**风险**: 低（API 层是胶水代码，核心逻辑不变）

#### 3.1.1 路由设计

| 端点 | 方法 | 功能 | 速率限制 |
|------|------|------|---------|
| `POST /api/v1/session` | POST | 创建/恢复会话（无认证单用户 → 预留 token 字段） | 10/min |
| `POST /api/v1/chat` | POST | 发送消息 → CoachAgent.act() → 返回 DSL 响应 | 30/min |
| `WS /api/v1/chat/ws` | WebSocket | 实时对话推流（含脉冲事件推送） | — |
| `POST /api/v1/pulse/respond` | POST | 用户对脉冲的接受/改写决策 | 30/min |
| `POST /api/v1/excursion/enter` | POST | 进入远足模式 | 5/min |
| `POST /api/v1/excursion/exit` | POST | 退出远足模式 | 5/min |
| `GET /api/v1/dashboard/user` | GET | 用户仪表盘数据（TTM/SDT 聚合） | 10/min |
| `GET /api/v1/admin/gates/status` | GET | 8 门禁状态快照（管理员 RBAC） | 30/min |
| `GET /api/v1/admin/audit/logs` | GET | 审计日志查询（管理员 RBAC） | 20/min |
| `GET /api/v1/health` | GET | 健康检查 | 60/min |

#### 3.1.2 关键组件

**coach_bridge.py** — CoachAgent 适配器：
```python
class CoachBridge:
    """将已冻结的 CoachAgent 封装为 API 可消费的服务。
    不做任何业务逻辑修改，仅做参数映射 + 结果序列化。"""
    
    def __init__(self):
        # 导入已冻结的 CoachAgent
        from src.coach.agent import CoachAgent
        self.agent = CoachAgent()
    
    async def chat(self, message: str, session_id: str) -> ChatResponse:
        # 1. 反序列化 session 状态
        # 2. 调用 agent.act() 
        # 3. 序列化返回（DSL packet → JSON）
        pass
```

**pulse_service.py** — 自适应降级实现（对应设计文档 5.1 隐患修复）：
```python
class PulseService:
    """主权脉冲自适应降级。
    
    设计文档要求：单会话 10 分钟内最多 2 次阻断式高强度确认。
    超阈值后降级为旁路软提示（珊瑚糖色高亮标记，不阻断流程）。
    """
    MAX_BLOCKING_PULSES: int = 2
    WINDOW_MINUTES: int = 10
    
    def should_block(self, session_id: str) -> bool:
        """检查是否应该阻断（TRUE=强制确认/FALSE=旁路软提示）"""
    
    def record_pulse(self, session_id: str, intensity: str):
        """记录脉冲事件"""
```

**auth.py** — IAM 骨架（对应设计文档 5.3 隐患修复）：
```python
class IAMSkeleton:
    """第一阶段：无认证模式（兼容单用户），但状态树挂载在 token 下。
    
    设计文档要求：哪怕 UI 上未露出登录注册界面，
    前端状态树必须是挂载在动态获取的身份令牌与 session_id 之下的树形结构。
    """
    def issue_anonymous_token(self) -> str:
        """签发匿名 token（后续可升级为 Keycloak JWT）"""
    
    def validate_token(self, token: str) -> bool:
        """验证 token 合法性"""
```

#### 3.1.3 测试要求

```
tests/test_api_session.py        — 会话 CRUD + token 隔离
tests/test_api_chat.py           — 对话转发 + WebSocket 推流
tests/test_api_pulse.py          — 自适应降级边界测试
tests/test_api_dashboard.py      — 仪表盘数据聚合
tests/test_api_rate_limit.py     — 速率限制击中/恢复
```

**全量回归**: `python -m pytest tests/ -q` → 1070 + API 测试 = 全部 pass

---

### S9.2 — Web 前端核心框架

**目标**: React + TypeScript 前端，含聊天界面、脉冲组件、色彩系统
**预估文件**: ~40 个源文件
**新增测试**: 20-30 前端组件测试
**风险**: 中（前端工具链需搭建，TypeScript 类型覆盖）
**工具链**: Vite + React 18 + TypeScript + React Router + TailwindCSS

#### 3.2.1 色彩系统实现

严格按照设计文档第 4 节的配色矩阵：

```typescript
// frontend/src/styles/theme.ts
export const coachColors = {
  // 主背景
  warmWhite: '#F5F1EA',       // #F5F1EA (245,241,234)
  // 主品牌色
  softBlue: '#AFC7E2',        // #AFC7E2 (175,199,226)
  // 探索模式/成功
  sageGreen: '#9CB59B',       // #9CB59B (156,181,155)
  // 次级界面
  lavenderGray: '#C6C1D2',    // #C6C1D2 (198,193,210)
  // 主文本
  deepMocha: '#6E5B4E',       // #6E5B4E (110,91,78)
  // 高亮警示（替代纯红）
  coralCandy: '#FEDDD8',      // #FEDDD8 (254,221,216)
  // 檀香薄雾（冥想场景）
  sandalwoodMist: '#D8CBB8',  // #D8CBB8
  creamPaper: '#F4EFE7',      // #F4EFE7
  warmSand: '#B39A7C',        // #B39A7C
  clayBrown: '#8A7C70',       // #8A7C70
  charcoal: '#2F2C2A',        // #2F2C2A
} as const;
```

#### 3.2.2 核心组件清单

| 组件 | 文件 | 功能 | 对应设计文档章节 |
|------|------|------|----------------|
| ChatBubble | `chat/ChatBubble.tsx` | AI/用户对话气泡，支持 DSL 动作类型渲染 | 2.2 |
| ChatInput | `chat/ChatInput.tsx` | 输入框 + /excursion 命令识别 | 2.1 |
| PulsePanel | `chat/PulsePanel.tsx` | 主权确认非阻断面板（Slide-to-Confirm） | 2.2 |
| ExcursionOverlay | `chat/ExcursionOverlay.tsx` | 远足模式视觉隔离（深色域切换） | 2.3 |
| TTMStageCard | `dashboard/TTMStageCard.tsx` | TTM 阶段雷达展示 | 1.1 / 3.2 |
| SDTEnergyRings | `dashboard/SDTEnergyRings.tsx` | 三环能量图 | 3.2 |
| GateShieldBadge | `dashboard/GateShieldBadge.tsx` | 用户侧门禁健康盾牌 | 3.3 |
| HealthShield | `shared/HealthShield.tsx` | 系统健康度徽章 | 3.3 |
| SlideToConfirm | `shared/SlideToConfirm.tsx` | 滑动确认组件（防误触） | 2.2 |

#### 3.2.3 TTM 状态驱动 UI 映射

```typescript
// frontend/src/utils/stateMachine.ts
const TTM_UI_MAP = {
  precontemplation: {
    theme: 'minimal',
    component: 'PassiveDashboard',     // 极简数据看板
    pulse: 'disabled',                  // 低频微轻推
    input: 'suggest_only',              // 仅系统建议
  },
  contemplation: {
    theme: 'balanced',
    component: 'DecisionBalanceCard',   // 对比决策卡
    pulse: 'gentle',                    // 情感化故事
    input: 'reflect_first',             // 触发反思
  },
  preparation: {
    theme: 'active',
    component: 'GoalStepper',           // 目标拆解向导
    pulse: 'commitment',                // 一键承诺
    input: 'scaffold',                  // 脚手架
  },
  action: {
    theme: 'energetic',
    component: 'ProgressRing',          // 进度环
    pulse: 'high_frequency',           // 即时反馈
    input: 'checkin',                   // 签到
  },
  maintenance: {
    theme: 'calm',
    component: 'StreakHeatmap',         // 连续打卡热力图
    pulse: 'milestone',                 // 里程碑解锁
    input: 'explore',                   // 高阶探索
  },
} as const;
```

#### 3.2.4 自适应降级前端实现

```typescript
// frontend/src/hooks/useAdaptivePulse.ts
function useAdaptivePulse(sessionId: string) {
  // 从 sessionStorage 读取本会话脉冲计数
  const [blockingCount, setBlockingCount] = useState(0);
  const SOFT_LIMIT = 2;       // 10 分钟内最多 2 次阻断
  const WINDOW_MS = 10 * 60 * 1000;
  
  function shouldShowBlocking(intensity: string): boolean {
    if (intensity !== 'HIGH') return false;
    if (blockingCount >= SOFT_LIMIT) return false; // 降级为旁路
    return true;
  }
  
  return {
    shouldShowBlocking,
    recordPulse: () => setBlockingCount(c => c + 1),
    isDegraded: blockingCount >= SOFT_LIMIT,
  };
}
```

---

### S9.3 — 治理仪表盘 + 管理后台

**目标**: 角色分离的管理后台（管理员）+ 简化的用户端健康看板
**预估文件**: ~15 个源文件
**新增测试**: 15-20 个组件测试
**风险**: 低（纯展示层，不涉及后端逻辑变更）

#### 3.3.1 RBAC 视图分级

| 角色 | 可见内容 | 实现方式 |
|------|---------|---------|
| 终端用户 | 系统健康盾牌徽章 + TTM 阶段雷达 + SDT 能量环 | `GateShieldBadge` 聚合（不含细节） |
| 管理员 | 8 门禁实时流水线 + 审计日志 + 风险评估面板 | `GatePipeline` 全展开 |
| 开发调试 | 底层 Ledger 原始事件 + Gate 裁决详情 | 调试模式开关 |

#### 3.3.2 GatePipeline 组件

```
┌─────────────────────────────────────────────────────┐
│  8 门禁实时状态 ──── 2026-05-04 14:32 UTC            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1 [Agency]  ● PASS  rewrite_rate=0.32              │
│  2 [Excursion] ● PASS  excursions=3 (48h)            │
│  3 [Learning] ● PASS  no_assist_trend=+5%            │
│  4 [Relational] ● PASS  compliance=0.21              │
│  5 [Causal]  ● PASS  三诊断全部通过                   │
│  6 [Audit]   ⚠ WARN  P1=2 (阈值=3), P0=0 ✅          │
│  7 [Framing] ● PASS  chi2_p=0.34 > 0.05              │
│  8 [Window]  ● PASS  version_drift=0.1, age=12min    │
│                                                      │
│  整体: ⚠ WARN (Audit Gate 接近阈值)                   │
│  升档: BLOCKED (门禁 6 未达到 PASS)  → 展开 ▼         │
└─────────────────────────────────────────────────────┘
```

每个 Gate 行支持点击下钻展开，显示：
- 该 Gate 的完整评估历史（折线图）
- 最近一次的裁决依据（哪些数据字段触发了什么规则）
- 如果是 block，显示违规的具体事件内容

#### 3.3.3 用户端仪表盘

只展示三层抽象：
1. **系统健康盾牌** — 绿色/黄色/红色，对应 8 门禁的摘要
2. **TTM 阶段雷达** — 五维倾向性评分（不暴露"门禁"概念）
3. **SDT 能量三环** — 自主性/胜任感/关联性的动态填充环

禁用技术性术语：不应出现"gate"、"pipeline"、"audit"、"P0/P1"等底层概念。

---

### S9.4 — 自适应降级 + 色彩无障碍 (Accessibility)

**目标**: 实现设计文档 5.1 和 4.2 的隐患修复和 WCAG AA 合规
**预估文件**: 修改已有前端组件 + 新增辅助工具
**新增测试**: 10 个自动化（WCAG 对比度检测 + 降级边界测试）
**风险**: 低（不涉及新功能，纯质量加固）

#### 3.4.1 WCAG AA 级对比度验证

对所有色彩组合执行自动化对比度检查：

```typescript
// utils/contrastCheck.ts
function getContrastRatio(hex1: string, hex2: string): number {
  // WCAG 2.1 relative luminance calculation
}

// 验证要求：
// 正常文本 (>= 4.5:1)
// 大文本 / 组件 (>= 3:1)
// 用户界面组件 (>= 3:1)
```

#### 3.4.2 环境光感知适配

```typescript
// utils/colorAdapt.ts
// 根据时间自动调整色温偏移
function getTimeBasedAdjustment(): ColorShift {
  const hour = new Date().getHours();
  // 夜间 (20:00-06:00): 暖色偏移 +5% 红色通道
  // 日间 (06:00-20:00): 保持基准色温
}
```

#### 3.4.3 自适应降级全链路集成

```
API 层 (PulseService)                   前端层 (useAdaptivePulse)
    │                                          │
    │  返回 blocking_mode: "soft" 或 "hard"      │
    │─────────── WebSocket ──────────────────→  │
    │                                          │
    │                                          ▼
    │                                blocking_mode 驱动渲染分支:
    │                                  "hard" → PulsePanel (阻断式)
    │                                  "soft" → Coral 高亮标记（不阻断）
    │                                  "none" → 正常对话流程
```

---

### 第二阶段：移动端（后续规划）

设计文档提议的 Flutter 移动端架构（底部导航栏、离线优先、50+ 核心界面）作为一个独立的第二阶段处理。Phase 9 完成后，移动端可以共享已有的 API 层和 WebSocket 协议，只需构建 Flutter 客户端即可。

**第二阶段前置条件**：
- Phase 9 全部 GO
- API 合约已冻结
- WebSocket 协议稳定

---

## 4. 合约冻结时间表

| 合约 | 冻结阶段 | 说明 |
|------|---------|------|
| 全部 11 份已有合约 | ✅ 已冻结 | Phase 0-8 完成，任何修改都需要版本升级 |
| `api_contract.json` | S9.2 结束时 | 新建：API 路由签名 + 请求/响应 schema + 错误码枚举 |

### api_contract.json 草案核心字段

```json
{
  "contract": "api_contract",
  "version": "1.0.0",
  "status": "frozen",
  "base_url": "/api/v1",
  "endpoints": [
    {
      "path": "/session",
      "method": "POST",
      "request": {"session_id": "string | null", "token": "string | null"},
      "response": {"session_id": "string", "token": "string", "user_state": "object"}
    },
    {
      "path": "/chat",
      "method": "POST",
      "request": {"session_id": "string", "message": "string"},
      "response": {"action_type": "string", "payload": "object", "pulse": "object | null"}
    },
    {
      "path": "/chat/ws",
      "method": "WEBSOCKET",
      "message_types": ["user_message", "coach_response", "pulse_event", "pulse_decision"]
    }
  ],
  "error_codes": {
    "SESSION_NOT_FOUND": {"http": 404, "retryable": false},
    "RATE_LIMITED": {"http": 429, "retryable": true, "retry_after_s": 60},
    "PULSE_DEGRADED": {"http": 200, "severity": "soft", "body": {"blocking_mode": "soft"}}
  },
  "rate_limits": {
    "default": {"requests": 30, "window_s": 60},
    "pulse": {"requests": 10, "window_s": 600},
    "admin": {"requests": 60, "window_s": 60}
  }
}
```

---

## 5. 测试策略

| 层级 | 覆盖 | 工具 | 阶段 | 要求 |
|------|------|------|------|------|
| API 单元测试 | 每个路由 + service | pytest + httpx | S9.1 | 强制 |
| API 集成测试 | 端到端调用 CoachAgent | pytest + FastAPI TestClient | S9.1 | 强制 |
| 前端组件测试 | 每个 React 组件渲染快照 | vitest + @testing-library/react | S9.2 | 强制 |
| 前端集成测试 | 核心对话流 TTM 状态驱动 | vitest + playwright | S9.2 | 推荐 |
| WCAG 无障碍测试 | 对比度检测 + ARIA 标签 | axe-core + vitest | S9.4 | 强制 |
| 全量回归测试 | 1070 + API tests + 前端 tests | pytest -q + vitest run | 每阶段 | 强制 |

---

## 6. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| API 层引入 CoachAgent 实例管理复杂 | 中 | 中 | 无状态路由，每个请求创建独立 agent 实例 |
| 前端 TypeScript 类型未对齐后端 DSL schema | 中 | 高 | `api_contract.json` 是单一真相源，前端类型自动生成 |
| 自适应降级逻辑与后端脉冲计算不一致 | 中 | 中 | `PulseService` 是唯一决策源，前端仅消费 `blocking_mode` 字段 |
| 色彩 WCAG AA 不达标需要调色 | 低 | 低 | 设计文档配色已预留调整空间，S9.4 专门处理 |
| 前端与已冻结后端之间出现行为漂移 | 低 | 高 | 所有 API 测试写为双端验证：API 响应 vs 直接调用 CoachAgent |

---

## 7. 回滚策略

| 触发条件 | 动作 | 影响范围 |
|---------|------|---------|
| API 层测试未通过 | 回退 `api/` 包 | 仅 S9.1 |
| 前端构建失败 | 回退 `frontend/` 目录 | 仅 S9.2 |
| 回归测试 < 1070 | 回退 API 层对 `src/` 的任何变动（不应有） | 全 Phase 9 |
| 自适应降级导致脉冲确认完全失效 | 移除降级逻辑，恢复全阻断模式 | 仅 S9.4 |
| 任何 P0 | 删除 `api/` + `frontend/`，还原至 Phase 8 基线 | 全 Phase 9 |

---

## 8. 关键技术决策

### 8.1 为什么先做 Web 前端而非移动端

| 维度 | Web (React) | 移动端 (Flutter) |
|------|------------|-----------------|
| 工具链 | Node.js + Vite，现有环境可用 | 需安装 Flutter SDK + Dart |
| 共享 API 层 | 相同 | 相同 |
| 开发速度 | 1-2 周可交付核心交互 | 4-6 周 |
| 验证成本 | 浏览器即运行 | 需模拟器或真机 |
| 设计文档建议 | — | 推荐 Flutter |

**决策**: S9.1→S9.4 先做 Web 前端 + API 层。API 层合约冻结后，移动端可以独立并行开发。

### 8.2 为什么 FastAPI 而非其他

- 与现有 Python 3.10+ 技术栈完全一致
- 原生 async/await 支持 WebSocket 直推
- Pydantic v2 自动生成 OpenAPI spec → 前端类型生成
- 零外部运行时依赖（仅需 uvicorn）

### 8.3 组件默认 OFF 策略在 Phase 9 的延续

前端新建组件统一默认关闭/隐藏：
- **自适应脉冲降级**：所有降级逻辑默认开启（此为安全机制不属行为干预）
- **TTM 状态驱动 UI**：SDT 能量环、远足模式覆盖层等默认关闭，用户按需启用
- **Gate 管理面板**：默认关闭，管理员手动激活

---

## 9. 启动建议

```
S9.1 (3天):  API 层搭建 → 路由 + WebSocket + 自适应降级 + IAM 骨架
             ↓ 冻结 api_contract.json
S9.2 (4天):  Web 前端核心 → 色彩系统 + 聊天界面 + 脉冲组件 + TTM 状态驱动
             ↓
S9.3 (2天):  治理仪表盘 → GatePipeline + RBAC 分级 + 用户端健康盾牌
             ↓
S9.4 (1天):  无障碍加固 → WCAG AA 扫描 + 色彩调校 + 自适应降级联调
             ↓
全量回归:    1070 + API tests + 前端 tests = 全部 pass
```

每个子阶段通过 `/run_phase9_{n}` 命令启动，读取对应的 `meta_prompts/` 元提示词。

---

## 10. 第一阶段总预估

| 指标 | 数值 |
|------|------|
| 新增源文件 | ~65 (api/ ~15, frontend/ ~45, contracts/ ~1, config/ ~1) |
| 新增测试 | ~80-100 |
| 冻结合约 | 1 份（api_contract.json） |
| 修改已有代码 | 零（不碰 src/inner/ / middle/ / outer/ / contracts/） |
| 总工期 | ~10 天（S9.1→S9.4 严格串行） |
| 移动端 | 第二阶段，待 Phase 9 全 GO 后启动 |
