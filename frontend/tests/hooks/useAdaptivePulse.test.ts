import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAdaptivePulse } from '../../src/hooks/useAdaptivePulse';

// 清理 sessionStorage 隔离测试
beforeEach(() => {
  sessionStorage.clear();
});

describe('useAdaptivePulse', () => {
  it('returns hard mode initially', () => {
    const { result } = renderHook(() => useAdaptivePulse('test-session'));
    expect(result.current.getBlockingMode()).toBe('hard');
  });

  it('pulseCount starts at 0', () => {
    const { result } = renderHook(() => useAdaptivePulse('test-session'));
    expect(result.current.pulseCount).toBe(0);
  });

  it('recordPulse increments count', () => {
    const { result } = renderHook(() => useAdaptivePulse('test-session'));
    act(() => { result.current.recordPulse(); });
    expect(result.current.pulseCount).toBe(1);
  });

  it('transitions to soft after 2 pulses', () => {
    const { result } = renderHook(() => useAdaptivePulse('test-session'));
    act(() => { result.current.recordPulse(); });
    act(() => { result.current.recordPulse(); });
    expect(result.current.pulseCount).toBe(2);
    expect(result.current.getBlockingMode()).toBe('soft');
  });

  it('different sessions have independent counts', () => {
    const { result: r1 } = renderHook(() => useAdaptivePulse('session-a'));
    const { result: r2 } = renderHook(() => useAdaptivePulse('session-b'));
    act(() => { r1.current.recordPulse(); });
    expect(r1.current.pulseCount).toBe(1);
    expect(r2.current.pulseCount).toBe(0);
  });
});
