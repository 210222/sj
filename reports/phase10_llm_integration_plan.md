# Phase 10 — LLM 内容生成引擎集成 完整落地方案

**编制日期**: 2026-05-05
**对齐源**: AI 教练引擎现有架构（Phase 0-8 冻结）+ LLM API（Claude/OpenAI）
**当前基线**: Phase 0-9 全部 GO，1070 tests pass，API 服务运行中
**前置**: 用户提供 LLM API Key

---

## 0. 执行摘要

### 0.1 为什么要做

当前 Coach 引擎在**规则模式**下运行：关键词匹配 → 模板文案。教练框架完整（8 种动作、TTM/SDT/心流、安全门禁、主权脉冲），但教学内容是固定模板。

接入 LLM 后，同样的教练框架不变，只是 **payload 生成**从模板替换为 LLM 生成：

```
用户 "教我 Python 循环"
  → CoachAgent.act()
    → intent = "scaffold"            (关键词匹配，规则模式不变)
    → TTM 阶段检测                    (规则模式不变)
    → SDT 动机评估                    (规则模式不变)
    → ── LLM 在这里介入 ──
    → 生成 payload: "Python 的 for 循环用来遍历序列... 试试看这段代码..."
    → ── 安全管线不变 ──
    → 8 道门禁检查                    (规则模式不变)
    → 主权脉冲/远足检测                (规则模式不变)
    → 返回给用户
```

### 0.2 总量

| 指标 | 数量 | 说明 |
|------|------|------|
| 新增源文件 | ~5 | llm_client.py, llm_prompt.py, llm_config.py, prompt_templates/ |
| 修改源文件 | ~3 | agent.py, composer.py, coach_defaults.yaml |
| 新增测试 | ~40 | LLM 客户端/提示词/集成/回退 |
| 新增合约 | 1 | llm_contract.json |
| 现有 tests 必须保持 pass | 1070 | 不可回退 |

### 0.3 红线

- **禁止绕过 8 道门禁** — LLM 输出必须经过 GateEngine 才能到达用户
- **禁止在架构中硬编码 API Key** — 只从环境变量或 `.env` 文件读取
- **禁止删除规则回退** — LLM 调用失败时必须平滑降级为规则模板
- **禁止修改已冻结模块**: `src/inner/**`, `src/middle/**`, `src/outer/**`, `src/mapek/**`, `src/cohort/**`

---

## 1. 架构设计

### 1.1 LLM 在现有架构中的位置

```
                              CoachAgent.act()
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            intent 解析 (规则)             TTM/SDT/Flow (规则)
                    │                               │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │       LLM Content Gen         │  ← 新增：LLM层
                    │  (llm_client.py)              │
                    │   ↓                           │
                    │  coach_context → prompt       │
                    │  → LLM API → payload          │
                    │  → 退火到 DSL schema           │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │       安全管线 (不变)           │
                    │  V18.8 脉冲/远足               │
                    │  GateEngine 8道                │
                    │  Semantic Safety 三件套        │
                    └───────────────────────────────┘
```

### 1.2 核心文件

```
src/coach/
├── agent.py          # ◀ 修改：act() 中调用 LLM 替代模板
├── composer.py       # ◀ 修改：新增 LLM-aware compose 路径
├── llm/              # ★ 新增：LLM 集成包
│   ├── __init__.py
│   ├── client.py     # LLM API 客户端（Claude/OpenAI 抽象）
│   ├── prompts.py    # 提示词模板（按 action_type 分模板）
│   ├── config.py     # LLM 配置读取 + API Key 管理
│   └── schemas.py    # LLM 输出 schema 定义 + 校验
├── dsl.py            # 修改：新增 LLM payload → DSL 映射
config/
├── coach_defaults.yaml  # ◀ 修改：新增 llm: 配置节
├── prompts/             # ★ 新增：提示词模板目录
│   ├── scaffold.md      # "教我/怎么" 场景模板
│   ├── probe.md         # "考考我" 场景模板
│   ├── challenge.md     # "挑战" 场景模板
│   ├── reflect.md       # "反思" 场景模板
│   └── suggest.md       # 通用建议模板
tests/
├── test_llm_client.py   # ★ 新增：LLM 客户端测试
├── test_llm_prompts.py  # ★ 新增：提示词模板测试
└── test_coach_agent_llm.py  # ★ 新增：agent LLM 集成测试
```

---

## 2. 分阶段实施

### 阶段 1（LLM 客户端 + 基础集成）— 2 天

**目标**: LLM 可调用，agent 能选择 LLM 或规则生成 payload

#### S1.1: 配置与合约

- 在 `coach_defaults.yaml` 新增 `llm:` 配置节：

```yaml
# ── Phase 10: LLM 内容生成引擎 ──
llm:
  enabled: false                    # 默认关闭，不影响现有行为
  provider: claude                  # claude | openai | custom
  model: claude-sonnet-4-6         # 模型名
  api_key_env: "LLM_API_KEY"       # 环境变量名
  timeout_s: 30                     # API 调用超时
  max_retries: 2                    # 重试次数
  temperature: 0.7                  # 生成温度
  max_tokens: 2000                  # 最大输出 token
  fallback_to_rules: true           # LLM 失败时回退到规则模式
  streaming: false                  # 是否启用流式输出（Phase 10 后续）
```

- 新建 `contracts/llm_contract.json`：

```json
{
  "contract_id": "llm_contract",
  "version": "1.0.0",
  "status": "frozen",
  "interfaces": {
    "LLMClient": {
      "generate": {"input": "coach_context: dict", "output": "LLMResponse"},
      "validate": {"input": "raw: dict", "output": "ValidatedPayload"}
    }
  },
  "field_definitions": {
    "coach_context": "包含 intent, action_type, ttm_stage, sdt_scores, user_message 等上下文",
    "LLMResponse": "LLM 原始响应，必须包含 DSL schema 兼容的 payload"
  }
}
```

#### S1.2: LLM 客户端

新建 `src/coach/llm/client.py`：

```python
class LLMClient:
    """LLM API 客户端 — 支持 Claude 和 OpenAI。

    核心设计:
    - provider 抽象: 通过统一 _call_api() 接口
    - 超时 + 重试 + 熔断
    - 流式/非流式双模式（流式后续阶段实现）
    - 始终可回退: 任何异常 → raise LLMError → 上层回退规则模式
    """

    def generate(self, context: CoachContext) -> LLMResponse:
        """根据教练上下文生成教学内容。

        Args:
            context: 包含 intent, action_type, user_message,
                    ttm_stage, sdt_scores, memory 等

        Returns:
            LLMResponse: 包含生成的 payload + 元数据

        Raises:
            LLMError: API 调用失败时，上层 catch 后回退规则模式
        """
```

#### S1.3: 提示词模板

新建 `src/coach/llm/prompts.py`，按 action_type 设计提示词结构：

```python
# 核心提示词结构（CoT 链式思考）

COACH_SYSTEM_PROMPT = """你是 Coherence 认知主权保护系统的教练引擎。

你的角色是 {action_type}。

当前用户画像:
- TTM 阶段: {ttm_stage}（{ttm_explanation}）
- 动机状态: 自主性 {autonomy}/1.0, 胜任感 {competence}/1.0, 关联性 {relatedness}/1.0
- 历史交互: {turn_count} 轮

输出要求:
1. 只输出 JSON，不输出其他文字
2. JSON 必须包含 "statement"（主要回复内容）
3. JSON 可选包含 "question", "step", "option", "hint", "difficulty"
4. 使用中文回复
5. 尊重用户的认知主权，不得代替用户做决定
6. 保持与用户当前 TTM 阶段一致的干预策略
"""
```

#### S1.4: agent.py 改造

在 `CoachAgent.act()` 中新增 LLM 路径：

```python
def act(self, user_input: str, context: dict | None = None) -> dict:
    ctx = context or {}
    # ... 现有逻辑不变（intent 解析、脉冲、远足、TTM/SDT）...

    # ★ 新增：LLM 内容生成
    llm_cfg = self._cfg().get("llm", {})
    use_llm = llm_cfg.get("enabled", False)

    if use_llm:
        try:
            coach_context = self._build_llm_context(
                user_input, intent, ttm_stage, sdt_profile
            )
            llm_response = self._llm_client.generate(coach_context)
            payload = llm_response.to_payload()
            # payload 仍然经过现有安全管线
        except LLMError:
            if llm_cfg.get("fallback_to_rules", True):
                payload = self.composer.build_payload(action_type, intent)
            else:
                raise
    else:
        # 现有规则路径不变
        payload = self.composer.build_payload(action_type, intent)

    # ... 后续管线不变（门禁、脉冲、远足）...
```

### 阶段 2（内容质量 + 安全）— 1 天

**目标**: LLM 输出被教练框架正确约束，不绕过安全设计

#### S2.1: LLM 输出校验

- LLM 响应必须通过 DSL schema 校验（`src/coach/dsl.py` 的 `DSLValidator`）
- payload 必须包含 `statement` 字段（不能为空）
- 过滤 forbidden_phrases（来自 `relational_safety` 配置）

#### S2.2: action_type 对齐

- LLM 生成的 `action_type` 必须与规则引擎选择的一致
- 如果 LLM 输出包含自选的 action_type，以规则引擎为准（不允许 LLM 自行决定教练策略）

#### S2.3: 门禁后校验

- LLM payload 通过 GateEngine 后，如果被 gate 阻断，记录 LLM 输出内容到审计日志
- 用于后续分析 LLM 哪些输出触发了门禁

### 阶段 3（流式输出 WebSocket）— 1 天

**目标**: LLM 内容通过 WebSocket 流式推送到前端

#### S3.1: 流式客户端

- `LLMClient.generate_stream()` 返回 AsyncGenerator
- 支持 SSE/WebSocket 两种推送方式

#### S3.2: WS 路由改造

- 现有 `api/routers/chat.py` 的 `/chat/ws` 端点
- 新增 LLM 流式写入：每个 chunk 推一个 `WSMessage(type="coach_chunk", ...)`
- 完成后推送完整 payload + 安全校验结果

### 阶段 4（记忆增强 + 多轮上下文）— 1 天

**目标**: LLM 感知对话历史和用户学习进度

#### S4.1: Context 增强

将 `SessionMemory` 中的最近轮次注入 LLM prompt：

```python
llm_context = {
    "recent_history": self.memory.recall(intent, limit=5),
    "user_progress": {
        "ttm_stage": ttm_stage,
        "sdt_scores": sdt_profile,
        "interaction_count": len(self._interaction_history),
        "previous_topics": self._get_covered_topics(),
    },
}
```

#### S4.2: 学习路径追踪

- 在 LLM prompt 中加入"已覆盖知识领域"列表
- LLM 可根据已学内容推荐下一步学习方向

### 阶段 5（工具使用 + 代码执行）— 1 天（可选）

**目标**: 教练可以生成并执行代码（用户确认后）

#### S5.1: Code Sandbox

- LLM 生成的代码在沙箱中运行
- 结果回传给教练，教练据此提供反馈
- **红线**：代码执行必须用户显式确认（主权脉冲）

---

## 3. 关键设计决策

### 3.1 为什么 LLM 在 composer 之后、门禁之前

```
规则引擎选 action_type → LLM 填 payload → 8 道门禁 → 输出
```

教练策略（"今天该 probe 还是 scaffold"）由规则引擎 + TTM/SDT 决定，**不由 LLM 决定**。LLM 只负责填充教学内容。这确保了：

- 安全策略不会被 LLM 绕过
- TTM 阶段判断保持一致性
- 脉冲/远足等主权机制正常工作

### 3.2 回退策略

```
LLM 调用 → 成功 → payload 进入安全管线
         → 失败(超时/限流/异常) → 回退规则模板 → 安全管线
                                 + 记录 LLMError 到审计日志
```

用户永远能看到回复（不会因为 LLM 挂了而白屏），只是质量降级。

### 3.3 API Key 安全

```
环境变量 LLM_API_KEY=sk-xxx
  → src/coach/llm/config.py 读取
  → 传递给 LLMClient
  → 不写入任何文件、日志、数据库
```

### 3.4 提示词版本管理

提示词模板作为独立文件存储在 `config/prompts/` 中，与代码分离。这样：
- 提示词修改不需要改代码
- 后续可以加 A/B 测试不同提示词版本
- 每个版本可追溯

---

## 4. 测试策略

### 4.1 LLM 客户端测试

```
test_llm_client.py:
  - 成功调用返回合法 JSON
  - API 超时 → LLMError
  - API 返回非 JSON → LLMError
  - API 返回字段缺失 → LLMError
  - 环境变量未设置 → LLMConfigError
  - 重试机制（最多 2 次）
```

### 4.2 提示词测试

```
test_llm_prompts.py:
  - 每个 action_type 的提示词包含必要字段
  - 提示词不含敏感/越权指令
  - 系统提示词包含认知主权声明
  - 上下文注入正确（session_id 等）
```

### 4.3 集成测试

```
test_coach_agent_llm.py:
  - LLM enabled=true → agent 调用 LLM 客户端
  - LLM enabled=false → agent 使用规则模式
  - LLM 失败 + fallback=true → 规则模式
  - LLM 失败 + fallback=false → 抛出异常
  - LLM payload 经过门禁检查
  - LLM 输出不含 forbidden_phrases
  - TTM/SDT 配置影响 LLM prompt
```

### 4.4 回退测试

```
test_llm_fallback.py:
  - API 无响应 → 规则回退
  - 限流 (429) → 规则回退
  - 无效 JSON → 规则回退
  - 以上组合情况
```

---

## 5. 门禁与安全

### 5.1 LLM 不绕过任何已有安全机制

| 安全层 | 是否受影响 | 说明 |
|--------|-----------|------|
| 8 道 GateEngine | 不变 | LLM payload 仍然经过 gates |
| 语义安全三件套 | 不变 | Counterfactual + CrossTrack + Precedent |
| 主权脉冲 | 不变 | 高频建议仍然触发脉冲 |
| 远足权 | 不变 | /excursion 命令仍然有效 |
| 关系安全 | 不变 | 禁止短语过滤、顺从监测 |
| V18.8 双账本 | 不变 | No-Assist 独立计分 |
| 审计日志 | 增强 | 新增 LLM 调用记录 |

### 5.2 新增边界约束

- LLM 单次输出长度上限：`max_tokens: 2000`（可配）
- LLM 连续调用频率限制：与现有 rate limiter 一致

---

## 6. 启用顺序

推荐按以下步骤启用 LLM：

```
Step 1: llm.enabled = true         → 验证基础调用
Step 2: enable TTM + SDT           → LLM prompt 包含用户画像
     (ttm.enabled = true, sdt.enabled = true)
Step 3: 启用语义安全三件套          → LLM 输出受安全约束
Step 4: 启用主权脉冲                → 高频 LLM 建议触发脉冲
Step 5: 启用流式 WebSocket         → 实时推送（阶段 3）
Step 6: 启用 MAPE-K               → 外循环监控 LLM 行为（阶段 3 可选）
```

---

## 7. 文件变更清单

### 新增 (5 个源文件)

| 文件 | 职责 | 代码量 |
|------|------|--------|
| `src/coach/llm/__init__.py` | 包声明 | ~5 |
| `src/coach/llm/client.py` | LLM API 客户端 | ~200 |
| `src/coach/llm/prompts.py` | 提示词模板 | ~150 |
| `src/coach/llm/config.py` | 配置 + API Key 管理 | ~80 |
| `src/coach/llm/schemas.py` | 输出 schema + 校验 | ~80 |

### 修改 (4 个源文件)

| 文件 | 改动 | 代码量 |
|------|------|--------|
| `src/coach/agent.py` | act() 中新增 LLM 路径 | ~60 |
| `src/coach/composer.py` | 新增 LLM-aware 构建 | ~30 |
| `config/coach_defaults.yaml` | 新增 llm: 配置节 | ~15 |
| `api/routers/chat.py` | 阶段 3 流式支持 | ~40 |

### 删除

无（不修改已冻结模块）

---

## 8. 回退方案

如果 LLM 集成后出现问题，回退只需一步：

1. 在 `coach_defaults.yaml` 设置 `llm.enabled: false`
2. 重启 API 服务
3. 整个系统回到当前规则模式，**零影响**

---

## 9. 后续方向（Phase 10 之后）

| 方向 | 说明 | 前置 |
|------|------|------|
| 代码沙箱 | LLM 生成代码可安全执行 | Phase 10 完成 |
| A/B 提示词实验 | 对比不同 prompt 的教学效果 | Phase 10 完成 |
| 学习路径推荐 | LLM 根据 TTM 推荐下一步 | Phase 10 完成 |
| MRT 实验 | 随机对比 LLM 模式 vs 规则模式 | Phase 7 + Phase 10 |
