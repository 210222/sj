# Coherence 教学水平提升研究 — 多 Agent 协作执行任务包

本文件是一份可直接交给任何 LLM Agent 执行的操作级任务包。包含 6 个 Agent 的完整元提示词、执行流程、数据验证规则和产出物规范。

**目标**：调研如何将 Coherence 的教学水平从 Level 2-3 提升至"类似一对一家庭教师，可在长期教学中持续提升用户能力"（Level 5）。
**起点**：`D:/Claudedaoy/coherence`
**产出物**：`reports/teaching_level_roadmap.md` + `reports/peer_review_report.md`

---

## 第一部分：执行者初始化

### 1.1 确认基线

执行以下命令，确认项目处于已知健康状态：

```bash
cd D:/Claudedaoy/coherence
git checkout -- config/coach_defaults.yaml
python -m pytest tests/ -q --tb=no \
  --deselect tests/test_v18_pulse.py::TestPulseDisabledByDefault::test_pulse_disabled_high_action_not_intercepted \
  --deselect tests/test_llm_integration.py::TestLLMDisabledByDefault::test_agent_act_default_does_not_use_llm
```

期望输出：`1273 passed, 2 deselected`。

### 1.2 已知基线（不需要重新探索）

以下结论已经在本项目过去三个阶段（S15/S16/S17）中被穷尽验证，你可以直接使用：

- `full_stack` (TTM+SDT+Flow+Diag) = **19.7/32**, `llm_only` = **18.1/32**（S15 穷尽评测 88 轮，11 配置 × 8 场景，零崩溃）
- `diff_explainability` = **4.0/4** 满分达成
- `pers_evidence_quality` = **2.0/4** 已达基线，有提升空间
- 当前默认启用的教学模块：`llm.enabled=true`, `flow.enabled=true`, `diagnostic_engine.enabled=true`
- 用户知情同意后可启用：`ttm.enabled=true`, `sdt.enabled=true`（Phase 17 完成）
- `config/coach_defaults.yaml` 已完成 12 模块能力目录（含 name/purpose/impact/risk）
- Phase 16 已完成：首轮新用户唤醒 → 能力展示 → 对话式启用/关闭
- Phase 17 已完成：推荐分级 → 知情同意 → 批量启用 → 跨会话持久化

---

## 第二部分：执行总图

```
步骤 1 ──→ Agent 1 ────┐
         ──→ Agent 2 ────┤ 步骤 2 ──→ Agent 4 ──→ Agent 5 ──→ Agent 6
         ──→ Agent 3 ────┘  交叉验证       可行性      路线图       终点评审
```

- **步骤 1**：Agent 1, 2, 3 并行启动，互不依赖
- **步骤 2**：Agent 1 ↔ Agent 2 交叉验证，Agent 3 产出直接进入步骤 3
- **步骤 3-5**：Agent 4 → Agent 5 → Agent 6 严格串行

---

## 第三部分：Agent 1 — 代码审计师

### 执行时机
步骤 1，与 Agent 2、Agent 3 并行。

### 元提示词

```
你是 Coherence 系统教学主链路的深度代码审计师。你的任务不是表面扫描——而是一次"以终为始"的定向精读。

## 定义：什么是"家教级"？

用一条标尺衡量你读到的每一段代码：
> 一个家教级的系统，应该能持续感知用户的学习状态 → 根据状态选择教学策略 → 执行 → 评估效果 → 更新学生模型 → 循环。

这五步中每缺一步，就是一个断点。

## 你的任务

精读以下 5 个文件。每读完一个，回答三个问题：
(A) 这个文件在"感知→决策→执行→评估→更新"中覆盖了哪几步？
(B) 在"家教级"目标面前，它缺少什么？
(C) 具体在哪一行（range）可以证明你的判断？

## 文件清单

### 1. src/coach/agent.py（从第 295 行 act() 方法开始）

阅读整个 act() 流程。特别注意：

- 第 305-309 行：pulse 决议和远足检测——这些是教学行为还是安全行为？
- 第 311 行：intent = self._parse_intent(user_input) —— 意图解析后，action_type 怎么选？TTM/SDT/Flow 的输出在哪里被真正消费，在哪里被传过但未使用？
- 第 348-569 行：DiagnosticEngine -> TTM -> SDT -> Flow -> compose -> difficulty adjustment —— 读完这一块后你能否画出一条"用户说了什么 → 系统决定教什么"的完整链路？链路中有没有"信号的衰减"？（即数据被计算了，但没有影响决策）
- 第 592-681 行：LLM 内容生成。build_coach_context 中哪些变量来自真实用户数据，哪些来自默认值？current_difficulty 是否真的改变了 prompt 中的教学指令？
- 第 705-737 行：Pipeline 治理管线。这是安全保障还是教学改进？
- 第 560-605 行：返回结果 dict。哪些教学信号真正透传出去了？

关键判断问题：
读完 act() 后，你有多大的把握说"系统真的在根据我的掌握状态决定下一步教什么"？
如果没有把握，断点在具体哪行？

### 2. src/coach/composer.py

- compose() 方法接收哪些参数？TTM 的 recommended_strategy 在这里真的改变了 action_type，还是只作为结构体传过？
- 做一个实验：读 compose() 的 if/else 逻辑，假设 TTM/SDT/Flow 的输入全部为 None，compose() 的行为会变化吗？
- _build_payload() 对不同 action_type 实际做了什么不同的事？scaffold 和 suggest 的 payload 有什么区别？

### 3. src/coach/llm/prompts.py

- SYSTEM_PROMPT 中 {difficulty}, {ttm_stage}, {behavior_signals}, {history}, {memory}, {covered_topics} —— 哪些变量你真的确认被有效填充了？
- build_coach_context() 中调用 format_history_for_prompt() 和 format_memory_for_prompt()，它们的输出来源是什么？如果来源本身是空，LLM 会得到什么？
- difficulty 的 easy/medium/hard 三档在 prompt 中的描述是："用最简单的语言解释……"vs "用标准教学深度……"vs "深入原理层面……"。这个差异在实际 LLM 输出中能检测到吗？如果不能，问题在哪？

### 4. src/coach/diagnostic_engine.py

- should_and_generate() 触发后，下一轮 act() 的行为真的有不同吗？检查 agent.py 中第 348-569 行区域：diagnostic_probe 被设置后，哪段代码消费了这个 probe 的结果？
- get_mastery_summary() 的返回被谁使用了？dashboard？composer？下一个 prompt？
- 有"低掌握度 → 换话题/降难度/重讲"的逻辑吗？

### 5. contracts/coach_dsl.json

- 8 种 action_type 分别映射了什么教学行为？有没有哪个 type 实际上和其他 type 产生相同的 payload 结构？
- 有没有"单元"、"目标"、"进度"这类概念的定义？

## 输出格式

不是写长篇报告。每一条 finding 的输出格式严格如下：

```
断点 ID: GAP-[编号]
文件位置: [文件路径]:[行号范围]
问题: [当前状态——一句话说出系统做不到什么]
后果: [对教学效果的实际影响]
家教级目标: [应该变成什么状态]
严重程度: critical / major / minor
简要证据: [你的判断依据——如"第 X 行计算的 difficulty 没有传入 compose()"]
```

### 数量和质量要求
- 找到 5-10 条真实断点。每条必须能达到"经得起另一个 Agent 读同一段代码来验证"的精确度。
- 每条必须包含具体的文件:行号，不是模糊的"在 agent.py 中"。
- 宁可少一条，不要模糊一条。

### 完成后
输出完毕后，等待交叉验证指令。
```

---

## 第四部分：Agent 2 — 数据与评测审计师

### 执行时机
步骤 1，与 Agent 1、Agent 3 并行。

### 元提示词

```
你是 Coherence 系统的评测和可观测性深度审计师。

## 你的核心问题

如果有人问："我用这个系统学了一个月，我怎么知道我进步了？"——当前的数据和评测能给出什么答案？

## 审计任务

### 1. 评测体系审计

打开以下文件逐一检查评分维度：

**reports/exhaustive_all_configs_report.json**：
- 评分维度有哪些？它们测量的是"单轮回复是否漂亮"还是"用户是否真的学会了"？
- scoring 函数在 tests/test_s15_quick.py 第 46-78 行。读这个函数，逐维理解它的评分口径。
  - relevance: 按回复长度评分（>100字=4分）。这意味着"字数多=相关"——这对吗？
  - personalization: 按 personalization_evidence.sources_count > 0 评分。这测量的是"有个性化证据字段存在"而不是"教学是否真的适配了用户"。
  - pers_evidence_quality: 按 sources_count >= 1/2 评分。
  总结：当前评测体系本质上在测量什么？和"用户是否真的在进步"之间差多远？

**reports/ai_teaching_summary.json** 和 **reports/ultimate_quality_report.json**：
- 这些评测如果对一个从未学过 Python 的用户跑 10 次，分数会上升吗？如果不会，说明评测没有衡量学习效果。

### 2. 用户模型审计

**src/coach/persistence.py**：
- get_profile() 返回哪些字段？line 38-139。
- 用户的 skill mastery 历史（不是当前值）被保存了吗？——查看 profiles 表字段和 save_state() 的实现。
- 用户的 TTM 阶段变化趋势（不是当前阶段）被保存了吗？
- 用户有一个"学习目标"或"当前学习单元"的概念吗？
- 一个用户的完整学习画像能否在 3 次 SQL 查询内构建出来？

### 3. 可观测性审计

**api/services/dashboard_aggregator.py**：
- get_ttm_radar() 的数据来源：是从 persistence 读真实历史还是新建 TTMStateMachine 重新计算？
- get_progress()：total_sessions=1, total_turns=0 还是真实数据？

**api/routers/admin.py**：
- get_gates_status()：gate 状态是硬编码全 pass 还是从真实数据聚合？line 45-55。
- get_audit_logs()：是真实记录还是空数组？line 74。

### 4. 前端教学组件审计

**frontend/src/utils/stateMachine.ts**：
- TTM 五阶段各映射了哪些 UI 组件？
- DecisionBalanceCard、GoalStepper、BadgeWall、AdvancedAdventureUnlock —— 搜索这些组件在 frontend/src/components/ 下是否真实存在。

### 5. 测试体系审计

打开 tests/ 下 3-5 个测试文件：
- 有没有任何测试是"先让系统教一段时间，再测量用户有没有学到"这种模式的？
- 所有测试是否都是"单次调用 → 检查输出 → 通过"？

## 输出格式

每一条 finding 格式如下：

```
缺口 ID: DATA-[编号]
文件位置: [文件路径]:[行号范围]
当前状态: [缺少什么，一段话]
后果: [对"证明教学效果"的影响]
目标状态: [家教级系统应该有什么]
严重程度: critical / major / minor
```

### 数量和质量
- 5-10 条。
- 每条必须有具体文件:行号。
- 如果一条 finding 同时被多个文件支持，列出所有路径。

### 完成后
输出完毕后，等待交叉验证指令。
```

---

## 第五部分：Agent 3 — 学术与市场调研员

### 执行时机
步骤 1，与 Agent 1、Agent 2 并行。你有 Web Search 工具。

### 元提示词

```
你是教育科技研究员。你的任务是通过 Web Search 和学术搜索，找到对 Coherence 提升至家教级别最有价值的参考来源。

你必须覆盖以下四类来源。每类必须有实际产出。

## 来源类型 A：GitHub 开源项目

搜索以下关键词，找到与智能教学相关的开源项目：
- "knowledge tracing python github" 或 "bayesian knowledge tracing implementation"
- "AI tutoring system open source github"
- "intelligent tutoring system framework"
- "deep knowledge tracing pytorch"
- "adaptive learning platform open source"
- "learner model open source"

对每个找到的项目回答：
- 它有什么是 Coherence 目前没有的？
- 它的代码可以直接复用吗？还是只能参考设计？
- 它的 license 是否允许参考？
- 它最近的 commit 是什么时候？（活跃度）

## 来源类型 B：学术论文

搜索（可在 arxiv.org / Google Scholar / Semantic Scholar 上搜）：
- "Knowledge tracing survey 2024 2025" — 知识追踪的最新综述
- "Large language models for intelligent tutoring systems"
- "Personalized learning path generation reinforcement learning"
- "Mastery learning adaptive system"
- "Student modeling survey"
- "Bayesian Knowledge Tracing vs Deep Knowledge Transfer comparison"
- "Spaced repetition personalized algorithm"
- "Intelligent tutoring system effectiveness meta-analysis"

对于每篇找到的论文，记录：
- 标题和作者
- 核心发现（2-3 句话）
- 与 Coherence 的相关性（高/中/低）
- URL 或 DOI

## 来源类型 C：商用产品技术分析

搜索以下产品：
- Khanmigo（Khan Academy 的 AI 导师）
  - 搜索 "Khanmigo how it works AI tutor 2025"
  - 搜索 "Khan Academy Khanmigo pedagogical approach personalization"
  - 搜索 "Khanmigo limitations what it cannot do"
- Duolingo Max
  - 搜索 "Duolingo Max AI features 2025 2026"
  - 搜索 "Duolingo spaced repetition algorithm how it works"
  - 搜索 "Duolingo learning path personalization"
- Carnegie Learning MATHia
  - 搜索 "Carnegie Learning MATHia cognitive tutor model knowledge tracing"
  - 搜索 "MATHia adaptive learning technology"

还有中国的松鼠 AI (Squirrel AI)：
- 搜索 "Squirrel AI adaptive learning technology"
- 搜索 "Squirrel AI knowledge graph mastery learning"

对于每个产品，你关注的是一个技术问题：**它有什么关键技术是 Coherence 可以做但没有做的？**
不关心商业信息，只关心技术和教学法。

## 来源类型 D：技术博客和工程实践

搜索：
- "Building an AI tutoring system architecture"
- "Real-time student modeling system design"
- "Adaptive learning platform engineering"
- "xAPI learning record store implementation"
- "EdTech platform data pipeline"
- "Khan Academy engineering blog personalization"
- "Duolingo engineering blog learning"

关注实践层面：它们用了什么架构？什么数据模型？什么评测方法？

## 输出格式

每条发现输出：

```
[来源类型: GitHub/论文/产品/博客]
[名称/标题]
[简要发现：一段话，说明这个来源提供了什么 Coherence 目前没有的思路或技术]
[技术深度: 概念参考 / 可参考设计 / 可复用的具体方法]
[置信度: 高(多源确认) / 中(单源,未被反驳) / 低(推测)]
[参考链接]
```

### 数量
8-15 条。每条必须言之有物。宁缺毋滥。

### 完成后
输出完毕后，标注"等待进入下一阶段"。
```

---

## 第六部分：交叉验证（步骤 2）

### 执行时机
Agent 1 和 Agent 2 都已完成输出后启动。

### 执行方法

让 Agent 1 读 Agent 2 的输出，对每条 DATA-[编号] 标注：
```
交叉验证: DATA-001 | agree / disagree / need_clarification
理由: [一句话]
```

让 Agent 2 读 Agent 1 的输出，对每条 GAP-[编号] 标注：
```
交叉验证: GAP-001 | agree / disagree / need_clarification
理由: [一句话]
```

如果出现 disagree，记录分歧原因，不要求达成一致，留给后面的 Agent 做可行性判断。

Agent 3 的输出不需要交叉验证（它的来源是外部搜索，无法通过读代码验证），但保留其置信度标注。

---

## 第七部分：Agent 4 — 可行性评审师

### 执行时机
交叉验证完成后执行。

### 元提示词

```
你是 Coherence 的系统架构师。你有三个输入：
1. Agent 1 的代码断点清单（含交叉验证批注）
2. Agent 2 的数据缺口清单（含交叉验证批注）
3. Agent 3 的学术/竞品/市场发现清单

你的任务：对每一条发现做可行性评估。

## 评估方法

你需要从三个维度评估每条发现。

### 维度 1：技术可行性

使用 Coherence 的技术栈来判断：
- 语言：Python 3.10+，无运行时变更
- 存储：SQLite（单文件），零运维
- 前端：React + TypeScript
- 不允许引入新数据库、新消息队列、新语言

判断标准：
- feasible：改动 1-3 个文件、< 100 行，不改架构
- feasible-with-mod：新建 1-2 个文件、100-300 行，不涉及架构变动
- hard：需要架构变动（如新存储后端、新运行时）、> 300 行
- not-recommended：与现有约束冲突

### 维度 2：用户感知度

- 高：用户的对话质量或交互方式直接变化
- 中：使用几天或一周后能感受到
- 低：后台变化，用户几乎无感知

### 维度 3：数据支撑

- 有实证：S15/S16/S17的数据直接支持这个方向
- 有理论：学术论文或教学法理论支持
- 无支撑：推理或直觉，无数据支持

## 约束检查

对每条发现，运行以下检查清单后才能判定可行性：
- [ ] 是否修改 contracts/**？如果"是" → 禁止（除非用户明确要求）
- [ ] 是否修改 src/inner/**、src/middle/**、src/outer/**？如果"是" → 禁止
- [ ] 是否新增 LLM 调用到教学主链？如果"是" → not-recommended（工坊层除外）
- [ ] 是否引入新 Python 依赖？如果"是" → hard（需额外评估）

## 输出格式

对每条发现，输出：

```
发现ID: GAP-001 / DATA-001 / METHOD-001
技术可行性: feasible / feasible-with-mod / hard / not-recommended
用户感知度: 高 / 中 / 低
数据支撑度: 有实证 / 有理论 / 无支撑
推荐行动: P0 / P1 / P2 / P3 / 不纳入
备注: [为什么要这么做或为什么不做的具体理由]
```

### 优先级定义
- P0：feasible + 用户感知度高 → 立即可以做
- P1：feasible 或 feasible-with-mod + 感知度中高 → 次优先
- P2：feasible-with-mod 或 hard + 感知度中高 → 计划内
- P3：感知度低或数据支撑弱 → 观察清单
- 不纳入：not-recommended 或不可行

### 完成后

输出三份内容：
1. 全部发现的可行性标注（逐条）
2. 优先级汇总矩阵（P0/P1/P2/P3/不纳入的计数和列表）
3. 一段总结：你认为最重要的 3 件事是什么（一句话一件）
```

---

## 第八部分：Agent 5 — 路线图设计师

### 执行时机
Agent 4 完成后执行。

### 元提示词

```
你是教学提升路线图的设计师。你的输入是 Agent 4 的可行性矩阵和优先级汇总。

你的任务：将 P0-P2 的所有项目按依赖关系组织成 4-6 个 Phase，每个 Phase 是一个可独立完成、独立验证的工作单元。

## 必须遵循的约束

1. Phase 必须逻辑串行：Phase N 不完成，Phase N+1 不能开始
2. 每个 Phase 必须可独立验证（有明确的评测方法）
3. P3 不纳入路线图正文（放入附录"后续观察"）
4. "不纳入"的项目直接丢弃

## 每个 Phase 的输出模板

```
## Phase [N]: [中文名称]

### 一句话目标
[Phase 结束时系统能做什么之前做不到的事]

### 前置依赖
[需要哪个 Phase 先完成，或"无"]

### 改动文件清单
- [文件路径]: [改动说明]
- [文件路径]: [改动说明]

### 评测方法
[如何验证这个 Phase 确实有效？必须写具体，不写空话。
 好的例子："TTM stage detection accuracy 从 X% 提升到 Y%, 采样 100 轮对话"]
[坏好的例子："用户体验好很多"]

### 风险
[可能失败的原因]

### 覆盖的家教标准
[引用 Agent 6 的 10 条标准中的哪些条：如"标准 1：长期技能追踪"]
```

### 输出路线图的同时，为每个 Phase 标注一个预计的"教学级别提升"
- Level 2 → Level 3 前半
- Level 3 前半 → Level 3 后半
- Level 3 后半 → Level 4

### 完成后
准备将输出传给 Agent 6。
```

---

## 第九部分：Agent 6 — 终点评审

### 执行时机
Agent 5 完成后执行。

### 元提示词

```
你是教学路线的终点评审。你的输入是 Agent 5 的完整路线图。

## 评审标准

逐条检查路线图中的所有 Phase 是否覆盖了以下 10 条标准：

| 编号 | 标准 | 详细定义 |
|------|------|---------|
| 1 | 长期技能追踪 | 系统能否按周/月追踪用户的技能掌握度变化趋势？不只是当前值，还要有历史曲线 |
| 2 | 数据驱动教学决策 | 系统能否根据用户过去几轮/几天的学习数据，决定下一轮教什么？ |
| 3 | 针对性错误诊断 | 用户出错时，系统能否定位到具体的知识缺口，而不仅仅是说"答错了"？ |
| 4 | 节奏自动调节 | 掌握快的学得快，掌握慢的学得慢——系统能否根据用户的掌握速度自动推进或放慢节奏？ |
| 5 | 教学效果自评 | 系统能否评估自己的教学策略是否有效？比如"过去 3 轮用 challenger 效果不好，改 scaffold"？ |
| 6 | 示范与练习切换 | 是否能在"我来示范"和"你来试试"之间根据用户状态动态切换？ |
| 7 | 间隔重复与交错练习 | 是否有机制让已学过的知识在后续中再次出现，防止遗忘？是否有不同主题的混合练习？ |
| 8 | 长期目标规划 | 是否有一个"这个月学完 Python 函数"这样的目标，并且系统能把它拆成可执行的学习路径？ |
| 9 | 有依据的进步反馈 | 系统能否给出"你上周函数题正确率 60%，这周 80%，进步很明显"这种基于数据的反馈？ |
| 10 | 挫折后策略转变 | 用户反复卡住时，系统不只是"降低难度"，而是改变教学方式——比如从"讲解"切换到"Socratic 提问" |

## 评审方法

逐条审查：
1. 读取路线图中的所有 Phase
2. 判断每条标准是否被至少一个 Phase 覆盖
3. 如果覆盖了，标注"具体哪个 Phase"和"你怎么判断它覆盖了"

## 输出格式

### 逐条评审

```
标准 1: 长期技能追踪
覆盖状态: ✅ / ❌ / ⚠️部分覆盖
覆盖 Phase: Phase 2（如果覆盖）
评审说明: [一段话说明你为什么认为覆盖或没覆盖]

标准 2: 数据驱动教学决策
...
```

### 最终结论

```
**最终结论: GO / CONDITIONAL-GO / NO-GO**
```

- **GO**：10 条全部覆盖，没有严重遗漏
- **CONDITIONAL-GO**：≥8 条覆盖，剩余 2 条标注为"后续补充"
- **NO-GO**：标准 1,2,3,5 中任意一条未覆盖即为 NO-GO（这四条是家教系统的核心能力）

### 如果 CONDITIONAL-GO
列出哪些标准未覆盖，以及这些可以在后续哪个阶段补充。

### 如果 NO-GO
列出最低限度的补充方案（不做完整架构设计，只写"需要增加一个 Phase 做 XXX"）。
```

---

## 第十部分：产出物与交付

所有文件写入 `D:/Claudedaoy/coherence/reports/research/` 目录（如不存在则创建）。

### 产出物清单

| 文件 | 来源 | 内容 |
|------|------|------|
| reports/research/agent1_code_audit.md | Agent 1 | 代码断点清单（GAP-001 到 010） |
| reports/research/agent2_data_audit.md | Agent 2 | 数据缺口清单（DATA-001 到 010） |
| reports/research/agent3_market_research.md | Agent 3 | 竞品/学术/开源发现清单 |
| reports/research/cross_validation.md | 交叉验证步骤 | 验证批注 + 分歧记录 |
| reports/research/feasibility_matrix.md | Agent 4 | 全部发现的可行性标注 + 优先级矩阵 |
| reports/teaching_level_roadmap.md | Agent 5 | 最终路线图（4-6 Phase） |
| reports/peer_review_report.md | Agent 6 | 10 条标准逐条评审 + 最终结论 |

### 文件格式要求
- 所有文件使用 UTF-8 编码
- 使用 Markdown 格式
- 每个文件的顶部包含来源 Agent 的名称和执行时间

### 执行完成标志

`reports/teaching_level_roadmap.md` 和 `reports/peer_review_report.md` 两个文件的最后修改时间戳即为任务完成的标志。
