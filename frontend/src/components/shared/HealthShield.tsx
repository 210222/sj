/** HealthShield — 三色健康盾牌徽章.

 * C 端用户视角，不暴露 gate/pipeline/audit/P0/P1 等技术术语。
 * 三种状态使用不同 SVG 路径以提供冗余语义。
 */
interface HealthShieldProps {
  status: 'pass' | 'warn' | 'block';
  label?: string;
  size?: number;
}

// pass: 盾牌 + 对勾
const SHIELD_PASS = 'M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5zM10 15l-3-3 1.41-1.41L10 12.17l5.59-5.59L17 8l-7 7z';
// warn: 盾牌 + 感叹号
const SHIELD_WARN = 'M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5zM12 8.5c-.83 0-1.5.67-1.5 1.5v3c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5v-3c0-.83-.67-1.5-1.5-1.5zM12 17c-.83 0-1.5.67-1.5 1.5S11.17 20 12 20s1.5-.67 1.5-1.5S12.83 17 12 17z';
// block: 盾牌 + 叉号
const SHIELD_BLOCK = 'M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5zM8.11 7.05l9.9 9.9c-.6.7-1.3 1.35-2.09 1.92L8.08 11c.01-.01.02-.02.03-.03.57-.66 1.23-1.27 1.97-1.8l-1.97-2.12z';

const SHIELD_PATHS: Record<string, string> = {
  pass: SHIELD_PASS,
  warn: SHIELD_WARN,
  block: SHIELD_BLOCK,
};

const STATUS_COLORS: Record<string, string> = {
  pass: 'var(--color-sage-green)',
  warn: 'var(--color-coral-candy)',
  block: '#FF8A80',
};

const STATUS_LABELS: Record<string, string> = {
  pass: '系统健康',
  warn: '请注意',
  block: '已保护',
};

export function HealthShield({ status, label, size = 64 }: HealthShieldProps) {
  const fillColor = STATUS_COLORS[status] || STATUS_COLORS.pass;
  const displayLabel = label || STATUS_LABELS[status] || '';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 'var(--space-sm)',
      }}
      className="animate-pulse-in"
    >
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        style={{ transition: 'fill var(--transition-base)' }}
      >
        <path
          d={SHIELD_PATHS[status] || SHIELD_PATHS.pass}
          fill={fillColor}
          opacity={0.9}
        />
        {status === 'block' && (
          <circle
            cx="12"
            cy="12"
            r="10"
            fill="none"
            stroke="#FF8A80"
            strokeWidth="0.5"
            className="animate-ring"
          />
        )}
      </svg>
      <span
        style={{
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--color-deep-mocha)',
          textAlign: 'center',
        }}
      >
        {displayLabel}
      </span>
    </div>
  );
}
