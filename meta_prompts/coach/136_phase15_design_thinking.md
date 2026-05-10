# Phase 15 Design Thinking — 个性化闭环固化

## 1. 问题定义

当前 Coherence 已经具备可运行的教练/教学主链，但 S15 的真实问题已经不是“还缺哪些模块”，而是这五条链路没有工程化闭环：

1. 个性化只部分依赖 prompt 中的引用指令，定义偏浅，容易被“机械引用用户原话”刷分。
2. 记忆注入链路不够可靠，memory/history/topic 可能静默失效，导致个性化没有稳定输入来源。
3. 诊断、自适应、难度调节分散在 DiagnosticEngine / Flow / persistence / Agent 中，没有单一契约和 reason code。
4. HTTP、WebSocket、frontend、dashboard 之间的证据字段不一致，系统内部知道的东西，用户和验收层未必看得见。
5. 评测与验收缺少固定工件，S14 vs S15 的改进无法被稳定比较、复查和交接。

## 2. 目标体验

Phase 15 结束后，系统不只要“看起来更会教”，还要达到下面五个结果：

- **用户可感知**：回复能持续引用用户已学内容、当前卡点、最近诊断结果，而不是每轮像失忆。
- **系统可解释**：每轮教学动作都能说明为什么是这个难度、为什么给这个问题、为什么引用这些历史。
- **前端可见**：聊天区、侧边栏、dashboard 能看到核心教学证据，而不是只在后端日志里存在。
- **报告可验收**：评测结果不只有平均分，还有失败案例索引、维度变化、阈值判定。
- **交接可复用**：下一位 Claude 或其他执行模型可以基于 Final audit 继续推进，而不需要重新猜测阶段目标。

## 3. 字段契约图

Phase 15 关注的字段应从 `coach -> API -> WS -> frontend -> reports` 一路贯穿。

### 3.1 个性化证据字段
- `personalization_evidence`
- `teaching_focus`
- `learner_state_summary`
- `memory_status`
- `memory_sources`

### 3.2 诊断与难度字段
- `diagnostic_result`
- `diagnostic_probe`
- `difficulty_contract`
- `difficulty_reason_codes`
- `difficulty_axes`

### 3.3 可观测链路字段
- HTTP chat response
- WebSocket `coach_response`
- dashboard 聚合字段
- frontend message metadata
- acceptance reports 中的 failure tags / reason tags

目标不是给用户暴露全部内部状态，而是保证：
1. 内部有的关键教学证据，外部至少能看到摘要。
2. 每个评分维度都能追溯到具体字段，而不是只看自然语言成品。

## 4. 依赖顺序

### S15.1 Personalization Contract 先行
必须先定义“个性化到底是什么”，否则后续记忆、难度、评测都会围绕不同标准各自优化。

### S15.2 Memory Reliability 第二
如果系统不能稳定记住用户，就没有可靠的 personalization input，后续难度与评测都会建立在噪声上。

### S15.3 Diagnostic + Difficulty Contract 第三
等输入稳定后，再把诊断、自适应、难度统合成一个单一契约，避免多个模块互相覆盖。

### S15.4 Observability Parity 第四
只有后端到前端的证据链统一了，A/B 验收和前端观测才具备真实依据。

### S15.5 Evaluation Harness 第五
评测必须在字段和观测稳定后做，否则得到的是不可复核的脆弱分数。

### S15.6 Final Audit 最后
统一收口，生成可以交接、可以复盘、可以签收的最终结论。

## 5. 验收标准

### Phase 15 总体通过标准
- 存在一份完整的 personalization contract。
- memory 注入具备 hit / miss / error 三态审计。
- 难度决策具备统一 contract 与 reason codes。
- HTTP / WebSocket / frontend 可观测字段对齐完成并产出 parity diff。
- 形成固定的 S14 vs S15 A/B 验收工件。
- Final audit 能逐条引用证据并给出 GO / CONDITIONAL-GO / NO-GO。

### Phase 15 总体失败条件
- 仍然依赖“主观感觉更好”作为主要验收依据。
- 仍然存在 WS 缺字段、dashboard 占位、memory 静默失败。
- A/B 报告没有失败案例索引，只有平均分。

## 6. 风险清单

1. **字段漂移风险**
   - 新增证据字段可能与既有 schema 命名不一致。
   - 必须统一 HTTP / WS / frontend 类型命名。

2. **评测刷分风险**
   - personalization 可能被“简单重复用户原话”投机式提升。
   - 必须增加反例、失败标签和 evidence-based 口径。

3. **记忆污染风险**
   - 错误记忆进入 prompt 会让教学越来越偏。
   - 必须区分 hit / miss / error，并记录来源。

4. **难度冲突风险**
   - DiagnosticEngine / Flow / persistence 可能给出不同信号。
   - 必须明确优先级和 override 规则。

5. **观测失真风险**
   - 后端字段存在但前端不展示，或 dashboard 继续用占位值，会让验收误判能力状态。

## 7. 最终建议

Phase 15 不应再以“继续叠功能”为目标，而应以“把已有教学能力做成可证明地更好”为目标。

这意味着：
- 先做契约定义，
- 再修信号来源，
- 再统一决策，
- 再贯穿观测，
- 最后再做评测与签收。

这是目前唯一稳妥的推进顺序。 
