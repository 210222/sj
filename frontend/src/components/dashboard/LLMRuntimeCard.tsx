/** LLMRuntimeCard — 本会话 LLM 运行时摘要。null 时不渲染. */
import type { SessionLLMSummary } from '../../types/api';
import { coachColors } from '../../styles/theme';

interface Props {
  summary: SessionLLMSummary | null | undefined;
  costUsd?: number;
}

export function LLMRuntimeCard({ summary, costUsd }: Props) {
  if (!summary || summary.total_calls === 0) return null;

  const pct = summary.cache_eligible_rate != null
    ? `${(summary.cache_eligible_rate * 100).toFixed(0)}%`
    : '--';
  const lat = summary.avg_latency_ms != null
    ? summary.avg_latency_ms < 1000
      ? `${Math.round(summary.avg_latency_ms)}ms`
      : `${(summary.avg_latency_ms / 1000).toFixed(1)}s`
    : '--';

  return (
    <div style={{
      background: 'linear-gradient(135deg, #f8f5f0 0%, #fdfaf5 100%)',
      border: `1px solid ${coachColors.lavenderGray}`,
      borderRadius: 10, padding: '12px 14px', marginBottom: 'var(--space-md)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, opacity: 0.7 }}>
        LLM Runtime (本会话)
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <StatBox label="缓存命中" value={pct} good={summary.cache_eligible_rate > 0.8} />
        <StatBox label="平均延迟" value={lat} good={summary.avg_latency_ms < 3000} />
        <StatBox label="LLM 调用" value={`${summary.total_calls}`} />
        <StatBox label="消耗" value={costUsd != null ? `$${costUsd.toFixed(4)}` : '--'} />
      </div>
    </div>
  );
}

function StatBox({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div style={{ textAlign: 'center', padding: 6, background: '#fff', borderRadius: 8 }}>
      <div style={{
        fontSize: 16, fontWeight: 700,
        color: good === true ? coachColors.sageGreen : good === false ? '#c9a04a' : 'inherit',
      }}>{value}</div>
      <div style={{ fontSize: 10, opacity: 0.5, marginTop: 2 }}>{label}</div>
    </div>
  );
}
