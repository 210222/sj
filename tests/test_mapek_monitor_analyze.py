"""S6.2 MAPE-K Monitor + Analyze 测试 — 8 tests。"""

import pytest
from src.mapek.monitor import Monitor
from src.mapek.analyze import Analyze


class TestMonitor:
    def test_ingest_adds_signal(self):
        m = Monitor()
        m.ingest({"content": "hello", "timestamp": "2026-05-03T00:00:00Z"})
        snap = m.snapshot()
        assert snap["count"] == 1

    def test_dedup_same_content_within_window(self):
        m = Monitor(dedup_window_s=10)
        m.ingest({"content": "dup", "timestamp": "2026-05-03T00:00:00Z"})
        m.ingest({"content": "dup", "timestamp": "2026-05-03T00:00:01Z"})
        assert m.snapshot()["count"] == 1

    def test_buffer_cap(self):
        m = Monitor(buffer_size=3)
        for i in range(5):
            m.ingest({"content": f"msg_{i}", "value": i})
        assert m.snapshot()["count"] == 3

    def test_flush_clears_buffer(self):
        m = Monitor()
        m.ingest({"content": "x"})
        assert len(m.flush()) == 1
        assert m.snapshot()["count"] == 0

    def test_dedup_outside_window_not_deduped(self):
        m = Monitor(dedup_window_s=0.01)
        m.ingest({"content": "same", "value": 1, "timestamp": "2026-05-03T00:00:00Z"})
        import time
        time.sleep(0.02)
        m.ingest({"content": "same", "value": 2, "timestamp": "2026-05-03T00:00:01Z"})
        assert m.snapshot()["count"] == 2


class TestAnalyze:
    def test_diagnose_returns_required_keys(self):
        a = Analyze()
        result = a.diagnose({"signals": []})
        for key in ("trends", "anomalies", "causal_signals",
                     "confidence", "summary"):
            assert key in result

    def test_anomaly_detection_works(self):
        a = Analyze()
        signals = [{"value": i} for i in [1, 1, 1, 1, 10, 1, 1]]
        result = a.diagnose({"signals": signals})
        assert len(result["anomalies"]) > 0

    def test_low_signal_confidence(self):
        a = Analyze()
        result = a.diagnose({"signals": [{"value": 1}]})
        assert result["confidence"] < 0.3

    def test_sufficient_signals_confidence(self):
        a = Analyze()
        signals = [{"value": i} for i in range(20)]
        result = a.diagnose({"signals": signals})
        assert result["confidence"] >= 0.3

    def test_constant_signal_no_anomaly(self):
        a = Analyze()
        signals = [{"value": 5} for _ in range(10)]
        result = a.diagnose({"signals": signals})
        assert len(result["anomalies"]) == 0

    def test_empty_snapshot_graceful(self):
        a = Analyze()
        result = a.diagnose({})
        for key in ("trends", "anomalies", "causal_signals", "confidence", "summary"):
            assert key in result
        assert len(result["anomalies"]) == 0

    def test_metrics_skip_index_keys(self):
        a = Analyze()
        signals = [{"index": i, "value": i % 3} for i in range(10)]
        metrics = a._detectable_metrics(signals)
        assert "index" not in metrics
        assert "value" in metrics
