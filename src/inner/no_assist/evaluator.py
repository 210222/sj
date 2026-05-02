"""Step 5: No-Assist 独立作答评估器 — 规则法版。

输入用户答案 + 可选的参考答案，基于文本质量、推理痕迹、
辅助使用标记等启发式规则产出 [0,1] 评分与等级分类。
"""

import re
import uuid
from datetime import datetime, timezone

from src.inner.clock import get_window_30min

from .config import (
    SCORE_THRESHOLD_INDEPENDENT,
    SCORE_THRESHOLD_PARTIAL,
    ASSIST_USED_SCORE_CAP,
    MIN_ANSWER_LENGTH,
    LENGTH_PENALTY_FACTOR,
    EMPTY_ANSWER_SCORE,
    TEMPLATE_PATTERNS,
    REASONING_KEYWORDS,
    REASONING_BONUS_PER_HIT,
    REASONING_BONUS_MAX,
    REF_SIMILARITY_WEIGHT,
    REF_OVERLAP_THRESHOLD_HIGH,
    REF_OVERLAP_THRESHOLD_LOW,
    RULE_VERSION,
)

_WORD_RE = re.compile(r"\b[a-zA-Z]{2,}\b")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


class NoAssistEvaluator:
    """No-Assist 独立作答评估器。

    输入一轮作答数据，输出标准化评分、等级和可审计字段。
    """

    RULE_VERSION = RULE_VERSION

    def evaluate(
        self,
        session_id: str,
        user_answer: str,
        assist_used: bool,
        event_time_utc: str,
        reference_answer: str | None = None,
        context: dict | None = None,
    ) -> dict:
        """评估作答独立性。

        Returns:
            {"session_id": str,
             "no_assist_score": float [0,1],
             "no_assist_level": "independent"|"partial"|"dependent",
             "evidence": dict,
             "rule_version": str,
             "reason_code": str,
             "event_time_utc": str,
             "window_id": str,
             "evaluated_at_utc": str}
        """
        # ── 输入校验 ────────────────────────────────────────────
        if not isinstance(session_id, str) or not session_id:
            raise TypeError("session_id must be a non-empty string")
        if not isinstance(user_answer, str):
            raise TypeError("user_answer must be a string")
        if not isinstance(assist_used, bool):
            raise TypeError("assist_used must be a bool")
        if not isinstance(event_time_utc, str) or not event_time_utc:
            raise ValueError("event_time_utc must be a non-empty string")
        if reference_answer is not None and not isinstance(
            reference_answer, str
        ):
            raise TypeError("reference_answer must be str or None")

        # ── 计算分数 ────────────────────────────────────────────
        score = self._compute_score(user_answer, assist_used,
                                     reference_answer)

        # ── 等级映射 ────────────────────────────────────────────
        if score >= SCORE_THRESHOLD_INDEPENDENT:
            level = "independent"
        elif score >= SCORE_THRESHOLD_PARTIAL:
            level = "partial"
        else:
            level = "dependent"

        # ── 证据包 ──────────────────────────────────────────────
        evidence = self._build_evidence(
            user_answer, assist_used, reference_answer, score
        )

        # ── reason_code ─────────────────────────────────────────
        reason_code = (
            f"NA_{'I' if level == 'independent' else 'P' if level == 'partial' else 'D'}"
            f"_{RULE_VERSION}_s{int(score * 100):02d}"
        )

        # ── 时间 ────────────────────────────────────────────────
        evaluated_at = (
            datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z"
        )
        window_id = get_window_30min(event_time_utc)

        return {
            "session_id": session_id,
            "no_assist_score": score,
            "no_assist_level": level,
            "evidence": evidence,
            "rule_version": self.RULE_VERSION,
            "reason_code": reason_code,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": evaluated_at,
        }

    # ── 审计映射 ────────────────────────────────────────────────

    def to_audit_fields(self, result: dict) -> dict:
        """将评估结果映射为可供 ledger/audit 消费的字段。"""
        return {
            "no_assist_score": result["no_assist_score"],
            "no_assist_level": result["no_assist_level"],
            "no_assist_reason_code": result["reason_code"],
            "no_assist_rule_version": result["rule_version"],
        }

    # ── 内部评分逻辑 ────────────────────────────────────────────

    def _compute_score(
        self,
        answer: str,
        assist_used: bool,
        reference: str | None,
    ) -> float:
        """规则法评分子系统。"""
        stripped = answer.strip()

        # 空答案
        if not stripped:
            score = EMPTY_ANSWER_SCORE
            return self._clamp_and_cap(score, assist_used)

        # 1) 文本质量基础分
        base = self._text_quality_score(stripped)

        # 2) 推理痕迹加分
        reasoning_bonus = self._reasoning_bonus(stripped)
        base += reasoning_bonus

        # 3) reference 相似度（如有）
        if reference:
            ref_bonus = self._reference_overlap(stripped, reference)
            base = base * (1 - REF_SIMILARITY_WEIGHT) + ref_bonus * REF_SIMILARITY_WEIGHT

        return self._clamp_and_cap(base, assist_used)

    def _text_quality_score(self, text: str) -> float:
        """文本质量评分 [0,1]。"""
        score = 0.6  # 默认中等起点

        # 长度检查
        word_count = len(_WORD_RE.findall(text.lower()))
        if word_count < MIN_ANSWER_LENGTH:
            score *= LENGTH_PENALTY_FACTOR  # 0.6 → 0.18
        elif word_count >= 30:
            score = min(1.0, score + 0.15)

        # 模板化检测
        text_lower = text.lower()
        for pattern in TEMPLATE_PATTERNS:
            if pattern in text_lower:
                score = max(0.0, score - 0.3)
                break  # 一次命中即扣分，不累加

        return max(0.0, min(1.0, score))

    def _reasoning_bonus(self, text: str) -> float:
        """推理痕迹检测加分。"""
        text_lower = text.lower()
        hits = sum(1 for kw in REASONING_KEYWORDS if kw in text_lower)
        bonus = min(hits * REASONING_BONUS_PER_HIT, REASONING_BONUS_MAX)
        return bonus

    def _reference_overlap(self, answer: str, reference: str) -> float:
        """轻量级词汇重叠度 [0,1]（纯 Python，无重依赖）。"""
        ans_tokens = _tokenize(answer)
        ref_tokens = _tokenize(reference)
        if not ref_tokens:
            return 0.5  # 参考答案无有效词 → 中性

        overlap = len(ans_tokens & ref_tokens)
        ratio = overlap / len(ref_tokens)

        # 非线性映射：低重叠惩罚，高重叠奖励
        if ratio > REF_OVERLAP_THRESHOLD_HIGH:
            return 0.8
        elif ratio < REF_OVERLAP_THRESHOLD_LOW:
            return 0.2
        else:
            return 0.5

    @staticmethod
    def _clamp_and_cap(score: float, assist_used: bool) -> float:
        """夹紧 + assist_used 上限约束。"""
        score = max(0.0, min(1.0, round(score, 4)))
        if assist_used and score > ASSIST_USED_SCORE_CAP:
            score = ASSIST_USED_SCORE_CAP
        return score

    @staticmethod
    def _build_evidence(
        answer: str,
        assist_used: bool,
        reference: str | None,
        score: float,
    ) -> dict:
        word_count = len(_WORD_RE.findall(answer.lower()))
        return {
            "word_count": word_count,
            "assist_used": assist_used,
            "reference_provided": reference is not None,
            "answer_length_chars": len(answer.strip()),
            "empty_answer": not bool(answer.strip()),
            "raw_score_before_cap": round(score, 4),
        }
