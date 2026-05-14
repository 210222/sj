import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAuth } from '../../src/hooks/useAuth';

beforeEach(() => {
  sessionStorage.clear();
});

describe('useAuth', () => {
  it('defaults to user role when no token', () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.role).toBe('user');
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('canView admin returns false for user role', () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.canView('admin')).toBe(false);
  });

  it('login sets role and token', () => {
    const { result } = renderHook(() => useAuth());
    act(() => { result.current.login('test-token', 'admin'); });
    expect(result.current.role).toBe('admin');
    expect(result.current.token).toBe('test-token');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.canView('admin')).toBe(true);
  });

  it('logout clears state', () => {
    const { result } = renderHook(() => useAuth());
    act(() => { result.current.login('test-token', 'admin'); });
    act(() => { result.current.logout(); });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.role).toBe('user');
    expect(result.current.canView('admin')).toBe(false);
  });

  it('debug role can view admin and debug', () => {
    const { result } = renderHook(() => useAuth());
    act(() => { result.current.login('debug-token', 'debug'); });
    expect(result.current.canView('admin')).toBe(true);
    expect(result.current.canView('debug')).toBe(true);
  });

  it('setRole changes role without changing token', () => {
    const { result } = renderHook(() => useAuth());
    act(() => { result.current.login('token', 'user'); });
    act(() => { result.current.setRole('admin'); });
    expect(result.current.role).toBe('admin');
    expect(result.current.token).toBe('token');
  });
});
