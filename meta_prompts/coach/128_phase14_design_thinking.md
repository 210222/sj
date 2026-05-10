# Phase 14: 诊断-适应闭环闭合 — 深度思考

## 现状：诊断有了，适应没做

Phase 13 激活了 DiagnosticEngine + TTM + SDT，256 组合穷举验证通过。

但穷举数据暴露了一个结构性矛盾：

```
诊断数据流：
  DiagnosticEngine → BKT mastery scores → 存入内存 ✓
                                            │
                                            ▼
                                         没人消费 ✗

适应数据流：
  Composer 选 action_type → LLM/Fallback 生成内容
    ↑                            ↑
    │                            │
  不看 BKT 掌握度              不看 student 水平
  (TTM/SDT 决定方向)            (固定模板/通用 prompt)
```

**症状：**

| 指标 | 值 | 根因 |
|------|------|------|
| Personalization | 1.81/4 | Composer 不引用前轮用户发言 |
| Structure (LLM OFF) | 1.2/4 | FallbackEngine 模板不分级 |
| LLM OFF avg | 14.5/24 | 所有学生按同一难度教 |
| 最低组合 | 12.0/24 | TTM+F+P+E 类组合（模型打架） |

## 核心洞察：这是一个"三缺一"问题

Phase 11 设计了「诊断 → 适应」闭环，Phase 12 做了 FallbackEngine（规则引擎兜底），Phase 13 激活了诊断端。

```
Phase 11:  诊断 ──→ 适应    (设计)
Phase 12:          适应     (规则引擎实现)
Phase 13:  诊断             (激活)
Phase 14:  诊断 ──→ 适应    (闭合!)
```

缺少的连接线就是 Phase 14 要做的事。

## 技术方案：两条注入线

### 注入线 A — 难度自适应（"教多难"）

```
Agent act():
  ┌─ diagnostic_engine.get_mastery(current_skill)
  │     mastery < 0.3 → difficulty = "easy"
  │     mastery 0.3-0.7 → difficulty = "medium"
  │     mastery > 0.7 → difficulty = "hard"
  └─→ 传入 composer.generate(..., difficulty=difficulty)
         │
         ▼
  Composer (LLM ON):
    prompt 中注入 "难度: easy/medium/hard"
    → LLM 自动调整解释深度

  Composer (LLM OFF):
    FallbackEngine 按难度选模板
    → _TEMPLATES 按 easy/medium/hard 分级
```

**关键设计决策**：难度由 Agent 决定，Composer 只消费。Agent 能看到全景（BKT + TTM + SDT），Composer 只负责生成。职责分离。

### 注入线 B — 上下文引用（"教谁"）

```
Agent act():
  ┌─ 维护 _context_window: list[str]  # 最近 2-3 轮用户发言
  └─→ 传入 composer.generate(..., context_window=context_window)
         │
         ▼
  Composer (LLM ON):
    prompt 中注入 "用户刚才说: {...}"
    → LLM 回复时先确认用户说法再展开

  Composer (LLM OFF):
    FallbackEngine 模板 {prev_user_said} 占位符
    → 不是新功能，Phase 12 已有，只是没传参
```

**关键设计决策**：Context window 只在 Agent 层维护（环形 buffer），Composer 只接收字符串列表。不引入新数据结构。

### 注入线 C — 话题连贯（"教什么"）

```
Agent act():
  ┌─ 每轮结束: _current_topic = 当前话题
  │  下次 should_and_generate():
  │    低掌握技能 → 自动成为 next_topic
  └─→ 话题切换时生成过渡语
```

**关键设计决策**：Topic 追踪不新建模块，只在 Agent 加两个字段 + 一个过渡函数。

## 为什么三条线必须同阶段做

1. **难度自适应** 是核心闭环（诊断→适应），是 Phase 14 存在的理由
2. **上下文引用** 直接解决 Personalization 1.81/4 这个最大扣分项
3. **话题连贯** 让前两条的效果在对话流中持续累积

三条线互不依赖，可以并行实现。它们的共同点是：**Agent 层收集信息 → Composer 层消费信息**。

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 难度注入后 LLM 回复变短（误以为"easy"=少写） | 中 | 中 | Prompt 写清楚 "easy≠简短，用更简单的语言和更多比喻" |
| Context window 过长超 token 限制 | 低 | 高 | 只传 2-3 轮，每轮截断到 100 字 |
| BKT mastery 不准导致难度误判 | 中 | 中 | 只在 mastery 明确高/低时切换，模糊区间保持 medium |
| 话题切换生硬 | 低 | 低 | 用"刚才我们讲了 X，接下来看看 Y"模板过渡 |

## 预期效果

| 指标 | Phase 13 | Phase 14 预期 | 提升来源 |
|------|----------|---------------|----------|
| Personalization | 1.81/4 | 2.8+/4 | 上下文引用 |
| LLM OFF avg | 14.5/24 | 15.5+/24 | 难度分级 + 模板改进 |
| LLM ON avg | 16.8/24 | 17.5+/24 | 难度自适应 + context |
| Structure (LLM OFF) | 1.2/4 | 2.0+/4 | 难度分级模板 |
| 最低组合 | 12.0/24 | 13.0+/24 | 难度自适应减少极端低分 |

## Phase 14 完成标准

1. Composer prompt 接收并消费 difficulty 参数
2. Agent 根据 BKT mastery 自动决定难度
3. Context window 传递到 Composer → LLM 回复引用前文
4. Agent 维护 current_topic，低掌握技能自动成为下轮话题
5. 穷举重测 256 组合全部 PASS，关键指标达到预期值
