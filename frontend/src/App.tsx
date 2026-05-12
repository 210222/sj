/** Coherence Coach — React SPA 根组件. */

import { useState, useCallback, useEffect } from 'react';
import { useCoachState } from './hooks/useCoachState';
import { useAdaptivePulse } from './hooks/useAdaptivePulse';
import { useWebSocket } from './hooks/useWebSocket';
import { ChatBubble } from './components/chat/ChatBubble';
import { ChatInput } from './components/chat/ChatInput';
import { PulsePanel } from './components/chat/PulsePanel';
import { ExcursionOverlay } from './components/chat/ExcursionOverlay';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { TTMStageCard } from './components/dashboard/TTMStageCard';
import { SDTEnergyRings } from './components/dashboard/SDTEnergyRings';
import { GateShieldBadge } from './components/dashboard/GateShieldBadge';
import { getUserDashboard } from './api/client';
import type { TTMRadarData, SDTRingsData } from './types/api';
import { createSession, sendMessage, respondPulse } from './api/client';
import { getTTMUI } from './utils/stateMachine';
import { applyColorAdaptation } from './utils/colorAdapt';
import { coachColors } from './styles/theme';
import type { ChatMessage, TTMStage } from './types/coach';
import type { PulseEvent } from './types/api';

let msgCounter = 0;
function nextMsgId() {
  return `msg-${Date.now()}-${++msgCounter}`;
}

/** 从 CoachAgent DSL payload 中提取可显示文本.
 *  不同 action_type 使用不同字段名.
 *  如果 payload 内容太简短（DSL 标签），格式化为可读消息。
 */
function extractPayloadText(
  payload: Record<string, unknown> | undefined,
  actionType?: string,
): string {
  if (!payload || typeof payload !== 'object') return '';
  const textFields = ['statement', 'question', 'option', 'step', 'problem', 'reason', 'prompt'];
  for (const field of textFields) {
    const val = payload[field];
    if (typeof val === 'string' && val.trim() && val !== 'general') return val;
  }
  // fallback: 根据 action_type 生成可读消息
  const actionLabels: Record<string, string> = {
    suggest: '好的，我们来探索一下这个话题。',
    challenge: '试试这个有点难度的挑战。',
    probe: '让我来检验一下你的理解。',
    reflect: '停下来想一想这个问题。',
    scaffold: '一步步来，我会引导你。',
    defer: '好的，我们先暂停这个话题。',
    pulse: '确认一下你的选择。',
    excursion: '进入探索模式，自由思考。',
  };
  return actionLabels[actionType || ''] || '我理解了，继续吧。';
}

export function App() {
  const {
    state,
    setSession,
    addMessage,
    dismissAwakening,
    setTTMStage,
    setSDTProfile,
    setBlockingMode,
    setExcursionActive,
    setFlowChannel,
  } = useCoachState();

  const { getBlockingMode, recordPulse } = useAdaptivePulse(state.sessionId);
  const [pendingPulse, setPendingPulse] = useState<PulseEvent | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<string>('connecting');
  const [isLoading, setIsLoading] = useState(false);
  // Phase 13x: 仪表盘可视化数据
  const [dashTTM, setDashTTM] = useState<TTMRadarData | null>(null);
  const [dashSDT, setDashSDT] = useState<SDTRingsData | null>(null);
  // Phase 13x: 侧边栏打开时加载仪表盘数据
  useEffect(() => {
    if (sidebarOpen && state.sessionId) {
      getUserDashboard(state.sessionId).then((d) => {
        setDashTTM(d.ttm_radar);
        setDashSDT(d.sdt_rings);
      }).catch(() => {});
    }
  }, [sidebarOpen, state.sessionId]);

  // 初始化会话
  useEffect(() => {
    applyColorAdaptation();
    if (!state.sessionId) {
      createSession().then((res) => {
        setSession(res.session_id, res.token);
        if (res.ttm_stage) setTTMStage(res.ttm_stage as TTMStage);
        if (res.sdt_scores) setSDTProfile(res.sdt_scores);
        setConnectionStatus('connected');
      }).catch(() => setConnectionStatus('error'));
    }
  }, [state.sessionId, setSession, setTTMStage, setSDTProfile]);

  // WebSocket
  const handleWSMessage = useCallback((msg: Record<string, unknown>) => {
    if (msg.type === 'coach_response') {
      const payload = (msg.payload ?? {}) as Record<string, unknown>;
      const passport = (msg.domain_passport ?? {}) as Record<string, unknown>;
      addMessage({
        id: nextMsgId(),
        role: 'coach',
        content: extractPayloadText(payload, msg.action_type as string),
        actionType: msg.action_type as ChatMessage['actionType'],
        sourceTag: typeof passport.source_tag === 'string'
          ? passport.source_tag as ChatMessage['sourceTag']
          : undefined,
        timestamp: new Date().toISOString(),
      });
      if (msg.ttm_stage) setTTMStage(msg.ttm_stage as TTMStage);
      if (msg.sdt_profile) setSDTProfile(msg.sdt_profile as Record<string, number>);
      if (msg.flow_channel) setFlowChannel(msg.flow_channel as string);
    }
  }, [addMessage, setTTMStage, setSDTProfile, setFlowChannel]);

  const handlePulseEvent = useCallback((msg: Record<string, unknown>) => {
    const mode = getBlockingMode();
    setPendingPulse({
      pulse_id: msg.pulse_id as string,
      statement: msg.statement as string,
      accept_label: (msg.accept_label as string) || '我接受',
      rewrite_label: (msg.rewrite_label as string) || '我改写前提',
      blocking_mode: mode,
    });
    setBlockingMode(mode);
  }, [getBlockingMode, setBlockingMode]);

  useWebSocket({
    sessionId: state.sessionId,
    onMessage: handleWSMessage,
    onPulseEvent: handlePulseEvent,
  });

  const handleSendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMsg);

    if (!state.sessionId) return;

    setIsLoading(true);
    const timeout = setTimeout(() => setIsLoading(false), 30000);
    try {
      const res = await sendMessage(state.sessionId, text);
      addMessage({
        id: nextMsgId(),
        role: 'coach',
        content: extractPayloadText(res.payload as Record<string, unknown> | undefined, res.action_type),
        actionType: res.action_type as ChatMessage['actionType'],
        sourceTag: typeof res.domain_passport?.source_tag === 'string'
          ? res.domain_passport.source_tag as ChatMessage['sourceTag']
          : undefined,
        timestamp: new Date().toISOString(),
        pulse: res.pulse ?? undefined,
        // Phase 19-26: 教学元数据
        llm_generated: res.llm_generated ?? undefined,
        difficulty_contract: res.difficulty_contract ?? undefined,
        personalization_evidence: res.personalization_evidence ?? undefined,
        memory_status: res.memory_status ?? undefined,
        options: (res.payload as any)?.options ?? undefined,
        awakening: res.awakening as ChatMessage['awakening'] ?? undefined,
      });
      if (res.ttm_stage) setTTMStage(res.ttm_stage as TTMStage);
      if (res.sdt_profile) setSDTProfile(res.sdt_profile);
      if (res.pulse) setPendingPulse(res.pulse);
      if (res.awakening) {
        addMessage({
          id: nextMsgId(),
          role: 'coach',
          content: '',
          actionType: 'awakening' as ChatMessage['actionType'],
          timestamp: new Date().toISOString(),
          awakening: res.awakening as ChatMessage['awakening'],
        });
      }
      if (res.sdt_profile) setDashSDT(res.sdt_profile as unknown as SDTRingsData);
    } catch {
      addMessage({
        id: nextMsgId(),
        role: 'coach',
        content: '抱歉，连接出现问题，请稍后再试。',
        timestamp: new Date().toISOString(),
      });
    }
    clearTimeout(timeout);
    setIsLoading(false);
  }, [state.sessionId, addMessage, setTTMStage, setSDTProfile]);

  // Phase 29: 选项按钮点击 → 发送消息
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as string;
      if (detail) handleSendMessage(detail);
    };
    window.addEventListener('coach-option-click', handler);
    return () => window.removeEventListener('coach-option-click', handler);
  }, [handleSendMessage]);

  const handlePulseAccept = useCallback(() => {
    if (!pendingPulse) return;
    recordPulse();
    respondPulse(state.sessionId, pendingPulse.pulse_id, 'accept').finally(() => {
      setPendingPulse(null);
    });
  }, [state.sessionId, pendingPulse, recordPulse]);

  const handlePulseRewrite = useCallback((content: string) => {
    if (!pendingPulse) return;
    recordPulse();
    respondPulse(state.sessionId, pendingPulse.pulse_id, 'rewrite', content).finally(() => {
      setPendingPulse(null);
    });
  }, [state.sessionId, pendingPulse, recordPulse]);

  const ttmUI = getTTMUI(state.ttmStage);

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        background: state.excursionActive ? coachColors.charcoal : coachColors.warmWhite,
        transition: 'background 300ms ease',
      }}
    >
      <ExcursionOverlay active={state.excursionActive} onExit={() => setExcursionActive(false)} />

      {/* 侧边仪表盘 */}
      <aside
        style={{
          width: sidebarOpen ? 320 : 0,
          overflow: 'hidden',
          transition: 'width 300ms ease',
          borderRight: sidebarOpen ? `1px solid ${coachColors.lavenderGray}` : 'none',
          background: 'var(--color-warm-white)',
        }}
      >
        {sidebarOpen && (
          <div style={{ padding: 'var(--space-md)', overflowY: 'auto', height: '100vh' }}>
            <h4 style={{ marginBottom: 'var(--space-sm)', color: 'var(--color-deep-mocha)', fontSize: 13 }}>
              {state.sessionId ? `Session: ${state.sessionId.slice(0, 8)}...` : 'Loading...'}
            </h4>
            <div style={{ marginBottom: 'var(--space-md)' }}>
              <GateShieldBadge overall={state.blockingMode === 'soft' ? 'warn' : 'pass'} />
            </div>
            {dashTTM && <TTMStageCard data={dashTTM} />}
            <div style={{ height: 'var(--space-md)' }} />
            {dashSDT && <SDTEnergyRings data={dashSDT} />}
            <div style={{ height: 'var(--space-lg)' }} />
            <SettingsPanel />
          </div>
        )}
      </aside>

      {/* 主聊天区 */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', maxWidth: 720, margin: '0 auto' }}>
        {/* 顶部栏 */}
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--space-md)',
            borderBottom: `1px solid ${coachColors.lavenderGray}`,
          }}
        >
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: 20,
              cursor: 'pointer',
              color: 'var(--color-deep-mocha)',
            }}
          >
            ☰
          </button>
          <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-deep-mocha)' }}>
            Coherence Coach
          </span>
          <span style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: connectionStatus === 'connected' ? coachColors.sageGreen : coachColors.coralCandy,
            display: 'inline-block',
          }} />
        </header>

        {/* Phase 28: 教学状态指示器 */}
        {state.messages.length > 0 && (() => {
          const last = state.messages[state.messages.length - 1];
          return (
            <div style={{
              display: 'flex', gap: 8, alignItems: 'center',
              padding: '4px 16px', fontSize: 12,
              background: 'var(--color-warm-white)',
              borderBottom: '1px solid var(--color-lavender-gray)',
            }}>
              {last?.llm_generated ? (
                <span style={{ padding: '1px 8px', borderRadius: 8,
                  background: coachColors.sageGreen, color: '#fff' }}>LLM 教学</span>
              ) : (
                <span style={{ padding: '1px 8px', borderRadius: 8,
                  background: coachColors.lavenderGray, color: coachColors.deepMocha }}>规则教学</span>
              )}
              {last?.difficulty_contract?.level != null && (
                <span>难度: {String((({easy:'简单',medium:'中等',hard:'困难'} as Record<string,string>)[String(last.difficulty_contract.level)] || last.difficulty_contract.level))}</span>
              )}
              {last?.actionType && last.actionType !== 'awakening' && (
                <span>策略: {last.actionType}</span>
              )}
              {state.ttmStage && (
                <span>阶段: {state.ttmStage}</span>
              )}
            </div>
          );
        })()}

        {/* 消息列表 */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            paddingTop: 'var(--space-md)',
          }}
        >
          {state.messages.length === 0 && (
            <div style={{ textAlign: 'center', padding: 'var(--space-xl)', color: 'var(--color-clay-brown)' }}>
              <p>欢迎使用 Coherence 教练</p>
              <p style={{ fontSize: 13, marginTop: 'var(--space-xs)' }}>我是你的认知主权保护教练，开始对话吧</p>
            </div>
          )}
          {state.messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              onEnableRecommended={() => { dismissAwakening(); handleSendMessage('启用推荐能力'); }}
              onSkipAwakening={() => { dismissAwakening(); handleSendMessage('不用'); }}
            />
          ))}

          {/* 等待回复动画 */}
          {isLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', marginBottom: 8 }}>
              <span style={{ fontSize: 13, color: 'var(--color-clay-brown)' }}>教练正在思考</span>
              <span className="typing-dots" style={{ display: 'inline-flex', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-sage-green)', animation: 'typing-bounce 1.4s infinite' }} />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-sage-green)', animation: 'typing-bounce 1.4s 0.2s infinite' }} />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-sage-green)', animation: 'typing-bounce 1.4s 0.4s infinite' }} />
              </span>
            </div>
          )}

          {/* 脉冲面板 */}
          {pendingPulse && (
            <PulsePanel
              statement={pendingPulse.statement}
              acceptLabel={pendingPulse.accept_label}
              rewriteLabel={pendingPulse.rewrite_label}
              blockingMode={pendingPulse.blocking_mode}
              onAccept={handlePulseAccept}
              onRewrite={handlePulseRewrite}
            />
          )}
        </div>

        {/* 输入区 */}
        <ChatInput
          inputMode={state.excursionActive ? 'explore' : ttmUI.inputMode}
          onSend={handleSendMessage}
        />
      </main>
    </div>
  );
}
