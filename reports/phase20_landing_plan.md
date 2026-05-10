# Phase 20 完整落地方案 — 可观测性 + 用户模型

## 一、现状（Phase 19 完成后）

```
Phase 19 后 LLM/诊断/个性化已经接通，但:
  - persistence.py get_profile() 只返回当前值，无历史趋势
  - agent.act() 从未调用 save_ttm_stage()/save_sdt_scores()
  - Dashboard 所有数据是硬编码占位符
  - 系统没有"学习目标"概念
  - 无法回答"用户学了一个月后进步了吗？"

关键发现——agent.py 当前只调 persistence 做 consent 持久化：
  grep: save_ttm|save_sdt|save_difficulty|increment_turns
  → 0 matches in agent.py
```

### 直接原因

| # | 问题 | 文件:行 | 影响 |
|---|------|---------|------|
| 1 | agent.act() 不调 persistence save 方法 | agent.py 全文无 `save_ttm_stage` 等 | 数据不进 profiles 表 |
| 2 | persistence.py 只有`profiles`覆盖式表，无历史表 | persistence.py:16-42 | 无法查历史趋势 |
| 3 | dashboard_aggregator.py 传硬编码 dummy 数据 | L57-61, L86-92, L106-111 | Dashboard 显示假数据 |
| 4 | persistence.py 无 learning_goal 字段 | L121-133 get_profile() | 系统不知道用户想学什么 |

## 二、目标状态

```
act() 每轮结束时：
  persistence.save_ttm_stage(stage)
  persistence.save_sdt_scores(auto, comp, rel)
  persistence.save_difficulty(level)
  persistence.increment_turns()
  
profile_history 表:
  session_id, field_name, old_value, new_value, timestamp
  → get_mastery_trend("python_loop", 30) 返回时间序列
  
Dashboard:
  total_turns > 0（真实值）
  ttm_radar 从 profile 表读取当前 TTM 阶段
  sdt_rings 从 profile 表读取三轴评分

Learning goal:
  persistence 加 learning_goal, current_topic, goal_progress 字段
  composer 新增 _select_topic_by_mastery()
```

## 三、改动清单

### 总览

| 子阶段 | 文件 | 行数 | 依赖 |
|--------|------|------|------|
| S20.1a 每轮持久化 | agent.py | +25 | Phase 19 完成 |
| S20.1b 历史表 | persistence.py | +80 | S20.1a |
| S20.2 Dashboard | dashboard_aggregator.py | +60 | S20.1a |
| S20.3 学习目标 | persistence.py + composer.py | +80 | S20.1b |
| **总计** | **4 个文件** | **+245** | |

### 执行顺序

```
S20.1a (25 行): agent.py act() 末尾调用 save_ttm/save_sdt/increment_turns
    ↓ 数据开始流入 profiles 表
S20.1b (80 行): persistence.py 新增 profile_history 表 + 查询方法
    ↓ 历史数据可用
S20.2 (60 行): dashboard_aggregator.py 从 persistence 读真实数据
    ↓ Dashboard 显示真实数据
S20.3 (80 行): persistence 加 goal 字段 + composer 技能选 topic
    ↓ 学习目标可追踪
```

## 四、约束

- 禁止修改 contracts/ 任何文件
- 禁止修改 src/inner/** src/middle/** src/outer/**
- 禁止修改 src/coach/llm/ 中的文件
- 禁止修改 src/coach/ttm.py、sdt.py、flow.py（已冻结）
- 全量回归 1275+ 必须通过
- 所有新增字段在 disabled 时返回默认值
- profiles 表已有字段不改名不改类型，只新增列

## 五、风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| profile_history 每轮写入影响 SQLite 性能 | 低 | WAL 模式 + append-only，实测 < 1ms |
| dashboard 改造后返回 None 导致前端崩溃 | 低 | 前端字段已有 Optional/None 保护 |
| learning_goal 字段新增需 ALTER TABLE | 低 | 使用 try/except OperationalError（同 consent 模式）|
| composer._select_topic_by_mastery 无数据时死循环 | 低 | 无 mastery 数据时返回 None |

## 六、验收

| 门禁 | 测试 | 通过条件 |
|------|------|---------|
| G1 | pytest tests/ -q | 1275+ passed |
| G2 | 3 轮对话后 persistency 表有真实记录 | total_turns > 0 |
| G3 | Dashboard API 返回 total_turns > 0 | 非硬编码值 |
| G4 | get_mastery_trend() 返回数组 | 有历史数据 |
| G5 | composer._select_topic_by_mastery() 返回 topic | 非 None |
