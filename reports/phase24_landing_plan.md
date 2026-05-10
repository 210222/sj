# Phase 24 完整落地方案 -- 纵向评测

## 一、现状

当前 score_response() 只有格式维度, 没有学习效果维度。
score_response(r) 只有响应 dict, 没有 agent 实例。
DiagnosticEngine() 空实例 get_all_masteries() 返回 {}, 不能这样用。

## 二、改动清单

| 子阶段 | 文件 | 行数 | 改动 |
|--------|------|------|------|
| S24.1 | test_s15_quick.py | +20 | score_response() 从 dict 字段推断学习效果 |
| S24.2 | tests/test_phase24_longitudinal.py | +40 | 字段完整性 + 持久化 + 压力测试 |
| S24.3 | dashboard_aggregator.py | +20 | get_mastery_snapshot() 技能快照 |
| **Total** | **3 文件** | **+80** | |

## 三、审查发现的 bug 及修复

| 问题 | 修复 |
|------|------|
| DiagnosticEngine() 空实例返回空 skills | 改为检查响应 dict 的 diagnostic_result 字段 |
| score_response(r) 没有 agent 引用 | 不实例化 engine, 只读 dict |
| profile_history 无 skill 级 field_name | get_mastery_trend() 不行, 改为 profiles JSON 快照 |

## 四、约束

- 不修改 contracts/ 内圈/中圈/外圈
- 不修改现有评分维度的计算方式
- 全量回归 1284+ 必须通过
- 不需要 DEEPSEEK_API_KEY
