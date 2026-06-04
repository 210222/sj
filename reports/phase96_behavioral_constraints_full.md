# Phase 96: Prompt 行为约束强化 — 完整落地方案（含每阶段 Agent Prompt）

**日期**: 2026-06-04
**代码基线**: `f2c8e28`（Phase 94-95 已完成）
**总预计耗时**: 25 分钟（含全量回归）

---

## 阶段依赖图

```
S96.0 前置审计 (3min)
  │
  ├──► S96.1 通用规则追加 (2min)
  ├──► S96.2 行为约束函数 (5min)
  ├──► S96.3 policy_layer 改造 (5min)
  ├──► S96.4 build_coach_context 传参 (2min)
  └──► S96.5 agent.py 传参 (2min)
         │
         ▼
      S96.6 回归验证 (10min)
         │
         ▼
      S96.7 约束逻辑单元测试 (2min)
         │
         ▼
      S96.8 验收签收 (3min)
```

---

## S96.0 — 前置审计

### Agent Prompt

```
审计任务: Phase 96 S96.0 — 前置审计

请依次读取以下函数的当前精确内容，报告每个函数的起止行号和关键特征。
这些信息将用于后续 Edit 工具的精确 old_string 匹配。

---

READ 1: _render_terminal_tutoring_checklist

文件: D:\Claudedaoy\coherence\src\coach\llm\prompts.py
定位: 约 lines 419-432

报告:
  - 函数起始行号
  - return 语句的行号（在这个位置之后插入新规则）
  - 当前函数中有多少条规则（以 "lines.append(" 计数）
  - 函数末尾 5 行的精确文本（用于 old_string 构造）

---

READ 2: _render_policy_layer

文件: D:\Claudedaoy\coherence\src\coach\llm\prompts.py
定位: 约 lines 350-393

报告:
  - 函数签名（精确的参数字符串）
  - 函数体中 rendered = ... 的位置
  - return 语句的行号（在这个位置之前插入约束块生成逻辑）
  - 函数末尾 5 行的精确文本

---

READ 3: build_coach_context

文件: D:\Claudedaoy\coherence\src\coach\llm\prompts.py
定位: 约 lines 232-347

报告:
  - 函数签名（精确的参数字符串）
  - 调用 _render_policy_layer( 的位置和完整的参数传递方式
  - 调用点的精确文本（3-5 行）

---

READ 4: _build_llm_context_bundle

文件: D:\Claudedaoy\coherence\src\coach\agent.py
定位: 约 lines 292-382

报告:
  - 调用 build_coach_context( 的位置和完整的参数传递方式
  - 是否有 flow_channel 相关的变量可用（搜索 "flow" 关键字在函数附近）
  - 是否有 mastery 变量可用（搜索 "mastery" 关键字在函数附近）
  - 调用点的精确文本（5-10 行）

---

输出格式:

对于每个 READ，输出:
```
[READ N] 函数名
  起始行: Lxxx, 结束行: Lyyy
  old_string 候选 (精确文本):
  <<<截取的文本>>>
```
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| terminal_tutoring 定位 | return 行号确认，末尾 5 行精确截取 |
| policy_layer 定位 | 函数签名确认，return 前 5 行截取 |
| build_coach_context 定位 | _render_policy_layer 调用点确认 |
| agent.py 定位 | build_coach_context 调用点 + flow/mastery 变量可用性确认 |

---

## S96.1 — 通用规则追加 (terminal_tutoring)

### Agent Prompt

```
修改任务: Phase 96 S96.1 — terminal_tutoring 追加 3 条通用规则

STEP 1: 用 Edit 工具修改 _render_terminal_tutoring_checklist 函数

定位: 找到函数中 return 语句之前的位置。在最后一个 lines.append(...) 之后、return 之前插入。

old_string: 从 S96.0 READ 1 获取的最后 2-3 个 lines.append + return 语句

new_string: 相同的最后 2-3 个 lines.append，然后追加以下内容，然后 return:

    lines.append("")
    lines.append("【互动比例】本轮你的回应是否超过了 3 句话？如果是 → 违规。压缩到 2-3 句核心内容 + 1 个开放型追问。一个知识点只讲一个核心点，不要试图一次讲完所有相关内容。")
    lines.append("【开放提问】本轮你是否用了'对不对/懂了吗/明白吗/会了吗/可以吗'？如果是 → 违规。必须替换为开放型提问（'你觉得呢/用你自己的话说说看/你怎么理解/试试看会怎样'）。")
    lines.append("【避免独白】检查最近两轮: 你是否连续两轮没有向学生提问？如果是 → 违规。每轮必须以至少一个开放型问题结尾，让学生说话。")

STEP 2: 验证

替换后用 Read 确认:
  - 3 条新规则全部出现
  - 原有 11 条规则未丢失
  - return 语句未被覆盖

STEP 3: 导入验证

python -c "from src.coach.llm.prompts import _render_terminal_tutoring_checklist; r = _render_terminal_tutoring_checklist(); assert '互动比例' in r; assert '开放提问' in r; assert '避免独白' in r; print('OK: 3 new rules present')"
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| 3 条新规则 | "互动比例"/"开放提问"/"避免独白" 全部出现 |
| 旧规则完整 | 原有 11 条规则计数不变 |
| 导入正常 | `_render_terminal_tutoring_checklist()` 正常返回 |

---

## S96.2 — 行为约束函数

### Agent Prompt

```
修改任务: Phase 96 S96.2 — 新增 _render_behavioral_constraints 函数

STEP 1: 定位插入点

在 prompts.py 中，找到 _render_policy_layer 函数定义的位置（约 line 350）。
新函数插入在 _render_policy_layer 之前。

STEP 2: 用 Edit 工具插入

old_string: _render_policy_layer 函数的 def 行（精确文本）

new_string: 以下函数 + 一个空行 + _render_policy_layer 的 def 行（原样）


def _render_behavioral_constraints(
    *,
    stage: str,
    autonomy: float,
    competence: float,
    relatedness: float,
    flow_channel: str = "",
    mastery: float | None = None,
) -> str:
    """根据当前信号生成教学行为约束（MUST/MUST NOT 指令）."""
    rules: list[tuple[int, str]] = []

    # Priority 1: Flow (most urgent)
    if flow_channel in ("anxiety", "near_anxiety"):
        rules.append((1, "学生可能焦虑 → 降一级难度。先做示范再让学生尝试。禁止: 追问/时间压力/连续挑战。"))
    elif flow_channel == "near_boredom":
        rules.append((1, "学生可能无聊 → 换一个角度或增加难度。禁止: 重复同类型练习。"))

    # Priority 2: Mastery
    if mastery is not None:
        if mastery < 0.3:
            rules.append((2, "学生是新手 → 用生活类比解释每个概念。禁止: 用术语解释术语/挑战题/连续多个新概念。"))
        elif mastery > 0.7:
            rules.append((2, "学生已熟练 → 给开放性问题和多解法题目。禁止: 重复基础概念解释/封闭型提问。"))

    # Priority 3: TTM Stage
    ttm_map = {
        "precontemplation": (3, "学生尚未决定学习 → 只探索感受和动机。禁止: 教学/练习/推荐行动。"),
        "contemplation": (3, "学生在犹豫 → 每次先肯定学生的思考。给一个低门槛尝试入口。禁止: 催促决定/长篇教学。"),
        "action": (3, "学生主动在学 → 每轮给练习机会。先练后讲。禁止: 连续两轮无互动/长篇独白。"),
        "maintenance": (3, "学生已掌握基础 → 引入变化防止回退。禁止: 重复已学内容/降低难度。"),
        "relapse": (3, "学生遭遇挫折 → 无评判接纳。给最短重启路径。禁止: 分析失败原因/追加压力。"),
    }
    if stage in ttm_map:
        rules.append(ttm_map[stage])

    # Priority 4: SDT
    if autonomy < 0.4:
        rules.append((4, "学生自主性低 → 提供 2-3 个选项让学生选。禁止: 替学生做学习决策/单一指令。"))
    if competence < 0.4:
        rules.append((4, "学生胜任感低 → 本轮必须指出至少一个学生做得好的具体点。禁止: 直接纠错而不先肯定。"))
    if relatedness < 0.4:
        rules.append((4, "学生关联感低 → 本轮必须关联学生之前提到过的兴趣或经历。"))

    if not rules:
        return ""

    rules.sort(key=lambda x: x[0])
    selected = rules[:5]

    lines = ["教学行为约束（本轮必须遵守）:"]
    for _, rule in selected:
        lines.append(f"  - {rule}")
    return "\n".join(lines)


STEP 3: 验证

python -c "from src.coach.llm.prompts import _render_behavioral_constraints; print('Import OK')"
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| 函数可导入 | `from ... import _render_behavioral_constraints` 成功 |
| 插入位置正确 | 在 _render_policy_layer 之前 |
| 不破坏已有导入 | 整个 prompts.py 模块可正常导入 |

---

## S96.3 — policy_layer 改造

### Agent Prompt

```
修改任务: Phase 96 S96.3 — _render_policy_layer 接收新参数并注入行为约束

STEP 1: 修改函数签名

在 _render_policy_layer 的参数列表末尾新增两个参数:
  flow_channel: str = "",
  mastery: float | None = None,

old_string: 函数签名行（从 S96.0 READ 2 获取）

new_string: 相同的签名行，但在末尾括号之前追加:
  , *, flow_channel: str = "", mastery: float | None = None

(注意: 函数已有 * 分隔符，如果已有 flow_channel 和 mastery 参数则不需要再加)

STEP 2: 在函数体的 return 语句之前插入约束块生成逻辑

定位: return rendered 之前

old_string: return 语句及之前 1-2 行

new_string:

    # 生成教学行为约束
    constraints = _render_behavioral_constraints(
        stage=stage,
        autonomy=autonomy,
        competence=competence,
        relatedness=relatedness,
        flow_channel=flow_channel,
        mastery=mastery,
    )
    if constraints:
        rendered += "\n\n" + constraints
    return rendered

(注意: 保持与原有 return 语句相同的变量名，可能是 'rendered' 或 'policy' 或其他)

STEP 3: 验证

python -c "from src.coach.llm.prompts import _render_policy_layer; print('Import OK')"
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| 函数签名更新 | flow_channel 和 mastery 参数已添加 |
| 约束块插入 | constraint 生成逻辑在 return 之前 |
| 不破坏已有逻辑 | 原有 policy_layer 渲染逻辑不变 |
| 导入正常 | 函数可正常导入 |

---

## S96.4 — build_coach_context 传参

### Agent Prompt

```
修改任务: Phase 96 S96.4 — build_coach_context 接收并传递新参数

STEP 1: 在 build_coach_context 函数签名末尾新增参数

找到 def build_coach_context( 行，在参数列表末尾追加:
  flow_channel: str = "",
  mastery: float | None = None,

STEP 2: 在调用 _render_policy_layer 时传递新参数

找到调用 _render_policy_layer( 的位置（通常在函数体中间）
在已有参数末尾追加:
  flow_channel=flow_channel,
  mastery=mastery,

注意: 确认调用格式是关键字参数还是位置参数。如果是位置参数，需要改为关键字参数或精确对齐位置。

STEP 3: 验证

python -c "
from src.coach.llm.prompts import build_coach_context
import inspect
sig = inspect.signature(build_coach_context)
assert 'flow_channel' in sig.parameters, 'flow_channel missing'
assert 'mastery' in sig.parameters, 'mastery missing'
print('Signature OK')
"
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| build_coach_context 签名 | flow_channel + mastery 参数存在 |
| _render_policy_layer 调用 | 两个新参数已传递 |
| 导入正常 | 函数可正常调用 |

---

## S96.5 — agent.py 传参

### Agent Prompt

```
修改任务: Phase 96 S96.5 — _build_llm_context_bundle 传递 flow_channel + mastery

STEP 1: 了解当前 flow_channel 的来源

在 agent.py 中搜索 "_flow_channel" 和 "flow_channel" 变量的赋值位置。
报告 flow_channel 在 _build_llm_context_bundle 调用上下文中是否可用。
如果不可直接用，找到最接近的可访问属性或变量。

STEP 2: 了解当前 mastery 的来源

在 _build_llm_context_bundle 函数中搜索 "mastery" 变量。
确认 mastery 变量已经存在（Phase 89 引入的）。
报告 mastery 变量的赋值行号。

STEP 3: 修改 build_coach_context 调用

定位调用点（约 line 379），在 **ctx 字典中新增:
  'flow_channel': <flow_channel 的实际来源>,
  'mastery': mastery,

注意:
- flow_channel 可能来自 self._flow_result 或 self._flow_channel 或 computed_result
- 如果不可用，使用空字符串兜底: getattr(self, '_flow_channel', '')
- mastery 应已在函数中可用（Phase 89 _get_current_mastery 的返回值）

STEP 4: 验证

python -c "from src.coach.agent import CoachAgent; print('Import OK')"
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| flow_channel 来源识别 | 找到可用变量或属性 |
| mastery 来源确认 | 确认变量已存在于函数中 |
| 调用参数追加 | build_coach_context 收到两个新参数 |
| CoachAgent 可导入 | 导入不报错 |

---

## S96.6 — 回归验证

### Agent Prompt

```
验证任务: Phase 96 S96.6 — 全量回归

依次执行。任何一步失败 → 立即停止并报告。

TEST 1: prompts.py 导入完整性

python -c "
from src.coach.llm.prompts import (
    _STABLE_SYSTEM_PREFIX, _render_policy_layer,
    _render_terminal_tutoring_checklist, _render_behavioral_constraints,
    _build_behavior_signals, build_coach_context
)
print('All imports OK')
"

TEST 2: agent.py 导入完整性

python -c "
from src.coach.agent import CoachAgent
print('CoachAgent import OK')
"

TEST 3: 全量回归

python -m pytest tests/ -q -k "not user_flow"

预期: 1501 passed, 0 failed

TEST 4: 快速功能验证 — 确认约束进入 prompt

python -c "
from src.coach.llm.prompts import build_coach_context
# 调用一次确认不崩溃
result = build_coach_context(
    intent='general', action_type='suggest',
    ttm_stage='action', sdt_profile={'autonomy': 0.5, 'competence': 0.5, 'relatedness': 0.5},
    user_message='test', history='', memory_snippets=[], covered_topics='',
    difficulty='medium', flow_channel='flow', mastery=0.5
)
# 正常信号 → 不应有约束块
sp = result['system_prompt']
assert '互动比例' in sp, 'Missing universal rule: 互动比例'
assert '开放提问' in sp, 'Missing universal rule: 开放提问'
assert '避免独白' in sp, 'Missing universal rule: 避免独白'
print('Universal rules present')

# 焦虑信号 → 应有约束块
result2 = build_coach_context(
    intent='general', action_type='suggest',
    ttm_stage='action', sdt_profile={'autonomy': 0.3, 'competence': 0.3, 'relatedness': 0.3},
    user_message='test', history='', memory_snippets=[], covered_topics='',
    difficulty='easy', flow_channel='near_anxiety', mastery=0.2
)
sp2 = result2['system_prompt']
assert '教学行为约束' in sp2, 'Missing behavioral constraints header'
assert '焦虑' in sp2, 'Missing anxiety constraint'
print('Signal-aware constraints present')
print('ALL OK')
"
```

### 判定标准

| 测试 | PASS 条件 |
|------|----------|
| TEST 1 | 5 个函数全部可导入 |
| TEST 2 | CoachAgent 可导入 |
| TEST 3 | 1501 passed, 0 failed |
| TEST 4 | 通用规则在有 prompt 中，信号感知规则在异常信号时出现 |

---

## S96.7 — 约束逻辑单元测试

### Agent Prompt

```
验证任务: Phase 96 S96.7 — _render_behavioral_constraints 单元测试

python -c "
from src.coach.llm.prompts import _render_behavioral_constraints

# 测试 1: 新手 + 焦虑 → 应输出多条约束
r = _render_behavioral_constraints(
    stage='action', autonomy=0.5, competence=0.3, relatedness=0.6,
    flow_channel='near_anxiety', mastery=0.2)
assert '焦虑' in r, f'Test1 fail - missing anxiety: {r}'
assert '新手' in r, f'Test1 fail - missing novice: {r}'
assert '胜任感低' in r, f'Test1 fail - missing competence: {r}'
lines = r.splitlines()
assert len(lines) <= 7, f'Test1 fail - too many lines: {len(lines)} (max 5 rules + title + empty)'
print(f'Test1 PASS: {len(lines)-2} rules for novice+anxiety')

# 测试 2: 熟练 + 维持 → mastery + TTM
r = _render_behavioral_constraints(
    stage='maintenance', autonomy=0.8, competence=0.8, relatedness=0.7,
    flow_channel='flow', mastery=0.8)
assert '熟练' in r, f'Test2 fail: {r}'
assert '维持' in r or 'maintenance' in r.lower(), f'Test2 fail - missing maintenance: {r}'
print('Test2 PASS: expert+maintenance')

# 测试 3: 正常信号 → 空字符串（不产生噪音）
r = _render_behavioral_constraints(
    stage='action', autonomy=0.5, competence=0.5, relatedness=0.5,
    flow_channel='flow', mastery=0.5)
assert r == '', f'Test3 fail - expected empty for normal signals, got: {r}'
print('Test3 PASS: normal signals → empty')

# 测试 4: 全部异常 → 不超过 5 条
r = _render_behavioral_constraints(
    stage='precontemplation', autonomy=0.2, competence=0.2, relatedness=0.2,
    flow_channel='anxiety', mastery=0.1)
lines = [l for l in r.splitlines() if l.strip() and not l.startswith('教学行为约束')]
assert len(lines) <= 5, f'Test4 fail - {len(lines)} rules > 5 max'
print(f'Test4 PASS: all abnormal → {len(lines)} rules (capped at 5)')

# 测试 5: 关联感低
r = _render_behavioral_constraints(
    stage='action', autonomy=0.5, competence=0.5, relatedness=0.3,
    flow_channel='flow', mastery=0.5)
assert '关联感低' in r, f'Test5 fail: {r}'
print('Test5 PASS: low relatedness detected')

# 测试 6: 无聊
r = _render_behavioral_constraints(
    stage='action', autonomy=0.6, competence=0.6, relatedness=0.6,
    flow_channel='near_boredom', mastery=0.6)
assert '无聊' in r, f'Test6 fail: {r}'
print('Test6 PASS: near_boredom detected')

# 测试 7: 沉思阶段
r = _render_behavioral_constraints(
    stage='contemplation', autonomy=0.5, competence=0.5, relatedness=0.5,
    flow_channel='flow', mastery=0.5)
assert '犹豫' in r, f'Test7 fail: {r}'
print('Test7 PASS: contemplation stage detected')

print()
print('=== ALL 7 TESTS PASSED ===')
"
```

### 判定标准

| 测试 | PASS 条件 |
|------|----------|
| Test 1 | 焦虑 + 新手 + 胜任感低 三条全部出现，不超过 5 条 |
| Test 2 | 熟练 + 维持阶段约束出现 |
| Test 3 | 正常信号 → 空字符串 |
| Test 4 | 全部异常 → 上限 5 条 |
| Test 5 | 关联感低 → 约束出现 |
| Test 6 | 无聊 → 约束出现 |
| Test 7 | 沉思阶段 → 约束出现 |

---

## S96.8 — 验收签收

### Agent Prompt

```
验收任务: Phase 96 S96.8 — 验收签收

创建文件: D:\Claudedaoy\coherence\reports\phase96_completion.md

内容必须包含以下五个部分:

---

第一部分: 改动清单

| 文件 | 改动 | 位置 |
|------|------|------|
| src/coach/llm/prompts.py | terminal_tutoring 追加 3 条通用规则 | _render_terminal_tutoring_checklist() |
| src/coach/llm/prompts.py | 新增 _render_behavioral_constraints() | _render_policy_layer 之前 |
| src/coach/llm/prompts.py | _render_policy_layer 加参数 + 约束注入 | 函数签名 + return 前 |
| src/coach/llm/prompts.py | build_coach_context 加参数 + 传递 | 函数签名 + 调用点 |
| src/coach/agent.py | _build_llm_context_bundle 传递新参数 | build_coach_context 调用点 |

---

第二部分: 逐项比对验收表

| 方案承诺 | 状态 | 证据 |
|---------|------|------|
| terminal_tutoring 追加 3 条通用规则 | ✅/❌ | 导入验证通过 |
| _render_behavioral_constraints 四级优先级正确 | ✅/❌ | S96.7 全部 7 项测试通过 |
| _render_policy_layer 接收并传递新参数 | ✅/❌ | 函数签名更新 |
| build_coach_context 传递 flow_channel + mastery | ✅/❌ | 函数签名更新 |
| agent.py 传递 flow_channel + mastery | ✅/❌ | 调用参数更新 |
| 正常信号不产生约束 | ✅/❌ | Test 3: 空字符串 |
| 异常信号最多 5 条约束 | ✅/❌ | Test 4: 上限保护 |
| 全量回归 1501/0/X | ✅/❌ | |
| prompts.py 原有逻辑未破坏 | ✅/❌ | |
| agent.py 仅传参，核心逻辑不变 | ✅/❌ | |

---

第三部分: 约束规则矩阵

| 优先级 | 信号 | 触发条件 | 约束文本 |
|--------|------|---------|---------|
| 1 | Flow: anxiety | flow_channel in (anxiety, near_anxiety) | 降难度+示范，禁止追问/压力 |
| 1 | Flow: boredom | flow_channel == near_boredom | 换角度+加难度，禁止重复 |
| 2 | Mastery: 新手 | mastery < 0.3 | 生活类比，禁止术语/挑战 |
| 2 | Mastery: 熟练 | mastery > 0.7 | 开放题+多解法，禁止重复基础 |
| 3 | TTM: precontemplation | stage | 只探索动机，禁止教学 |
| 3 | TTM: contemplation | stage | 先肯定+低门槛，禁止催促 |
| 3 | TTM: action | stage | 每轮练习，禁止无互动 |
| 3 | TTM: maintenance | stage | 引入变化，禁止重复 |
| 3 | TTM: relapse | stage | 无评判接纳，禁止追因 |
| 4 | SDT: autonomy < 0.4 | | 给选项，禁止替决策 |
| 4 | SDT: competence < 0.4 | | 指进步，禁止直接纠错 |
| 4 | SDT: relatedness < 0.4 | | 关联学生经历 |

---

第四部分: 风险登记册

| 风险 | 状态 | 备注 |
|------|------|------|
| R1 回复过于机械 | ⚠️ 待教学审计验证 | 约束是边界不是脚本 |
| R2 flow 信号误判 | ⚠️ 待教学审计验证 | 影响仅 1 轮 |
| R3 规则间冲突 | ✅ 已缓解 | 四级优先级明确 |
| R4 prompt 长度增加 | ✅ 可接受 | +400 chars，可忽略 |

---

第五部分: 验证命令记录

[粘贴 S96.6 和 S96.7 的实际命令输出]

---

**Phase 96 签收**: [✅ GO / ❌ NO-GO]
```

### 判定标准

| 检查项 | PASS 条件 |
|--------|----------|
| 验收报告完整 | 五个部分全部填写 |
| 逐项比对 | 所有方案承诺 = ✅ |
| 约束矩阵 | 13 条规则全部列出 |
| 风险登记 | 4 项风险全部有状态 |
| 验证命令 | 实际输出，非占位符 |

---

## 附录 A: 完整改动序列

```
执行顺序:
  S96.0 → S96.1 → S96.2 → S96.3 → S96.4 → S96.5 → S96.6 → S96.7 → S96.8

S96.0: 只读。审计当前代码状态。
S96.1: 改 prompts.py terminal_tutoring。
S96.2: 改 prompts.py 插新函数。
S96.3: 改 prompts.py policy_layer 签名 + 函数体。
S96.4: 改 prompts.py build_coach_context 签名 + 调用点。
S96.5: 改 agent.py _build_llm_context_bundle 调用点。
S96.6: 只读。验证+测试。
S96.7: 只读。单元测试。
S96.8: 只读。报告生成。

每个阶段严格串行。前一阶段非 PASS 不得进入下一阶段。
```

## 附录 B: 约束规则优先级决策树

```
生成行为约束:
  │
  ├─ flow_channel == "anxiety"/"near_anxiety"? → 加焦虑规则 (pri=1)
  ├─ flow_channel == "near_boredom"?           → 加无聊规则 (pri=1)
  │
  ├─ mastery < 0.3?  → 加新手规则 (pri=2)
  ├─ mastery > 0.7?  → 加熟练规则 (pri=2)
  │
  ├─ stage 在 TTM map 中? → 加对应阶段规则 (pri=3)
  │
  ├─ autonomy < 0.4?     → 加自主性规则 (pri=4)
  ├─ competence < 0.4?   → 加胜任感规则 (pri=4)
  └─ relatedness < 0.4?  → 加关联感规则 (pri=4)
  │
  ▼
按优先级排序 → 取前 5 条 → 输出
```
