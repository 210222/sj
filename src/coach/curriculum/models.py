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
    knowledge_type: str = ""  # Phase 92: conceptual|procedural|factual

    def validate(self) -> tuple[bool, list[str]]:
        errors = []
        if not self.definition:
            errors.append("definition is empty")

        # Phase 92: 阈值分型
        kt = self.knowledge_type
        thresholds = {
            "conceptual":  (3, 2, 2),
            "unknown":     (2, 1, 1),
            "procedural":  (1, 1, 1),
            "factual":     (2, 1, 0),
        }
        min_mis, min_stick, min_det = thresholds.get(kt, thresholds["unknown"])

        if len(self.misconceptions) < min_mis:
            errors.append(f"misconceptions < {min_mis}: {len(self.misconceptions)}")
        if len(self.sticking_points) < min_stick:
            errors.append(f"sticking_points < {min_stick}: {len(self.sticking_points)}")
        if len(self.detours) < min_det:
            errors.append(f"detours < {min_det}: {len(self.detours)}")
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
    knowledge_type: str = ""  # Phase 92: conceptual|procedural|factual
