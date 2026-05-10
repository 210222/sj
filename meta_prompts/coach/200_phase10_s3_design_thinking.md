# Phase 10 S3 — WebSocket 流式推送 元提示词设计思考

> 编制日期: 2026-05-05
> 对齐源: Phase 10 S2 已完成（三层安全护栏已 GO）, Phase 10 落地方案 §3
> 前置条件: Phase 10 S1+S2 已 GO, 1162 tests pass, `src/coach/llm/` 包完整

---

## 0. 为什么这份思考文档

S3（WebSocket 流式推送）看起来只是"把 LLM 响应改成流式输出"，但有两个核心问题必须在写元提示词之前想清楚：

1. **安全护栏在流式场景下如何工作？** S2 的三层校验（对齐→过滤→校验）都假设完整 payload 可用。流式场景下 token 逐个到达，校验逻辑不能逐 token 执行，否则会误杀半句话。

2. **流式改造的边界在哪里？** 改 client、改 WS 路由、还是改 CoachAgent？哪些不能动？

---

## 1. 核心架构决策

### 1.1 流式安全校验策略 — 分段到达、终点校验

流式场景下安全校验不能逐 token 做，原因：

```
逐 token 校验:
  token 1: "我"    → 无害
  token 2: "比你"  → 无害
  token 3: "更了"  → 无害
  token 4: "解你"  → 有害! → 回退? 但前面已经发出去了
```

**决策**: 双阶段策略

```
Phase 1 — 流式推送（无校验）:
  LLM token → WS chunk → 前端渲染
  （零校验，低延迟）

Phase 2 — 终点校验（完整 payload 到达后）:
  完整 payload → S2 三层校验（align → filter → validate）
  → 校验通过: 前端已渲染完毕，静默结束
  → 校验失败: 推送 safety_override 消息覆盖已渲染内容
```

理由：
- **流式期间不做校验**：校验需要完整字符串匹配（forbidden_phrases 是子串匹配），半句话无法判断
- **终点必校验**：最终 payload 必须通过 S2 全套三层校验
- **校验失败可回滚**：前端收到 `safety_override` 后替换已渲染内容
- **管理用户预期**：流式内容立即展示，但最终解释权归安全护栏

### 1.2 LLMClient.generate_stream() — 为什么是 AsyncGenerator 而不是 Callback

流式 API 有两种常见的暴露方式：

| 方式 | 优点 | 缺点 |
|------|------|------|
| AsyncGenerator[yield str] | 调用方控制消费节奏 | 需要 async 上下文 |
| Callback(chunk: str) → None | 同步友好 | 控制流反转，错误处理复杂 |

**决策**: AsyncGenerator。理由：
- WS 路由已经是 async 上下文（FastAPI WebSocket endpoint 是 async）
- CoachBridge.chat() 在 WS 路由中已经通过 `run_in_executor` 处理同步阻塞
- Callback 模式在错误处理、资源清理上更复杂

### 1.3 流式是否经过 CoachBridge

当前架构：

```
WS route → CoachBridge.chat() [线程池] → CoachAgent.act()
```

流式改造后：

```
WS route → CoachBridge.chat_stream() [async] → LLMClient.generate_stream() [async gen]
```

**决策**: CoachBridge 新增 `chat_stream()` 静态方法，不走线程池（因为 generate_stream 本身就是异步的），但 CoachAgent.act() 中的规则逻辑（intent 解析、TTM/SDT）仍走同步路径。

两条路径的汇合点：
1. 规则路径走完全部意图分析 + DSL 构建（同步）
2. LLM 生成走流式（异步，通过 LLMClient.generate_stream）
3. LLM 流式结束后拼接完整 payload → S2 校验 → 如果失败发 safety_override

### 1.4 WSMessageType 扩展

当前 WSMessageType 枚举已有：
- user_message, coach_response, pulse_event, pulse_decision, pulse_timeout, excursion_event, error

S3 新增：
- `coach_chunk` — 流式内容块，包含部分 statement 文本
- `coach_stream_end` — 流式结束信号，包含完整 payload + safety 结果

### 1.5 流式与现有 WS 路由的关系

**决策**: 不重写现有 WS 路由，而是在其中新增流式分支。

```
chat_websocket():
  if streaming_enabled and llm_enabled:
    # 流式路径（S3 新增）
    CoachBridge.chat_stream() → yield chunks → ws.send_json
  else:
    # 现有非流式路径
    CoachBridge.chat() → ws.send_json(coach_response)
```

这样保证了：
- llm.enabled: false 时完全走现有路径
- llm.enabled: true 但 streaming: false 时走现有路径
- 只有两者都开启时才走流式路径

---

## 2. S3 与已有机制的关系

### 2.1 S3 不替代任何现有机制

| 组件 | S3 做什么 | 关系 |
|------|----------|------|
| LLMClient.generate() | 保留 | S3.1 新增 generate_stream()，不改 generate() |
| WS 路由 /chat/ws | 增强 | 新增流式分支，保留现有非流式路径 |
| WSMessageType 枚举 | 扩展 | 新增 coach_chunk + coach_stream_end 值 |
| S2 三层安全护栏 | 依赖 | 流式终点必须调用 S2 校验 |
| CoachBridge.chat() | 保留 | 新增 chat_stream()，不修改 chat() |
| CoachAgent.act() | 不改 | 流式 bypass act() 的同步 LLM 路径 |

### 2.2 S3 的边界

**S3 不改**:
- `src/coach/llm/client.py` 的 `generate()` 方法
- `src/coach/agent.py` 任何逻辑
- `src/coach/dsl.py` DSL 构建器
- 现有 WS 非流式路径
- `CoachBridge.chat()` 签名和返回值

**S3 新增/修改**:
- `src/coach/llm/client.py` 新增 `generate_stream()` async generator
- `src/coach/llm/schemas.py` 新增流式响应结构 / 终点校验集成
- `api/routers/chat.py` WS 路由新增流式分支
- `api/models/websocket.py` WSMessageType 新增枚举值
- `api/services/coach_bridge.py` 新增 `chat_stream()` 静态方法
- `config/coach_defaults.yaml` 确认 streaming 配置项（已有）

---

## 3. 边界情况处理

### 3.1 LLM 流式生成过程中中断

```
用户断开 WS → WebSocketDisconnect 异常
→ 需要 cancel async generator → LLM API 连接断开
→ 已发出的 chunk 前端已渲染 → 不补偿
```

**处理**: FastAPI 的 WebSocketDisconnect 异常中关闭 async generator，不推送 coach_stream_end。

### 3.2 流式内容超长

```
max_tokens: 2000 已经限制了 LLM 输出长度
流式情况下: chunk 逐个到达，累计超 2000 tokens 时 LLM API 返回 finish_reason="length"
→ 正常终止流，推送 coach_stream_end
```

### 3.3 流式终点校验失败

```
完整 payload 组装完成 → S2 校验 → 发现 forbidden 短语
→ 推送 safety_override 消息（非 coach_chunk）
→ 前端替换已渲染内容为安全提示
```

### 3.4 SSE 解析出错

DeepSeek/OpenAI 流式 API 返回 SSE 格式：
```
data: {"choices":[{"delta":{"content":"你好"},"index":0}]}\n\n
data: [DONE]\n\n
```

解析出错时：
- 非 JSON 行跳过
- `[DONE]` 标记流结束
- parse 错误 → 关闭 async generator → 后续回退到非流式响应

### 3.5 并发流式请求

WS 路由按 session 串行处理消息。一个 session 同时只能有一个流在运行（现有 WS while 循环天然串行）。不额外加锁。

---

## 4. 测试策略

### 4.1 流式客户端测试

```
test_llm_stream.py:
  - generate_stream 返回 AsyncGenerator
  - yield 的 chunk 是递增的文本片段
  - 最终拼接结果与同步 generate() 一致
  - SSE 格式解析（data: {...}\n\n）
  - [DONE] 标记解析
  - 网络错误 → LLMError
  - 空响应 → 空 generator
```

### 4.2 WS 流式路由测试

```
test_ws_stream.py:
  - streaming 开启 → 收到 coach_chunk + coach_stream_end
  - streaming 关闭 → 只收到 coach_response（现有行为）
  - llm disabled → 只收到 coach_response（现有行为）
  - 流式终点校验失败 → 收到 safety_override
  - WS 断开 → 不崩溃
```

### 4.3 流式 vs 非流式兼容性测试

- 确保 streaming: false 时行为完全不变
- 确保 llm.enabled: false 时行为完全不变
- 确保 WSMessageType.COACH_CHUNK 不影响现有前端

---

## 5. S3 在整个 Phase 10 中的位置

```
Phase 10:
  S1: LLM 客户端 + 基础集成      ← GO ✅
  S2: 输出校验 + 安全对齐        ← GO ✅
  S3: WebSocket 流式推送          ← 本次
  S4: 记忆增强 + 多轮上下文       ← 后续
  S5: 代码沙箱                   ← 后续
```

S3 依赖于 S2 的安全护栏：终点校验必须使用 S2 的 LLMDSLAligner + LLMSafetyFilter。S4（记忆增强）需要在 S3 的流式上下文基础上扩展。

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 流式期间安全盲区 | 低 | 中 | 终点必校验，失败发 safety_override |
| SSE 解析兼容性（不同 provider） | 中 | 低 | 统一 data: {...} 格式，provider 差异隔离在 _parse_sse_line() |
| 流式 + WS 双 async 资源竞争 | 低 | 低 | WS 天然串行，不引入并发 |
| CoachBridge 新增 chat_stream 复杂度 | 低 | 低 | chat_stream 作为独立静态方法，不修改 chat() |
| 流式 chunk 顺序错乱 | 低 | 低 | SSE 天然保序，AsyncGenerator yield 有序 |
