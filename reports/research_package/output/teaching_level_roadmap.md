# Teaching Level Improvement Roadmap

## Current State

Coherence 当前处于教学 Level 2.0 — 有传感器（TTM/SDT/Flow/DiagnosticEngine）和执行器（LLM + 8 action_types），但两者之间的控制回路是断的。系统能"看见"用户但无法根据所见的调整行为。全量 1275 测试覆盖了功能正确性，但无法验证"教学是否有效"。

## Target State

Level 4.0 — 完整的感知→决策→执行→评估→更新闭环。系统有学习目标、能追踪 mastery 趋势、能自适应调节难度和策略、能用纵向数据证明教学效果。

Teaching Level: Level 2.0 → Level 4.0

---

## Phase 1: 学习历史激活 + 难度闭环

### One-Line Goal
系统能记住用户学过什么，并据此调节教学难度。

### Prerequisites
None

### Findings Covered
GAP-005 (学习历史为空), GAP-001 (诊断→决策断路), GAP-002 (难度调节断路)

### Files to Change
- src/coach/agent.py: act() 中填充 s4_history 从 SessionMemory；将 diagnostic_engine.get_mastery_summary() 的结果注入 compose() 和 build_coach_context()；将 composer 产出的 difficulty 传入 build_coach_context()
- src/coach/llm/prompts.py: 优化 {difficulty} 占位符的差异化描述（easy=仅用类比, medium=类比+原理, hard=仅用原理）
- src/coach/composer.py: compose() 新增 mastery 参数，低 mastery→优先 reflect/scaffold

### Verification Method
- python -m pytest tests/ -q 全量回归通过
- 新测试 tests/test_phase18_history_flow.py：验证多轮对话后 s4_history 非空、difficulty 随 mastery 变化、prompt 中 difficulty 不为 "medium"
- A/B 对比：修复前后 personalization 维度评分提升 ≥1.0

### Risk
SessionMemory 当前仅存储最近几轮——长期历史的存储和检索可能影响性能

### Teaching Level Impact
Level 2.0 → Level 2.8 (学习历史的闭环建立)

---

## Phase 2: 用户模型 + Dashboard 真实化

### One-Line Goal
Dashboard 展示真实学习数据，用户模型支持历史趋势查询。

### Prerequisites
Phase 1

### Findings Covered
DATA-002 (无历史趋势), DATA-003 (Dashboard 假数据)

### Files to Change
- src/coach/persistence.py: 新增 profile_history 表（session_id, field_name, old_value, new_value, timestamp）；新增 get_mastery_trend() 查询方法
- api/services/dashboard_aggregator.py: get_ttm_radar() 和 get_sdt_rings() 改为从 persistence 读取 session 数据；get_progress() 查询真实轮次
- src/coach/agent.py: 每次 TTM/SDT/Flow 更新后调用 persistence 记录历史

### Verification Method
- Dashboard API 调用返回真实数据（total_turns > 0, mastery 历史数组非空）
- 新测试 tests/test_dashboard_real_data.py 验证数据真实性

### Risk
历史表写入频率高（每轮一次）——需要确认 SQLite 写入性能

### Teaching Level Impact
Level 2.8 → Level 3.2 (可观测性建立)

---

## Phase 3: 教学策略增强（评估→更新回路 + 学习目标）

### One-Line Goal
系统能设定学习目标，并根据 mastery 数据调整 TTM/SDT 评估。

### Prerequisites
Phase 2

### Findings Covered
GAP-003 (评估→更新回路), GAP-007 (无学习目标)

### Files to Change
- src/coach/agent.py: TTM.assess() 和 SDT.assess() 调用前注入 mastery_summary；act() 新增 goal 参数
- src/coach/composer.py: 新增 _select_topic_by_mastery()——选 mastery 最低的 topic 出题
- src/coach/diagnostic_engine.py: get_competence_signal() 接入 SDT 的 competence 更新
- contracts/coach_dsl.json: 追加 learning_goal 相关字段(新增字段，不修改已有)

### Verification Method
- 纵向测试：5 轮 learn → 2 轮 diagnose → 验证 TTM stage 和 SDT competence 有变化
- 新测试 tests/test_goal_driven_teaching.py

### Risk
goal 参数需要前端配合——可能需要新增 API 字段

### Teaching Level Impact
Level 3.2 → Level 3.6 (教学决策智能化)

---

## Phase 3.5: Spaced Repetition

### One-Line Goal
已学知识按计算好的间隔重新出现，防止遗忘。

### Prerequisites
Phase 2 (需要 mastery 历史数据)

### Findings Covered
SRC-010 (Duolingo HLR), Agent 7 Standard 7 gap

### Files to Change
- src/coach/flow.py: BKTEngine 新增 estimate_retention()——基于 mastery 变化率+距上次练习天数估算记忆保留率
- src/coach/composer.py: 新增 _check_review_queue()——当有 overdue 复习(estimated_retention<0.6)时，action_type 优先 review
- src/coach/diagnostic_engine.py: 记录每次 mastery 更新的时间戳

### Verification Method
- 测试：10 轮 learn→wait 5 轮→系统自动插入复习→验证 action_type=review
- A/B：spaced repetition ON vs OFF 的 mastery 保留率对比

### Risk
复习题与当前学习目标可能不相关——需要权衡"复习旧知识"和"推进新目标"

### Teaching Level Impact
Level 3.6 → Level 3.7 (Standard 7 覆盖)

---

## Phase 4: 评测体系升级（纵向评测 + 学习效果维度）

### One-Line Goal
评测体系能从"单轮回答质量"升级为"多轮学习效果"测量。

### Prerequisites
Phase 3 (需要 mastery 数据来测量学习效果)

### Findings Covered
DATA-001 (评分不测学习效果), DATA-005 (无纵向测试), DATA-006 (评分区分度低)

### Files to Change
- tests/test_s15_quick.py: score_response() 新增 2 个 mastery-based 维度（mastery_progress, knowledge_retention）
- tests/test_longitudinal_learning.py: 新增——teach 10 轮 + 3 轮诊断 → 验证 mastery 上升
- tests/test_s15_full_exhaustive.py: 重新运行全部 256 配置，验证新评分区分度 >15 分（旧 8.9）

### Verification Method
- 新评分维度下 full_stack vs llm_only 差异 ≥4 分（旧 ~3 分）
- 纵向测试验证 mastery_after > mastery_before

### Risk
新增评分维度可能改变原有排名——需与旧评分共存

### Teaching Level Impact
Level 3.6 → Level 3.8 (可验证性建立)

---

## Phase 5: 教学行为差异化 (action_type + 难度双向调节)

### One-Line Goal
8 种 action_type 在 LLM 层面产生真正差异化的教学行为。

### Prerequisites
Phase 2

### Findings Covered
GAP-004 (action_type 差异不足), GAP-006 (难度单向调节), SRC-007 (Birdbrain 选题策略), SRC-009 (Khanmigo Socratic Prompt)

### Files to Change
- src/coach/llm/prompts.py: 每种 action_type 使用独立 prompt 模板（而非一行文字描述）；probe 必须含 expected_answer、scaffold 必须含 step 数组、challenge 必须含 difficulty
- src/coach/composer.py: _adjust_difficulty_up() 新增——当 mastery>0.7 时提高难度
- src/coach/agent.py: compose 调用前从 diagnostic_engine.get_mastery_summary() 选 mastery 最低 topic

### Verification Method
- A/B 评测：验证 scaffold 的 steps 覆盖率 >80%、probe 的 expected_answer 字段非空率 >90%
- 对比 Phase 5 前后的 action_type 分布变化

### Risk
独立 prompt 模板增加 LLM token 消耗

### Teaching Level Impact
Level 3.8 → Level 4.0 (教学行为差异化完成)

---

## Appendix: Future Observation (P3 Items)

- DATA-004 (门禁系统无真实数据): 门禁数据需要从 gate 检查管线实时读取——目前 gate 管线本身是硬编码的。在 gate 系统重构前搁置。

## Appendix: Dropped Items

None — 所有 findings 均通过 constraint check，无 banned 修改。

## Dependency Closure Check

- Phase 1: 无依赖 ✓
- Phase 2: 依赖 Phase 1 ✓
- Phase 3: 依赖 Phase 2 ✓
- Phase 4: 依赖 Phase 3 ✓
- Phase 5: 依赖 Phase 2 ✓
- 无循环依赖 ✓
- 无缺失前置 ✓
