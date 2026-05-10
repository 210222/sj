# Phase 9 — 前端与移动端界面 完整落地方案

**编制日期**: 2026-05-04
**设计对齐源**: `前端和移动端页面设计.txt`（行为科学驱动的AI教练系统前端与移动端界面设计及项目审查深度报告）
**元提示词**: `meta_prompts/coach/00_phase9_orchestrator.xml` + `91~94_*.xml`
**当前基线**: 1070 tests pass, Phase 0-8 全部 GO, 11 份冻结合约
**前置**: Phase 8（最终门禁闭环与系统签收）已完成

---

## 0. 执行摘要

### 0.1 要建什么

将 Phase 0-8 完成的纯后端 Python 智能引擎，转化为面向终端用户的交互式服务产品。核心交付：

```
后端引擎(Python) → FastAPI 服务层 → React+TS Web前端 → 用户
                              ↘  Flutter 移动端 (第二阶段)
```

### 0.2 总量

| 指标 | 第一阶段 (当前) | 第二阶段 (移动端) |
|------|----------------|------------------|
| 新增源文件 | ~65 (api/ ~15, frontend/ ~45, config/ ~1, contracts/ ~1) | ~50 (Flutter) |
| 新增测试 | ~90 (50 API + 30 前端 + 10 降级) | — |
| 冻结合约 | 1 份 (api_contract.json) | — |
| 修改已有代码 | 零 | 零 |
| 预估工期 | ~10 天 (严格串行) | 待 Phase 9 GO 后启动 |

### 0.3 禁改铁律

```
src/inner/**         — 绝对禁止修改
src/middle/**        — 绝对禁止修改
src/outer/**         — 绝对禁止修改
src/coach/**         — 绝对禁止修改 (Coach 引擎全部冻结)
src/mapek/**         — 绝对禁止修改 (Phase 6 冻结)
src/cohort/**        — 绝对禁止修改 (接口占位)
contracts/*.json     — 已有 11 份禁止修改 (只新增 api_contract.json)
tests/               — 已有测试只新增不修改
config/coach_defaults.yaml — 已冻结, 只追加新增段
```

---

## 1. 设计文档核心提取

### 1.1 TTM 六态 → UI 组件映射

| TTM 阶段 | 用户心理状态 | 行为转化策略 | 具象化 UI 组件 |
|----------|------------|------------|--------------|
| 前意向 | 缺乏信息/气馁, 改变弊端>收益, 无意图 | 意识提升+环境再评估 | 极简看板; 低频Nudges; 非互动信息图表 |
| 意向 | 矛盾心理, 收益与障碍趋于平衡 | 自我再评估+戏剧性缓解 | Pros vs Cons决策平衡卡; 故事轮播; 收益进度条 |
| 准备 | 决策天平倾斜, 需结构化指导 | 自我解放, SMART目标 | 目标拆解Stepper; 微习惯日程表; 一键承诺 |
| 行动 | 动机峰值, 对摩擦极度敏感 | 反条件化+强化管理 | 发光进度环; 全屏撒花; 一键签到 |
| 维持 | 习惯巩固, 效能增长 | 刺激控制+社区支持 | 连续打卡热力图; 成就徽章墙; 高阶解锁 |
| 复发 | 非线性倒退, 挫败感 | 重构认知, 最短重启路径 | 关怀卡片; "时光机"一键恢复 |

### 1.2 SDT 界面转化

| 需求 | 策略 | 实现 |
|------|------|------|
| 自主性 | 放弃线型流程控制 | 仪表盘拖拽; 字体/背景自定义; Onboarding 跳过 |
| 胜任感 | 极致直观性 | 情境 Tooltips; 一致导航; 全局 Undo |
| 关联性 | 情感纽带 | 个性化语态; 一致设计语言 |

### 1.3 色彩矩阵（精确 Hex）

| 角色 | Hex | RGB | 用途 |
|------|-----|-----|------|
| 暖白色 | #F5F1EA | 245,241,234 | 主背景, 替代纯白 |
| 柔和蓝 | #AFC7E2 | 175,199,226 | AI气泡/导航/CTA |
| 鼠尾草绿 | #9CB59B | 156,181,155 | excursion/成功高亮 |
| 薰衣草灰 | #C6C1D2 | 198,193,210 | 次级图表/卡片投影 |
| 深摩卡 | #6E5B4E | 110,91,78 | 替代纯黑字色 |
| 珊瑚糖 | #FEDDD8 | 254,221,216 | 柔性警告, 替代纯红 |

檀香薄雾辅助色: #D8CBB8, #F4EFE7, #B39A7C, #8A7C70, #2F2C2A

### 1.4 三隐患修复

| 隐患 | 问题 | 修复 | 组件 |
|------|------|------|------|
| 脉搏确认疲劳 | 高强度无差别阻断 | 自适应降级: 10min/2次→旁路 | PulseService + useAdaptivePulse |
| 认知过载 | 8 Gates 对 C 端暴露 | RBAC: 用户盾牌, 管理员全流水线 | GateShieldBadge / GatePipeline |
| 单用户架构债 | 状态树未挂 token | IAM 骨架: token + session 树 | IAMSkeleton + useAuth |

---

## 2. 最终系统架构

```
用户 (Web 浏览器 → React SPA)
    │  HTTPS REST + WebSocket
    ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI 服务层                          │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ routers/ │  │ middleware/   │  │ services/          │ │
│  │ session  │  │ auth(IAM)    │  │ coach_bridge       │ │
│  │ chat+ws  │  │ rate_limit   │  │ pulse_service      │ │
│  │ pulse    │  │              │  │ dash_aggregator    │ │
│  │ excursion│  │              │  │                    │ │
│  │ dashboard│  │              │  │                    │ │
│  │ admin    │  │              │  │                    │ │
│  │ health   │  │              │  │                    │ │
│  └──────────┘  └──────────────┘  └────────────────────┘ │
└──────────────────────┬───────────────────────────────────┘
                       │ import (不修改源码)
                       ▼
┌──────────────────────────────────────────────────────────┐
│               已冻结 Python 后端 (Phase 0-8)              │
│  src/coach/  src/inner/  src/middle/  src/outer/        │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│              Web 前端 (React 18 + TypeScript)              │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ chat/    │  │ dashboard/   │  │ admin/             │ │
│  │ ChatBub  │  │ TTMStageCard │  │ GatePipeline       │ │
│  │ ChatInpt │  │ SDTEnergyRin│  │ AuditLogViewer     │ │
│  │ PulsePnl │  │ ProgressTime│  │ RiskDashboard      │ │
│  │ Excursn  │  │ GateShield  │  │                    │ │
│  └──────────┘  └──────────────┘  └────────────────────┘ │
│  hooks/: useWebSocket / useCoachState / useAdaptivePulse  │
│  styles/: theme.ts(Hex矩阵) / global.css / animations    │
│  utils/: stateMachine.ts(6态TTM) / colorAdapt.ts         │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 子阶段分解（严格串行）

### S9.1 — API 服务层（3 天）

**元提示词**: `meta_prompts/coach/91_api_layer.xml`
**路线**: `/run_phase9_1`

#### 路由表

| 端点 | 方法 | 功能 | 限流 |
|------|------|------|------|
| `/api/v1/session` | POST | 创建/恢复会话 + TTM 阶段返回 | 10/min |
| `/api/v1/chat` | POST | 消息 → CoachAgent → DSL 响应 | 30/min |
| `/api/v1/chat/ws` | WS | 实时推流 + 脉冲事件推送 | — |
| `/api/v1/pulse/respond` | POST | 接受/改写决策 | 30/min |
| `/api/v1/excursion/enter` | POST | 进入远足(返回 theme:"dark") | 5/min |
| `/api/v1/excursion/exit` | POST | 退出远足 | 5/min |
| `/api/v1/dashboard/user` | GET | TTM 雷达 + SDT 环 + 进度 | 10/min |
| `/api/v1/admin/gates/status` | GET | 8 门禁状态(管理员) | 30/min |
| `/api/v1/admin/audit/logs` | GET | 审计日志分页 | 20/min |
| `/api/v1/health` | GET | 健康检查 | 60/min |

#### 核心组件

**PulseService** — 自适应降级:
```python
MAX_BLOCKING_PULSES = 2
WINDOW_MINUTES = 10
def should_block(session_id) -> bool    # <MAX→True(阻断)
def get_blocking_mode(session_id) -> str # 'hard'|'soft'|'none'
```

**IAMSkeleton** — 多租户准备:
```python
def issue_anonymous_token() -> str       # UUID4
def validate_token(token) -> bool
def get_session_tree(token, sid) -> dict # 状态树根节点
```

**CoachBridge** — 适配器:
```python
# import 已冻结的 CoachAgent, 仅参数映射+序列化, 不修改源码
def chat(message, session_id) -> dict
def get_ttm_stage(session_id) -> str
def get_sdt_scores(session_id) -> dict
```

#### 测试

| 文件 | 内容 |
|------|------|
| `tests/test_api_session.py` | 会话 CRUD + token 隔离 |
| `tests/test_api_chat.py` | HTTP 对话 + WebSocket 推流 |
| `tests/test_api_pulse.py` | 脉冲决策 + 自适应降级边界 |
| `tests/test_api_dashboard.py` | TTM/SDT 聚合数据正确性 |
| `tests/test_api_rate_limit.py` | 限流击中/恢复/窗口重置 |

---

### S9.2 — Web 前端核心框架（4 天）

**元提示词**: `meta_prompts/coach/92_web_frontend.xml`
**路线**: `/run_phase9_2`

#### 色彩系统 — theme.ts

```typescript
export const coachColors = {
  warmWhite:    '#F5F1EA',   // 主背景
  softBlue:     '#AFC7E2',   // AI气泡/导航/CTA
  sageGreen:    '#9CB59B',   // excursion/成功高亮
  lavenderGray: '#C6C1D2',   // 次级填充/卡片投影
  deepMocha:    '#6E5B4E',   // 替代纯黑字
  coralCandy:   '#FEDDD8',   // 柔性警告(替代纯红)
  sandalwoodMist:'#D8CBB8',  // 檀香薄雾
  creamPaper:   '#F4EFE7',
  warmSand:     '#B39A7C',
  clayBrown:    '#8A7C70',
  charcoal:     '#2F2C2A',
} as const;
```

#### 核心组件

| 组件 | 设计要求 |
|------|---------|
| **PulsePanel** | 非阻断式内联滑动确认(Slide-to-Confirm) + 毛玻璃(backdrop-filter: blur) + 对话气泡区域纵向位移 |
| **ExcursionOverlay** | 全局主题切换: 白底→深色暗调; 边缘光晕; 气泡曲率改变; CSS transition 300ms |
| **TTMStageCard** | 五维雷达图展示各阶段倾向性评分 |
| **SDTEnergyRings** | 三环能量图: 自主性/胜任感/关联性, 流体饱和度提升+发光动画 |
| **GateShieldBadge** | 三色盾牌(绿/黄/红) — 不暴露"门禁/审计/P0/P1"等技术术语 |
| **useAdaptivePulse** | sessionStorage 脉冲计数 → 消费 blocking_mode |

#### TTM 状态驱动 UI — stateMachine.ts

```typescript
const TTM_UI_MAP = {
  precontemplation: { theme:'minimal', inputMode:'suggest_only', pulseMode:'disabled' },
  contemplation:    { theme:'balanced', inputMode:'reflect_first', pulseMode:'gentle' },
  preparation:      { theme:'active', inputMode:'scaffold', pulseMode:'commitment' },
  action:           { theme:'energetic', inputMode:'checkin', pulseMode:'high_frequency' },
  maintenance:      { theme:'calm', inputMode:'explore', pulseMode:'milestone' },
  relapse:          { theme:'gentle', inputMode:'recover', pulseMode:'none' },
};
```

---

### S9.3 — 治理仪表盘 + 管理后台（2 天）

**元提示词**: `meta_prompts/coach/93_admin_dashboard.xml`
**路线**: `/run_phase9_3`

#### RBAC 三级视图

| 角色 | 可见内容 |
|------|---------|
| **终端用户** | GateShieldBadge(三色盾牌) + TTMStageCard + SDTEnergyRings |
| **管理员** | GatePipeline 全展开(8门禁实时状态+趋势+下钻) + AuditLog + RiskDashboard |
| **开发调试** | 底层 Ledger 原始事件 + Gate 裁决详情 (调试模式开关) |

#### C 端阻断话术

被安全门阻断时 → 转换为 AI 教练拟人化话术:
> "这个问题有点复杂，让我们换一个更轻松的角度探讨"

#### 管理员左侧导航

```
全局概览 → 实时监控 → 阻断违规 → 风险评估 → 审计日志
```

---

### S9.4 — 无障碍加固 + 自适应降级联调（1 天）

**元提示词**: `meta_prompts/coach/94_accessibility_and_degradation.xml`
**路线**: `/run_phase9_4`

| 任务 | 内容 |
|------|------|
| WCAG AA 对比度 | 所有色彩组合自动验证: 正常文本≥4.5:1, 大文本≥3:1 |
| 环境光色温 | 20:00-06:00→暖色偏移+5%; 06:00-20:00→基准色温 |
| 降级全链路 | API PulseService → WebSocket → 前端 useAdaptivePulse 一致 |
| 最终回归 | 1070 + 50 API + 30 前端 + 10 降级 = 1160 pass |

---

## 4. 合约冻结

### api_contract.json（S9.2 结束时冻结）

```json
{
  "contract": "api_contract",
  "version": "1.0.0",
  "status": "frozen",
  "base_url": "/api/v1",
  "endpoints": [
    {"path": "/session", "method": "POST"},
    {"path": "/chat", "method": "POST"},
    {"path": "/chat/ws", "method": "WEBSOCKET"}
  ],
  "error_codes": {
    "SESSION_NOT_FOUND": {"http": 404},
    "RATE_LIMITED": {"http": 429, "retry_after_s": 60}
  },
  "rate_limits": {
    "default": {"requests": 30, "window_s": 60},
    "pulse": {"requests": 10, "window_s": 600}
  }
}
```

---

## 5. 子阶段总览

| 子阶段 | 命令 | 元提示词 | 工期 | 交付 | 测试新增 |
|--------|------|---------|------|------|---------|
| S9.1 | `/run_phase9_1` | `91_api_layer.xml` | 3天 | api/ 包 (FastAPI+WS+降级+IAM) | ~50 |
| S9.2 | `/run_phase9_2` | `92_web_frontend.xml` | 4天 | frontend/ (React+TS+TTM UI) | ~30 |
| S9.3 | `/run_phase9_3` | `93_admin_dashboard.xml` | 2天 | 治理仪表盘 (GatePipeline+RBAC) | ~20 |
| S9.4 | `/run_phase9_4` | `94_accessibility_...xml` | 1天 | WCAG+色温+降级联调 | ~10 |
| **合计** | | | **10天** | | **~110** |

---

## 6. 测试策略

| 层级 | 工具 | 要求 |
|------|------|------|
| API 路由 | pytest + httpx + FastAPI TestClient | 每个路由正常/异常路径 |
| WebSocket | pytest + websockets | 推流/脉冲/超时/重连 |
| 前端组件 | vitest + @testing-library/react | 渲染+交互+TTM 驱动 |
| 对比度 | vitest + 自定义 | 所有色彩组合 WCAG AA |
| 全链路降级 | pytest | API→WS→前端 完整链路 |
| 全量回归 | pytest -q + vitest run | 每阶段强制 |

---

## 7. 第二阶段：移动端（Flutter）

设计文档建议的 Flutter 架构（底部导航栏: 对话/探索/成长/配置; 离线优先; 50+ 界面）作为独立阶段。Phase 9 GO 后可启动。

**第二阶段前置条件**:
```
Phase 9 全部 GO
contracts/api_contract.json 已冻结
WebSocket 协议稳定
```

共享资产:
- API 合约 (api_contract.json)
- WebSocket 消息协议
- 色彩系统 (theme.ts → Flutter ThemeData)

---

## 8. 成功标准

```
Phase 9 结束时:
1. api/ 包存在: FastAPI + 10 路由 + WebSocket + 降级 + IAM
2. frontend/ 存在: React + TS 完整前端
3. 设计文档 6 主色+5 辅助色 Hex 精确实现
4. TTM 6 态 UI 映射完整
5. PulsePanel 非阻断滑动确认
6. ExcursionOverlay 全局暗调切换
7. GateShieldBadge 三色盾牌(无技术术语)
8. GatePipeline 管理员视图(下钻展开)
9. 全部色彩组合通过 WCAG AA
10. 自适应降级全链路验证通过
11. contracts/api_contract.json 已冻结
12. 1070 + ~110 新增 = ~1180 tests 全部 pass
13. 不修改任何禁改区文件
14. reports/coach_global_state.json Phase 9 → GO
```
