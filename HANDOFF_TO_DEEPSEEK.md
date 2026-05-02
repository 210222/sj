# Coherence V18.8.3 — 内圈闭环交接文档

**目标读者：下一个 AI 代理（DeepSeek / Claude Code / 等）**
**生成时间：2026-04-29**
**当前阶段：中圈完成，准备外圈 (2026-04-30 更新)**

---

## 1. 项目概况

**项目名称：** Coherence — 认知主权保护系统 V18.8.3
**根目录：** `D:/Claudedaoy/coherence`
**技术栈：** Python 3.10+ / SQLite / pytest / 纯标准库（无外部依赖）
**用户角色：** 规则制定者与验收者（不写代码）
**你的角色：** 实现代理（编写代码 + 运行测试 + 合约审计 + GO/NO-GO 报告）

---

## 2. 架构概述（三层）

```
采集层 → 三层图谱(Content/Entity/Fact) → 状态估计层(HBSSM) → 双轨决策(LRM+稳健轨)
→ 语义安全层 → 元认知与关系安全门控 → 低摩擦交付(Flow/Checkpoint)
→ 双账本评估(Performance/Learning) → 证据账本 + 可验证声明
```

当前完成的是**内圈**（基础设施层），中圈和外圈尚未开始。

---

## 3. 内圈完成状态（6 模块，全部锁定）

### 模块清单

| Step | 模块 | 路径 | 测试数 | 核心职责 |
|------|------|------|--------|---------|
| 1 | Evidence Ledger | `src/inner/ledger/` | 22 | append-only 事件存储 + SHA-256 哈希链 + 并发安全(BEGIN IMMEDIATE+重试) |
| 2 | P0/P1 Audit | `src/inner/audit/` | 33 | P0 缺失阻断 / P1 窗口缺失率(1%告警/3%冻结) / 审计报告(9字段) |
| 3 | Clock & Window | `src/inner/clock/` | 36 | UTC 统一解析 / 30min 前闭后开窗口 / D+N 偏移(24h/168h) / 双周窗口 / 一致性校验 |
| 4 | L3 Resolver | `src/inner/resolver/` | 26 | 三因子冲突分数 / low/mid/high 三级仲裁 / dominant_layer / conservative_hold |
| 5 | No-Assist | `src/inner/no_assist/` | 25 | 独立作答评估 / 文本质量+推理痕迹+reference 重叠 / assist_used 上限 cap |
| 6 | Eight Gates | `src/inner/gates/` | 82 | 八道门禁逐门评估 / AND 聚合 / GO/WARN/FREEZE 决策 |

### 测试汇总

```
669 passed / 0 failed / 0 skipped (2026-04-30 更新)
内圈:
  ledger:      22
  audit:       33
  clock:       36
  resolver:    26
  no_assist:   25
  gates:       82
中圈:
  M1 shared:   84
  M2 state_l0: 65
  M3 state_l1: 66
  M4 state_l2: 59
  M5 decision: 56
  M6 safety:   56
深测:         59
```

### 并发安全

Ledger 的 `append_event` 使用 `BEGIN IMMEDIATE` + 指数退避重试(最多3次, 50/100/200ms) + `UNIQUE(chain_height)` 约束。4 线程 80 条并发写入后 `verify_chain_integrity()` 始终返回 `True`。

---

## 4. 冻结合约（严禁修改）

| 文件 | 版本 | 内容 |
|------|------|------|
| `contracts/ledger.json` | 1.0.0 | events 表 23 字段定义、P0/P1 分类、哈希链规则 |
| `contracts/audit.json` | 1.0.0 | P0 阻断/P1 阈值(1%/3%)、audit_result 9 字段 |
| `contracts/clock.json` | 1.0.0 | UTC/30min 窗口/D+N/window_id 格式 |
| `contracts/resolver.json` | 1.0.0 | 三级冲突(0.3/0.7)、dominant_layer 枚举、intervention_intensity 枚举 |
| `contracts/gates.json` | 1.0.0 | 八门禁 AND 逻辑、gate_result_schema |

---

## 5. 内圈模块间依赖（只读方向）

```
clock ─────────────> ledger ──────────────> audit
  │                    │                      │
  │                    └──────┐               │
  │                           │               │
  └──> resolver ──────────────┴──> gates <────┘
         │                           │
         └──> no_assist ─────────────┘
```

- **clock** 是纯工具层，被 ledger/no_assist/gates 消费
- **ledger** 提供事件存储，被 audit/resolver/no_assist/gates 间接使用
- **audit** 从 ledger 读取事件做 P0/P1 检查
- **resolver/no_assist/gates** 各自独立产出评估结果，通过 `to_audit_fields()` 映射到 P1 字段

---

## 6. 关键设计决策

1. **SQLite 单文件 + append-only 触发器** → 零运维，个人本地运行
2. **所有时间统一 UTC + Z 后缀** → clock 模块统一入口，禁止本地时区
3. **合约冻结 > 实现便利** → contracts/ 文件只读，实现必须对齐
4. **参数配置化** → 每个模块有 `config.py`，阈值/权重/版本号集中管理
5. **BEGIN IMMEDIATE 写事务** → 并发安全的哈希链追加
6. **规则法优先** → resolver/no_assist/gates 使用规则法，不引入 ML 依赖
7. **to_audit_fields() 统一接口** → 各模块输出映射到 P1 字段，不改合约

---

## 7. 关键接口速查

### EventStore (ledger)
```python
store = EventStore(database_path)
store.initialize()
event = store.create_genesis_event(trace_id, policy_version)  # → dict
event = store.append_event(p0_values, p1_values={})             # → dict (并发安全)
store.verify_chain_integrity()                                   # → {"valid": bool, "failures": [...]}
```

### AuditClassifier (audit)
```python
c = AuditClassifier()
r = c.classify(event)                        # → {"p0_pass": bool, "has_p1_issue": bool, ...}
c.evaluate_threshold(p1_rate_ratio)          # → "pass" | "p1_warn" | "p1_freeze"
report = generate_audit_report(events)       # → {"per_event": [...], "batch_stats": {...}}
```

### Clock (clock)
```python
get_window_30min(ts)           # → "YYYY-MM-DDTHH:MM_YYYY-MM-DDTHH:MM"
add_days_anchor(ts, days)      # → ISO 8601 UTC (D+1/D+7)
validate_window_id(wid)        # → bool
validate_window_consistency(e) # → {"valid": bool, ...}
```

### DisagreementResolver (resolver)
```python
dr = DisagreementResolver()
r = dr.resolve(state_l0, residual_l1, feasibility_l2, uncertainty_vector)
# → {"resolved_state": dict, "intervention_intensity": enum, "disagreement_score": float, ...}
af = dr.to_audit_fields(r)
```

### NoAssistEvaluator (no_assist)
```python
na = NoAssistEvaluator()
r = na.evaluate(session_id, user_answer, assist_used, event_time_utc, reference_answer=None)
# → {"no_assist_score": float, "no_assist_level": "independent"|"partial"|"dependent", ...}
af = na.to_audit_fields(r)
```

### GateEngine (gates)
```python
ge = GateEngine()
r = ge.evaluate(gate_inputs={}, event_time_utc=ts, window_id=None)
# → {"decision": "GO"|"WARN"|"FREEZE", "gate_score": float, "gates": {8 gates}, ...}
af = ge.to_audit_fields(r)
```

---

## 8. 下一阶段：中圈开发

### 中圈模块（按推荐顺序）

| 顺序 | 模块 | 预计路径 | 依赖 |
|------|------|---------|------|
| M1 | 中圈配置与共享基础设施 | `src/middle/shared/` | 内圈全部 |
| M2 | L0 状态估计层 (HBSSM) | `src/middle/state_l0/` | clock, ledger |
| M3 | L1 扰动残差层 (Shock/Memory/Trend) | `src/middle/state_l1/` | L0, clock |
| M4 | L2 行为可行性层 (COM-B) | `src/middle/state_l2/` | L1, resolver |
| M5 | 双轨决策 (LRM + 稳健轨) | `src/middle/decision/` | L0/L1/L2, resolver, gates |
| M6 | 语义安全层 (在线快检) | `src/middle/semantic_safety/` | 双轨, gates |

### 中圈启动前置条件（已满足）

- [x] 内圈 6 模块全绿（224 tests）
- [x] 5 份冻结合约静态核对通过
- [x] 运行时深测全部通过
- [x] 哈希链并发安全验证通过

---

## 9. 工作流程速查

每次开发一个模块时：
1. **读取合约** → `contracts/<relevant>.json`
2. **读已有接口** → `src/inner/<module>/` 的 `__init__.py` 了解导出
3. **写代码** → 仅限当前模块目录 + 对应测试文件
4. **跑单测** → `python -m pytest tests/test_<module>.py -v`
5. **跑全量** → `python -m pytest tests/ -q`
6. **输出报告** → 变更文件 + 测试结果 + 合约一致性 + GO/NO-GO

---

## 10. 快速验证命令

```bash
# 全量回归 (669 tests)
cd D:/Claudedaoy/coherence && python -m pytest tests/ -q

# 单模块
python -m pytest tests/test_ledger.py -v
python -m pytest tests/test_audit.py -v
python -m pytest tests/test_clock.py -v
python -m pytest tests/test_resolver.py -v
python -m pytest tests/test_no_assist.py -v
python -m pytest tests/test_gates.py -v
python -m pytest tests/test_middle_shared_contract.py tests/test_middle_shared_config.py tests/test_middle_shared_adversarial.py -v
python -m pytest tests/test_state_l0.py -v
python -m pytest tests/test_state_l1.py -v
python -m pytest tests/test_state_l2.py -v
python -m pytest tests/test_decision_engine.py -v
python -m pytest tests/test_semantic_safety_engine.py -v
python -m pytest tests/test_comprehensive_deep.py -v
```

---

**此文档由 Claude Code 在 2026-04-29 内圈闭环验收完成后生成。**
**下一个代理应从此文档开始，直接读取项目文件，无需重复探索。**
