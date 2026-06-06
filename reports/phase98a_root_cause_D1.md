# D1=1 根源分析 — 为什么静态 prompt 修剪无法解决"先诊后教"

**日期**: 2026-06-06
**数据**: Phase 98a-1 修复后，anxious 20 轮审计 D1=1（与修复前相同）

---

## 一、直接根因：规则类型错配

D1=1 不是内容问题——是位置问题。

```
同一个语义的"探测闭环"规则:
  放在 stable_prefix(位置1): D1 = 1  ← 不执行
  放在 terminal(位置2):     D1 = ?  ← 之前 46 个 Phase 都在这里

为什么位置决定执行:
  stable_prefix 在 LLM 处理 prompt 时是"背景知识"——它被读了，被理解了，
  但在 decoding 时刻不是"行动触发器"。
  
  terminal 在 decoding 时刻被重新关注——LLM 生成每个 token 时都会回看
  prompt 末尾的指令。terminal 规则是"行动触发器"。
```

**6 条协议可以按"注意力需求"分为两类：**

```
Type A — 解码触发型（需要 terminal 位置）:
  先诊后教:   必须在新话题第一轮触发——错过了就整轮错了
  每轮提问:   必须在每轮末尾触发——terminal 的 recency bias 最高
  避免独白:   跨轮检查——必须在 decoding 时比较当前轮和上一轮
  教完验证:   必须在教完概念后立即触发——时机敏感

Type B — 知识型（stable_prefix 足够）:
  引用安全:   持续生效的约束——LLM 知道规则后自动应用
  图表规则:   适用时自动触发——不需要每轮提醒
  反馈具体:   给出反馈时自然应用——是"怎么做好"不是"记得做"
```

探测闭环是 Type A——它在 terminal 存在了 46 个 Phase 不是因为前人忘了去重，而是因为它的位置本身就是功能的一部分。

---

## 二、深层根因：静态 prompt 装配假设"所有规则每轮都相关"

当前 `_render_terminal_tutoring_checklist()` 不接受任何参数—它总是返回相同的 3-4 条规则：

```python
def _render_terminal_tutoring_checklist() -> str:
    return """最终输出前自检（最高优先级）:
- 【情绪检测】...     ← 每轮都显示，即使学生没有情绪波动
- 【学生反馈处理】...  ← 每轮都显示，即使学生没有表达困惑
- 【避免独白】...     ← 每轮都显示（这个是合理的——每轮都需要检查）
```

**实际上每轮只需要 1-2 条，而不是 3-4 条：**

```
新话题第一轮+学生正常:        只需要"先诊后教"
上一轮探测过+学生正确回答:    只需要"探测闭环"
学生表达困惑:                只需要"学生反馈处理"
学生情绪低落:                只需要"情绪检测"
普通教学轮:                  只需要"避免独白"+ "教完验证"
```

当 terminal 只有 3-4 条时，3 条不相关的规则不会淹没 1 条相关的。但 14 条时，相关的 1 条被 13 条不相关的淹没。**terminal 精简到 3-4 条已经大幅改善了无关规则的干扰**——但把"探测闭环"从 terminal 移除则直接删除了唯一与 D1 相关的解码触发器。

---

## 三、元根因：prompt 装配是上下文无关的

`build_coach_context()` 有丰富的上下文数据可以驱动条件化规则显示：

```
已有数据:
  user_message → 可以检测情绪词/困惑词 → 决定是否显示"情绪检测"/"学生反馈处理"
  action_type → 知道当前是什么模式 → 决定是否显示"避免独白"(pulse/defer 可能不需要)
  
跨轮数据(可以从 agent 层传入):
  上一轮的 action_type → 是否探测过 → 决定是否显示"探测闭环"
  当前是否新话题 → 决定是否显示"先诊后教"
  上一轮是否教了新概念 → 决定是否显示"教完验证"
```

但这些数据从未被传入 terminal 渲染函数。terminal 是唯一**完全无参数**的 prompt 段——它不感知任何上下文。

---

## 四、修复路径

### Phase 98a-1 补丁（立即，1 行）

```
回退 Fix 1: 从 stable_prefix 移除"探测后处理"段
恢复 terminal "探测闭环": 作为第 4 条规则加回 terminal

terminal 回到 4 条: 情绪检测/探测闭环/学生反馈处理/避免独白
```

**为什么 4 条不会退化**: Phase 98a 去重已经把 14 条减到 4 条。4 条规则的注意力竞争远低于 14 条。D3 从 2→3 的数据证明了这一点——terminal 精简后，保留的规则获得了更高的遵从度。

### Phase 98b（架构改进，2-3 天）

修改 `_render_terminal_tutoring_checklist()` 接受上下文参数，按需显示规则：

```python
def _render_terminal_tutoring_checklist(
    user_message: str = "",
    previous_action_type: str = "",
    is_new_topic: bool = False,
    just_taught_concept: bool = False,
) -> str:
    rules = []
    
    # Always
    rules.append("【避免独白】...")
    
    # Conditional — only when relevant
    if is_new_topic and previous_action_type != "probe":
        rules.append("【先诊后教】...")  # ← 这就是 D1 的答案
    elif previous_action_type == "probe":
        rules.append("【探测闭环】...")
    
    if _detect_distress(user_message):
        rules.append("【情绪检测】...")
    if _detect_confusion(user_message):
        rules.append("【学生反馈处理】...")
    if just_taught_concept:
        rules.append("【教完验证】...")
    
    return "\n".join(rules) if rules else ""
```

**预期效果**: 每轮 terminal 只有 1-3 条高度相关的规则。LLM 注意力不再被无关规则稀释。"先诊后教"在新话题轮次获得 100% 的 terminal 注意力。

---

## 五、为什么 Phase 98a 的"静态去重"仍然有价值

```
Phase 98a 做了什么:
  ✅ 去除了 10 条完全重复的规则（14→4）
  ✅ 消除了图表规则的双重版本
  ✅ 保留了 3 条独特的终端规则（情绪检测/学生反馈处理/避免独白）
  ✅ D3 从 2→3（terminal 精简→保留规则获得更高遵从度）

Phase 98a 没做什么:
  ❌ 修复 D1（探测闭环被错误地从终端移除）
  ❌ 让终端上下文感知（架构限制——terminal 函数不接收参数）
```

Phase 98a 是正确的一步——它清理了冗余，降低了注意力稀释。D1 需要 Phase 98b 解决。两者的关系不是"替代"——是"基础"和"进阶"。
