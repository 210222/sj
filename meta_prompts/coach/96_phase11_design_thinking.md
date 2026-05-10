# Phase 11 深度思考 — 教练交互质量升级

## 来源：120 轮质量测试的量化诊断

2026-05-06 执行了 ULTIMATE Quality Test：12 种配置组合 × 10 轮连续对话 = 120 轮。

### 六维评分（0-4）

| 维度 | 均分 | 解读 |
|------|------|------|
| interactive (交互性) | 3.38 | 高 — LLM 天然会追问 |
| clarity (清晰度) | 3.02 | 中高 — 基本表达清晰 |
| encouragement (鼓励) | 2.67 | 中等 — 有鼓励但不够 |
| personalization (个性化) | **2.77** | 低 — 几乎不引用用户历史 |
| relevance (相关性) | **2.42** | 低 — 回答有时跑题 |
| structure (结构性) | **2.12** | 最低 — 缺少步骤拆解 |

### 三个核心问题

---

## 问题 1：结构 = 2.12/4 — 缺少"第一步→第二步→第三步"

### 证据

```
Turn 7: colors = ['red', 'blue'] — 我怎么取出第一个颜色
COACH: 要取出第一个颜色，可以使用索引0。在Python中，列表索引从0开始...
QUALITY: str=1/4 (结构性=1)
```

用户问了"怎么取"，这是一个典型的"how-to"问题，最佳回应应该是：
```
第一步：用方括号加索引访问 colors[0]
第二步：验证结果 'red'
第三步：试试 colors[1] 取第二个
```

但实际回复是平铺直叙的单一陈述，没有步骤划分。

### 根因链

1. `src/coach/llm/prompts.py` 的 SYSTEM_PROMPT 只有一条弱提示：
   ```
   4. 可选: "question", "step", "option", "hint", "topics"
   ```
   其中 `step` 字段是可选且从未被强制要求。

2. `src/coach/composer.py` 中 `scaffold` 的 payload 模板是：
   ```python
   "scaffold": {"hint": "逐步拆解思路"}
   ```
   这只是一个 hint 字符串，没有结构化的步骤数组。

3. LLM 输出中 `step` 字段的生成率极低，因为没有任何强制指令要求分步。

4. `scaffold` action_type 仅在用户输入含"怎么"/"如何"时触发（composer_rules），但即使触发了，LLM 也没有结构化输出约束。

### 修复方案

- SYSTEM_PROMPT 新增结构化教学协议：当 action_type 为 scaffold 时，必须输出 `steps: [{order, description, example}]` 数组
- composer 中 scaffold 的 payload 改为 `{"steps": [], "summary": ""}` 结构
- 新增 `structure_level` 上下文: `single_step` / `multi_step` / `guided_discovery`

---

## 问题 2：个性化 = 2.77/4 — 教练很少引用用户之前说的话

### 证据

```
Turn 2: 变量是什么，用最简单的话解释
COACH: 变量就像一个带标签的盒子...

Turn 3: 所以变量就像一个盒子，可以放不同的东西进去对吧
COACH: 是的，这个比喻很形象...
```

Turn 3 的"是的，这个比喻很形象"是全场最高频的结构，但之后第 4 轮就不再引用用户自己说的话了。

跨 12 种配置看，用户明确提到"盒子"比喻后，教练在第 4 轮完全没有回引这个比喻来解释类型检查。

### 根因链

1. SYSTEM_PROMPT 包含 `{history}` 和 `{memory}`，但没有使用它们的指令：
   - 没有"你必须引用用户上一轮说过的话"
   - 没有"你的回复中至少包含一处对用户原话的回引"

2. `build_coach_context()` 把 history 传给了 LLM，但没有显式注入最近 1-2 轮的摘要引用。

3. `SessionMemory.recall()` 返回的 `relevant` 数据在 `agent.py` 中只用于 composer 决策，没有作为 strong signal 注入到 LLM 上下文。

4. FTS5 全文搜索返回的结果是历史记录列表，但 LLM prompt 中没有专门的"personalization_snippets"字段来突出显示用户的关键陈述。

### 修复方案

- SYSTEM_PROMPT 新增显式指令："引用用户上一轮的说法，使用「你刚才说...」句式"
- `build_coach_context()` 新增 `personalization_snippets: [用户原话摘要]` 字段
- agent.py 中从 `relevant` 提取最近的用户表述注入 LLM 上下文
- 新增 `memory_context.py` 中的 `extract_user_quotes()` 工具

---

## 问题 3：所有配置组合得分接近（15.2~17.9）— 行为模型在短对话中差异不明显

### 证据

```
12 种配置的 action_type 分布完全一致：
{scaffold: 3, reflect: 1, suggest: 5, probe: 1}

评分最高的 rules_diag (17.9) 甚至没有启用任何行为模型。
评分最低的 safety_full (15.2) 启用了全部安全模块。

TTM 阶段在 10 轮对话中从未变化（全部为 None/contemplation）。
```

### 根因链

1. **TTM 在短对话中不变化**：`TTMStateMachine` 需要至少 5-8 轮交互才能检测阶段变化。10 轮对话中 TTM 始终为 `contemplation`，所以 TTM 的差异化影响为零。所有配置的 ttm_stages 字段都是 `{}`。

2. **SDT 影响微弱**：即使 SDT 评估了 autonomy/competence/relatedness，但 composer 的 SDT 分支只有一个简单判断：
   ```python
   if sdt_profile and sdt_profile.get("advice", {}).get("adjust_autonomy_support"):
       action_type = "reflect"
   ```
   这个判断极少被触发，因为 SDT 的 adjust_autonomy_support 在短对话中变化幅度太小。

3. **Flow 几乎无影响**：FlowOptimizer 需要 BKT 掌握度历史，而短对话中 BKT 观测数不足，`adjust_difficulty = 0` 是常态。

4. **LLM 是主导因素**：无论什么配置，所有回复都经过 DeepSeek LLM 生成。LLM 自身的回复风格（礼貌、追问、举例）在所有配置中一致，覆盖了行为模型的微小差异。

### 修复方案

- **TTM 模拟速度加快**：在短对话中，每 3 轮强制 TTM 状态重评估（目前是每次 act 都调用，但状态变化阈值太高）
- **SDT 影响显式化**：在 SYSTEM_PROMPT 中把 autonomy/competence/relatedness 的引导建议直接写为教学策略指令
- **Flow 差分可见**：当 flow_channel 为 "boredom" 时增加挑战度，为 "anxiety" 时降低难度 — 这些指令直接写入 LLM prompt
- **行为模型配置对比测试**：新增差异化验证脚本，确保 TTM ON/OFF 配置的输出 text 有显著差异

---

## 问题 3b：诊断题 (probe) 第 10 轮始终问"认知主权"

### 证据

```
Turn 10 (baseline_rules): 
QUEST: 认知主权保护系统的主要目标是什么？

Turn 10 (llm_only):
QUEST: 在中文中，'怎么'通常用来询问什么？

Turn 10 (llm_ttm):
QUEST: 以下哪个选项最符合认知主权的核心原则？

Turn 10 (full_stack):
QUEST: 什么是认知主权？
```

用户在每一轮的第 10 句都说"能考考我今天学的东西吗"——话题是 Python 变量/循环/列表——但 probe 却问了完全不相关的问题。

### 根因链

1. **agent.py 中 covered_topics 被硬编码为空列表**：
   ```python
   covered = []
   diagnostic_probe = self.diagnostic_engine.should_and_generate(
       covered_topics=covered, ...
   ```
   导致 `_select_candidate_skill()` 跳过"untested topics"分支，直接走到 intent 兜底。

2. **intent 解析为 "general"**：用户说"能考考我吗"，`_parse_intent()` 无法匹配具体关键词，兜底到 `"general"`。

3. **skill = "general" 时**：`_fallback_probe("general", "medium")` 输出：
   ```
   "请描述「general」的核心原理和使用场景。"
   ```
   当 LLM 处理这个 prompt 时，"general" 被解释为系统的全局概念（认知主权）。

4. **diagnostic_engine 的 LLM prompt** 没有传递对话历史，所以 LLM 不知道用户刚刚学了 Python。

### 修复方案

- **agent.py 修复**：把 `LearningPathTracker.get_covered_topics()` 的真实结果传给 diagnostic_engine
- **DIAGNOSTIC_PROBE_PROMPT 增强**：新增 `conversation_context` 字段，传递近几轮对话摘要
- **_select_candidate_skill() 增强**：当 intent 为 "general" 时，改用最近对话主题作为 skill
- **diagnostic_engine 增加话题路由**：在 _generate_probe() 中自动取 `covered_topics[0]` 作为 skill

---

## 修复优先级

| 优先级 | 子阶段 | 影响维度 | 预期提升 | 修改文件数 |
|--------|--------|----------|---------|-----------|
| P0 | S11.3 Probe 质量修复 | relevance + probe | +2-3 | 2 |
| P0 | S11.1 结构化教学 | structure | +1-2 | 2 |
| P1 | S11.2 个性化增强 | personalization | +1-2 | 2 |
| P2 | S11.4 行为模型差异化 | differentiation | — | 3 |

## 预期效果

修复后预期六维评分：

| 维度 | 当前 | 目标 | 提升方法 |
|------|------|------|----------|
| structure | 2.12 | 3.0+ | S11.1 结构化协议强制 steps |
| personalization | 2.77 | 3.2+ | S11.2 引用指令 + snippets |
| relevance | 2.42 | 3.0+ | S11.3 probe 话题锚定 |
| interactive | 3.38 | 3.5+ | 连带提升 |
| clarity | 3.02 | 3.3+ | 步骤拆解自然提高清晰度 |
| encouragement | 2.67 | 3.0+ | 连带提升 |

总体 avg quality 从 16.4/24 → 19+/24 预期。
