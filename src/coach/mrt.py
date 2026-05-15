"""S7.1 MRT 微随机实验框架 + Phase 38 outcome 采集。

在低风险 flow 动作上实施微随机实验，贝叶斯估计因果效应。
Phase 38: 新增 record_outcome() + SQLite 持久化 + aggregate_outcomes()。
"""

import json
import random
import sqlite3
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "coherence.db"


@dataclass
class MRTConfig:
    """MRT 实验配置，默认值来自合约。"""
    randomization_rate: float = 0.2
    window_hours: int = 24
    eligible_action_types: tuple = ("challenge", "probe", "reflect", "scaffold")
    excluded_action_types: tuple = ("suggest", "defer")
    outcome_metrics: tuple = ("engagement_score", "completion_rate", "satisfaction_rating")
    min_sample_per_variant: int = 10
    confidence_level: float = 0.95

    @classmethod
    def from_dict(cls, d: dict) -> "MRTConfig":
        return cls(
            randomization_rate=d.get("randomization_rate", 0.2),
            window_hours=d.get("window_hours", 24),
            eligible_action_types=tuple(d.get("eligible_action_types",
                ["challenge", "probe", "reflect", "scaffold"])),
            outcome_metrics=tuple(d.get("outcome_metrics",
                ["engagement_score", "completion_rate", "satisfaction_rating"])),
            min_sample_per_variant=d.get("estimation", {}).get(
                "min_sample_per_variant", 10),
        )


@dataclass
class MRTAssignment:
    """单次 MRT 变体分配结果。"""
    variant_id: str | None = None
    variant_name: str | None = None
    is_variant: bool = False
    delta: float = 0.0
    dimension: str = "style"
    trace_id: str = ""
    window_id: str = ""
    assigned_at_utc: str = ""

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "variant_name": self.variant_name,
            "is_variant": self.is_variant,
            "delta": self.delta,
            "dimension": self.dimension,
            "trace_id": self.trace_id,
            "window_id": self.window_id,
            "assigned_at_utc": self.assigned_at_utc,
        }


@dataclass
class MRTOutcome:
    """S38.1: 单次 MRT 变体的 outcome 信号（原始特征，非教学评分）."""
    variant_id: str | None = None
    trace_id: str = ""
    session_id: str = ""
    action_type: str = ""
    response_length: int = 0
    has_steps: bool = False
    has_example: bool = False
    transport_status: str = "ok"
    created_at_utc: str = ""

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "action_type": self.action_type,
            "response_length": self.response_length,
            "has_steps": self.has_steps,
            "has_example": self.has_example,
            "transport_status": self.transport_status,
            "created_at_utc": self.created_at_utc,
        }


def _ensure_mrt_outcome_table() -> None:
    """创建 mrt_outcomes 表（幂等）."""
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mrt_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at_utc TEXT NOT NULL,
                variant_id TEXT DEFAULT '',
                trace_id TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                action_type TEXT DEFAULT '',
                response_length INTEGER DEFAULT 0,
                has_steps INTEGER DEFAULT 0,
                has_example INTEGER DEFAULT 0,
                transport_status TEXT DEFAULT 'ok'
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


class MRTExperiment:
    """MRT 实验管理器。"""

    VARIANTS = [
        # Style 变体（Phase 7 原有）
        {"id": "A", "name": "鼓励型", "delta": 0.2, "dimension": "style"},
        {"id": "B", "name": "反思型", "delta": -0.1, "dimension": "style"},
        # Strategy 变体（Phase 38 S38.2 新增）
        {"id": "S_scaffold_first", "name": "脚手架优先", "override_action_type": "scaffold", "dimension": "strategy"},
        {"id": "S_suggest_first", "name": "建议优先", "override_action_type": "suggest", "dimension": "strategy"},
    ]

    # S38.2: 不可被 strategy 变体覆盖的安全 action_type
    PROTECTED_ACTION_TYPES = {"pulse", "defer", "probe"}

    def __init__(self, config: MRTConfig | None = None):
        self.config = config or MRTConfig()
        self._assignments: list[MRTAssignment] = []

    def get_strategy_override(self, assignment: MRTAssignment) -> str | None:
        """S38.2: 从 strategy 变体中提取 action_type 覆盖值."""
        if not assignment.is_variant or assignment.dimension != "strategy":
            return None
        for v in self.VARIANTS:
            if v["id"] == assignment.variant_id:
                return v.get("override_action_type")
        return None

    def current_window_id(self) -> str:
        now = datetime.now(timezone.utc)
        epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
        elapsed_hours = (now - epoch).total_seconds() / 3600
        window_index = int(elapsed_hours // self.config.window_hours)
        return f"win_{window_index:08d}"

    def _window_assignments(self, window_id: str) -> list[MRTAssignment]:
        return [a for a in self._assignments if a.window_id == window_id]

    def _window_variant_count(self, window_id: str) -> int:
        return sum(1 for a in self._window_assignments(window_id) if a.is_variant)

    def _window_total_count(self, window_id: str) -> int:
        return len(self._window_assignments(window_id))

    def eligible(self, action_type: str) -> bool:
        return action_type in self.config.eligible_action_types

    def assign(self, action_type: str, context: dict | None = None,
               trace_id: str = "") -> MRTAssignment:
        if not self.eligible(action_type):
            return MRTAssignment(
                variant_id=None, variant_name=None, is_variant=False,
                trace_id=trace_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )

        window_id = self.current_window_id()
        total = self._window_total_count(window_id)
        variants = self._window_variant_count(window_id)
        current_rate = variants / total if total > 0 else 0

        if current_rate >= self.config.randomization_rate:
            assignment = MRTAssignment(
                variant_id=None, variant_name=None, is_variant=False,
                trace_id=trace_id, window_id=window_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        elif random.random() < self.config.randomization_rate:
            variant = random.choice(self.VARIANTS)
            assignment = MRTAssignment(
                variant_id=variant["id"],
                variant_name=variant["name"],
                is_variant=True,
                delta=variant.get("delta", 0.0),
                dimension=variant["dimension"],
                trace_id=trace_id,
                window_id=window_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        else:
            assignment = MRTAssignment(
                variant_id=None, variant_name=None, is_variant=False,
                trace_id=trace_id, window_id=window_id,
                assigned_at_utc=datetime.now(timezone.utc).isoformat(),
            )

        self._assignments.append(assignment)
        return assignment

    def record_outcome(self, outcome: MRTOutcome) -> None:
        """S38.1: 持久化一条 MRT outcome 到 SQLite."""
        try:
            _ensure_mrt_outcome_table()
            conn = sqlite3.connect(str(_DB_PATH))
            conn.execute(
                """INSERT INTO mrt_outcomes
                   (created_at_utc, variant_id, trace_id, session_id,
                    action_type, response_length, has_steps, has_example,
                    transport_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    outcome.variant_id or "",
                    outcome.trace_id,
                    outcome.session_id,
                    outcome.action_type,
                    outcome.response_length,
                    1 if outcome.has_steps else 0,
                    1 if outcome.has_example else 0,
                    outcome.transport_status,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # outcome 持久化失败不阻塞主流程

    @staticmethod
    def aggregate_outcomes() -> dict:
        """S38.3: 按 variant_id 聚合 outcome，返回 success/failure 计数."""
        _ensure_mrt_outcome_table()
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            rows = conn.execute(
                """SELECT variant_id, response_length, has_steps, has_example, transport_status
                   FROM mrt_outcomes
                   WHERE variant_id IS NOT NULL AND variant_id != ''"""
            ).fetchall()
            conn.close()
        except Exception:
            return {}

        variants: dict[str, dict] = {}
        for variant_id, resp_len, has_steps, has_example, transport in rows:
            if variant_id not in variants:
                variants[variant_id] = {"total": 0, "success": 0}
            variants[variant_id]["total"] += 1
            # success 条件：基本 + 增强
            basic_ok = resp_len >= 40 and transport == "ok"
            enhanced_ok = bool(has_steps) or bool(has_example)
            if basic_ok and enhanced_ok:
                variants[variant_id]["success"] += 1
        return variants

    def window_stats(self, window_id: str | None = None) -> dict:
        wid = window_id or self.current_window_id()
        assigns = self._window_assignments(wid)
        total = len(assigns)
        variants = sum(1 for a in assigns if a.is_variant)
        return {
            "window_id": wid,
            "total_assignments": total,
            "variant_count": variants,
            "control_count": total - variants,
            "variant_rate": round(variants / total, 4) if total > 0 else 0.0,
        }


def generate_variant_comparison_report(output_dir: str | None = None) -> dict:
    """S38.3: 从 mrt_outcomes 聚合数据，运行贝叶斯估计，产出对比报告."""
    aggregated = MRTExperiment.aggregate_outcomes()
    if not aggregated or len(aggregated) < 2:
        return {"status": "insufficient_data", "variants": len(aggregated), "note": "need at least 2 variants with data"}

    estimator = BayesianEstimator()
    # Use the variant with most samples as "control" (likely scaffold_first)
    sorted_variants = sorted(aggregated.items(), key=lambda x: -x[1]["total"])
    control_id, control_data = sorted_variants[0]
    comparisons = []
    min_sample = 10

    for variant_id, data in sorted_variants[1:]:
        est = estimator.estimate_binary(
            variant_successes=data["success"],
            variant_total=data["total"],
            control_successes=control_data["success"],
            control_total=control_data["total"],
        )
        est["variant_id"] = variant_id
        est["control_id"] = control_id
        est["sample_size_warning"] = (
            data["total"] < min_sample or control_data["total"] < min_sample
        )
        comparisons.append(est)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "control": {"variant_id": control_id, "total": control_data["total"], "success": control_data["success"]},
        "comparisons": comparisons,
        "min_sample_per_variant": min_sample,
        "note": "effect_size > 0 favors variant; posterior_overlap near 0 = clear separation",
    }

    if output_dir:
        out_path = Path(output_dir) / "mrt_variant_comparison.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report


class BayesianEstimator:
    """贝叶斯因果效应估计器。Beta-Bernoulli 共轭先验。"""

    def __init__(self, alpha_prior: float = 1.0, beta_prior: float = 1.0):
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior

    def estimate_binary(self, variant_successes: int, variant_total: int,
                        control_successes: int, control_total: int) -> dict:
        a_v = self.alpha_prior + variant_successes
        b_v = self.beta_prior + variant_total - variant_successes
        a_c = self.alpha_prior + control_successes
        b_c = self.beta_prior + control_total - control_successes

        mean_v = a_v / (a_v + b_v)
        mean_c = a_c / (a_c + b_c)
        effect = mean_v - mean_c

        var_v = (a_v * b_v) / ((a_v + b_v) ** 2 * (a_v + b_v + 1)) if (a_v + b_v) > 0 else 0
        var_c = (a_c * b_c) / ((a_c + b_c) ** 2 * (a_c + b_c + 1)) if (a_c + b_c) > 0 else 0
        se = (var_v + var_c) ** 0.5
        ci_lower = effect - 1.96 * se
        ci_upper = effect + 1.96 * se

        overlap = self._posterior_overlap(a_v, b_v, a_c, b_c)

        return {
            "method": "beta_binomial",
            "variant_mean": round(mean_v, 4),
            "control_mean": round(mean_c, 4),
            "effect_size": round(effect, 4),
            "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
            "posterior_overlap": round(overlap, 4),
            "variant_n": variant_total,
            "control_n": control_total,
        }

    @staticmethod
    def _posterior_overlap(a1, b1, a2, b2, samples: int = 10000) -> float:
        """P(treatment > control) 的贝叶斯后验概率。

        对称化: 0.5=无差异, 1.0=完全重叠。
        """
        count = 0
        for _ in range(samples):
            s1 = random.betavariate(a1, b1)
            s2 = random.betavariate(a2, b2)
            if s1 > s2:
                count += 1
        return 2.0 * min(count / samples, 1.0 - count / samples)
