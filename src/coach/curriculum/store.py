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
    """Phase 76: JSON 文件存储。Phase 77: Fts5LessonStore, Phase 77.1: ChromaLessonStore 升级。"""

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
