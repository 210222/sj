# Phase 30 完整落地方案 — 技能知识图谱

## 一、现状

BKT 每个技能独立追踪，不知道技能间的依赖关系。

```
python_list: 0.73    ← 已掌握
python_loop: 0.45    ← 薄弱
python_dict: 0.50    ← 中等

BKT 不知道: 学 dict 前需要先会 list，list 掌握后 dict 应该更快上手
composer 不知道: loop 是 list 的前置，应该先补 loop 再学 dict
```

## 二、改动清单

| # | 文件 | +行 | 内容 |
|---|------|-----|------|
| 1 | 新文件 `config/skill_graph.json` | +30 | 技能依赖关系 DAG |
| 2 | `diagnostic_engine.py` | +30 | `SkillGraph` 类 + BKT 传播 |
| 3 | `composer.py` | +20 | `_select_topic_by_mastery()` 增强: 优先前置技能 |
| 4 | `test_phase30.py` | +30 | 验证传播和 topic 选择 |
| **Total** | **4 文件** | **+110** | |

## 三、设计

### skill_graph.json 格式

```json
{
  "python_list": {
    "prerequisites": ["python_variable", "python_loop"],
    "related": ["python_dict", "python_tuple"]
  },
  "python_loop": {
    "prerequisites": ["python_variable", "python_condition"],
    "related": ["python_list", "python_comprehension"]
  },
  "python_function": {
    "prerequisites": ["python_variable", "python_condition", "python_loop"],
    "related": ["python_class", "python_module"]
  },
  "python_dict": {
    "prerequisites": ["python_list", "python_variable"],
    "related": ["python_json"]
  },
  "python_comprehension": {
    "prerequisites": ["python_list", "python_loop", "python_function"],
    "related": ["python_generator"]
  }
}
```

### BKT 传播算法

```
用户答对 list 题 → BKT 更新 python_list: 0.73→0.81 (+0.08)
  → SkillGraph.propagate("python_list", 0.08)
    → 查找依赖 python_list 的技能 (python_dict, python_comprehension)
    → 对每个子技能: prior += gain * 0.3 (30% 知识迁移率)
    → python_dict 先验: 0.50 → 0.52
    → python_comprehension 先验: 0.30 → 0.32
```

### composer 选 topic 增强

```
当前: 选 mastery 最低的技能 → python_loop (0.45)
改后: 选 mastery 最低且前置已掌握的技能
  1. python_loop mastery=0.45, 但前置 python_condition=0.30 未掌握 → 跳过
  2. python_dict mastery=0.50, 前置 python_list=0.73 已掌握 → 选中
```

## 四、约束

- 不修改 contracts/ 内圈/中圈/外圈
- 不修改 ttm.py sdt.py flow.py
- 全量回归 1363+ 必须通过
- skill_graph.json 为新文件, 不影响现有代码
