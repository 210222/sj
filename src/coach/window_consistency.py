"""S8.2 窗口一致性门禁 (Window Gate) — gate 8 运行时实现。

Schema 版本 + 窗口一致性 + 数据新鲜度 三维检查。
"""

from dataclasses import dataclass
from datetime import datetime, timezone


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class ComponentVersion:
    """单个组件上报的版本信息。"""
    component: str             # mrt / diagnostics / gates / clock
    window_id: str             # 窗口标识
    schema_version: str         # schema 版本号
    data_timestamp: str         # ISO 8601
    data_age_seconds: float     # 数据年龄（秒）


@dataclass
class WindowConsistencyResult:
    """窗口一致性检查结果。"""
    all_consistent: bool
    version_count: int
    max_version_drift: int
    fresh: bool
    max_data_age_seconds: float
    detail: str = ""
    evaluated_at_utc: str = ""

    def window_schema_version_consistency(self) -> dict:
        """gate 8 需要的 5 字段。"""
        return {
            "all_consistent": self.all_consistent,
            "version_count": self.version_count,
            "max_version_drift": self.max_version_drift,
            "fresh": self.fresh,
            "max_data_age_seconds": self.max_data_age_seconds,
        }

    def to_dict(self) -> dict:
        return {
            **self.window_schema_version_consistency(),
            "detail": self.detail,
            "evaluated_at_utc": self.evaluated_at_utc,
        }


class WindowConsistencyChecker:
    """窗口一致性检查器 — 只读，验证数据一致性。"""

    def __init__(self, max_version_drift: int = 0, max_age_seconds: float = 3600.0):
        self.max_version_drift = max_version_drift
        self.max_age_seconds = max_age_seconds

    def check(self, versions: list[ComponentVersion]) -> WindowConsistencyResult:
        if not versions:
            return WindowConsistencyResult(
                all_consistent=True, version_count=0, max_version_drift=0,
                fresh=True, max_data_age_seconds=0.0,
                detail="无版本数据，跳过窗口一致性检查",
                evaluated_at_utc=_now_utc(),
            )

        # Schema 版本一致
        schema_versions = set(v.schema_version for v in versions)
        unique_versions = len(schema_versions)
        max_drift = max(0, unique_versions - 1) if unique_versions > 0 else 0
        version_ok = max_drift <= self.max_version_drift

        # 窗口一致
        window_ids = set(v.window_id for v in versions if v.window_id)
        window_ok = len(window_ids) <= 1

        # 数据新鲜度
        max_age = max(v.data_age_seconds for v in versions) if versions else 0.0
        fresh = max_age <= self.max_age_seconds

        all_ok = version_ok and window_ok and fresh

        failures = []
        if not version_ok:
            failures.append(f"版本漂移: {unique_versions} 个不同版本 (允许 ≤{self.max_version_drift})")
        if not window_ok:
            failures.append(f"窗口不一致: {len(window_ids)} 个不同窗口")
        if not fresh:
            failures.append(f"数据过期: max_age={max_age:.0f}s (允许 ≤{self.max_age_seconds}s)")

        return WindowConsistencyResult(
            all_consistent=all_ok,
            version_count=unique_versions,
            max_version_drift=max_drift,
            fresh=fresh,
            max_data_age_seconds=round(max_age, 2),
            detail="; ".join(failures) if failures else "所有检查通过",
            evaluated_at_utc=_now_utc(),
        )
