"""跨轨一致性检查器 — action_type ↔ dominant_layer 匹配。

语义安全三件套第二道闸门：检测 DSL 动作类型与管线主导层之间的跨轨偏离。
"""

# action_type → 期望的 dominant_layer
EXPECTED_DOMINANT: dict[str, str] = {
    "suggest":   "L0",
    "reflect":   "L0",
    "pulse":     "L0",
    "challenge": "L1",
    "probe":     "L1",
    "excursion": "L1",
    "scaffold":  "L2",
    "defer":     "L2",
}


class CrossTrackChecker:
    """跨轨一致性检查器。

    check(action_type, dominant_layer) → dict
    """

    DOMINANT_LAYERS = {"L0", "L1", "L2"}

    def __init__(self, config: dict | None = None):
        self._config = config or {}

    def check(self, action_type: str, dominant_layer: str) -> dict:
        """检查 action_type 与 dominant_layer 是否一致。"""
        expected = EXPECTED_DOMINANT.get(action_type)
        if expected is None:
            return {
                "consistent": True, "expected": None,
                "actual": dominant_layer, "severity": "none",
                "description": f"Unknown action_type '{action_type}', skipped",
            }

        consistent = (expected == dominant_layer)

        if consistent:
            severity = "none"
            desc = f"{action_type} ↔ {dominant_layer} 一致"
        else:
            layers = ["L0", "L1", "L2"]
            try:
                gap = abs(layers.index(expected) - layers.index(dominant_layer))
            except ValueError:
                gap = 1
            if gap >= 2:
                severity = "high"
            elif gap == 1:
                severity = "medium"
            else:
                severity = "low"
            desc = f"{action_type} 期望 {expected}，实际 {dominant_layer}（{severity}偏离）"

        return {
            "consistent": consistent,
            "expected": expected,
            "actual": dominant_layer,
            "severity": severity,
            "description": desc,
        }

    def check_batch(self, checks: list[tuple[str, str]]) -> list[dict]:
        """批量检查多条记录。"""
        return [self.check(at, dl) for at, dl in checks]

    def summary(self, results: list[dict]) -> dict:
        """从检查结果生成汇总统计。"""
        total = len(results)
        consistent = sum(1 for r in results if r["consistent"])
        return {
            "total": total,
            "consistent": consistent,
            "inconsistent": total - consistent,
            "consistency_rate": round(consistent / max(total, 1), 4),
            "severity_counts": {
                "high": sum(1 for r in results if r["severity"] == "high"),
                "medium": sum(1 for r in results if r["severity"] == "medium"),
                "low": sum(1 for r in results if r["severity"] == "low"),
            },
        }

    def suggest_correction(self, action_type: str, dominant_layer: str) -> dict:
        """当不一致时，提供修正建议。"""
        expected = EXPECTED_DOMINANT.get(action_type)
        if expected is None or expected == dominant_layer:
            return {"needs_correction": False, "suggested_action": None}

        layers: dict[str, list[str]] = {
            "L0": ["suggest", "reflect", "pulse"],
            "L1": ["challenge", "probe", "excursion"],
            "L2": ["scaffold", "defer"],
        }
        suggestions = layers.get(dominant_layer, [])
        return {
            "needs_correction": True,
            "suggested_action": suggestions[0] if suggestions else None,
            "alternatives": suggestions[1:] if len(suggestions) > 1 else [],
        }
