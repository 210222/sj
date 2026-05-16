"""Phase 44: LLM 学生代理 — 模拟有知识状态的交互式学习者."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

STUDENT_SYSTEM_PROMPT = """你是一个正在学习中的人类学生。你的学习背景是：{profile_description}。

当前你已经学会的概念（掌握度 0.0=完全不懂，1.0=精通）：
{known_concepts_summary}

教练刚教过但你还不太确定的概念：
{exposed_concepts_summary}

教练上一轮对你说：{last_coach_statement}
上一轮你问的问题是：{last_student_message}

请以真实学生的身份回复教练。你的回复应该：
1. 如果用你自己的话能复述关键点，说明你理解了（但不要完美复述原文）
2. 如果某个概念你之前没搞懂，现在教练的解释让你有所收获，表达出来
3. 如果仍有困惑，诚实说出具体哪里不懂
4. 如果你觉得教练的说法和你之前的理解有矛盾，可以追问
5. 不要假装全懂，不要过度奉承，不要像机器人一样完美回应
6. 回复长度保持在 1-3 句话，像一个真实学生在聊天

只输出学生的回复文本，不要加引号、不要加角色标记。"""


@dataclass
class StudentKnowledgeState:
    known_concepts: dict[str, float] = field(default_factory=dict)
    exposed_concepts: set[str] = field(default_factory=set)
    turn_history: list[dict] = field(default_factory=list)

    def expose(self, concept: str) -> None:
        if concept and concept not in self.known_concepts:
            self.exposed_concepts.add(concept)

    def learn(self, concept: str, gain: float = 0.15) -> float:
        old = self.known_concepts.get(concept, 0.0)
        if concept in self.exposed_concepts:
            self.exposed_concepts.discard(concept)
        new = min(1.0, old + gain)
        self.known_concepts[concept] = new
        return new - old

    def mastery_delta(self, before: dict[str, float]) -> float:
        delta = 0.0
        for concept, after_val in self.known_concepts.items():
            delta += after_val - before.get(concept, 0.0)
        return round(delta, 4)

    def summary(self) -> str:
        if not self.known_concepts:
            return "（新学习者，尚无明确掌握的概念）"
        items = sorted(self.known_concepts.items(), key=lambda x: -x[1])
        return "; ".join(f"{c}({v:.0%})" for c, v in items[:8])


STUDENT_PROFILES: dict[str, dict] = {
    "beginner": {
        "name": "零基础学习者",
        "description": "你对编程完全陌生。你听过 Python 这个词但不知道它是什么。你容易困惑但愿意学习。",
        "known_concepts": {},
        "curiosity": 0.5,
        "confusion_threshold": 0.7,
    },
    "fuzzy_basics": {
        "name": "有基础但模糊",
        "description": "你学过一点编程但概念是模糊的。列表和循环你有点印象但不自信。你喜欢追问细节。",
        "known_concepts": {"变量": 0.3, "列表": 0.2, "循环": 0.15},
        "curiosity": 0.7,
        "confusion_threshold": 0.5,
    },
    "jumpy": {
        "name": "跳跃联想型",
        "description": "你有一些零散的知识碎片，经常把不同话题连在一起。你容易走神但灵感多。",
        "known_concepts": {"变量": 0.4, "函数": 0.1, "条件判断": 0.2},
        "curiosity": 0.9,
        "confusion_threshold": 0.4,
    },
    "passive": {
        "name": "被动确认型",
        "description": "你学习比较被动，倾向于只回复'好''嗯''继续'。你需要教练引导才会追问。",
        "known_concepts": {},
        "curiosity": 0.3,
        "confusion_threshold": 0.9,
    },
}


class StudentAgent:
    """LLM 驱动的学生代理，模拟真实学习者的交互行为."""

    def __init__(self, profile_id: str = "beginner"):
        profile = STUDENT_PROFILES.get(profile_id, STUDENT_PROFILES["beginner"])
        self.profile_id = profile_id
        self.profile = profile
        self.state = StudentKnowledgeState(
            known_concepts=dict(profile.get("known_concepts", {})),
        )
        self._initial_state = dict(self.state.known_concepts)
        self._turn_count = 0
        self._last_coach_statement = ""
        self._last_student_message = ""

    def consume_coach_response(self, coach_response: dict) -> None:
        stmt = str(coach_response.get("payload", {}).get("statement", ""))
        action_type = str(coach_response.get("action_type", ""))
        self._last_coach_statement = stmt[:500]
        extracted = self._extract_concepts(stmt)
        for concept in extracted:
            self.state.expose(concept)
        self.state.turn_history.append({
            "turn": self._turn_count,
            "coach_statement": stmt[:200],
            "action_type": action_type,
        })
        self._turn_count += 1

    def generate_response(self, llm_client, llm_config) -> str:
        from src.coach.llm.client import LLMClient
        client = llm_client or LLMClient(llm_config)
        system = STUDENT_SYSTEM_PROMPT.format(
            profile_description=self.profile["description"],
            known_concepts_summary=self.state.summary(),
            exposed_concepts_summary="; ".join(self.state.exposed_concepts)[:300] or "（暂无）",
            last_coach_statement=self._last_coach_statement[:400] or "（刚开始对话）",
            last_student_message=self._last_student_message or "（刚开始对话）",
        )
        ctx = {"system": system, "user_message": "请以学生的身份回复教练", "action_type": "suggest"}
        response = client.generate(ctx)
        student_msg = response.to_payload().get("statement", "嗯，继续讲吧")[:300]
        self._last_student_message = student_msg

        if any(kw in student_msg for kw in ["懂了", "明白了", "理解了", "原来如此", "是这样"]):
            for concept in list(self.state.exposed_concepts)[:2]:
                self.state.learn(concept, gain=0.2)
        return student_msg

    def get_mastery_delta(self) -> float:
        return self.state.mastery_delta(self._initial_state)

    def get_effectiveness_summary(self) -> dict:
        return {
            "profile": self.profile_id,
            "turns": self._turn_count,
            "mastery_delta": self.get_mastery_delta(),
            "concepts_learned": len(self.state.known_concepts) - len(self._initial_state),
            "concepts_exposed": len(self.state.exposed_concepts),
            "final_known": self.state.known_concepts,
        }

    @staticmethod
    def _extract_concepts(text: str) -> list[str]:
        concepts = []
        keywords = [
            "变量", "列表", "循环", "函数", "字典", "条件", "字符串",
            "Python", "算法", "递归", "类", "对象", "模块", "包",
            "for", "while", "if", "def", "class", "import",
        ]
        for kw in keywords:
            if kw in text:
                concepts.append(kw)
        return concepts[:5]
