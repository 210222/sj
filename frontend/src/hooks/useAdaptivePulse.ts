/** useAdaptivePulse — 脉冲计数 + 降级判断.

 * sessionStorage 追踪脉冲计数，10 分钟窗口重置。
 * 与后端 PulseService 保持一致性.
 * 使用 ref 存储脉冲数据避免 stale closure。
 */
import { useState, useRef, useCallback } from 'react';
import type { BlockingMode } from '../types/coach';

const PULSE_MAX_BLOCKING = 2;
const PULSE_WINDOW_MS = 10 * 60 * 1000; // 10 分钟

interface StoredPulse {
  ts: number;
  count: number;
}

function loadPulses(sessionId: string): StoredPulse {
  try {
    const raw = sessionStorage.getItem(`pulse:${sessionId}`);
    if (raw) {
      const data: StoredPulse = JSON.parse(raw);
      if (Date.now() - data.ts < PULSE_WINDOW_MS) {
        return data;
      }
    }
  } catch { /* ignore */ }
  return { ts: Date.now(), count: 0 };
}

function savePulses(sessionId: string, data: StoredPulse): void {
  sessionStorage.setItem(`pulse:${sessionId}`, JSON.stringify(data));
}

export function useAdaptivePulse(sessionId: string) {
  const [pulseData, setPulseData] = useState<StoredPulse>(() => loadPulses(sessionId));
  // ref 保持最新值，防止 useCallback 闭包过期
  const pulseRef = useRef(pulseData);
  pulseRef.current = pulseData;

  const getBlockingMode = useCallback((): BlockingMode => {
    const current = pulseRef.current;
    const now = Date.now();
    if (now - current.ts >= PULSE_WINDOW_MS) {
      const fresh = { ts: now, count: 0 };
      setPulseData(fresh);
      savePulses(sessionId, fresh);
      return 'hard';
    }
    return current.count < PULSE_MAX_BLOCKING ? 'hard' : 'soft';
  }, [sessionId]);

  const recordPulse = useCallback(() => {
    const current = pulseRef.current;
    const now = Date.now();
    const windowReset = now - current.ts >= PULSE_WINDOW_MS;
    const next: StoredPulse = {
      ts: windowReset ? now : current.ts,
      count: windowReset ? 1 : current.count + 1,
    };
    setPulseData(next);
    savePulses(sessionId, next);
  }, [sessionId]);

  return { pulseCount: pulseData.count, getBlockingMode, recordPulse };
}
