# Phase 78: BKT 章节化 — 完整落地方案

## 〇、背景

Phase 75-76 已交付课程大纲 + 备课卡片。当前 BKT 引擎追踪 20 个孤立技能节点（skill_graph.json），与课程章节结构不匹配。Phase 78 将 BKT 从"技能级"升级为"知识点→章节→课程"三级追踪。

---

## 阶段 0：全局元提示词

```
你是 Coherence 教练系统的架构审计员。

Phase 78 目标: 将 BKT 掌握度追踪从"20 个孤立技能节点"升级为"课程章节级追踪"。

当前状态:
  - skill_graph.json: 20 个独立技能节点，含 prerequisites 和 related
  - SkillMasteryStore: 每技能一个 BKTEngine，诊断探针观测更新
  - SkillGraph: DAG 依赖图 + 知识传播（gain×0.3 到子技能）
  - 3 个 BKT 参数: prior=0.3, guess=0.1, slip=0.1, learn=0.2

Phase 75-76 交付:
  - 课程大纲: 12 章 → 每章 2-3 节 → 每节 N 个知识点
  - 备课卡片: 每知识点有练习题（exercises 字段）

目标:
  - 知识点级 BKT: 每个 knowledge_point 一个 BKTEngine（从 LessonCard 练习题观测）
  - 章节级聚合: 该章所有知识点的观测加权平均
  - 课程级进度: 所有章节的 mastery 汇总
  - 章节解锁: 前一章 mastery >= threshold → 解锁下一章
  - 旧版兼容: 无大纲时回退到 skill_graph + 诊断探针

五个根本问题:

Q1: BKT 追踪粒度——三层都要？
Q2: 观测数据来源——LessonCard 练习题 vs 诊断探针？
Q3: 知识传播（gain×0.3）在章节级如何变化？
Q4: 章节解锁阈值——全局还是每章不同？
Q5: BKT 数据存储——JSON 还是 ChromaDB？Phase 78 和 Phase 77 的关系？

约束:
  - 不改 SkillMasteryStore 的 API（1466 测试保护）
  - 不改 skill_graph.json（向后兼容）
  - 新增 chapter_graph.json 独立存放
  - 无大纲时自动回退到旧行为

自审查（开始前回答 YES/NO）:
  □ 是否理解了 BKT 从孤立技能到课程树的三级追踪架构？
  □ 是否考虑了 LessonCard 练习题和诊断探针的共存/切换？
  □ 是否考虑了无课程大纲时的回退路径？
  □ 是否考虑了 mastery 下降后是否重新锁定章节？
```

### 自审查回答

```
□ YES — 底层 BKTEngine 不变。上层 ChapterProgressStore 做聚合。
  三层: knowledge_point → chapter → course。

□ YES — 有课程大纲 → 练习题观测。无大纲 → 诊断探针（旧行为）。
  切换机制: if syllabus_exists for this session → use exercise path else probe path。

□ YES — Phase 78 在无大纲时完全回退到现有 skill_graph + 诊断探针。

□ NO — 当前设计不重新锁定。mastery 下降 → 设置面板显示警告但不锁。
  理由: 学生已经学过，重新锁死会打击积极性。解锁是单向的。
```

---

## 阶段 1：架构决策

### 阶段 1 元提示词

```
你的任务: 回答 Q1-Q5。每个决策给出理由和替代方案分析。

输入: 阶段 0 自审查中未解决的问题（Q4 回退锁定）

输出: 每个 Q 的答案 + 理由 + 被否决方案 + 否决原因

约束:
  - 改动文件数 ≤ 3
  - 不改 SkillMasteryStore API
  - 旧版兼容
```

### Q1: 三层追踪架构

```
选: 三层，底层不变。

底层（知识点 BKT）:
  每个 knowledge_point 一个 BKTEngine 实例
  观测: 学生回答练习题正确/错误
  API: 不变——SkillMasteryStore 照样用

中层（章节聚合）:
  ChapterProgressStore.compute_chapter_mastery(chapter_id)
  = 该章所有知识点的观测加权平均
  未观测知识点（observation_count=0）→ 权重 0

顶层（课程进度）:
  CourseProgressTracker.current_chapter + overall_mastery
  用于前端展示，不用于解锁判断
```

### Q2: 观测来源

```
选: LessonCard 练习题为主，诊断探针为兼容路径。

有课程大纲时:
  教练在教学轮中问 LessonCard 的练习题
  学生回答 → agent.act() → 评估正确性 → record_exercise_observation(kp, correct)
  → SkillMasteryStore.update(kp, correct)
  诊断探针暂停（练习题已覆盖）

无课程大纲时:
  回退到现有行为: 诊断探针每 interval_turns 出题
  agent.act() 中 diagnostic_engine.process_turn() 照旧

切换判断:
  session 创建时检查 syllabus 是否存在 → 设置 _use_exercise_path 标志
```

### Q3: 知识传播

```
选: 传播比例不变（gain×0.3），方向从"技能依赖"改为"章节顺序"。

旧版: python_variable +0.1 → python_type +0.03
新版: Ch1 mastery +0.1 → Ch2 每个 kp +0.03 → Ch3 每个 kp +0.009

衰减因子: gain × multiplier^(距离)
  multiplier = 0.3（和旧版一致）
  距离 = 章节 index 差

被否决:
  ❌ 传播到所有后续章节（无衰减）→ 否决: 学到变量对装饰器的帮助很间接
  ❌ 取消传播 → 否决: 保留了旧版设计意图，只是应用范围变了
```

### Q4: 解锁阈值

```
选: 全局默认 0.7，每章可在大纲中覆盖。

解锁条件: 前一章 mastery >= threshold
  且 前一章 ≥ 50% 知识点有 ≥ 2 次观测

不自动重新锁定。mastery 下降 → 显示 ⚠️ 建议复习。

大纲中可覆盖:
  { "chapters": [{"id": "ch1", "mastery_threshold": 0.6}] }
  不指定 → 默认 0.7
```

### Q5: 数据存储

```
选: Phase 78 用 JSON（和 Phase 76 一致策略）。

Phase 78: JsonProgressStore
  data/course_progress/{course_id}/progress.json
  Phase 77 升级 ChromaDB 时替换为 ChromaProgressStore（接口不变）
```

---

## 阶段 2：技术方案

### 阶段 2 元提示词

```
你的任务: 写出 Phase 78 的精确改动清单、完整代码、算法设计。

输入: 阶段 1 的架构决策 + 现有 SkillMasteryStore 代码

输出:
  1. 每个文件的精确代码
  2. 聚合算法
  3. 向后兼容机制
  4. 验证测试方案

自审查:
  □ 不改 SkillMasteryStore API 是否确认？
  □ 无大纲回退是否覆盖？
  □ chapter_graph.json 的生成逻辑是什么？
```

---

### 文件 1（新建）: `src/coach/curriculum/progress.py`

```python
"""章节级 BKT 追踪: 知识点→章节→课程三层架构."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class KPProgress:
    """单个知识点的 BKT 状态."""
    mastery: float = 0.3       # P(learned)
    observations: int = 0       # 观测次数
    correct_count: int = 0      # 正确次数
    last_observed: str = ""     # ISO timestamp


@dataclass
class ChapterProgress:
    """章节掌握度."""
    chapter_id: str
    mastery: float = 0.3
    knowledge_points: dict[str, KPProgress] = field(default_factory=dict)
    unlocked: bool = False
    completed: bool = False
    completed_at: str = ""
    threshold: float = 0.7


@dataclass
class CourseProgress:
    """课程整体进度."""
    course_id: str
    chapters: dict[str, ChapterProgress] = field(default_factory=dict)
    overall_mastery: float = 0.3
    current_chapter: str = ""
    total_observations: int = 0


class ChapterProgressStore:
    """章节进度存储 + 聚合 + 解锁。兼容旧版 SkillMasteryStore。"""

    def __init__(self, course_id: str, syllabus: dict | None = None,
                 base_dir: str | None = None):
        self.course_id = course_id
        self.syllabus = syllabus
        self._progress = CourseProgress(course_id=course_id)

        if base_dir is None:
            base_dir = str(
                Path(__file__).resolve().parent.parent.parent.parent
                / "data" / "course_progress"
            )
        self._base = Path(base_dir)
        self._path = self._base / f"{course_id}.json"

        # 初始化章节结构
        if syllabus:
            self._init_chapters(syllabus)

        # 尝试加载已有进度
        self._load()

    # ── 初始化 ──

    def _init_chapters(self, syllabus: dict) -> None:
        for ch in syllabus.get("chapters", []):
            ch_id = ch["id"]
            cp = ChapterProgress(
                chapter_id=ch_id,
                unlocked=(ch_id == "ch1"),  # 第一章默认解锁
                threshold=ch.get("mastery_threshold", 0.7),
            )
            for section in ch.get("sections", []):
                for kp_name in section.get("knowledge_points", []):
                    cp.knowledge_points[kp_name] = KPProgress()
            self._progress.chapters[ch_id] = cp
        if self._progress.chapters:
            self._progress.current_chapter = "ch1"

    # ── 观测记录 ──

    def record_observation(self, knowledge_point: str, correct: bool,
                           chapter_id: str = "") -> None:
        """记录一次知识点观测，更新 mastery，传播到后续章节。"""
        if not chapter_id:
            chapter_id = self._find_chapter(knowledge_point)

        ch = self._progress.chapters.get(chapter_id)
        if not ch:
            return

        kp = ch.knowledge_points.get(knowledge_point)
        if not kp:
            kp = KPProgress()
            ch.knowledge_points[knowledge_point] = kp

        # 简单 BKT 更新（贝叶斯公式近似，保持和旧版一致）
        prior = kp.mastery
        if correct:
            posterior = prior + (1 - prior) * 0.2  # learn rate
        else:
            posterior = prior * (1 - 0.1)           # slip rate

        kp.mastery = max(0.01, min(0.99, posterior))
        kp.observations += 1
        if correct:
            kp.correct_count += 1
        kp.last_observed = _now_iso()
        self._progress.total_observations += 1

        # 重新计算章节 mastery
        old_ch_mastery = ch.mastery
        ch.mastery = self._compute_chapter_mastery(chapter_id)

        # 知识传播：章节 mastery 变化 → 传播到后续章节
        if chapter_id and old_ch_mastery > 0:
            gain = ch.mastery - old_ch_mastery
            if gain > 0:
                self._propagate(chapter_id, gain)

        # 检查解锁
        self._check_unlock()

        self._save()

    # ── 聚合 ──

    def _compute_chapter_mastery(self, chapter_id: str) -> float:
        """章节 mastery = 该章所有知识点的观测加权平均。"""
        ch = self._progress.chapters.get(chapter_id)
        if not ch:
            return 0.3
        total_w = 0.0
        weighted = 0.0
        for kp in ch.knowledge_points.values():
            w = min(kp.observations, 5)  # 饱和权重（≥5次观测后不再增加权重）
            weighted += kp.mastery * w
            total_w += w
        if total_w == 0:
            return 0.3
        return round(weighted / total_w, 4)

    # ── 知识传播 ──

    def _propagate(self, from_chapter_id: str, gain: float) -> None:
        """章节 mastery 提升后，按 0.3×距离衰减传播到后续章节。"""
        chapters = list(self._progress.chapters.keys())
        try:
            from_idx = chapters.index(from_chapter_id)
        except ValueError:
            return
        for dist in range(1, len(chapters) - from_idx):
            target_id = chapters[from_idx + dist]
            ch = self._progress.chapters[target_id]
            multiplier = 0.3 ** dist
            boost = gain * multiplier
            if boost < 0.001:
                break
            for kp in ch.knowledge_points.values():
                kp.mastery = min(0.99, kp.mastery + boost)

    # ── 解锁 ──

    def _check_unlock(self) -> None:
        """检查前一章是否达到阈值 → 解锁下一章。"""
        chapters = list(self._progress.chapters.keys())
        for i, ch_id in enumerate(chapters):
            ch = self._progress.chapters[ch_id]
            if ch.unlocked and not ch.completed:
                # 检查是否完成
                observed_kps = sum(1 for kp in ch.knowledge_points.values() if kp.observations >= 2)
                total_kps = max(len(ch.knowledge_points), 1)
                if ch.mastery >= ch.threshold and observed_kps / total_kps >= 0.5:
                    ch.completed = True
                    ch.completed_at = _now_iso()
                    # 解锁下一章
                    if i + 1 < len(chapters):
                        next_id = chapters[i + 1]
                        self._progress.chapters[next_id].unlocked = True
                        self._progress.current_chapter = next_id

    # ── 查询 ──

    def get_chapter_mastery(self, chapter_id: str) -> float:
        ch = self._progress.chapters.get(chapter_id)
        return ch.mastery if ch else 0.3

    def get_kp_mastery(self, kp_name: str, chapter_id: str = "") -> float:
        if chapter_id:
            ch = self._progress.chapters.get(chapter_id)
            if ch:
                kp = ch.knowledge_points.get(kp_name)
                return kp.mastery if kp else 0.3
        for ch in self._progress.chapters.values():
            kp = ch.knowledge_points.get(kp_name)
            if kp:
                return kp.mastery
        return 0.3

    def get_all_kp_masteries(self) -> dict[str, float]:
        result = {}
        for ch in self._progress.chapters.values():
            for name, kp in ch.knowledge_points.items():
                result[name] = kp.mastery
        return result

    def is_chapter_unlocked(self, chapter_id: str) -> bool:
        ch = self._progress.chapters.get(chapter_id)
        return ch.unlocked if ch else False

    def to_dict(self) -> dict:
        return {
            "course_id": self._progress.course_id,
            "current_chapter": self._progress.current_chapter,
            "overall_mastery": self._progress.overall_mastery,
            "total_observations": self._progress.total_observations,
            "chapters": {
                cid: {
                    "mastery": ch.mastery,
                    "unlocked": ch.unlocked,
                    "completed": ch.completed,
                    "threshold": ch.threshold,
                    "knowledge_points": {
                        n: {"mastery": kp.mastery, "observations": kp.observations,
                            "correct": kp.correct_count}
                        for n, kp in ch.knowledge_points.items()
                    }
                }
                for cid, ch in self._progress.chapters.items()
            }
        }

    # ── 持久化 ──

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            for cid, cd in data.get("chapters", {}).items():
                if cid in self._progress.chapters:
                    ch = self._progress.chapters[cid]
                    ch.mastery = cd.get("mastery", 0.3)
                    ch.unlocked = cd.get("unlocked", cid == "ch1")
                    ch.completed = cd.get("completed", False)
                    for n, kd in cd.get("knowledge_points", {}).items():
                        if n in ch.knowledge_points:
                            ch.knowledge_points[n].mastery = kd.get("mastery", 0.3)
                            ch.knowledge_points[n].observations = kd.get("observations", 0)
                            ch.knowledge_points[n].correct_count = kd.get("correct", 0)
            self._progress.current_chapter = data.get("current_chapter", "ch1")
            self._progress.total_observations = data.get("total_observations", 0)
        except Exception:
            pass

    def _find_chapter(self, kp_name: str) -> str:
        for cid, ch in self._progress.chapters.items():
            if kp_name in ch.knowledge_points:
                return cid
        return ""


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
```

---

## 阶段 3：交互审查 + 回归风险

### 阶段 3 元提示词

```
你的任务: 审查 Phase 78 的改动对现有系统的影响。

输入: 阶段 2 的 progress.py + 现有 SkillMasteryStore

审查对象:
  1. SkillMasteryStore — 是否受影响？
  2. diagnostic_engine — 诊断探针是否受影响？
  3. 教学管线 — BKT 章节化是否阻塞 act()？
  4. 旧版兼容 — 无大纲时是否完全回退？
  5. 测试基线 — 新增模块是否影响 1466 测试？

输出: 回归风险矩阵 + 防范措施
```

### 回归风险矩阵

| 风险 | 概率 | 影响 | 防范 |
|------|------|------|------|
| SkillMasteryStore API 被修改 | 无 | 无 | progress.py 是独立模块，不引用 SkillMasteryStore |
| 无大纲时 BKT 回退失败 | 低 | 中 | ChapterProgressStore(syllabus=None) → 所有查询返回 prior 0.3 |
| 章节解锁过快（阈值太低） | 低 | 低 | 默认 0.7 + 50% 知识点需 ≥2 次观测 |
| 传播使后续章节 mastery 虚高 | 低 | 低 | multiplier 0.3×距离衰减迅速 |
| 现有测试受影响 | 无 | 无 | 新增模块，不修改现有文件 |
| JSON 存储文件损坏 | 低 | 低 | _load() 异常吞掉 → 从零开始（prior） |

### 不影响的部分

```
✅ SkillMasteryStore — 不修改
✅ diagnostic_engine — 不修改
✅ skill_graph.json — 不修改
✅ CoachAgent.act() — BKT 观测在 act() 之后异步记录，不阻塞主流程
✅ 现有测试 — 新增模块，不影响 1466 测试
```

---

## 四、验证测试

```python
# 手动验证
from src.coach.curriculum.progress import ChapterProgressStore

# 模拟大纲
syllabus = {
    "chapters": [
        {"id": "ch1", "sections": [
            {"knowledge_points": ["variable_def", "assignment"]}
        ]},
        {"id": "ch2", "sections": [
            {"knowledge_points": ["print_func", "input_func"]}
        ]},
    ]
}

store = ChapterProgressStore("test_course", syllabus)

# Ch1 默认解锁
assert store.is_chapter_unlocked("ch1")
assert not store.is_chapter_unlocked("ch2")

# 记录观测
store.record_observation("variable_def", True, "ch1")
store.record_observation("variable_def", True, "ch1")
store.record_observation("assignment", True, "ch1")

# Ch1 mastery 应该上升
ch1_m = store.get_chapter_mastery("ch1")
assert ch1_m > 0.3  # 有观测后应该比 prior 高

print(f"Ch1 mastery: {ch1_m}")
print(f"Ch1 unlocked: {store.is_chapter_unlocked('ch1')}")
print(f"Ch2 unlocked: {store.is_chapter_unlocked('ch2')}")
```

### 验证检查点

```
□ ChapterProgressStore(syllabus) → 章节结构初始化
□ record_observation() → mastery 上升
□ 无大纲时回退（syllabus=None → 所有查询返回 0.3）
□ 章节 completion → 解锁下一章
□ 知识传播 → 检查后续章节 mastery 是否有 boosting
□ JSON 持久化 → _save/_load 往返无丢失
□ 现有测试 1466 passed
```

---

## 五、实施清单

```
1. [新建] src/coach/curriculum/progress.py
2. [验证] 手动运行验证测试
3. [验证] python -m pytest tests/ -q → 1466 passed
```
