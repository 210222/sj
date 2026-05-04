# Phase 6 完整落地计划 — MAPE-K 闭环 + 向量记忆 + 多智能体分层

**编制日期**: 2026-05-03
**对齐源**: `ai教练.txt` V18.7 多智能体架构 + `自适应AI伴学.txt` MAPE-K/Letta 记忆
**前提**: Phase 5 已 GO ✅ (916 tests pass)
**预计工期**: 7 个子阶段，约 5-7 天

---

## 0. 执行摘要

Phase 6 是 Coherence 教练系统从"单智能体"升级为"多智能体分层 + 完整控制循环"的关键转型。

| 维度 | 当前 (Phase 5) | 目标 (Phase 6) |
|------|---------------|----------------|
| 架构 | CoachAgent 单类决策 | CEO → Manager → Specialist 三层分层 |
| 控制循环 | 无闭环（每次 act 独立） | MAPE-K 五步闭环（Monitor→Analyze→Plan→Execute→Knowledge） |
| 记忆 | 轻量 SQLite facts + session_memory | ArchivalMemory（FTS5 语义搜索）+ WorkingMemory + RMM |
| 合约 | coach_dsl / ttm_stages / user_profile | 新增 mapek_loop.json 冻结 |

---

## 1. 子阶段划分 (S6.1 → S6.7)

### S6.1: MAPE-K 合约冻结 (0.5 天)

新建 `contracts/mapek_loop.json`，定义 MAPE-K 五组件的接口合约、知识库 schema、循环定时参数。

**产出**:
- `contracts/mapek_loop.json` — 冻结后只读

### S6.2: Monitor + Analyze 组件 (1 天)

| 文件 | 类 | 职责 |
|------|---|------|
| `src/mapek/__init__.py` | — | 包导出 |
| `src/mapek/monitor.py` | `Monitor` | 感知层：收集用户输入信号、DSL 反馈、外部传感器数据，缓冲后送 Analyze |
| `src/mapek/analyze.py` | `Analyze` | 分析层：对 Monitor 输出做深层诊断（趋势检测、异常识别、因果推断信号提取） |

**测试**: `tests/test_mapek_monitor_analyze.py` (~60 行, 10 个测试)

### S6.3: Plan + Execute 组件 (1 天)

| 文件 | 类 | 职责 |
|------|---|------|
| `src/mapek/plan.py` | `Plan` | 规划层：基于 Analyze 输出生成下一阶段策略组合，含资源分配和冲突消解 |
| `src/mapek/execute.py` | `Execute` | 执行层：分发 DSL 动作包、调用外部 API、写入 ledger、触发审计 |

**测试**: `tests/test_mapek_plan_execute.py` (~60 行, 10 个测试)

### S6.4: Knowledge 仓库 (1 天)

| 文件 | 类 | 职责 |
|------|---|------|
| `src/mapek/knowledge.py` | `Knowledge` | 知识仓库：Facts CRUD、策略历史记录、实验证据存储、置信度更新 |

- 基于现有 `data.py` facts 表 schema，扩展为 Knowledge 类封装
- 支持证据追加、置信度衰减、生命周期管理

**测试**: `tests/test_mapek_knowledge.py` (~50 行, 8 个测试)

### S6.5: 向量记忆升级 (1.5 天)

修改 `src/coach/memory.py`，新增三类记忆架构：

| 组件 | 类 | 存储 | 能力 |
|------|---|------|------|
| ArchivalMemory | `ArchivalMemory` | SQLite FTS5 虚拟表 + json1 | 语义搜索（MATCH 查询）、事实归档、过期回收 |
| WorkingMemory | `WorkingMemory` | session_memory 表 | 当前会话上下文缓存、优先级管理 |
| RMM | `ReflectiveMemoryManager` | 后台函数 | 定期置信度衰减、生命周期状态转移 (active→frozen→archived)、低置信度证据清理 |

参考: [letta-ai/letta](https://github.com/letta-ai/letta) memory.py 和 archival.py 的接口设计思路。

**测试**: `tests/test_vector_memory.py` (~120 行, 15 个测试)

### S6.6: 多智能体分层 (1 天)

将 CoachAgent 重构为三层次架构：

```
CoachAgent (CEO 层)                          ← 宏观阶段判断 + TTM 阶段切换 + 长期目标分解
    │ PolicyComposer (Manager 层)            ← DSL 动作选择 + 资源调配 + 进度追踪
    ├── ProbeHandler      (专员层)           ← 管理"探查"类型动作
    ├── ChallengeHandler  (专员层)           ← 管理"挑战任务"类型动作
    ├── ReflectHandler    (专员层)           ← 管理"反思对话"类型动作
    └── ScaffoldHandler   (专员层)           ← 管理"脚手架"类型动作
```

| 文件 | 改动 |
|------|------|
| `src/coach/agent.py` | CoachAgent 升级：act() 中增加 CEO 层判断逻辑，将 DSL 构建委托给 Manager 层 |
| `src/coach/composer.py` | PolicyComposer 升级为 Manager：路由到正确 Handler + MAPE-K 循环触发 |
| `src/coach/handlers.py` | 新建：四个 Handler 类，每个封装一个 action_type 的完整执行逻辑 |

**测试**: `tests/test_multi_agent_layering.py` (~80 行, 12 个测试)

### S6.7: Phase 6 冻结 + 全量回归 (1 天)

| 操作 | 详情 |
|------|------|
| 合约冻结 | `contracts/mapek_loop.json` 标记 frozen，禁止修改 |
| 全量回归 | `python -m pytest tests/ -q` — 916+ 测试全 pass |
| Config 冻结 | `config/coach_defaults.yaml` Phase 6 配置段标记 `frozen: true` |
| 状态更新 | `reports/coach_global_state.json` Phase 6 → GO |
| 完结报告 | 输出 Phase 6 交付清单 + 证据包 |

---

## 2. 合约设计: mapek_loop.json

```json
{
  "contract": "mapek_loop",
  "version": "1.0.0",
  "status": "draft",
  "components": {
    "monitor": {
      "inputs": ["user_input", "dsl_feedback", "external_signals"],
      "output": "monitor_snapshot",
      "buffer_size": 100,
      "dedup_window_s": 5
    },
    "analyze": {
      "inputs": ["monitor_snapshot"],
      "output": "analysis_report",
      "methods": ["trend_detection", "anomaly_detection", "causal_signal"],
      "min_confidence": 0.3
    },
    "plan": {
      "inputs": ["analysis_report", "current_strategy"],
      "output": "plan",
      "methods": ["strategy_generation", "resource_allocation", "conflict_resolution"],
      "max_horizon_steps": 5
    },
    "execute": {
      "inputs": ["plan"],
      "output": "execution_result",
      "targets": ["CoachAgent", "Ledger", "Audit", "ExternalAPI"],
      "max_retries": 2
    },
    "knowledge": {
      "stores": ["facts", "strategy_history", "experiment_evidence"],
      "query_methods": ["exact_match", "semantic_search", "temporal_range"],
      "confidence_decay_rate": 0.05,
      "archival_after_days": 30
    }
  },
  "loop_timing": {
    "min_interval_ms": 100,
    "max_interval_ms": 5000,
    "adaptive": true,
    "backpressure_threshold": 0.8
  }
}
```

---

## 3. 完整文件清单

| 操作 | 文件 | 子阶段 |
|------|------|--------|
| **新建** | `contracts/mapek_loop.json` | S6.1 |
| **新建** | `src/mapek/__init__.py` | S6.2 |
| **新建** | `src/mapek/monitor.py` | S6.2 |
| **新建** | `src/mapek/analyze.py` | S6.2 |
| **新建** | `src/mapek/plan.py` | S6.3 |
| **新建** | `src/mapek/execute.py` | S6.3 |
| **新建** | `src/mapek/knowledge.py` | S6.4 |
| **修改** | `src/coach/memory.py` (ArchivalMemory + WorkingMemory + RMM) | S6.5 |
| **修改** | `src/coach/agent.py` (CEO 层升级) | S6.6 |
| **修改** | `src/coach/composer.py` (Manager 层升级) | S6.6 |
| **新建** | `src/coach/handlers.py` (4 个 Handler) | S6.6 |
| **新建** | `tests/test_mapek_monitor_analyze.py` | S6.2 |
| **新建** | `tests/test_mapek_plan_execute.py` | S6.3 |
| **新建** | `tests/test_mapek_knowledge.py` | S6.4 |
| **新建** | `tests/test_vector_memory.py` | S6.5 |
| **新建** | `tests/test_multi_agent_layering.py` | S6.6 |
| **修改** | `config/coach_defaults.yaml` (Phase 6 配置段) | S6.1 |
| **修改** | `reports/coach_global_state.json` | S6.7 |

---

## 4. 集成点

### 4.1 CoachAgent ↔ MAPE-K 集成

```
CoachAgent.act() 入口
    ↓
Monitor.ingest(user_input, context)        ← S6.2: 感知输入
    ↓
Analyze.diagnose(monitor_snapshot)          ← S6.2: 深层诊断
    ↓
Plan.generate(analysis_report)              ← S6.3: 生成策略
    ↓
PolicyComposer.compose(plan)                ← 现有: DSL 动作选择
    ↓  (Phase 5 三件套闸门)
Execute.dispatch(dsl_packet)                ← S6.3: 分发执行
    ↓
Knowledge.record(execution_result)          ← S6.4: 记录证据
    ↓
Memory.archival.store(dsl_packet)           ← S6.5: 归档记忆
```

### 4.2 多智能体调用链

```
CoachAgent.act() [CEO]
  → 读取 TTM 当前阶段 + 用户状态
  → 判断宏观策略（维持/推进/回退/切换阶段）
  → 传递策略意图给 PolicyComposer

PolicyComposer.compose() [Manager]
  → 接收 CEO 策略意图 + Analyze 报告
  → 选择 action_type + 填充 payload
  → 检查 Domain Passport → 跨域需缴纳迁移税
  → 路由到对应 Handler

Handler.handle() [Specialist]
  → ProbeHandler: 生成 probing prompt, 设置难度
  → ChallengeHandler: 构建任务 objective, 设定评分标准
  → ReflectHandler: 构建反思问题链
  → ScaffoldHandler: 生成 step-by-step 支架
  → 返回完整 DSL 动作包
```

### 4.3 Vector Memory 集成

```
CoachAgent.act() 中:
  → WorkingMemory.store(当前输入 + context)   ← 每次对话写入
  → ArchivalMemory.search(query)              ← 检索相关历史事实
  → RMM.consolidate()                         ← 每 N 轮触发一次后台整理
```

---

## 5. 测试策略

| 测试文件 | 覆盖 | 测试数 |
|----------|------|--------|
| `tests/test_mapek_monitor_analyze.py` | Monitor 信号收集/去重 + Analyze 趋势/异常检测 | ~10 |
| `tests/test_mapek_plan_execute.py` | Plan 策略生成 + Execute 分发/重试 | ~10 |
| `tests/test_mapek_knowledge.py` | Facts CRUD + 置信度衰减 + 生命周期 | ~8 |
| `tests/test_vector_memory.py` | Archival FTS5 搜索 + WorkingMemory 缓存 + RMM 整理 | ~15 |
| `tests/test_multi_agent_layering.py` | Handler 路由 + CEO 判断 + Manager 委托 | ~12 |
| **全量回归** | 916+ 已有 tests 全部 pass | — |

---

## 6. 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| MAPE-K 循环增加 CoachAgent.act() 延迟 | 中 | 中 | 异步 Monitor + 超时熔断，回退直通模式 |
| Vector Memory FTS5 查询在高频对话下性能下降 | 低 | 低 | SQLite FTS5 索引优化，限制每次 MATCH 结果数 |
| 多智能体分层引入不必要的复杂度 | 中 | 低 | Handler 是轻量类（不跨进程），可降级为直通调用 |
| ArchivalMemory 过期回收误删有用事实 | 低 | 中 | 回收前写日志 + 软删除（lifecycle_status=archived 而非物理删除） |
| 916 已有测试回归 | 低 | 高 | 每子阶段结束时执行 pytest -q，失败立即修复 |

---

## 7. 成功标准

Phase 6 结束时：

1. `contracts/mapek_loop.json` 已冻结（frozen 标记 + 版本 1.0.0）
2. `src/mapek/` 包 5 个文件全部存在：monitor.py / analyze.py / plan.py / execute.py / knowledge.py
3. `src/coach/memory.py` 新增三类记忆：ArchivalMemory / WorkingMemory / ReflectiveMemoryManager
4. `src/coach/handlers.py` 存在 4 个 Handler 类
5. CoachAgent (CEO) → PolicyComposer (Manager) → Handler (Specialist) 三层路由可用
6. MAPE-K 五步闭环集成到 CoachAgent.act() 流中
7. 新增测试 55+ 全部 pass
8. 916+ 已有测试零回归
9. `reports/coach_global_state.json` Phase 6 → GO
