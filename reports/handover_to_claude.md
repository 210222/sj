# Coherence 项目 — Claude 交接档案

**编制日期**: 2026-05-04
**项目性质**: 自适应AI教练系统 (认知主权保护系统 V18.8.3)
**技术栈**: Python 3.10+, SQLite, pytest, mypy

---

## 1. 你的职责

你是 Coherence 项目的 AI 实现者。用户是规则制定者和验收者——用户不写代码，只看 diff 摘要、测试通过/失败、是否符合合约定义。

你的核心工作模式：
1. 用户指定阶段 → 你读取元提示词 (meta_prompts/) 和合约 (contracts/)
2. 生成代码 + 测试 → 运行回归 → 展示结果
3. 用户确认 → 冻结合约 → 进入下一阶段

---

## 2. 项目当前状态 — 全部 3 轨完成

```
A轨 (外圈A版): 已冻结 git tag outer_A_v1.0.0_frozen
B轨 (外圈B版): B1→B8 全部 GO, 最终决策 GO
C轨 (持续运营): C1→C6 全部 GO, 最终决策 GO
Coach轨:        Phase 0→8 全部 GO, 1070 tests, 11 份冻结合约
```

**当前阶段**: **全部完成**。11 份合约全部冻结，1070 tests 全部 pass，系统已签收。

---

## 3. 项目结构

```
D:\Claudedaoy\coherence\
├── CLAUDE.md                      # 项目指令（新Claude先读此文件）
├── run_platinum_audit.py          # 白金审计启动脚本
├── platinum_full_audit.py         # 全量白金审计
├── full_scan.py                   # 全量扫描
│
├── contracts/                     # ★ 11 份冻结合约（只读！）
│   ├── ledger.json                # 内圈冻结
│   ├── audit.json                 # 内圈冻结
│   ├── clock.json                 # 内圈冻结
│   ├── resolver.json              # 内圈冻结
│   ├── gates.json                 # 内圈冻结 — 8 门禁定义
│   ├── coach_dsl.json             # Phase 1 冻结 — DSL 协议
│   ├── user_profile.json          # Phase 2 冻结 — 用户模型
│   ├── ttm_stages.json            # Phase 4 冻结 — TTM 阶段
│   ├── mapek_loop.json            # Phase 6 冻结 — MAPE-K 接口
│   ├── causal_governance.json     # Phase 7 冻结 — 因果治理
│   └── operations_governance.json # Phase 8 冻结 — 运营治理
│
├── src/
│   ├── inner/                     # ✅ 冻结 禁改
│   │   ├── ledger/                # 事件账本
│   │   ├── audit/                 # 审计分类器
│   │   ├── clock/                 # 时间窗口
│   │   ├── resolver/              # 冲突仲裁
│   │   ├── no_assist/             # 无辅助评估
│   │   └── gates/                 # GateEngine
│   ├── middle/                    # ✅ 冻结 禁改
│   │   ├── state_l0/             # L0状态估计
│   │   ├── state_l1/             # L1扰动检测
│   │   ├── state_l2/             # L2可行性判定
│   │   ├── decision/             # 决策层
│   │   ├── semantic_safety/      # 语义安全引擎
│   │   └── shared/               # 共享配置
│   ├── outer/                    # ✅ 冻结 禁改
│   │   ├── api/                  # 服务入口
│   │   ├── orchestration/        # 管线编排 pipeline.py
│   │   ├── presentation/         # 格式化
│   │   └── safeguards/           # 安全策略
│   ├── coach/                    # ★ 教练引擎（全部冻结）
│   │   ├── agent.py              # CoachAgent 主类 (36KB)
│   │   ├── dsl.py                # DSL 构建/校验
│   │   ├── composer.py           # Policy Composer
│   │   ├── state.py              # 用户状态追踪
│   │   ├── memory.py             # 轻量会话记忆
│   │   ├── data.py               # 数据模型
│   │   ├── ttm.py                # TTM 五阶段状态机
│   │   ├── sdt.py                # SDT 动机评估
│   │   ├── flow.py               # 心流互信息
│   │   ├── counterfactual.py     # 反事实仿真
│   │   ├── cross_track.py        # 跨轨一致性检查
│   │   ├── precedent_intercept.py # 先例拦截
│   │   ├── mrt.py                # MRT 微随机实验
│   │   ├── diagnostics.py        # 三诊断
│   │   ├── gates_v18_7.py        # V18.7 四门禁
│   │   ├── handlers.py           # 专项处理器
│   │   ├── audit_health.py       # ★ S8.1 Audit Gate
│   │   └── window_consistency.py # ★ S8.2 Window Gate
│   ├── mapek/                    # ★ MAPE-K 控制循环
│   │   ├── monitor.py / analyze.py / plan.py / execute.py / knowledge.py
│   └── cohort/                   # ★ 量化自我接口占位
│       └── collector.py
│
├── tests/                        # ★ 1070 个测试
│   ├── test_s8_audit_health.py   # S8.1 (10 tests)
│   ├── test_s8_window_consistency.py # S8.2 (8 tests)
│   ├── test_s8_full_chain_integration.py # S8.3 (18 tests)
│   ├── test_s7_mrt.py / _diagnostics.py / _gates.py  # Phase 7
│   └── ... (共 53 个测试文件)
│
├── config/
│   ├── parameters.yaml           # 系统参数
│   ├── coach_defaults.yaml       # 教练引擎参数（含 Phase 8 配置段）
│   ├── change_policy.yaml        # B轨变更策略
│   └── release_train.yaml        # C轨发布列车
│
├── meta_prompts/                 # ★ 系统提示词库（Claude 的执行指南）
│   ├── coach/                    # 55 个文件 — Coach 轨全部元提示词
│   │   ├── 00_phase0~8_orchestrator.xml  # 9 个阶段总控
│   │   ├── 11~14_*.xml          # Phase 1 子阶段
│   │   ├── 21~25_*.xml          # Phase 2 子阶段
│   │   ├── 31~35_*.xml          # Phase 3 子阶段
│   │   ├── 41~45_*.xml          # Phase 4 子阶段
│   │   ├── 51~55_*.xml          # Phase 5 子阶段
│   │   ├── 61~67_*.xml          # Phase 6 子阶段
│   │   ├── 71~74_*.xml          # Phase 7 子阶段
│   │   └── 81~84_*.xml          # Phase 8 子阶段
│   ├── b/                        # B轨元提示词 (8 文件)
│   ├── c/                        # C轨元提示词 (7 文件)
│   └── outer/                    # A轨外圈 (4 文件)
│
├── reports/
│   ├── coach_global_state.json   # Coach轨全局状态
│   ├── b_global_state.json       # B轨全局状态
│   ├── c_global_state.json       # C轨全局状态
│   ├── full_implementation_roadmap.md  # 完整落地方案（原始7阶段）
│   ├── phase8_implementation_plan.md   # Phase 8 落地方案
│   ├── phase8_completion.md      # 系统签收报告
│   └── full_scan/               # 白金审计报告
│
└── memory (自动记忆): C:\Users\21022\.claude\projects\D--Claudedaoy-coherence\memory\
```

---

## 4. Coach 轨 — 全部 8 阶段完成明细

| Phase | 名称 | 测试 | 核心交付物 | 冻结合约 |
|-------|------|------|-----------|---------|
| 0 | 接线 | 714 | pipeline 接入 Ledger/Audit/Gates | — |
| 1 | CCA-T 教练引擎 | +62=776 | agent.py / dsl.py / composer.py / state.py | coach_dsl.json |
| 2 | 记忆与用户模型 | +32=808 | memory.py / data.py / qs_collector.py | user_profile.json |
| 3 | V18.8 运行时 | +31=839 | 主权脉冲/远足/双账本/关系安全 | — |
| 4 | 行为科学模型 | +42=881 | ttm.py / sdt.py / flow.py | ttm_stages.json |
| 5 | 语义安全三件套 | +35=916 | counterfactual.py / cross_track.py / precedent_intercept.py | — |
| 6 | MAPE-K + 多智能体 | +59=975 | mapek/ 5组件 / handlers.py / memory升级 | mapek_loop.json |
| 7 | 因果稳健 + 治理 | +59=1034 | mrt.py / diagnostics.py / gates_v18_7.py | causal_governance.json |
| **8** | **门禁闭环 + 签收** | **+36=1070** | **audit_health.py / window_consistency.py** | **operations_governance.json** |

---

## 5. 六种门禁系统

### 5.1 八门禁升档闸门（Coach 轨）

全部 8 道门禁通过才允许升档（AND 逻辑）：

| Gate | 名称 | 指标 | 实现文件 | 实现阶段 |
|------|------|------|---------|---------|
| 1 | Agency Gate | premise_rewrite_rate ≥ 阈值 | src/inner/gates/ | Phase 3 |
| 2 | Excursion Gate | 有有效探索证据 | src/inner/gates/ | Phase 3 |
| 3 | Learning Gate | No-Assist 不持续下滑 | src/inner/gates/ | Phase 3 |
| 4 | Relational Gate | 顺从信号 ≤ 阈值 | src/inner/gates/ | Phase 3 |
| 5 | Causal Gate | 三诊断全部通过 | src/coach/diagnostics.py | Phase 7 |
| **6** | **Audit Gate** | **P0=0 且 P1≤阈值** | **src/coach/audit_health.py** | **Phase 8** |
| 7 | Framing Gate | 选择架构无操纵效应 | src/coach/gates_v18_7.py | Phase 7 |
| **8** | **Window Gate** | **版本一致+数据新鲜** | **src/coach/window_consistency.py** | **Phase 8** |

### 5.2 V18.7 四门禁（Phase 7）

| 门禁 | 实现 | 数据源 |
|------|------|--------|
| Verification Load Gate | 用户验证时间 ≤ 自主产出时间 | CoachAgent 计时 |
| Serendipity Gate | 偶发探索占比达标 | excursion 记录 |
| Trespassing Gate | 越权熔断器零泄漏 | 语义安全审计 |
| Manipulation Gate | 选择架构无显著操纵效应 | scipy chi2 (可选依赖) |

**关键**: ManipulationGate 使用 `from scipy.stats import chi2_contingency`，ImportError 时优雅 pass。

---

## 6. 三轨调度系统

### 切换命令

A轨（外圈A版）:
```
/run_node_1 → 产品角色 (meta_prompts/outer/01_product_outer.xml)
/run_node_2 → 架构角色 (meta_prompts/outer/02_architect_outer.xml)
/run_node_3 → QA 角色   (meta_prompts/outer/03_qa_outer.xml)
/run_node_4 → DevOps 角色 (meta_prompts/outer/04_devops_outer.xml)
```

B轨（外圈B版受控演进）:
```
/run_b_stage_1 → B1 范围锁定  → ... → /run_b_stage_8 → B8 运营冻结
严格串行: 上一阶段非 GO 不得进入下一阶段
状态文件: reports/b_global_state.json
```

C轨（持续运营与演进治理）:
```
/run_c_stage_1 → C1 基线封版 → ... → /run_c_stage_6 → C6 季度签收
严格串行
状态文件: reports/c_global_state.json
```

Coach轨:
```
/run_coach_s8_1 → S8.1 Audit Gate
/run_coach_s8_2 → S8.2 Window Gate  
/run_coach_s8_3 → S8.3 Full Chain Integration
/run_coach_s8_4 → S8.4 Final Sign-off
```

---

## 7. 关键架构决策

### 组件默认 OFF 策略
所有 Coach 轨组件默认 `enabled: false`，用户按需启用。零行为漂移：
- Phase 3 (主权脉冲/远足/双账本): OFF 默认
- Phase 4 (TTM/SDT/心流): OFF 默认
- Phase 5 (语义安全): OFF 默认
- Phase 6 (MAPE-K): OFF 默认
- Phase 8 (Audit/Window Gate): OFF 默认

### MRT 微随机实验
- 24h 窗口, 20% 变体概率, Beta-Bernoulli 贝叶斯估计
- `src/coach/mrt.py` → `MRTExperiment.assign()` + `BayesianEstimator`

### 三诊断 (Causal Gate)
- Balance Check: SMD + epsilon 零方差防护
- Negative Control: 蒙特卡洛 P(治疗>对照)
- Placebo Window: 真实干预前窗口不应有效果

### 合约冻结规则
- 一旦 status=frozen，只读——后续只能新增字段，不可修改已有字段
- 不可删改参数在 frozen_constraints 中标注

---

## 8. 重要约定和陷阱

### 禁改边界
```
src/inner/**   —  绝对禁止修改 (✅ 全部冻结)
src/middle/**  —  绝对禁止修改 (✅ 全部冻结)
src/outer/**   —  绝对禁止修改 (✅ 全部冻结)
contracts/     —  已有合约禁止修改，只可新增
tests/         —  只新增，不修改已有测试文件
```

### 已知遗留问题
1. `src/inner/ledger/db.py` — Phase 0 做过连接泄漏修复（导致 S80 白金审计 FAIL）
2. `assert` 在测试代码中使用 — 被 S10 标记为 P2（-O 标志禁用 assert，但测试代码影响有限）
3. 巴士因子 = 1 — 单人项目固有
4. FTS5 中文分词精度有限 — LIKE fallback 已覆盖

### 关键参数位置
| 参数 | 位置 |
|------|------|
| MRT enabled/variant_rate/window_hours | `config/coach_defaults.yaml` |
| Audit Gate p1_threshold/trend_window | `config/coach_defaults.yaml` + `contracts/operations_governance.json` |
| Window Gate max_version_drift/max_age | `config/coach_defaults.yaml` + `contracts/operations_governance.json` |
| 三诊断 epsilon | `src/coach/diagnostics.py` BalanceCheck 内联 |
| 8 门禁阈值 | `contracts/gates.json` |

---

## 9. 可执行命令

```bash
# 全量回归测试
python -m pytest tests/ -q

# 仅跑 Phase 8 测试
python -m pytest tests/test_s8_*.py -v

# 白金审计 (完整)
python run_platinum_audit.py

# 白金审计 (快速模式)
python run_platinum_audit.py --quick

# 查看最终审计报告
start reports/full_scan/99_final_report.md
```

---

## 10. 下一步可能的方向

Phase 8 完成后，系统已具备完整能力。后续可能的演进方向：

1. **生产部署** — Docker 化、CI/CD、API 网关
2. **量化自我对接** — `src/cohort/collector.py` 接口已有占位，可对接 Apple Health / Fitbit
3. **MRT 实验分析** — 运行真实 MRT 实验并分析因果效应
4. **三模型启用调优** — 按 TTM→SDT→心流顺序逐个启用并验证
5. **白金审计流水线加固** — 修复 S80 对 db.py 的误报
6. **多用户支持** — 当前为单用户系统
7. **前端界面** — 当前为 API/CLI 界面

---

## 11. 快速验证

接档后先确认系统正常：
```bash
# 1. 全量回归
python -m pytest tests/ -q
# 期望: 1070 passed

# 2. 读取 coach_global_state.json 确认 Phase 8=GO
cat reports/coach_global_state.json

# 3. 确认 11 份合约全部 frozen
ls contracts/*.json
```
