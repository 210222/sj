# Phase 12: 规则引擎重建 — Fallback 教学模板深度思考

## 问题：为什么纯规则只有 2.8/24？

### 根因链

穷举测试（256 组合）明确显示：LLM OFF 平均质量 **2.8/24**，LLM ON 平均 **16.6/24**。差距 5.9 倍。

```
_build_payload() 返回模板字典
  ↓ 字段值 = 用户原始输入（无任何教学内容）
  ↓ DSLBuilder 格式化输出
  ↓ 回复极短、无内容、无个性化、无鼓励
  ↓ 六维评分全面崩溃
  ↓ 2.8/24
```

### 核心缺陷

`src/coach/composer.py:120-132` 的 `_build_payload()`：

```python
"scaffold": {"step": intent, ...}       # step = 用户的问题原文！
"suggest": {"option": intent, ...}      # option = 用户的问题原文！
"reflect": {"question": intent, ...}    # question = 用户的问题原文！
"probe": {"prompt": intent, "expected_skill": "general"}  # 永远用 "general"
```

这些模板没有存储任何教学语句。当 LLM 不可用时，**教练系统实际上无话可说**。

### 为什么 ultimate_quality_test 显示 17.6/24？

12 组合测试中，`baseline_rules` 和 `all_off` 配置显示 `llm=True`——说明该测试的配置隔离有 bug，LLM 仍然在运行。真实规则引擎分数应从穷举测试的 LLM OFF 组读取。

### 修复方向

**短期（S12.1-S12.2）**：为每个 action_type + 常见意图预写结构化教学模板

**中期（S12.3）**：模板级个性化引用 + 鼓励性语言

**长期（S12.4）**：模板间状态共享（跨轮连续性）

---

## S12.1 — 基础教学模板库

### 设计原则

1. **每个意图模板包含完整回复**：statement（讲解）+ question（追问）+ steps（步骤拆解）
2. **覆盖高频教学意图**：变量、类型、循环、函数、列表、条件等编程基础
3. **结构化输出**：复用 LLM 的 `{"statement": ..., "steps": [...], "question": ...}` schema

### 数据来源

从 exhaustive 测试日志中提取 LLM 生成的高质量回复（评分 18+/24 的样本），将其转化为结构化模板。

### 模板示例

```yaml
fallback_templates:
  scaffold:
    python_variable:
      statement: "变量就像一个带标签的盒子。你把数据放进去，标签就是变量名。比如 `age = 18` 就把数字18存进了名为age的变量。"
      steps:
        - "给变量起个名字（如 age、name）"
        - "用等号 = 把值赋给变量"
        - "用变量名来使用里面的值"
      question: "你想试试创建一个存有你名字的变量吗？"
    python_type:
      statement: "type() 函数可以查看变量的类型。比如 type(42) 返回 int，type('hello') 返回 str。不同类型帮计算机正确理解数据——数字能算，文字能拼。"
      steps:
        - "用 type(变量名) 查看类型"
        - "int 是整数，str 是字符串，float 是小数"
        - "不同类型不能直接混用，需要转换"
      question: "你觉得数字和文本在计算机里存储的方式一样吗？"
  suggest: { ... }
  reflect: { ... }
  probe: { ... }
```

### 实现方式

在 `config/coach_defaults.yaml` 新增 `fallback_templates` 配置段 + `src/coach/fallback.py` 模板引擎。

---

## S12.2 — 上下文感知 Fallback

### 问题

当前 fallback 每轮独立，不知道前一轮说了什么。第二轮回复无法引用第一轮的内容。

### 解决方案

- FallbackEnginer 维护对话状态队列（最近 3 轮）
- 从 `UserStateTracker` 读取已覆盖话题
- 构建 `{conversation_summary}` 用于模板选择

---

## S12.3 — 鼓励性与个性化模板

### 问题

LLM OFF 时 encouragement = 0.00/4, personalization = 0.05/4。纯规则回复完全没有鼓励和个性化。

### 解决方案

- 每轮回复随机选择 1-2 句鼓励语插入到 statement 开头或结尾
- 从历史对话中提取用户用过的比喻或关键词，注入模板
- 鼓励语分级：新手（更多鼓励）vs 进阶（少一些）

---

## S12.4 — 诊断题 Fallback 修复

### 问题

`_build_payload("probe", intent)` 返回 `{"prompt": intent, "expected_skill": "general"}`。diagnostic_engine 的 fallback probe 也一直问"认知主权"。

### 解决方案

- 从 covered_topics 或对话历史推断当前话题
- 为每个话题预写 3-5 道诊断题（难/中/易三级）
- 诊断题考察真正教过的内容

---

## 执行优先级

```
P0: S12.1 (模板库) → S12.2 (上下文)  
P1: S12.3 (鼓励/个性化) → S12.4 (诊断题)
```

## 成功标准

| 指标 | 当前 | 目标 |
|------|------|------|
| 规则引擎 avg quality | 2.8/24 | 12+/24 |
| encouragement | 0.00/4 | 2.0+/4 |
| personalization | 0.05/4 | 1.5+/4 |
| structure | 0.73/4 | 2.5+/4 |
| relevance | 0.05/4 | 2.0+/4 |
