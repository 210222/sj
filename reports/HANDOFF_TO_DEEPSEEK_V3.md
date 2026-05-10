# Coherence V19 — 全项目交接档案 (DeepSeek V3)

**交接时间**: 2026-05-08
**项目路径**: `D:/Claudedaoy/coherence`
**当前基线**: Phase 0-16 全部 GO, 1266 tests pass, LLM 已启用 (DeepSeek V4 Flash)
**交接方**: Claude Code → **接收方**: DeepSeek

---

## 1. 项目是什么

Coherence 是一个**认知主权保护 AI 教练系统**。不是传统的 AI 助手优化器，而是确保用户在与 AI 交互时保有"可中断、可拒绝、可脱离的认知主导权"的教练。

### 核心架构

```
用户输入 → CoachAgent.act()
  → TTM 阶段检测 → SDT 动机评估 → Flow 心流计算
  → composer 选 action_type
  → LLM (DeepSeek) 或 FallbackEngine 生成教学内容
  → DiagnosticEngine 定期出诊断题 → BKT 掌握度追踪
  → 8 道安全门禁检查
  → 主权脉冲/远足检测
  → 返回 DSL 响应包
```

---

## 2. 你的角色和职责

### 你的身份

你是本项目的 **AI 实现者** — 负责代码生成、测试、调试、审计。用户是 **规则制定者 + 验收者** — 不写代码，只看结果。

### 核心规则

1. **每次只做一个模块** — 不可跨阶段并行开发
2. **禁改边界**: `contracts/**`、`src/inner/**`、`src/middle/**` 不可修改
3. **全量回归**: 每次修改后必须 `python -m pytest tests/ -q` 且 1266 tests 全部 pass
4. **所有新特性默认 OFF** — 通过 `config/coach_defaults.yaml` 的 `enabled: false` 控制
5. **每个新 Phase 必须先 Plan Mode**: EnterPlanMode → 并行 Agent 审计 → 写计划 → 用户审批 → 执行

### 单模块开发协议

```
用户指定本轮模块 → 用户给出规则参数 → AI 读取 contracts/ 生成代码
→ 类型检查 → 测试 → 用户确认 GO → 锁定进入下一阶段
```

---

## 3. 当前阶段状态

### Phase 0-16 全部 GO

| Phase | 名称 | 核心交付 | 状态 |
|------|------|---------|------|
| 0-8 | 后端引擎 | Ledger/Audit/Clock/Gates + Coach/DSL/TTM/SDT/Flow/MAPEK | GO ✅ |
| 9 | 前端+移动端 | FastAPI + React+TS Web + Flutter 移动端 | GO ✅ |
| 10 | LLM 集成 S1-S5 | DeepSeek客户端/安全校验/流式/记忆/代码沙箱 | GO ✅ |
| 11 | 交互质量 | 结构化教学/个性化/steps 生成 | GO ✅ |
| 12 | Fallback 规则 | FallbackEngine 模板库 | GO ✅ |
| 13 | 自适应+持久化 | TTM/SDT/Diag 激活 + SessionPersistence | GO ✅ |
| 14 | 诊断→适应闭环 | BKT难度注入 + 上下文引用 | GO ✅ |
| 15 | 个性化闭环固化 | 5 字段透传 + 契约 + 评测 | GO ✅ |
| 16 | 能力唤醒 | Capabilities目录 + 对话启用模块 | GO ✅ |

### 测试增长曲线

```
698 → 714 → 776 → 808 → 839 → 881 → 916 → 975 → 1034 → 1070
→ 1157 → 1174 → 1187 → 1203 → 1214 → 1256 → 1266
```

---

## 4. 项目结构速查

```
coherence/
├── CLAUDE.md                    # 项目宪法
├── contracts/                   # 14 份冻结合约 — 禁改
│   ├── ledger/audit/clock/resolver/gates.json
│   ├── coach_dsl/user_profile/ttm_stages/mapek_loop.json
│   ├── causal_governance/operations_governance.json
│   ├── api_contract/llm_contract.json
│   └── personalization_contract.md
│
├── src/coach/                   # 32 文件, 5,899 行 — 核心引擎
│   ├── agent.py (1034行)        # 主编排器 — 所有 Phase 集成点
│   ├── composer.py              # action_type 选择 + payload 构建
│   ├── fallback.py              # FallbackEngine — LLM OFF 时教学模板
│   ├── diagnostic_engine.py     # DiagnosticEngine — BKT 掌握度追踪
│   ├── persistence.py           # SessionPersistence — SQLite 跨会话
│   ├── ttm.py / sdt.py / flow.py # 行为科学三模型
│   ├── memory.py                # SessionMemory — 会话记忆
│   └── llm/ (10 文件)           # LLM 集成: client/prompts/schemas/safety_filter/audit/sandbox
│
├── api/                         # FastAPI 服务层, 18 文件
│   ├── main.py                  # 应用入口, CORS, 路由注册
│   ├── routers/ (8 文件)        # chat/session/pulse/excursion/dashboard/admin/code_executor/config
│   ├── services/ (3 文件)       # coach_bridge/pulse_service/dashboard_aggregator
│   ├── middleware/ (2 文件)     # auth (IAM)/rate_limit
│   └── models/ (2 文件)        # schemas/websocket
│
├── frontend/                    # React+TS Web 前端, 15 组件
│   └── src/components/
│       ├── chat/ (5)            # ChatBubble/ChatInput/PulsePanel/ExcursionOverlay/AwakeningPanel
│       ├── dashboard/ (4)       # TTMStageCard/SDTEnergyRings/ProgressTimeline/GateShieldBadge
│       ├── admin/ (3)           # GatePipeline/AuditLogViewer/RiskDashboard
│       ├── shared/ (2)          # SlideToConfirm/HealthShield
│       └── settings/ (1)        # SettingsPanel — 14 toggle 开关
│
├── mobile/                      # Flutter 移动端, 31 Dart 文件, 2,751 行
├── config/
│   └── coach_defaults.yaml      # 全部可调参数 + 能力目录
├── tests/                       # 79 文件, 16,013 行, 1266 tests
├── meta_prompts/coach/          # 元提示词 (~95 XML, 135-150 为 Phase 15/16)
└── reports/                     # 审计报告 + 阶段报告 + 交接文档
```

---

## 5. 快速验证命令

```bash
cd D:/Claudedaoy/coherence

# 启动后端 (含 LLM)
set DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001

# 启动前端
cd frontend && npm run dev

# 全量测试回归 (每次修改后必须运行)
python -m pytest tests/ -q
# 预期: 1266 passed

# 启动移动端
cd mobile && flutter run -d edge

# 查看已冻结合约
python -c "import os,json;[print(f'{f}: frozen') for f in sorted(os.listdir('contracts')) if f.endswith('.json') and json.load(open(f'contracts/{f}',encoding='utf-8')).get('status')=='frozen']"
```

---

## 6. 能力清单 (Capabilities)

13 个模块，当前 default 均为 `enabled: false`（除 LLM）：

| 模块 | 用途 | 风险 |
|------|------|------|
| LLM (DeepSeek) | AI 智能回复 | 低 |
| TTM | 学习阶段检测 (前意向→维持) | 低 |
| SDT | 动机评估 (自主性/胜任感/关联性) | 低 |
| Flow | 心流动态难度调节 | 中 |
| DiagnosticEngine | 定期出诊断题 + BKT 追踪 | 中 |
| Counterfactual | 反事实仿真 | 中 |
| Diagnostics | 因果诊断三件套 | 高 |
| MAPE-K | 自主控制循环 | 高 |
| MRT | 微随机对照实验 | 高 |
| Precedent Intercept | 失败先例拦截 | 中 |
| Sovereignty Pulse | 主权脉冲确认 | 低 |
| Excursion | 探索模式 (/excursion) | 低 |
| Relational Safety | 关系安全过滤 | 低 |

---

## 7. 数据流完整性 (已知缺口)

| 字段 | 后端产出 | API透传 | WS透传 | 前端类型 | 前端渲染 |
|------|---------|---------|--------|---------|---------|
| ttm_stage | ✅ | ✅ | ✅ | ✅ | ✅ (TTMStageCard) |
| sdt_profile | ✅ | ✅ | ✅ | ✅ | ✅ (SDTEnergyRings) |
| flow_channel | ✅ | ✅ | ✅ | ✅ | ❌ 未渲染 |
| awakening | ✅ | ✅ | ❌ | ❌ | ❌ (AwakeningPanel 死代码) |
| diagnostic_result | ✅ | ✅ | ✅ | ✅ | ❌ |
| diagnostic_probe | ✅ | ✅ | ✅ | ✅ | ❌ |
| personalization_evidence | ❌ | ✅ | ✅ | ❌ | ❌ |
| memory_status | ❌ | ✅ | ✅ | ❌ | ❌ |
| difficulty_contract | ❌ | ✅ | ✅ | ❌ | ❌ |

---

## 8. 已知例外与风险

| 项目 | 说明 |
|------|------|
| 配置污染 | coach_defaults.yaml 会在测试中被修改。每次 Phase 结束需手动恢复并确认 `llm.enabled=true` |
| 巴士因子=1 | 单人项目 |
| 无 CI/CD | 本地单用户运行 |
| E2E 测试缺失 | 0 条端到端测试 |
| WS/HTTP 字段缺口已修复 | Phase 15 已将 WS 从 6 字段扩到 20 字段 |
| 前端组件存在但未渲染 | AwakeningPanel/ProgressTimeline/HealthShield 是死代码 |
| API Key 管理 | 只从环境变量读取，不写入文件 |

---

## 9. 启动 Checklist (新 Agent 4 步验证)

```bash
# 1. 确认基线
cd D:/Claudedaoy/coherence && python -m pytest tests/ -q
# 预期: 1266 passed

# 2. 验证合约
python -c "
import os, json
for f in sorted(os.listdir('contracts')):
    if f.endswith('.json'):
        c = json.load(open(f'contracts/{f}', encoding='utf-8'))
        print(f'{f}: v{c.get(\"version\",\"?\")} [{c.get(\"status\",\"?\")}]')
"
# 预期: 13 份合约, 全部 frozen

# 3. 验证 coach 导入
python -c "from src.coach import CoachAgent; a=CoachAgent(); r=a.act('hello'); print('Coach OK, keys:', len(r))"
# 预期: Coach OK, keys: 31

# 4. 验证 LLM 可用
set DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
python -c "
from src.coach.llm.client import LLMClient
from src.coach.llm.config import LLMConfig
import yaml
with open('config/coach_defaults.yaml',encoding='utf-8') as f: c=yaml.safe_load(f)
c['llm']['enabled']=True
lc=LLMConfig.from_yaml(c)
client=LLMClient(lc)
print(f'LLM OK: model={lc.model}')
"
# 预期: LLM OK: model=deepseek-chat
```

---

**此文档由 Claude Code 在 2026-05-08 Phase 16 完结后生成，基于 3 次并行全项目审计。**
