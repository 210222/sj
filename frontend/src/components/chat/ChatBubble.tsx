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
