# Phase 10 S4 — 记忆增强 + 多轮上下文 元提示词设计思考

> 编制日期: 2026-05-05
> 对齐源: Phase 10 S1+S2+S3 已 GO, Phase 10 落地方案 §4
> 前置条件: 1192 tests pass, `src/coach/llm/prompts.py` 现有 build_coach_context 函数

---

## 0. 为什么这份思考文档

S4（记忆增强 + 多轮上下文）看起来是"把历史对话塞进 LLM prompt"，但三个核心问题必须先想清楚：

1. **Prompt 长度控制** — 注入历史对话会把 prompt 撑长。LLM 的 max_tokens 是 2000，历史和记忆占用的 token 越多，生成内容的 token 越少。
2. **信息选择性** — 不是所有历史都有用。5 轮前的"你好"没有注入价值，但用户说过的"我卡在递归上了"很有价值。
3. **记忆污染** — LLM 可能把之前自己的错误回答当成事实，在多轮中持续放大。

---

## 1. 核心架构决策

### 1.1 Prompt 预算分配 — 为什么历史不超过 30%

LLM 单次调用的 context window 受 `max_tokens: 2000` 限制。prompt 中的每一段历史都会吃掉生成 token 的配额。

**决策**: 硬性预算分配

```
prompt 预算 = max_tokens × 60%（约 1200 tokens）
  ├─ 系统指令 + 用户画像: ~400 tokens（固定）
  ├─ 对话历史: ~400 tokens（最多 5 轮）
  ├─ 记忆片段: ~200 tokens（最多 3 条）
  └─ 用户消息: ~200 tokens（当前输入）
生成预算 = max_tokens × 40%（约 800 tokens）
```

理由：
- **系统指令不可压缩**：TTM 策略、SDT 描述、JSON 格式要求必须完整
- **对话历史限 5 轮**：超过 5 轮的历史对当前回复的质量贡献递减（用户心理学研究支持）
- **记忆片段限 3 条**：ArchivalMemory 的搜索结果取 top-3，每条 ~60 tokens
- **不可突破上限**：当历史和记忆超预算时，从最旧开始丢弃

### 1.2 历史注入策略 — why 摘要优先于全文

两种策略对比：

| 策略 | 优点 | 缺点 |
|------|------|------|
| 全文注入 | 信息无损 | 快速撑爆 token，且 5 轮前的"好的"无意义 |
| 摘要注入 | token 高效 | 摘要本身消耗 token，且可能有损 |
| **选择性注入** | 兼顾深度与效率 | 需要选择策略 |

**决策**: 选择性注入 — 选择有信息的轮次，跳过无信息轮次。

选择规则：
- **保留**：用户的提问（含知识点关键词）、LLM 的 scaffold 响应、TTM 阶段变化
- **跳过**：用户的"好的""谢谢"、脉冲确认轮、过长的重复

每轮存储时打标签：
```python
turn_data = {
    "user_input": "教我递归",
    "action_type": "scaffold",
    "has_info": True,  # 用户输入 > 5 字 或 包含知识点关键词
    "topics": ["递归", "栈"],  # 知识点提取
}
```

### 1.3 知识覆盖追踪 — 轻量方案 vs 向量方案

| 方案 | 复杂度 | 准确度 | 维护成本 |
|------|--------|--------|---------|
| 关键词集合 | 低 | 中 | 零维护 |
| 向量嵌入 | 高 | 高 | 需要向量 DB |
| LLM 标注 | 中 | 高 | 每轮消耗 token |

**决策**: 关键词集合（轻量方案），后续可升级为向量方案。

实现：
```
_covered_topics: dict[str, int] = {}  # 话题 → 提及次数
```

关键词来源：
- 用户输入的意图词（"递归"、"for 循环"）
- LLM 响应的知识点标注（LLM 在 JSON 中带回 `topics` 字段）
- 规则的 intent 标签（已有关键词匹配）

### 1.4 是否改 build_coach_context 签名

现有 `build_coach_context(intent, action_type, ttm_stage, sdt_profile, user_message)` 签名。

**决策**: 不改签名，新增参数 + 解包。保持向后兼容：

```python
def build_coach_context(
    intent: str,
    action_type: str,
    ttm_stage: str | None = None,
    sdt_profile: dict | None = None,
    user_message: str = "",
    # ★ S4 新增
    recent_history: list[dict] | None = None,  # 最近对话历史
    covered_topics: dict[str, int] | None = None,  # 已覆盖知识领域
    archival_memories: list[dict] | None = None,  # 长期记忆
) -> dict:
```

这样调用方可以选择性传入，不传时行为与 S1 完全一致。

### 1.5 S4 是否改 agent.py

需要改：
1. `act()` 中在 `build_coach_context` 调用处传入新增参数
2. `act()` 中新增知识覆盖追踪逻辑（在 intent 解析后、LLM 调用前）
3. `_get_covered_topics()` 方法（已存在于 agent.py 的意识中，需实现）

不改：
- `SessionMemory` 的 store/recall 签名
- `CoachAgent` 的构造方法
- 现有规则路径

---

## 2. S4 与已有机制的关系

| 组件 | S4 做什么 | 关系 |
|------|----------|------|
| `build_coach_context()` | 新增 history/memory 参数 | 不改现有参数，新增可选参数 |
| `SessionMemory.recall()` | 复用现有方法获取历史 | 不改，直接调用 |
| `ArchivalMemory.search()` | 复用现有语义搜索 | 不改，直接调用 |
| `LLMClient.generate()` | 保持不变 | 不改，prompt 内容变长但结构不变 |
| `prompts.py` SYSTEM_PROMPT | 新增历史/知识区段 | 保持 JSON 输出要求不变 |
| `agent.py §4.5` | 增强 context 构建 | 不改现有 LLM 路径 |
| S2 三层校验 | 后续 S4 输出也要通过 | 不改 S2，校验在生成之后执行 |

### 2.1 记忆污染防护

注入历史引入的风险：LLM 可能复读之前的错误回答。

**缓解策略**:
- 历史只保留用户的输入 + 教练的 action_type，不保留之前 LLM 生成的原始内容
- 每轮历史格式：`user: 教我递归 → coach: scaffold(递归,栈)`
- 不注入之前的 LLM JSON payload（只注入意图和知识点标签）

---

## 3. 边界情况处理

### 3.1 首次对话无历史

```
covered_topics = {}
recent_history = []
→ prompt 中不包含历史区段
→ 与 S1 行为完全一致
```

### 3.2 历史超过预算长度

```
超过 3 轮历史时，从最旧开始丢弃。
最少保留：最近的 1 轮用户输入（保证上下文连贯性）。
```

### 3.3 知识覆盖为空的 action_type

```
pulse（主权脉冲）/ excursion（远足）等非教学 action_type
→ 不追踪知识覆盖
→ covered_topics 在 prompt 中标注为 "当前为脉冲确认/探索模式"
```

### 3.4 LLM 返回 topics 字段

LLM 需要在 JSON 中可选返回 `topics` 字段，用于更新 `_covered_topics`。

```
用户: "教我递归"
LLM JSON: {
    "statement": "递归就是函数调用自己...",
    "topics": ["递归", "栈", "base case"]
}
```

如果 LLM 不返回 topics 字段，从 user_input 的 intent 关键词中提取。

### 3.5 知识覆盖的去重

同一知识点多次提及不再重复添加，只增加计数。

```
_covered_topics = {"递归": 3, "栈": 1, "循环": 5}
```

LLM prompt 中显示为：
```
已涵盖知识: 递归(3次), 栈(1次), 循环(5次)
```

---

## 4. 测试策略

### 4.1 上下文增强测试

```
test_context_enhance.py:
  - build_coach_context 含历史时 prompt 包含历史区段
  - build_coach_context 无历史时 prompt 不含历史区段
  - 历史超过 5 轮时截断到最近 5 轮
  - 历史格式正确（user: ... → coach: ...）
  - 知识覆盖字段格式正确
```

### 4.2 学习路径追踪测试

```
test_learning_path.py:
  - 新对话 covered_topics 为空
  - scaffold 后 covered_topics 增加
  - 重复话题不重复添加
  - pulse/excursion 不追踪知识
  - LLM 返回 topics 字段被正确解析
```

### 4.3 集成测试

```
test_s4_integration.py:
  - agent.act() 带历史时 LLM prompt 含历史
  - agent.act() 无历史时 LLM prompt 不含历史
  - 多次调用后知识覆盖持续累积
  - LLM 禁用时知识覆盖不追踪（零影响）
```

---

## 5. S4 在整个 Phase 10 中的位置

```
Phase 10:
  S1: LLM 客户端 + 基础集成      ← GO ✅
  S2: 输出校验 + 安全对齐        ← GO ✅
  S3: WebSocket 流式推送          ← 元提示词已创建
  S4: 记忆增强 + 多轮上下文       ← 本次
  S5: 代码沙箱                   ← 后续
```

S4 是 LLM 从"单轮问答"到"多轮教练"的关键升级。没有 S4，LLM 每次对话都是"初次见面"——不知道之前教过什么，可能重复、矛盾、遗漏。

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| prompt 超长导致 LLM 截断 | 中 | 中 | 硬性预算分配，历史超预算丢弃最旧 |
| LLM 复读历史错误 | 低 | 低 | 只注入意图标签，不注入原始 LLM 输出 |
| 知识覆盖污染（错误知识点进入追踪） | 低 | 低 | topics 只来自 intent 关键词匹配，LLM 返回的 topics 二次校验 |
| 首次对话行为退化 | 低 | 低 | 无历史/无知识时行为与 S1 一致 |
| agent.py 复杂度增加 | 中 | 低 | 知识追踪封装为独立方法 `_track_coverage()`，不散落在 act() 中 |
