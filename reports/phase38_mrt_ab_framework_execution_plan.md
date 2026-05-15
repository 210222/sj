# Phase 38 — 教学策略 A/B 测试框架：MRT 闭环：执行计划

## 1. 文档目的

Phase 38 的目标是把 Phase 7 已存在的 MRT 框架从半成品升级为可运行的教学策略 A/B 对比系统。
不新建框架，不替换 composer，不做强化学习。

---

## 2. 权威 XML 层

| 文件 | 用途 |
|------|------|
| `265_phase38_orchestrator.xml` | 总控编排 |
| `266_s38_1_outcome_collection.xml` | Outcome 采集 |
| `267_s38_2_strategy_variants.xml` | 策略变体扩展 |
| `268_s38_3_bayesian_estimation.xml` | 贝叶斯估计接入 |
| `269_s38_4_regression_close.xml` | 回归与收口 |

---

## 3. 全局边界

- 不改 contracts/**、src/inner/**、src/middle/**、src/outer/**
- 不改 provider/model/base_url
- 不改 Phase 32 scoring
- 不替换 composer 主逻辑
- 不做多臂老虎机/RL

---

## 4. 执行顺序

```
S38.1 (Outcome 采集) → S38.2 (策略变体) → S38.3 (贝叶斯估计) → S38.4 (回归收口)
```

---

## 5. 每阶段详情

### S38.1 — Outcome 采集

- **目标**：MRT assignment → outcome 信号关联并持久化
- **outcome 信号**：response_length, has_steps, has_example, transport_status
- **关键原则**：outcome 只采集原始特征，不计算教学评分

### S38.2 — 策略变体扩展

- **目标**：从 style delta 扩展到 strategy 级变体
- **不可覆盖清单**：pulse, precedent_intercept, counterfactual, diagnostic_probe
- **高风险 action_type 不参与**

### S38.3 — 贝叶斯估计

- **目标**：aggregate_outcomes() → BayesianEstimator → 后验分布
- **输出**：mrt_variant_comparison.json (mean, ci_95, effect_size, posterior_overlap, n)

### S38.4 — 回归与收口

- **目标**：targeted tests + full regression + completion 文档

---

## 6. NO-GO 条件

1. 修改了 contracts/ 或 frozen layers
2. strategy 变体绕过了安全门禁
3. composer 主逻辑被替换
4. full regression 未通过
