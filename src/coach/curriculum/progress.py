"""章节级 BKT 追踪: 知识点→章节→课程三层架构."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class KPProgress:
    mastery: float = 0.3
    observations: int = 0
    correct_count: int = 0
    last_observed: str = ""


@dataclass
class ChapterProgress:
    chapter_id: str
    mastery: float = 0.3
    knowledge_points: dict[str, KPProgress] = field(default_factory=dict)
    unlocked: bool = False
    completed: bool = False
    completed_at: str = ""
    threshold: float = 0.7


@dataclass
class CourseProgress:
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

        if syllabus:
            self._init_chapters(syllabus)

        self._load()

    def _init_chapters(self, syllabus: dict) -> None:
        for ch in syllabus.get("chapters", []):
            ch_id = ch["id"]
            cp = ChapterProgress(
                chapter_id=ch_id,
                unlocked=(ch_id == "ch1"),
                threshold=ch.get("mastery_threshold", 0.7),
            )
            for section in ch.get("sections", []):
                for kp_name in section.get("knowledge_points", []):
                    cp.knowledge_points[kp_name] = KPProgress()
            self._progress.chapters[ch_id] = cp
        if self._progress.chapters:
            self._progress.current_chapter = "ch1"

    def record_observation(self, knowledge_point: str, correct: bool,
                           chapter_id: str = "") -> None:
        if not chapter_id:
            chapter_id = self._find_chapter(knowledge_point)

        ch = self._progress.chapters.get(chapter_id)
        if not ch:
            return

        kp = ch.knowledge_points.get(knowledge_point)
        if not kp:
            kp = KPProgress()
            ch.knowledge_points[knowledge_point] = kp

        prior = kp.mastery
        if correct:
            posterior = prior + (1 - prior) * 0.2
        else:
            posterior = prior * (1 - 0.1)

        kp.mastery = max(0.01, min(0.99, posterior))
        kp.observations += 1
        if correct:
            kp.correct_count += 1
        kp.last_observed = _now_iso()
        self._progress.total_observations += 1

        old_ch_mastery = ch.mastery
        ch.mastery = self._compute_chapter_mastery(chapter_id)

        if chapter_id and old_ch_mastery > 0:
            gain = ch.mastery - old_ch_mastery
            if gain > 0:
                self._propagate(chapter_id, gain)

        self._check_unlock()
        self._save()

    def _compute_chapter_mastery(self, chapter_id: str) -> float:
        ch = self._progress.chapters.get(chapter_id)
        if not ch:
            return 0.3
        total_w = 0.0
        weighted = 0.0
        for kp in ch.knowledge_points.values():
            w = min(kp.observations, 5)
            weighted += kp.mastery * w
            total_w += w
        if total_w == 0:
            return 0.3
        return round(weighted / total_w, 4)

    def _propagate(self, from_chapter_id: str, gain: float) -> None:
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

    def _check_unlock(self) -> None:
        chapters = list(self._progress.chapters.keys())
        for i, ch_id in enumerate(chapters):
            ch = self._progress.chapters[ch_id]
            if ch.unlocked and not ch.completed:
                observed_kps = sum(1 for kp in ch.knowledge_points.values() if kp.observations >= 2)
                total_kps = max(len(ch.knowledge_points), 1)
                if ch.mastery >= ch.threshold and observed_kps / total_kps >= 0.5:
                    ch.completed = True
                    ch.completed_at = _now_iso()
                    if i + 1 < len(chapters):
                        next_id = chapters[i + 1]
                        self._progress.chapters[next_id].unlocked = True
                        self._progress.current_chapter = next_id

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
