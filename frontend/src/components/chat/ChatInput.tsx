/** ChatInput — 对话输入框.

 * inputMode 驱动的输入行为差异化。
 */
import { useState, useCallback, type KeyboardEvent } from 'react';
import type { InputMode } from '../../types/coach';

interface ChatInputProps {
  inputMode?: InputMode;
  onSend: (text: string) => void;
  disabled?: boolean;
}

const PLACEHOLDERS: Record<InputMode, string> = {
  suggest_only: '你想了解什么？',
  reflect_first: '先想一想，你对此感觉如何？',
  scaffold: '让我们一步步来...',
  checkin: '今天进展怎么样？',
  explore: '探索更多可能...',
  recover: '没关系，我们重新开始...',
};

export function ChatInput({ inputMode = 'suggest_only', onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState('');

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (trimmed) {
      onSend(trimmed);
      setText('');
    }
  }, [text, onSend]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div
      style={{
        display: 'flex',
        gap: 'var(--space-sm)',
        padding: 'var(--space-md)',
        background: 'var(--color-warm-white)',
        borderTop: '1px solid var(--color-lavender-gray)',
      }}
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={PLACEHOLDERS[inputMode] || '输入消息...'}
        disabled={disabled}
        rows={2}
        style={{
          flex: 1,
          resize: 'none',
          padding: 'var(--space-sm) var(--space-md)',
          border: '1px solid var(--color-lavender-gray)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--color-warm-white)',
          color: 'var(--color-deep-mocha)',
          fontSize: 15,
          lineHeight: 1.5,
          outline: 'none',
        }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        style={{
          alignSelf: 'flex-end',
          padding: 'var(--space-sm) var(--space-lg)',
          background: text.trim() ? 'var(--color-soft-blue)' : 'var(--color-lavender-gray)',
          color: 'var(--color-deep-mocha)',
          border: 'none',
          borderRadius: 'var(--radius-md)',
          fontSize: 15,
          fontWeight: 500,
          opacity: text.trim() ? 1 : 0.5,
          transition: 'all var(--transition-fast)',
        }}
      >
        发送
      </button>
    </div>
  );
}
