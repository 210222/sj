"""M5: 决策融合引擎 — 规则法版。

L0/L1/L2 三路证据 + 不确定性向量 → 加权融合分
→ 冲突检测 → intensity 映射 + dominant_layer + conflict_level。
所有常量/类型/异常走 src.middle.shared，所有时间走 src.inner.clock。
"""

import math
from datetime import datetime, timezone

from src.inner.clock import get_window_30min, format_utc, parse_utc
from src.middle.shared.config import (
    DECISION_WEIGHT_TRANSFER,
    DECISION_WEIGHT_CREATIVITY,
    DECISION_WEIGHT_INDEPENDENCE,
    DECISION_MAX_DELTA_PER_UPDATE,
    DECISION_MIN_WEIGHT,
    DECISION_LRM_WEIGHT,
    DECISION_ROBUST_WEIGHT,
    DECISION_CONFLICT_ESCALATE,
    MIDDLE_CONFIG_VERSION,
)
from src.middle.shared.constants import (
    INTERVENTION_INTENSITIES,
    DOMINANT_LAYERS,
    CONFLICT_LEVELS,
)
from src.middle.shared.exceptions import StateEstimationError

INTENSITY_FULL = "full"
INTENSITY_REDUCED = "reduced"
INTENSITY_MINIMAL = "minimal"
INTENSITY_NONE = "none"

INTENSITY_ORDER = [INTENSITY_FULL, INTENSITY_REDUCED, INTENSITY_MINIMAL, INTENSITY_NONE]

VALID_INTENSITIES = frozenset(INTENSITY_ORDER)
VALID_DOMINANT = frozenset(DOMINANT_LAYERS)
VALID_CONFLICT = frozenset(CONFLICT_LEVELS)

MODEL_VERSION = "decision_v1.0.0"

# ── 强度映射阈值 ──────────────────────────────────────────────
_INTENSITY_FULL_MIN = 0.70
_INTENSITY_REDUCED_MIN = 0.45


class DecisionEngine:
    """中圈决策融合引擎。

    融合 L0/L1/L2 三路证据 + 不确定性向量，
    产出 intensity + dominant_layer + conflict_level。
    """

    MODEL_VERSION = MODEL_VERSION

    def __init__(
        self,
        weight_transfer: float | None = None,
        weight_creativity: float | None = None,
        weight_independence: float | None = None,
        max_delta: float | None = None,
        min_weight: float | None = None,
        lrm_weight: float | None = None,
        robust_weight: float | None = None,
        conflict_escalate: float | None = None,
    ):
        self.w_transfer = (
            weight_transfer if weight_transfer is not None
            else DECISION_WEIGHT_TRANSFER
        )
        self.w_creativity = (
            weight_creativity if weight_creativity is not None
            else DECISION_WEIGHT_CREATIVITY
        )
        self.w_independence = (
            weight_independence if weight_independence is not None
            else DECISION_WEIGHT_INDEPENDENCE
        )
        self.max_delta = (
            max_delta if max_delta is not None
            else DECISION_MAX_DELTA_PER_UPDATE
        )
        self.min_weight = (
            min_weight if min_weight is not None else DECISION_MIN_WEIGHT
        )
        self.lrm_weight = (
            lrm_weight if lrm_weight is not None else DECISION_LRM_WEIGHT
        )
        self.robust_weight = (
            robust_weight if robust_weight is not None else DECISION_ROBUST_WEIGHT
        )
        self.conflict_escalate = (
            conflict_escalate if conflict_escalate is not None
            else DECISION_CONFLICT_ESCALATE
        )
        self._validate_config()

    def _validate_config(self) -> None:
        if self.w_transfer < 0.0 or self.w_transfer > 1.0:
            raise StateEstimationError(
                f"weight_transfer must be in [0,1], got {self.w_transfer}"
            )
        if self.w_creativity < 0.0 or self.w_creativity > 1.0:
            raise StateEstimationError(
                f"weight_creativity must be in [0,1], got {self.w_creativity}"
            )
        if self.w_independence < 0.0 or self.w_independence > 1.0:
            raise StateEstimationError(
                f"weight_independence must be in [0,1], got {self.w_independence}"
            )
        weight_sum = self.w_transfer + self.w_creativity + self.w_independence
        if abs(weight_sum - 1.0) > 1e-9:
            raise StateEstimationError(
                f"Decision weights must sum to 1.0, got {weight_sum} "
                f"(transfer={self.w_transfer}, creativity={self.w_creativity}, "
                f"independence={self.w_independence})"
            )
        if self.conflict_escalate < 0.0 or self.conflict_escalate > 1.0:
            raise StateEstimationError(
                f"conflict_escalate must be in [0,1], got {self.conflict_escalate}"
            )

    # ── 主入口 ─────────────────────────────────────────────────

    def decide(
        self,
        trace_id: str,
        event_time_utc: str,
        l0: dict,
        l1: dict,
        l2: dict,
        uncertainty: dict,
        context: dict | None = None,
    ) -> dict:
        """执行决策融合。

        Args:
            trace_id: 追溯 ID。
            event_time_utc: ISO 8601 UTC。
            l0: {"state": str, "confidence": float}
            l1: {"correction": str, "magnitude": float}
            l2: {"feasible": bool, "block_reason": str}
            uncertainty: {"l0": float, "l1": float, "l2": float}
            context: 可选。

        Returns:
            {"intensity": str, "dominant_layer": str,
             "conflict_level": str, "reason_code": str,
             "total_score": float, "conflict_score": float,
             "model_version": str, "config_version": str,
             "event_time_utc": str, "window_id": str,
             "evaluated_at_utc": str}
        """
        self._validate_inputs(trace_id, event_time_utc, l0, l1, l2, uncertainty)

        # 1. 安全硬门控
        if not l2["feasible"]:
            return self._blocked_result(event_time_utc, l2["block_reason"])

        # 2. 三路候选分
        transfer_score = self._transfer_score(l0, l1)
        creativity_score = self._creativity_score(l0, l1)
        independence_score = self._independence_score(l0, uncertainty)

        # 3. 加权融合
        total_score = (
            self.w_transfer * transfer_score
            + self.w_creativity * creativity_score
            + self.w_independence * independence_score
        )
        total_score = max(0.0, min(1.0, total_score))

        # max_delta 约束：限制单次总分变化幅度
        ctx = context or {}
        prior_score = ctx.get("prior_total_score")
        if prior_score is not None and isinstance(prior_score, (int, float)):
            delta = abs(total_score - prior_score)
            if delta > self.max_delta:
                if total_score > prior_score:
                    total_score = prior_score + self.max_delta
                else:
                    total_score = prior_score - self.max_delta
                total_score = max(0.0, min(1.0, total_score))

        # 4. 冲突检测
        conflict_score = self._compute_conflict(
            transfer_score, creativity_score, independence_score, uncertainty
        )
        if conflict_score >= self.conflict_escalate:
            conflict_level = "high"
        elif conflict_score >= self.conflict_escalate * 0.6:
            conflict_level = "mid"
        else:
            conflict_level = "low"

        # 5. 强度映射（含冲突降档）
        intensity, reason_code = self._map_intensity(
            total_score, conflict_level
        )

        # 6. 主导层判定
        dominant = self._dominant_layer(l0, l1, l2)

        window_id = get_window_30min(event_time_utc)

        return {
            "intensity": intensity,
            "dominant_layer": dominant,
            "conflict_level": conflict_level,
            "reason_code": reason_code,
            "total_score": total_score,
            "conflict_score": conflict_score,
            "model_version": self.MODEL_VERSION,
            "config_version": MIDDLE_CONFIG_VERSION,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
        }

    # ── 安全门控 ───────────────────────────────────────────────

    def _blocked_result(self, event_time_utc: str,
                        block_reason: str) -> dict:
        window_id = get_window_30min(event_time_utc)
        return {
            "intensity": INTENSITY_NONE,
            "dominant_layer": "L2",
            "conflict_level": "low",
            "reason_code": f"DEC_BLOCK_{block_reason or 'L2_NOT_FEASIBLE'}",
            "total_score": 0.0,
            "conflict_score": 0.0,
            "model_version": self.MODEL_VERSION,
            "config_version": MIDDLE_CONFIG_VERSION,
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "evaluated_at_utc": format_utc(datetime.now(timezone.utc)),
        }

    # ── 三路评分 ───────────────────────────────────────────────

    def _transfer_score(self, l0: dict, l1: dict) -> float:
        """迁移得分：l0 稳定性 × l1 修正一致性。"""
        confidence = l0.get("confidence", 0.5)
        magnitude = l1.get("magnitude", 0.0)
        correction = l1.get("correction", "none")

        # 修正方向为 none 时打折
        direction_factor = 0.5 if correction == "none" else 0.8
        score = confidence * 0.5 + magnitude * direction_factor
        return max(0.0, min(1.0, score))

    def _creativity_score(self, l0: dict, l1: dict) -> float:
        """创造性得分：l0 状态多样性 × l1 修正幅度。"""
        confidence = l0.get("confidence", 0.5)
        magnitude = l1.get("magnitude", 0.0)
        correction = l1.get("correction", "none")

        # increase/decrease 促进创造性
        delta_factor = 1.0 if correction != "none" else 0.4
        score = confidence * 0.4 + magnitude * 0.4 + delta_factor * 0.2
        return max(0.0, min(1.0, score))

    def _independence_score(self, l0: dict,
                            uncertainty: dict) -> float:
        """独立思考得分：l0 置信度 × (1 - L0 不确定度)。"""
        confidence = l0.get("confidence", 0.5)
        u_l0 = uncertainty.get("l0", 0.5)
        score = confidence * (1.0 - u_l0)
        return max(0.0, min(1.0, score))

    # ── 冲突检测 ───────────────────────────────────────────────

    def _compute_conflict(
        self,
        transfer: float,
        creativity: float,
        independence: float,
        uncertainty: dict,
    ) -> float:
        # 分路差异
        score_spread = max(transfer, creativity, independence) - min(
            transfer, creativity, independence
        )
        # 不确定性差异
        u_vals = [
            uncertainty.get("l0", 0.5),
            uncertainty.get("l1", 0.5),
            uncertainty.get("l2", 0.5),
        ]
        u_spread = max(u_vals) - min(u_vals)

        conflict = self.lrm_weight * score_spread + self.robust_weight * u_spread
        return max(0.0, min(1.0, conflict))

    # ── 强度映射 ───────────────────────────────────────────────

    def _map_intensity(self, total_score: float,
                       conflict_level: str) -> tuple[str, str]:
        # 极端低分
        if total_score < self.min_weight:
            return INTENSITY_NONE, "DEC_NONE_LOW_SCORE"

        # 基础映射
        if total_score >= _INTENSITY_FULL_MIN:
            base = INTENSITY_FULL
            reason = "DEC_FULL"
        elif total_score >= _INTENSITY_REDUCED_MIN:
            base = INTENSITY_REDUCED
            reason = "DEC_REDUCED"
        else:
            base = INTENSITY_MINIMAL
            reason = "DEC_MINIMAL"

        # 高冲突降一档
        if conflict_level == "high":
            idx = INTENSITY_ORDER.index(base)
            if idx < len(INTENSITY_ORDER) - 1:
                downgraded = INTENSITY_ORDER[idx + 1]
                return downgraded, f"DEC_{downgraded.upper()}_CONFLICT_DOWN"

        return base, reason

    # ── 主导层判定 ─────────────────────────────────────────────

    def _dominant_layer(self, l0: dict, l1: dict, l2: dict) -> str:
        if not l2.get("feasible", True):
            return "L2"

        scores = {
            "L0": l0.get("confidence", 0.5),
            "L1": l1.get("magnitude", 0.0),
            "L2": 0.6,  # 可行时给中等基线
        }
        best = max(scores, key=scores.get)
        # 如果差距不够大，返回 none
        if scores[best] < 0.3:
            return "none"
        return best

    # ── 输入校验 ───────────────────────────────────────────────

    def _validate_inputs(self, trace_id: str, event_time_utc: str,
                         l0: dict, l1: dict, l2: dict,
                         uncertainty: dict) -> None:
        if not isinstance(trace_id, str) or not trace_id:
            raise StateEstimationError("trace_id must be a non-empty string")
        if not isinstance(event_time_utc, str) or not event_time_utc:
            raise StateEstimationError(
                "event_time_utc must be a non-empty string"
            )
        try:
            parse_utc(event_time_utc)
        except (ValueError, Exception) as e:
            raise StateEstimationError(f"Invalid event_time_utc: {e}") from e

        for name, d in [("l0", l0), ("l1", l1), ("l2", l2), ("uncertainty", uncertainty)]:
            if not isinstance(d, dict):
                raise StateEstimationError(f"{name} must be a dict, got {type(d).__name__}")

        self._check_field(l0, "l0", "confidence")
        self._check_field(l1, "l1", "magnitude")
        self._check_field(l2, "l2", "feasible")
        self._check_field(l2, "l2", "block_reason")
        for k in ("l0", "l1", "l2"):
            self._check_field(uncertainty, "uncertainty", k)

    def _check_field(self, d: dict, label: str, key: str) -> None:
        val = d.get(key)
        if val is None:
            raise StateEstimationError(f"Missing {label}.{key}")
        if key == "feasible":
            if not isinstance(val, bool):
                raise StateEstimationError(
                    f"{label}.{key} must be bool, got {type(val).__name__}"
                )
        elif key == "block_reason":
            if not isinstance(val, str):
                raise StateEstimationError(
                    f"{label}.{key} must be str, got {type(val).__name__}"
                )
        else:
            if isinstance(val, bool):
                raise StateEstimationError(
                    f"{label}.{key} is bool, numeric required"
                )
            if not isinstance(val, (int, float)):
                raise StateEstimationError(
                    f"{label}.{key} must be numeric, got {type(val).__name__}"
                )
            if math.isnan(val) or math.isinf(val):
                raise StateEstimationError(
                    f"{label}.{key} is NaN or Inf"
                )
            if val < 0.0 or val > 1.0:
                raise StateEstimationError(
                    f"{label}.{key} out of [0,1]: {val}"
                )
