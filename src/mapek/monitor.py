"""MAPE-K Monitor — 感知层：信号收集 + 缓冲 + 去重 + 格式化。"""

from datetime import datetime, timezone


class Monitor:
    """感知层：收集所有相关信号 → 缓冲 → 去重 → 格式化输出 snapshot。

    ingest(signal) → 缓冲
    snapshot() → monitor_snapshot
    flush() → 清空缓冲区
    """

    def __init__(self, buffer_size: int = 100, dedup_window_s: int = 5):
        self._buffer: list[dict] = []
        self._buffer_size = buffer_size
        self._dedup_win = dedup_window_s

    def ingest(self, signal: dict) -> None:
        """收集一个信号，自动去重和缓冲管理。"""
        if self._is_duplicate(signal):
            return
        if len(self._buffer) >= self._buffer_size:
            self._buffer.pop(0)
        self._buffer.append(signal)

    def snapshot(self) -> dict:
        """返回当前缓冲区快照。"""
        return {
            "signals": list(self._buffer),
            "count": len(self._buffer),
            "earliest": self._buffer[0].get("timestamp") if self._buffer else None,
            "latest": self._buffer[-1].get("timestamp") if self._buffer else None,
        }

    def flush(self) -> list[dict]:
        """清空缓冲区并返回历史信号。"""
        data = list(self._buffer)
        self._buffer.clear()
        return data

    def _is_duplicate(self, signal: dict) -> bool:
        if not self._buffer:
            return False
        last = self._buffer[-1]
        if signal.get("content") == last.get("content"):
            sig_ts = self._parse_ts(signal.get("timestamp"))
            last_ts = self._parse_ts(last.get("timestamp"))
            if sig_ts and last_ts and abs(sig_ts - last_ts) < self._dedup_win:
                return True
        return False

    @staticmethod
    def _parse_ts(ts_str: str | None) -> float | None:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
