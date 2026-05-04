"""MAPE-K Plan — 规划层：策略组合生成 + 资源分配 + 冲突消解。"""

from datetime import datetime, timezone


class Plan:
    """规划层：基于 Analyze 输出生成策略组合。

    generate(analysis_report) → plan
    """

    def __init__(self, max_horizon_steps: int = 5):
        self._max_steps = max_horizon_steps
        self._current_strategy: dict | None = None

    def generate(self, analysis_report: dict) -> dict:
        """生成下一阶段策略组合。"""
        trends = analysis_report.get("trends", [])
        anomalies = analysis_report.get("anomalies", [])
        confidence = analysis_report.get("confidence", 0.0)

        action_type = self._select_action_type(trends, anomalies)
        intensity = self._compute_intensity(anomalies, confidence)
        resource_budget = self._allocate_resources(intensity)
        conflicts = self._resolve_conflicts(action_type, intensity)

        plan = {
            "target_action_type": action_type,
            "intensity": intensity,
            "resource_budget": resource_budget,
            "horizon_steps": min(self._max_steps, max(1, len(anomalies) // 2 + 1)),
            "conflicts": conflicts,
            "confidence": confidence,
            "generated_at": self._now_utc(),
        }
        self._current_strategy = plan
        return plan

    def _select_action_type(self, trends: list[dict],
                             anomalies: list[dict]) -> str:
        if len(anomalies) > 2:
            return "probe"
        rising_metrics = [t["metric"] for t in trends
                          if t.get("direction") == "rising"]
        falling_metrics = [t["metric"] for t in trends
                           if t.get("direction") == "falling"]
        if len(falling_metrics) >= len(rising_metrics) and len(falling_metrics) > 0:
            return "scaffold"
        if len(rising_metrics) > len(falling_metrics):
            return "challenge"
        return "suggest"

    @staticmethod
    def _compute_intensity(anomalies: list[dict], confidence: float) -> str:
        if len(anomalies) == 0 and confidence < 0.5:
            return "low"
        elif len(anomalies) <= 2:
            return "medium"
        return "high"

    @staticmethod
    def _allocate_resources(intensity: str) -> dict:
        base = {"max_steps": 3, "max_retries": 1, "timeout_ms": 1000}
        if intensity == "high":
            base.update({"max_steps": 5, "max_retries": 3, "timeout_ms": 3000})
        elif intensity == "low":
            base.update({"max_steps": 1, "max_retries": 0, "timeout_ms": 500})
        return base

    def _resolve_conflicts(self, action_type: str, intensity: str) -> list[dict]:
        conflicts = []
        if self._current_strategy:
            prev_type = self._current_strategy.get("target_action_type")
            if prev_type and prev_type != action_type:
                if intensity == "high" and prev_type in ("probe", "reflect"):
                    conflicts.append({
                        "type": "action_type_switch",
                        "from": prev_type,
                        "to": action_type,
                        "severity": "medium",
                        "resolution": "allow_with_caution",
                    })
        return conflicts

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
