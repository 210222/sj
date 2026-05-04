"""失败先例拦截器 — facts 表检索 + 意图匹配 + 阻断。

语义安全三件套第三道闸门：从 facts 表检索与当前 DSL 动作相似的失败先例。
"""

import logging
import re

_logger = logging.getLogger(__name__)


class PrecedentInterceptor:
    """基于 facts 表的失败先例拦截。

    通过依赖注入接受 data_source（不自行实例化真实数据层）。
    """

    def __init__(self, config: dict | None = None, data_source=None):
        self._config = config or {}
        self._match_cfg = self._config.get("matching", {})
        self._data = data_source

    def intercept(self, intent: str, domain: str = "general",
                  action_type: str = "") -> dict:
        """检查当前动作是否命中失败先例。

        Returns keys: hit, precedents, action, reason, precedent_count
        """
        precedents = self._search_precedents(intent, domain)

        if not precedents:
            return {
                "hit": False, "precedents": [],
                "action": "pass", "reason": None, "precedent_count": 0,
            }

        on_hit = self._config.get("action", {}).get("on_hit", "block")
        best = precedents[0]
        return {
            "hit": True,
            "precedents": precedents,
            "action": on_hit,
            "reason": (
                f"命中失败先例: {best.get('claim', 'unknown')} "
                f"(相似度 {best.get('_similarity', 0):.2f})"
            ),
            "precedent_count": len(precedents),
        }

    def _search_precedents(self, intent: str, domain: str) -> list[dict]:
        """从 facts 表检索失败的相似先例。"""
        if not self._data:
            return []

        try:
            precedents = self._data.query_facts(
                context_scope=domain,
                lifecycle_status="archived",
                limit=self._match_cfg.get("max_results", 5),
            )
        except Exception:
            _logger.warning("Precedent search: data source query failed", exc_info=True)
            return []

        # 过滤 reversibility_flag=0（不可回退）
        irreversibles = [p for p in precedents if p.get("reversibility_flag") == 0]

        threshold = self._match_cfg.get("text_similarity_threshold", 0.4)
        matched = []
        intent_keywords = set(self._tokenize(intent))

        for p in irreversibles:
            claim_keywords = set(self._tokenize(p.get("claim", "")))
            if not intent_keywords or not claim_keywords:
                continue
            overlap = len(intent_keywords & claim_keywords) / max(
                len(intent_keywords | claim_keywords), 1
            )
            if overlap >= threshold:
                p_dict = dict(p) if not isinstance(p, dict) else p
                p_dict["_similarity"] = round(overlap, 4)
                matched.append(p_dict)

        return sorted(matched, key=lambda x: x.get("_similarity", 0), reverse=True)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中英文混合分词：CJK 按字拆，ASCII 按词拆，混合段分别处理。"""
        words: list[str] = []
        for part in re.split(r'[\s,，。；；：、！？?]+', text):
            if not part:
                continue
            # 逐字符分群：连续 CJK / 连续 ASCII
            buf: list[str] = []
            buf_is_cjk: bool | None = None
            for ch in part:
                is_cjk = '一' <= ch <= '鿿'
                if buf_is_cjk is None:
                    buf_is_cjk = is_cjk
                elif is_cjk != buf_is_cjk:
                    # 边界：刷新缓冲区
                    if buf_is_cjk:
                        words.extend(buf)
                    else:
                        words.append(''.join(buf).lower())
                    buf = []
                    buf_is_cjk = is_cjk
                buf.append(ch)
            if buf:
                if buf_is_cjk:
                    words.extend(buf)
                else:
                    words.append(''.join(buf).lower())
        return words
