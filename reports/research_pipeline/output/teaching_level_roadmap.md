# Teaching Level Improvement Roadmap

Generated: 2026-05-10T05:00:24.153801+00:00
Pipeline version: v2
Pipeline status: running

## Roadmap Phases

## Phase 1: 核心回路修复（P0 必做）

**One-Line Goal:** 接通已存在但断裂的数据回路：mastery→composer、TTM→action_type、SDT→prompt

**覆盖 9 个 finding:**

### GAP-001: Mastery未反馈至决策
- **问题:** diagnostic_engine.should_and_generate() 计算 mastery 数据，但 agent.py 中仅将其存入 result dict，未传递给 composer 或 prompts 用于调整教学策略。compose() 的 action_type 选择不依赖 mastery。
- **目标:** mastery 数据应流入 compose() 的 action_type 选择逻辑，或直接注入 prompt 上下文，实现低 mastery → 重教，高 mastery → 进阶。
- **代码证据:** agent.py:348-465, composer.py:compose() 参数列表, agent.py:560-605

### GAP-002: TTM策略未影响compose
- **问题:** ttm.assess() 输出 recommended_strategy，但 compose() 的 if/else 链仅基于 action_type 参数，未读取 recommended_strategy。即使 TTM 输出为 None，compose() 行为不变。
- **目标:** compose() 应将 recommended_strategy 作为 action_type 选择的输入之一，实现策略驱动的教学动作。
- **代码证据:** agent.py:348-465, composer.py:compose() 方法体

### GAP-006: Probe结果未闭环
- **问题:** diagnostic_engine.should_and_generate() 触发 probe 后，probe 结果存入 result dict，但下一个 act() 循环未读取该结果来调整教学策略。probe 是单次事件，无后续利用。
- **目标:** probe 结果应写入学生模型，并在后续 act() 中影响 action_type 或 prompt 内容，形成闭环。
- **代码证据:** agent.py:348-465, diagnostic_engine.py:should_and_generate()

### GAP-009: 五步模型仅覆盖执行
- **问题:** act() 方法覆盖了五步模型中的 '执行' 步骤（LLM 生成），但 '感知'（用户状态仅通过 intent 提取）、'决策'（无策略选择）、'评估'（无效果评估）、'更新'（无学生模型更新）均缺失或仅存数据计算无下游消费。
- **目标:** act() 应包含完整的五步循环：感知 → 决策 → 执行 → 评估 → 更新，每一步的数据流必须影响下一步。
- **代码证据:** agent.py:295-681 整体结构

### DATA-001: 评分维度失真
- **问题:** relevance 评分基于响应长度(>100字符=4分)，而非语义相关性。personalization 评分仅检查 sources_count>0，不验证个性化内容。pers_evidence_quality 评分仅检查 sources_count>=1/2。
- **目标:** 评分应基于语义相关性、个性化内容质量、学习适应性等真实教学指标。
- **代码证据:** tests/test_s15_quick.py:46-78; reports/exhaustive_all_configs_report.json

### DATA-002: 无纵向学习测试
- **问题:** grep 搜索 'mastery_after|learning_progress|longitudinal' 在 tests/ 中返回 0 匹配。所有 1275 个测试均为单轮调用→检查输出模式。
- **目标:** 应包含至少一个测试：模拟多轮教学→测量用户技能变化→验证学习效果。
- **代码证据:** grep -rn 'mastery_after|learning_progress|longitudinal' tests/ → 0 matches; pytest tests/ -q → 1275 passed

### DATA-003: 用户模型无历史记录
- **问题:** persistence.py:38-139 get_profile() 返回当前技能值、TTM阶段，但未保存历史变更。无法重建用户学习轨迹。
- **目标:** 应保存技能掌握度历史（时间戳+值）、TTM阶段变迁日志、学习目标记录。
- **代码证据:** src/coach/persistence.py:38-139

### DATA-006: 评测不随学习变化
- **问题:** ultimate_quality_report.json 和 ai_teaching_summary.json 的评分维度与用户学习无关。对从未学习Python的用户重复运行10次，分数不会提升。
- **目标:** 评测应包含学习敏感指标：技能掌握度变化、错误率下降、响应时间缩短等。
- **代码证据:** reports/ultimate_quality_report.json; reports/ai_teaching_summary.json

### DATA-008: 数据流关键组件缺失
- **问题:** grep 搜索 'mastery|competence_signal|flow_channel|bkt|diagnostic_engine|SkillMasteryStore' 在 src/ 中无匹配。无技能掌握度计算、无诊断引擎、无BKT模型。
- **目标:** 应实现技能掌握度追踪、诊断引擎、知识追踪模型（如BKT）以支持学习效果评估。
- **代码证据:** grep -rn 'mastery|competence_signal|flow_channel|bkt|diagnostic_engine|SkillMasteryStore' src/ → 0 matches

---

## Phase 2: 教学行为增强（P1 优先）

**One-Line Goal:** 增强教学差异化：action_type 行为分离、难度双向调节、build_coach_context() 数据注入

**覆盖 17 个 finding:**

### GAP-003: SDT输出未改变prompt
- **问题:** sdt.assess() 输出 behavior_signals，但 build_coach_context() 中 behavior_signals 仅作为字符串拼接，未用于调整 prompt 结构或系统指令。LLM 收到的是原始信号而非策略性引导。
- **目标:** behavior_signals 应影响 SYSTEM_PROMPT 的 instruction 部分，例如检测到 frustration 时切换为鼓励性语气。
- **代码证据:** agent.py:592-681, prompts.py:SYSTEM_PROMPT 模板

### GAP-004: Difficulty档位差异不足
- **问题:** difficulty 有三个档位 easy/medium/hard，但在 prompts.py 中仅作为字符串变量 {difficulty} 插入，无对应的 instruction 分支或示例切换。LLM 输出难以因档位不同而产生可测量差异。
- **目标:** 每个 difficulty 档位应有独立的 instruction 段落、示例难度或约束条件，确保 LLM 输出可区分。
- **代码证据:** prompts.py:SYSTEM_PROMPT 中 {difficulty} 出现位置

### GAP-005: Flow输出未影响响应
- **问题:** flow.compute_flow() 输出 flow_state，但 agent.py 中仅将其存入 result dict，未用于调整 prompt 或 compose 行为。教学节奏无法动态适应。
- **目标:** flow_state 应影响 compose() 的 action_type 选择（如 flow 低 → 减速/复习）或 prompt 中的节奏提示。
- **代码证据:** agent.py:348-465, agent.py:560-605

### GAP-007: 8种action_type同质化
- **问题:** coach_dsl.json 定义了 8 种 action_type，但 compose() 的 if/else 链中，多个 action_type 映射到相同的 payload 结构（如 'explain' 和 'teach' 均返回 explanation 字段），无差异化教学行为。
- **目标:** 每种 action_type 应有独特的 payload 字段和教学意图，例如 'quiz' 应包含问题列表，'explain' 应包含概念分解。
- **代码证据:** contracts/coach_dsl.json, composer.py:compose() 方法体

### GAP-008: 历史记忆未用于决策
- **问题:** build_coach_context() 包含 {history} 和 {memory} 变量，但 agent.py 中无逻辑判断历史中的错误模式或记忆中的知识点覆盖来调整教学策略。历史仅作为上下文传递，无决策影响。
- **目标:** 历史数据应被分析（如错误频率、重复概念），并用于调整 difficulty、action_type 或 prompt 内容。
- **代码证据:** agent.py:592-681, prompts.py:SYSTEM_PROMPT 中 {history} 和 {memory}

### DATA-004: 仪表盘数据为占位符
- **问题:** dashboard_aggregator.py 中 get_progress() 返回 total_sessions=1, total_turns=0，非真实数据。get_ttm_radar() 数据来源不明。
- **目标:** 仪表盘应聚合真实用户交互数据：会话数、轮次、技能变化、学习时长。
- **代码证据:** api/services/dashboard_aggregator.py:get_progress(), get_ttm_radar()

### DATA-005: 管理后台门控状态硬编码
- **问题:** admin.py:45-55 get_gates_status() 中门控状态硬编码为 'pass'，非从真实数据读取。get_audit_logs() 返回空数组。
- **目标:** 门控状态应基于用户实际学习进度和评测结果动态计算。审计日志应记录真实操作。
- **代码证据:** api/routers/admin.py:45-55, line 74

### DATA-007: 无学习目标概念
- **问题:** persistence.py 中用户模型缺少 'learning_goal' 或 'current_objective' 字段。无法追踪用户是否达成学习目标。
- **目标:** 用户模型应包含学习目标（如'掌握Python基础'）、目标分解、完成状态。
- **代码证据:** src/coach/persistence.py:38-139

### DATA-010: 无法用3条SQL重建学习弧
- **问题:** 由于无历史表、无学习目标表、无技能变化表，无法用3条SQL查询重建用户完整学习弧。
- **目标:** 应设计学习弧表：user_skill_history(user_id, skill, value, timestamp)、user_goal_history(user_id, goal, status, timestamp)、user_session_log(user_id, session_id, start, end, outcome)。
- **代码证据:** src/coach/persistence.py:38-139; 综合 DATA-003, DATA-007, DATA-009

### SRC-001: BohdanFL/getmind: BKT集成
- **问题:** BohdanFL/getmind 项目集成了BKT与LLM驱动的RAG和苏格拉底式教学，Coherence缺乏正式的BKT模块。
- **目标:** 参考getmind设计，在persistence.py中实现BKT学生模型或在llm_tutor.py中集成苏格拉底式提示。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

### SRC-002: pyBKT: 成熟知识追踪库
- **问题:** pyBKT (CAHLR/pyBKT) 是一个成熟的知识追踪Python库，提供fit/predict API，MIT许可。Coherence无知识追踪能力。
- **目标:** 将pyBKT作为依赖集成到persistence.py中，用于学生模型的知识追踪。
- **代码证据:** GitHub: CAHLR/pyBKT (stars=253, license=MIT)

### SRC-003: BohdanFL/getmind: PDF自适应学习
- **问题:** getmind项目将静态PDF转换为自适应学习内容，Coherence缺乏PDF解析和自适应学习路径生成管道。
- **目标:** 参考getmind设计，在ingestion.py中实现PDF解析+RAG管道。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

### SRC-004: BohdanFL/getmind: 认知科学原则
- **问题:** getmind显式实现了'Make It Stick'学习原则（检索练习、间隔、交错），Coherence缺乏明确的认知科学框架。
- **目标:** 参考getmind设计，在curriculum.py中实现认知科学原则引擎。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

### SRC-005: BohdanFL/getmind: 苏格拉底式+BKT
- **问题:** getmind将LLM苏格拉底式教学与正式BKT学生模型结合，Coherence的LLM教学未基于概率学生模型。
- **目标:** 在llm_tutor.py中将BKT状态添加到提示上下文中。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

### SRC-006: BohdanFL/getmind: RAG知识库
- **问题:** getmind使用RAG将教学锚定在特定源文档（PDF）中，Coherence的教学未基于可检索的知识库。
- **目标:** 在rag_retriever.py中实现文档分块+检索模块。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

### SRC-007: BohdanFL/getmind: 自适应路径生成
- **问题:** getmind基于学生BKT状态生成自适应学习路径，Coherence遵循固定课程，无自适应路径生成。
- **目标:** 在curriculum.py中实现自适应路径规划器。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

### SRC-008: BohdanFL/getmind: ITS架构
- **问题:** getmind被设计为正式的智能教学系统（ITS），Coherence是通用LLM教学系统，缺乏ITS架构。
- **目标:** 参考getmind架构，重构模块结构以包含学生模型、教学模型、领域模型等ITS组件。
- **代码证据:** GitHub: BohdanFL/getmind (stars=0, license=unknown)

---

## Phase 3: 评测与可观测性（P2 规划）

**One-Line Goal:** 升级评测体系、持久化学习轨迹、仪表盘真实化

**覆盖 2 个 finding:**

### GAP-010: Pipeline治理非教学
- **问题:** agent.py:705-737 的 pipeline governance 逻辑仅检查安全性和合规性，未涉及教学质量评估或教学策略调整。
- **目标:** pipeline governance 应包含教学质量门控，例如 mastery 阈值检查、学习进度验证，确保输出符合教学目标。
- **代码证据:** agent.py:705-737

### DATA-009: TTM阶段无趋势记录
- **问题:** persistence.py 中 TTM 阶段仅保存当前值，无历史变迁记录。无法分析用户动机变化趋势。
- **目标:** 应保存 TTM 阶段变迁日志（时间戳+阶段），支持动机变化分析。
- **代码证据:** src/coach/persistence.py:38-139

---

