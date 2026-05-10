# Coherence — V18.8.3 认知主权保护系统

## 可执行命令

```bash
# 白金级全系统审计 (S00→S90 完整流水线)
cd D:/Claudedaoy/coherence && python run_platinum_audit.py

# 快速审计模式 (跳过 S10/S40/S50，约 30 秒)
cd D:/Claudedaoy/coherence && python run_platinum_audit.py --quick

# 仅运行全量测试回归
cd D:/Claudedaoy/coherence && python -m pytest tests/ -q

# 查看审计报告
start D:/Claudedaoy/coherence/reports/full_scan/99_final_report.md
```

## 适用前提

- 单用户系统，个人本地运行
- LLM 通过 API 调用
- 用户不写代码，只做规则决策与验收
- AI（Claude Code）负责全部代码实现

## 核心原则

### 内圈优先

内圈（Ledger → 审计 → 时钟 → 仲裁器 → No-Assist → 门禁骨架）未跑通前，中圈和外圈一行代码都不写。

### 单模块开发协议

每轮只做一个模块。流程如下：

1. 用户指定本轮模块
2. 用户给出规则参数（阈值、边界、禁止项）
3. AI 读取已锁定的 contracts/ 文件，生成代码
4. AI 编译/类型检查 → 报错 → 修复 → 通过
5. AI 生成单元测试 → 运行 → 失败 → 修复 → 通过
6. AI 展示 diff + 测试结果
7. 用户确认锁定，AI 更新 contracts/ 中的接口文件（如有新增接口）

### 模块分类与代码生成策略

| 分类 | 特征 | 策略 |
|------|------|------|
| A 类（高确定性） | I/O 明确、规则可穷举 | AI 直接生成，跑类型检查+单测 |
| B 类（中确定性） | 核心逻辑明确但参数需校准 | AI 生成代码，参数写成配置文件常量 |
| C 类（低确定性） | 涉及统计推断、领域判断 | AI 生成接口+测试桩+简单基线，核心由用户审核 |

### 禁止行为

- 禁止修改 `contracts/` 中任何已锁定的 JSON 文件（除非用户明确要求并标记版本升级）
- 禁止在中圈/外圈模块中重新定义内圈已锁定的数据结构
- 禁止跳过编译检查和单元测试就直接展示结果
- 禁止一次性生成多个模块的代码
- 禁止在未锁定的模块中引用未实现的模块接口

### 用户角色

- 用户 = 规则制定者 + 验收者
- 用户不参与代码编写，不审查实现细节
- 用户只看：diff 摘要 + 测试通过/失败 + 是否符合合约定义
- 用户的"通过" = 锁定模块，进入下一步

## 项目结构

```
coherence/
├── CLAUDE.md              # 本文件
├── contracts/             # 已冻结的接口合约（后续模块只读）
│   ├── README.md
│   ├── ledger.json
│   ├── audit.json
│   ├── clock.json
│   ├── resolver.json
│   └── gates.json
│   ├── coach_dsl.json     # ★ 新增（阶段1冻结）
│   ├── user_profile.json  # ★ 新增（阶段2冻结）
│   ├── ttm_stages.json    # ★ 新增（阶段4冻结）
│   └── mapek_loop.json    # ★ 新增（阶段6冻结）
├── src/                   # 源代码
│   ├── inner/             # ✅ 已冻结，禁改
│   │   ├── ledger/
│   │   ├── audit/
│   │   ├── clock/
│   │   ├── resolver/
│   │   ├── no_assist/
│   │   └── gates/
│   ├── middle/            # ✅ 已冻结，禁改
│   ├── outer/             # ✅ 已冻结，禁改
│   ├── coach/             # ★ 新增：教练引擎（阶段1）
│   │   ├── agent.py       # CoachAgent 主类
│   │   ├── dsl.py         # DSL 构建器+校验器
│   │   ├── composer.py    # Policy Composer
│   │   ├── state.py       # 用户状态追踪
│   │   ├── memory.py      # 轻量会话记忆
│   │   ├── ttm.py         # TTM 状态机（阶段4）
│   │   ├── sdt.py         # SDT 动机评估（阶段4）
│   │   └── flow.py        # 心流互信息计算（阶段4）
│   ├── mapek/             # ★ 新增：MAPE-K 控制循环（阶段6）
│   └── cohort/            # ★ 新增：量化自我数据聚合（阶段2接口占位）
├── tests/                 # 单元测试（698 + 阶段性新增）
├── config/
│   ├── parameters.yaml    # 可调参数
│   └── coach_defaults.yaml # ★ 新增：教练引擎参数（阶段1）
├── reports/
│   ├── full_implementation_roadmap.md  # ★ 完整落地方案
│   ├── gap_analysis_vs_design_docs.md  # ★ 差距分析
│   └── ... (已有报告)
└── data/                  # 运行时数据（SQLite 等）
```

## 目标与红线

### 三大同权目标
1. 提升学习迁移（D7/D30/D90）
2. 保持/提升创造性（发散与跨域联想）
3. 提升独立思考（No-Assist 表现）

### 硬红线
- 不输出医疗/心理诊断式权威结论
- 高风险动作必须可回退
- 因果只做证据排序，不做真值承诺
- 不让用户长期沦为审核员
- 创造性双周不低于基线 -3%

## 技术栈

- 语言：Python 3.11+
- 存储：SQLite（单文件，零运维）
- 类型检查：mypy
- 测试框架：pytest
- 时区处理：所有时间统一 UTC

---

## A/B 双轨调度

### A 轨 — 内圈/中圈/外圈 A 版（已冻结）

| 命令 | 处理器 | 说明 |
|------|--------|------|
| `/run_node_1` | `meta_prompts/outer/01_product_outer.xml` | 产品角色，写 global_state.json |
| `/run_node_2` | `meta_prompts/outer/02_architect_outer.xml` | 架构角色，生成 src/ 代码 |
| `/run_node_3` | `meta_prompts/outer/03_qa_outer.xml` | QA 角色，审查 src/，输出 qa_feedback.json |
| `/run_node_4` | `meta_prompts/outer/04_devops_outer.xml` | DevOps 角色，生成 Docker 部署文件 |

### B 轨 — 外圈 B 版受控演进（当前活动）

| 命令 | 处理器 | 阶段 |
|------|--------|------|
| `/run_b_stage_1` | `meta_prompts/b/01_scope_lock.xml` | B1 范围锁定 |
| `/run_b_stage_2` | `meta_prompts/b/02_design_freeze.xml` | B2 设计冻结 |
| `/run_b_stage_3` | `meta_prompts/b/03_implementation.xml` | B3 实现 |
| `/run_b_stage_4` | `meta_prompts/b/04_gate_validation.xml` | B4 门禁验证 |
| `/run_b_stage_5` | `meta_prompts/b/05_observation.xml` | B5 观测窗口 |
| `/run_b_stage_6` | `meta_prompts/b/06_signoff.xml` | B6 最终签收 |
| `/run_b_stage_7` | `meta_prompts/b/07_release_hardening.xml` | B7 发布加固 |
| `/run_b_stage_8` | `meta_prompts/b/08_operational_freeze.xml` | B8 运营冻结 |

**B 轨调度协议**：严格串行，上一阶段非 GO 不得进入下一阶段（B1→B8）。
B 轨状态文件：`reports/b_global_state.json`（与 A 轨 `global_state.json` 隔离）。

### C 轨 — 持续运营与演进治理（当前活动）

| 命令 | 处理器 | 阶段 |
|------|--------|------|
| `/run_c_stage_1` | `meta_prompts/c/01_baseline_freeze.xml` | C1 基线封版 |
| `/run_c_stage_2` | `meta_prompts/c/02_change_policy.xml` | C2 变更准入 |
| `/run_c_stage_3` | `meta_prompts/c/03_continuous_observation.xml` | C3 持续观测 |
| `/run_c_stage_4` | `meta_prompts/c/04_resilience_drills.xml` | C4 韧性演练 |
| `/run_c_stage_5` | `meta_prompts/c/05_release_train.xml` | C5 发布列车 |
| `/run_c_stage_6` | `meta_prompts/c/06_quarterly_signoff.xml` | C6 季度签收 |

**C 轨调度协议**：严格串行（C1→C6），上一阶段非 GO 不得进入下一阶段。
C 轨状态文件：`reports/c_global_state.json`（c_ 前缀命名空间隔离）。

### 禁改边界（A/B 通用）

- **禁止修改**：`contracts/**`、`src/inner/**`、`src/middle/**`
- **禁止漂移**：8 字段输出 schema、reason_code 分层 (INVALID_INPUT / PIPELINE_ERROR / SEM_*)、编排链顺序
- **B 轨报告**：所有字段使用 `b_` 前缀，不覆盖 A 轨历史字段
- **A 回滚锚点**：git tag `outer_A_v1.0.0_frozen`，B 版出现 P0 时切回此 tag

---

## 教练系统落地方案（当前活动）

当前执行计划：`reports/full_implementation_roadmap.md`（完整方案）

### 阶段约束（严格执行）

- **阶段推进必须严格串行**：阶段 N 未完成并经用户确认 GO，不得进入阶段 N+1
- **全量回归**：每个阶段合并前必须 `python -m pytest tests/ -q` 且 698 tests 全部 pass
- **源码边界**：`src/inner/**`、`src/middle/**`、`src/outer/**` 禁止修改；新代码只允许在 `src/coach/`、`src/mapek/`、`src/cohort/`
- **合约冻结规则**：新合约一旦标记为 frozen，后续只能新增字段不可修改已有字段

### 当前阶段

- **活动阶段**: Phase 17 — 知情同意启用 TTM+SDT + A/B 验证
- **已完成阶段**: Phase 0-16 全部 GO ✅
- **全量测试**: 1274 passed

### 三模型启用顺序

Phase 4 的三个行为科学模型默认关闭（`enabled: false`）。推荐按以下顺序逐个启用：

```
TTM（阶段变化理论）→ SDT（自决理论）→ 心流互信息
```

**TTM 先开**：决定对话的大方向（"做什么"）——五阶段检测+策略粗筛，独立运行不依赖其他模型。  
**SDT 再开**：在 TTM 选好 action_type 之后微调风格（"怎么做"）——低自主性→转 reflect，低胜任感→降难度。  
**心流最后开**：在 TTM+SDT 都稳定后精调难度（"多难合适"）——无聊↔焦虑的动态难度调节。

先定方向 → 再调风格 → 最后精调难度，逐层叠加便于定位问题。

### 增量原则

- 每轮只做一个模块（遵循现有单模块开发协议）
- 用户指定本轮阶段 → 用户给出规则参数 → AI 生成代码 → 类型检查 → 测试 → 用户确认锁定
- 当前阶段工作完成前，禁止提前实现后续阶段的模块
