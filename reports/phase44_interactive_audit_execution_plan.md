# Phase 44 — 交互式教学审计：基于 LLM 学生代理

## 1. 文档目的

本文件是 Phase 44 的完整执行计划。它不能被 Phase 44 completion 替代——completion 记录"做完了什么"，本文件定义"怎么做、怎么判定 GO"。

### 1.1 为什么需要这个阶段

当前审计系统用 3 个固定脚本画像评估教学。学生消息是预写字符串，不追问、不困惑、不基于教练回复产生新问题。评分测的是"回复形态"（n-gram、句号数、action_type 一致性），不是"教学效果"（学生学会了没有、教练是否在学生困惑时调整了策略）。

Phase 44 在现有脚本审计旁边建一条新 lane——交互式教学审计——用 LLM 模拟一个有知识状态、有个性、会追问的学生，在真实对话循环中评估教练的教学效果。

### 1.2 本阶段的权威 XML 层

- `meta_prompts/coach/294_phase44_orchestrator.xml`
- `meta_prompts/coach/295_s44_1_student_agent.xml`
- `meta_prompts/coach/296_s44_2_interactive_engine.xml`
- `meta_prompts/coach/297_s44_3_effect_scoring.xml`
- `meta_prompts/coach/298_s44_4_regression_close.xml`

---

## 2. 全局边界

### 2.1 禁止修改
- `contracts/**`
- `src/inner/**`、`src/middle/**`、`src/outer/**`
- provider / model / base_url
- 现有 scoring 维度与 breakpoint probes
- 现有 `score_turn()` 函数和 `--quick` 模式的任何逻辑

### 2.2 本阶段明确不是
- 不替代现有脚本审计（作为形态基线保留）
- 学生代理不干涉教练行为（只读 coach response，不修改）
- 不做多学生同时模拟
- 不做完整多轮长会话（默认 5 轮，可调）
- `student_agent.py` 不依赖 coach 内部模块（除 LLM client）

### 2.3 本阶段是
- 在现有审计旁边建一条新的 `--interactive` lane
- 新增 4 维效果评分，与现有 5 维形态评分并列
- 新增可独立运行、可跨阶段复用的学生代理模块

---

## 3. 执行顺序

严格串行：

1. S44.1 — Student Agent 核心
2. S44.2 — 交互式审计引擎
3. S44.3 — 效果评分
4. S44.4 — 回归与收口

任何一段未 GO，不进入下一段。

---

## 4. S44.1 — Student Agent 核心

### 4.1 目标

创建 `src/coach/student_agent.py`，包含知识状态模型、学生代理类、学生画像和学生 LLM prompt 模板。

### 4.2 当前真实状态

- 此类模块不存在
- 现有审计的学生是 3 个预写字符串列表（`run_experience_audit.py` 的 `PROFILES` 字典）
- 学生不能追问、不能困惑、不能基于教练回复产生新消息

### 4.3 主要输入

无——这是一个全新模块。可参考：
- `src/coach/mrt.py` 的 dataclass 模式
- `src/coach/llm/prompts.py` 的 prompt 模板模式
- `run_experience_audit.py` 的画像概念

### 4.4 主要输出

#### `src/coach/student_agent.py`

##### `StudentKnowledgeState` dataclass

```python
@dataclass
class StudentKnowledgeState:
    known_concepts: dict[str, float]      # 概念 → 掌握度 (0-1)
    exposed_concepts: set[str]             # 教练提过但未验证
    turn_history: list[dict]               # 每轮记录
```

方法：
- `expose(concept: str)` — 教练介绍了新概念，标记为 exposed
- `learn(concept: str, gain: float = 0.15)` — 学生确认理解，掌握度提升。从 exposed 移到 known
- `mastery_delta(before: dict[str, float])` — 计算相对于初始状态的掌握度变化
- `summary() -> str` — 人类可读的知识状态摘要

##### `StudentAgent` 类

```python
class StudentAgent:
    def __init__(self, profile_id: str = "beginner")
    def consume_coach_response(self, coach_response: dict)
    def generate_response(self, llm_client, llm_config) -> str
    def get_mastery_delta(self) -> float
    def get_effectiveness_summary(self) -> dict
```

##### `STUDENT_PROFILES` 字典 — 4 个画像

| profile_id | 名称 | 特点 |
|-----------|------|------|
| beginner | 零基础学习者 | 概念全空，困惑阈值高，被动接收 |
| fuzzy_basics | 有基础但模糊 | 部分概念 0.2-0.3，主动追问 |
| jumpy | 跳跃联想型 | 零散概念，容易走神，灵感多 |
| passive | 被动确认型 | 倾向于只回复确认词，需要教练引导才能追问 |

##### `STUDENT_SYSTEM_PROMPT` 字符串模板

模板包含：画像描述、已知概念摘要、未确定概念列表、上一轮教练教学、上一轮学生消息。约束学生回复为 1-3 句话的真实学生风格。

##### `_extract_concepts(text: str)` — 静态方法

从教练回复文本中提取教学概念。当前用关键词列表兜底，后续可升级为 LLM 提取。

### 4.5 禁止事项

- 学生代理不得 import coach 内部模块（除 LLM client），保持模块解耦
- `learn()` 不接受 gain=0（不会产生"学了但没变化"）
- prompt 不得指示学生刁难教练或故意出错

### 4.6 推荐验证

```bash
python -c "
from src.coach.student_agent import StudentAgent, STUDENT_PROFILES
a = StudentAgent('beginner')
print(a.profile['name'])
print(a.state.mastery_delta({}))
"
```

```bash
python -m pytest tests/ -q
```

### 4.7 GO 标准

- `student_agent.py` 可独立 import，无循环依赖
- `StudentAgent` 可创建全部 4 种画像
- `consume_coach_response()` + `generate_response()` 方法签名正确
- 全量回归不受影响

---

## 5. S44.2 — 交互式审计引擎

### 5.1 目标

在 `run_experience_audit.py` 中新增 `--interactive` 模式，实现学生代理 ↔ 教练 API 的交互循环。

### 5.2 当前真实状态

- `run_experience_audit.py` 有 `--quick` 和完整模式，都使用 `PROFILES` 字典的固定字符串
- `src/coach/student_agent.py` 已在 S44.1 创建

### 5.3 主要输入

- `src/coach/student_agent.py`（S44.1 产出）
- `run_experience_audit.py` 现有结构（函数签名、参数解析、run 目录管理）

### 5.4 主要输出

#### 新增函数：`_run_interactive_audit(student_agent, turns, api_url)`

交互循环伪代码：

```
student_msg = "我想学编程"  # 首条消息由学生代理的画像决定
for turn in 1..turns:
    coach_response = POST api_url/chat {"session_id": sid, "message": student_msg}
    记录 coach_response
    student.consume_coach_response(coach_response)
    student_msg = student.generate_response(llm_client, llm_config)
    记录 student_msg
    记录 student.state snapshot
```

#### 新增 CLI 参数

- `--interactive`：启��交互式审计模式
- `--profile`：学生画像 ID，默认 `beginner`。可选 `beginner|fuzzy_basics|jumpy|passive`
- `--interactive-turns`：交互轮数，默认 5，范围 3-20

#### `--interactive` 与 `--quick` 互斥

用 argparse 的 `mutually_exclusive_group` 约束。不能同时指定。

#### 产出文件

- `reports/experience_audit/runs/<run_id>/interactive_turns.json`

每轮记录：

```json
{
  "turn": 1,
  "student_message": "...",
  "coach_response": {...},
  "student_state_snapshot": {
    "known_concepts": {...},
    "exposed_concepts": [...],
    "mastery_delta_so_far": 0.0
  }
}
```

### 5.5 禁止事项

- 不改 `--quick` 模式的任何逻辑或输出
- 学生代理产生的消息不能超过 500 字符
- 交互循环不能修改 `coach_response` 的原始数据

### 5.6 推荐验证

```bash
# 交互模式不破坏快速模式
python run_experience_audit.py --quick  # 应正常结束

# 交互模式语法检查
python run_experience_audit.py --interactive --help
```

### 5.7 GO 标准

- `--interactive` 参数可被 argparse 正确解析
- `--quick` 和 `--interactive` 互斥约束生效
- `_run_interactive_audit()` 函数签名正确，可被调用
- `--quick` 模式产出与 Phase 43 完全一致

---

## 6. S44.3 — 效果评分

### 6.1 目标

新增 4 维教学效果评分，与现有 5 维形态评分并列，不替代。

### 6.2 当前真实状态

- `run_experience_audit.py` 的 `score_turn()` 只覆盖 5 维形态评分
- `StudentAgent.get_effectiveness_summary()` 已产出 `mastery_delta` 和 `concepts_learned`

### 6.3 主要输入

- `run_experience_audit.py` 的 `score_turn()` 函数（S32.2，不可修改）
- `src/coach/student_agent.py` 的 `StudentAgent.get_effectiveness_summary()`
- `interactive_turns.json`（S44.2 产出）

### 6.4 主要输出

#### 新增函数：`score_interactive_session(turns, student_agent) -> dict`

4 个维度，每维 0-4 分：

| 维度 | 测量内容 | 算法 |
|------|---------|------|
| 知识转移 | 学生概念掌握度是否提升 | pre/post mastery_delta。每 +0.1 得 1 分，上限 4 |
| 策略适应 | 教练是否在学生困惑时调整方法 | 学生消息含困惑关键词后，教练是否切换 action_type。切换得 3-4，合理保持得 1-2，无视困惑得 0 |
| 解释质量 | 学生是否能复述核心概念 | 学生回复与教练教学的概念 n-gram 重叠 + 学生 `learn()` 触发次数 |
| 互动节奏 | 教练是否给学生思考和提问空间 | 学生非确认轮次比例 + 学生追问（为什么/不懂/具体点）次数 |

困惑关键词列表：`"不懂", "不太理解", "困惑", "为什么", "什么意思", "不确定", "不明白"`

#### 产出文件

- `reports/experience_audit/runs/<run_id>/interactive_scoring.json`

```json
{
  "run_id": "...",
  "profile": "beginner",
  "turns": 5,
  "morphology_scores": {
    "引用性": 0.8, "连续性": 3.2, "无空转": 4.0, "稳定性": 3.4, "推进感": 2.6,
    "total": 14.0
  },
  "effect_scores": {
    "知识转移": 2.0, "策略适应": 3.0, "解释质量": 2.5, "互动节奏": 2.0,
    "total": 9.5
  }
}
```

### 6.5 设计约束

- 效果评分与形态评分的总分**不合并**——它们是两个独立视角
- 所有新评分字段必须为 0-4 或 null（无数据时）
- 形态评分仍由原 `score_turn()` 计算，不受影响

### 6.6 禁止事项

- 不修改 `score_turn()` 函数
- 不修改现有 5 维的语义
- 效果评分不参与 `comparison.json` 或 `llm_baseline_band.json` 的当前 band 机制（那是为形态评分设计的）

### 6.7 推荐验证

```bash
# 确认现有评分函数未被修改（git diff 检查）
git diff run_experience_audit.py | grep score_turn

# 确认 score_interactive_session 在交互模式后可调用
python -c "from run_experience_audit import score_interactive_session; print('OK')"
```

### 6.8 GO 标准

- `score_interactive_session()` 函数存在且可 import
- 4 维均为 0-4 范围
- `score_turn()` 未被修改（git diff 确认）

---

## 7. S44.4 — 回归与收口

### 7.1 目标

验证现有脚本审计不受影响，全量回归通过，完成 Phase 44 归档。

### 7.2 当前真实状态

- S44.1-S44.3 的代码改动已完成
- 全量回归需要通过才能收口

### 7.3 任务

1. 运行 `python run_experience_audit.py --quick --use-http` 并对比 Phase 43 的产出——确认评分、breakpoint、evidence 文件产出完全一致
2. 运行 `python -m pytest tests/ -q` ——确认 0 failed
3. 运行 `python run_experience_audit.py --interactive --turns 3 --use-http` ——确认交互循环不崩溃、不超时
4. 输出 `reports/phase44_interactive_audit_completion.md`

### 7.4 GO 标准

- `--quick` 模式行为与 Phase 43 完全一致
- `--interactive` 模式可成功完成交互审计
- 全量回归 0 failed
- completion 文档落盘

---

## 8. 最终验收标准

### A 类：学生代理

- 4 种画像可独立创建
- 知识状态在交互后产生可测量的 delta
- 模块解耦，不依赖 coach 内部模块

### B 类：交互引擎

- `--interactive` 与 `--quick` 互斥且各自正常
- 交互循环无超时、无崩溃
- `interactive_turns.json` 成功产出

### C 类：效果评分

- 4 维效果评分与 5 维形态评分并列
- 评分范围均在 0-4
- 原 `score_turn()` 未被修改

### D 类：回归

- 全量回归 0 failed
- `--quick` 产出与 Phase 43 完全一致
- Phase 44 completion 归档

---

## 9. NO-GO 条件

任一命中，Phase 44 立即判定 NO-GO：

1. 修改了 `contracts/**`、`src/inner/**`、`src/middle/**`、`src/outer/**`
2. 修改了 `score_turn()` 函数
3. `--quick` 模式行为与 Phase 43 不一致
4. `student_agent.py` import 破坏了已有测试
5. 全量回归失败
6. `--interactive` 模式在 3 轮内崩溃或超时
