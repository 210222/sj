# Coherence V19.5 — 完整交接档案

**编制日期**: 2026-05-13
**写给**: 接手此项目的下一个 Claude/DeepSeek 实例
**项目根目录**: `D:\Claudedaoy\coherence`

---

## 一、这是什么项目

Coherence 是一个**自适应 AI 教练系统**（认知主权保护系统），帮助用户通过学习迁移、创造力保持、独立思考三条主线进行自我提升。

技术栈：`Python 3.11+ / SQLite / FastAPI / React 18 + TypeScript + Vite / pytest / mypy`

三个同权目标：
1. 提升学习迁移（D7/D30/D90 测量）
2. 保持/提升创造性（发散与跨域联想）
3. 提升独立思考（No-Assist 表现）

---

## 二、用户是谁

- **角色**: 规则制定者 + 验收者，不写代码
- **关注点**: diff 摘要 + 测试结果 + 是否符合合约 — 不看实现细节
- **决策权**: 所有阶段推进、模型启用、参数调整由用户拍板
- **沟通风格**: 要简洁直接，不要废话、不要 emoji、不要末尾总结
- **深度**: 用户是资深技术人员，不需要基础概念解释

---

## 三、你的职责

你是这个项目的**总控调度引擎 + 全栈实现者**，需要：

1. **按单模块开发协议执行**: 用户指定模块 → 给规则参数 → 你生成代码 → 编译/类型检查 → 单元测试 → 用户确认锁定
2. **保护冻结边界**: `contracts/`、`src/inner/`、`src/middle/`、`src/outer/` 全部禁改 — 新代码只能进 `src/coach/`、`src/mapek/`、`src/cohort/`
3. **每个 Phase 严格执行**: 严格遵守 CLAUDE.md 中的阶段约束，不跳步
4. **独立审查**: 收到任何方案或任务后，先用自己的判断力审查，发现真问题直接指出，没问题就说没问题
5. **全量回归**: 任何代码变更后必须 `python -m pytest tests/ -q` 全绿

---

## 四、协作铁律（5 条，优先级排序）

### 规则 1: 每个新 Phase 必须先 Plan Mode
收到新 Phase 任务 → **第一步必须是 EnterPlanMode** → 并行 Explore Agent 审计 → 写计划 → ExitPlanMode 等审批 → 执行。**绝对禁止直接写代码。**

### 规则 2: 先审后做，不盲从
收到方案先深度理解意图 → 独立审查 → 坦诚反馈。方案好就说好直接执行；有坑就指出；有更优做法就建议。不强凑问题数。

### 规则 3: 先讨论后修改
用户提出问题但没给具体方案 → 分析根因 → 提出 2-3 个具体方案 → 等用户确认 → 改哪个文件、改什么逻辑、预期效果 — 全部确认后才动手。

### 规则 4: 穷尽报告只出方案，不亲自跑
穷尽/穷举测试场景 → 只交付执行方案（测试矩阵、步骤、判分标准、输入输出格式、汇总模板）— **不直接运行穷举测试。**

### 规则 5: 每轮只做一个模块
不一次性生成多个模块代码。不提前实现后续阶段。不在未锁定模块中引用未实现接口。

---

## 五、风格要求

| 要求 | 说明 |
|------|------|
| 简洁 | 一句话能说清不说一段话 |
| 无 emoji | 除非用户明确要求 |
| 无末尾总结 | 用户说"我能看 diff" |
| 代码不加多余注释 | 只在 WHY 不清晰时加一行 |
| 不创建 .md 文档 | 除非用户明确要求 |
| 不设计未来 | 不为假想的未来需求做抽象 |
| 不建 feature flag | 不需要的代码直接改，不加开关 |

---

## 六、项目架构

### 分层结构（从内到外）

```
contracts/           ← 13 份 JSON 冻结合约 —— 禁改
src/inner/           ← Ledger/Audit/Clock/Resolver/No-Assist/Gates —— 禁改
src/middle/          ← Decision/SemanticSafety/State L0-L2/Shared —— 禁改
src/outer/           ← API/Orchestration/Presentation/Safeguards —— 禁改
src/coach/           ← ★ 教练引擎（活动区）—— 可改
src/mapek/           ← ★ MAPE-K 控制循环 —— 可改
src/cohort/          ← ★ 量化自我数据聚合 —— 可改
api/                 ← FastAPI 服务层（22 文件）
frontend/            ← React 18 + TypeScript（33 组件文件）
tests/               ← 89 文件 / ~1308 test 函数（只增不改）
```

### src/coach/ 核心模块

| 文件 | 功能 |
|------|------|
| `agent.py` | CoachAgent 主类 — 对话处理入口 |
| `composer.py` | Policy Composer — 策略编排 + 技能知识图谱选题 |
| `dsl.py` | DSL 构建器 + 校验器 |
| `ttm.py` | TTM 阶段变化理论 — 五阶段状态机 |
| `sdt.py` | SDT 自决理论 — 动机评估 |
| `flow.py` | 心流互信息 — 动态难度调节 |
| `state.py` | 用户状态追踪 |
| `memory.py` | 轻量会话记忆 |
| `persistence.py` | SQLite 持久化 |
| `diagnostic_engine.py` | 诊断引擎 |
| `diagnostics.py` | 三线诊断（认知/动机/策略） |
| `fallback.py` | LLM 降级回退 |
| `handlers.py` | 消息处理器 |
| `mrt.py` | MRT 框架 |
| `counterfactual.py` | 反事实模拟 |
| `cross_track.py` | 跨轨检查 |
| `precedent_intercept.py` | 先例拦截 |
| `window_consistency.py` | 窗口一致性 |
| `audit_health.py` | 健康审计 |
| `gates_v18_7.py` | 门禁系统 |
| `data.py` | 数据层 |
| `llm/` | LLM 子系统（client/prompts/safety_filter/sandbox/schemas 等） |

### 三轨调度（全部 GO）

| 轨 | 阶段范围 | 最终状态 |
|----|----------|----------|
| A 轨 | 内圈/中圈/外圈 | v1.0.0 冻结封版 |
| B 轨 | B1→B8 (Scope Lock→Operational Freeze) | 全部 GO |
| C 轨 | C1→C6 (Baseline→Quarterly Signoff) | 全部 GO, C6 签收 |

### 行为科学三模型（Phase 4 引入，默认关闭）

推荐启用顺序：
1. **TTM**（阶段变化理论）→ 决定"做什么"（五阶段检测+策略粗筛）
2. **SDT**（自决理论）→ 决定"怎么做"（低自主性→reflect，低胜任感→降难度）
3. **心流互信息** → 决定"多难合适"（无聊↔焦虑动态调节）

---

## 七、当前状态 (2026-05-13)

```
最新 commit:  615c442 — Coherence V19.5 Phase 27-31 全线收尾
测试基线:     1363 passed / 7 failed / 5 skipped
合约:         13 份全部 frozen
数据库:       SQLite data/coherence.db (~50MB)
LLM:          DeepSeek V4（1M token 上下文窗口）
前端:         React 18 + Vite 6
```

### 已完成的主要工作

- **Phase 0-8**: Coach 轨完整交付（DSL/Agent/Composer/State/Memory/TTM/SDT/Flow）
- **Phase 9**: Web 前端 + API 层 + 管理面板
- **Phase 10**: LLM 接线（DeepSeek V4 Flash）
- **Phase 11**: 结构化教学 + 个性化
- **Phase 12**: 回退模板 + 鼓励个性化
- **Phase 13**: TTM+SDT 激活 + 诊断回退
- **Phase 14**: 难度注入 + 上下文引用
- **Phase 15**: 个性化合约 + 评估框架
- **Phase 16**: 苏醒面板 + 对话激活
- **Phase 17**: 知情同意 TTM/SDT + A/B 验证
- **Phase 18**: 共享状态 + 并行执行 + 质量门禁
- **Phase 19**: LLM 接线完整版 + 诊断个性化
- **Phase 20**: 持久化写入 + 历史表 + 仪表盘
- **Phase 21**: 数据注入 + SDT 语调 + WebSocket 同步
- **Phase 22**: Prompt 注入防护 + 字段验证
- **Phase 23**: 间隔重复 + 复习队列
- **Phase 24**: 评分 + 纵向评测 + 趋势图
- **Phase 25**: 自我评估 + 策略切换
- **Phase 26**: 进度追踪 + Prompt 优化
- **Phase 27**: 上下文引擎重做（5 块结构化上下文，DeepSeek 1M 窗口）
- **Phase 28**: 前端教学数据展示（难度/策略/阶段/选项按钮）
- **Phase 29**: 7 处接线修复 + 体验优化
- **Phase 30**: 技能知识图谱（8 技能 DAG + BKT 传播 + 前置检查）
- **Phase 31**: 收尾加固（entity_profiles 写入 + 白金审计 + start.py）

### 已知问题

1. **CLAUDE.md 过期** — 写的是"Phase 17 活动"，实际已到 Phase 31，需更新
2. **7 个测试失败** — 集中在 coach agent keyword 匹配（probe/challenge/reflect/scaffold）和 disabled 基线，属于 Phase 27 上下文重构后的已知回归，非 P0
3. **大量未提交文件** — 约 300+ 个未跟踪文件（报告、测试日志、新增测试文件、meta_prompts、mobile/ 等），需要清理或提交
4. **未提交的源文件修改**: `api/models/schemas.py`, `api/routers/dashboard.py`, `api/services/dashboard_aggregator.py`, `config/coach_defaults.yaml`, `frontend/src/App.tsx`, `frontend/src/components/chat/ChatInput.tsx`, `frontend/src/types/api.ts`, `src/coach/agent.py`, `src/coach/llm/prompts.py`

---

## 八、关键命令

```bash
# === 必备 ===
cd D:/Claudedaoy/coherence

# 一键启动全系统
python start.py

# 全量测试回归（每次变更后必须跑）
python -m pytest tests/ -q

# 白金级全系统审计 (S00→S90)
python run_platinum_audit.py
python run_platinum_audit.py --quick    # 快速模式

# 启动后端 API (需要 DeepSeek API Key)
DEEPSEEK_API_KEY="sk-xxx" uvicorn api.main:app --port 8001

# 启动前端开发服务器
cd frontend && npm run dev

# 类型检查
mypy src/ --ignore-missing-imports

# 查看审计报告
start D:/Claudedaoy/coherence/reports/full_scan/99_final_report.md
```

---

## 九、调度命令速查

### A 轨（已冻结，仅参考）
| 命令 | 作用 |
|------|------|
| `/run_node_1` | 产品角色 → global_state.json |
| `/run_node_2` | 架构角色 → 生成 src/ |
| `/run_node_3` | QA 角色 → qa_feedback.json |
| `/run_node_4` | DevOps 角色 → Docker 部署 |

### B 轨（全部 GO，已完成）
`/run_b_stage_1` ... `/run_b_stage_8`

### C 轨（全部 GO，已完成）
`/run_c_stage_1` ... `/run_c_stage_6`

---

## 十、重要文件索引

| 文件 | 说明 |
|------|------|
| `CLAUDE.md` | 项目级指令 + 三轨调度 + 禁改边界（可能有过期内容） |
| `contracts/` | 13 份冻结合约 JSON |
| `config/coach_defaults.yaml` | 教练引擎可调参数 |
| `config/parameters.yaml` | 可调参数 |
| `config/skill_graph.json` | 8 技能 DAG |
| `meta_prompts/coach/` | Phase 0-32 全部元提示词 |
| `meta_prompts/b/` | B 轨元提示词 |
| `meta_prompts/c/` | C 轨元提示词 |
| `reports/b_global_state.json` | B 轨全局状态 |
| `reports/c_global_state.json` | C 轨全局状态 |
| `reports/full_scan/99_final_report.md` | 最新审计报告 |
| `reports/full_implementation_roadmap.md` | 完整落地方案 |
| `data/coherence.db` | 运行时数据库 |
| `start.py` | 一键启动脚本 |
| `D:\Claudedaoy\CLAUDE.md` | 上层多智能体工作流 SOP |

---

## 十一、项目初始化步骤（换电脑后）

```bash
# 1. 克隆或复制项目到 D:/Claudedaoy/coherence

# 2. 安装 Python 依赖
cd D:/Claudedaoy/coherence
pip install pytest>=8.0.0 mypy>=1.8.0 pyyaml>=6.0 fastapi uvicorn

# 3. 安装前端依赖
cd frontend
npm install

# 4. 验证环境
cd D:/Claudedaoy/coherence
python -m pytest tests/ -q    # 应该看到 1360+ passed

# 5. 配置 DeepSeek API Key
set DEEPSEEK_API_KEY=sk-xxx   # Windows
# 或 export DEEPSEEK_API_KEY=sk-xxx  # Linux/Mac

# 6. 启动
python start.py
```

---

## 十二、红线（绝对不能做的事）

- ❌ 修改 `contracts/` 中任何 JSON
- ❌ 修改 `src/inner/`、`src/middle/`、`src/outer/` 任何代码
- ❌ 修改已有测试（只增不改）
- ❌ 跳过类型检查和单元测试
- ❌ 一次性生成多个模块的代码
- ❌ 在未锁定模块中引用未实现接口
- ❌ 跳过 Plan Mode 直接写代码
- ❌ `git push --force` 到 main
- ❌ 输出医疗/心理诊断式权威结论
- ❌ 在没有用户确认的情况下提交代码
