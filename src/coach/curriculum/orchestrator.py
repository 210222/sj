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
