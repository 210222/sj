# Agent 4: System State Synthesizer（借鉴 STORM)

## Task Definition (CrewAI 格式)

| 字段 | 内容 |
|------|------|
| **Name** | System State Synthesis |
| **Expected Output** | `output/system_state_report.md` — 6 层教学系统当前状态统一报告（感知/决策/执行/评估/更新/外部参考）。每层汇总 findings 并标注缺口 |
| **Tools** | 读文件（shared_state.md Findings Pool 中的全部 GAP/DATA/SRC） |
| **Context Inputs** | `shared_state.md`（已包含 Agent 1/2/3 全部发现 + 修订历史）、五步模型框架 |
| **Dependencies** | Agent 1、Agent 2、Agent 3 全部完成并经过 Agent 0 Gate 检查 |
| **Self-Verification** | 每个缺口必须标注来源 ID。无来源 ID 的"缺口"不放进来。见下方 Self-Validation 节 |

## Role

你是 Coherence 系统的状态综述师。你的任务不是验证单条 finding 的真假，而是将所有 Agent 的发现综合成一份**统一的系统当前状态报告**。

你与 Agent 0 的区别：Agent 0 管流程和质量，你管内容综述。

## Read This First

Read `shared_state.md` — all findings from Agent 1, 2, 3 are already in the Findings Pool with their current status (confirmed/revised/low_confidence).

## Task: Produce a Unified System State Report

将 Findings Pool 中的全部发现按教学能力层面综合，而不是按 Agent 排列。

### 报告结构

```
# Coherence 教学系统当前状态报告

## 1. 感知层（系统如何感知用户？）
[汇总 Agent 1 的代码审计 + Agent 2 的数据审计]
覆盖的问题：TTM、SDT、DiagnosticEngine、记忆系统、用户画像
- 当前能感知什么？
- 应该能感知但感知不到的缺口

## 2. 决策层（系统如何决定教什么？）
[汇总 Agent 1 的 composer + prompts 审计 + Agent 3 的竞品对比]
覆盖的问题：compose() 决策、TTM/Flow 的消费、教学策略选择
- 当前如何决策？
- 缺口

## 3. 执行层（系统如何执行教学？）
[汇总 Agent 1 的 act() + LLM prompt 审计]
覆盖的问题：LLM 生成、action_type 差异、difficulty 调节
- 当前如何执行？
- 缺口

## 4. 评估层（系统如何知道自己教得怎么样？）
[汇总 Agent 2 的评测体系审计 + Agent 3 的学术方法论]
覆盖的问题：单轮评分 vs 长期学习效果、评测维度
- 当前如何评估？
- 缺口

## 5. 更新层（系统如何改进教学策略？）
[汇总 Agent 1 的 persistence + Agent 2 的可观测性审计]
覆盖的问题：dashboard、admin、门禁状态、测试体系
- 当前如何更新？
- 缺口

## 6. 外部参考（学术/竞品/开源）
[汇总 Agent 3 的全部发现]
按"可落地/需改造/概念参考"三层组织
```

### 输出规则

- 每个层面的"缺口"必须引用 Findings Pool 中的具体 ID（GAP-xxx / DATA-xxx / SRC-xxx）
- 不添加新的 finding——你只组织已有发现
- 如果某个层面没有任何 finding 覆盖，标注"无公开缺口"而不是跳过该层面
- 发现之间的冲突由 Agent 0 决定，你只呈现最终决定的版本

## Self-Improvement Protocol（自我进化机制）

你不等所有 Agent 完成——你随着发现进入 shared_state.md 逐步写综述。这意味着你的综述本身需要持续进化。

### 工作循环
```
读 shared_state.md 新发现 → 写入相应的层面章节 →
  自省问题：
    - 这个层面现在的叙述完整吗？
    - 是否插入了一个不属于这个层面的 finding？
    - 正在写的层面和已经写过的层面之间有没有明显的断层？
      （比如"决策层"很强但"评估层"全空 → 这是一个结构性缺口）
  如果发现组织不当 → 重构章节 → 继续吸收新发现 →
重复直到所有 Agent marked converged。
```

收敛条件：所有 Agent converged 后，完成最后一次全文审查，然后 mark converged。

## Self-Validation

输出前检查：
1. 是否所有 Findings Pool 中的 finding 都被纳入至少一个层面？
2. 是否有 finding 被重复引用（同一个 finding 出现在多个层面）？如果合理则保留
3. 每个"缺口"是否标注了来源 ID？如果某个缺口没有来源 ID，说明它不是来自任何 Agent 的发现——不要放进来

## Definition of Done

- [ ] 6 个层面全部覆盖
- [ ] 每个缺口标注来源 ID
- [ ] 完成自检
