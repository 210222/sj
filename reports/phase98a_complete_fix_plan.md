# Phase 98a 完整修复方案 — 教练提示词规则重组

**日期**: 2026-06-06
**依赖**: Phase 97 审计完成（keyword 评估器已校准、LLM judge 已可用）
**基线**: 1551/0/8 | anxious keyword 3.0/5, LLM judge 4.83/5
**元提示词**: `meta_prompts/coach/380_phase98a_prompt_pruning.xml`
**根因分析**: `reports/phase98_direction_b_root_cause.md`

---

## 一、修复目标

教练提示词（`prompts.py`）经过 97 个 Phase 的累积，形成 119 条规则。5/6 核心协议在 2 个位置有重复副本。3 处已确认矛盾。动态行为约束被放在最低注意力区。这些问题不是设计错误——是 97 次独立增量变更的自然结果。

**目标**: 让 LLM 看到一致的、无矛盾的指令集，不再被互相矛盾的规则拉向不同方向。

**量化目标**: anxious 画像 keyword 学情诊断 ≥2（当前 1-2）、深度互动 ≥3（当前 2）。

---

## 二、分 Phase 策略（基于自审查优化）

元提示词自审查发现：6 个 step 不能一次性执行——去重和重排是两个独立变量，需要分开验证才能归因。

```
Phase 98a-1（去重+消解矛盾+降频）: 只改规则内容和数量, 不改装配顺序
  → 审计验证 → 确认改善且无退化 → 进入 98a-2

Phase 98a-2（重排）: 只改装配顺序, 不改规则内容
  → 审计验证 → 确认行为约束提升有效 → 完成
```

### 为什么必须分两步

```
如果一次性执行 6 个 step 后审计显示改善:
  是去重的贡献？重排的贡献？还是降频的贡献？
  → 无法归因 → 如果后续需要微调，不知道调哪个

如果一次性执行后审计显示退化:
  哪一步导致了退化？
  → 只能全部回退 → 从头开始
```

---

## 三、Phase 98a-1: 去重 + 消解矛盾 + 降频

### 3.1 去重: 5/6 协议从两个位置合并为一个

**原则: 保留信息量更丰富的版本，放置在语义正确的位置。**

```
协议 1 — 先诊后教:
  stable_prefix(详细): "引入任何新概念前，必须先问学生对此了解多少。
                       使用'你之前接触过X吗？''你是怎么理解X的？'等开放式探测。
                       同一话题只诊断一次——如果上一轮已经问过探测题，
                       不论学生如何回答，本轮直接进入教学，不重复探测。"
  terminal(补充条件):  "探测闭环: 如果上一轮探测过→直接教学。此规则覆盖先诊后教。"
  → 合并后(stable_prefix): 保留 stable 版本 + 吸 terminal 的"覆盖"逻辑
                          稳定的版本已经包含"同一话题只诊断一次"——terminal 的"覆盖"是冗余的
                          terminal 中删除此条目

协议 2 — 多提问少独白:
  stable_prefix(详细): "每轮教学输出后必须跟随至少一个开放型追问。
                       使用'你觉得呢？''如果换个条件会怎样？''用你自己的话说说看'。
                       目标：学生的话语应多于教练。"
  terminal(4条):      "本轮是否跟了开放型追问？"
                      "互动比例: 回应超过3句话→违规"
                      "开放提问: 用了'对不对/懂了吗'→违规"
                      "避免独白: 连续两轮没有提问→违规"
  → 合并后: stable_prefix 保留原则+示例
            terminal 只保留"避免独白"(连续两轮无提问=违规)
            删除: "本轮是否跟了开放型追问"(与stable重复)
                  "互动比例"(程序化覆盖 — Phase 97 compactness)
                  "开放提问禁止"(与stable的"使用开放型追问"重复)

协议 3 — 利用错误:
  stable_prefix(详细): "不要直接给正确答案。使用认知冲突引导他自己发现。
                       '顺着你的思路，你看这里会怎样？'
                       把错误正常化：'很多人一开始都这么想，正好是个突破口。'"
  terminal(精简):     "错误理解→用'顺着你的思路'引导。不给正确答案。"
  → 合并后(stable_prefix): 保留 stable 版本(有示例)
                           terminal 中删除此条目

协议 4 — 反馈具体:
  stable_prefix(详细): "不泛泛说'很好'——说'你刚才自己画图试出来的，这个方法很好'。
                       不泛泛说'不对'——说'到了第3步时逻辑断了，你再看这里？'"
  terminal(精简):     "反馈是否具体到过程？"
  → 合并后(stable_prefix): 保留 stable 版本(有正反例)
                           terminal 中删除此条目

协议 5 — 教完验证:
  stable_prefix(详细): "每完成一个教学概念，让学生独立输出验证。
                       使用'现在不看笔记，你自己试一下''你来讲一遍我听听'。
                       如果学生做不出来，说明需要换方式再教，而不是继续推进。"
  terminal(精简):     "教了新概念→statement末尾必须是独立验证指令。做不出→换方式再教。"
  → 合并后(stable_prefix): 保留 stable 版本
                           terminal 中删除此条目

协议 6 — 察觉情绪:
  stable_prefix(原则): "当学生表现出退缩、沮丧或沉默时，先共情再调整。
                       使用'这部分确实有点绕，我们拆成更小步骤'。
                       不空泛鼓励——把大目标切成学生能做到的小台阶。"
  terminal(具体):     "情绪检测: 学生回复突然变短/带负面词(太难了/算了吧/学不会/不想学了)？
                      是→先共情('这部分确实绕，很多人在这卡过')，拆成更小步骤。不直接教新内容。
                      此规则优先于'简短确认'豁免。"
  → 合并后: terminal 版本有 stable 版本没有的"检测条件"(变短/负面词列表)
            保留 terminal 版本(terminal_tutoring)
            stable_prefix 版本改为简短引用: "察觉学生情绪变化并及时调整——见终端情绪检测规则"

_diagram_plan 重复:
  stable_prefix(完整): 触发原则(结构关系vs语法符号)+正例反例+灰度判断+格式规范+示例(~600字符)
  terminal(精简):     "教学自查⑦: 本轮是否引入新概念/教操作/对比分类？是→JSON必须含_diagram_plan"
                      "教学用图: 结构关系→画图。代码语法→KaTeX。不确定→倾向不画图"
  → 合并后: 保留 stable_prefix 完整版(有触发逻辑+示例)
            terminal 中删除两个 diagram 条目
```

**去重后 terminal_tutoring 保留的规则（5-7 条）：**

```
1. 【引用安全】— 白名单检查（独特，不在 stable_prefix 中）
2. 【情绪检测】— 具体检测条件（比 stable 版本更精确）
3. 【学生反馈处理】— 三分类处理（独特，stable 只有"利用错误"原则）
4. 【避免独白】— 连续两轮无提问检查（独特，stable 有原则但无连续检查）
5. 【教学自查精简】— 仅保留⑦(_diagram_plan 检查，因为 stable 有完整规则故可删)...
   实际: 教学自查全部 7 项已在 stable_prefix + action_contract 中有覆盖
   → 整个"教学自查"块删除

保留的理由:
  - 引用安全: Phase 97 白名单模式, terminal 的检查逻辑与 stable 不同
  - 情绪检测: 具体的"变短/负面词"检测条件——这是 stable 版本没有的操作化规则
  - 学生反馈处理: 不知道/错误/困惑三种情况的三分支处理——stable 只有单一原则
  - 避免独白: 跨轮次检查(连续两轮)——terminal 的独特价值是它可以引用"最近两轮"的上下文
```

### 3.2 消解矛盾: 3 处矛盾的显式优先级

```
矛盾 1 — R107 vs R05 (引用句式):
  R107: "使用'之前你学了X，现在...'句式(X必须来自已学知识列表)"
  R05:  "禁止使用的句式: '在学/学过...'"
  解决: R05 禁止列表加例外 —
        "禁止'你刚才说/提到/想了解/在学/问过/聊到...'
         (例外: '之前你学了X，现在...'的X必须来自已学知识列表;
          '你刚才说的X'的X必须来自本轮可安全引用列表)"

矛盾 2 — R58 vs R22 (焦虑+提问):
  R58: "学生可能焦虑 → 禁止: 追问/时间压力/连续挑战"
  R22: "每轮教学输出后必须跟随至少一个开放型追问"
  解决: 在 R58 条文中加显式覆盖声明 —
        "学生可能焦虑 → 降一级难度。先做示范再让学生尝试。
         覆盖通用提问规则: 本轮不强制开放型追问。改为低压力开放式确认(如'想从哪里开始？')。
         禁止: 追问/时间压力/连续挑战。"

矛盾 3 — R62 vs R19 (前意向+诊断):
  R62: "学生尚未决定学习 → 禁止: 教学/练习/推荐行动"
  R19: "引入任何新概念前，必须先问学生对此了解多少"
  解决: 在 R62 条文中加显式覆盖声明 —
        "学生尚未决定学习 → 只探索感受和动机。
         覆盖先诊后教: 本轮不诊断、不教学。
         禁止: 教学/练习/推荐行动/诊断提问。"
```

### 3.3 降频: _diagram_plan 从 6→2 action_types 强制

```
当前: 6/8 action_types 的 _ACTION_TYPE_INSTRUCTIONS 中写"必须输出"

修改:
  scaffold:  "必须输出" → 不变（教学型轮次，图表最有价值）
  suggest:   "必须输出" → 不变（建议型轮次，对比/分类常用）
  probe:     "必须输出" → 删除（探测轮次不需要图表）
  challenge: "必须输出" → "如果挑战题涉及结构关系，可选输出 _diagram_plan"
  reflect:   "必须输出" → 删除（反思轮次不需要图表）
  pulse/defer/excursion: 不变（原本就不要求）

stable_prefix 图表规则增加:
  "probe/reflect 轮次: _diagram_plan 非强制。教学重点在对话互动，非视觉展示。"
```

### 3.4 程序化覆盖移除

```
以下规则已被 Phase 97 程序化约束强制执行——从 prompt 中移除:
  R86/R88: 句子截断(compactness 代码执行)
  R03: statement 必填(validator 代码执行)

保留精简版提示: "statement 简洁聚焦，一个核心点 + 一个追问。"
（不指定具体句子数——compactness 会自动截断）
```

---

## 四、Phase 98a-2: 重排

### 4.1 行为约束从位置 4 提升到位置 2

```
当前装配 (prompts.py:298-309):
  [0] stable_prefix
  [1] terminal_tutoring     ← 通用协议在位置 2
  [2] action_contract
  [3] policy_layer          ← 动态约束在位置 4 (含 behavioral_constraints)
  [4] context_layer
  [5] terminal_checklist

修改后:
  [0] stable_prefix         ← Tier 2 教学协议
  [1] behavioral_constraints ← Tier 1 动态约束(独立段, 从 policy_layer 提取)
  [2] terminal_tutoring     ← 精简后(5-7条自检规则)
  [3] action_contract       ← 输出格式
  [4] policy_layer          ← 上下文(不含 behavioral_constraints)
  [5] context_layer         ← 更多上下文
  [6] terminal_checklist    ← scaffold 专用
```

### 4.2 代码修改点

```
prompts.py build_coach_context():
  1. 独立调用 behavioral_constraints = _render_behavioral_constraints(...)
     放在 system_parts 的索引 1 位置
  2. 如果 behavioral_constraints 为空字符串 → 不插入(避免空段)

prompts.py _render_policy_layer():
  3. 移除 constraints 参数
  4. 移除 "rendered += '\n\n' + constraints" 逻辑
```

### 4.3 行为约束格式优化

```
当前格式(长句):
  "学生可能焦虑 → 降一级难度。先做示范再让学生尝试。禁止: 追问/时间压力/连续挑战。"

优化后(简短指令式):
  "焦虑→降难度，做示范，不追问。改为低压力确认。"

原因: 行为约束在位置 2 获得高注意力——但它需要被 LLM 快速解析。
     长句适合 Tier 2(上下文, 慢读), 短指令适合 Tier 1(约束, 快查)。
     每条约束 ≤30 字。
```

---

## 五、验证计划

### Phase 98a-1 验证

```
Step 1: 全量回归 python -m pytest tests/ -q → 1551/0/8

Step 2: anxious 画像, 1 跑, 10 轮, keyword+LLM judge
  目标: 学情诊断 ≥2, 深度互动 ≥3
  红线: 即时反馈/关系建立/效果验证 不下降

Step 3: 如果 anxious 达标 → 全画像(5画像) × 1 跑 × 10 轮
  确认无画像退化

Step 4: 如果任何画像退化 → 逐条回退合并规则, 定位退化源
```

### Phase 98a-2 验证

```
Step 1: 全量回归

Step 2: anxious 画像, 1 跑, 10 轮
  目标: 与 98a-1 得分持平或改善
  特别关注: 焦虑画像的即时反馈(行为约束提升应该改善焦虑体验)

Step 3: 全画像验证
```

---

## 六、修改文件清单

| 文件 | Phase | 变更 |
|------|:---:|------|
| `src/coach/llm/prompts.py` — `_STABLE_SYSTEM_PREFIX` | 98a-1 | 5/6 协议合并(保留详细版)、矛盾消解(R05 加例外)、图表规则加 probe/reflect 豁免 |
| `src/coach/llm/prompts.py` — `_render_terminal_tutoring_checklist()` | 98a-1 | 从 14 条精简到 5-7 条(引用安全+情绪检测+学生反馈处理+避免独白) |
| `src/coach/llm/prompts.py` — `_ACTION_TYPE_INSTRUCTIONS` | 98a-1 | probe/reflect 删除 _diagram_plan 要求; challenge 改为可选 |
| `src/coach/llm/prompts.py` — `_render_behavioral_constraints()` | 98a-2 | 格式优化(长句→短指令)、加覆盖声明 |
| `src/coach/llm/prompts.py` — `_render_policy_layer()` | 98a-2 | 移除 constraints 参数和追加逻辑 |
| `src/coach/llm/prompts.py` — `build_coach_context()` | 98a-2 | 独立调用 behavioral_constraints、插入 system_parts[1] |

---

## 七、风险与回退

| 风险 | 缓解 |
|------|------|
| 去重误删独特规则 → 特定行为退化 | terminal 只删除"与 stable_prefix 语义完全相同"的条目。独特规则(情绪检测条件/学生反馈三分支/避免独白)保留。Step 3 全画像验证 |
| stable_prefix 变更 → 首次缓存未命中 | 长度变化 <±10%(~350 chars)。首次调用后自动恢复 |
| 行为约束过于强势 → coach 机械 | 上限 5 条不变。格式改为短指令(≤30字)减少压迫感 |
| probe 无图表 → 探测质量下降 | probe 目标是诊断，不是教学——图表不是核心需求。如果审计显示 probe 轮次学生理解下降，Phase 98b 恢复 |
| 98a-1 vs 98a-2 交互 → 归因模糊 | 分 Phase 验证，每个 Phase 单变量实验 |

### 回退方式

```yaml
# coach_defaults.yaml (新增)
prompt_pruning:
  phase_98a_1_enabled: true   # 去重+消解矛盾+降频
  phase_98a_2_enabled: true   # 重排
```

如果 98a-2 导致退化 → `phase_98a_2_enabled: false` → 只保留 98a-1 的效果。如果 98a-1 也退化 → 两个都 false → 完整回退。
