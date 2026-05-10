# Phase 17 Design Thinking — 知情同意启用 TTM+SDT + A/B 验证

## 问题陈述

Phase 16 实现了能力唤醒——新用户首轮看到可用但未启用的模块列表。但唤醒只是信息展示，缺少三个关键环节：

1. **推荐分级** — 16 个模块全列出来，用户不知道该开哪个
2. **同意流程** — 没有"一键启用推荐"的交互机制
3. **选择持久化** — 每次新会话重复询问

Phase 17 补上最后一步：知情 → 同意 → 启用 → 持久化 → 验证。

## 设计决策

### 为什么推荐 TTM + SDT（而非其他组合）

S15 穷尽评测数据支撑：
- full_stack (TTM+SDT+Flow+Diag) = 19.7/32 vs llm_only = 18.1/32 (+8.8%)
- llm_ttm = 19.5/32（单开 TTM 也有 +7.7%）
- 但 Flow+Diag 需要 TTM+SDT 先稳定运行才能发挥作用
- TTM（定方向）→ SDT（调风格）→ Flow（精调难度）的层次依赖

### 为什么通过聊天消息流而非新 API

- 保持 Phase 16 的"对话式启用"范式一致性
- 不引入新的 API 路由，零后端基础设施变更
- 用户自然语言表达同意/拒绝，符合认知主权原则

### 为什么 consent_status 用三态而非布尔

- `never_asked`: 新用户，需要展示唤醒
- `consented`: 已同意，不再展示
- `declined`: 已拒绝，不再展示但保留重新询问的可能（未来需求）

## 架构影响

- 无新 API 路由
- 无新 LLM 调用
- 1 个新 DB 列 (consent_status)
- 2 个新 YAML 字段 (ttm/sdt.recommended)
- 前端 AwakeningPanel 从死代码变为活动组件
