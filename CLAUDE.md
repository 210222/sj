# Coherence — V20.0 认知主权保护系统

## 可执行命令

```bash
# 教学体验审计 (3 画像 × 5 轮，LLM 模式需要后端运行)
cd D:/Claudedaoy/coherence && python run_experience_audit.py --quick --use-http

# 仅运行全量测试回归
cd D:/Claudedaoy/coherence && python -m pytest tests/ -q

# 启动后端 (需要 API key)
$env:DEEPSEEK_API_KEY = "sk-xxx"
uvicorn api.main:app --host 0.0.0.0 --port 8001

# 启动前端开发服务器
cd D:/Claudedaoy/coherence/frontend && npm run dev

# 构建 APK (需要 JDK 21+ + Android SDK)
cd D:/Claudedaoy/coherence && build_apk.bat

# 白金级全系统审计 (S00→S90 完整流水线)
cd D:/Claudedaoy/coherence && python run_platinum_audit.py
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
├── CLAUDE.md                    # 本文件
├── contracts/                   # 13 份冻结合约 — 禁改
├── src/
│   ├── inner/                   # ✅ 已冻结 — 基础设施
│   ├── middle/                  # ✅ 已冻结 — 状态估计
│   ├── outer/                   # ✅ 已冻结 — 外圈
│   ├── coach/                   # 教练引擎 — 可写
│   │   ├── agent.py             # CoachAgent 主入口
│   │   ├── composer.py          # Policy Composer
│   │   ├── memory.py            # 会话记忆 (SQLite + FTS5)
│   │   ├── llm/                 # LLM 子模块 (Phase 19+)
│   │   │   ├── client.py        # LLMClient (DeepSeek)
│   │   │   ├── prompts.py       # Stable prefix + 分层 prompt
│   │   │   ├── schemas.py       # LLMResponse + Observability
│   │   │   ├── memory_context.py # Retention bundle
│   │   │   └── config.py        # LLMConfig
│   │   ├── ttm.py / sdt.py / flow.py  # 行为科学模型
│   │   └── ...
│   ├── mapek/                   # MAPE-K 控制循环
│   └── cohort/                  # 量化自我 (占位)
├── api/                         # FastAPI 后端 (Phase 9+)
│   ├── main.py                  # 应用入口 + 前端静态文件
│   ├── routers/                 # chat / dashboard / admin / ...
│   ├── services/                # CoachBridge / DashboardAggregator
│   └── models/                  # Pydantic schemas / WebSocket
├── frontend/                    # React + Vite 前端 (Phase 9+)
│   ├── src/                     # TypeScript 源码
│   ├── dist/                    # 构建产物
│   ├── android/                 # Capacitor Android 项目
│   └── capacitor.config.json   # APK 配置 (后端 URL)
├── tests/                       # 1466 tests
├── config/                      # YAML 配置
├── reports/                     # 审计报告 + 阶段报告
│   ├── experience_audit/        # 体验审计产物
│   │   ├── runs/                # Per-run 证据 (7 类文件)
│   │   ├── llm_baseline_band.json
│   │   ├── llm_prefix_stability_report.json
│   │   ├── regression_alerts.json
│   │   ├── score_trends.json
│   │   └── failure_patterns.json
│   └── phase*_completion.md     # 阶段验收文档
├── meta_prompts/coach/          # XML 元提示词 (Phase 0-40)
├── data/                        # SQLite 运行时数据
├── build_apk.bat                # APK 构建脚本
├── run_experience_audit.py      # 体验审计入口
└── requirements.txt
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
- **API 密钥安全**：`DEEPSEEK_API_KEY` 只在终端 `$env:` 注入，禁止写入任何文件或提交 git。`.gitignore` 已屏蔽 `.claude/settings.local.json`、`*.env`、`*.key`

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

### 当前阶段

- **活动阶段**: Phase 41 — 跨会话学习连续性
- **已完成阶段**: Phase 0-41 全部 GO ✅
- **全量测试**: 1466 passed / 0 failed / 5 skipped
- **教学评分基线**: Overall Mean 15.6（Phase 34.5 基线 14.59），Cache hit rate ~56%

### Phase 35-40 核心交付

| Phase | 名称 | 核心交付 |
|-------|------|----------|
| **35** | Stable Prefix + 上下文重构 | 分层 prompt、retention bundle、sync/stream 主链统一，实测 55.9% cache hit |
| **35.1** | 质量调优 | Terminal checklist、scaffold context 减重 — 修复稳定性/推进感回归 |
| **36** | Context Caching 实证化 | 34 字段 observability、cache eligibility 证据链、prefix stability 报告 |
| **37** | 观测与审计补齐 | cost_usd 真实定价、SQLite 持久化 90 天清理、评分趋势、回归告警 |
| **38** | 教学策略 A/B 测试框架 | MRT outcome 采集、strategy 变体、BayesianEstimator 真实数据消费 |
| **39** | 全量稳定性收口 | API 路由修复、测试断言对齐、全量回归 0 failed |
| **40** | 策略自评与自适应 | get_strategy_quality() → _apply_mrt_preference()：MRT 回灌 composer |
| **41** | 跨会话学习连续性 | _restore_persisted_state() → 同一 session_id 回来恢复 TTM/SDT/BKT |

### 跨会话连续性

同一 `session_id` 回来时：
- `_restore_persisted_state()` 从 `SessionPersistence` 恢复 TTM 阶段、SDT 三轴、BKT 掌握度
- `_is_returning_user` 标记老用户，`_build_context_summary()` 注入"上次学习回顾"块
- 新用户（`total_turns == 0`）不受影响，恢复失败不阻塞主流程

### 策略自适应回路

```
MRT assign → record_outcome() → aggregate_outcomes() → Bayesian
                               ↓
get_strategy_quality() → _apply_mrt_preference() → composer
```
偏好仅在数据充足（≥5 样本）且差距显著（≥10%）时生效，不覆盖 pulse/precedent/counterfactual。

### 可观测性体系

- **34 运行时字段**：cache (11) + runtime (15, 含 cost_usd) + retention (8)
- **API 面**：`llm_observability` 同步在 HTTP response 和 WS stream_end
- **运维面**：dashboard/user、admin/llm/runtime、admin/llm/history
- **审计面**：每次 audit 自动产出 7 evidence 文件 + MRT 变体对比报告

### 阶段约束

- 全量回归：每个阶段合并前必须 `python -m pytest tests/ -q` 通过
- 源码边界：`src/inner/**`、`src/middle/**`、`src/outer/**` 禁止修改
- 合约冻结规则：`contracts/` 中 frozen 合约只能新增字段不可修改已有字段

### 三模型启用顺序

```
TTM → SDT → 心流
```
默认关闭（`enabled: false`），先定方向 → 再调风格 → 最后精调难度。
