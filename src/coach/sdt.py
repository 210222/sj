"""自决理论三需求评估 — 交互行为 → Autonomy/Competence/Relatedness 评分。"""

import logging

_logger = logging.getLogger(__name__)


class SDTProfile:
    """SDT 评估输出。"""

    def __init__(self, autonomy: float, competence: float, relatedness: float,
                 advice: dict | None = None):
        self.autonomy = round(max(0.0, min(1.0, autonomy)), 4)
        self.competence = round(max(0.0, min(1.0, competence)), 4)
        self.relatedness = round(max(0.0, min(1.0, relatedness)), 4)
        self.advice = advice or {}

    def to_dict(self) -> dict:
        return {
            "autonomy": self.autonomy,
            "competence": self.competence,
            "relatedness": self.relatedness,
            "advice": self.advice,
        }


class SDTAssessor:
    """从交互行为推断三需求满足程度。

    assess(session_data) → SDTProfile（含三轴评分 + 策略建议）
    """

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._signal_history: dict[str, list[float]] = {
            "autonomy": [],
            "competence": [],
            "relatedness": [],
        }

    # ── 主入口 ──────────────────────────────────────────────────

    def assess(self, session_data: dict | None = None) -> SDTProfile:
        """评估三需求满足程度。"""
        if session_data is None:
            session_data = {}

        auto = self._score_autonomy(session_data)
        comp = self._score_competence(session_data)
        rel = self._score_relatedness(session_data)

        self._signal_history["autonomy"].append(auto)
        self._signal_history["competence"].append(comp)
        self._signal_history["relatedness"].append(rel)

        advice = self._generate_advice(auto, comp, rel)
        return SDTProfile(auto, comp, rel, advice)

    # ── 三轴评分 ────────────────────────────────────────────────

    def _score_autonomy(self, data: dict) -> float:
        """自主性评分 [0,1]。

        - rewrite_rate: pulse 改写率（高改写→高 Autonomy）
        - excursion_use_count: 远足使用次数
        - command_initiation_rate: 用户主动发起率
        """
        has_data = any(k in data and data[k] is not None
                       for k in ("rewrite_rate", "excursion_use_count", "initiation_rate"))
        if not has_data:
            return 0.5

        rewrite_rate = data.get("rewrite_rate") or 0.0
        excursion_count = data.get("excursion_use_count") or 0
        initiation_rate = data.get("initiation_rate") or 0.5

        auto_score = rewrite_rate * 0.4
        exc_score = min(excursion_count / 3.0, 1.0) * 0.3
        init_score = initiation_rate * 0.3
        return auto_score + exc_score + init_score

    def _score_competence(self, data: dict) -> float:
        """胜任感评分 [0,1]。

        - no_assist_scores: list[float] No-Assist 评估分数
        - task_completion_rate: 任务完成率
        - difficulty_trend: 难度选择趋势
        """
        has_data = any(k in data and data[k] is not None
                       for k in ("no_assist_scores", "task_completion_rate", "difficulty_trend"))
        if not has_data:
            return 0.5

        nas = data.get("no_assist_scores") or []
        tcr = data.get("task_completion_rate") or 0.5
        diff_trend = data.get("difficulty_trend") or 0.0

        nas_avg = sum(nas[-3:]) / max(len(nas[-3:]), 1) if nas else 0.5
        nas_score = nas_avg * 0.5
        tcr_score = tcr * 0.3
        diff_score = max(0.0, min(1.0, diff_trend * 2.0)) * 0.2
        return nas_score + tcr_score + diff_score

    def _score_relatedness(self, data: dict) -> float:
        """关联性评分 [0,1]。

        - session_count: 总会话数
        - return_rate: 主动返回率
        - interaction_depth: 平均交互深度
        """
        has_data = any(k in data and data[k] is not None
                       for k in ("session_count", "return_rate", "interaction_depth"))
        if not has_data:
            return 0.5

        sessions = data.get("session_count") or 0
        return_rate = data.get("return_rate") or 0.5
        depth = data.get("interaction_depth") or 0.0

        sess_score = min(sessions / 20.0, 1.0) * 0.3
        ret_score = return_rate * 0.4
        depth_score = min(depth / 10.0, 1.0) * 0.3
        return sess_score + ret_score + depth_score

    # ── 策略建议 ────────────────────────────────────────────────

    def _generate_advice(self, auto: float, comp: float, rel: float) -> dict:
        """根据三轴评分生成对话策略建议。"""
        cfg = self._config.get("thresholds", {})
        auto_low = cfg.get("autonomy_low", 0.3)
        comp_low = cfg.get("competence_low", 0.3)
        rel_low = cfg.get("relatedness_low", 0.3)

        advice = {
            "adjust_autonomy_support": auto < auto_low,
            "adjust_difficulty": (
                "lower" if comp < comp_low
                else "raise" if comp > 0.7
                else "maintain"
            ),
            "increase_relatedness": rel < rel_low,
        }

        needs = []
        if auto < auto_low:
            needs.append("autonomy")
        if comp < comp_low:
            needs.append("competence")
        if rel < rel_low:
            needs.append("relatedness")
        advice["dominant_needs"] = needs if needs else ["none"]

        return advice
