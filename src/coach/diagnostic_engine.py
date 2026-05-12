"""自适应诊断探测引擎 — DiagnosticEngine.

定期生成诊断题 → 分析正确率 → 更新逐技能 BKT 掌握度 → 反馈到 SDT/Flow.
复用现有 LLM 管道 + probe action_type + BKTEngine.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from src.coach.flow import BKTEngine

_logger = logging.getLogger(__name__)

# ── 诊断题 prompt ──────────────────────────────────────────
DIAGNOSTIC_PROBE_PROMPT = """你是自适应教练系统的诊断问题生成器。
目标: 生成一个探测性问题来评估用户在「{skill}」方面的掌握程度。

对话上下文（用户最近的学习内容）:
{conversation_context}

要求:
1. 问题必须与用户最近学习的内容直接相关（参考对话上下文）
2. 提供 expected_answer 字段，描述正确答案的要点（3-5 个关键词或判断标准）
3. 难度: {difficulty}（easy: 概念理解, medium: 应用分析, hard: 综合评估）
4. JSON 格式输出，包含: statement, question, expected_answer, topics
5. 用中文提问，问题要有区分度（不能所有人都能答对）

输出 JSON 示例:
{{
  "statement": "让我检查一下你对这个知识点的掌握情况。",
  "question": "在 Python 中，列表和元组的根本区别是什么？给出一个具体的应用场景。",
  "expected_answer": "列表可变适合动态数据、元组不可变适合常量；列表用[]、元组用()",
  "topics": ["Python 基础", "数据结构"]
}}"""

# ── 答案评估 prompt ───────────────────────────────────────
EVALUATION_PROMPT = """判断用户对诊断问题的回答是否正确。

技能: {skill}
问题: {question}
正确答案要点: {expected_answer}
用户回答: {user_response}

你的任务: 判断用户回答是否基本正确（不必逐字匹配，核心概念正确即可）。
输出 JSON: {{"correct": true/false, "confidence": 0.0-1.0, "reason": "简要理由"}}"""


# ── 数据结构 ───────────────────────────────────────────────

@dataclass
class DiagnosticProbe:
    """一次诊断探测."""
    skill: str
    question: str
    expected_answer: str
    prompt: str = ""            # 完整展示给用户的内容
    timestamp: float = 0.0
    trace_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())
        if not self.prompt:
            self.prompt = self.question


@dataclass
class DiagnosticRecord:
    """一次完整的诊断记录（含用户应答 + 评估结果）."""
    probe: DiagnosticProbe
    user_response: str = ""
    correct: bool = False
    correct_confidence: float = 0.0
    mastery_before: float = 0.0
    mastery_after: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


# ── 技能掌握度存储 ────────────────────────────────────────

class SkillMasteryStore:
    """逐技能的 BKT 掌握度追踪器.

    每技能一个 BKTEngine 实例，支持序列化/反序列化。
    """

    def __init__(self, bkt_params: dict | None = None):
        self._bkt_params = deepcopy(bkt_params) or {
            "prior": 0.3, "guess": 0.1, "slip": 0.1, "learn": 0.2,
        }
        self._engines: dict[str, BKTEngine] = {}
        self._mastery: dict[str, float] = {}
        self._observation_count: dict[str, int] = {}  # 每技能观测数

    def _get_engine(self, skill: str) -> BKTEngine:
        if skill not in self._engines:
            self._engines[skill] = BKTEngine(**self._bkt_params)
            self._mastery[skill] = self._bkt_params["prior"]
            self._observation_count[skill] = 0
        return self._engines[skill]

    def update(self, skill: str, correct: bool, skill_graph: "SkillGraph | None" = None) -> float:
        """记录一次观测，返回更新后的 P(learned).

        Phase 30: 知识传播 —— 掌握度提升后按 30% 比例传播到依赖此技能的子技能。
        """
        engine = self._get_engine(skill)
        obs = 1 if correct else 0
        probs = engine.predict([obs])
        new_mastery = probs[-1]
        old_mastery = self._mastery.get(skill, 0.3)
        gain = new_mastery - old_mastery
        self._mastery[skill] = new_mastery
        self._observation_count[skill] = self._observation_count.get(skill, 0) + 1

        # Phase 30: 知识图谱传播
        if skill_graph and gain > 0:
            boosts = skill_graph.propagate(skill, gain, self._mastery)
            for dep_skill, new_val in boosts.items():
                old = self._mastery.get(dep_skill, 0.3)
                if new_val > old:
                    self._mastery[dep_skill] = new_val

        return new_mastery

    def get_mastery(self, skill: str) -> float:
        """获取指定技能的 P(learned)."""
        return self._mastery.get(skill, self._bkt_params["prior"])

    def get_all_masteries(self) -> dict[str, float]:
        """返回全部技能的掌握度."""
        return dict(self._mastery)

    def get_low_mastery(self, threshold: float = 0.3) -> list[str]:
        """返回掌握度低于阈值的技能列表."""
        return [
            s for s, m in self._mastery.items()
            if m < threshold
        ]

    def get_untested_skills(self) -> list[str]:
        """返回仅有 1 次观测的技能（不稳定的新技能）."""
        return [
            s for s, c in self._observation_count.items()
            if c <= 1
        ]

    @property
    def total_skills(self) -> int:
        return len(self._engines)

    def to_dict(self) -> dict:
        """序列化 —— 用于跨会话持久化."""
        return {
            "bkt_params": dict(self._bkt_params),
            "mastery": dict(self._mastery),
            "observation_count": dict(self._observation_count),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SkillMasteryStore:
        store = cls(bkt_params=data.get("bkt_params"))
        # 反序列化时重建引擎（只需要 mastery 即可，BKT 纯函数式）
        store._mastery = dict(data.get("mastery", {}))
        store._observation_count = dict(data.get("observation_count", {}))
        total_observations = sum(store._observation_count.values())
        # 只按需创建引擎（在 update 时懒加载）
        _logger.info(
            "SkillMasteryStore restored: %d skills, %d total observations",
            len(store._mastery), total_observations,
        )
        return store


# ── 诊断引擎主类 ──────────────────────────────────────────

class DiagnosticEngine:
    """自适应诊断探测引擎.

    职责:
    1. process_turn() — 每次对话轮次开始时的处理（评估 pending probe）
    2. should_and_generate() — 判断是否该出题并生成诊断题
    3. 更新 SkillMasteryStore → 反馈到 SDT/Flow
    """

    def __init__(self, config: dict | None = None):
        self._cfg = config or {}
        self._store = SkillMasteryStore(
            bkt_params=self._cfg.get("bkt"),
        )
        self._pending_probe: DiagnosticProbe | None = None
        self._history: list[DiagnosticRecord] = []
        self._probe_count: int = 0

        self._interval = self._cfg.get("interval_turns", 5)
        self._last_diagnose_turn: int = -(self._interval)  # turn 0 不阻塞

        self._min_confidence = self._cfg.get("min_confidence", 0.3)
        self._max_probes = self._cfg.get("max_probes_per_session", 3)
        self._default_difficulty = self._cfg.get("difficulty_default", "medium")
        self._llm_evaluation = self._cfg.get("llm_evaluation", True)

    # ── 属性 ──

    @property
    def enabled(self) -> bool:
        return self._cfg.get("enabled", False)

    @property
    def is_pending(self) -> bool:
        return self._pending_probe is not None

    @property
    def store(self) -> SkillMasteryStore:
        return self._store

    @property
    def probe_count(self) -> int:
        return self._probe_count

    # ── 外部接口 ──

    def process_turn(
        self,
        user_input: str,
        turn_count: int,
        llm_client: Any = None,
    ) -> dict | None:
        """处理一次对话轮次（评估 pending probe、触发新一轮决策）.

        返回 dict（有评估结果时）或 None.
        """
        if not self.enabled:
            return None

        # 只评估，不生成（生成由 should_and_generate 负责）
        if self._pending_probe is None:
            return None

        probe = self._pending_probe
        self._pending_probe = None  # 消费掉 pending

        # 评估
        mastery_before = self._store.get_mastery(probe.skill)
        correct, confidence = self._evaluate(
            skill=probe.skill,
            question=probe.question,
            expected=probe.expected_answer,
            response=user_input,
            llm_client=llm_client,
        )

        # 低置信度 → 丢弃
        if confidence < 0.5:
            _logger.info(
                "Diagnostic evaluation discarded (confidence=%.2f): skill=%s",
                confidence, probe.skill,
            )
            return {
                "skill": probe.skill,
                "evaluated": False,
                "reason": "low_confidence",
                "mastery": mastery_before,
            }

        # 更新 BKT
        mastery_after = self._store.update(probe.skill, correct)

        # 记录
        record = DiagnosticRecord(
            probe=probe,
            user_response=user_input,
            correct=correct,
            correct_confidence=confidence,
            mastery_before=mastery_before,
            mastery_after=mastery_after,
        )
        self._history.append(record)

        _logger.info(
            "Diagnostic: skill=%s correct=%s mastery=%.3f→%.3f",
            probe.skill, correct, mastery_before, mastery_after,
        )

        return {
            "skill": probe.skill,
            "evaluated": True,
            "correct": correct,
            "confidence": confidence,
            "mastery_before": mastery_before,
            "mastery_after": mastery_after,
        }

    def should_and_generate(
        self,
        turn_count: int,
        covered_topics: list[str] | None = None,
        llm_client: Any = None,
        intent: str = "general",
    ) -> dict | None:
        """判断是否该出题；若是，生成诊断题并返回 dict.

        返回格式: {"question": ..., "skill": ..., "expected_answer": ...}
        """
        if not self.enabled:
            return None

        # 有 pending 先等答复
        if self._pending_probe is not None:
            return None

        # 已达上限
        if self._probe_count >= self._max_probes:
            return None

        # 检查间隔
        turns_since_last = turn_count - self._last_diagnose_turn
        if turns_since_last < self._interval:
            return None

        # 候选技能
        skill = self._select_candidate_skill(covered_topics, intent)
        if skill is None:
            return None

        # 生成诊断题
        difficulty = self._get_difficulty(skill)
        probe_dict = self._generate_probe(skill, difficulty, llm_client)
        if probe_dict is None:
            return None

        self._pending_probe = DiagnosticProbe(
            skill=skill,
            question=probe_dict.get("question", ""),
            expected_answer=probe_dict.get("expected_answer", ""),
            prompt=probe_dict.get("statement", "") + "\n\n" + probe_dict.get("question", ""),
        )
        self._probe_count += 1
        self._last_diagnose_turn = turn_count

        _logger.info("Diagnostic probe generated: skill=%s", skill)

        return {
            "question": self._pending_probe.question,
            "skill": self._pending_probe.skill,
            "expected_answer": self._pending_probe.expected_answer,
        }

    def get_mastery_summary(self) -> dict:
        """返回当前掌握度概览，供 SDT/Flow 消费."""
        return {
            "skills": self._store.get_all_masteries(),
            "low_mastery": self._store.get_low_mastery(self._min_confidence),
            "total_probes": self._probe_count,
            "recent_history": [
                {
                    "skill": r.probe.skill,
                    "correct": r.correct,
                    "mastery_before": r.mastery_before,
                    "mastery_after": r.mastery_after,
                }
                for r in self._history[-5:]
            ],
        }

    def get_competence_signal(self) -> float | None:
        """返回最近一次诊断的correct率，用于 SDT competence 更新."""
        if not self._history:
            return None
        recent = self._history[-1]
        return 1.0 if recent.correct else 0.0

    # ── 内部方法 ──

    def _select_candidate_skill(
        self,
        covered_topics: list[str] | None = None,
        intent: str = "general",
    ) -> str | None:
        """选择要探测的技能.

        优先级:
        1. 已追踪但掌握度低 (< min_confidence) 的技能
        2. covered_topics 中尚未测试过的 topic
        3. 兜底: intent
        """
        low = self._store.get_low_mastery(self._min_confidence)
        if low:
            return low[0]

        if covered_topics:
            # 找 covered_topics 中未测试的
            tested = set(self._store.get_all_masteries().keys())
            for topic in covered_topics:
                if topic not in tested:
                    return topic

            # 全部测过 → 选掌握度最低的覆盖 topic
            topic_masteries = {
                t: self._store.get_mastery(t)
                for t in covered_topics
            }
            if topic_masteries:
                return min(topic_masteries, key=topic_masteries.get)

        # 兜底: intent 作为 skill，包括 "general"（通用诊断题）
        if intent:
            return intent
        return "general_problem_solving"

    def _get_difficulty(self, skill: str) -> str:
        """根据技能当前掌握度选择难度."""
        mastery = self._store.get_mastery(skill)
        if mastery < 0.3:
            return "easy"
        elif mastery < 0.6:
            return "medium"
        else:
            return "hard"

    def _generate_probe(
        self,
        skill: str,
        difficulty: str,
        llm_client: Any = None,
    ) -> dict | None:
        """用 LLM 生成诊断题."""
        if llm_client is None:
            return self._fallback_probe(skill, difficulty)

        # 构建对话上下文摘要
        conv_summary = "（无对话历史）"
        if self._history:
            recent = self._history[-3:]
            conv_summary = "; ".join(
                f"Q: {r.probe.question[:60]} A: {r.user_response[:60]}"
                for r in recent)

        prompt = DIAGNOSTIC_PROBE_PROMPT.format(
            skill=skill,
            difficulty=difficulty,
            conversation_context=conv_summary,
        )
        context = {
            "system": prompt,
            "user_message": f"请针对「{skill}」生成一道难度为 {difficulty} 的诊断题。",
            "action_type": "probe",
        }

        try:
            resp = llm_client.generate(context)
            payload = resp.to_payload()
            if not isinstance(payload, dict):
                raise ValueError(f"LLM returned non-dict: {type(payload)}")
            return {
                "question": payload.get("question", payload.get("statement", "")),
                "expected_answer": payload.get("expected_answer", ""),
                "statement": payload.get("statement", ""),
            }
        except Exception as e:
            _logger.warning("LLM probe generation failed: %s", e)
            return self._fallback_probe(skill, difficulty)

    def _fallback_probe(self, skill: str, difficulty: str) -> dict | None:
        """从 FallbackEngine 获取诊断题，匹配不到时用通用兜底."""
        # Phase 13: 尝试从 FallbackEngine 获取结构化诊断题
        try:
            from src.coach.fallback import FallbackEngine, _detect_topic
            topic = _detect_topic(skill)
            if topic:
                engine = FallbackEngine()
                payload = engine.generate("probe", skill)
                q = payload.get("question", "")
                expected = payload.get("expected_answer", "")
                if q and q != "{}":
                    return {
                        "question": q,
                        "expected_answer": expected or f"{skill}的核心概念和应用",
                        "statement": payload.get("statement", ""),
                    }
        except Exception:
            pass

        # 通用兜底
        templates = {
            "easy": {
                "question": f"请简要说明{skill}是什么，并举一个具体例子。",
                "expected_answer": f"{skill}的基本定义 + 一个正确示例",
            },
            "medium": {
                "question": f"请描述{skill}的核心原理和典型使用场景。",
                "expected_answer": f"{skill}的核心原理和至少一个应用场景",
            },
            "hard": {
                "question": f"请解释「{skill}」的高级用法或与其他概念的关联。",
                "expected_answer": f"{skill}的高级特性或关联概念",
            },
        }
        tpl = templates.get(difficulty, templates["medium"])
        return {
            "question": tpl["question"],
            "expected_answer": tpl["expected_answer"],
        }

    def _evaluate(
        self,
        skill: str,
        question: str,
        expected: str,
        response: str,
        llm_client: Any = None,
    ) -> tuple[bool, float]:
        """评估用户回答是否正确.

        Returns:
            (correct: bool, confidence: float)
        """
        if not response or not response.strip():
            return False, 0.0

        if self._llm_evaluation and llm_client is not None:
            return self._llm_evaluate(skill, question, expected, response, llm_client)
        return self._keyword_evaluate(response, expected)

    def _llm_evaluate(
        self,
        skill: str,
        question: str,
        expected: str,
        response: str,
        llm_client: Any,
    ) -> tuple[bool, float]:
        """用 LLM 评估回答."""
        prompt = EVALUATION_PROMPT.format(
            skill=skill,
            question=question,
            expected_answer=expected,
            user_response=response,
        )
        context = {
            "system": prompt,
            "user_message": f"请判断用户对「{skill}」问题的回答是否正确。",
            "action_type": "probe",
            "intent": "diagnostic",
        }
        try:
            resp = llm_client.generate(context)
            payload = resp.to_payload()
            correct = bool(payload.get("correct", False))
            confidence = float(payload.get("confidence", 0.5))
            return correct, min(confidence, 1.0)
        except Exception as e:
            _logger.warning("LLM evaluation failed, fallback to keyword: %s", e)
            return self._keyword_evaluate(response, expected)

    def _keyword_evaluate(self, response: str, expected: str) -> tuple[bool, float]:
        """关键词匹配兜底评估."""
        if not expected:
            return False, 0.3

        response_lower = response.lower()
        keywords = expected.lower().replace("，", ",").replace("、", ",").split(",")
        keywords = [k.strip() for k in keywords if len(k.strip()) > 1]

        if not keywords:
            return True, 0.4  # 无关键词可匹配，保守给 False

        matched = sum(1 for k in keywords if k in response_lower)
        ratio = matched / len(keywords)

        if ratio >= 0.5:
            return True, min(0.5 + ratio * 0.3, 0.8)
        return False, max(0.3, ratio * 0.5)


# ── Phase 30: 技能知识图谱 ──────────────────────────────────

class SkillGraph:
    """技能依赖关系图谱.

    加载 JSON DAG, 提供前置查询和知识传播。
    """

    def __init__(self, graph_path: str | None = None):
        import json as _json
        from pathlib import Path as _Path
        path = graph_path or str(_Path(__file__).resolve().parent.parent.parent / "config" / "skill_graph.json")
        self._graph: dict[str, dict] = {}
        try:
            p = _Path(path)
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    self._graph = _json.load(f)
        except Exception:
            pass

    def get_prerequisites(self, skill: str) -> list[str]:
        return self._graph.get(skill, {}).get("prerequisites", [])

    def get_related(self, skill: str) -> list[str]:
        return self._graph.get(skill, {}).get("related", [])

    def get_dependents(self, skill: str) -> list[str]:
        """返回依赖此技能的其他技能."""
        return [s for s, info in self._graph.items() if skill in info.get("prerequisites", [])]

    def has_unmastered_prerequisites(self, skill: str, mastery: dict[str, float],
                                      threshold: float = 0.6) -> list[str]:
        """返回 skill 中掌握度低于 threshold 的前置技能."""
        prereqs = self.get_prerequisites(skill)
        return [p for p in prereqs if mastery.get(p, 0) < threshold]

    def propagate(self, skill: str, gain: float, mastery: dict[str, float],
                  rate: float = 0.3) -> dict[str, float]:
        """技能 mastery 提升后, 按 rate 传播到依赖它的子技能."""
        result = {}
        for dep in self.get_dependents(skill):
            old = mastery.get(dep, 0.3)
            boost = gain * rate
            new = min(1.0, old + boost)
            if new != old:
                result[dep] = new
        return result
