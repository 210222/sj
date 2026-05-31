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
    misconceptions: list[str]
    sticking_points: list[str]
    detours: list[str]
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
    grade: str
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
    call4_bias_check: dict = field(default_factory=dict)  # Phase 84: D4 偏差检测结果


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
