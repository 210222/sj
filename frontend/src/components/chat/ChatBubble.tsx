/** ChatBubble — 对话气泡.

 * source_tag 渲染为小型标签标识（rule/statistical/hypothesis）.
 */
import type { ChatMessage } from '../../types/coach';
import { coachColors } from '../../styles/theme';
import { AwakeningPanel } from './AwakeningPanel';

interface ChatBubbleProps {
  message: ChatMessage;
  onPulseAccept?: () => void;
  onPulseRewrite?: (content: string) => void;
  onEnableRecommended?: () => void;
  onSkipAwakening?: () => void;
}

const SOURCE_TAG_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  rule: { bg: coachColors.softBlue, text: coachColors.deepMocha, label: '规则' },
  statistical: { bg: coachColors.lavenderGray, text: coachColors.deepMocha, label: '统计' },
  hypothesis: { bg: coachColors.coralCandy, text: coachColors.deepMocha, label: '假设' },
};

export function ChatBubble({ message, onEnableRecommended, onSkipAwakening }: ChatBubbleProps) {
  const isUser = message.role === 'user';

  if (message.actionType === 'awakening' && message.awakening) {
    return (
      <AwakeningPanel
        recommended={message.awakening.recommended}
        advanced={message.awakening.advanced}
        totalModules={message.awakening.total_modules}
        hint={message.awakening.hint}
        onEnableRecommended={() => onEnableRecommended?.()}
        onSkip={() => onSkipAwakening?.()}
      />
    );
  }

  const tagStyle = message.sourceTag ? SOURCE_TAG_STYLES[message.sourceTag] : null;

  return (
    <div
      className="animate-slide-up"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 'var(--space-md)',
        paddingInline: 'var(--space-md)',
      }}
    >
      <div
        style={{
          maxWidth: '75%',
          padding: 'var(--space-md)',
          background: isUser ? 'var(--color-bubble-user, var(--color-lavender-gray))' : 'var(--color-bubble-coach, var(--color-soft-blue))',
          color: 'var(--color-text, var(--color-deep-mocha))',
          fontSize: 15,
          lineHeight: 1.6,
          borderRadius: isUser
            ? 'var(--radius-lg) var(--radius-lg) var(--border-radius-bubble, var(--radius-sm)) var(--radius-lg)'
            : 'var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--border-radius-bubble, var(--radius-sm))',
        }}
      >
        {message.content}
      </div>

      {/* Phase 29: 选项按钮 */}
      {message.options && message.options.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6, maxWidth: '75%' }}>
          {message.options.map((opt, i) => (
            <button
              key={i}
              onClick={() => {
                const text = opt.label.replace(/\(.*\)/, '').trim();
                // 触发发送消息 (通过自定义事件)
                window.dispatchEvent(new CustomEvent('coach-option-click', { detail: text }));
              }}
              style={{
                padding: '8px 14px', borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-sage-green)',
                background: 'var(--color-warm-white)',
                color: 'var(--color-deep-mocha)',
                fontSize: 13, cursor: 'pointer', textAlign: 'left',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Phase 28: 教学标签 (仅教练消息) */}
      {!isUser && message.actionType !== 'awakening' && (
        <div style={{
          display: 'flex', gap: 4, flexWrap: 'wrap',
          marginTop: 4, fontSize: 11, opacity: 0.7,
        }}>
          {message.llm_generated ? (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: coachColors.sageGreen, color: '#fff' }}>AI</span>
          ) : (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: coachColors.lavenderGray, color: coachColors.deepMocha }}>规则</span>
          )}
          {message.difficulty_contract?.level != null && (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: coachColors.coralCandy, color: coachColors.deepMocha }}>
              难度: {({easy:'简单',medium:'中等',hard:'困难'} as Record<string,string>)[String(message.difficulty_contract.level)] || String(message.difficulty_contract.level)}
            </span>
          )}
          {(message.personalization_evidence as any)?.sources_count > 0 && (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: coachColors.softBlue, color: coachColors.deepMocha }}>
              已引用
            </span>
          )}
          {/* Phase 42: LLM observability compact tags */}
          {(message.llm_observability as any)?.runtime?.latency_ms > 0 && (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: 'var(--color-warm-white)', color: coachColors.deepMocha, border: '1px solid var(--color-lavender-gray)' }}>
              {(message.llm_observability as any).runtime.latency_ms < 1000
                ? `${Math.round((message.llm_observability as any).runtime.latency_ms)}ms`
                : `${((message.llm_observability as any).runtime.latency_ms / 1000).toFixed(1)}s`}
            </span>
          )}
          {(message.llm_observability as any)?.cache?.cache_eligible && (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: coachColors.sageGreen, color: '#fff', opacity: 0.8 }}>
              缓存
            </span>
          )}
          {(message.llm_observability as any)?.runtime?.cost_usd != null && (
            <span style={{ padding: '1px 6px', borderRadius: 8,
              background: coachColors.coralCandy, color: coachColors.deepMocha }}>
              ${(message.llm_observability as any).runtime.cost_usd.toFixed(4)}
            </span>
          )}
        </div>
      )}

      {tagStyle && (
        <span
          style={{
            display: 'inline-block',
            marginTop: 'var(--space-xs)',
            padding: '2px 8px',
            borderRadius: 10,
            fontSize: 11,
            background: tagStyle.bg,
            color: tagStyle.text,
            opacity: 0.8,
          }}
        >
          {tagStyle.label}
        </span>
      )}
    </div>
  );
}
