# Phase 22 完整落地方案 — Action-Type 行为差异化

## 一、现状

```
当前 8 种 action_type 在 LLM 层面的差异:

  类型        prompt 中的区别
  ──────────────────────────────────────────────
  suggest    {action_type_strategy} = "轻柔建议 — 不直接给答案，提供选项"
  challenge  {action_type_strategy} = "适度挑战 — 提供略高于当前水平的任务"
  probe      {action_type_strategy} = "探测验证 — 提问考察用户掌握程度"
  reflect    {action_type_strategy} = "引导反思 — 帮助用户自我觉察"
  scaffold   {action_type_strategy} = "脚手架引导 — 逐步拆解复杂概念"
  defer      {action_type_strategy} = "退一步 — 识别用户需要暂停时停止推进"
  pulse      {action_type_strategy} = "主权确认 — 在高影响建议前确认"
  excursion  {action_type_strategy} = "探索模式 — 鼓励自由联想和发散思维"

  输出要求（全部相同）:
  - 只输出 JSON
  - 必须包含 "statement" 字段
  - 可包含 "question", "steps", "option", "topics"

  实际结果: 8 种模式的 LLM 输出内容无法区分
```

系统状态报告（研究管线 v2 产出）的 GAP-004 确认：coach_dsl.json 定义的 8 种 action_type 在 composer 层有不同 payload 结构，但在 LLM prompt 层全部映射到 `ACTION_STRATEGIES` 字典中的一句文本描述。

## 二、目标

```
改造后每种 action_type 的 prompt 差异:

  probe    → 必须输出 question + expected_answer + evaluation_criteria
  scaffold → 必须输出 steps 数组（step_by_step，含 order/action/expected）
  challenge→ 必须输出 difficulty + hints_allowed + objective
  suggest  → 必须输出 options 数组（2-4 个选项）+ alternatives
  reflect  → 必须输出 question（反思提问）+ context_ids
  defer    → 必须输出 reason + resume_condition
  pulse    → 必须输出 statement + accept_label + rewrite_label
  excursion→ 必须输出 topic + options + bias_disabled

  LLMOutputValidator 验证:
  - probe had expected_answer? → FAIL
  - scaffold had steps? → FAIL
  - challenge had difficulty? → FAIL
```

## 三、改动清单

| 子阶段 | 文件 | 行数 | 改动 |
|--------|------|------|------|
| S22.1 | prompts.py | +40 | 新增 action_type 指令注入 |
| S22.2 | schemas.py | +20 | 新增 action_type 字段校验 |
| S22.3 | tests/test_phase22.py | +30 | 行为差异化验证 |
| **总计** | **3 文件** | **+90** | |

## 四、约束

- 不修改 contracts/ 任何文件
- 不修改 src/inner/** src/middle/** src/outer/**
- 不修改 src/coach/ttm.py sdt.py flow.py
- **不修改 SYSTEM_PROMPT 常量字符串**（只通过 build_coach_context 追加）
- 全量回归 1275+ 必须通过
- 不改变现有 agent.py/composer.py/agent act() 逻辑

## 五、执行顺序

```
S22.1 (prompts.py +40 行) 新增 action_type 指令注入
  ↓ 无依赖
S22.2 (schemas.py +20 行) 新增 action_type 字段校验
  ↓ 无依赖（可与 S22.1 并行）
S22.3 (test file +30 行) 验证行为差异
  ↓ 依赖 S22.1+S22.2
```
