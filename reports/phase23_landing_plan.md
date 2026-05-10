# Phase 23 完整落地方案 -- 间隔重复

## 一、现状

系统现在能追踪用户掌握度（BKT）, 但:
- 用户学过函数 -> BKT 算出 mastery=0.85
- 用户 30 天没碰函数 -> mastery 仍然 0.85（不会衰减）
- 系统不知道"该复习了"
- SRC-010 (Duolingo HLR) 和 Agent 7 评审均指出此缺口

## 二、目标

学习新知识后第 1 周: retention=0.85 -> 正常，无需复习
学习新知识后第 4 周: retention=0.42 -> < 0.6，系统主动插入复习

## 三、改动清单

| 子阶段 | 文件 | 行数 | 改动 |
|--------|------|------|------|
| S23.1 | flow.py | +30 | BKTEngine.estimate_retention() |
| S23.2 | persistence.py | +25 | get_skills_with_recency() 从 JSON blob 读 mastery |
| | agent.py | +30 | compose() 前复习队列检查 + action_type 覆盖 |
| S23.3 | tests/test_phase23.py | +20 | 验证 |
| **Total** | **4 文件** | **+95** | |

## 四、约束

- 不修改 contracts/ 内圈/中圈/外圈
- 不修改已有的 BKT predict/fit 方法
- retention 衰减不影响现有 mastery 值
- 全量回归 1284+ 必须通过

## 五、执行顺序

S23.1 (flow.py retention) -> S23.2 (persistence+agent 复习覆盖) -> S23.3 (测试)
