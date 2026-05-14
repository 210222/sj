import type { UserDashboardResponse } from '../types/api';

export function TeachingStatus({ dashboard }: { dashboard: UserDashboardResponse }) {
  const skills = dashboard.mastery_snapshot?.skills as Record<string, number> | undefined;
  const reviewQueue = dashboard.review_queue as Array<{ skill: string; retention: number }> | undefined;

  return (
    <div style={{ padding: 'var(--space-md)', fontSize: 13 }}>
      {skills && Object.keys(skills).length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 4, color: 'var(--color-deep-mocha)' }}>
            技能掌握度
          </div>
          {Object.entries(skills).map(([skill, value]) => (
            <div key={skill} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <span>{skill}</span>
              <span>{((value as number) * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
      {reviewQueue && reviewQueue.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 4, color: 'var(--color-deep-mocha)' }}>
            待复习
          </div>
          {reviewQueue.map((item, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
              <span>{item.skill}</span>
              <span style={{ color: '#c44' }}>{(item.retention * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
