# Shared State — Coherence Research Pipeline

## Execution Log

| Time | Agent | Action | Status |
|------|-------|--------|--------|
| T1 | A0 | Pipeline initialized | started |
| T2 | A1 | Agent 1 started — Code Audit 5 files | in_progress |
| T3 | A1 | 7 GAP findings written | converged |

## Agent Status

| Agent | Status | Findings | Iterations |
|-------|--------|----------|------------|
| A1 | converged | 7 (GAP-001~007) | 3 rounds |
| A2 | pending | - | - |
| A3 | pending | - | - |
| A4 | pending | - | - |
| A5 | pending | - | - |
| A6 | pending | - | - |
| A7 | pending | - | - |

## Fact Base (预验证事实)

FB-001: config/coach_defaults.yaml 默认 ttm.enabled=false, sdt.enabled=false, flow.enabled=false, diagnostic_engine.enabled=false, llm.enabled=true
FB-002: contracts/ 目录 13 份 JSON 全部 status=frozen, 禁止修改
FB-003: src/inner/**, src/middle/**, src/outer/** 禁止修改
FB-004: 全量测试 1275 passed (Phase 17 基线)

---

## Findings Pool

### AGENT 1: Code Audit (GAP)

---
Finding ID: GAP-001
Title: 诊断→决策断路
File: src/coach/agent.py:570-611
Current State: diagnostic_result 在第575行初始化为 None，从未被赋值。process_turn() 和 should_and_generate() 虽在 act() 中被调用，但其返回值（diagnostic_result, diagnostic_probe）从未流入 compose() 或 build_coach_context()。difficulty_contract 仅检查 hasattr(self, 'diagnostic_engine')（line 610）——一个二元存在性检查，不读取实际 mastery 数据。
Gap: 诊断引擎的 mastery 输出（BKT 掌握度）应被 composer 消费以调整难度和策略选择。家教级系统会在用户掌握度 < 0.3 时自动降低难度或切换到"重教"模式。
Impact: 即使用户经过 10 轮诊断题全部答错，系统的教学策略和难度不会自动调整。BKT 追踪被"存了不用"。
Evidence: agent.py:570 `current_difficulty = "medium"` 硬编码；line 608-611 difficulty_contract 只检查 hasattr 不读 mastery。
Severity: critical
Self-Check-1: YES (line 570-611)
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---
Finding ID: GAP-002
Title: 难度调节断路(LLM)
File: src/coach/agent.py:570, src/coach/llm/prompts.py:28,88
Current State: composer.compose() 可通过 flow_result["adjust_difficulty"] 调整 payload["difficulty"]（composer.py:80-87）。但 act() 中的 LLM 生成路径从未将 payload 的 difficulty 传递给 build_coach_context()。prompts.py:28 的 {difficulty} 占位符需要外部传入，但 act() 行 570 硬编码 current_difficulty = "medium"。
Gap: LLM prompt 的 {difficulty} 变量始终为 "medium"。"easy=简化解释多用类比" 和 "hard=深入原理减少铺垫" 两条路径从未被实际使用。
Impact: 用户在心流"无聊"通道（需提高难度）或"焦虑"通道（需降低难度）时，LLM 生成内容难度不变。
Evidence: prompts.py:88 difficulty 参数默认值 "medium"；agent.py:570 硬编码。
Severity: major
Self-Check-1: YES
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---
Finding ID: GAP-003
Title: 评估→更新回路缺失
File: src/coach/agent.py:366-372 (TTM), 379-387 (SDT), 570-575 (result)
Current State: TTM.assess() 输入只含 cognitive_indicators、behavioral_indicators、session_count。SDT.assess() 输入只含 rewrite_rate、excursion_use_count、initiation_rate、no_assist_scores。两者都不接受 DiagnosticEngine 的 mastery 数据。get_mastery_summary()、get_competence_signal() 方法存在但未被任何调用方使用。
Gap: 五步模型的"评估→更新"回路断裂——步骤 4（评估效果）产出了 mastery 数据，但步骤 5（更新学生模型）只更新了 SkillMasteryStore 内部状态，不更新 TTM 阶段或 SDT 动机值。
Impact: TTM 可能永远停留在"contemplation"，因为阶段检测不参考用户的真实技能掌握度。
Evidence: agent.py:366-372 TTM assess 无 mastery 参数；get_competence_signal() 在 diagnostic_engine.py:365-370 定义但 agent.py 全文无引用。
Severity: critical
Self-Check-1: YES
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---
Finding ID: GAP-004
Title: action_type 行为差异不足
File: contracts/coach_dsl.json:8-57, src/coach/composer.py:119-132, src/coach/llm/prompts.py:65-74
Current State: 8 个 action_type 在 composer 层有不同 payload 结构，但在 LLM prompt 层全部映射到 ACTION_STRATEGIES 字典中的一句文本描述（如 "suggest: 轻柔建议"）。probe/challenge/reflect/scaffold 的 payload 差异在 build_coach_context() 中被忽略——prompt 只用 {action_type_strategy} 和 {behavior_signals}。
Gap: coach_dsl.json 定义了 "lesson", "objective", "curriculum", "progress" 等教学概念全部缺失。8 个 action_type 在 LLM 眼中的差异仅是 prompt 中的一行文字描述。
Impact: 所有 8 种 action_type 在实际 LLM 输出中可能产生类似内容。
Evidence: prompts.py:65-74 ACTION_STRATEGIES 仅一行文字；composer.py:122-132 _build_payload 仅设置字段名不设置行为差异。
Severity: major
Self-Check-1: YES
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---
Finding ID: GAP-005
Title: 学习历史永久为空
File: src/coach/agent.py:571-572, 603-606, src/coach/llm/prompts.py:47-51
Current State: act() 第571-572行初始化 s4_history = [] 和 s4_memory = []。这两个变量从未被赋值。personalization_evidence 在 line 603-606 检查 s4_history 或 s4_memory 非空，但始终为 None。prompts.py:48 的 {history} 和 line 51 的 {covered_topics} 始终为"新用户，无历史学习记录"。
Gap: 用户的完整学习历史在 LLM prompt 中不可见。系统每次对话都是"第一次见用户"。
Impact: LLM 无法引用用户之前学过的内容、无法检测重复教学、无法识别知识缺口。
Evidence: agent.py:571 `s4_history: list = []`；line 603-606 始终 None。
Severity: critical
Self-Check-1: YES
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---
Finding ID: GAP-006
Title: 难度单向调节
File: src/coach/composer.py:76-77, 80-87, 135-141
Current State: SDT advice 的 adjust_difficulty 只实现 "lower"（composer.py:76-77 和 _adjust_difficulty_down:135-141）。没有 "raise_difficulty" 路径。心流的 adjust_difficulty 可以双向调节（composer.py:80-87），但需要 flow.enabled=true（默认 false）。
Gap: 默认配置下系统只能降低难度，不能提高难度。难度调节是单向的。
Impact: 长期使用后教学内容会因频繁触发 "lower" 而持续变容易，用户会感到无聊。
Evidence: composer.py:76-77 只检查 adjust_difficulty == "lower"。
Severity: major
Self-Check-1: YES
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---
Finding ID: GAP-007
Title: 无学习目标/课程概念
File: contracts/coach_dsl.json:58-82, src/coach/persistence.py:19-33, src/coach/agent.py:301
Current State: coach_dsl.json 的 required_fields 仅含 action_type/payload/trace_id/intent/domain_passport。没有 "learning_goal"、"curriculum"、"objective"、"progress" 概念。persistence.py profiles 表没有 "current_learning_goal" 字段。agent.py act() 无 goal 参数。
Gap: 系统完全不知道"用户想学什么"。每次对话都是独立、无目标的交互。家教的第一步"设定学习目标"完全缺失。
Impact: 用户使用系统一个月后，系统无法回答"我学会了什么"或"我还应该学什么"。
Evidence: coach_dsl.json 无学习目标定义；persistence.py 无 goal 字段；agent.py act() 无 goal 参数。
Severity: critical
Self-Check-1: YES
Self-Check-2: YES
Self-Check-3: DIRECT
Status: draft_final

---

## A1 Iteration Log

A1 | ITER | 第1轮 | 发现: GAP-001,GAP-002,GAP-003 | 框架: 五步模型覆盖度分析 (agent.py act() 全链)
A1 | ITER | 第2轮 | 发现: GAP-004,GAP-005 | 调整: 补充 composer.py 决策逻辑 + prompts.py LLM 注入深度分析
A1 | ITER | 第3轮 | 发现: GAP-006,GAP-007 | 自省: 全部自检通过，当前分析路径边际收益已低于阈值 → converged

Agent 1 | STATUS | converged | 总发现数: 7 | 总迭代轮数: 3

---

### AGENT 2: Data Audit (DATA)

---
Finding ID: DATA-001
Title: 评分体系测回答质量而非学习效果
Location: tests/test_s15_quick.py:46-78, reports/exhaustive_all_configs_report.json:dimension_averages
Current State: relevance 按回答长度评分（>100 chars=4分），personalization 按 personalization_evidence.sources_count>0 评分（字段存在=得分），pers_evidence_quality 按 sources_count>=1/2 评分。6 个维度中有 4 个基于回答文本的表面特征，无一个基于用户学习效果（如"10轮后答对率""知识保留率"）。
Impact: 如果对一个从不学 Python 的用户跑 10 次评测，分数仍会提高（因为评分只测回答文本质量，不测学习效果）。这使得当前的评测体系无法回答最核心的问题："用户进步了吗？"
Target State: 评测体系应包含"学习效果"维度——如诊断题答对率变化趋势、同一 topic 多次提问后的回答深度变化、知识保留测试。
Severity: critical
Verification Method: 读 test_s15_quick.py score_response() 函数 (line 46-78)，确认所有维度评分逻辑不依赖任何用户状态变化。
Self-Check-1: YES (test_s15_quick.py:46-78)
Self-Check-2: YES (解决此缺口可直接证明系统对学习效果的贡献)
Status: draft_final

---
Finding ID: DATA-002
Title: 用户模型无历史趋势
Location: src/coach/persistence.py:19-33, 114-125
Current State: profiles 表存储当前值（ttm_stage、autonomy、competence、relatedness、skill_masteries JSON 字符串），但不存储历史值。get_profile() 返回当前快照。没有 ttm_stage_history 表、没有 mastery_over_time 时间序列、没有 topic_progress 趋势数据。
Impact: 无法回答"用户从 contemplation 到 action 花了多少轮？"、"Python 变量的掌握度从 0.3 到 0.7 用了多少次诊断？"——即无法绘制学习曲线。
Target State: 应增加 profiles_history 表或 time-series 存储，记录每次变更的时间戳和旧值→新值。
Severity: major
Verification Method: 读 persistence.py 完整 schema，确认无历史表；SQL: SELECT sql FROM sqlite_master WHERE name LIKE '%history%' 返回空。
Self-Check-1: YES (persistence.py:19-33)
Self-Check-2: YES (可以画学习曲线是证明教学效果的必需能力)
Status: draft_final

---
Finding ID: DATA-003
Title: Dashboard 数据全部是假的
Location: api/services/dashboard_aggregator.py:50-111, api/routers/admin.py:38-74
Current State: get_ttm_radar() 每次创建 NEW TTMStateMachine 并喂入硬编码值（cognitive=0.5, behavioral=0.5, session_count=1）——完全不是从真实用户会话加载。get_sdt_rings() 同样用 rewrite_rate=0.5、excursion_use_count=0 创建新 SDTAssessor。get_progress() 返回 total_turns=0 硬编码。get_audit_logs() 返回空数组。8 个门禁 gate status 全部硬编码 "pass"。
Impact: 前端仪表盘展示的 TTM 雷达图、SDT 能量环、学习进度、门禁状态全部是假数据。用户看到的"学习进度"和真实的用户学习状态完全脱节。
Target State: Dashboard 应通过 persistence.py 从 SQLite 读取真实用户数据，而非每次创建新对象喂入默认值。
Severity: critical
Verification Method: 读 dashboard_aggregator.py line 55-68 — 每次调用创建新 TTMStateMachine(ttm_cfg)，输入 [0.5] 硬编码。line 104-111 get_progress() 返回 total_turns=0。
Self-Check-1: YES
Self-Check-2: YES (修复后前端可显示真实学习进度)
Status: draft_final

---
Finding ID: DATA-004
Title: 门禁系统无真实数据
Location: api/routers/admin.py:45-55, 63-74
Current State: get_gates_status() 返回 8 个 GateStatusItem，全部 status="pass"，无实际 metric 值。get_audit_logs() 返回空数组 (logs=[], total=0)。门禁系统作为 Coherence 的核心安全机制，其管理面板展示的是完全虚构的"全绿"。
Impact: 如果某道门禁实际应该触发 FAIL（如 Agency Gate 检测到 premise_rewrite_rate 异常），管理员从前端看不到任何告警。
Target State: Gate 状态应从真实门禁检查结果读取，audit_logs 应查询实际审计日志存储。
Severity: major
Verification Method: admin.py:46-53 全部 hardcoded status="pass"；line 74 logs=[] hardcoded。
Self-Check-1: YES
Self-Check-2: YES (管理面板的真实性直接影响系统运维能力)
Status: draft_final

---
Finding ID: DATA-005
Title: 测试全部是单轮模式无纵向评测
Location: tests/ directory (79 files, ~1275 tests)
Current State: 全部 1275 个测试都是"单次 act() 调用 → 检查返回值"模式。tests/test_long_conversation.py 有 3 用户 × 18-20 轮，但只检查每轮的输出格式（ttm_stage/sdt_profile 字段存在性），不检查"经过 N 轮教学后用户是否学会了"。test_s15_quick.py/test_s15_full_exhaustive.py 的评分也只是单轮质量评分。
Impact: 即使修改 composer 让系统每次都输出"你好"，只要输出格式正确，1275 个测试也全部通过。没有测试验证"教学是否有效"。
Target State: 应增加纵向测试——在多轮对话后验证：诊断题答对率上升、用户从"不知道"变为"能正确回答"、BKT mastery 随时间上升。
Severity: critical
Verification Method: 搜索 tests/ 目录 — 无任何测试包含 "before vs after" 对比、无 "learning_progress" 断言、无 "mastery_increased" 检查。
Self-Check-1: YES (全量测试搜索结果)
Self-Check-2: YES (有纵向测试才能验证教学系统的核心价值)
Status: draft_final

---
Finding ID: DATA-006
Title: 256 配置组合评分区分度低
Location: reports/exhaustive_all_configs_report.json:top_10, bottom_10
Current State: top_10 最高分 20.2，bottom_10 最低分 11.3，极差仅 8.9 分（满分 24）。top_10 内部差异仅 2 分（20.2→18.2）。full_stack 排名第 1 (20.2) 与 llm_only 的差异被淹没在噪声中。256 种配置中多数评分接近均值 15.6。
Impact: 评分体系无法有效区分"好的教学"和"差的教学"。增强个性化（TTM+SDT+Flow+Diag）最多只能带来 1-2 分的提升（约 5-10%），这个差异在统计上可能不显著。
Target State: 需要更能反映"学习效果"的评分维度——如诊断题答对率、知识保留率、学习速度——这些维度的区分度应远高于文本质量维度。
Severity: major
Verification Method: exhaustive_all_configs_report.json: overall_avg_quality=15.6, top_10 全部集中在 18.2-20.2 区间。
Self-Check-1: YES
Self-Check-2: YES (提高评分区分度可直接验证教学改进的有效性)
Status: draft_final

## A2 Iteration Log

A2 | ITER | 第1轮 | 发现: DATA-001,DATA-002,DATA-003 | 框架: 评测体系→用户模型→可观测性
A2 | ITER | 第2轮 | 发现: DATA-004,DATA-005,DATA-006 | 调整: 补充 admin 和测试体系深度分析
A2 | ITER | 关联检查: DATA-003 与 GAP-005 强关联(CONFIRMS)——学习历史永久为空导致 dashboard 只能用假数据；DATA-005 与 GAP-003 关联(EXTENDS)——评估体系缺失使"评估→更新"回路不可验证
A2 | ITER | 第3轮 | 自省: 全部自检通过，6 条 findings 覆盖全部 4 个审计任务 → converged

Agent 2 | STATUS | converged | 总发现数: 6 | 总迭代轮数: 3

---

### AGENT 3: Market Research (SRC)

---
Source Type: GitHub
Name: pyBKT — Bayesian Knowledge Tracing (CAHLR/pyBKT)
Stars: ~249
Latest Commit: March 2025
License: MIT
What It Has That Coherence Doesn't: 完整的 BKT 参数估计 pipeline（prior/learn/guess/slip）+ scikit-learn API（fit/predict/evaluate/crossvalidate）+ 多种扩展（forgets/multiprior/multigs/multilearn）。Coherence 有 BKTEngine 但仅用于 DiagnosticEngine 内部，缺少独立的参数拟合和交叉验证能力。
Reusability: partial code reuse — pyBKT 的 params fitting 逻辑可直接替代 Coherence 的硬编码 BKT 参数
Coherence File Match: src/coach/flow.py (BKTEngine), src/coach/diagnostic_engine.py (SkillMasteryStore)
Confidence: high
Status: draft_final

---
Source Type: GitHub
Name: pyKT-toolkit (pykt-team/pykt-toolkit)
Stars: ~592
Latest Commit: 2024 (active)
License: MIT
What It Has That Coherence Doesn't: 10+ 深度学习 KT 模型（DKT/DKVMN/AKT/SAINT/sparseKT/stableKT/ReKT）+ 统一评测框架 + benchmark 数据集加载器。Coherence 的 BKT 是单模型，无模型对比能力。
Reusability: design reference — 模型对比框架可参考，但 Coherence 不需要 DL 模型
Coherence File Match: tests/test_s15_quick.py (评测框架)，src/coach/flow.py (BKTEngine)
Confidence: medium
Status: draft_final

---
Source Type: GitHub
Name: OATutor-LLM-Learner (CAHLR/OATutor-LLM-Learner)
Stars: ~50
Latest Commit: 2024
License: Open Source
What It Has That Coherence Doesn't: 完整的自适应辅导系统——BKT 实时 mastery 估计 → 自适应选题 → 脚手架提示 → 渐进式干预。Coherence 有 BKT 但没有"基于 mastery 选择下一道题/话题"的能力。
Reusability: design reference — 自适应选题逻辑（"选用户 mastery 最低的 skill 出题"）可直接参考
Coherence File Match: src/coach/composer.py (教学策略选择), src/coach/diagnostic_engine.py (_select_candidate_skill)
Confidence: high
Status: draft_final

---
Source Type: Paper
Title: A Systematic Review of Knowledge Tracing and Large Language Models in Education: Opportunities, Issues, and Future Research
Authors: Yongwan Cho et al.
DOI/arXiv: arXiv:2412.09248 (Dec 2024)
Core Claim: "LLMs can enhance KT performance via in-context learning, agent-based approaches, and solving cold-start problems. However, studies are heavily dependent on structured limited datasets."
My Insight: LLMs 不应替代 BKT，而应为 BKT 提供"语义理解"层——用 LLM 理解用户回答的语义质量（而非仅关键词匹配），然后喂给 BKT 做数学推理。这正好是 Coherence 可以做但没做的：DiagnosticEngine._keyword_evaluate() 是关键词匹配兜底，但 LLM 评估才是主路径。
Applicability to Coherence: high
Confidence: high — directly applicable
Status: draft_final

---
Source Type: Paper
Title: Exploring Knowledge Tracing in Tutor-Student Dialogues using LLMs
Authors: Alexander Scarlatos et al. (UMass Amherst)
DOI/arXiv: arXiv:2409.16490 (Sep 2024, LAK 2025)
Core Claim: "LLMKT significantly outperforms existing KT methods in predicting student response correctness on tutoring dialogue datasets."
My Insight: LLM 可以直接从对话文本中推断知识掌握度，不需要 explicit quiz。Coherence 的 chat 对话就是天然的 tutoring dialogue——但当前只靠 BKT 的二元 correct/incorrect 更新。如果接入 LLM 评估每一轮用户回答的正确性和理解深度，可以大幅提高 mastery 更新频率和精度。
Applicability to Coherence: high
Confidence: high
Status: draft_final

---
Source Type: Paper
Title: A Comprehensive Survey and Taxonomy on Large Language Model-Based Knowledge Tracing
Authors: Sunwoo Park, Hyeoncheol Kim (Korea University)
DOI/arXiv: ITS 2025 Conference
Core Claim: "Three-category taxonomy for LLM-based KT: LLM-enhanced, LLM-integrated, and LLM-standalone."
My Insight: Coherence 当前处于"LLM-standalone"和"LLM-enhanced"之间——BKT 独立运行，LLM 生成教学内容但两者互不相通。最可行的升级路径是"LLM-enhanced KT"——用 LLM 理解对话内容、提取知识点、判断回答质量，然后将这些作为 BKT 的观测输入。
Applicability to Coherence: high
Confidence: high
Status: draft_final

---
Source Type: Product
Name: Duolingo — Birdbrain 个性化引擎
Feature: ML 模型实时预测每位用户对每道题的正确概率 P(correct | user, exercise)
How It Works: 基于数十亿练习痕迹训练的预测模型 → Session Generator 选"最近发展区"难度(~80%正确率)的练习 → 用户答完反馈给模型。自研半衰期回归(HLR)算法结合 Ebbinghaus 遗忘曲线。
Technical Depth: implementable — Coherence 可以用 BKT mastery 值替代 Birdbrain 的预测概率，然后在 composer 中选 mastery 最低的 topic 出题
Coherence Counterpart: src/coach/diagnostic_engine.py (SkillMasteryStore), src/coach/composer.py (教学策略)
Confidence: confirmed — multiple sources (IEEE Spectrum, Duolingo blog)
Source URLs: https://blog.duolingo.com/learning-how-to-help-you-learn-introducing-birdbrain/
Status: draft_final

---
Source Type: Product
Name: Carnegie Learning MATHia — 认知导师
Feature: Model-Tracing：追踪解题每一步操作 → 与专家模型比对 → 即时识别错误模式
How It Works: ACT-R 认知架构 → 将数学知识分解为产生式规则 → BKT/DKT 双模型追踪每技能的 mastery → LiveLab 教师仪表盘实时监控。不只看答案对错，而是追踪解题过程。
Technical Depth: design reference — Model-Tracing 的思路可用于 Coherence：不只看用户回答的最终结果，而是分析解题步骤找出具体的 knowledge gap
Coherence Counterpart: src/coach/diagnostic_engine.py (评估), api/services/dashboard_aggregator.py (仪表盘)
Confidence: confirmed
Source URLs: https://discover.carnegielearning.com/meet-mathia
Status: draft_final

---
Source Type: Product
Name: Khan Academy — Khanmigo
Feature: Socratic Tutor：GPT-4 + 多层 prompt 工程 → 不直接给答案，引导用户自己发现
How It Works: Prompt 核心指令 "You are a Socratic tutor" — 每个使用场景单独微调 prompt → 自建评估流水线检查 prompt 效果 → Langfuse 可观测性平台追踪每次 AI 交互。Go 后端 + 图像输入 + 实时白板。
Technical Depth: concept — Socratic 引导已经是 Coherence 的 reflect action_type 的意图，但 prompt 层面没有系统化的 Socratic 引导策略
Coherence Counterpart: src/coach/llm/prompts.py (SYSTEM_PROMPT)
Confidence: confirmed
Source URLs: https://python-sdk-v2.docs-snapshot.langfuse.com/customers/khan-academy/
Status: draft_final

---
Source Type: Blog
Name: Duolingo — Half-Life Regression (ACL 2016 工程化)
Insight: 将 Ebbinghaus 遗忘曲线参数化为 ML 模型，预测每个单词的"记忆半衰期"，结合 spaced repetition 实现 45%+ 错误率降低和 12% 日活提升。开源代码+13M 数据：github.com/duolingo/halflife-regression
Coherence File Match: src/coach/flow.py (BKTEngine), src/coach/persistence.py (用户模型)
Confidence: high
Source URL: https://github.com/duolingo/halflife-regression
Status: draft_final

---
Source Type: Blog
Name: Khan Academy — Langfuse LLM 可观测性
Insight: 用 Langfuse 追踪每次 GPT-4 交互——7 个产品团队+4 个基础设施团队共用，内部 UI 直接链接 trace → 团队可查看用户体验全链路。Coaching 系统的 LLM 调用同样需要可观测性，但当前 Coherence 的 LLM 调用（src/coach/llm/client.py）没有 trace/dashboard。
Coherence File Match: src/coach/llm/client.py (LLMClient)
Confidence: medium
Source URL: https://langfuse.com/customers/khan-academy
Status: draft_final

---
Source Type: Blog
Name: Duolingo Engineering — A/B Testing Infrastructure for Birdbrain
Insight: 个性化模型的 A/B 测试导致 DynamoDB 成本翻倍 → 实现内存缓冲+LRU 淘汰策略 → 50% 成本降低。Coherence 的 S15/S17 A/B 评测是脚本式的（每次重跑全部配置），如果要在生产环境中持续追踪多个策略变体的效果，需要类似的轻量级基础设施。
Coherence File Match: tests/test_s15_quick.py (评测框架), src/coach/mrt.py (微随机实验)
Confidence: medium
Source URL: https://blog.duolingo.com/ (May 2024 engineering post)
Status: draft_final

## A3 Iteration Log

A3 | ITER | 第1轮 | 发现: SRC-001~SRC-005 (GitHub+Paper 初搜) | 框架: 四类来源覆盖率检查
A3 | ITER | 第2轮 | 发现: SRC-006~SRC-009 (Product 深度分析) | 调整: 补充 Khanmigo/Duolingo/MATHia 技术架构对比
A3 | ITER | 第3轮 | 发现: SRC-010~SRC-012 (Blog 工程实践) | 自省: 四类来源全部≥2条，每条有 Coherence File Match → converged

Agent 3 | STATUS | converged | 总发现数: 12 | 总迭代轮数: 3

---

## Structured Debate (Agent 1 ↔ Agent 2)

### Agent 1 → Agent 2 CRITIQUES

CRITIQUE | DATA-001 | Agent 1 → Agent 2
Type: agree
Rationale: 评分体系测"回答质量"而非"学习效果"——代码层面完全验证。test_s15_quick.py score_response() 全部基于单轮文本特征（长度、字段存在），不包含任何跨轮对比。GAP-005（学习历史为空）和 DATA-005（无纵向测试）从不同角度确认了同一个根因。
Code Evidence: agent.py:571 s4_history=[] 硬编码 — 这解释了为什么评分只能测单轮质量：因为没有历史数据可供评分函数读取。

CRITIQUE | DATA-003 | Agent 1 → Agent 2
Type: agree
Rationale: Dashboard 数据是假的一一与 GAP-005 形成连锁：学习历史永久为空 → dashboard 无法从 persistence 读真实数据 → 只能每次创建新 TTMStateMachine 喂入硬编码值。这不是 dashboard 的问题，是上游数据管道断了。
Code Evidence: agent.py:571-572 s4_history/s4_memory 从未赋值；dashboard_aggregator.py:55-68 每次 new TTMStateMachine(cfg) 输入 [0.5] 硬编码。

CRITIQUE | DATA-006 | Agent 1 → Agent 2
Type: agree
Rationale: 256 config 评分区分度低——代码层面的解释是 GAP-004：8 个 action_type 在 LLM prompt 层的差异仅是一行文字描述。如果所有配置在 LLM 眼中"看起来差不多"，评分自然趋近均值。
Code Evidence: prompts.py:65-74 ACTION_STRATEGIES 每种仅一行文字；composer.py:119-132 _build_payload 只设置字段名。

CRITIQUE | DATA-002 | Agent 1 → Agent 2
Type: agree
Rationale: 用户模型无历史趋势——GAP-003 从代码层面确认了这个缺口的根因：评估→更新回路断裂。即使 persistence 存储了历史值，TTM/SDT 也不消费它们来更新自身。
Code Evidence: agent.py:366-372 TTM assess 无 mastery 参数输入。

### Agent 2 → Agent 1 CRITIQUES

CRITIQUE | GAP-001 | Agent 2 → Agent 1
Type: agree
Rationale: 诊断→决策断路——exhaustive_all_configs_report.json 显示 full_stack (含 Diag) 仅比 llm_only 高 ~3 分（满分 24），统计上几乎无差异。如果 DiagnosticEngine 的输出真的被 composer 消费，分数差异应该更大（参考 Duolingo Birdbrain 的 A/B 测试：12% 日活提升）。
Data Evidence: exhaustive_all_configs_report.json: top_10 最高分 20.2 (含 Diag) vs llm_only 约 16.1 (从 ultimate_quality_report 确认)，差距主要来自其他维度而非 mastery-dependent 维度。

CRITIQUE | GAP-005 | Agent 2 → Agent 1
Type: agree
Rationale: 学习历史永久为空——这正是 DATA-003（Dashboard 假数据）的根因，也是 S15/S17 评测评分区分度低（DATA-006）的原因。没有历史数据 → 评分只能看单轮文本质量 → 无法区分"真正会教"和"表面会教"。
Data Evidence: persistence.py profiles 表有 skill_masteries 列但仅存当前值，无 histories 表。

CRITIQUE | GAP-002 | Agent 2 → Agent 1
Type: need_clarification
Rationale: 难度调节断路——但 ultimate_quality_report.json 显示 full_stack (含 Flow difficulty 调节) 排名第 4 (17.2)，llm_only 排名第 6 (16.1)，差异仅 1.1 分。这是否说明 difficulty 调节即使传入 LLM，对实际输出质量的影响也很小？还是说"difficulty 信号本身设计得不够差异化"？
Data Evidence: ultimate_quality_report.json ranking 显示 full_stack vs llm_only 差距不大。

### Agent 1 RESPONSE to A2 critique on GAP-002
Response: 同意需要澄清。difficulty 的 "easy/medium/hard" 在 prompt 中对应"简化解释多用类比 / 标准教学 / 深入原理减少铺垫"——这三句话的差异可能确实不足以让 LLM 输出产生显著变化。这加强了 GAP-002 的结论：不仅需要把 difficulty 传入 LLM，还需要重新设计 prompt 中的 difficulty 差异使其更实质化（如 easy=只给类比, medium=类比+原理, hard=只给原理）。
Status: acknowledged, finding updated

### Post-Debate Status
All findings: draft_final → final (after revisions)
辩论轮数: 1/2 — 达成充分共识，无需第二轮
