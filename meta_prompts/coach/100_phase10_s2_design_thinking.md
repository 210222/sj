# Phase 10 S2 — LLM 输出校验 + 安全对齐 元提示词设计思考

> 编制日期: 2026-05-05
> 对齐源: Phase 10 S2 落地方案 (`reports/phase10_s2_plan.md`), Phase 10 S1 (LLM 客户端)
> 前置条件: Phase 10 S1 已 GO, `src/coach/llm/` 包可用, Python 1162 tests pass

---

## 0. 为什么这份思考文档

在写 S2 的元提示词之前，必须想清楚以下核心问题。LLM 内容校验不是一个简单的"加个 if 检查"——它涉及到教练引擎的安全架构根基。如果这些不先想透，生成的元提示词会沦为"加几行校验代码"的机械指令，而不是一个可落地的安全加固方案。

---

## 1. 核心架构决策

### 1.1 三层校验的顺序为什么重要

LLM 输出到 DSL 构建之间有三层校验，顺序不可互换：

```
LLM raw output → Schema 对齐 → 安全过滤 → 输出校验 → DSL 构建
                       ↑             ↑           ↑
                   必须先对齐    再过滤短语   最后校验完整性
```

理由：
- **Schema 对齐先做**：LLM 可能输出 DSL 不认识的字段。如果先做安全过滤，会在垃圾字段上浪费过滤资源。先对齐丢弃非法字段，后续过滤只在有意义的字段上操作。
- **安全过滤后做输出校验**：过滤可能替换字符串（forbidden → [已过滤]），所以输出校验必须在过滤之后，检查的是最终要进入 DSL 的 payload。
- **输出校验作为最后一道闸门**：在校验失败时整体回退规则模式，而不是部分回退。

### 1.2 ActionType 强制 — 为什么必须硬约束而不是软提示

LLM prompt 中已经写了"不要自选 action_type"，但 prompt 约束不是安全约束。

```
prompt 约束: "请使用系统指定的 action_type"    → 软约束，LLM 可能忽略
代码强制:   LLMSafetyFilter.enforce_action_type() → 硬约束，不可绕过
```

**决策**: 双重保障——prompt 中保留不选 action_type 的指令（减少 LLM 犯错概率），同时代码层面做强制覆盖（即使 LLM 选错了也被纠正）。

### 1.3 门禁审计 — 为什么需要独立模块而不是复用现有审计

现有审计（`src/coach/audit_health.py`、gate audit 等）记录的是**系统级事件**（门禁状态、P0 计数等）。LLM 门禁审计记录的是**内容级事件**（LLM 说了什么被 gate 拦了）。

两者数据结构完全不同：
- 系统级审计：`{gate_name, status, timestamp}`
- LLM 门禁审计：`{session_id, trace_id, llm_payload_truncated, gate_result, alignment_report, safety_report}`

混在一起会导致 audit schema 膨胀。独立模块保持审计链路清晰。

### 1.4 对齐报告的长度限制

LLM payload 可能很大（LLM 一次生成数千 token）。门禁审计日志如果存储完整 payload，内存会快速膨胀。

**决策**: `llm_payload` 只存前 500 字符 + `...truncated` 标记。完整的 LLM 响应在 $response 中已经返回给前端，审计只做"取证线索"用途。

---

## 2. 与现有安全机制的关系

### 2.1 S2 不替代任何现有机制

| 现有机制 | S2 做什么 | 关系 |
|---------|----------|------|
| `_filter_forbidden()` (agent.py:778) | 过滤 output 中的禁语 | S2 的 `LLMSafetyFilter` 是 LLM payload 专用的前置过滤；`_filter_forbidden` 保留作为最终输出过滤。双层保险。 |
| `DSLValidator.validate()` (dsl.py:23) | 校验 DSL 包完整性 | S2 的 `LLMDSLAligner` 在 DSL 构建之前做对齐；`DSLValidator` 在 DSL 构建之后做校验。一个是对齐，一个是校验。 |
| `GateEngine` (src/outer/) | 8 道安全门禁 | S2 的 `LLMGateAuditor` 在 gate 之后记录日志，不改动 gate 逻辑。 |
| `Semantic Safety 三件套` | 反事实/交叉检查/先例拦截 | S2 在校验层运行，三件套在门禁层运行，互不干扰。 |

### 2.2 S2 是"LLM 内容专用安全层"

Phase 0-9 的安全机制都是为**规则引擎输出**设计的。规则引擎的输出是确定的、可控的、可预测的。

LLM 输出本质上是**不确定的、不可控的、不可预测的**。所以需要一层专门的内容安全层来处理 LLM 特有的风险：

- 输出不符合 DSL 格式 → 对齐
- 输出包含禁用表述 → 过滤
- 输出试图篡改教练策略 → 强制覆盖

---

## 3. 边界情况处理

### 3.1 LLM 输出全部为空

```python
LLMResponse(content="")
# to_payload() → {"statement": ""}
# LLMOutputValidator → missing 'statement' + empty 'statement'
# LLMDSLAligner → valid=False
# 最终: 回退规则模式
```

### 3.2 LLM 输出超长

```python
# max_tokens=2000 已经限制了 LLM 输出长度
# 但在门禁审计中只存前 500 字符
# 对齐报告中的 dropped_fields 不含被截断的内容
```

### 3.3 forbidden 短语匹配到 payload 中非文本字段

```python
payload = {"difficulty": 0.8, "hints_allowed": 2}
# difficulty 和 hints_allowed 不是字符串，不匹配
# filter_payload 只递归扫描字符串值
```

### 3.4 LLM 输出合法的 DSL 但内容有误（如错误的教学建议）

S2 不做内容正确性校验。内容正确性由：
1. LLM 自身的质量保证
2. 后续的 `GateEngine`（如果内容触犯安全规则）
3. 用户在对话中的反馈（主权脉冲、改写）

S2 只做**形式校验**（格式对不对）+ **安全过滤**（有没有禁语），不做**内容正确性校验**。

### 3.5 LLM 输出中有多个可能的 action_type（如 JSON 同时包含 challenge 和 reflect 字段）

```python
payload = {
    "statement": "...",
    "objective": "challenge 字段",
    "question": "reflect 字段",
}
# LLMDSLAligner 使用规则引擎确定的 action_type
# 如果 action_type="reflect"，丢弃 "objective"（challenge 的专属字段）
# 如果 action_type="challenge"，丢弃 "question"（但 question 是通用字段？保留）
```

通用字段策略：`statement`、`question`、`hint`、`difficulty` 是所有 action_type 的通用字段，不会因为 action_type 不同而被丢弃。

---

## 4. 测试策略思考

### 4.1 如何测试"LLM 输出含禁语被过滤"

因为 LLM 调用在测试环境中不可用（无 API Key），S2 的测试直接用构造的 payload 调用 `LLMSafetyFilter.filter_payload()`。

```
测试 payload: {"statement": "我比你更了解你，应该怎么做"}
→ 过滤后: {"statement": "[已过滤]，应该怎么做"}
→ triggered_phrases: ["我比你更了解你"]
```

### 4.2 如何测试"LLM 不使能时全路径跳过"

在 `test_llm_integration.py` 中已有 `test_agent_act_default_does_not_use_llm`。S2 的集成测试在 LLM disabled 时验证：

- response 中不含 `llm_alignment` 字段
- response 中不含 `llm_safety` 字段
- 不调用 `LLMGateAuditor.record_gate_block()`

### 4.3 如何测试门禁审计

门禁审计不依赖真实 LLM 调用。测试直接构造 gate 阻断场景：

```python
# 模拟 gate_decision != "GO" 的场景
LLMGateAuditor.record_gate_block(
    session_id="test",
    trace_id="trace-test",
    action_type="suggest",
    llm_payload={"statement": "test"},
    gate_result={"decision": "BLOCK", "gate": "L2"},
)
assert len(LLMGateAuditor.get_recent_blocked()) == 1
```

---

## 5. S2 在整个 Phase 10 中的位置

```
Phase 10:
  S1: LLM 客户端 + 基础集成      ← 已 GO
  S2: 输出校验 + 安全对齐        ← 本次
  S3: WebSocket 流式推送          ← 后续
  S4: 记忆增强 + 多轮上下文       ← 后续
  S5: 代码沙箱                   ← 后续
```

S2 是 Phase 10 的安全基石。没有 S2，LLM 输出是裸奔的——格式错误、禁语、action_type 篡改都不受控。

S3（流式推送）依赖 S2 的校验逻辑：流式 chunk 也需要经过输出校验才能推送给用户。所以 S2 必须在 S3 之前完成。

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LLMDSLAligner 过于保守（丢弃太多有用字段） | 中 | 低 | alignment_report 包含 dropped_fields，可调试 |
| forbidden_phrases 匹配到正常教学内容（如"你应该"被误杀） | 低 | 低 | payload 的 statement 包含"你应该试试"→ partial match？不，短语匹配是精确子串匹配。如果"你应该听我的"是短语，"你应该试试"不会触发。 |
| 门禁审计日志内存溢出 | 低 | 中 | 只存前 500 字符 + `get_recent_blocked(limit=20)` 限制 |
| 三层校验增加 LLM 路径延迟 | 低 | 低 | 校验是纯本地 CPU 操作，耗时 < 1ms，远小于 LLM API 调用的 1-5s |
