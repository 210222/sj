"""TTM 五阶段状态机 — 阶段检测 + 转移验证 + 策略推荐。

数据源: contracts/ttm_stages.json (只读)
"""

import json
from pathlib import Path

_CONTRACT_PATH = Path(__file__).resolve().parent.parent.parent / "contracts" / "ttm_stages.json"
with open(_CONTRACT_PATH, encoding="utf-8") as _f:
    _CONTRACT = json.load(_f)

STAGES = [s["id"] for s in _CONTRACT["stages"]]
STAGE_STRATEGY_MAP = _CONTRACT["stage_strategy_map"]


class TTMStateMachine:
    """TTM 五阶段状态机。

    核心方法: assess / validate_transition / transition_to / get_strategy
    """

    STAGES = STAGES

    _VALID_TRANSITIONS: dict[str, list[str]] = {
        "precontemplation": ["precontemplation", "contemplation"],
        "contemplation":    ["precontemplation", "contemplation", "preparation"],
        "preparation":      ["contemplation", "preparation", "action"],
        "action":           ["preparation", "action", "maintenance"],
        "maintenance":      ["action", "maintenance"],
    }

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._current_stage: str = "precontemplation"
        self._stage_confidence: float = 0.0

    # ── 阶段检测 ────────────────────────────────────────────────

    def assess(self, user_data: dict, history: list[dict] | None = None) -> dict:
        """根据用户数据判断当前 TTM 阶段。

        Args:
            user_data: dict with cognitive_indicators, behavioral_indicators,
                       emotional_indicators, social_indicators (all list[float]),
                       optional session_count.
            history: 历史评估结果列表（可选）

        Returns:
            {current_stage, confidence, valid_transitions,
             recommended_strategy, next_stage_candidates}
        """
        scores = self._compute_stage_scores(user_data)
        best_stage = max(scores, key=scores.get)
        confidence = scores[best_stage]

        cfg = self._config.get("detect", {})
        threshold = cfg.get("confidence_threshold", 0.6)
        min_int = cfg.get("min_interactions", 5)

        # 数据不足时降低置信度
        total_indicators = sum(len(user_data.get(k, [])) for k in (
            "cognitive_indicators", "behavioral_indicators",
            "emotional_indicators", "social_indicators",
        ))
        if total_indicators < min_int:
            confidence = min(confidence, scores[best_stage] * 0.7)

        # 结合 history 做转移约束
        if history and self._config.get("transition", {}).get("allow_forward_jump", False) is False:
            prev = history[-1] if isinstance(history[-1], dict) else None
            if prev and "current_stage" in prev:
                prev_stage = prev["current_stage"]
                valid = self._VALID_TRANSITIONS.get(prev_stage, [prev_stage])
                if best_stage not in valid:
                    # 选择合法范围内得分最高的
                    constrained = {s: scores.get(s, 0.0) for s in valid}
                    best_stage = max(constrained, key=constrained.get)
                    confidence = min(confidence, constrained[best_stage])

        if confidence < threshold and history:
            prev = history[-1] if isinstance(history[-1], dict) else None
            if prev and "current_stage" in prev:
                best_stage = prev["current_stage"]
                confidence = scores.get(best_stage, 0.0)

        self._current_stage = best_stage
        self._stage_confidence = confidence

        strategy = self.get_strategy(best_stage)

        # 候选阶段（得分接近的）
        candidates = sorted(
            [{"stage": s, "score": v} for s, v in scores.items() if s != best_stage],
            key=lambda x: x["score"], reverse=True,
        )[:2]

        return {
            "current_stage": best_stage,
            "confidence": round(confidence, 4),
            "valid_transitions": self._VALID_TRANSITIONS.get(best_stage, [best_stage]),
            "recommended_strategy": strategy,
            "next_stage_candidates": candidates,
        }

    # ── 转移验证 ────────────────────────────────────────────────

    def validate_transition(self, to_stage: str) -> bool:
        """从当前阶段转移到 to_stage 是否合法。"""
        valid = self._VALID_TRANSITIONS.get(self._current_stage, [])
        return to_stage in valid

    def transition_to(self, to_stage: str) -> dict:
        """执行阶段转移。"""
        old_stage = self._current_stage
        if not self.validate_transition(to_stage):
            return {
                "success": False,
                "reason": f"Invalid transition: {old_stage} → {to_stage}",
                "from_stage": old_stage,
                "to_stage": to_stage,
            }
        self._current_stage = to_stage
        return {
            "success": True,
            "from_stage": old_stage,
            "to_stage": to_stage,
            "strategy": self.get_strategy(to_stage),
        }

    # ── 策略推荐 ────────────────────────────────────────────────

    def get_strategy(self, stage: str | None = None) -> dict:
        """获取指定阶段的策略映射。"""
        target = stage or self._current_stage
        return dict(STAGE_STRATEGY_MAP.get(target, {}))

    # ── 阶段得分计算 ────────────────────────────────────────────

    def _compute_stage_scores(self, user_data: dict) -> dict[str, float]:
        """对每个阶段计算匹配分数 [0,1]."""
        cog = user_data.get("cognitive_indicators", [])
        beh = user_data.get("behavioral_indicators", [])
        emo = user_data.get("emotional_indicators", [])
        soc = user_data.get("social_indicators", [])

        def _avg(lst, n=3):
            return sum(lst[-n:]) / max(len(lst[-n:]), 1) if lst else 0.0

        scores: dict[str, float] = {}

        # PC: 低认知 → 高得分
        if cog:
            scores["precontemplation"] = 1.0 - _avg(cog, 3)
        else:
            scores["precontemplation"] = 0.5

        # C: 中等认知 + 低行为
        avg_cog = _avg(cog, 3) if cog else 0.5
        avg_beh = _avg(beh, 3)
        scores["contemplation"] = avg_cog * 0.7 + (1.0 - avg_beh) * 0.3

        # P: 高认知 + 开始计划
        scores["preparation"] = _avg(cog, 3) if cog else 0.3

        # A: 高行为
        scores["action"] = _avg(beh, 5)

        # M: 持续行为 + 社交支持
        scores["maintenance"] = _avg(beh, 10) * 0.6 + _avg(soc, 5) * 0.4

        return {k: round(max(0.0, min(1.0, v)), 4) for k, v in scores.items()}
