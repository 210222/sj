# Phase 59 — 学习路径前端可视化：完成归档

判定: GO ✅ (1466/0/5, npm build 194 kB)

交付:
- `api/main.py`: +4 行 /config 静态挂载
- `SkillTreeCard.tsx`: 新建 (~90 行)，CONCEPT_NAMES 19 映射，颜色编码 (绿≥0.7/黄0.3-0.7/灰<0.3)，前置层级缩进
- `App.tsx`: 侧边栏集成 (TeachingStatus 下方)

数据流: GET /config/skill_graph.json → 图谱结构 + GET /dashboard/user → mastery_snapshot → 合并渲染技能树

3 场景: 新学生(全灰) / 学习中(绿+黄+虚线前置) / 进阶(解锁提示)
