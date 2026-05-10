/** ProgressTimeline — 学习进度时间线.

 * 展示阶段性学习里程碑与成就.
 */
import { coachColors } from '../../styles/theme';
import type { ProgressData } from '../../types/api';

interface ProgressTimelineProps {
  data: ProgressData;
  ttmStage?: string | null;
}

const STAGE_MILESTONES: Record<string, { label: string; icon: string }> = {
  precontemplation: { label: '开始觉察', icon: '🌱' },
  contemplation: { label: '权衡思考', icon: '⚖️' },
  preparation: { label: '制定计划', icon: '📋' },
  action: { label: '付诸行动', icon: '🚀' },
  maintenance: { label: '巩固习惯', icon: '🌟' },
  relapse: { label: '重新出发', icon: '🔄' },
};

export function ProgressTimeline({ data, ttmStage }: ProgressTimelineProps) {
  const milestone = (ttmStage && STAGE_MILESTONES[ttmStage])
    ? STAGE_MILESTONES[ttmStage]
    : { label: '旅程开始', icon: '✨' };

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
      <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-deep-mocha)', marginBottom: 'var(--space-md)' }}>
        学习进度
      </h3>

      {/* 核心指标 — F 型左上角 */}
      <div style={{ display: 'flex', gap: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-deep-mocha)' }}>
            {data.total_sessions}
          </span>
          <p style={{ fontSize: 11, color: 'var(--color-clay-brown)', marginTop: 'var(--space-xs)' }}>
            总会话数
          </p>
        </div>
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-deep-mocha)' }}>
            {data.total_turns}
          </span>
          <p style={{ fontSize: 11, color: 'var(--color-clay-brown)', marginTop: 'var(--space-xs)' }}>
            总交互轮次
          </p>
        </div>
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: 'var(--color-deep-mocha)' }}>
            {data.no_assist_avg !== null ? `${Math.round(data.no_assist_avg * 100)}%` : '—'}
          </span>
          <p style={{ fontSize: 11, color: 'var(--color-clay-brown)', marginTop: 'var(--space-xs)' }}>
            独立完成率
          </p>
        </div>
      </div>

      {/* 当前里程碑 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-md)',
          padding: 'var(--space-md)',
          background: coachColors.sandalwoodMist,
          borderRadius: 'var(--radius-md)',
        }}
      >
        <span style={{ fontSize: 24 }}>{milestone.icon}</span>
        <div>
          <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-deep-mocha)' }}>
            {milestone.label}
          </span>
          {data.last_active_utc && (
            <p style={{ fontSize: 11, color: 'var(--color-clay-brown)', marginTop: 'var(--space-xs)' }}>
              最近活跃: {data.last_active_utc}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
