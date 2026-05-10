"""S4.2 — 知识覆盖追踪.

轻量方案: dict[str, int] 关键词集合，从 intent 标签 + LLM topics 提取。
后续可升级为向量方案。
"""

from __future__ import annotations


class LearningPathTracker:
    """追踪用户在教练系统中接触过的知识领域.

    轻量实现 — 内存 dict，不依赖数据库。
    """

    def __init__(self):
        self._topics: dict[str, int] = {}  # topic → encounter_count

    def record_topic(self, topic: str) -> None:
        """记录一个知识主题被涉及."""
        key = topic.strip().lower()
        if key and key != "general":
            self._topics[key] = self._topics.get(key, 0) + 1

    def record_from_payload(self, payload: dict) -> None:
        """从 LLM payload 中提取 topics 字段记录."""
        topics = payload.get("topics", [])
        if isinstance(topics, list):
            for t in topics:
                if isinstance(t, str):
                    self.record_topic(t)

    def extract_topics_from_text(self, text: str) -> list[str]:
        """从文本中提取关键词作为 topic（简化版）."""
        # 提取大写开头的专业词汇或英文标识符
        import re
        keywords = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[a-zA-Z]+)*\b', text)
        return keywords[:10]

    def get_covered_topics(self, limit: int = 20) -> list[str]:
        """获取已覆盖的知识领域列表（按频次降序）."""
        sorted_topics = sorted(
            self._topics.items(), key=lambda x: x[1], reverse=True)
        return [t for t, _ in sorted_topics[:limit]]

    def get_new_topics(self, limit: int = 5) -> list[str]:
        """获取低频/首次接触的知识领域."""
        return [t for t, c in self._topics.items() if c <= 1][:limit]

    def get_topic_count(self) -> int:
        return len(self._topics)

    def to_dict(self) -> dict:
        return dict(self._topics)

    def clear(self) -> None:
        self._topics.clear()


# 全局实例
_global_tracker: LearningPathTracker | None = None


def get_learning_path() -> LearningPathTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LearningPathTracker()
    return _global_tracker
