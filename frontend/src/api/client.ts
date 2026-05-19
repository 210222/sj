/** API 客户端 — axios 替代(轻量 fetch 封装) + WebSocket. */

import type {
  ChatResponse,
  HealthResponse,
  SessionResponse,
  UserDashboardResponse,
} from '../types/api';

const BASE_URL = '/api/v1';

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = sessionStorage.getItem('coherence_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.detail || err.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── 会话 ──

export function createSession(sessionId?: string, token?: string): Promise<SessionResponse> {
  return request<SessionResponse>('POST', '/session', {
    session_id: sessionId ?? null,
    token: token ?? null,
  });
}

// ── 对话 ──

export function sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
  return request<ChatResponse>('POST', '/chat', { session_id: sessionId, message });
}

// ── 脉冲 ──

export function respondPulse(
  sessionId: string,
  pulseId: string,
  decision: 'accept' | 'rewrite',
  rewriteContent?: string,
): Promise<{ status: string; next_action: unknown; blocking_mode: string }> {
  return request('POST', '/pulse/respond', {
    session_id: sessionId,
    pulse_id: pulseId,
    decision,
    rewrite_content: rewriteContent ?? null,
  });
}

// ── 远足 ──

export function enterExcursion(sessionId: string): Promise<{ status: string; excursion_id: string; theme: string }> {
  return request('POST', '/excursion/enter', { session_id: sessionId });
}

export function exitExcursion(sessionId: string, excursionId: string): Promise<{ status: string }> {
  return request('POST', '/excursion/exit', { session_id: sessionId, excursion_id: excursionId });
}

// ── 仪表盘 ──

export function getUserDashboard(sessionId: string): Promise<UserDashboardResponse> {
  return request('GET', `/dashboard/user?session_id=${encodeURIComponent(sessionId)}`);
}

// ── 健康检查 ──

export function healthCheck(): Promise<HealthResponse> {
  return request('GET', '/health');
}

// ── WebSocket ──

export function createChatWebSocket(_sessionId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const ws = new WebSocket(`${protocol}//${host}/api/v1/chat/ws`);
  ws.onopen = () => {
    // 发送轻量 ping 确认连接，不触发 LLM 调用
    ws.send(JSON.stringify({ type: 'ping' }));
  };
  return ws;
}
