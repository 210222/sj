"""S8.1 审计分级门禁 (Audit Gate) — gate 6 运行时实现。

P0/P1 聚合评分 + 历史趋势追踪。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class AuditFinding:
    """单条审计发现。"""
    severity: str       # "P0" | "P1" | "P2" | "P3"
    category: str       # "security" | "quality" | "coverage" | "drift" | "contract"
    detail: str = ""

    def is_blocking(self) -> bool:
        return self.severity == "P0"

    def is_warning(self) -> bool:
        return self.severity == "P1"


@dataclass
class AuditHealthScore:
    """审计健康评分结果。"""
    score: float
    p0_count: int
    p1_count: int
    p0_blocking: bool
    p1_above_threshold: bool
    threshold: int = 3
    evaluated_at_utc: str = ""

    def audit_health(self) -> dict:
        """gate 6 需要的 5 字段。"""
        return {
            "score": self.score,
            "p0_count": self.p0_count,
            "p1_count": self.p1_count,
            "p0_blocking": self.p0_blocking,
            "p1_above_threshold": self.p1_above_threshold,
        }

    def to_dict(self) -> dict:
        return {
            **self.audit_health(),
            "threshold": self.threshold,
            "evaluated_at_utc": self.evaluated_at_utc,
        }


class AuditHealthScorer:
    """审计健康评分器 — 只读，聚合已有 finding。

    evaluate(findings) → AuditHealthScore
    """

    def __init__(self, p1_threshold: int = 3, trend_window: int = 10):
        self.p1_threshold = p1_threshold
        self.trend_window = trend_window
        self._history: list[AuditHealthScore] = []

    def evaluate(self, findings: list[AuditFinding]) -> AuditHealthScore:
        p0_count = sum(1 for f in findings if f.is_blocking())
        p1_count = sum(1 for f in findings if f.is_warning())

        if p0_count > 0:
            score = max(0.0, 0.5 - 0.1 * p0_count)
            p0_blocking = True
        elif p1_count == 0:
            score = 1.0
            p0_blocking = False
        elif p1_count <= self.p1_threshold:
            score = 0.8 + 0.2 * (1.0 - p1_count / max(self.p1_threshold, 1))
            p0_blocking = False
        else:
            score = max(0.3, 0.7 - 0.1 * (p1_count - self.p1_threshold))
            p0_blocking = False

        result = AuditHealthScore(
            score=round(score, 4),
            p0_count=p0_count,
            p1_count=p1_count,
            p0_blocking=p0_blocking,
            p1_above_threshold=p1_count > self.p1_threshold,
            threshold=self.p1_threshold,
            evaluated_at_utc=_now_utc(),
        )
        self._history.append(result)
        if len(self._history) > self.trend_window:
            self._history = self._history[-self.trend_window:]
        return result

    def trend(self) -> dict:
        if not self._history:
            return {"avg_score": 1.0, "total_scores": 0, "trend": "stable"}
        scores = [h.score for h in self._history]
        avg = sum(scores) / len(scores)
        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / 3
            older_avg = sum(scores[:3]) / 3 if len(scores) >= 6 else avg
            if recent_avg < older_avg - 0.1:
                direction = "declining"
            elif recent_avg > older_avg + 0.1:
                direction = "improving"
            else:
                direction = "stable"
        else:
            direction = "stable"
        return {
            "avg_score": round(avg, 4),
            "total_scores": len(scores),
            "trend": direction,
            "latest_score": scores[-1],
        }
