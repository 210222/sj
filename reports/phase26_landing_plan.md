# Phase 26 完整落地方案 -- 主动进步反馈 (Standard 9)

## 一、现状

profile_history + BKT mastery + retention 数据全部就位, 但系统不会主动告诉用户。
Standard 9 (Evidence-Based Progress Feedback) 一直是 PARTIAL。

## 二、触发条件 (事件驱动, 非固定轮数)

任一条件满足时生成 progress_summary:
1. 任何技能 BKT mastery 变化 > 0.1 (进步/退步)
2. 任何技能 mastery 首次跨过 0.7 (学会)
3. 任何技能 retention < 0.6 (该复习)
4. 距上次反馈超过 1 小时 (频率限制)

## 三、改动清单

| # | 文件 | 行 | 改动 |
|---|------|---|------|
| 1 | agent.py | +35 | progress_summary 生成 (4 条件触发) |
| 2 | prompts.py | +20 | progress 区块注入 prompt |
| 3 | test_phase26.py | +15 | 验证 |
| **Total** | **3 文件** | **+70** | |

## 四、约束

- 不修改 contracts/ 内圈/中圈/外圈
- 全量回归 1299+ 必须通过
- 不需要 DEEPSEEK_API_KEY
