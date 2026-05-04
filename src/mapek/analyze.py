"""MAPE-K Analyze — 分析层：趋势检测 + 异常识别 + 因果信号提取。"""


class Analyze:
    """分析层：接收 monitor_snapshot，输出 analysis_report。

    diagnose(monitor_snapshot) → analysis_report
    """

    def __init__(self, min_confidence: float = 0.3):
        self._min_conf = min_confidence

    # 数值型键名中跳过非业务指标
    _SKIP_METRICS = {"index", "id", "count", "timestamp", "seq"}

    def diagnose(self, snapshot: dict) -> dict:
        """对 Monitor snapshot 做分析诊断。"""
        signals = snapshot.get("signals", [])
        anomalies = self._detect_anomalies(signals)
        return {
            "trends": self._detect_trends(signals),
            "anomalies": anomalies,
            "causal_signals": self._extract_causal_signals(signals),
            "confidence": self._compute_confidence(signals),
            "summary": self._summarize(signals, anomalies),
        }

    def _detect_trends(self, signals: list[dict]) -> list[dict]:
        if len(signals) < 4:
            return [{"metric": "insufficient_data", "direction": "unknown"}]

        half = len(signals) // 2
        recent = signals[half:]
        older = signals[:half]

        trends = []
        for metric in self._detectable_metrics(signals):
            older_avg = self._avg_metric(older, metric)
            recent_avg = self._avg_metric(recent, metric)
            if recent_avg > older_avg * 1.1:
                direction = "rising"
            elif recent_avg < older_avg * 0.9:
                direction = "falling"
            else:
                direction = "stable"
            trends.append({
                "metric": metric, "direction": direction,
                "older_avg": older_avg, "recent_avg": recent_avg,
            })
        return trends

    def _detect_anomalies(self, signals: list[dict]) -> list[dict]:
        if len(signals) < 3:
            return []
        anomalies = []
        for metric in self._detectable_metrics(signals):
            values = [s.get(metric, 0) for s in signals if metric in s]
            if not values:
                continue
            avg = sum(values) / len(values)
            var = sum((v - avg) ** 2 for v in values) / len(values)
            if var == 0:
                continue  # 常数信号无异常
            std = var ** 0.5
            for i, s in enumerate(signals):
                val = s.get(metric, 0)
                if abs(val - avg) > 2 * std:
                    anomalies.append({
                        "index": i, "metric": metric,
                        "value": val, "expected": round(avg, 4),
                        "deviation_std": round(abs(val - avg) / std, 2),
                    })
        return anomalies

    def _extract_causal_signals(self, signals: list[dict]) -> list[dict]:
        return [{"note": "Lightweight correlation analysis — requires MRT for causal claims"}]

    def _compute_confidence(self, signals: list[dict]) -> float:
        if len(signals) < 2:
            return 0.0
        scale = 1.0 - self._min_conf
        return round(min(1.0, self._min_conf + len(signals) / 20.0 * scale), 4)

    def _summarize(self, signals: list[dict], anomalies: list[dict]) -> str:
        count = len(signals)
        anomaly_count = len(anomalies)
        if anomaly_count > count * 0.3:
            return f"High anomaly ratio ({anomaly_count}/{count}) — recommend intervention"
        elif anomaly_count > 0:
            return f"Acceptable state with {anomaly_count} minor anomalies"
        return "Normal operation — no anomalies detected"

    @staticmethod
    def _detectable_metrics(signals: list[dict]) -> list[str]:
        if not signals:
            return []
        numeric_keys = []
        for k, v in signals[0].items():
            if isinstance(v, (int, float)) and k not in Analyze._SKIP_METRICS:
                numeric_keys.append(k)
        return numeric_keys

    @staticmethod
    def _avg_metric(signals: list[dict], metric: str) -> float:
        vals = [s.get(metric, 0) for s in signals if metric in s]
        return sum(vals) / len(vals) if vals else 0.0
