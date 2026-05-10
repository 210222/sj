/** useCoachState — 全局教练状态管理. */

import { useState, useCallback } from 'react';
import type { CoachState, ChatMessage, TTMStage, BlockingMode } from '../types/coach';

function loadInitialState(): CoachState {
  const token = sessionStorage.getItem('coherence_token') || '';
  const sessionId = sessionStorage.getItem('coherence_session_id') || '';
  return {
    sessionId,
    token,
    ttmStage: null,
    sdtProfile: null,
    flowChannel: null,
    messages: [],
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
    setState((s) => ({ ...s, messages: [...s.messages, msg] }));
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
    setTTMStage,
    setSDTProfile,
    setBlockingMode,
    incrementPulse,
    setExcursionActive,
    setFlowChannel,
  };
}
