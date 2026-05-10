/** useAuth — RBAC 角色路由.

 * 三种视图层级:
 *   - user: 终端用户 → 盾牌 + TTM 雷达 + SDT 能量环
 *   - admin: 管理员 → GatePipeline 全展开 + 审计日志
 *   - debug: 开发调试 → 底层 Ledger 原始事件 + Gate 裁决详情
 */
import { useState, useCallback } from 'react';

export type AuthRole = 'user' | 'admin' | 'debug';

interface AuthState {
  role: AuthRole;
  token: string | null;
  isAuthenticated: boolean;
}

function loadAuth(): AuthState {
  const token = sessionStorage.getItem('coherence_token');
  const roleStr = sessionStorage.getItem('coherence_role') as AuthRole | null;
  const role = roleStr === 'admin' || roleStr === 'debug' ? roleStr : 'user';
  return {
    role,
    token: token || null,
    isAuthenticated: !!token,
  };
}

export function useAuth() {
  const [auth, setAuth] = useState<AuthState>(loadAuth);

  const setRole = useCallback((role: AuthRole) => {
    sessionStorage.setItem('coherence_role', role);
    setAuth((s) => ({ ...s, role }));
  }, []);

  const login = useCallback((token: string, role: AuthRole = 'user') => {
    sessionStorage.setItem('coherence_token', token);
    sessionStorage.setItem('coherence_role', role);
    setAuth({ role, token, isAuthenticated: true });
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem('coherence_token');
    sessionStorage.removeItem('coherence_role');
    setAuth({ role: 'user', token: null, isAuthenticated: false });
  }, []);

  const canView = useCallback((view: 'admin' | 'debug') => {
    if (view === 'admin') return auth.role === 'admin' || auth.role === 'debug';
    if (view === 'debug') return auth.role === 'debug';
    return false;
  }, [auth.role]);

  return {
    role: auth.role,
    token: auth.token,
    isAuthenticated: auth.isAuthenticated,
    setRole,
    login,
    logout,
    canView,
  };
}
