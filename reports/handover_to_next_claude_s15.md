# Coherence 交接报告 — 给下一个 Claude

## 1. 项目现在处在什么位置

当前项目处在 **S15 前置期 / LLM-Only 个性化闭环阶段**。

已确认的现状：
- 系统默认 LLM 开启，`fallback_to_rules` 已关闭。
- `llm.enabled=true` 是默认路径，当前不再考虑无 LLM 的业务分支。
- 256/256 穷举质量测试已完成，0 failed。
- 当前总体质量基线：`overall_avg_quality = 15.6/24`。
- 个性化仍是主要短板：`personalization = 1.81/4`。
- 关键注入链已存在：
  - `src/coach/agent.py`：difficulty / context_window 注入
  - `src/coach/llm/prompts.py`：difficulty 写入 system prompt
  - `src/coach/llm/config.py`：LLM 默认开启

## 2. 当前阶段的真实目标

下一阶段不是继续加功能，而是把“LLM 默认开启”变成“个性化可测、可见、可验收”的闭环：
- 提升 personalization 指标
- 让上下文引用、难度自适配、追问跟随卡点都可判分
- 用 A/B 验证 S14 vs S15 是否真有提升

## 3. 目前已完成的关键事实

- 穷举测试完成，结果稳定：`256/256 pass`
- LLM 主链已启用
- `fallback_to_rules` 已关闭
- `src/coach/agent.py` 中 LLM 失败会直接报错，不再回退到规则链
- `src/coach/llm/config.py` 默认值已改为 LLM 强依赖模式

## 4. 当前待做事项

优先级从高到低：
1. 重写个性化评测指标
2. 强化 LLM system prompt 约束
3. 将单一 difficulty 升级为三轴控制
4. 做 S14 vs S15 A/B 验收
5. 在前端补齐可观测展示

## 5. 我的职责

我负责的是：
- 读懂当前代码与约束
- 找到真正影响指标的改动点
- 在不破坏已有门禁的前提下修改代码
- 跑测试、读结果、修回归
- 输出给用户可验收的结论，而不是空泛建议

## 6. 我的能力边界

我能做：
- 代码阅读、定位、修改、验证
- 生成或重写提示词
- 设计评测和验收流程
- 组织测试与回归
- 生成交接、报告、门禁说明

我不能依赖的前提：
- 不能假设无 LLM 分支存在
- 不能假设 `DEEPSEEK_API_KEY` 一定可用
- 不能把“质量提升”只写成主观描述，必须落到指标

## 7. 给下一个 Claude 的直接建议

接手后先做三件事：
1. 读取 `reports/exhaustive_all_configs_report.json`
2. 读取 `src/coach/agent.py`、`src/coach/llm/prompts.py`、`src/coach/llm/config.py`
3. 立刻进入 S15 的指标重构，不要再扩功能

## 8. 一句话总结

项目已经从“功能可用”进入“质量提升验证”阶段；下一步的核心不是再接线，而是把个性化做成能被量化证明的增长。
