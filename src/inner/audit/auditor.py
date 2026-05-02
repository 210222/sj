"""Step 2: P0/P1 审计分级 — 合约对齐版。

contracts/audit.json 冻结约束：
- audit_level in {"pass", "p1_warn", "p1_freeze", "p0_block"}
- 每条 audit_result 包含: audit_id, event_id, p0_pass, p0_missing_fields,
  p1_null_fields, p1_null_rate_window, audit_time_utc, window_id, audit_level
- P1 缺失率 = count(events_with_any_P1_null) / total_events_in_window
"""

import uuid
from datetime import datetime, timezone

from .config import WARN_THRESHOLD, FREEZE_THRESHOLD

P0_FIELDS = [
    "trace_id",
    "policy_version",
    "counterfactual_ranker_version",
    "counterfactual_feature_schema_version",
]

P1_FIELDS = [
    "objective_weights_snapshot",
    "tradeoff_reason",
    "protected_metric_guardrail_hit",
    "used_fact_ids",
    "ignored_fact_ids_with_reason",
    "degradation_path",
    "counterfactual_policy_rank",
    "assignment_features",
    "eligibility_rule_id",
    "meta_conflict_score",
    "track_disagreement_level",
    "meta_conflict_alert_flag",
]


class AuditClassifier:
    """P0/P1 审计分类器 — 字段级分析 + 批量阈值判断。"""

    P0_FIELDS = P0_FIELDS
    P1_FIELDS = P1_FIELDS

    def __init__(
        self,
        warn_threshold: float | None = None,
        freeze_threshold: float | None = None,
    ):
        self.warn_threshold = (
            warn_threshold if warn_threshold is not None else WARN_THRESHOLD
        )
        self.freeze_threshold = (
            freeze_threshold if freeze_threshold is not None else FREEZE_THRESHOLD
        )

    def classify(self, event: dict) -> dict:
        """对单条事件做字段级缺失分析（不含批量阈值决策）。

        Returns:
            {"p0_pass": bool,
             "missing_p0_fields": [str],
             "missing_p1_fields": [str],
             "has_p1_issue": bool}
        """
        missing_p0 = [f for f in self.P0_FIELDS if not event.get(f)]
        missing_p1 = [f for f in self.P1_FIELDS if event.get(f) is None]

        return {
            "p0_pass": len(missing_p0) == 0,
            "missing_p0_fields": missing_p0,
            "missing_p1_fields": missing_p1,
            "has_p1_issue": len(missing_p1) > 0,
        }

    def classify_batch(self, events: list[dict]) -> list[dict]:
        """批量字段分析。"""
        return [self.classify(e) for e in events]

    def evaluate_threshold(self, p1_rate_ratio: float) -> str:
        """P1 缺失率阈值判断，返回合约 audit_level。

        Args:
            p1_rate_ratio: P1 缺失率（小数），如 0.015 表示 1.5%

        Returns:
            "p1_freeze" | "p1_warn" | "pass"
        """
        if p1_rate_ratio > self.freeze_threshold:
            return "p1_freeze"
        if p1_rate_ratio > self.warn_threshold:
            return "p1_warn"
        return "pass"


# ── 模块级函数 ──────────────────────────────────────────────────

def compute_batch_stats(events: list[dict]) -> dict:
    """合约定义 P1 缺失率：count(events_with_any_P1_null) / total。

    Returns:
        {"p0_incident_count": int,
         "p1_incident_count": int,      # 有任一 P1 为 NULL 的事件数
         "p1_rate_ratio": float,        # 小数（合约口径）
         "total_events": int}
    """
    if not events:
        return {
            "p0_incident_count": 0,
            "p1_incident_count": 0,
            "p1_rate_ratio": 0.0,
            "total_events": 0,
        }

    c = AuditClassifier()
    classifications = c.classify_batch(events)

    p0_count = sum(1 for r in classifications if not r["p0_pass"])
    # 合约定义：events_with_any_P1_null
    p1_any_null_count = sum(1 for e in events if _has_any_p1_null(e))
    total = len(events)
    p1_rate_ratio = round(p1_any_null_count / total, 6)

    return {
        "p0_incident_count": p0_count,
        "p1_incident_count": p1_any_null_count,
        "p1_rate_ratio": p1_rate_ratio,
        "total_events": total,
    }


def generate_audit_report(events: list[dict]) -> dict:
    """生成合约对齐的标准化审计报告。

    每条 per_event 条目严格包含 contracts/audit.json audit_result.fields：
    - audit_id, event_id, p0_pass, p0_missing_fields,
      p1_null_fields, p1_null_rate_window, audit_time_utc, window_id, audit_level
    """
    if not events:
        return {
            "batch_stats": compute_batch_stats([]),
            "per_event": [],
        }

    c = AuditClassifier()
    stats = compute_batch_stats(events)
    batch_p1_level = c.evaluate_threshold(stats["p1_rate_ratio"])
    classifications = c.classify_batch(events)
    audit_time = (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    )

    per_event = []
    for i, (event, cl) in enumerate(zip(events, classifications)):
        # ── 确定 audit_level ──
        if not cl["p0_pass"]:
            audit_level = "p0_block"
        elif cl["has_p1_issue"]:
            audit_level = batch_p1_level
        else:
            audit_level = "pass"

        per_event.append({
            "audit_id": str(uuid.uuid4()),
            "event_id": event.get("id"),
            "p0_pass": cl["p0_pass"],
            "p0_missing_fields": cl["missing_p0_fields"],
            "p1_null_fields": cl["missing_p1_fields"],
            "p1_null_rate_window": stats["p1_rate_ratio"],
            "audit_time_utc": audit_time,
            "window_id": event.get("window_id", ""),
            "audit_level": audit_level,
        })

    return {
        "batch_stats": stats,
        "per_event": per_event,
    }


def _has_any_p1_null(event: dict) -> bool:
    """合约定义：事件是否有至少一个 P1 字段为 NULL。"""
    return any(event.get(f) is None for f in P1_FIELDS)
