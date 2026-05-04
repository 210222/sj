"""用户状态追踪 — 包装 L0/L1/L2 管线输出。"""


class UserStateTracker:
    """聚合 L0/L1/L2 状态为统一用户画像。

    - update() 接收 pipeline 中各层输出，更新内部状态
    - get_state() 返回当前用户状态摘要
    """

    def __init__(self):
        self._l0_state = "stable"
        self._l0_confidence = 0.5
        self._l1_correction = "none"
        self._l1_magnitude = 0.0
        self._l2_feasible = True
        self._l2_uncertainty = 0.5

    def update(
        self,
        l0_result: dict | None = None,
        l1_result: dict | None = None,
        l2_result: dict | None = None,
    ) -> None:
        """从管线各层结果更新状态追踪。

        每个参数为可选 dict，只更新提供的字段。
        """
        if l0_result:
            self._l0_state = l0_result.get("state", self._l0_state)
            self._l0_confidence = l0_result.get("confidence", self._l0_confidence)

        if l1_result:
            self._l1_correction = l1_result.get("correction", self._l1_correction)
            self._l1_magnitude = l1_result.get("magnitude", self._l1_magnitude)

        if l2_result:
            self._l2_feasible = l2_result.get("feasible", self._l2_feasible)
            self._l2_uncertainty = l2_result.get("uncertainty", self._l2_uncertainty)

    def get_state(self) -> dict:
        """返回当前用户状态摘要（6 字段）。"""
        return {
            "state": self._l0_state,
            "confidence": self._l0_confidence,
            "correction": self._l1_correction,
            "magnitude": self._l1_magnitude,
            "feasible": self._l2_feasible,
            "uncertainty": self._l2_uncertainty,
        }
