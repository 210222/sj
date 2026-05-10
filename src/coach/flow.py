"""心流互信息计算 + 轻量 BKT 知识追踪。

参考: pyBKT (CAHLR/pyBKT) — models.py 接口约定
实现: 1-skill 纯 Python BKT（无外部依赖）
"""

import math
import logging

_logger = logging.getLogger(__name__)


def _entropy(prob: float) -> float:
    """二值熵 H(p) = -p*log2(p) - (1-p)*log2(1-p)。"""
    if prob <= 0.0 or prob >= 1.0:
        return 0.0
    return -prob * math.log2(prob) - (1 - prob) * math.log2(1 - prob)


class BKTEngine:
    """1-skill 贝叶斯知识追踪。

    pyBKT 参考: CAHLR/pyBKT models.py 中 BKT.fit/predict 接口。
    """

    def __init__(self, prior: float = 0.3, guess: float = 0.1,
                 slip: float = 0.1, learn: float = 0.2):
        self.prior = max(0.01, min(0.99, prior))
        self.guess = max(0.01, min(0.99, guess))
        self.slip = max(0.01, min(0.99, slip))
        self.learn = max(0.01, min(0.99, learn))

    def predict(self, observations: list[int]) -> list[float]:
        """给定观测序列 [0/1 正确/错误]，返回每步后的 P(learned)。"""
        p_learned = self.prior
        result = [p_learned]

        for obs in observations:
            if obs == 1:
                p_obs_given_learned = 1.0 - self.slip
                p_obs_given_not = self.guess
            else:
                p_obs_given_learned = self.slip
                p_obs_given_not = 1.0 - self.guess

            p_obs = p_learned * p_obs_given_learned + (1 - p_learned) * p_obs_given_not
            if p_obs > 0:
                p_learned_given_obs = (p_learned * p_obs_given_learned) / p_obs
            else:
                p_learned_given_obs = p_learned

            p_learned = p_learned_given_obs + (1 - p_learned_given_obs) * self.learn
            p_learned = max(0.0, min(1.0, p_learned))
            result.append(p_learned)

        return result

    # Phase 23: 间隔重复 — 遗忘曲线估计
    def estimate_retention(self, mastery: float, days_since_last_practiced: float,
                           half_life: float = 7.0) -> float:
        """估计技能保留率（基于 Ebbinghaus 遗忘曲线）。

        R = mastery * 0.5^(days / half_life)
        第 0 天: R = mastery
        第 half_life 天: R = mastery * 0.5
        """
        mastery = max(0.01, min(1.0, mastery))
        days = max(0.0, days_since_last_practiced)
        retention = mastery * (0.5 ** (days / max(half_life, 0.5)))
        return round(max(0.0, min(1.0, retention)), 4)


class FlowOptimizer:
    """心流优化器：互信息 + BKT + 难度调节。

    compute_flow(skill_probs, task_difficulty) → dict
    """

    def __init__(self, bkt_params: dict | None = None, config: dict | None = None):
        self._bkt_params = bkt_params or {}
        self._config = config or {}
        self._bkt = BKTEngine(
            prior=self._bkt_params.get("prior", 0.3),
            guess=self._bkt_params.get("guess", 0.1),
            slip=self._bkt_params.get("slip", 0.1),
            learn=self._bkt_params.get("learn", 0.2),
        )
        self._last_adjustment_turn: int = 0

    def compute_flow(self, skill_probs: list[float] | None = None,
                     task_difficulty: float = 0.5,
                     observations: list[int] | None = None) -> dict:
        """计算心流状态。I(M;E) = H(M) - H(M|E)。"""
        if observations is not None:
            probs = self._bkt.predict(observations)
            current_knowledge = probs[-1] if probs else self._bkt.prior
        elif skill_probs and len(skill_probs) > 0:
            current_knowledge = skill_probs[-1]
        else:
            current_knowledge = 0.5

        h_task = _entropy(task_difficulty)
        h_residual = _entropy(current_knowledge)
        mutual_info = max(0.0, h_task - h_residual)
        flow_ratio = mutual_info / max(h_task, 0.001)

        # 知识-难度差（方向性修正——熵在 0.2/0.8 处对称，无法区分高低技能）
        skill_gap = task_difficulty - current_knowledge

        cfg = self._config.get("flow_zone", {})
        opt_low = cfg.get("optimal_low", 0.4)
        opt_high = cfg.get("optimal_high", 0.6)
        boredom_th = cfg.get("boredom_threshold", 0.2)
        anxiety_th = cfg.get("anxiety_threshold", 0.8)

        if task_difficulty < 0.05 or h_task < 0.1:
            channel = "apathy"
        elif skill_gap > 0.3:
            channel = "anxiety"          # 任务远高于技能
        elif skill_gap < -0.3:
            channel = "boredom"          # 技能远高于任务
        elif abs(skill_gap) <= 0.15:
            channel = "flow"             # 技能-难度匹配
        elif flow_ratio > anxiety_th:
            channel = "near_anxiety"
        elif flow_ratio < boredom_th:
            channel = "near_boredom"
        elif opt_low <= flow_ratio <= opt_high:
            channel = "flow"
        elif flow_ratio < opt_low:
            channel = "near_boredom"
        else:
            channel = "near_anxiety"

        adjust = 0.0
        if channel == "boredom":
            adjust = 0.2
        elif channel == "anxiety":
            adjust = -0.2
        elif channel == "near_boredom":
            adjust = 0.1
        elif channel == "near_anxiety":
            adjust = -0.1

        return {
            "mutual_information": round(mutual_info, 4),
            "entropy_task": round(h_task, 4),
            "entropy_residual": round(h_residual, 4),
            "flow_ratio": round(flow_ratio, 4),
            "flow_channel": channel,
            "adjust_difficulty": round(adjust, 4),
            "student_knowledge": round(current_knowledge, 4),
        }

    def fit_bkt(self, observations: list[list[int]]) -> dict:
        """简单参数拟合——从观测序列估算 prior/guess/slip/learn。"""
        all_correct = []
        for seq in observations:
            all_correct.extend(seq)

        if not all_correct:
            return {"prior": self._bkt.prior, "guess": self._bkt.guess,
                    "slip": self._bkt.slip, "learn": self._bkt.learn}

        firsts = [seq[0] for seq in observations if seq]
        prior = sum(firsts) / max(len(firsts), 1) if firsts else 0.3

        halves = len(all_correct) // 2
        early_correct = sum(all_correct[:halves]) / max(halves, 1)
        late_correct = sum(all_correct[halves:]) / max(len(all_correct) - halves, 1)
        learn = max(0.01, min(0.5, late_correct - early_correct))

        return {
            "prior": round(prior, 4),
            "guess": self._bkt.guess,
            "slip": self._bkt.slip,
            "learn": round(learn, 4),
        }
