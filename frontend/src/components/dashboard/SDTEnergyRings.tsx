/** SDTEnergyRings — 三环能量图.

 * 设计文档第 3.2 节:
 * - 三维嵌套能量环: 自主性/胜任感/关联性
 * - 每次积极互动 → 对应能量环流体色彩饱和度提升 + 发光动画
 */
import { coachColors } from '../../styles/theme';
import type { SDTRingsData } from '../../types/api';

interface SDTEnergyRingsProps {
  data: SDTRingsData;
}

const RING_CONFIG = [
  { key: 'autonomy', label: '自主性', color: coachColors.softBlue, radius: 80 },
  { key: 'competence', label: '胜任感', color: coachColors.sageGreen, radius: 56 },
  { key: 'relatedness', label: '关联性', color: coachColors.coralCandy, radius: 32 },
];

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg - 90) * (Math.PI / 180);
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
  return [
    'M', start.x, start.y,
    'A', r, r, 0, largeArcFlag, 0, end.x, end.y,
  ].join(' ');
}

export function SDTEnergyRings({ data }: SDTEnergyRingsProps) {
  const cx = 100;
  const cy = 100;

  return (
    <div
      className="animate-pulse-in"
      style={{
        background: 'var(--color-warm-white)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-lg)',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <h3
        style={{
          fontSize: 16,
          fontWeight: 600,
          color: 'var(--color-deep-mocha)',
          marginBottom: 'var(--space-md)',
          textAlign: 'center',
        }}
      >
        动机能量
      </h3>

      <svg viewBox="0 0 200 200" style={{ display: 'block', margin: '0 auto' }}>
        {/* 背景环 */}
        {RING_CONFIG.map((ring) => (
          <circle
            key={`bg-${ring.key}`}
            cx={cx}
            cy={cy}
            r={ring.radius}
            fill="none"
            stroke={coachColors.lavenderGray}
            strokeWidth={8}
            opacity={0.3}
          />
        ))}

        {/* 数据环 */}
        {RING_CONFIG.map((ring) => {
          const value = data[ring.key as keyof SDTRingsData] as number || 0;
          const angle = Math.max(1, value * 360);
          return (
            <g key={`data-${ring.key}`}>
              <path
                d={describeArc(cx, cy, ring.radius, 0, angle)}
                fill="none"
                stroke={ring.color}
                strokeWidth={8}
                strokeLinecap="round"
                className="animate-fluid-fill"
                style={{ filter: `drop-shadow(0 0 ${value * 8}px ${ring.color})` }}
              />
              {/* 端点 */}
              {angle > 5 && (
                <circle
                  cx={polarToCartesian(cx, cy, ring.radius, angle).x}
                  cy={polarToCartesian(cx, cy, ring.radius, angle).y}
                  r={5}
                  fill={ring.color}
                  className="animate-glow"
                />
              )}
            </g>
          );
        })}

        {/* 中心文字 */}
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dominantBaseline="central"
          style={{
            fontSize: 14,
            fontWeight: 600,
            fill: 'var(--color-deep-mocha)',
          }}
        >
          SDT
        </text>
      </svg>

      {/* 图例 */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-lg)', marginTop: 'var(--space-md)' }}>
        {RING_CONFIG.map((ring) => {
          const value = data[ring.key as keyof SDTRingsData] as number || 0;
          return (
            <div key={ring.key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: ring.color,
                  display: 'inline-block',
                }}
              />
              <span style={{ fontSize: 12, color: 'var(--color-deep-mocha)' }}>
                {ring.label} {Math.round(value * 100)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
