/** TTMStageCard — 五维雷达图展示各阶段倾向性评分.

 * 设计文档第 3.2 节 — 用户端仪表盘.
 */
import { coachColors, ttmStageColors } from '../../styles/theme';
import type { TTMRadarData } from '../../types/api';

interface TTMStageCardProps {
  data: TTMRadarData;
}

const STAGE_LABELS: Record<string, string> = {
  precontemplation: '前意向',
  contemplation: '意向',
  preparation: '准备',
  action: '行动',
  maintenance: '维持',
};

const STAGES = ['precontemplation', 'contemplation', 'preparation', 'action', 'maintenance'] as const;

export function TTMStageCard({ data }: TTMStageCardProps) {
  if (!data || !data.current_stage) {
    return (
      <div style={{ padding: 'var(--space-lg)', textAlign: 'center', color: 'var(--color-clay-brown)' }}>
        TTM 阶段数据暂未可用
      </div>
    );
  }

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
        }}
      >
        行为阶段分析
      </h3>

      {/* 柱状图 */}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-end', height: 120, marginBottom: 'var(--space-md)' }}>
        {STAGES.map((stage) => {
          const value = data[stage as keyof TTMRadarData] as number || 0;
          const isCurrent = stage === data.current_stage;
          return (
            <div
              key={stage}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 'var(--space-xs)',
              }}
            >
              <span style={{ fontSize: 11, color: 'var(--color-clay-brown)' }}>
                {Math.round(value * 100)}%
              </span>
              <div
                className="animate-fluid-fill"
                style={{
                  width: '100%',
                  height: `${Math.max(4, value * 100)}%`,
                  minHeight: 4,
                  borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                  background: isCurrent
                    ? ttmStageColors[stage] || coachColors.softBlue
                    : coachColors.lavenderGray,
                  transition: 'height var(--transition-base)',
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  color: isCurrent ? 'var(--color-deep-mocha)' : 'var(--color-clay-brown)',
                  fontWeight: isCurrent ? 600 : 400,
                }}
              >
                {STAGE_LABELS[stage] || stage}
              </span>
            </div>
          );
        })}
      </div>

      {/* 当前阶段 */}
      <div
        style={{
          textAlign: 'center',
          padding: 'var(--space-sm) var(--space-md)',
          background: coachColors.sandalwoodMist,
          borderRadius: 'var(--radius-md)',
          fontSize: 14,
          color: 'var(--color-deep-mocha)',
        }}
      >
        当前阶段: <strong>{STAGE_LABELS[data.current_stage] || data.current_stage}</strong>
      </div>
    </div>
  );
}
