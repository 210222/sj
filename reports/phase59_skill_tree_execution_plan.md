# Phase 59 — 学习路径前端可视化：执行计划

## 1. 文档目的
将 Phase 58 的学习路径从教练端扩展到学生端 Dashboard 可视化。

## 2. 权威 XML
- `320_phase59_orchestrator.xml`
- `321_s59_1_skill_tree_component.xml`
- `322_s59_2_app_integration.xml`
- `323_s59_3_build_regression.xml`

## 3. 全局边界
不改后端逻辑（仅 +3 行静态挂载）。不改 composer/agent/frozen layers。

## 4. 数据准确性
| 数据 | 来源 | 状态 |
|------|------|------|
| 技能图谱 | /config/skill_graph.json (静态挂载) | 18 概念 |
| 掌握度 | GET /dashboard/user → mastery_snapshot | 新session返回null(正常) |

## 5. 执行顺序
S59.1 → S59.2 → S59.3

## 6. 最终验收
- /config/skill_graph.json HTTP 可访问
- 技能树在 Dashboard 渲染，3 场景正确
- 1466/0/5
