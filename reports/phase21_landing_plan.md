# Phase 21 完整落地方案 — 教学策略闭环

## 一、现状

| 数据通道 | REST 路径 (agent.py) | WS 路径 (coach_bridge.py) |
|---------|---------------------|--------------------------|
| ttm_stage | ✅ 已传 | ✅ 已传 |
| sdt_profile | ✅ 已传 | ✅ 已传 |
| difficulty | ✅ 动态计算 | ❌ 不传 |
| history | ✅ memory.recall() | ❌ 不传 |
| memory_snippets | ❌ None | ❌ 不传 |
| covered_topics | ❌ None | ❌ 不传 |
| mastery 数据 | ❌ 不进 prompt | ❌ 不进 prompt |

**核心矛盾**: LLM 收不到用户的掌握度和动机数据——即使 BKT 算出 python_loop=0.45，LLM 也看不到。

## 二、改动清单

| 子阶段 | 文件 | 行数 | 改动 |
|--------|------|------|------|
| S21.1 | agent.py | +15 | 填充 memory_snippets 和 covered_topics |
| | prompts.py | +5 | 确认格式化兼容 |
| S21.2 | prompts.py | +25 | _build_behavior_signals() 新增 SDT 指令 |
| S21.3 | coach_bridge.py | +20 | WS path 同步 REST 参数 |
| **总计** | **3 文件** | **+65** | |

## 三、执行顺序

```
S21.1 (+15行) agent.py 填充 memory/covered_topics
  ↓ 无数据依赖
S21.2 (+25行) prompts.py SDT 语气增强
  ↓ 无数据依赖（可以和 S21.1 并行）
S21.3 (+20行) coach_bridge.py WS 同步
  ↓ 依赖 S21.1 验证通过
```

## 四、风险

| 风险 | 缓解 |
|------|------|
| extract_memory_snippets 失败 | try/except 回退 None |
| diagnostic_engine disabled 时 get_all_masteries 不存在 | hasattr 检查 + 三元表达式 |
| WS 路径的 agent 实例没有 diagnostic_engine | 同 try/except 保护 |
| _build_behavior_signals 返回值格式变化破坏下游 | 保持 str 格式不变，只追加行 |

## 五、验收

| 门禁 | 条件 |
|------|------|
| G1 | pytest tests/ -q 全绿 |
| G2 | diagnostic_engine enabled 时 covered_topics 含技能列表 |
| G3 | SDT 低自主性时 _build_behavior_signals 含步骤指令 |
| G4 | WS 路径 build_coach_context 收到至少 6 个非 None 参数 |
