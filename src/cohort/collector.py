"""量化自我数据聚合接口 — 阶段 2 占位壳。阶段 6 对接 Apple Health / Fitbit / Oura 等。"""


class QSCollector:
    """量化自我数据聚合接口。"""

    def pull_health_data(self, source: str = "") -> dict:
        """占位：从健康数据源拉取指标。"""
        raise NotImplementedError("QS health data source not configured — Phase 6")

    def pull_productivity_data(self, source: str = "") -> dict:
        """占位：从生产力工具拉取数据。"""
        raise NotImplementedError("QS productivity data source not configured — Phase 6")
