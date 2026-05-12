/** useCoachState — 全局教练状态管理. */

import { useState, useCallback } from 'react';
import type { CoachState, ChatMessage, TTMStage, BlockingMode } from '../types/coach';

function loadInitialState(): CoachState {
  const token = sessionStorage.getItem('coherence_token') || '';
  const sessionId = sessionStorage.getItem('coherence_session_id') || '';
  // 从 localStorage 恢复对话历史
  let messages: any[] = [];
  if (sessionId) {
    try {
      const saved = localStorage.getItem(`coherence_messages_${sessionId}`);
      if (saved) messages = JSON.parse(saved);
    } catch { messages = []; }
  }
  return {
    sessionId,
    token,
    ttmStage: null,
    sdtProfile: null,
    flowChannel: null,
    messages,
    pulseCount: 0,
    blockingMode: 'hard',
    excursionActive: false,
  };
}

export function useCoachState() {
  const [state, setState] = useState<CoachState>(loadInitialState);

  const setSession = useCallback((sessionId: string, token: string) => {
    sessionStorage.setItem('coherence_session_id', sessionId);
    sessionStorage.setItem('coherence_token', token);
    setState((s) => ({ ...s, sessionId, token }));
  }, []);

  const addMessage = useCallback((msg: ChatMessage) => {
    setState((s) => {
      const newMessages = [...s.messages, msg];
      // 持久化到 localStorage（按 session_id 隔离）
      if (s.sessionId) {
        try { localStorage.setItem(`coherence_messages_${s.sessionId}`, JSON.stringify(newMessages)); } catch {}
      }
      return { ...s, messages: newMessages };
    });
  }, []);

  const dismissAwakening = useCallback(() => {
    setState((s) => ({
      ...s,
      messages: s.messages.filter((m) => m.actionType !== 'awakening'),
    }));
  }, []);

  const setTTMStage = useCallback((stage: TTMStage | null) => {
    setState((s) => ({ ...s, ttmStage: stage }));
  }, []);

  const setSDTProfile = useCallback((profile: Record<string, number> | null) => {
    setState((s) => ({ ...s, sdtProfile: profile }));
  }, []);

  const setBlockingMode = useCallback((mode: BlockingMode) => {
    setState((s) => ({ ...s, blockingMode: mode }));
  }, []);

  const incrementPulse = useCallback(() => {
    setState((s) => ({ ...s, pulseCount: s.pulseCount + 1 }));
  }, []);

  const setExcursionActive = useCallback((active: boolean) => {
    setState((s) => ({ ...s, excursionActive: active }));
  }, []);

  const setFlowChannel = useCallback((channel: string | null) => {
    setState((s) => ({ ...s, flowChannel: channel }));
  }, []);

  return {
    state,
    setSession,
    addMessage,
    dismissAwakening,
    setTTMStage,
    setSDTProfile,
    setBlockingMode,
    incrementPulse,
    setExcursionActive,
    setFlowChannel,
  };
}
