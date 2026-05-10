# Coherence 教学系统当前状态报告

## 1. 感知层 — 系统如何感知用户？

### 当前能力
- **TTM 阶段检测**：通过 cognitive/behavioral 指标 + session_count 推断用户处于 precontemplation→maintenance 的哪一阶段 [agent.py:366-372]
- **SDT 动机评估**：通过 rewrite_rate/excursion_use/initiation_rate 评估自主性/胜任感/关联性 [agent.py:379-387]
- **DiagnosticEngine**：每 5 轮出诊断题，用 BKT 追踪技能掌握度 [diagnostic_engine.py:293-346]
- **Flow 心流计算**：互信息 I(M;E) 计算无聊/心流/焦虑通道 [flow.py]

### 缺口
- **GAP-001 (critical)**: 诊断引擎的 mastery 输出从未被 consumer 消费——BKT 追踪被"存了不用"
- **GAP-005 (critical)**: 学习历史永久为空——系统每次对话都是第一次见用户
- **DATA-002 (major)**: 用户模型无历史趋势——无法画学习曲线
- **DATA-003 (critical)**: Dashboard 数据全是假的——TTM 雷达/SDT 能量环展示的是硬编码默认值

## 2. 决策层 — 系统如何决定教什么？

### 当前能力
- **composer.compose()**：TTM 粗筛(avoid/recommended action_type) → SDT 微调(低自主性→reflect、低胜任感→降难度) → Flow 定难度 [composer.py:37-109]
- **8 种 action_type**：probe/challenge/reflect/scaffold/suggest/pulse/excursion/defer [coach_dsl.json]
- **越权熔断**：高风险域+低证据→强制降级为 reflect [composer.py:174-203]
- **跨域迁移税**：跨领域建议降低难度一级 [composer.py:205-224]

### 缺口
- **GAP-004 (major)**: 8 种 action_type 在 LLM 层的差异仅一行文字描述——教学行为差异不足
- **GAP-006 (major)**: 难度仅单向调节(SDT 只能 low)——Flow 可双向但默认关闭
- **SRC-007 (参照)**: Duolingo Birdbrain 用 ML 预测 P(correct|user,exercise) 驱动选题决策，Coherence 无类似能力
- **SRC-008 (参照)**: MATHia 用 Model-Tracing 追踪解题步骤找 knowledge gap，Coherence 只看最终回答

## 3. 执行层 — 系统如何执行教学？

### 当前能力
- **LLM prompt 注入**：SYSTEM_PROMPT 含 action_type_strategy/ttm_stage/sdt_profile/difficulty/history/memory [prompts.py:8-54]
- **action_type 差异化 payload**：各 action_type 有不同字段结构 [composer.py:119-132]
- **FallbackEngine**：LLM OFF 时的规则模板 [fallback.py]
- **结构化教学协议**：scaffold 输出 steps 数组、suggest 推荐输出 steps [prompts.py:30-34]

### 缺口
- **GAP-002 (major)**: difficulty 始终为 "medium"——composer 调整了 payload["difficulty"] 但从未传到 build_coach_context()
- **GAP-004 (major)**: 所有 action_type 的 LLM 输出可能近似——prompt 差异不足

## 4. 评估层 — 系统如何知道自己教得怎么样？

### 当前能力
- **S15/S16/S17 评测体系**：256 配置 × 6 维度的单轮评分 [test_s15_quick.py, exhaustive_all_configs_report.json]
- **DiagnosticEngine 评估**：BKT 追踪 + LLM 答案评估 + 关键词兜底 [diagnostic_engine.py:504-572]
- **A/B 评测脚本**：llm_only vs full_stack 统计对比 [test_s17_ab_evaluation.py]

### 缺口
- **DATA-001 (critical)**: 评分体系测"回答质量"而非"学习效果"——relevance=长度，personalization=字段存在
- **DATA-005 (critical)**: 全部 1275 个测试是单轮模式——无纵向教学效果验证
- **DATA-006 (major)**: 256 配置评分区分度极低(极差仅 8.9 分，满分 24)——full_stack vs llm_only 差异淹没在噪声中
- **SRC-005 (参照)**: LLMKT 论文证明 LLM 可直接从对话文本推断 mastery——Coherence 未利用此能力
- **SRC-010 (参照)**: Duolingo HLR 实现 45%+ 错误率降低——Coherence 无 spaced repetition

## 5. 更新层 — 系统如何改进教学策略？

### 当前能力
- **SessionPersistence**：profiles 表存储 ttm_stage/sdt_scores/skill_masteries/difficulty_level [persistence.py]
- **BKT mastery 更新**：每次诊断后更新 P(learned) [diagnostic_engine.py:266]
- **Phase 17 同意持久化**：consent_status 跨会话保留 [persistence.py:135-150]
- **MRT 微随机实验**：A/B 变体分配（默认关闭）[agent.py:490-503]
- **MAPE-K 闭环**：Monitor→Analyze→Plan→Execute→Knowledge（默认关闭）[agent.py:341-354]

### 缺口
- **GAP-003 (critical)**: 评估→更新回路断裂——TTM/SDT 不消费 mastery 数据来调整自身的阶段评估
- **GAP-007 (critical)**: 无学习目标/课程概念——系统不知道用户想学什么
- **DATA-004 (major)**: 门禁系统无真实数据——8 个 gate 全部硬编码 "pass"
- **SRC-006 (参照)**: ITS 2025 survey 提出 LLM-enhanced KT 三层分类——Coherence 当前在 LLM-standalone 和 LLM-enhanced 之间

## 6. 外部参考

### 可落地
- **pyBKT** [SRC-001]: MIT licensed, 可直接替代 Coherence 的硬编码 BKT 参数 → src/coach/flow.py
- **Duolingo Birdbrain** [SRC-007]: P(correct|user,exercise) 预测模型 → 替代 Coherence 当前的关键词匹配评估
- **LLMKT** [SRC-005]: LLM 从对话中推断 mastery → 替代二元 correct/incorrect 评估

### 需改造
- **OATutor** [SRC-003]: 自适应选题逻辑 → 改造适配 Coherence 的 compose() 框架
- **MATHia Model-Tracing** [SRC-008]: 解题步骤追踪 → 改造适配 Coherence 的 chat-based 交互
- **Duolingo HLR** [SRC-010]: 半衰期回归算法 → 改造适配 Coherence 的 BKTEngine
- **Khanmigo Socratic Prompt** [SRC-009]: 多层 prompt 工程 → 改造适配 Coherence 的 SYSTEM_PROMPT

### 概念参考
- **pyKT-toolkit** [SRC-002]: 多模型评测框架 → 概念参考
- **MATHia ASTRA** [SRC-008]: BERT 策略表征 → 远未来参考
- **Langfuse 可观测性** [SRC-011]: LLM trace 追踪 → 未来架构参考

---

## Summary

| 层 | 当前教学级别 | 缺口数 | 最严重缺口 |
|----|------------|--------|----------|
| 感知 | Level 2 (有传感器但数据不流动) | 4 | GAP-001 mastery 被存不用 |
| 决策 | Level 2.5 (有策略选择但无目标规划) | 4 | GAP-007 无学习目标 |
| 执行 | Level 3 (有 LLM 但 prompt 硬化) | 2 | GAP-002 difficulty 断路 |
| 评估 | Level 1.5 (有评分但测错东西) | 3 | DATA-001 不测学习效果 |
| 更新 | Level 1 (有存储但无闭环) | 4 | GAP-003 评估→更新回路断 |
| 外部参考 | — | 12 SRC | — |

**整体教学级别: Level 2.0** — 有传感器、有执行器，但两者之间的控制回路是断的。
