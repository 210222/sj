# Phase 9 — API 层 + 前端交互界面

**编制日期**: 2026-05-04
**当前基线**: 1070 tests pass, Coach 轨 Phase 0-8 全部 GO
**目标**: 为 CoachAgent 引擎添加 HTTP API 层和前端交互界面

---

## 0. 为什么需要 Phase 9

当前系统是一个纯后端 Python 引擎——所有能力通过 `CoachAgent.act()` 方法调用。没有 HTTP 接口、没有前端、没有可视化。要成为可用产品，需要：

1. 将教练对话能力暴露为 REST API
2. 提供前端界面（Web/移动端）让用户与教练交互
3. 处理实时双向通信（脉冲确认、远足触发的用户响应）

Phase 9 不做的事：
- ❌ 多用户支持（单用户模式不变）
- ❌ 修改已有冻结代码（src/inner/middle/outer/coach 全部冻结）
- ❌ 引入新行为科学或治理能力

---

## 1. 系统架构（Phase 9 完成后）

```
                   ┌───────────────────────┐
                   │   Frontend (Web/App)   │
                   │  React / Flutter       │
                   │  - 对话界面            │
                   │  - 仪表盘              │
                   │  - 脉冲确认弹窗        │
                   │  - 远足入口            │
                   └────────┬──────────────┘
                            │ HTTP REST + WebSocket
                            ▼
┌─────────────────────────────────────────────────────┐
│                  API Layer (FastAPI)                  │
│  src/outer/api/main.py   ← 新增 FastAPI 应用          │
│  src/outer/api/routes.py ← 新增 API 路由              │
│  src/outer/api/models.py ← 新增 Pydantic 模型         │
│  src/outer/api/auth.py   ← 简单 token 认证            │
│  src/outer/api/ws.py     ← WebSocket 实时通道         │
│                                                       │
│  /api/v1/chat          POST → CoachAgent.act()        │
│  /api/v1/session       GET  → 会话状态                │
│  /api/v1/gates         GET  → 8 门禁状态              │
│  /api/v1/pulse         WS  → 脉冲确认双向             │
│  /api/v1/excursion     WS  → 远足交互                 │
└──────────────────────┬──────────────────────────────┘
                       │ 调用 CoachAgent.act()
                       ▼
┌─────────────────────────────────────────────────────┐
│              CoachAgent 引擎 (已冻结)                 │
│  act(user_input, context) → DSL packet               │
│  Phase 0-8 全部能力可用                              │
└─────────────────────────────────────────────────────┘
```

---

## 2. REST API 设计

### 2.1 基础端点

| 方法 | 路径 | 用途 | 请求 | 响应 |
|------|------|------|------|------|
| POST | `/api/v1/chat` | 发送用户消息 | `{message, session_id}` | `{reply, action_type, ...}` |
| GET | `/api/v1/session` | 会话状态 | — | `{session_id, turn_count, ...}` |
| GET | `/api/v1/status` | 系统健康 | — | `{status, tests, version}` |
| GET | `/api/v1/gates` | 8 门禁状态 | — | `{gates: [...], decision}` |
| GET | `/api/v1/metrics` | MRT/审计指标 | — | `{mrt, audit, ...}` |

### 2.2 实时端点

| 协议 | 路径 | 用途 |
|------|------|------|
| WebSocket | `/api/v1/ws` | 脉冲确认、远足交互、状态推送 |

### 2.3 `/api/v1/chat` 核心接口

```json
// Request
{
    "message": "我今天不想学编程了",
    "session_id": "default"
}

// Response
{
    "reply": {
        "text": "听起来今天动力不太够。想聊聊遇到了什么困难吗？",
        "action_type": "reflect",
        "intent": "frustration",
        "intensity": 0.4
    },
    "dsl_packet": { ... },
    "gate_decision": "GO",
    "pulse_needed": false,
    "ttm_stage": "contemplation",
    "sdt_profile": {
        "autonomy": 0.6,
        "competence": 0.4,
        "relatedness": 0.7
    },
    "session_id": "default",
    "turn_count": 12
}
```

### 2.4 认证

单用户模式，简单 token：
```
Authorization: Bearer <static-token>
```

token 配置在 `config/coach_defaults.yaml` 新增段。

---

## 3. 前端技术选型

### 选项 A：Web 优先 → 后续移动端（推荐）

| 层 | 技术 | 理由 |
|----|------|------|
| UI 框架 | React + TypeScript | 成熟生态，组件库丰富 |
| 状态管理 | Zustand | 轻量，适合单用户 |
| HTTP 客户端 | fetch / axios | 标准 |
| WebSocket |原生 WebSocket API | 标准浏览器 API |
| UI 组件库 | Ant Design / shadcn/ui | 快速搭建设计 |
| 打包 | Vite | 快速开发体验 |
| 移动端后续 | Flutter | 跨平台 iOS+Android |

**为什么 Web 优先**：
- 迭代速度快（改代码即刷新）
- 验证交互设计后再做移动端，减少返工
- 不需要额外构建工具链

### 选项 B：Flutter 一步到位

| 层 | 技术 |
|----|------|
| 框架 | Flutter |
| 平台 | iOS + Android + Web 同时 |
| 状态管理 | Riverpod / BLoC |
| HTTP | Dio |
| WebSocket | web_socket_channel |

**为什么可能需要 Flutter**：
- 用户明确要移动端
- 一次开发三平台
- 未来要对接健康数据（Apple Health / Google Fit）时更方便

**建议**：Web 验证交互 → 再 Flutter 封装，两阶段走。

---

## 4. 会话管理

当前 `CoachAgent.__init__(session_id="default")` 为单会话设计。

API 化后需要：

```python
# src/outer/api/session.py （新增）

class SessionManager:
    """单用户会话管理器。

    维持 CoachAgent 实例生命周期。
    session_id 预留为后续多用户扩展。
    """

    def __init__(self):
        self._agent: CoachAgent | None = None

    def get_agent(self) -> CoachAgent:
        if self._agent is None:
            self._agent = CoachAgent(session_id="default")
        return self._agent

    def reset(self):
        self._agent = None
```

---

## 5. 交互流程

### 5.1 普通对话

```
用户 → POST /api/v1/chat {message: "帮我学 Python"}
  → SessionManager.get_agent().act("帮我学 Python")
  → CoachAgent:
      解析意图 → composer → DSL 构建 → 管线安全校验
      → V18.8 脉冲检测 → V18.8 远足/双账本/关系安全
      → Phase 4/5/6/7/8 全部可选能力
  → 返回 DSL packet + 回复文本
  → API 格式化 → 前端渲染对话气泡
```

### 5.2 脉冲确认（双向交互）

```
用户发起 HIGH 强度动作
  → act() 返回 pulse_needed: true, pulse_statement: "..."
  → 前端弹窗显示两选项 [接受] [改写]
  → 用户选择 → POST /api/v1/chat {message: "我接受", pulse_response: "accept"}
  → act() 处理脉冲响应 → 继续或改写
```

### 5.3 远足交互

```
用户点击"探索其他选项"
  → POST /api/v1/chat {message: "/excursion", domain: "learning_path"}
  → act() 进入远足模式 → 返回非偏好选项
  → 前端展示多个选项卡片
  → 用户选择 → 结束远足
```

---

## 6. 目录结构变化

```
src/outer/api/
├── __init__.py
├── main.py          ← 新增: FastAPI 应用入口, uvicorn 启动
├── routes.py        ← 新增: 所有 API 路由
├── models.py        ← 新增: Pydantic 请求/响应模型
├── ws.py            ← 新增: WebSocket 处理器
├── session.py       ← 新增: 会话管理器
└── auth.py          ← 新增: 简单 token 认证

frontend/            ← 新增: Web 前端 (React)
├── package.json
├── vite.config.ts
├── src/
│   ├── App.tsx
│   ├── ChatView.tsx       — 对话界面
│   ├── Dashboard.tsx      — 仪表盘（TTM/SDT/门禁）
│   ├── PulseModal.tsx     — 脉冲确认弹窗
│   ├── ExcursionPanel.tsx — 远足面板
│   ├── api.ts             — API 客户端
│   └── ws.ts              — WebSocket 客户端

config/coach_defaults.yaml
  └── api: {}           ← 新增: API 配置段 (host/port/token)
```

---

## 7. 子阶段分解

### S9.1 — API 基础设施
新建 API 骨架：
- `src/outer/api/main.py` — FastAPI 应用 + CORS
- `src/outer/api/routes.py` — 路由注册
- `src/outer/api/models.py` — Pydantic request/response 模型
- `src/outer/api/session.py` — SessionManager
- `src/outer/api/auth.py` — token 认证
- 验证：`curl POST /api/v1/chat` 返回正确响应

### S9.2 — 核心 Chat 端点
实现 `/api/v1/chat` 完整端点：
- 接收用户消息 → 调用 CoachAgent.act()
- 格式化返回（含 reply 文本、DSL 信息、门禁状态）
- 错误处理 + fallback
- 测试：pytest 测试端点

### S9.3 — WebSocket + 实时交互
- `src/outer/api/ws.py` — WebSocket 连接管理
- 脉冲确认实时推送
- 远足交互通道
- 状态变更推送（门禁/指标）

### S9.4 — 数据查询端点
- `GET /api/v1/session` — 会话状态和指标
- `GET /api/v1/gates` — 8 门禁当前状态
- `GET /api/v1/metrics` — MRT 实验数据、审计健康

### S9.5 — Web 前端（React）
- 项目初始化（Vite + React + TypeScript）
- ChatView — 对话气泡、输入框、消息列表
- PulseModal — 改写/接受弹窗
- ExcursionPanel — 远足多选项
- Dashboard — TTM 阶段、SDT 评分、门禁状态可视化
- 状态栏 — 辅助强度、当前会话统计

### S9.6 — 集成测试 + 部署
- 端到端测试（API → CoachAgent → 响应）
- Dockerfile 构建
- 启动脚本

---

## 8. config/coach_defaults.yaml 新增段

```yaml
# ── Phase 9: API 服务 ──────────────────────────────
api:
  enabled: false
  host: "127.0.0.1"
  port: 8000
  token: "coherence-dev-token"
  cors_origins: ["http://localhost:5173"]
```

---

## 9. 测试策略

| 类型 | 覆盖 | 工具 |
|------|------|------|
| API 单元测试 | 各端点输入/输出验证 | pytest + httpx |
| WebSocket 测试 | 脉冲/远足交互流程 | pytest + websockets |
| 集成测试 | API → CoachAgent 全链路 | pytest |
| 回归测试 | 1070 已有测试保持 pass | pytest -q |
| 前端测试 | 组件渲染 | Vitest + Testing Library |

---

## 10. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| CoachAgent 有状态，HTTP 无状态冲突 | 低 | 高 | SessionManager 持有单例 |
| 脉冲确认需要异步回调 | 中 | 中 | WebSocket 双向通信 |
| 前端技术选型不适合后续移动端 | 中 | 高 | Web 验证 → Flutter 迁移 |
| API 暴露未鉴权的系统能力 | 低 | 中 | token 认证 + CORS 限制 |

---

## 11. 路由命令

| 命令 | 子阶段 | 交付物 |
|------|--------|--------|
| `/run_phase9_s1` | API 基础设施 | main.py / routes.py / models.py / session.py / auth.py |
| `/run_phase9_s2` | Chat 端点 | POST /api/v1/chat 完整实现 |
| `/run_phase9_s3` | WebSocket | ws.py + 脉冲/远足实时交互 |
| `/run_phase9_s4` | 数据查询 | GET session/gates/metrics 端点 |
| `/run_phase9_s5` | Web 前端 | React 项目 + 4 个核心组件 |
| `/run_phase9_s6` | 集成 + 部署 | e2e 测试 + Dockerfile |

---

## 12. 成功标准

1. `curl POST /api/v1/chat` 返回正确的教练响应
2. 脉冲确认通过 WebSocket 实时推送和接收
3. 前端对话界面可用，显示历史消息
4. 仪表盘展示 TTM 阶段和门禁状态
5. 1070 已有测试零回归
6. 新增 API 测试全部 pass
7. 不修改任何已冻结代码

---

你可以先定前端方向——**React Web 优先验证**，还是直接上 **Flutter 三平台**？定下来后输入 `/run_phase9_s1` 开始实施。
