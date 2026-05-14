# Phase 25 完整落地方案 -- 教学自评 + 策略切换

## 一、现状

系统能调节难度、间隔重复、区分 8 种教学模式。但:
- 不知道"教得怎么样" -- 过去 5 轮的 scaffold 有效吗?
- 如果效果差, 不会主动切换策略 -- 只会调难度, 不会换方法
- Standard 5 (Self-Evaluation) 一直标记为 critical 缺口

## 二、改动

| 子阶段 | 文件 | 行数 | 改动 |
|--------|------|------|------|
| S25.1 | agent.py | +40 | 跟踪每轮效果 + compose 前注入 self_eval |
| S25.2 | composer.py | +20 | compose() 接收 self_eval, 策略失效时切换 action_type |
| S25.3 | tests/test_phase25.py | +20 | 验证切换逻辑 |
| **Total** | **3 文件** | **+80** | |

## 三、策略切换规则

| 当前策略 | 检测条件 | 切换到 |
|---------|---------|--------|
| scaffold | 3 轮后 mastery 无提升 | probe |
| challenge | 用户 competence < 0.3 | scaffold |
| probe | 连续 2 轮答错 | reflect |
| suggest | 用户无响应或无选择 | scaffold |
