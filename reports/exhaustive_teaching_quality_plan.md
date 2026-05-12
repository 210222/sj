# 穷尽教学质量测试 — 执行方案

**基线**: 1302 tests passed | **规格源**: 37 份元提示词, 139 条验收标准
**目标**: 按元提示词规格驱动的穷尽测试，聚焦教学质量

---

## 一、覆盖缺口分析

| 维度 | 规格数 | 现有测试覆盖 | 缺口 |
|------|--------|-------------|------|
| 全量回归 | 34 | ✅ 1302 tests | 0 |
| 字段存在性 | 2 | ✅ test_phase24 | 0 |
| Action-Type 差异化 | 13 | ⚠️ Phase 22 仅测 prompt | **需扩展** |
| 数据流完整链 | 26 | ⚠️ 分散在各 Phase | **需端到端** |
| 持久化 | 5 | ✅ Phase 20 tests | 0 |
| 边界/空值 | 12 | ⚠️ 部分覆盖 | **需系统化** |
| Disabled 零变化 | 4 | ✅ 隐式覆盖 | 0 |

## 二、执行方案

### 模块 A: Action-Type 8 路穷尽 (13 条标准, 预计 +30 tests)

针对 Phase 22 规格: 8 种 action_type 的 prompt、校验、行为必须可区分。

```
A.1 prompt 差异化 (8 tests — 每种 action_type 独立验证)
  - 每种含独有关键词 (已完成: test_phase22)
  - 新增: 每种不含其他 action_type 的关键词 (反向验证)
  - 新增: prompt 长度各不同 (结构差异可量化)

A.2 字段校验穷尽 (8 tests × 2 场景 = 16 tests)
  - 每种 action_type: 缺必填字段→validate_with_type=False
  - 每种 action_type: 全字段→validate_with_type=True
  - 已完成: probe/scaffold/challenge (test_phase22)
  - 新增: suggest/reflect/defer/pulse/excursion (5×2=10 tests)

A.3 compose 输出 action_type 覆盖 (8 tests)
  - 验证 8 种 action_type 均可被 compose() 选中
  - 通过 ttm_strategy.recommended_action_types 引导
  - 新增: 6 tests (suggest/reflect 已有覆盖)
```

### 模块 B: 数据流端到端 (26 条标准, 预计 +15 tests)

验证 mastery → TTM/SDT/Flow → composer → LLM 全链路。

```
B.1 mastery→TTM 注入 (3 tests)
  - diagnostic_engine enabled: mastery_values 非空传入 TTM.assess()
  - diagnostic_engine disabled: mastery_values=空, cognitive_indicators 仅含 confidence
  - 边界: mastery_summary.skills 为空 dict → mastery_values=[]

B.2 mastery→SDT 注入 (3 tests)
  - diagnostic_engine enabled: competence_signal 传入 sdt_data
  - diagnostic_engine disabled: sdt_data 不含 task_completion_rate
  - 边界: get_competence_signal() 返回 None → sdt_data 不变

B.3 mastery→Flow 注入 (3 tests)
  - diagnostic_engine enabled: skill_probs 使用 BKT mastery 值
  - diagnostic_engine disabled: skill_probs 使用 confidence
  - 边界: mastery_values 为空 → fallback 到 confidence

B.4 mastery→difficulty (3 tests)
  - any mastery < 0.3 → difficulty="easy"
  - all mastery > 0.7 → difficulty="hard"
  - 空 mastery → difficulty="medium" (default)

B.5 mastery→covered_topics (3 tests)
  - skills 非空 → _covered_topics 含 "skill(掌握度:XX%)"
  - skills 为空 → _covered_topics=None
  - memory_snippets 非空 → _memory_snippets 传入 build_coach_context
```

### 模块 C: 边界系统化 (12 条标准, 预计 +10 tests)

```
C.1 diagnostic_engine 全路径空安全 (4 tests)
  - diagnostic_engine=None → store 不调用 (已验证)
  - diagnostic_engine enabled 但 get_all_masteries()={} → 不崩溃
  - process_turn() 无 pending probe → 返回 None
  - should_and_generate() 超 max_probes → 返回 None

C.2 persistence 空安全 (3 tests)
  - get_profile() 无行 → 返回 {}
  - get_mastery_trend() 无数据 → 返回 []
  - get_skills_with_recency() skill_masteries={} → 返回 {}

C.3 LLM 降级路径 (3 tests)
  - LLMConfig.from_yaml(llm.enabled=false) → LLMClient 抛出 LLMError → 规则引擎保底
  - LLM output 校验失败 → llm_generated=False
  - LLM API 网络错误 → 不崩溃
```

### 模块 D: Disabled 零变化穷尽 (4 条标准, 预计 +5 tests)

```
D.1 全模块 disabled 基线 (1 test)
  - 所有 13 模块 enabled=false → act() 行为与 Phase 0 基线一致

D.2 单模块启用不污染 (4 tests)
  - 仅 ttm.enabled=true → sdt/flow 字段为 None
  - 仅 sdt.enabled=true → ttm/flow 字段为 None
  - 仅 flow.enabled=true → ttm/sdt 字段为 None
  - 仅 diagnostic_engine.enabled=true → 其他模型不受影响
```

## 三、执行统计

| 模块 | 新增测试 | 预计时间 | 优先级 |
|------|---------|---------|--------|
| A: Action-Type 穷尽 | ~30 | 8 min | P1 |
| B: 数据流端到端 | ~15 | 5 min | P0 |
| C: 边界系统化 | ~10 | 3 min | P1 |
| D: Disabled 零变化 | ~5 | 2 min | P1 |
| **总计** | **~60** | **~18 min** | |

## 四、执行顺序

```
1. D (Disabled 零变化) — 基线快, 先确保不会引入退化
2. B (数据流端到端) — P0, 核心教学质量链路
3. C (边界系统化) — 空安全防御
4. A (Action-Type 穷尽) — 体积最大, 最后跑
```

## 五、验收标准

- 全部 ~60 新测试通过
- 全量回归 1302 + 60 = ~1362 passed
- 每个测试文件可独立运行
- 不需要 DEEPSEEK_API_KEY (不调真实 LLM)
