/** GateShieldBadge — 用户侧健康盾牌 (无技术术语).

 * 8 道门禁状态压缩为极简三色盾牌。
 * 不暴露 gate/pipeline/audit/P0/P1 等底层概念.
 * 阻断时使用 AI 教练拟人化话术.
 */
import { semanticColors } from '../../styles/theme';

interface GateShieldBadgeProps {
  overall: 'pass' | 'warn' | 'block';
  blockedMessage?: string;
}

const SHIELD_MESSAGES: Record<string, { label: string; detail: string }> = {
  pass: {
    label: '系统守护中',
    detail: '一切运行顺畅，你可以自由探索',
  },
  warn: {
    label: '正在留意',
    detail: '有些地方需要关注，不过不影响你继续',
  },
  block: {
    label: '已保护',
    detail: '这个问题有点复杂，让我们换一个更轻松的角度探讨',
  },
};

export function GateShieldBadge({ overall, blockedMessage }: GateShieldBadgeProps) {
  const msg = SHIELD_MESSAGES[overall] || SHIELD_MESSAGES.pass;
  const shieldColor =
    overall === 'pass' ? semanticColors.pass :
    overall === 'warn' ? semanticColors.warn :
    semanticColors.block;

  return (
    <div
      className="animate-pulse-in"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 'var(--space-sm)',
        padding: 'var(--space-lg)',
      }}
    >
      {/* 盾牌图标 */}
      <svg viewBox="0 0 24 24" width={56} height={56}>
        <path
          d="M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z"
          fill={shieldColor}
          opacity={0.85}
        />
        {overall === 'pass' && (
          <path d="M10 15l-3-3 1.41-1.41L10 12.17l5.59-5.59L17 8l-7 7z" fill="#fff" />
        )}
        {overall === 'block' && (
          <path d="M8 8l8 8M16 8l-8 8" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
        )}
      </svg>

      <span
        style={{
          fontSize: 15,
          fontWeight: 600,
          color: 'var(--color-deep-mocha)',
        }}
      >
        {msg.label}
      </span>

      <span
        style={{
          fontSize: 12,
          color: 'var(--color-clay-brown)',
          textAlign: 'center',
          maxWidth: 180,
          lineHeight: 1.5,
        }}
      >
        {blockedMessage || msg.detail}
      </span>
    </div>
  );
}
