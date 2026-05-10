# Phase 13: 诊断-适应闭环激活 — 深度思考

## 现状：四个子系统代码就绪，全部 disabled

穷举测试（256 组合）结束后，系统处于一个奇怪的状态：

| 子系统 | 代码 | 测试 | config |
|:-------|:----:|:----:|:------:|
| DiagnosticEngine | 554 行 ✅ | 42/42 ✅ | enabled: **false** |
| TTM 阶段检测 | 已实现 ✅ | — | enabled: **false** |
| SDT 胜任感评估 | 已实现 ✅ | — | enabled: **false** |
| BKT 知识追踪 | 作为 Flow 的子模块 ✅ | — | 依赖 DiagnosticEngine |

```
症状：四个相互关联的子系统，各自独立完成，但没人把它们接通。
```

### 为什么走到这一步？

1. **Phase 0-8 的目标是"跑通骨架"** — 每个模块只需存在、不报错，优先级高于激活
2. **Phase 9-10 聚焦前端 + LLM** — 产品化优先于教学深度
3. **Phase 11 设计了诊断闭环** — 但执行时被 Phase 12 的"规则引擎 2.8→14.5"抢了优先级
4. **Phase 12 完成 FallbackEngine** — 现在规则引擎可用了，诊断闭环才有意义

### 激活后的系统架构

```
用户输入
  │
  ▼
TTM 阶段检测 ──────→ 输出: contemplation/preparation/action...
  │                     决定对话大方向（"做什么"）
  ▼
SDT 胜任感评估 ────→ 输出: autonomy/competence/relatedness 信号
  │                     决定教学风格（"怎么做"）
  ▼
composer 选 action_type
  │
  ├─→ LLM ON? ──→ LLM 生成教学内容
  │                   │
  └─→ LLM OFF? ──→ FallbackEngine 模板
                        │
                        ▼
                   DiagnosticEngine ──→ 每 5 轮出诊断题
                        │                  │
                        ▼                  ▼
                   BKT 掌握度更新 ───→ Flow 难度调节
                        │
                        ▼
                   cross-session persistence
```

### 关键问题：数据验证

穷举测试提供的决策依据：

| 模型 | ON | OFF | 差距 | 含义 |
|:-----|:--:|:---:|:----:|:-----|
| TTM | 15.3 | 16.0 | **-0.65** | TTM 刻意选 reflect/challenge，牺牲短分促长学 |
| SDT | 15.8 | 15.5 | +0.23 | SDT 有正向作用 |
| Flow | 15.7 | 15.7 | 0.00 | Flow 无诊断输入，等于空转 |

TTM 的分数下降需要解释：这是设计取舍，不是 bug。reflect/challenge action 输出内容更少但要求用户更多思考——短期评分低，长期效果好。

### 激活顺序（基于依赖关系）

```
S13.1: DiagnosticEngine + FallbackEngine 题库
   │ 依赖: DiagnosticEngine 代码(✅), FallbackEngine 题库(✅)
   │ 改动: ~30 行
   ▼
S13.2: TTM 阶段检测
   │ 依赖: DiagnosticEngine 的输出（TTM 需要知道用户水平）
   │ 改动: config 改 enabled:true
   ▼
S13.3: SDT 胜任感评估
   │ 依赖: DiagnosticEngine 的诊断信号（SDT 需要 competence 输入）
   │ 改动: config 改 enabled:true + 连接信号
   ▼
S13.4: 跨会话持久化 + 难度自适应
   │ 依赖: DiagnosticEngine 运作中
   │ 改动: ~50 行
   ▼
S13.V: 穷举验证
```

### 风险识别

1. **TTM 降分不可接受？** → 需要重新审视 TTM 的策略权重，或接受这是长期教学的必要代价
2. **DiagnosticEngine 打断对话流？** → 题目前加过渡语句，让出题看起来是自然的教学延伸
3. **跨会话持久化冲突？** → 文件锁问题（单用户系统可忽略）

### 成功标准

| 指标 | 当前 | 目标 |
|:-----|:----:|:----:|
| Diagnostic probe 相关性 | 泛泛通用题 | 与教学话题一致 |
| TTM 阶段检测准确率 | N/A | 80%+ 匹配用户阶段 |
| SDT 胜任感校准 | N/A | 与 BKT 掌握度正相关 |
| 掌握度跨会话保留 | 每次归零 | 重启后恢复 |
| 全量回归 | 1256 pass | 1256+ pass |
