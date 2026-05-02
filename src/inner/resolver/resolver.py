"""Step 4: L3 冲突仲裁器 — 规则法版。

contracts/resolver.json 冻结约束：
- 冲突低 (<0.3): passthrough — 不做修正
- 冲突中 [0.3, 0.7): reduce_intervention — 降一级干预强度
- 冲突高 (>=0.7): conservative_minimum — 最小干预保守策略
- 输出: resolved_state, intervention_intensity, resolver_reason_code,
         disagreement_score, dominant_layer, resolver_policy_version
"""

from .config import (
    LOW_CONFLICT_THRESHOLD,
    HIGH_CONFLICT_THRESHOLD,
    WEIGHT_STATE_INCONSISTENCY,
    WEIGHT_FEASIBILITY_CONFLICT,
    WEIGHT_UNCERTAINTY,
    RESOLVER_POLICY_VERSION,
)

# 合约干预强度枚举及其降级顺序
INTENSITY_ORDER = ["full", "reduced", "minimal", "none"]


class DisagreementResolver:
    """L3 冲突仲裁器。

    输入 L0/L1/L2 三层的各自输出 + 不确定性向量，
    输出统一仲裁结果，遵循"最小干预优先"原则。
    """

    POLICY_VERSION = RESOLVER_POLICY_VERSION

    def __init__(
        self,
        low_threshold: float | None = None,
        high_threshold: float | None = None,
        w_state: float | None = None,
        w_feasibility: float | None = None,
        w_uncertainty: float | None = None,
    ):
        self.low_threshold = (
            low_threshold if low_threshold is not None
            else LOW_CONFLICT_THRESHOLD
        )
        self.high_threshold = (
            high_threshold if high_threshold is not None
            else HIGH_CONFLICT_THRESHOLD
        )
        self.w_state = (
            w_state if w_state is not None else WEIGHT_STATE_INCONSISTENCY
        )
        self.w_feasibility = (
            w_feasibility if w_feasibility is not None
            else WEIGHT_FEASIBILITY_CONFLICT
        )
        self.w_uncertainty = (
            w_uncertainty if w_uncertainty is not None
            else WEIGHT_UNCERTAINTY
        )

    # ── 主入口 ──────────────────────────────────────────────────

    def resolve(
        self,
        state_l0: dict,
        residual_l1: dict,
        feasibility_l2: dict,
        uncertainty_vector: dict,
        context: dict | None = None,
    ) -> dict:
        """执行三层冲突仲裁。

        Args:
            state_l0: L0 HBSSM 输出 {"state": str, "dwell_time": float, ...}
            residual_l1: L1 残差修正 {"correction": str, "magnitude": float, ...}
            feasibility_l2: L2 COM-B {"feasible": bool, "block_reason": str, ...}
            uncertainty_vector: {"l0": float, "l1": float, "l2": float}
            context: 可选附加上下文

        Returns:
            {"resolved_state": str,
             "intervention_intensity": "full"|"reduced"|"minimal"|"none",
             "resolver_action": "normal"|"deescalate"|"minimal_conservative",
             "resolver_reason_code": str,
             "disagreement_score": float,
             "dominant_layer": "L0"|"L1"|"L2"|"MIXED",
             "resolver_policy_version": str,
             "meta_conflict_alert_flag": int}
        """
        # 输入校验
        self._validate_inputs(state_l0, residual_l1, feasibility_l2,
                              uncertainty_vector)

        # 1) 计算 disagreement_score
        score_state = self._state_inconsistency(state_l0, residual_l1,
                                                feasibility_l2)
        score_feasibility = self._feasibility_conflict(feasibility_l2)
        score_uncertainty = self._uncertainty_level(uncertainty_vector)

        disagreement_score = round(
            self.w_state * score_state +
            self.w_feasibility * score_feasibility +
            self.w_uncertainty * score_uncertainty,
            4,
        )
        disagreement_score = max(0.0, min(1.0, disagreement_score))

        # 2) 确定冲突等级 + resolver_action
        if disagreement_score < self.low_threshold:
            conflict_level = "low"
            resolver_action = "normal"
        elif disagreement_score < self.high_threshold:
            conflict_level = "mid"
            resolver_action = "deescalate"
        else:
            conflict_level = "high"
            resolver_action = "minimal_conservative"

        # 3) 确定 dominant_layer
        dominant_layer = self._determine_dominant(
            state_l0, residual_l1, feasibility_l2, uncertainty_vector
        )

        # 4) 确定干预强度
        base_intensity = self._base_intensity(state_l0, residual_l1,
                                              feasibility_l2)
        intervention_intensity = self._apply_conflict(
            base_intensity, conflict_level
        )

        # 5) resolved_state（取主导层或保守融合）
        resolved_state = self._resolve_state(
            state_l0, residual_l1, feasibility_l2,
            conflict_level, dominant_layer
        )

        # 6) reason_code
        resolver_reason_code = self._build_reason_code(
            conflict_level, dominant_layer, disagreement_score
        )

        return {
            "resolved_state": resolved_state,
            "intervention_intensity": intervention_intensity,
            "resolver_action": resolver_action,
            "resolver_reason_code": resolver_reason_code,
            "disagreement_score": disagreement_score,
            "dominant_layer": dominant_layer,
            "resolver_policy_version": self.POLICY_VERSION,
            "meta_conflict_alert_flag": 1 if conflict_level == "high" else 0,
        }

    # ── 审计字段映射 ────────────────────────────────────────────

    def to_audit_fields(self, result: dict) -> dict:
        """将仲裁结果映射为可供 ledger/audit 消费的 P1 字段。"""
        return {
            "meta_conflict_score": result["disagreement_score"],
            "track_disagreement_level": result["disagreement_score"],
            "meta_conflict_alert_flag": result["meta_conflict_alert_flag"],
        }

    # ── 内部组件 ────────────────────────────────────────────────

    def _validate_inputs(self, state_l0, residual_l1, feasibility_l2,
                         uncertainty_vector):
        for name, val in [
            ("state_l0", state_l0),
            ("residual_l1", residual_l1),
            ("feasibility_l2", feasibility_l2),
            ("uncertainty_vector", uncertainty_vector),
        ]:
            if not isinstance(val, dict):
                raise TypeError(f"{name} must be dict, got {type(val).__name__}")
        for key in ("l0", "l1", "l2"):
            if key not in uncertainty_vector:
                raise ValueError(
                    f"uncertainty_vector missing key: '{key}'"
                )
            u = uncertainty_vector[key]
            if not isinstance(u, (int, float)) or u < 0 or u > 1:
                raise ValueError(
                    f"uncertainty_vector['{key}'] must be float in [0,1], "
                    f"got {u!r}"
                )

    def _state_inconsistency(self, state_l0, residual_l1,
                             feasibility_l2) -> float:
        """计算 L0/L1/L2 状态标签不一致度 [0,1]。

        若各层对用户状态的判断方向不同，得分较高。
        """
        l0_state = state_l0.get("state", "")
        l1_correction = residual_l1.get("correction", "")
        l2_feasible = feasibility_l2.get("feasible", True)

        conflicts = 0

        # L0 vs L1: 如果 L1 的修正方向与 L0 状态明显冲突
        if l0_state and l1_correction:
            if self._states_conflict(l0_state, l1_correction):
                conflicts += 1

        # L1 vs L2: 如果 L1 建议的方向被 L2 标记为不可行
        if l1_correction and not l2_feasible:
            conflicts += 1

        # L0 vs L2: 如果 L0 状态指向的行为被 L2 阻断
        if l0_state and not l2_feasible:
            block_reason = feasibility_l2.get("block_reason", "")
            if block_reason and l0_state.lower() in block_reason.lower():
                conflicts += 1

        if conflicts == 0:
            return 0.0
        elif conflicts == 1:
            return 0.5
        else:
            return 1.0

    def _feasibility_conflict(self, feasibility_l2: dict) -> float:
        """L2 可行性冲突度 [0,1]。

        feasible=False 时得分高；有 block_reason 时进一步升高。
        """
        feasible = feasibility_l2.get("feasible", True)
        block_reason = feasibility_l2.get("block_reason", "")

        if feasible:
            return 0.0
        if block_reason:
            return 0.8
        return 0.5

    def _uncertainty_level(self, uv: dict) -> float:
        """从 uncertainty_vector 提取聚合不确定性 [0,1]。

        取 L0/L1/L2 三层不确定性的加权均值。
        """
        return round((uv["l0"] + uv["l1"] + uv["l2"]) / 3.0, 4)

    def _determine_dominant(
        self,
        state_l0: dict,
        residual_l1: dict,
        feasibility_l2: dict,
        uv: dict,
    ) -> str:
        """确定 dominant_layer。

        规则：不确定性最低且输出最确定的层为主导层。
        如果最低不确定性有两个或以上的层共享 → MIXED。
        """
        uncertainties = {
            "L0": uv["l0"],
            "L1": uv["l1"],
            "L2": uv["l2"],
        }
        min_uncertainty = min(uncertainties.values())
        leaders = [
            layer for layer, u in uncertainties.items()
            if u == min_uncertainty
        ]
        if len(leaders) == 1:
            return leaders[0]
        return "none"

    def _base_intensity(
        self,
        state_l0: dict,
        residual_l1: dict,
        feasibility_l2: dict,
    ) -> str:
        """从各层输出中推测基础干预强度。"""
        l0_state = state_l0.get("state", "")
        l1_mag = residual_l1.get("magnitude", 0.5)
        l2_feasible = feasibility_l2.get("feasible", True)

        # L2 明确不可行 → 已经是最高干预
        if not l2_feasible:
            return "full"

        # L1 修正幅度大 → 高干预
        if isinstance(l1_mag, (int, float)) and l1_mag > 0.7:
            return "full"

        # L0 状态异常或剧烈
        if l0_state and any(
            tag in l0_state.lower()
            for tag in ("critical", "shock", "crisis")
        ):
            return "full"

        # 中等干预
        if isinstance(l1_mag, (int, float)) and l1_mag > 0.3:
            return "reduced"

        # 低干预
        return "minimal"

    def _apply_conflict(
        self, base_intensity: str, conflict_level: str
    ) -> str:
        """根据冲突等级降级干预强度。"""
        if conflict_level == "low":
            return base_intensity
        if conflict_level == "mid":
            return self._deescalate(base_intensity)
        # high conflict → 最小干预保守策略
        return "minimal"

    def _deescalate(self, intensity: str) -> str:
        """降一级干预强度。"""
        try:
            idx = INTENSITY_ORDER.index(intensity)
        except ValueError:
            return "reduced"
        new_idx = min(idx + 1, len(INTENSITY_ORDER) - 1)
        return INTENSITY_ORDER[new_idx]

    def _resolve_state(
        self,
        state_l0: dict,
        residual_l1: dict,
        feasibility_l2: dict,
        conflict_level: str,
        dominant_layer: str,
    ) -> dict:
        """仲裁后的融合状态对象（合约 type: object）。"""
        if conflict_level == "low":
            if dominant_layer == "L0":
                desc = state_l0.get("state", "unknown")
            elif dominant_layer == "L1":
                desc = residual_l1.get("correction", "unknown")
            elif dominant_layer == "L2":
                block = feasibility_l2.get("block_reason", "")
                desc = block if block else "feasible"
            else:
                desc = state_l0.get("state", "unknown")
            return {
                "status": desc,
                "source_layer": dominant_layer,
                "conflict_level": "low",
            }

        if conflict_level == "mid":
            base = state_l0.get("state", "unknown")
            corr = residual_l1.get("correction", "")
            desc = (
                f"{base} (moderated, correction: {corr})"
                if corr else base
            )
            return {
                "status": "moderated",
                "description": desc,
                "source_layer": dominant_layer,
                "conflict_level": "mid",
            }

        return {
            "status": "conservative_hold",
            "description": (
                f"L0={state_l0.get('state', '?')}, "
                f"L1={residual_l1.get('correction', '?')}, "
                f"L2={'blocked' if not feasibility_l2.get('feasible', True) else 'ok'}"
            ),
            "source_layer": dominant_layer,
            "conflict_level": "high",
        }

    def _build_reason_code(
        self, conflict_level: str, dominant: str, score: float
    ) -> str:
        """生成可审计的 reason_code。"""
        return (
            f"L3_{conflict_level}_{dominant}_"
            f"{self.POLICY_VERSION}_s{int(score * 100):02d}"
        )

    @staticmethod
    def _states_conflict(s1: str, s2: str) -> bool:
        """简单的方向冲突判定：状态词是否指向相反方向。"""
        positive = {"improving", "stable", "engaged", "progressing"}
        negative = {"deteriorating", "disengaged", "regressing", "critical"}

        s1_lower = s1.lower()
        s2_lower = s2.lower()

        s1_pos = any(w in s1_lower for w in positive)
        s1_neg = any(w in s1_lower for w in negative)
        s2_pos = any(w in s2_lower for w in positive)
        s2_neg = any(w in s2_lower for w in negative)

        if s1_pos and s2_neg:
            return True
        if s1_neg and s2_pos:
            return True
        return False
