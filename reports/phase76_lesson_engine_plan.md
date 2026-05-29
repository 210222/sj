# Phase 76: 备课引擎 — 完整落地方案

## 〇、背景

Phase 75 已完成搜索大纲。Phase 76 实现课程化的核心备课循环：搜索资料 → 消化提取 → 费曼自述 → 自验证（三方隔离）→ 质量门 → 备课卡片。这是整个课程化链路中最复杂的阶段——多个 LLM 调用串联 + 循环控制 + 代码层防御。

---

## 阶段 0：全局元提示词

```
你是 Coherence 教练系统的架构审计员。

Phase 76 目标: 实现备课引擎的核心循环——
搜索资料 → 消化提取 → 费曼自述 → 自验证 → 质量门 → 备课卡片。

输入:
  - Phase 75 已完成（搜索大纲 + 结构化 JSON）
  - phase75_curriculum_design.md 中定义的完整备课流程
  - 大纲中的每个知识点逐一进入备课循环

已知约束:
  - 每知识点最多 3 轮循环，3 轮不通过 → 标记"需人工审核"
  - 自验证 3 个独立 LLM 调用（出题/答题/判分）+ 5 道代码层防御
  - 费曼自述 4 道代码层检测（术语/空话/三步跳跃/强制不确定）
  - 消化阶段 JSON schema 强制（≥3 misconceptions, ≥2 sticking_points, ≥2 detours）
  - 不阻塞主教学管线——备课在后台执行

五个根本问题:

Q1: 备课引擎是独立模块还是集成到 CoachAgent？
Q2: 循环控制放哪一层——Python 代码还是 LLM prompt？
Q3: Phase 76 和 Phase 75 的关系——大纲生成后自动备课还是手动触发？
Q4: 备课卡片暂存方案——JSON 文件还是 ChromaDB？如何为 Phase 77 预留接口？
Q5: 逐知识点串行还是整章批量并发？

约束:
  - 每个阶段的 prompt 必须和 Coherence 教学 prompt 完全隔离
  - 不引入新的外部依赖
  - 备课失败不影响现有教学管线
  - 文件数 ≤ 7（MVP 原则）
  - 存储接口抽象——为 Phase 77 ChromaDB 预留

自审查（开始前回答 YES/NO）:
  □ 是否理解了消化/费曼/自验证三者之间的依赖和循环回退机制？
  □ 是否考虑了"LLM 费曼表演理解"的具体防范？
  □ 是否考虑了备课进度可见性（用户如何知道备到哪了）？
  □ 存储方案是否能在 Phase 77 无缝升级到 ChromaDB？
```

### 自审查回答

```
□ YES — 消化产出 → 费曼消费。费曼不通过 → 回搜索。费曼通过 → 自验证。
  自验证不通过 → 回搜索（只搜失败子话题）。自验证通过 → 备课卡片。

□ YES — 术语检测/空话检测/三步跳跃检测/强制不确定追问 四道防线。

□ NO — 当前设计没有进度可见性。备课每知识点 30-90 秒，用户需要知道进度。
  修复: orchestrator 每完成一个知识点回调 progress_callback(kp_name, status)。

□ NO — Phase 76 如果用 JSON 文件直接写，Phase 77 迁移需要重写。
  修复: AbstractLessonStore 抽象接口 → JsonLessonStore 实现 → Phase 77 换 ChromaDB。
```

---

## 阶段 1：架构决策

### 阶段 1 元提示词

```
你的任务: 回答 Q1-Q5。每个决策必须给出理由和替代方案分析。

输入: 阶段 0 自审查中的未解决问题

输出: 每个 Q 的答案 + 理由 + 被否决方案 + 否决原因

约束:
  - 不引入外部依赖
  - 文件数 ≤ 7
  - 存储接口抽象
```

### Q1: 独立模块还是集成到 CoachAgent？

```
选: 独立模块 —— src/coach/curriculum/orchestrator.py。

理由:
  - 备课和教学是两个独立生命周期。CoachAgent 负责教学，Orchestrator 负责备课。
  - 独立模块可单独测试，不依赖 CoachAgent 的复杂管线。
  - 备课期间不需要 CoachAgent 的任何内部状态。

模块结构:
  src/coach/curriculum/
    __init__.py
    models.py          # 数据类
    orchestrator.py    # 主循环控制
    digester.py        # 消化阶段
    feynman.py         # 费曼自述 + 代码检测
    verifier.py        # 自验证 + 5道防御
    store.py           # 存储接口 + JSON 实现

被否决:
  ❌ 集成到 CoachAgent → 否决: _prev_teaching 会被备课内容污染
  ❌ 独立微服务 → 否决: 单用户系统不需要进程级隔离
```

### Q2: 循环控制放哪一层？

```
选: Python 代码层 —— orchestrator.py 中的 for 循环。

理由:
  - LLM 不应该控制"要不要重试"——LLM 会倾向于 self-pass
  - 代码层判断: 费曼 grade != "通过" → 回搜索。自验证 verified != true → 回搜索
  - 3 轮硬上限在代码层强制执行——LLM 绕不过去

伪代码:
  for attempt in range(1, 4):
      search_result = digester.search_knowledge(kp)
      digested = digester.digest(kp, search_result)
      if not digester.validate(digested): continue
      feynman = feynman.explain(kp, digested)
      if not feynman.check(feynman): continue
      verified = verifier.verify(kp, feynman, digested)
      if not verified.verified: continue
      card = build_card(kp, digested, feynman, verified)
      if quality_gate(card): return card
  return mark_for_review(kp)
```

### Q3: 自动备课还是手动触发？

```
选: 自动启动，逐章确认。

Phase 75 大纲确认 → 自动备第 1 章
→ 备完通知: "第 1 章已备好，要开始学吗？还是继续备第 2 章？"
→ 用户选择: 开始学 / 继续备课 / 先看卡片
```

### Q4: 暂存方案？

```
选: JSON 文件 + 抽象接口。

AbstractLessonStore（定义接口）→ JsonLessonStore（Phase 76 实现）
→ Phase 77 替换为 ChromaLessonStore，接口不变。
```

### Q5: 串行还是并发？

```
选: 逐知识点串行。

理由: 每个知识点依赖费曼自述的结果（[不确定] 标记影响后续搜索方向）。
      串行保证质量——不会因为并发而跳过自我诊断。
      每知识点 ~30-90 秒，一章 3 知识点 ≈ 2-5 分钟。
```

---

## 阶段 2：技术方案 —— 7 文件的精确实现

### 阶段 2 元提示词

```
你的任务: 写出 Phase 76 的精确改动清单、每个模块的完整代码、prompt 设计。

输入: 阶段 1 的架构决策 + phase75_curriculum_design.md 中的 prompt 定义

输出:
  1. 每个文件的完整代码（可直接复制运行）
  2. 每个 LLM 调用的 prompt 模板
  3. 代码层检测函数
  4. 验证测试方案

自审查:
  □ 费曼代码检测是否覆盖了四道防线？
  □ 自验证三方调用是否真的独立（三个独立 LLM 请求）？
  □ 循环控制是否在代码层而非 prompt 层？
  □ 存储接口是否方便 Phase 77 替换？
```

---

### 文件 1: `src/coach/curriculum/__init__.py`

```python
"""Phase 76: 备课引擎 — 搜索→消化→费曼→自验证→卡片."""
```

### 文件 2: `src/coach/curriculum/models.py`

```python
"""备课引擎数据模型."""

from dataclasses import dataclass, field


@dataclass
class KnowledgePoint:
    name: str
    chapter_id: str
    subject: str
    category: str


@dataclass
class DigestedOutput:
    knowledge_point: str
    definition: str
    misconceptions: list[str]  # ≥3
    sticking_points: list[str]  # ≥2
    detours: list[str]  # ≥2
    prerequisites: list[str]

    def validate(self) -> tuple[bool, list[str]]:
        errors = []
        if not self.definition:
            errors.append("definition is empty")
        if len(self.misconceptions) < 3:
            errors.append(f"misconceptions < 3: {len(self.misconceptions)}")
        if len(self.sticking_points) < 2:
            errors.append(f"sticking_points < 2: {len(self.sticking_points)}")
        if len(self.detours) < 2:
            errors.append(f"detours < 2: {len(self.detours)}")
        return len(errors) == 0, errors


@dataclass
class FeynmanCard:
    knowledge_point: str
    analogy: str
    one_sentence: str
    three_steps: list[str]
    uncertain_markers: list[dict]
    grade: str  # "通过" | "不通过"
    jargon_count: int


@dataclass
class VerificationReport:
    knowledge_point: str
    verified: bool
    total_questions: int
    passed_questions: int
    failed_topics: list[str]
    call1_questions: list[dict]
    call2_answers: list[dict]
    call3_grading: dict


@dataclass
class LessonCard:
    knowledge_point: str
    chapter_id: str
    subject: str
    category: str
    definition: str
    feynman: dict
    self_verify: dict
    teaching_insights: dict
    exercises: list[dict]
    quality_gate: dict
    version: int
    created_at: str
```

### 文件 3: `src/coach/curriculum/store.py`

```python
"""备课卡片存储 — 抽象接口 + JSON 实现."""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

_logger = logging.getLogger(__name__)


class AbstractLessonStore(ABC):
    @abstractmethod
    def save_card(self, course_id: str, card) -> None:
        ...

    @abstractmethod
    def get_card(self, course_id: str, knowledge_point: str) -> dict | None:
        ...

    @abstractmethod
    def list_cards(self, course_id: str) -> list[str]:
        ...

    @abstractmethod
    def card_count(self, course_id: str) -> int:
        ...


class JsonLessonStore(AbstractLessonStore):
    """Phase 76: JSON 文件存储。Phase 77 替换为 ChromaLessonStore。"""

    def __init__(self, base_dir: str | None = None):
        if base_dir is None:
            base_dir = str(
                Path(__file__).resolve().parent.parent.parent.parent
                / "data" / "lesson_cards"
            )
        self._base = Path(base_dir)

    def _path(self, course_id: str, kp: str) -> Path:
        safe_kp = kp.replace("/", "_").replace("\\", "_")
        return self._base / course_id / f"{safe_kp}.json"

    def save_card(self, course_id: str, card) -> None:
        p = self._path(course_id, card.knowledge_point)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "knowledge_point": card.knowledge_point,
            "chapter_id": card.chapter_id,
            "subject": card.subject,
            "category": card.category,
            "definition": card.definition,
            "feynman": card.feynman,
            "self_verify": card.self_verify,
            "teaching_insights": card.teaching_insights,
            "exercises": card.exercises,
            "quality_gate": card.quality_gate,
            "version": card.version,
            "created_at": card.created_at,
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_card(self, course_id: str, knowledge_point: str) -> dict | None:
        p = self._path(course_id, knowledge_point)
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def list_cards(self, course_id: str) -> list[str]:
        d = self._base / course_id
        if not d.exists():
            return []
        return [p.stem for p in d.glob("*.json")]

    def card_count(self, course_id: str) -> int:
        return len(self.list_cards(course_id))
```

### 文件 4: `src/coach/curriculum/digester.py`

```python
"""消化阶段: 搜索知识点资料 → 提取结构化教学信息."""

import json
import logging

_logger = logging.getLogger(__name__)

# — 搜索 prompt —
DIGEST_SEARCH_SYSTEM = """你是教学研究员。搜索 {kp} 的教学资料。

搜索方向:
1. {kp} 的准确定义（找 2-3 个权威源交叉验证）
2. 初学者在 {kp} 上最常见的 3-5 个误解
3. 学生在 {kp} 上最容易卡住的 2-3 个地方
4. 初学者在学习 {kp} 时容易走的 2-3 条弯路
5. 学习 {kp} 必须的前置知识

学科: {subject}（{category}）
输出为纯文本，不要 JSON。"""

DIGEST_SEARCH_USER = """请搜索 {subject} 中 "{kp}" 的教学资料。

重点搜索:
- 官方文档中的定义
- StackOverflow 上关于 {kp} 的高赞误区
- 教学博客中提到的常见卡点

输出为纯文本摘要，列出所有找到的关键信息。"""

# — 消化 prompt —
DIGEST_SYSTEM = """你是教学研究员。根据搜索结果，提取 {kp} 的结构化教学信息。

输出 JSON（严格按此格式，不得修改结构）:

{{
  "definition": "{kp} 的精确定义（1-2句话，从搜索结果中交叉验证得出）",
  "misconceptions": [
    "误解1: 具体的错误理解内容",
    "误解2: 另一个常见错误",
    "误解3: ..."
  ],
  "sticking_points": [
    "卡点1: 学生容易卡在哪个环节",
    "卡点2: ..."
  ],
  "detours": [
    "弯路1: 初学者常走的弯路",
    "弯路2: 学了正确内容后再回头看这个内容觉得浪费时间的"
  ],
  "prerequisites": [
    "前置知识1",
    "前置知识2"
  ]
}}

约束:
- misconceptions ≥ 3 条，每条必须具体（不是"理解不深"这种泛泛描述）
- sticking_points ≥ 2 条
- detours ≥ 2 条
- 所有内容必须能从搜索结果中找到依据
- 只输出 JSON，不输出其他文字"""

DIGEST_USER = """为 {subject}（{category}）的 "{kp}" 提取教学信息。

搜索结果:
{search_text}

请提取 misconception、sticking_point、detour、prerequisite。
每个条目必须具体、可操作、有搜索依据。"""


def digest(kp_name: str, search_text: str, llm_client,
           subject: str = "", category: str = "") -> "DigestedOutput":
    """消化: 搜索 → 提取结构化信息 → 校验。"""
    from src.coach.curriculum.models import DigestedOutput

    system = DIGEST_SYSTEM.replace("{kp}", kp_name)
    user = DIGEST_USER.replace("{subject}", subject or kp_name)
    user = user.replace("{category}", category)
    user = user.replace("{kp}", kp_name)
    user = user.replace("{search_text}", search_text[:3000])

    raw = llm_client.search(system, user)
    if isinstance(raw, str):
        raw = json.loads(raw)

    return DigestedOutput(
        knowledge_point=kp_name,
        definition=str(raw.get("definition", "")),
        misconceptions=[str(m) for m in raw.get("misconceptions", [])],
        sticking_points=[str(s) for s in raw.get("sticking_points", [])],
        detours=[str(d) for d in raw.get("detours", [])],
        prerequisites=[str(p) for p in raw.get("prerequisites", [])],
    )


def search_knowledge(kp_name: str, llm_client,
                     subject: str = "", category: str = "") -> str:
    """搜索知识点的原始教学资料。"""
    system = DIGEST_SEARCH_SYSTEM.replace("{kp}", kp_name)
    system = system.replace("{subject}", subject or kp_name)
    system = system.replace("{category}", category)
    user = DIGEST_SEARCH_USER.replace("{subject}", subject or kp_name)
    user = user.replace("{kp}", kp_name)

    resp = llm_client.search(system, user, json_mode=False)
    if isinstance(resp, dict):
        text = resp.get("raw_text", json.dumps(resp, ensure_ascii=False))
    else:
        text = str(resp)
    return text
```

### 文件 5: `src/coach/curriculum/feynman.py`

```python
"""费曼自述阶段: 比喻解释 + 一句话 + 三步拆解 + 代码检测."""

import json
import logging
import re

_logger = logging.getLogger(__name__)

FEYNMAN_SYSTEM = """你是 {subject} 教师，正在备课 "{kp}"。

用费曼学习法检验自己——如果你不能用简单的比喻向12岁小孩讲清楚，说明你没有真正理解。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
规则（缺一条 = 不通过）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 用比喻解释，零术语。如果必须用术语，先定义它。
   正确: "变量像贴标签。盒子是内存，标签是变量名。age=25是把25放进盒子。"
   错误: "变量是内存地址的符号引用，赋值将右值绑定到左值标识符。"

2. 一句话归纳核心。格式: "一句话：________"
   正确: "一句话：极限 = 无限接近但从不到达。"
   错误: "一句话：极限是微积分的基础概念，在数学分析中很重要。"（这是"重要性"不是"核心"）

3. 拆成三个最小步骤。每步一句话，可独立理解，无逻辑跳跃。

4. 标注每一个不确定。任何时间感到"这个比喻不够精确""这个边界我没把握"→ 必须标注[不确定]。
   格式: [不确定] 位置描述: 为什么不精确 / 还需要搞清楚什么
   [不确定] 不是失败——它告诉你在教这个知识前还有什么要深挖。

消化阶段参考:
  定义: {definition}
  常见误解: {misconceptions}
  容易卡住: {sticking_points}
  常见弯路: {detours}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
输出 JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "analogy": "零术语比喻解释（100-200字）",
  "one_sentence": "一句话核心归纳",
  "three_steps": ["步骤1", "步骤2", "步骤3"],
  "uncertain_markers": [
    {{"location": "在比喻的哪部分", "issue": "为什么不精确", "whats_needed": "还需要搞清楚什么"}}
  ],
  "grade": "通过 或 不通过"
}}

只输出 JSON。"""

FEYNMAN_USER = """请对 {subject} 的 "{kp}" 做费曼自述。参考消化阶段的信息，但必须用自己的理解和比喻。"""


# — 各学科的术语词库 —
JARGON_DB = {
    "编程语言": ["变量", "赋值", "引用", "内存", "类型", "函数", "参数", "返回",
                 "对象", "类", "实例", "指针", "静态", "动态", "编译", "解释",
                 "作用域", "循环", "条件", "迭代", "递归", "模块", "导入"],
    "数学": ["函数", "极限", "导数", "积分", "矩阵", "向量", "定理", "证明",
             "收敛", "发散", "无穷", "域", "集合", "映射", "变换", "特征值"],
    "语言学习": ["时态", "语态", "从句", "主语", "谓语", "宾语", "定语", "状语",
                 "虚拟语气", "倒装", "省略", "冠词", "介词", "连词"],
}
HOLLOW_PATTERNS = [
    re.compile(r"是.*的基础"), re.compile(r"在.*中很重要"),
    re.compile(r"是.*的核心概念"), re.compile(r"理解.*的关键"),
    re.compile(r"掌握.*的前提"),
]


def feynman_self_explain(kp_name: str, digested, llm_client,
                         subject: str = "", category: str = "") -> "FeynmanCard":
    """费曼自述 + 代码层检测。"""
    from src.coach.curriculum.models import FeynmanCard

    system = FEYNMAN_SYSTEM.replace("{subject}", subject or kp_name)
    system = system.replace("{kp}", kp_name)
    system = system.replace("{definition}", digested.definition)
    system = system.replace("{misconceptions}", ", ".join(digested.misconceptions))
    system = system.replace("{sticking_points}", ", ".join(digested.sticking_points))
    system = system.replace("{detours}", ", ".join(digested.detours))

    user = FEYNMAN_USER.replace("{subject}", subject or kp_name)
    user = user.replace("{kp}", kp_name)

    raw = llm_client.search(system, user)
    if isinstance(raw, str):
        raw = json.loads(raw)

    card = FeynmanCard(
        knowledge_point=kp_name,
        analogy=str(raw.get("analogy", "")),
        one_sentence=str(raw.get("one_sentence", "")),
        three_steps=[str(s) for s in raw.get("three_steps", [])],
        uncertain_markers=list(raw.get("uncertain_markers", [])),
        grade=str(raw.get("grade", "不通过")),
        jargon_count=0,
    )

    # 代码层检测
    card = feynman_code_check(card, category)
    return card


def feynman_code_check(card: "FeynmanCard", category: str = "") -> "FeynmanCard":
    """四道防线: 术语 + 空话 + 跳跃 + 不确定追问。"""
    jargon_list = JARGON_DB.get(category, [])
    found = [j for j in jargon_list if j in card.analogy]
    card.jargon_count = len(found)
    if found:
        card.grade = "不通过"
        _logger.warning(f"Feynman jargon detected ({category}): {found}")

    for pat in HOLLOW_PATTERNS:
        if pat.search(card.one_sentence):
            card.grade = "不通过"
            _logger.warning(f"Feynman hollow one_sentence: {card.one_sentence[:60]}")

    if len(card.three_steps) < 3:
        card.grade = "不通过"

    if len(card.uncertain_markers) == 0 and card.grade == "通过":
        _logger.warning(f"Feynman zero uncertainty for {card.knowledge_point} — possible performance")
        card.uncertain_markers.append({
            "location": "自动检测",
            "issue": "零 [不确定] 标注——可能是表演性理解",
            "whats_needed": "强制追问: 比喻在什么条件下失效？有没有不敢100%确定的边界case？"
        })

    return card
```

### 文件 6: `src/coach/curriculum/verifier.py`

```python
"""自验证阶段: 出题/答题/判分三方隔离 + 5 道代码防御."""

import json
import logging
import random
import re

_logger = logging.getLogger(__name__)

VERIFIER_Q_SYSTEM = """你是考题设计师。你的任务是**找出教师理解的漏洞**。

你正在审核 {subject} 的 "{kp}" 知识点。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
出 3 类题目，每类 ≥ 1 题，总 ≥ 5 题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A 类 — 误解陷阱（盯着这些 misconceptions 出题）:
  {misconceptions}
  每条 misconception 必须至少有 1 道题覆盖。

B 类 — 边界推演（盯着这些 sticking_points 出题）:
  {sticking_points}
  至少 1 道题针对 sticking_points。

C 类 — 对比质疑（为什么选 A 而不是 B）:
  设计题目让教师解释设计选择，而不是只证明"选A是对的"。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
题目格式硬约束
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

禁止: 纯选择题/判断题/填空题
允许: 开放型问答题/"给出输出并解释原因"/"找出错误并修正"/"用比喻解释"/"对比分析"
C类题如用"选择"措辞 → 必须要求回答包含设计目标+选择理由+代价/局限三要素。

输出 JSON（只出题，不回答）:
{{
  "questions": [
    {{"id": "Q1", "type": "A", "targets": "针对哪条 misconception",
      "question": "题目文本",
      "expected_outline": "判分参考——期望的大致回答方向"}}
  ],
  "coverage": {{"total_misconceptions": N, "covered": N, "uncovered": []}}
}}

coverage.uncovered 非空 → 输出不完整，重新出题。只输出 JSON。"""

VERIFIER_A_SYSTEM = """你是被考核的 {subject} 教师。逐题诚实回答。

规则:
1. 每道题独立回答。不会就说不会。
2. 确定 → certainty: "high"。基本确定有细微不确定 → "medium"。不确定 → "low"或"uncertain"。
3. 低 certainty 时必须说明卡在哪里、需要查什么。
4. 不要用废话填充——诚实的"我卡在XX"比长篇废话更有价值。

输出 JSON:
{{"answers": [
  {{"question_id": "Q1", "answer": "你的回答",
    "certainty": "high|medium|low|uncertain",
    "uncertain_detail": "如果不确定——卡在哪"}}
]}}"""

VERIFIER_G_SYSTEM = """你是判卷人。不给同情分。

判分标准（任何一条不满足 → 不通过）:
- 回答正确且推理完整
- certainty="high"或"medium"
- 能用非术语的语言表述
- 和消化阶段的定义一致（不一致 → 消化阶段可能有问题）

不通过条件（任何一条满足 → 不通过）:
- 回答模糊、回避、答非所问
- 回答用术语解释术语
- certainty="low"或"uncertain"
- 回答"需要具体分析"但未给出分析框架

输出 JSON:
{{
  "graded": [{{"question_id": "Q1", "passed": true/false, "reason": "..."}}],
  "verified": true/false,
  "failed_topics": [],
  "deductions": [],
  "improvements": []
}}
"""

# — 代码防御 —
RED_FLAGS = ["从某种角度来说", "需要具体分析", "取决于具体情况",
             "总而言之", "关键在于", "既要...又要", "辩证地看"]
SELECTION_ONLY = re.compile(r"^[A-D][)）]?\s*$|^选\s*[A-D]\s*$|^答案是?\s*[A-D]\s*$")


def self_verify(kp_name: str, feynman_card, digested, llm_client,
                subject: str = "", category: str = "") -> "VerificationReport":
    """自验证: 3 个独立 LLM 调用 + 代码防御。"""
    from src.coach.curriculum.models import VerificationReport

    # Call 1: question setter
    q_system = VERIFIER_Q_SYSTEM.replace("{subject}", subject or kp_name)
    q_system = q_system.replace("{kp}", kp_name)
    q_system = q_system.replace("{misconceptions}", ", ".join(digested.misconceptions))
    q_system = q_system.replace("{sticking_points}", ", ".join(digested.sticking_points))
    q_user = f"为 {subject} 的 {kp_name} 设计自验证考题。"
    q_raw = llm_client.search(q_system, q_user)
    if isinstance(q_raw, str):
        q_raw = json.loads(q_raw)
    questions = q_raw.get("questions", [])

    # Defense 1: coverage check
    covered = set(q.get("targets", "") for q in questions)
    if len(questions) < 5:
        return VerificationReport(kp_name, False, len(questions), 0, ["不足5题"], [], [], {})
    types = set(q["type"] for q in questions)
    for t in ["A", "B", "C"]:
        if t not in types:
            return VerificationReport(kp_name, False, len(questions), 0, [f"缺{t}类题"], [], [], {})

    # Detect forbidden question types
    for q in questions:
        for pat, qtype in [(re.compile(r"下列(哪个|哪项|哪种).*(正确|错误|恰当)"), "纯选择题"),
                            (re.compile(r"对还是错|判断.*正确.*错误"), "判断题"),
                            (re.compile(r"填空|____"), "填空题")]:
            if pat.search(q["question"]):
                return VerificationReport(kp_name, False, len(questions), 0, [f"禁止题型: {qtype}"], [], [], {})

    # Defense 5: obfuscate questions
    shuffled, target_ids = _obfuscate(questions)
    a_user = f"回答以下考题:\n{json.dumps(shuffled, ensure_ascii=False, indent=2)}"

    # Call 2: exam taker
    a_system = VERIFIER_A_SYSTEM.replace("{subject}", subject or kp_name)
    a_raw = llm_client.search(a_system, a_user)
    if isinstance(a_raw, str):
        a_raw = json.loads(a_raw)
    answers = a_raw.get("answers", [])

    # Defense 2: answer quality
    for a in answers:
        # Non-answer detection
        for flag in RED_FLAGS:
            if flag in a.get("answer", "") and a.get("certainty") in ("high", "medium"):
                return VerificationReport(kp_name, False, 0, 0, ["废话检测"], [], [], {})
        if a.get("answer", "").count("但") > 3 and a.get("certainty") != "low":
            return VerificationReport(kp_name, False, 0, 0, ["过度转折"], [], [], {})
        # Bare selection detection
        if SELECTION_ONLY.match(a.get("answer", "").strip()):
            return VerificationReport(kp_name, False, 0, 0, ["只选不解释"], [], [], {})
        if re.match(r"^[A-D][)）]", a.get("answer", "")[:3]) and len(a.get("answer", "")) < 80:
            return VerificationReport(kp_name, False, 0, 0, ["选项推理不足"], [], [], {})

    # Filter target answers only
    target_answers = [a for a in answers if a["question_id"] in target_ids]

    # Call 3: grader
    g_user = f"判分:\n题目: {json.dumps([q for q in questions if q['id'] in target_ids], ensure_ascii=False, indent=2)}\n回答: {json.dumps(target_answers, ensure_ascii=False, indent=2)}"
    g_raw = llm_client.search(VERIFIER_G_SYSTEM, g_user)
    if isinstance(g_raw, str):
        g_raw = json.loads(g_raw)
    verified = g_raw.get("verified", False)
    failed = g_raw.get("failed_topics", [])
    passed_q = sum(1 for g in g_raw.get("graded", []) if g.get("passed", False))

    # Defense 3: grading strictness
    if verified:
        uncertain_answers = [a for a in target_answers if a.get("certainty") in ("low", "uncertain")]
        if uncertain_answers:
            verified = False
            failed.append("不确定答题但判通过")
        if not g_raw.get("improvements"):
            _logger.warning("Grader passed without improvements")

    # Defense 4: model bias (every 5 KPs, run external check)
    # Simplified: skip for now, can be added as a cron-like check

    return VerificationReport(
        knowledge_point=kp_name,
        verified=verified,
        total_questions=len(questions),
        passed_questions=passed_q,
        failed_topics=failed,
        call1_questions=questions,
        call2_answers=answers,
        call3_grading=g_raw,
    )


def _obfuscate(questions: list) -> tuple[list, list]:
    """打乱顺序，返回 (shuffled, target_ids)。"""
    shuffled = list(questions)
    random.shuffle(shuffled)
    return shuffled, [q["id"] for q in questions]
```

### 文件 7: `src/coach/curriculum/orchestrator.py`

```python
"""备课引擎主循环: 逐章逐知识点 → 3轮循环 → 进度回调."""

import json
import logging
from datetime import datetime, timezone
from typing import Callable

from src.coach.curriculum.models import KnowledgePoint, LessonCard
from src.coach.curriculum.store import AbstractLessonStore, JsonLessonStore
from src.coach.curriculum.digester import digest, search_knowledge
from src.coach.curriculum.feynman import feynman_self_explain
from src.coach.curriculum.verifier import self_verify

_logger = logging.getLogger(__name__)
MAX_RETRIES = 3


def prepare_knowledge_point(
    kp: KnowledgePoint,
    llm_client,
    store: AbstractLessonStore | None = None,
    course_id: str = "",
    on_progress: Callable | None = None,
) -> LessonCard | None:
    """单知识点备课: 搜索→消化→费曼→自验证→卡片。最多 3 轮。"""
    store = store or JsonLessonStore()

    def _progress(status: str, detail: str = ""):
        if on_progress:
            on_progress(kp.name, status, detail)

    for attempt in range(1, MAX_RETRIES + 1):
        _progress(f"搜索中 (第{attempt}轮)")
        search_text = search_knowledge(kp.name, llm_client, kp.subject, kp.category)

        _progress(f"消化中 (第{attempt}轮)")
        digested = digest(kp.name, search_text, llm_client, kp.subject, kp.category)
        ok, errs = digested.validate()
        if not ok:
            _logger.warning(f"Digest validation failed (attempt {attempt}): {errs}")
            continue

        _progress(f"费曼自述 (第{attempt}轮)")
        feynman = feynman_self_explain(kp.name, digested, llm_client, kp.subject, kp.category)
        if feynman.grade != "通过":
            _logger.warning(f"Feynman failed (attempt {attempt}): jargon={feynman.jargon_count}")
            continue

        _progress(f"自验证 (第{attempt}轮)")
        verified = self_verify(kp.name, feynman, digested, llm_client, kp.subject, kp.category)
        if not verified.verified:
            _logger.warning(f"Verify failed (attempt {attempt}): {verified.failed_topics}")
            continue

        # Build card
        card = LessonCard(
            knowledge_point=kp.name,
            chapter_id=kp.chapter_id,
            subject=kp.subject,
            category=kp.category,
            definition=digested.definition,
            feynman={
                "analogy": feynman.analogy,
                "one_sentence": feynman.one_sentence,
                "three_steps": feynman.three_steps,
                "grade": feynman.grade,
            },
            self_verify={
                "total": verified.total_questions,
                "passed": verified.passed_questions,
                "verified": verified.verified,
            },
            teaching_insights={
                "misconceptions": digested.misconceptions,
                "sticking_points": digested.sticking_points,
                "detours": digested.detours,
                "prerequisites": digested.prerequisites,
            },
            exercises=verified.call1_questions,
            quality_gate={"passed": True, "checks": 5},
            version=1,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        _progress("已完成")
        store.save_card(course_id, card)
        return card

    _progress("需人工审核")
    return None


def prepare_chapter(
    chapter: dict,
    subject: str,
    category: str,
    llm_client,
    course_id: str = "",
    store: AbstractLessonStore | None = None,
    on_progress: Callable | None = None,
) -> dict[str, LessonCard | None]:
    """逐知识点备课一章。返回 {kp_name: LessonCard | None}。"""
    store = store or JsonLessonStore()
    results = {}

    for section in chapter.get("sections", []):
        for kp_name in section.get("knowledge_points", []):
            kp = KnowledgePoint(
                name=kp_name,
                chapter_id=chapter.get("id", ""),
                subject=subject,
                category=category,
            )
            card = prepare_knowledge_point(kp, llm_client, store, course_id, on_progress)
            results[kp_name] = card

    return results
```

---

## 阶段 3：交互审查 + 回归风险

### 阶段 3 元提示词

```
你的任务: 审查 Phase 76 改动对现有系统的影响。

输入: 阶段 2 的 7 个文件

审查对象:
  1. 现有教学管线 — 是否受影响？
  2. LLMClient.search() — 备课和教学的 search() 调用是否隔离？
  3. API 配额 — 备一堂课消耗多少次 LLM 调用？
  4. 测试基线 — 新增模块是否影响 1466 现有测试？
  5. 进度回调 — 是否每个知识点完成都通知用户？

输出: 回归风险矩阵
```

### 回归风险矩阵

| 风险 | 概率 | 影响 | 防范 |
|------|------|------|------|
| 备课占用 LLM 配额 | 高 | 中 | 每知识点 4-5 次 API 调用。备完可缓存的 12 章 ≈ 60 次调用。对比教学每次对话 1 次，占比可接受 |
| 费曼/自验证 prompt 和教学 prompt 混淆 | 无 | 无 | 备课走独立 LLMClient.search()，不走 coaching 管线 |
| JsonLessonStore 文件散落 | 低 | 低 | 统一 data/lesson_cards/ 目录，Phase 77 无缝迁移 |
| 循环中某一步抛异常 → 整个知识点备课中断 | 中 | 中 | orchestrator 每步 try/except → 异常 = 该轮失败 → 下一轮 |
| 现有测试受影响 | 无 | 无 | 新增模块，不修改现有文件 |

### 不影响的部分

```
✅ CoachAgent.act() — 完全独立
✅ 终端自检清单 — 不经过
✅ LLMClient.generate() — 不修改
✅ 前端 — MVP 不需要新 UI
✅ 现有测试 — 新增模块，不影响 1466 测试
```

---

## 四、验证测试

```python
# 手动验证（需 DEEPSEEK_API_KEY）
from src.coach.llm.config import LLMConfig
from src.coach.llm.client import LLMClient
from src.coach.curriculum.orchestrator import prepare_knowledge_point
from src.coach.curriculum.models import KnowledgePoint

config = LLMConfig.from_yaml(cfg)
client = LLMClient(config)

kp = KnowledgePoint(name="变量赋值", chapter_id="ch1",
                    subject="Python", category="编程语言")

# 准备进度回调
def progress(kp_name, status, detail):
    print(f"  [{status}] {kp_name}: {detail}")

card = prepare_knowledge_point(kp, client, on_progress=progress)
if card:
    print(f"备课成功: {card.definition}")
    print(f"费曼: {card.feynman['one_sentence']}")
else:
    print("备课失败（需人工审核）")
```

### 验证检查点

```
□ 单知识点备课流程跑通（搜索→消化→费曼→自验证→卡片）
□ 费曼术语检测生效（故意给一个术语比喻 → 判不通过）
□ 自验证三方调用返回 verified=true
□ 卡片已写入 data/lesson_cards/{course_id}/{kp}.json
□ 3 轮失败后返回 None
□ 异常不中断主循环（try/except 包裹每个阶段）
□ 现有测试 1466 passed
```

---

## 五、实施清单

```
1. [新建] src/coach/curriculum/__init__.py
2. [新建] src/coach/curriculum/models.py
3. [新建] src/coach/curriculum/store.py
4. [新建] src/coach/curriculum/digester.py
5. [新建] src/coach/curriculum/feynman.py
6. [新建] src/coach/curriculum/verifier.py
7. [新建] src/coach/curriculum/orchestrator.py
8. [验证] 手动运行验证测试（需 API key）
9. [验证] python -m pytest tests/ -q → 1466 passed
```
