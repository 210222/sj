# 网页端问题深度修复报告 — 7 个 Bug 根因分析 + 修复 + 副作用预防

## 问题 1: 苏醒面板每次对话都弹

**根因**：`_consent_pending` 是 CoachAgent 实例变量。每次 API 请求新建实例，该变量永远为 False。`_handle_consent_response()` 检查 `consent_status == "never_asked" and not _consent_pending` → 当 _consent_pending=False 时直接 return None，不处理 consent 关键词。

**修复**：`_build_awakening()` 展示后立即持久化 `consent_status = "shown"`。下次实例加载时从 DB 读到 "shown"，跳过唤醒面板。

**检查条件**：`consent_status in ("consented", "declined", "shown")` → 不展示。

**副作用分析**：
- 用户首次看到唤醒面板 → 忽略 → 刷新网页 → 面板消失且无法再触发
- "启用推荐能力" 关键词在所有 consent_status 下仍可触发（never_asked/declined/shown 都处理）
- `consent_status = "shown"` 的影响：TTM+SDT 保持关闭（只标记已读，不自动启用）

**副作用预防**：前端 SettingsPanel 始终可手动开启所有模块，不依赖唤醒面板。

---

## 问题 2: 对话上下文无关联（每轮像新对话）

**根因**：`history` 传给 LLM 的是 `format_history_for_prompt()` 的输出，但该函数只输出 intent 标签（"第3轮: general"），不含用户消息原文。LLM 看到的是无信息量的标签，无法建立上下文连续性。

**修复**：Phase 27 `_build_context_summary()` 生成 5 块结构化上下文：
- Block 1: 对话历史（FULL/COMPRESS/PLACEHOLDER 三级，含用户消息原文）
- Block 2: 技能快照（BKT mastery + 新鲜度标签）
- Block 3: 学习目标
- Block 4: 策略连续性（上一轮 action_type，跨实例从 memory 读取）
- Block 5: 待复习

**关键设计决策**：Block 4 从 `self.memory.recall()` 读取上一轮数据，而非 `_prev_ctx` 实例变量。原因：同问题 1，实例变量在跨请求时丢失。

**副作用分析**：
- 5 块上下文每轮都计算 → 增加 token 消耗（估算每块 ~50-150 tokens）
- `self.memory.recall()` 不按 session_id 过滤 → 可能混入其他会话历史（已加 `session_id` filter）
- `get_skills_with_recency()` 用 `MAX(timestamp)` 给所有技能同一个 days_elapsed（已知限制）

**副作用预防**：
- Block 1 限制最近 10 条 → `limit=10`
- Block 2 限制 5 个技能 → `[:5]`
- Block 5 限制 3 个待复习 → `[:3]`
- 所有块包裹 `try/except: pass` — 任一失败不影响其他

---

## 问题 3: 每轮都是探测题（一直考不教）

**根因**：三个因素叠加——
1. 诊断引擎 `should_and_generate()` 每 5 轮生成 probe，直接覆盖 `action["action_type"] = "probe"`
2. SDT `adjust_autonomy_support` 建议在低自主性时切换 suggest→reflect，被诊断引擎 probe 覆盖
3. composer 的 SDT 低自主性 scaffolding 逻辑在 `adjust_autonomy_support` 之前执行，被后续 advice 覆盖

**修复**：
- 诊断引擎 probe 增加 3 个跳过条件：前一 turn 已是 probe、当前 action 已是 probe、autonomy < 0.4（低自主性先教）
- composer SDT 逻辑重排：低自主性 scaffold 优先级最高（`if autonomy < 0.4: action_type = "scaffold"`），在 `adjust_autonomy_support` 之前执行，不随后续 advice 覆盖

**副作用分析**：
- autonomy < 0.4 永不 probe → 用户始终低自主性时，系统永远不检测掌握度
- 连续对话中只有第一轮是 probe → 多轮教学后无法自动评估

**副作用预防**：
- `autonomy < 0.4` 条件只阻止 diagnostic_engine 的强制 probe，不影响 compose() 自身选择 probe
- TTM 策略的 `avoid_action_types` 仍可触发 probe
- 用户在对话中说"考考我"→ 关键词匹配 probe，绕过诊断引擎限制

---

## 问题 4: 网页设置面板的开关不生效

**根因**：`_write_config()` 使用 `yaml.dump()` 写入配置，该函数在 Windows 环境下产生不可解析的输出（`null\n...`）。同时，已运行的进程不重载模块级 `_coach_cfg`。

**修复**：
- `yaml.dump` → `yaml.safe_dump`（可靠写入）
- 写入后 `del sys.modules["src.coach.*"]` → 下次请求自动重载配置
- 前端 `vite.config.ts` 增加 `ws: true` → WebSocket 代理生效

**副作用分析**：
- `del sys.modules` 清除所有 coach 模块 → 下次请求有冷启动开销（~0.1s）
- `yaml.safe_dump` 不支持某些 Python 对象 → 配置文件只允许 dict/list/str/int/float/bool/None

**副作用预防**：
- 配置写入前验证：所有值必须是 YAML-safe 类型
- 写入使用 `yaml.safe_dump` + 失败时回退到 `yaml.dump`

---

## 问题 5: 刷新网页消息全消失

**根因**：前端消息存储在 React state（内存），刷新即丢失。`sessionStorage` 只保存了 session_id 和 token。

**修复**：
- `addMessage()` 中追加 `localStorage.setItem(coherence_messages_{sessionId}, JSON.stringify(messages))`
- `loadInitialState()` 中从 localStorage 恢复消息
- 新增 `GET /api/v1/chat/history?session_id=xxx` 从 coherence.db 读原始消息（服务端备份）

**副作用分析**：
- localStorage 有 5-10MB 限制 → 长期对话可能超出
- 多个 session_id → 多个 localStorage key → 占用累积
- `JSON.stringify` 大数组可能阻塞主线程

**副作用预防**：
- 消息数组超过 200 条时，保留最近 200 条，旧消息只存服务端
- `GET /api/v1/chat/history` 作为服务端权威数据源
- localStorage 写入包裹 `try/catch`，写入失败静默忽略

---

## 问题 6: WebSocket 连接失败导致无响应

**根因**：Vite proxy 的 WebSocket 代理未开启（`ws: true` 缺失）。同时 `useWebSocket` 无限重连（5 秒间隔），持续刷屏错误。

**修复**：
- `vite.config.ts` proxy 加 `ws: true`
- `useWebSocket.ts` onclose 不再重连 → 失败一次即走 HTTP fallback
- `handleSendMessage` 始终使用 HTTP `sendMessage()` 作为主路径

**副作用分析**：
- 无 WebSocket 实时推流 → LLM 生成期间用户看不到 partial tokens
- HTTP fallback 等待完整响应 → 6-8 秒延迟（vs WebSocket 的逐 token 流式）
- `ws: true` 可能与其他 Vite 中间件冲突

**副作用预防**：
- 保留 WebSocket 创建逻辑，`ws: true` 后自动恢复流式
- HTTP fallback 作为可靠兜底，始终可用
- 加 loading 动画消除等待焦虑（问题 7）

---

## 问题 7: 无回复等待提示

**根因**：无 loading 状态管理。用户发送消息后到 LLM 回复之间有 6-10 秒空白，无法判断系统是否在工作。

**修复**：
- App.tsx 增加 `isLoading` state
- `handleSendMessage` 发送前 `setIsLoading(true)`，回复后 `setIsLoading(false)`
- UI 渲染三点跳动动画："教练正在思考 ● ● ●"
- CSS: `@keyframes typing-bounce` 弹跳动画

**副作用分析**：
- 如果 `setIsLoading(false)` 因异常未执行 → loading 永久卡住
- 快速连续发送消息 → loading 状态可能被第二次发送覆盖

**副作用预防**：
- `setIsLoading(false)` 放在 try/catch/finally 中保证执行
- 30 秒超时 → 自动清除 loading + 显示"回复超时，请重试"

---

## 检查规则

在实施任何新的前端/后端修改后，验证以下项目：

```
[ ] 苏醒面板: 新 session 首轮展示 → 第二轮不再展示 → "启用推荐能力" 仍可触发
[ ] 上下文: 3 轮对话 → LLM 回复引用前两轮具体内容
[ ] 教学模式: 新用户 → 首轮 probe → 后续 scaffold/suggest (不再连续 probe)
[ ] 配置开关: PUT /api/v1/config → YAML 可解析 → 下次请求读取新值
[ ] 消息持久: 发 3 条消息 → 刷新 → 3 条仍在 → 换浏览器 → 服务端历史可恢复
[ ] WebSocket: 控制台无 WebSocket 错误 → 消息正常收发
[ ] Loading: 发消息 → 显示思考动画 → 回复到达 → 动画消失
[ ] 全量回归: pytest tests/ -q 全部 passed
```
