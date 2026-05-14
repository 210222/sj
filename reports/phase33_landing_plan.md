# Phase 33 — 前端教学功能展示

## 一、现状

后端 Phase 19-31 实现的教学数据全部未在前端展示。用户只看到聊天气泡和 TTM/SDT 图表。

## 二、改动清单

| # | 文件 | +行 | 内容 |
|---|------|-----|------|
| 1 | `api/routers/dashboard.py` | +8 | 注入 mastery_snapshot + review_queue |
| 2 | `api/services/dashboard_aggregator.py` | +20 | get_review_queue() |
| 3 | `api/models/schemas.py` | +2 | UserDashboardResponse 新增字段 |
| 4 | `frontend/src/components/TeachingStatus.tsx` | +30 | 教学状态面板 |
| 5 | `frontend/src/App.tsx` | +5 | 集成到侧边栏 |
| **Total** | **5 文件** | **+65** | |

## 三、展示效果

侧边栏新增板块:

```
技能掌握度
  python_list:  73%
  python_loop:  45%

待复习
  pandas_csv: 保留率 42%
  numpy:      保留率 38%

当前策略: scaffold
```

## 四、约束

- 不修改 contracts/
- 不修改 agent.py、composer.py、prompts.py
- 全量回归 1370+ 必须通过
- npm run build 无 TS 错误
