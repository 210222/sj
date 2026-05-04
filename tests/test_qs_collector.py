"""S2.4 QSCollector 占位壳测试。"""

import pytest
from src.cohort import QSCollector


def test_qs_collector_imports():
    assert QSCollector is not None


def test_pull_health_data_raises():
    c = QSCollector()
    with pytest.raises(NotImplementedError, match="Phase 6"):
        c.pull_health_data("apple_health")


def test_pull_productivity_data_raises():
    c = QSCollector()
    with pytest.raises(NotImplementedError, match="Phase 6"):
        c.pull_productivity_data("rescuetime")
