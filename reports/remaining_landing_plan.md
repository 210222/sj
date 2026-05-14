# 剩余缺口完整落地方案

## 缺口 1: 技能知识图谱（Phase 30 — 待执行）

| # | 文件 | +行 | 内容 |
|---|------|-----|------|
| 1 | `config/skill_graph.json` | +30 | 8 个 Python 技能 DAG |
| 2 | `diagnostic_engine.py` | +60 | SkillGraph 类 + BKT 传播 |
| 3 | `composer.py` | +20 | `_select_topic_by_mastery` 前置检查 |
| 4 | `test_phase30.py` | +30 | 6 个测试 |
| **Total** | **4 文件** | **+140** | |

数据流:
```
答对"列表" → BKT: 0.50→0.73 → propagate → python_dict: 0.50→0.57
composer 选 topic: dict(0.40) 但前置 loop(0.30) 未掌握 → 先教 loop
```

## 缺口 2: 用户画像完整接入

合约 `contracts/user_profile.json` 定义了两层:

| 层 | 合约字段 | 代码实现 | 运行时调用 |
|----|---------|----------|-----------|
| Entity | entity_id, timeline, session_tags, device_id | `data.py` MemoryStore.upsert_entity | ❌ 无人调 |
| Fact | fact_id, claim, confidence, ttl, lifecycle | `data.py` MemoryStore.insert_fact | ✅ SessionMemory 内部在用 |

### 改动

| 文件 | +行 | 内容 |
|------|-----|------|
| `agent.py` __init__ | +2 | 初始化 `self._entity_id` |
| `agent.py` return 前 | +10 | 每轮 upsert_entity (timeline + session_tags) |
| `agent.py` return 前 | +10 | 每轮 insert_fact (skill_masteries 作为事实持久化) |
| **Total** | **+22** | |

### 效果

```
改之前: profiles 表存简化数据, entity_profiles 表永远空
改之后: 每轮结束时同步写入 entity_profiles(timeline + session_tags) 和 facts(skill_masteries)
        两份表并存: profiles 快速读写 + entity_profiles 长线归档
```

## 执行顺序

```
Phase 30 (知识图谱, +140 行) → 用户画像接线 (+22 行)
  无依赖                    无依赖
```

两个缺口独立，可并行。

## 元提示词

| 缺口 | 元提示词文件 |
|------|------------|
| 知识图谱 | `209_phase30_orchestrator.xml` + `209-212_s30_*.xml`（已写） |
| 用户画像 | `214_user_profile.xml`（需写）|

需要我写用户画像接线的元提示词吗？
