# Phase 97 方向 B — 完整根源分析

**日期**: 2026-06-06
**方法**: 系统层 → 合约层 → 评估层 → 提示层，四层追溯

---

## 一、系统层：三个组件，两个教学哲学

Coherence 教练系统有三个独立设计的组件，它们优化的是不同的东西：

```
DSL 合约 (contracts/coach_dsl.json) — Phase S1.4 冻结
  优化目标: 全面教学 — 每个 action_type 输出丰富的结构化字段
  例: scaffold 必须输出 steps(每步含 order/action/expected)
       probe 必须输出 expected_answer/skill/difficulty
       6/8 action_types 要求输出 _diagram_plan

教学评估器 (teaching_evaluator.py) — Phase 48
  优化目标: 苏格拉底式辅导 — 提问、诊断、反馈、验证
  例: 奖励探针提问(probe_question)、深度追问(deep_ask)、开放提问(open_question)
       奖励具体反馈(specific_praise)、认知冲突(cognitive_conflict)

提示装配 (prompts.py) — Phase 1-97 累积
  优化目标: 两者都要 — 同时遵守 DSL 合约和实现评估器标准
  方式: 119 条规则，来自 97 个 Phase，分 6 个位置
```

**这不是"规则太多"的问题——是 DSL 合约和评估器定义了两种不同的教学哲学，而提示被夹在中间。**

---

## 二、两种教学哲学的具体冲突

```
全面教学哲学(DSL合约)          苏格拉底辅导哲学(评估器)
─────────────────────         ─────────────────────
输出 _diagram_plan            先诊后教
公式先行，解释后置              多提问少独白
步骤拆解(2-4步)               开放型提问
提供选项(options)              具体到过程的反馈
列出知识点(topics)             教完必须验证
JSON 结构化输出                察觉情绪并调整

在 4 句预算下:
  全面教学需要 3-4 句(公式+解释+步骤+图表描述)
  苏格拉底辅导需要 3-4 句(探测+倾听+追问+反馈)
  → 总共需要 6-8 句 → 只能产出 4 句 → 必须取舍
```

**LLM 做的取舍（从审计数据反推）：**

```
赢了(LLM 优先执行):             输了(LLM 放弃或打折):
  KaTeX 公式/具体数字实例         先诊后教(学情诊断 keyword=1)
  _diagram_plan 输出             深度追问(深度互动 keyword=1→2)
  引用安全(硬约束标签)             情绪支持(关系建立 keyword=2, 未改善)
  开放提问(terminal 高注意力)     行为约束(在 policy_layer 低注意力区)
```

取舍不是随机的——LLM 倾向于执行"有明确格式要求的"(KaTeX、diagram_plan、JSON 字段)和"提示末端高注意力的"(terminal checklist)，放弃"只有抽象描述的"和"在提示中间低注意力的"。

---

## 三、合约层：DSL 合约的"冷冻"效应

DSL 合约被标记为"冻结"——不可修改。但合约冻结的意图是"不要随意变更接口"，不是"合约的内容永远是正确设计"。

合约中有两个结构性偏向：

**偏向 1: 所有 action_type 都是"输出型"**
```
probe:     输出探测题 + expected_answer + skill + difficulty
scaffold:  输出 2-4 步 + steps 数组 + question
suggest:   输出建议 + options + alternatives + question
challenge: 输出任务 + objective + difficulty + hints

没有 action_type 是"倾听型"的——没有一个主要职责是"听学生说了什么并回应"。
最接近的是 reflect(反思)和 pulse(脉冲)，但它们仍然要求输出结构化字段。
```

**偏向 2: 6/8 action_types 要求 _diagram_plan**
```
probe:     "_diagram_plan: 引入新概念/教操作/对比分类时必须输出"
scaffold:  "_diagram_plan: 引入新概念/教操作/对比分类时必须输出"
challenge: "_diagram_plan: 引入新概念/教操作/对比分类时必须输出"
suggest:   "_diagram_plan: 引入新概念/教操作/对比分类时必须输出"
reflect:   "_diagram_plan: 引入新概念/教操作/对比分类时必须输出"
pulse/defer/excursion: 不要求

这意味着 75% 的教学轮次中，LLM 被要求输出图表计划——
即使这一轮的主要目标是"探测学生理解"或"提供情绪支持"。
```

图表输出消耗了本可以用于诊断和情绪支持的注意力和 token 预算。

---

## 四、评估层：评估器的"结构盲区"

评估器衡量教练行为的质量——但它只衡量文本内容，不衡量 DSL 结构合规性。

```
评估器看到的:   "你觉得矩阵乘法满足交换律吗？" → 这是一个开放提问 ✅
评估器看不到:   这个提问在 payload.question 中，不在 payload.statement 中
               → 即使提问存在于 DSL 结构中，评估器也无法识别（直到 Phase 97 审计修复）

评估器看到的:   "C[i][j] = ΣA[i][k]B[k][j]" → 这是教学 ✅
评估器看不到:   这个公式是 _diagram_plan 的一部分，还是 statement 的一部分
               → 对评估器来说都一样——都是"教练话语"，增加 coach 占比
```

评估器鼓励"少说多问"——但 DSL 合约鼓励"多说（结构化字段）"。同一个行为（输出公式）在 DSL 视角是"合规"，在评估器视角是"增加 coach 占比→触发惩罚"。

---

## 五、提示层：6 个位置，3 种注意力权重

```
系统提示 = 6 段拼接（prompts.py:300-309）

段1: stable_prefix              [位置: 开头, 注意力: 中]
段2: terminal_tutoring          [位置: 前段, 注意力: 中高]
段3: action_contract            [位置: 前中, 注意力: 中]
段4: policy_layer               [位置: 中间, 注意力: 低]  ← 动态行为约束在这里
段5: context_layer              [位置: 后中, 注意力: 中]
段6: terminal_checklist         [位置: 末尾, 注意力: 最高] ← 仅 scaffold
```

**5/6 的核心规则在段1(开头)和段2(前段)都有副本。** terminal_tutoring(段2)是 Phase 51 作为"补丁"添加的——当时 stable_prefix 中的规则不被遵守，所以在更靠近生成端的位置加了精简版。但它不是替换——是追加。

**矛盾 R58(焦虑禁止追问) vs R22(每轮必须提问)的位置解释：**
```
R22(必须提问): 段1(stable_prefix) + 段2(terminal_tutoring)
  → 两个位置, 中+中高注意力 → 综合注意力: 中高
R58(焦虑禁止追问): 段4(policy_layer)
  → 一个位置, 低注意力 → 综合注意力: 低
  → R22 赢了。焦虑学生仍然被追问。
```

这不是规则设计错误——是规则**放置**错误。行为约束应该放在比通用协议更靠近生成端的位置（段2 而非段4），以便覆盖通用协议。

---

## 六、根本原因：缺少"规则冲突检测"机制

97 个 Phase，每个 Phase 向系统添加规则，但没有机制检测：

```
□ 新规则是否与已有规则矛盾？
  → Phase 96(R58: 焦虑禁止追问) vs Phase 51(R22: 每轮必须提问)
  → 两个 Phase 独立验证通过，但合在一起从未被验证

□ 新规则是否被已有规则覆盖（重复）？
  → Phase 51(terminal checklist) 复制了 Phase 49(stable_prefix 辅导协议)
  → 当时是正确的"注意力补丁"，但现在变成了重复

□ 新规则的提示位置是否正确？
  → Phase 96 的行为约束放在 policy_layer(段4, 最低注意力)
  → 如果放在 terminal_tutoring(段2), 焦虑规则就能覆盖通用提问规则

□ 新规则与 DSL 合约是否一致？
  → Phase 62(图表教学) 要求 6/8 action_types 输出 _diagram_plan
  → Phase 48(评估器) 惩罚 coach 占比 >80%
  → 两个要求互相矛盾——图表输出增加 coach 占比
```

---

## 七、修复路径

### Phase 98a: 提示修剪（方向 B — 已规划）

修复症状（规则竞争），不修复根因（结构冲突）。

```
1. 去重: terminal checklist 中与 stable_prefix 重复的 5/6 规则 → 移除
2. 重排: 行为约束从段4(policy_layer)提升到段2(terminal_tutoring)
          → 让动态约束(MUST/MUST NOT)覆盖通用协议
3. 消解矛盾: R107 vs R05, R58 vs R22, R62 vs R19 → 显式优先级
4. 降频: _diagram_plan 从 6/8 action_types 强制 → scaffold/suggest 强制, 其余建议
```

**预期效果**: keyword 学情诊断 1→2-3, 深度互动 2→3。LLM 得到一致的指令而非矛盾指令。

**无法解决**: DSL 合约"全面教学"和评估器"苏格拉底辅导"的根本张力仍然存在。

### Phase 98b: 双通道输出（方向 C — 长期）

修复根因（结构冲突）。

```
statement(对话式 3-4 句): 探测/教学/反馈/提问 — 评估器评分依据
结构化附件(分离渲染):    KaTeX 公式 / diagram / steps / topics — 不被评估器计入 coach 占比

前端: statement 作为对话气泡, 附件作为可展开卡片
评估器: 只看 statement, coach 占比自然下降
LLM:    不需要在 4 句中塞入公式+图表+步骤+提问
```

### Phase 98c: 规则冲突检测机制（流程修复）

```
每个 Phase 的验收标准新增:
  □ 新规则与已有规则是否矛盾？（交叉引用检查）
  □ 新规则是否被已有规则覆盖？（重复检查）
  □ 新规则的提示位置是否与其优先级匹配？（位置检查）
  □ 新规则与 DSL 合约是否一致？（合约一致性检查）
```
