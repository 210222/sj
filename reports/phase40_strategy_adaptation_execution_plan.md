# Phase 40 — 策略自评与自适应：执行计划（治理层补齐）

## 1. 权威 XML
- `270_phase40_orchestrator.xml`
- `271_s40_1_self_eval_upgrade.xml`
- `272_s40_2_composer_adaptation.xml`
- `278_s40_3_regression_close.xml`

## 2. 代码实现面
| 交付 | 位置 |
|------|------|
| get_strategy_quality() | `src/coach/mrt.py` |
| _apply_mrt_preference() | `src/coach/composer.py` |

## 3. 关键行为
- 偏好仅在 scaffold↔suggest、challenge↔probe 之间生效
- 需 ≥5 样本 + 10% 以上有效率优势
- 不覆盖 pulse/precedent/counterfactual 安全门禁
