"""MAPE-K Execute — 执行层：动作分发 + 重试 + 写 ledger。"""

from datetime import datetime, timezone


class Execute:
    """执行层：分发 DSL 动作包 + 调用外部 API + 结果记录。

    dispatch(plan, context) → execution_result
    """

    TARGETS = ["CoachAgent", "Ledger", "Audit", "ExternalAPI"]

    def __init__(self, max_retries: int = 2):
        self._max_retries = max_retries
        self._history: list[dict] = []

    def dispatch(self, plan: dict, context: dict | None = None) -> dict:
        """分发策略计划到各目标。"""
        ctx = context or {}
        target = plan.get("target_action_type", "suggest")
        intensity = plan.get("intensity", "low")

        results = {}
        for tgt in self.TARGETS:
            result = self._dispatch_to(tgt, plan, ctx)
            results[tgt] = result

        execution = {
            "target": target,
            "intensity": intensity,
            "results": results,
            "all_success": all(r.get("success") for r in results.values()),
            "timestamp": self._now_utc(),
        }
        self._history.append(execution)
        return execution

    def _dispatch_to(self, target: str, plan: dict, context: dict) -> dict:
        for attempt in range(self._max_retries + 1):
            try:
                if target == "CoachAgent":
                    return self._call_coach_agent(plan, context)
                elif target == "Ledger":
                    return self._write_ledger(plan)
                elif target == "Audit":
                    return self._trigger_audit(plan)
                elif target == "ExternalAPI":
                    return self._call_external(plan, context)
            except Exception as e:
                if attempt < self._max_retries:
                    continue
                return {"target": target, "success": False,
                        "error": str(e), "attempts": attempt + 1}
        return {"target": target, "success": False, "error": "unknown"}

    @staticmethod
    def _call_coach_agent(plan: dict, context: dict) -> dict:
        return {"target": "CoachAgent", "success": True,
                "action": plan.get("target_action_type"),
                "note": "CoachAgent integration — activated in S6.7"}

    @staticmethod
    def _write_ledger(plan: dict) -> dict:
        return {"target": "Ledger", "success": True,
                "note": "Ledger write — activated in S6.7"}

    @staticmethod
    def _trigger_audit(plan: dict) -> dict:
        return {"target": "Audit", "success": True,
                "note": "Audit trigger — activated in S6.7"}

    @staticmethod
    def _call_external(plan: dict, context: dict) -> dict:
        return {"target": "ExternalAPI", "success": True,
                "note": "External API call — QS collector placeholder"}

    def history(self) -> list[dict]:
        return list(self._history)

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
