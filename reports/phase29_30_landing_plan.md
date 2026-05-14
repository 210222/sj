# Phase 29-30 完整落地方案

## 一、Phase 29 — 全线接回调（已交付）

7 处"写好了但没调" + 4 处剩余接入。

### 已修复（7 处）

| # | 方法 | 文件 | 状态 |
|---|------|------|------|
| P0-1 | save_current_topic | agent.py return 前 | GO |
| P0-2 | save_learning_goal | agent.py return 前 | GO |
| P0-3 | save_goal_progress | agent.py return 前 | GO |
| P1-4 | select_topic_by_mastery | agent.py compose 前 | GO |
| P1-5 | adjust_difficulty | agent.py return 前 | GO |
| P2-6 | save_topics/load_topics | agent.py return 前 | GO |
| P2-7 | mastery_snapshot API | schemas.py + dashboard.py | GO |

### 刚修复（4 处）

| # | 方法 | 调用点 | 状态 |
|---|------|--------|------|
| 1 | add_excursion_evidence | _detect_excursion_command 中 | GO |
| 2 | suggest_correction | cross_track_result 后 | GO |
| 3 | extract_topics_from_text | build_coach_context 前 | GO |
| 4 | get_related | compose 调用前 | GO |

### 前端修复

| 问题 | 修复 |
|------|------|
| 苏醒面板每轮都弹 | consent_status="shown" 持久化 |
| 上下文无关联 | Phase 27 5 块结构 |
| 每轮都是探测题 | diagnostic_engine probe 跳过条件 |
| 设置开关不生效 | yaml.safe_dump + 清除模块缓存 |
| 刷新消息消失 | localStorage + 服务端历史 |
| WS 连接失败 | ws:true + HTTP fallback |
| 无回复等待提示 | loading + 30s 超时 |
| AI 一直问确认 | Phase 27 上下文已解决 |

## 二、Phase 30 — 技能知识图谱（待执行）

### 改动

| # | 文件 | +行 | 内容 |
|---|------|-----|------|
| 1 | config/skill_graph.json | +30 | 技能依赖 DAG |
| 2 | diagnostic_engine.py | +60 | SkillGraph 类 + BKT 传播 |
| 3 | composer.py | +20 | 前置技能检查 |
| 4 | test_phase30.py | +30 | 6 个测试 |
| **Total** | | **+140** | |

### 数据流

```
用户答对"列表" → BKT python_list: 0.50→0.73
  → propagate("python_list", gain=0.23)
    → python_dict prior: 0.50→0.57 (+30% 迁移)
    → python_comprehension: 0.30→0.37

composer 选 topic:
  dict(0.40) 但前置 loop(0.30) 未掌握 → 先教 loop
```

## 三、检查规则更新

`reports/meta_prompt_design_checklist.md` 新增：

```
[ ] 调用点注入: 新增的 save/load/update 方法是否被 act()/compose() 调用?
    [ ] 是 → success_criteria 中含调用验证
    [ ] 否 → 标注"此方法由 XXX 在 Phase N 调用"
```

## 四、项目状态

| 指标 | Phase 19 前 | 现在 |
|------|------------|------|
| 测试 | 1275 | **1363** |
| Phase 文件 | 0 | **19 个** (19-30) |
| 接线缺口 | — | 11 处全修复 |
| 核心教学链 | LLM 旁路, 行为模型 OFF | LLM 主路径, 上下文结构化, 策略自切换 |
| 教学 Level | 2.0 | **~4.5** |
