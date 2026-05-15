# Phase 40 — 教学策略自评与自适应：最终验收

## 1. 文档目的

Phase 40 将 Phase 38 的 MRT outcome 闭环数据回灌到 composer，形成"评估→偏好"最短回路。

---

## 2. 执行摘要

| 子阶段 | 名称 | 核心交付 | 判定 |
|--------|------|----------|------|
| S40.1 | Self-Eval 升级 | `MRTExperiment.get_strategy_quality()` | GO |
| S40.2 | Composer 偏好 | `PolicyComposer._apply_mrt_preference()` | GO |
| S40.3 | 回归与收口 | 1466 passed / 0 failed | GO |

---

## 3. 实现摘要

### get_strategy_quality(min_samples=5)

- 从 `mrt_outcomes` 表读取最近 200 条
- 按 action_type 分组统计 effective_rate / structured_rate / avg_length / n
- n < min_samples 时该类型不返回
- 异常或空数据时返回 `{}`

### _apply_mrt_preference(action_type, intent)

- 唯一允许的策略对：scaffold↔suggest、challenge↔probe
- 切换条件：双方 n≥5，备选 effective_rate 高 0.1+，structured_rate 更高
- 置于 compose() 流程中 TTM/SDT/flow 之后、Phase 25 切换之前
- 不可覆盖：pulse、precedent_intercept、counterfactual、diagnostic_probe

---

## 4. 关键设计约束验证

| 约束 | 状态 |
|------|------|
| 不改 contracts/** | ✅ |
| 不改 frozen layers | ✅ |
| 不改 provider/model/base_url | ✅ |
| 不改 scoring | ✅ |
| 软偏置，不硬覆盖 | ✅ 阈值保护 |
| 不做强化学习 | ✅ 仅静态偏好 |

---

## 5. 全量回归

```
1466 passed, 5 skipped, 0 failed
```

---

## 6. Phase 38-40 回路全景

```
Phase 38: MRT assign → record_outcome() → aggregate_outcomes() → Bayesian estimation
                              ↓
Phase 40: get_strategy_quality() → _apply_mrt_preference() → composer compose()
```

## 7. 最终结论

**Phase 40 判定：GO** ✅
