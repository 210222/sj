# Phase 8 — 最终门禁闭环与系统签收

**编制日期**: 2026-05-04
**当前基线**: 1034 tests pass, Phase 1-7 GO
**对齐源**: `contracts/gates.json` (8 门禁定义), `meta_prompts/coach/00_phase8_orchestrator.xml`
**前置**: Phase 7（因果稳健 + 治理闭环）已 GO

---

## 0. 为什么需要 Phase 8

Phase 1-7 实现了完整的 Coach 轨核心能力——CCA-T 教练引擎、行为科学模型、语义安全、MAPE-K 闭环、因果稳健、8 道门禁（4 道 V18.8 + 4 道 V18.7）。但 gates.json 中定义的第 6 道（Audit Gate）和第 8 道（Window Gate）缺少运行时实现——它们的指标字段目前没有数据源。

Phase 8 的任务：补齐 gate 6 和 gate 8 的运行时实现，完成八门禁全链路集成验证，执行最终合约冻结与系统签收。

---

## 1. 最终八门禁全景

| Gate | 名称 | 指标 | 实现来源 | 状态 |
|------|------|------|---------|------|
| 1 | Agency Gate | `premise_rewrite_rate` | `src/coach/agent.py` (Phase 3) | ✅ |
| 2 | Excursion Gate | `effective_exploration_evidence` | `src/coach/agent.py` (Phase 3) | ✅ |
| 3 | Learning Gate | `no_assist_trajectory` | `src/coach/agent.py` (Phase 3) | ✅ |
| 4 | Relational Gate | `compliance_signal_score` | `src/coach/agent.py` (Phase 3) | ✅ |
| 5 | Causal Gate | `causal_diagnostics_triple` | `src/coach/diagnostics.py` (Phase 7) | ✅ |
| **6** | **Audit Gate** | **`audit_health`** | **`src/coach/audit_health.py` (S8.1)** | **⬅ 补齐** |
| 7 | Framing Gate | `independent_framing_audit_pass` | `src/coach/gates_v18_7.py` (Phase 7) | ✅ |
| **8** | **Window Gate** | **`window_schema_version_consistency`** | **`src/coach/window_consistency.py` (S8.2)** | **⬅ 补齐** |

**升档规则**: AND 逻辑 — 全部 8 道门禁通过才允许升档。任一 fail 阻断。

---

## 2. 最终系统数据流（Phase 8 完成后）

```
用户对话
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│         CCA-T 教练引擎 (CoachAgent.act())                      │
│  ├── 意图解析 (Phase 1)                                       │
│  ├── 用户状态追踪 (Phase 2)                                   │
│  ├── 会话记忆 (Phase 2)                                       │
│  ├── TTM 阶段检测 (Phase 4)                                   │
│  ├── SDT 动机评估 (Phase 4)                                   │
│  ├── 心流互信息 (Phase 4)                                     │
│  ├── 主权脉冲 (Phase 3)                                       │
│  ├── 远足权 (Phase 3)                                         │
│  ├── 关系安全层 (Phase 3)                                     │
│  ├── 语义安全三件套 (Phase 5)                                 │
│  ├── MAPE-K 外循环 (Phase 6)                                  │
│  ├── 多智能体分层 (Phase 6)                                   │
│  ├── 向量记忆 (Phase 6)                                       │
│  ├── MRT 微随机实验 (Phase 7)                                 │
│  └── 门禁闭环 (Phase 8) ← 当前                                │
└──────────────────┬───────────────────────────────────────────┘
                   │ DSL action packet
                   ▼
┌──────────────────────────────────────────────────────────────┐
│          8 道门禁升档闸门                                       │
│  1. Agency Gate    (改写率 ≥ 阈值)                             │
│  2. Excursion Gate (有远足证据)                                │
│  3. Learning Gate  (No-Assist 不持续下滑)                      │
│  4. Relational Gate (顺从信号 ≤ 阈值)                          │
│  5. Causal Gate    (三诊断全部通过)                             │
│  6. Audit Gate     (P0=0 且 P1 ≤ 阈值) ← S8.1 补齐            │
│  7. Framing Gate   (选择架构无操纵效应)                         │
│  8. Window Gate    (版本一致性) ← S8.2 补齐                     │
│  规则: AND — 全部通过才允许升档                                 │
└──────────────────┬───────────────────────────────────────────┘
                   │ pass/block
                   ▼
┌──────────────────────────────────────────────────────────────┐
│         治理管线 + Ledger + Audit                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 子阶段分解（严格串行）

### 3.1 S8.1 — 审计分级门禁 (Audit Gate)

**命令**: `/run_coach_s8_1`
**元提示词**: `meta_prompts/coach/81_audit_gate.xml`

#### 问题

gates.json 中 gate 6 的定义：
```json
"6_audit_gate": {
    "metric": "audit_health",
    "rule": "P0=0 且 P1 低于告警阈值"
}
```

但运行时没有一个组件能产出 `audit_health` 指标。已有的审计数据源分散在：
- `src/inner/audit/` — 底层审计模块（冻结，只读）
- `reports/full_scan/` — S10-S90 白金审计报告
- `src/coach/mrt.py` — MRT 实验记录
- `src/coach/diagnostics.py` — 三诊断结果
- `src/coach/gates_v18_7.py` — 门禁结果

需要聚合这些分散的 finding 为一个统一的审计健康评分。

#### 设计

**AuditHealthScorer** — 只读审计评分器，不修改审计流程。

**P0/P1 分级**：
| 级别 | 含义 | 示例 | Gate 影响 |
|------|------|------|----------|
| P0 | 阻断性缺陷 | 安全违规、数据丢失、合约违反 | 直接阻断 |
| P1 | 非阻断告警 | 性能退化、覆盖不足、配置偏差 | 超阈值告警 |
| P2/P3 | 信息/建议 | 优化建议 | 不参与 gate |

**评分规则**：
```
P0=0 且 P1=0       → score=1.0 (完美)     → gate_pass=True
P0=0 且 P1≤threshold → score≥0.8 (良好)    → gate_pass=True
P0=0 且 P1>threshold → score=0.3~0.7 (告警) → gate_pass=False
P0>0                → score<0.5 (阻断)     → gate_pass=False
```

**历史趋势**：滑动窗口（默认最近 10 次评分），输出 `improving/declining/stable`。

#### 代码结构

```
src/coach/audit_health.py
├── AuditFinding         — 单条审计发现 dataclass
│   ├── severity (P0/P1/P2/P3)
│   ├── category (security/quality/coverage/drift/contract)
│   ├── detail / source / timestamp
│   ├── is_blocking()   → severity=="P0"
│   └── is_warning()    → severity=="P1"
├── AuditHealthScore     — 审计健康评分 dataclass
│   ├── score / p0_count / p1_count
│   ├── p0_blocking / p1_above_threshold
│   ├── audit_health()  → gate 6 需要的字典 (5字段)
│   └── to_dict()       → JSON 可序列化
└── AuditHealthScorer    — 评分器
    ├── evaluate(findings) → AuditHealthScore
    └── trend()           → 历史趋势字典
```

#### 交付物

| 文件 | 操作 | 估计 |
|------|------|------|
| `src/coach/audit_health.py` | 新建 | ~130 行 |
| `tests/test_s8_audit_health.py` | 新建 | ~80 行 |
| `config/coach_defaults.yaml` | 追加 Phase 8 配置段 | +7 行 |

#### 测试覆盖

| 测试 | 场景 | 预期 |
|------|------|------|
| 无 finding | 完美健康 | score=1.0, gate_pass=True |
| P0 阻断 | 安全违规 | p0_blocking=True, score<0.5, gate_pass=False |
| P1 未超阈值 | 少量告警 | p1_above_threshold=False, score≥0.8 |
| P1 超阈值 | 大量告警 | p1_above_threshold=True, gate_pass=False |
| 混合 P0+P1 | 同时存在阻断和告警 | p0_blocking=True, p1_count 正确 |
| 趋势追踪 | 多次 evaluate | trend() 返回历史评分 |
| 输出格式 | audit_health() | 5 字段齐全 |
| 序列化 | to_dict() | JSON 可序列化 |

---

### 3.2 S8.2 — 窗口一致性门禁 (Window Gate)

**命令**: `/run_coach_s8_2`
**元提示词**: `meta_prompts/coach/82_window_gate.xml`

#### 问题

gates.json 中 gate 8 的定义：
```json
"8_window_gate": {
    "metric": "window_schema_version_consistency",
    "rule": "参与升档计算的所有数据使用同一 window_schema_version"
}
```

运行时数据由多个组件产出——MRT (24h window_id)、DiagnosticEngine (evaluated_at_utc)、GateResult (evaluated_at_utc)——但没有一个组件验证这些数据的版本一致性。

#### 设计

**WindowConsistencyChecker** — 只读一致性检查器，不修改数据，不熔断，不降级。

**三维检查**：
1. **Schema 版本一致性** — 所有组件 `schema_version` 相同（默认 `max_version_drift=0`）
2. **窗口标识一致性** — 所有组件 `window_id` 属于同一时间窗口
3. **数据新鲜度** — 所有数据在 `max_age_seconds` 内（默认 3600s = 1h）

**冷启动策略**：无版本数据时 pass（all_consistent=True, fresh=True）

#### 代码结构

```
src/coach/window_consistency.py
├── ComponentVersion             — 单组件版本 dataclass
│   ├── component (mrt/diagnostics/gates/clock)
│   ├── window_id / schema_version
│   ├── data_timestamp / data_age_seconds
├── WindowConsistencyResult       — 检查结果 dataclass
│   ├── all_consistent / version_count / max_version_drift
│   ├── fresh / max_data_age_seconds / components / detail
│   ├── window_schema_version_consistency() → gate 8 需要的字典 (5字段)
│   └── to_dict() → JSON 可序列化
└── WindowConsistencyChecker      — 检查器
    └── check(versions) → WindowConsistencyResult
```

#### 交付物

| 文件 | 操作 | 估计 |
|------|------|------|
| `src/coach/window_consistency.py` | 新建 | ~130 行 |
| `tests/test_s8_window_consistency.py` | 新建 | ~85 行 |

#### 测试覆盖

| 测试 | 场景 | 预期 |
|------|------|------|
| 全部一致 | 同一版本 + 同窗口 + 新鲜 | gate_pass=True |
| 版本漂移 | schema_version 不同 | all_consistent=False |
| 窗口不一致 | window_id 不同 | all_consistent=False |
| 数据过时 | 超过 1 小时 | fresh=False |
| 无版本数据 | 空列表 | all_consistent=True（冷启动友好）|
| 允许漂移 | max_version_drift=1 | 允许 1 个版本差异 |
| 输出格式 | window_schema_version_consistency() | 5 字段齐全 |
| 序列化 | to_dict() | JSON 可序列化 |

---

### 3.3 S8.3 — 八门禁全链路集成验证

**命令**: `/run_coach_s8_3`
**元提示词**: `meta_prompts/coach/83_full_chain_integration.xml`

#### 目标

创建 `tests/test_s8_full_chain_integration.py`，验证全部 8 道门禁的端到端集成行为。

**关键约束**：S8.3 只新增测试文件，不产生任何 `src/` 代码。

#### 测试场景

**A. 每道门禁独立验证（8 个测试类）**

| Gate | 测试类 | 场景数 |
|------|--------|--------|
| 1. Agency Gate | `TestAgencyGateIntegration` | 3（高/低/边界） |
| 2. Excursion Gate | `TestExcursionGateIntegration` | 2（有/无证据） |
| 3. Learning Gate | `TestLearningGateIntegration` | 2（稳定/下滑） |
| 4. Relational Gate | `TestRelationalGateIntegration` | 2（低/高顺从） |
| 5. Causal Gate | `TestCausalGateIntegration` | 2（全通过/平衡fail） |
| 6. Audit Gate | `TestAuditGateIntegration` | 3（无/P0阻断/P1超阈值） |
| 7. Framing Gate | `TestFramingGateIntegration` | 2（一致/发散） |
| 8. Window Gate | `TestWindowGateIntegration` | 2（一致/漂移） |

**B. 门禁交互验证（`TestMultiGateInteraction`）**

| 场景 | 输入 | 预期 |
|------|------|------|
| 全 pass | 所有 8 门禁 pass | all_pass=True |
| 单 fail | 任意一个 fail | AND 逻辑阻断 → all_pass=False |
| 多 fail | 多个 gate 同时 fail | 互不影响，各自状态独立 |
| 空数据 | 无数据输入 | 优雅处理，不崩溃 |
| 故障恢复 | P0→修复→P0=0 | gate 恢复 pass |

**真实实现引用**（非 mock）：
- Gate 5: `src/coach/diagnostics.py` → DiagnosticEngine
- Gate 6: `src/coach/audit_health.py` → AuditHealthScorer
- Gate 7: `src/coach/gates_v18_7.py` → ManipulationGate
- Gate 8: `src/coach/window_consistency.py` → WindowConsistencyChecker

#### 交付物

| 文件 | 操作 | 估计 |
|------|------|------|
| `tests/test_s8_full_chain_integration.py` | 新建 | ~200 行 |

---

### 3.4 S8.4 — 系统最终冻结与签收

**命令**: `/run_coach_s8_4`
**元提示词**: `meta_prompts/coach/84_final_signoff.xml`

#### 目标

S8.4 不写代码——只做文档、冻结、签收。

#### 步骤 A：合约冻结

`contracts/operations_governance.json` status `draft` → `frozen`：

```json
{
  "contract": "operations_governance",
  "version": "1.0.0",
  "status": "frozen",
  "frozen_constraints": {
    "p1_threshold": "不可删改",
    "max_version_drift": "不可删改"
  },
  "frozen_at": "<current_utc>"
}
```

**11 份合约全部冻结验证**：
| 合约 | 冻结阶段 |
|------|---------|
| ledger.json | 内圈（预冻结） |
| audit.json | 内圈（预冻结） |
| clock.json | 内圈（预冻结） |
| resolver.json | 内圈（预冻结） |
| gates.json | 内圈（预冻结） |
| coach_dsl.json | Phase 1 |
| user_profile.json | Phase 2 |
| ttm_stages.json | Phase 4 |
| mapek_loop.json | Phase 6 |
| causal_governance.json | Phase 7 |
| **operations_governance.json** | **Phase 8 (S8.4)** |

#### 步骤 B：全量回归

```
python -m pytest tests/ -q
```

期望：1034+ 全部 pass。

#### 步骤 C：系统签收报告

生成 `reports/phase8_completion.md`，包含：

1. **系统能力全景图** — 用户对话 → CCA-T → 8 门禁 → 治理管线的完整架构图
2. **交付物清单** — 全部 8 阶段 / 9 个交付物 / 文件路径 / 对应合约
3. **合约冻结审计** — 11 份合约版本、冻结阶段、冻结日期
4. **禁改边界验证** — src/inner/middle/outer 零修改
5. **测试统计** — Phase 0→5 (916) + 6 (59) + 7 (44) + 8 (N) = 总计
6. **已知风险与缓解** — MRT 低流量、三诊断小样本、scipy 依赖、MAPE-K 默认 OFF
7. **运营要点** — 全量回归/白金审计/快审/配置调整/合约只读命令

#### 步骤 D：全局状态更新

`reports/coach_global_state.json`：
- Phase 8 → GO
- 新增 `coach_track_completed: true`
- 新增 `coach_completed_at_utc`

#### 交付物

| 文件 | 操作 |
|------|------|
| `contracts/operations_governance.json` | 新建 + 冻结 |
| `reports/phase8_completion.md` | 新建 |
| `reports/coach_global_state.json` | 更新 |

---

## 4. 合约冻结时间表（最终版）

| 合约 | 冻结阶段 | 说明 |
|------|---------|------|
| `ledger.json` | ✅ 预冻结 | 内圈核心 |
| `audit.json` | ✅ 预冻结 | 内圈核心 |
| `clock.json` | ✅ 预冻结 | 内圈核心 |
| `resolver.json` | ✅ 预冻结 | 内圈核心 |
| `gates.json` | ✅ 预冻结 | 内圈核心 |
| `coach_dsl.json` | ✅ Phase 1 | 教练 DSL 协议 |
| `user_profile.json` | ✅ Phase 2 | 用户模型 |
| `ttm_stages.json` | ✅ Phase 4 | TTM 阶段枚举 |
| `mapek_loop.json` | ✅ Phase 6 | MAPE-K 接口 |
| `causal_governance.json` | ✅ Phase 7 | 因果治理 |
| `operations_governance.json` | ⬅ Phase 8 S8.4 | 运营治理 |

---

## 5. 测试增长趋势

| 阶段 | 新增 | 累计 |
|------|------|------|
| Phase 0 | 714 (基线) | 714 |
| Phase 1 | 62 | 776 |
| Phase 2 | 32 | 808 |
| Phase 3 | 31 | 839 |
| Phase 4 | 42 | 881 |
| Phase 5 | 35 | 916 |
| Phase 6 | 59 | 975 |
| Phase 7 | 59 | 1034 |
| **Phase 8 (S8.1+S8.2+S8.3)** | **~30-40** | **~1064-1074** |

---

## 6. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Audit Gate P0/P1 分类过于简化 | 低 | 中 | 可通过配置调整 p1_threshold |
| Window Gate 版本检查过于严格 | 低 | 中 | max_version_drift 可调，冷启动空数据 pass |
| 全链路测试 mock 不足覆盖边界 | 低 | 低 | 使用真实实现而非 mock |
| 已有 1034 测试回归 | 低 | 高 | S8.1/S8.2 不修改已有代码，只新增 |

---

## 7. 路由命令一览

| 命令 | 子阶段 | 执行内容 |
|------|--------|---------|
| `/run_coach_s8_1` | Audit Gate | 实现 audit_health.py + 测试 |
| `/run_coach_s8_2` | Window Gate | 实现 window_consistency.py + 测试 |
| `/run_coach_s8_3` | Full Chain | 创建八门禁全链路集成测试 |
| `/run_coach_s8_4` | Final Sign-off | 合约冻结 + 签收报告 + 完结 |

**严格串行规则**：上一子阶段非 GO，不得进入下一子阶段。

---

## 8. 成功标准

1. `contracts/operations_governance.json` status=`frozen` + `frozen_at` 非空
2. 11 份合约全部冻结验证通过
3. `src/coach/audit_health.py` 存在：AuditFinding / AuditHealthScore / AuditHealthScorer
4. `src/coach/window_consistency.py` 存在：ComponentVersion / WindowConsistencyResult / WindowConsistencyChecker
5. gate 6 `audit_health` 指标有运行时数据源
6. gate 8 `window_schema_version_consistency` 指标有运行时数据源
7. `tests/test_s8_full_chain_integration.py` 全部 pass
8. 1034 已有测试零回归
9. `reports/coach_global_state.json` Phase 8 → GO
10. `coach_global_state.json` 新增 `coach_track_completed=true` + `coach_completed_at_utc`
11. `reports/phase8_completion.md` 系统签收报告（含全景图/交付物清单/合约审计/测试统计/风险/运营）
12. 不修改任何已有代码或测试文件（只新增）
13. Coach 轨全部 8 阶段完成

---

## 9. 元提示词清单

5 份元提示词文件已就位：

| 文件 | 路径 |
|------|------|
| Phase 8 总控 | `meta_prompts/coach/00_phase8_orchestrator.xml` |
| S8.1 Audit Gate | `meta_prompts/coach/81_audit_gate.xml` |
| S8.2 Window Gate | `meta_prompts/coach/82_window_gate.xml` |
| S8.3 Full Chain | `meta_prompts/coach/83_full_chain_integration.xml` |
| S8.4 Final Sign-off | `meta_prompts/coach/84_final_signoff.xml` |
