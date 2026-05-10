# S9.2 Web 前端全量审计报告

生成时间: 2026-05-04
范围: frontend/ (24 源文件, 4 测试文件)
构建: tsc 零错误, vite build 成功 (41 模块)
测试: 17/17 前端测试通过, 1128/1128 Python 全量回归通过

---

## 1. 成功标准验证

| # | 标准 | 状态 | 说明 |
|---|------|------|------|
| 1 | 前端项目可正常启动 (npm run dev) | ✅ | vite build 683ms |
| 2 | 色彩系统 6 主色 + 5 辅助色, Hex 码准确 | ✅ | theme.ts 精确匹配设计文档第 4.1 节 |
| 3 | TTM 6 态(含复发期) × UI 组件映射完整 | ✅ | stateMachine.ts 6 态齐全 |
| 4 | PulsePanel 非阻断滑动确认 + 毛玻璃 | ✅ | SlideToConfirm + backdrop-filter 实现 |
| 5 | ExcursionOverlay 全局暗调 + 光晕 | ⚠️ | CSS 变量已注入但未被组件消费 |
| 6 | useAdaptivePulse 计数 + 降级 | ✅ | sessionStorage 存储, MAX_BLOCKING=2 |
| 7 | ChatBubble 按 source_tag 渲染标签 | ⚠️ | 组件实现但 WS 消息未传递 sourceTag |
| 8 | 组件测试全部 pass | ✅ | 17/17 |

## 2. 设计偏差 (Design Deviations)

### D2 [MEDIUM] ExcursionOverlay CSS 变量未被消费

ExcursionOverlay 设置 `--color-bubble-user`, `--color-bubble-coach`, `--border-radius-bubble` 等 CSS 变量，但 `ChatBubble` 和 `ChatInput` 组件使用硬编码颜色值（`var(--color-soft-blue)`, `var(--color-lavender-gray)`），未引用这些变量。

**影响**: 进入探索模式后，对话气泡颜色不改变，需要手动刷新才能看到暗调效果。Excursion 的"对话气泡边界曲率改变"无法生效。

**文件**: `frontend/src/components/chat/ChatBubble.tsx:42` — 硬编码 `var(--color-lavender-gray)` 和 `var(--color-soft-blue)`，未使用 `var(--color-bubble-user)` 和 `var(--color-bubble-coach)`

### D3 [LOW] PulsePanel 内联 animation 不链接 CSS keyframe

PulsePanel 使用 `animation: 'slideUp 0.3s ease-out'` 作为内联样式。但这个 `slideUp` keyframe 定义在 `animations.css` 中，内联 style 属性无法跨文件引用外部 CSS 中的 @keyframes。

**影响**: 脉动面板的入场滑入动画效果不生效（silent failure — 组件正常渲染但无动画）。

**文件**: `frontend/src/components/chat/PulsePanel.tsx:55`

### D5 [LOW] HealthShield 三个状态共享相同 SVG path

```typescript
const SHIELD_PATHS: Record<string, string> = {
  pass: 'M12 2L3 7v5c0 5.55 ...',
  warn: 'M12 2L3 7v5c0 5.55 ...',   // 完全相同
  block: 'M12 2L3 7v5c0 5.55 ...',  // 完全相同
};
```

三种状态使用完全相同的 SVG path 字符串。视觉差异仅来自颜色变化。pass/warn/block 的图标本应有不同形状（如盾牌对勾/盾牌感叹号/盾牌叉号）以提供冗余语义。

**文件**: `frontend/src/components/shared/HealthShield.tsx:11-15`

### D6 [INFO] SlideToConfirm touchAction:none 影响页面滚动

滑动确认组件设置 `touchAction: 'none'` 禁用触摸滚动。在移动端浏览时，如果滑块位于视口内，用户上下滑动页面会意外触发滑块。

## 3. 隐藏 Bug (Hidden Bugs)

### X1 [HIGH] WebSocket 发送冗余 `__connect__` 消息

`createChatWebSocket()` 在 WebSocket 连接建立时发送 `__connect__` 消息:

```typescript
ws.onopen = () => {
  ws.send(JSON.stringify({ type: 'user_message', session_id: sessionId, content: '__connect__' }));
};
```

后端 `chat_websocket` 将此视为真实的 `user_message`，调用 `CoachBridge.chat("__connect__", sessionId)`——生成一次浪费的 LLM 调用。且响应会出现在消息列表中（phantom message）。

**影响**: 每次 WS 重连时触发一次无意义的 LLM API 调用，增加延迟和成本。

**文件**: `frontend/src/api/client.ts:95-97`

### X2 [HIGH] Excursion CSS 变量未消费（同 D2）

同上。ExcursionOverlay 设置的全局 CSS 变量与 ChatBubble 实际使用的颜色无关联。

**影响**: 探索模式的视觉隔离效果不完整。用户进入 Excursion 后气泡外观不变。

### X4 [MEDIUM] Stale Closure — useAdaptivePulse

`getBlockingMode` 和 `recordPulse` 使用 `useCallback` 依赖 `[sessionId, pulseData]`。当 `pulseData` 更新时生成新引用。若这些回调被传递给子组件或存储到 ref 中，会捕获过期的闭包值。

```typescript
const getBlockingMode = useCallback((): BlockingMode => {
  if (now - pulseData.ts >= PULSE_WINDOW_MS) { ... }  // pulseData 可能过期
}, [sessionId, pulseData]);
```

**影响**: 极端时序下（高频脉冲事件），降级判断可能使用过期计数。

**文件**: `frontend/src/hooks/useAdaptivePulse.ts:37-46`

### X5 [MEDIUM] 不安全类型断言 — App.tsx

```typescript
(res.payload as Record<string, string>)?.statement || ''
(res.domain_passport as Record<string, string>)?.source_tag as ...
```

两处 `as` 强制类型断言绕过了 TypeScript 的类型检查。如果后端响应中 `payload` 或 `domain_passport` 结构变化，前端将静默失败（返回空字符串或 undefined）。

**文件**: `frontend/src/App.tsx:101,103`

### X6/X7 [LOW] TTMStageCard / SDTEnergyRings 不安全类型断言

```typescript
data[stage as keyof TTMRadarData] as number
(data[ring.key as keyof SDTRingsData] as number) || 0
```

从 `unknown` 到 `number` 的类型断言无校验，值为 `null`/`undefined` 时静默变为 `0`。

**文件**: `frontend/src/components/dashboard/TTMStageCard.tsx:55`, `frontend/src/components/dashboard/SDTEnergyRings.tsx:78`

### X8 [MEDIUM] ChatBubble sourceTag 未从 WS 消息提取

`handleWSMessage` 处理 WebSocket 的 `coach_response` 时，未提取 `source_tag` 字段传给消息对象。ChatBubble 实现了 source_tag 标签渲染但该字段永远为空（从 WS 通道接收时）。

```typescript
// handleWSMessage — 缺少:
// sourceTag: msg.source_tag as ChatMessage['sourceTag'],
```

**文件**: `frontend/src/App.tsx:63` (缺失 sourceTag 传递)

## 4. 测试覆盖缺口

| 模块 | 文件 | 现有测试 | 缺口 |
|------|------|---------|------|
| ChatBubble | components/chat/ChatBubble.tsx | 0 | source_tag 渲染, user/coach 样式, 空内容 |
| ChatInput | components/chat/ChatInput.tsx | 0 | 6 种 inputMode placeholder, 发送行为, disabled |
| SlideToConfirm | components/shared/SlideToConfirm.tsx | 0 | 滑块交互, 确认回调, 重置行为 |
| HealthShield | components/shared/HealthShield.tsx | 0 | 3 状态渲染, 颜色映射, SVG 结构 |
| SDTEnergyRings | components/dashboard/SDTEnergyRings.tsx | 0 | 3 环渲染, 空数据, 极端值 |
| useCoachState | hooks/useCoachState.ts | 0 | setSession, addMessage, state 更新 |
| useWebSocket | hooks/useWebSocket.ts | 0 | 连接, 重连, 消息分发 |
| stateMachine | utils/stateMachine.ts | 0 | 6 态映射, null 回退 |
| colorAdapt | utils/colorAdapt.ts | 0 | 昼夜切换, CSS 变量写入 |
| theme | styles/theme.ts | 0 | Hex 码验证, 语义色映射 |
| client | api/client.ts | 0 | request 函数, error 处理, token 注入 |
| App | App.tsx | 0 | 会话创建, WS 集成, 脉冲流程 |

**总计**: 12 个模块零测试覆盖（除已有 17 个测试覆盖的 4 个模块外）。

## 5. 修复建议优先级

### P0 — 立即修复
1. **[X1] WebSocket `__connect__` 消息** — 删除 `__connect__` 消息发送，或改为轻量 ping
2. **[X2/D2] Excursion CSS 变量消费** — ChatBubble 改用 `var(--color-bubble-*)` 变量

### P1 — 尽快修复
3. **[X8] WS sourceTag 传递** — handleWSMessage 提取 source_tag 参数
4. **[X5] 不安全类型断言** — App.tsx 使用类型守卫或默认值替代 as 断言
5. **[D3] 内联 animation 引用** — PulsePanel 改用 className 引用 animation

### P2 — 后续优化
6. **[X4] Stale closure** — useAdaptivePulse 改用 ref 存储脉冲数据
7. **[D5] HealthShield 不同 SVG 路径** — 为 warn/block 设计不同图标
8. **[X6/X7] 不安全类型断言** — TTMStageCard/SDTEnergyRings 添加校验

### P3 — 测试覆盖
9. 补充 12 个零覆盖模块的测试（约 40 个新测试）
10. App.tsx 集成测试（完整用户流程）

---

## 6. 关键指标

| 指标 | 值 |
|------|-----|
| 源文件 | 24 |
| 测试文件 | 4 |
| 现有测试 | 17 (全部通过) |
| 构建产物 | 161.63 KB JS, 2.54 KB CSS |
| TypeScript 错误 | 0 |
| 设计偏差 | 4 |
| 隐藏 Bug | 6 |
| 零覆盖模块 | 12 |
| Python 全量回归 | 1128 通过 |

---

*本报告基于 meta_prompts/coach/92_test_s9_2.xml 执行生成*
