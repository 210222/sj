# Phase 29 完整落地方案 — 全线接回调（第二阶段）

## 一、现状

全盘扫描发现 7 处"方法写好了但没调"。

```
Phase 20 S20.3 写了:
  save_current_topic()     → 从未调, current_topic 永远空
  save_learning_goal()     → 从未调, learning_goal 永远空
  save_goal_progress()     → 从未调, goal_progress 永远 0
  save_topics()/load_topics() → 从未调, 已学知识不落盘

Phase 20 S20.2 写了:
  adjust_difficulty()      → 从未调, 难度自适应不触发

Phase 20 S20.3 写了:
  _select_topic_by_mastery() → 从未调, compose 不根据薄弱点选话题

Phase 24 S24.3 写了:
  get_mastery_snapshot()   → 有方法但无 API 路由
```

## 二、改动清单

| # | 级别 | 改什么 | 文件 | 行 |
|---|------|--------|------|----|
| 1 | P0 | save_current_topic | agent.py return 前 | +3 |
| 2 | P0 | save_learning_goal | agent.py return 前 | +5 |
| 3 | P0 | save_goal_progress | agent.py return 前 | +6 |
| 4 | P1 | select_topic_by_mastery (移到 agent.py compose 前) | agent.py compose 前 | +8 |
| 5 | P1 | adjust_difficulty | agent.py return 前 | +8 |
| 6 | P2 | save_topics/load_topics | agent.py return 前 | +5 |
| 7a | P2 | UserDashboardResponse 加字段 | schemas.py | +1 |
| 7b | P2 | get_mastery_snapshot 注入响应 | dashboard.py return 前 | +5 |

**Total: 4 文件 / +41 行**

## 三、审查发现的 P0 Bug

| Bug | 原方案 | 修复 |
|-----|--------|------|
| compose() 无 `context` 参数 | P1-4 引用不存在的变量 | 移到 agent.py compose 前 (diagnostic_engine 可访问) |
| Pydantic 模型固定字段 | P2-7 直接追加 key | 先改 schemas.py 加 Optional 字段, 再传值 |

## 四、约束

- 不修改 contracts/ 内圈/中圈/外圈
- 不修改 ttm.py sdt.py flow.py
- 全量回归 1363+ 必须通过

## 五、验收

| 门禁 | 条件 |
|------|------|
| G1 | pytest tests/ -q 全绿 |
| G2 | 1 轮 act() 后 current_topic 非空, learning_goal 非空 |
| G3 | "继续当前教学"显示具体 topic |
| G4 | GET /dashboard/user 含 mastery_snapshot 字段 |
| G5 | compose() 签名不变 (无 context 参数) |
