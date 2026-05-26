# Phase 62 — 图文教学能力：详细执行计划

## 1. 触发策略（精确插入位置与文本）

### _STABLE_SYSTEM_PREFIX 插入位置

`src/coach/llm/prompts.py`，在"一对一辅导协议"第 6 条"察觉情绪并调整"之后（约第 57 行），插入：

```
图形触发规则（最高优先级，覆盖所有 action_type）:

请根据教学内容自动判断是否输出 diagram 字段：

1. 自动触发（主动使用图形，不等待用户要求）:
   - 流程/步骤类解说 → diagram: {"type":"mermaid","content":"flowchart TD..."}
   - 概念关系/知识体系 → diagram: {"type":"mermaid","content":"graph/mindmap..."}
   - 数据结构(树/链表/继承) → diagram: {"type":"mermaid","content":"graph/classDiagram..."}
   - 函数图像题/几何题 → diagram: {"type":"desmos","content":{"expressions":[...]}}
   - 代码示例 → diagram: {"type":"prism","content":"...","language":"python"}
   - 数学公式/标注 → 在 statement 中用 $...$ 包裹 LaTeX（KaTeX 自动渲染），不通过 diagram 字段

2. 用户要求触发（强制使用图形）:
   - 用户说"画个图""看不懂""太抽象了""举个例子看看""图示一下"→ 必须输出 diagram

3. 不使用图形的场景:
   - 简单问答、情绪支持、简短确认、纯概念讨论且不超过 2 句话
```

### _ACTION_TYPE_INSTRUCTIONS 追加文本

在 scaffold/challenge/suggest/reflect/probe 五种 action_type 的 JSON 字段要求中，各追加一行：

```
- "diagram": 可选字段。如果本轮内容涉及流程/关系/函数/代码/数据结构，必须输出此字段。
  格式: {"type":"mermaid|desmos|prism","content":"...","language":"(仅prism需要)"}
  如果你觉得本轮不需要图形，可以省略此字段。
```

## 2. 前端降级方案规范

### DiagramRenderer 分发器伪代码

```tsx
export function DiagramRenderer({ diagram }: { diagram?: { type: string; content: any } }) {
  if (!diagram) return null;
  try {
    switch (diagram.type) {
      case 'mermaid': return <MermaidRenderer content={diagram.content} />;
      case 'desmos': return <DesmosRenderer content={diagram.content} />;
      case 'prism':  return <PrismRenderer content={diagram.content} language={diagram.language} />;
      default:       return <FallbackBlock text={JSON.stringify(diagram.content)} />;
    }
  } catch (e) {
    return <FallbackBlock text={typeof diagram.content === 'string' ? diagram.content : JSON.stringify(diagram.content)} />;
  }
}
```

### 各渲染器的降级行为

| 渲染器 | 正常渲染 | 加载失败时 |
|--------|---------|----------|
| MermaidRenderer | Mermaid.js → SVG | 显示原始 Mermaid 文本（灰底等宽字体） |
| DesmosRenderer | Desmos API → 交互画布 | 显示表达式文本 + "Desmos 加载失败" |
| PrismRenderer | Prism.js → 代码高亮 | 显示原始代码（灰底等宽字体，无高亮） |
| KaTeX (inline) | KaTeX auto-render → 公式 | 显示原始 LaTeX 文本 |

### ChatBubble 集成位置

`ChatBubble.tsx` 中，在 `<div>{message.content}</div>` 之后、LLM 标签之前：

```tsx
{message.diagram && (
  <div style={{ marginTop: 8 }}>
    <DiagramRenderer diagram={message.diagram} />
  </div>
)}
```

## 3. 数据流验证

```
教练 LLM 输出 JSON
  → CoachAgent.act() 返回
    → ChatResponse.payload.diagram = {...}
      → ChatBubble 检测 payload.diagram
        → DiagramRenderer 按 type 分发渲染
```

KaTeX 略有不同——不在 diagram 字段，而是 statement/question 文本中的 `$...$`：
```
statement: "sin(x) 的周期是 $T = 2\pi$"
  → ChatBubble 渲染 statement 时
    → KaTeX auto-render 检测 $...$ 并替换为公式
```
