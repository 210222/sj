"""S8.2 窗口一致性门禁测试。"""

import pytest
from src.coach.window_consistency import (
    ComponentVersion, WindowConsistencyChecker,
)


def _cv(component="mrt", window="win_000042", schema="1.0.0",
        ts="2026-05-04T00:00:00Z", age=60.0):
    return ComponentVersion(
        component=component, window_id=window,
        schema_version=schema, data_timestamp=ts, data_age_seconds=age,
    )


class TestWindowConsistency:
    def test_all_consistent_passes(self):
        checker = WindowConsistencyChecker()
        versions = [_cv("mrt"), _cv("diag"), _cv("gates")]
        result = checker.check(versions)
        assert result.all_consistent is True
        assert result.fresh is True

    def test_version_drift_detected(self):
        checker = WindowConsistencyChecker(max_version_drift=0)
        versions = [_cv(schema="1.0.0"), _cv(schema="1.1.0")]
        result = checker.check(versions)
        assert result.all_consistent is False
        assert result.max_version_drift > 0

    def test_different_windows_fail(self):
        checker = WindowConsistencyChecker()
        versions = [_cv(window="win_A"), _cv(window="win_B")]
        result = checker.check(versions)
        assert result.all_consistent is False

    def test_stale_data_fails(self):
        checker = WindowConsistencyChecker(max_age_seconds=100)
        versions = [_cv(age=200)]  # 200s > 100s
        result = checker.check(versions)
        assert result.fresh is False

    def test_empty_versions_passes(self):
        checker = WindowConsistencyChecker()
        result = checker.check([])
        assert result.all_consistent is True
        assert result.version_count == 0

    def test_single_version_passes(self):
        checker = WindowConsistencyChecker()
        versions = [_cv()]
        result = checker.check(versions)
        assert result.all_consistent is True

    def test_wsc_output_has_5_fields(self):
        checker = WindowConsistencyChecker()
        result = checker.check([_cv()])
        wsc = result.window_schema_version_consistency()
        for key in ("all_consistent", "version_count", "max_version_drift",
                     "fresh", "max_data_age_seconds"):
            assert key in wsc, f"Missing: {key}"

    def test_fresh_data_passes(self):
        checker = WindowConsistencyChecker(max_age_seconds=3600)
        versions = [_cv(age=59)]
        result = checker.check(versions)
        assert result.fresh is True
