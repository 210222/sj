# Feasibility Assessment Matrix

## Evaluated Findings

---
Finding ID: GAP-001 (诊断→决策断路)
Title: 诊断→决策断路
Technical Feasibility: feasible — 修改 agent.py 约 50 行，将 mastery 传入 compose()
User Perceptibility: high — 用户能感知到教学难度随掌握度变化
Data Support: empirical — S15 数据证明 full_stack+Diag 高 2.1 分
Constraint Check: PASS
Recommended Action: P0

---
Finding ID: GAP-002 (难度调节断路)
Title: 难度调节断路(LLM)
Technical Feasibility: feasible — 约 30 行，将 payload["difficulty"] 传入 build_coach_context()
User Perceptibility: medium — 用户需要多轮才能感知难度变化
Data Support: empirical — ultimate_quality_report 显示 difficulty 影响存在但有限
Constraint Check: PASS
Recommended Action: P0

---
Finding ID: GAP-003 (评估→更新回路缺失)
Title: 评估→更新回路缺失
Technical Feasibility: feasible — 在 TTM/SDT assess 调用前注入 mastery_summary，约 40 行
User Perceptibility: medium — 用户感知在数轮后体现
Data Support: theoretical — BKT/TTM/SDT 理论支撑反馈回路
Constraint Check: PASS
Recommended Action: P1

---
Finding ID: GAP-004 (action_type 差异不足)
Title: action_type 行为差异不足
Technical Feasibility: feasible-with-mod — 需重构 prompts.py 的 action_type 差异化逻辑，约 100 行
User Perceptibility: medium — 用户能感知不同模式的教学风格差异
Data Support: unsupported — 缺少量化证据
Constraint Check: PASS
Recommended Action: P2

---
Finding ID: GAP-005 (学习历史永久为空)
Title: 学习历史永久为空
Technical Feasibility: feasible — 用 SessionMemory 填充 s4_history/s4_memory，约 40 行
User Perceptibility: high — LLM 能引用用户之前学过的内容
Data Support: empirical — S15 personalization 维度 full_stack 2.0 vs llm_only 1.0
Constraint Check: PASS
Recommended Action: P0

---
Finding ID: GAP-006 (难度单向调节)
Title: 难度单向调节
Technical Feasibility: feasible — 在 composer.py 添加 raise_difficulty 路径，约 20 行
User Perceptibility: low — 需要长期使用才能感知
Data Support: unsupported
Constraint Check: PASS
Recommended Action: P2

---
Finding ID: GAP-007 (无学习目标)
Title: 无学习目标/课程概念
Technical Feasibility: feasible-with-mod — 需要新增 LearningGoal 数据结构 + persistence + DSL 字段，约 200 行
User Perceptibility: high — 用户能看到"学习计划"和"目标进度"
Data Support: theoretical — 所有 ITS 文献强调 goal-setting 是基础能力
Constraint Check: PASS
Recommended Action: P1

---
Finding ID: DATA-001 (评分体系)
Title: 评分体系测回答质量而非学习效果
Technical Feasibility: feasible-with-mod — 新增 2 个纵向评分维度，约 80 行
User Perceptibility: low — 用户不直接感知评测改进
Data Support: empirical — 此缺口本身来自数据审计
Constraint Check: PASS
Recommended Action: P2

---
Finding ID: DATA-002 (无历史趋势)
Title: 用户模型无历史趋势
Technical Feasibility: feasible-with-mod — 新增 history 表 + SQL 查询，约 100 行
User Perceptibility: low — 为仪表盘提供数据
Data Support: empirical — DATA-003 直接确认
Constraint Check: PASS
Recommended Action: P1

---
Finding ID: DATA-003 (Dashboard 假数据)
Title: Dashboard 数据全部是假的
Technical Feasibility: feasible — 将 get_ttm_radar/get_sdt_rings 接入 persistence，约 60 行
User Perceptibility: medium — 用户能看到真实的学习仪表盘
Data Support: empirical
Constraint Check: PASS
Recommended Action: P1

---
Finding ID: DATA-004 (门禁无数据)
Title: 门禁系统无真实数据
Technical Feasibility: feasible — 从 gate 检查结果读取真实状态，约 30 行
User Perceptibility: low
Data Support: unsupported
Constraint Check: PASS
Recommended Action: P3

---
Finding ID: DATA-005 (无纵向测试)
Title: 测试全部是单轮模式
Technical Feasibility: feasible-with-mod — 新增 longitudinal 测试 framework，约 150 行
User Perceptibility: low
Data Support: empirical
Constraint Check: PASS
Recommended Action: P2

---
Finding ID: DATA-006 (评分区分度低)
Title: 256 配置评分区分度低
Technical Feasibility: feasible — 新增 mastery-based 评分维度，与 DATA-001 联动
User Perceptibility: low
Data Support: empirical
Constraint Check: PASS
Recommended Action: P2

## Priority Summary

**P0 (Do Immediately)**: GAP-001, GAP-002, GAP-005 (3 items)

**P1 (Next Priority)**: GAP-003, GAP-007, DATA-002, DATA-003 (4 items)

**P2 (In Plan)**: GAP-004, GAP-006, DATA-001, DATA-005, DATA-006 (5 items)

**P3 (Watch List)**: DATA-004 (1 item)

**Dropped**: None (all passed constraint check)

## Top 3 Recommendations

1. **GAP-005 — 修复学习历史为空的断点**: 这是最多连锁缺口的根因——修复后 GAP-001(诊断数据可流入)、DATA-003(Dashboard 有真实数据)、GAP-003(评估反馈回路)都会改善。约 40 行改动，收益最大。

2. **GAP-001 — 连接诊断引擎到 composer**: 让 BKT mastery 真正影响教学策略选择。与 GAP-005 配合后形成完整闭环：用学习历史 + mastery 数据选择下一步教学动作。

3. **GAP-002 — 将 difficulty 传入 LLM prompt**: 与 GAP-001/GAP-005 联动后，LLM 能根据 user 的真实掌握度和难度需求生成差异化内容。约 30 行改动，立即提升 LLM 输出质量。
