# System State Report

Generated: 2026-05-10T05:00:24.153801+00:00


### Mastery未反馈至决策
- Current: diagnostic_engine.should_and_generate() 计算 mastery 数据，但 agent.py 中仅将其存入 result dict，未传递给 composer 或 prompts 用于调整教学策略。compose() 的 action_type 选择不依赖 mastery。
- Target: mastery 数据应流入 compose() 的 action_type 选择逻辑，或直接注入 prompt 上下文，实现低 mastery → 重教，高 mastery → 进阶。
- Evidence: agent.py:348-465, composer.py:compose() 参数列表, agent.py:560-605

### TTM策略未影响compose
- Current: ttm.assess() 输出 recommended_strategy，但 compose() 的 if/else 链仅基于 action_type 参数，未读取 recommended_strategy。即使 TTM 输出为 None，compose() 行为不变。
- Target: compose() 应将 recommended_strategy 作为 action_type 选择的输入之一，实现策略驱动的教学动作。
- Evidence: agent.py:348-465, composer.py:compose() 方法体

### SDT输出未改变prompt
- Current: sdt.assess() 输出 behavior_signals，但 build_coach_context() 中 behavior_signals 仅作为字符串拼接，未用于调整 prompt 结构或系统指令。LLM 收到的是原始信号而非策略性引导。
- Target: behavior_signals 应影响 SYSTEM_PROMPT 的 instruction 部分，例如检测到 frustration 时切换为鼓励性语气。
- Evidence: agent.py:592-681, prompts.py:SYSTEM_PROMPT 模板

### Difficulty档位差异不足
- Current: difficulty 有三个档位 easy/medium/hard，但在 prompts.py 中仅作为字符串变量 {difficulty} 插入，无对应的 instruction 分支或示例切换。LLM 输出难以因档位不同而产生可测量差异。
- Target: 每个 difficulty 档位应有独立的 instruction 段落、示例难度或约束条件，确保 LLM 输出可区分。
- Evidence: prompts.py:SYSTEM_PROMPT 中 {difficulty} 出现位置

### Flow输出未影响响应
- Current: flow.compute_flow() 输出 flow_state，但 agent.py 中仅将其存入 result dict，未用于调整 prompt 或 compose 行为。教学节奏无法动态适应。
- Target: flow_state 应影响 compose() 的 action_type 选择（如 flow 低 → 减速/复习）或 prompt 中的节奏提示。
- Evidence: agent.py:348-465, agent.py:560-605

### Probe结果未闭环
- Current: diagnostic_engine.should_and_generate() 触发 probe 后，probe 结果存入 result dict，但下一个 act() 循环未读取该结果来调整教学策略。probe 是单次事件，无后续利用。
- Target: probe 结果应写入学生模型，并在后续 act() 中影响 action_type 或 prompt 内容，形成闭环。
- Evidence: agent.py:348-465, diagnostic_engine.py:should_and_generate()

### 8种action_type同质化
- Current: coach_dsl.json 定义了 8 种 action_type，但 compose() 的 if/else 链中，多个 action_type 映射到相同的 payload 结构（如 'explain' 和 'teach' 均返回 explanation 字段），无差异化教学行为。
- Target: 每种 action_type 应有独特的 payload 字段和教学意图，例如 'quiz' 应包含问题列表，'explain' 应包含概念分解。
- Evidence: contracts/coach_dsl.json, composer.py:compose() 方法体

### 历史记忆未用于决策
- Current: build_coach_context() 包含 {history} 和 {memory} 变量，但 agent.py 中无逻辑判断历史中的错误模式或记忆中的知识点覆盖来调整教学策略。历史仅作为上下文传递，无决策影响。
- Target: 历史数据应被分析（如错误频率、重复概念），并用于调整 difficulty、action_type 或 prompt 内容。
- Evidence: agent.py:592-681, prompts.py:SYSTEM_PROMPT 中 {history} 和 {memory}

### 五步模型仅覆盖执行
- Current: act() 方法覆盖了五步模型中的 '执行' 步骤（LLM 生成），但 '感知'（用户状态仅通过 intent 提取）、'决策'（无策略选择）、'评估'（无效果评估）、'更新'（无学生模型更新）均缺失或仅存数据计算无下游消费。
- Target: act() 应包含完整的五步循环：感知 → 决策 → 执行 → 评估 → 更新，每一步的数据流必须影响下一步。
- Evidence: agent.py:295-681 整体结构

### Pipeline治理非教学
- Current: agent.py:705-737 的 pipeline governance 逻辑仅检查安全性和合规性，未涉及教学质量评估或教学策略调整。
- Target: pipeline governance 应包含教学质量门控，例如 mastery 阈值检查、学习进度验证，确保输出符合教学目标。
- Evidence: agent.py:705-737

### 评分维度失真
- Current: relevance 评分基于响应长度(>100字符=4分)，而非语义相关性。personalization 评分仅检查 sources_count>0，不验证个性化内容。pers_evidence_quality 评分仅检查 sources_count>=1/2。
- Target: 评分应基于语义相关性、个性化内容质量、学习适应性等真实教学指标。
- Evidence: tests/test_s15_quick.py:46-78; reports/exhaustive_all_configs_report.json

### 无纵向学习测试
- Current: grep 搜索 'mastery_after|learning_progress|longitudinal' 在 tests/ 中返回 0 匹配。所有 1275 个测试均为单轮调用→检查输出模式。
- Target: 应包含至少一个测试：模拟多轮教学→测量用户技能变化→验证学习效果。
- Evidence: grep -rn 'mastery_after|learning_progress|longitudinal' tests/ → 0 matches; pytest tests/ -q → 1275 passed

### 用户模型无历史记录
- Current: persistence.py:38-139 get_profile() 返回当前技能值、TTM阶段，但未保存历史变更。无法重建用户学习轨迹。
- Target: 应保存技能掌握度历史（时间戳+值）、TTM阶段变迁日志、学习目标记录。
- Evidence: src/coach/persistence.py:38-139

### 仪表盘数据为占位符
- Current: dashboard_aggregator.py 中 get_progress() 返回 total_sessions=1, total_turns=0，非真实数据。get_ttm_radar() 数据来源不明。
- Target: 仪表盘应聚合真实用户交互数据：会话数、轮次、技能变化、学习时长。
- Evidence: api/services/dashboard_aggregator.py:get_progress(), get_ttm_radar()

### 管理后台门控状态硬编码
- Current: admin.py:45-55 get_gates_status() 中门控状态硬编码为 'pass'，非从真实数据读取。get_audit_logs() 返回空数组。
- Target: 门控状态应基于用户实际学习进度和评测结果动态计算。审计日志应记录真实操作。
- Evidence: api/routers/admin.py:45-55, line 74

### 评测不随学习变化
- Current: ultimate_quality_report.json 和 ai_teaching_summary.json 的评分维度与用户学习无关。对从未学习Python的用户重复运行10次，分数不会提升。
- Target: 评测应包含学习敏感指标：技能掌握度变化、错误率下降、响应时间缩短等。
- Evidence: reports/ultimate_quality_report.json; reports/ai_teaching_summary.json

### 无学习目标概念
- Current: persistence.py 中用户模型缺少 'learning_goal' 或 'current_objective' 字段。无法追踪用户是否达成学习目标。
- Target: 用户模型应包含学习目标（如'掌握Python基础'）、目标分解、完成状态。
- Evidence: src/coach/persistence.py:38-139

### 数据流关键组件缺失
- Current: grep 搜索 'mastery|competence_signal|flow_channel|bkt|diagnostic_engine|SkillMasteryStore' 在 src/ 中无匹配。无技能掌握度计算、无诊断引擎、无BKT模型。
- Target: 应实现技能掌握度追踪、诊断引擎、知识追踪模型（如BKT）以支持学习效果评估。
- Evidence: grep -rn 'mastery|competence_signal|flow_channel|bkt|diagnostic_engine|SkillMasteryStore' src/ → 0 matches

### TTM阶段无趋势记录
- Current: persistence.py 中 TTM 阶段仅保存当前值，无历史变迁记录。无法分析用户动机变化趋势。
- Target: 应保存 TTM 阶段变迁日志（时间戳+阶段），支持动机变化分析。
- Evidence: src/coach/persistence.py:38-139

### 无法用3条SQL重建学习弧
- Current: 由于无历史表、无学习目标表、无技能变化表，无法用3条SQL查询重建用户完整学习弧。
- Target: 应设计学习弧表：user_skill_history(user_id, skill, value, timestamp)、user_goal_history(user_id, goal, status, timestamp)、user_session_log(user_id, session_id, start, end, outcome)。
- Evidence: src/coach/persistence.py:38-139; 综合 DATA-003, DATA-007, DATA-009
