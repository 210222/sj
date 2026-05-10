/** AuditLogViewer — 审计日志查询与分页.

 * 管理聚焦(Management by Exception):
 *  默认展示 P0 级别事件，支持按严重级别筛选和分页浏览.
 */
import { useState, useCallback } from 'react';
import { coachColors, semanticColors } from '../../styles/theme';
import type { AdminAuditResponse } from '../../types/api';

interface AuditLogViewerProps {
  data: AdminAuditResponse;
  onPageChange: (page: number) => void;
  onSeverityChange: (severity: string) => void;
  loading?: boolean;
}

const SEVERITY_STYLES: Record<string, { bg: string; label: string }> = {
  P0: { bg: semanticColors.block, label: 'P0 严重' },
  P1: { bg: semanticColors.warn, label: 'P1 警告' },
  pass: { bg: semanticColors.pass, label: '正常' },
};

export function AuditLogViewer({
  data,
  onPageChange,
  onSeverityChange,
  loading,
}: AuditLogViewerProps) {
  const [severity, setSeverity] = useState('all');

  const handleSeverity = useCallback((s: string) => {
    setSeverity(s);
    onSeverityChange(s);
  }, [onSeverityChange]);

  const logs = data?.logs ?? [];
  const total = data?.total ?? 0;
  const page = data?.page ?? 1;
  const pageSize = data?.page_size ?? 50;

  return (
    <div style={{ background: 'var(--color-warm-white)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-lg)', boxShadow: 'var(--shadow-card)' }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-deep-mocha)', marginBottom: 'var(--space-md)' }}>
        审计日志
      </h3>

      {/* 筛选栏 */}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', marginBottom: 'var(--space-md)', flexWrap: 'wrap' }}>
        {['all', 'P0', 'P1', 'pass'].map((s) => (
          <button
            key={s}
            onClick={() => handleSeverity(s)}
            style={{
              padding: '4px 14px',
              border: `1px solid ${severity === s ? coachColors.deepMocha : coachColors.lavenderGray}`,
              borderRadius: 'var(--radius-lg)',
              background: severity === s ? coachColors.deepMocha : 'transparent',
              color: severity === s ? coachColors.warmWhite : 'var(--color-deep-mocha)',
              fontSize: 13,
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
          >
            {s === 'all' ? '全部' : s}
          </button>
        ))}
      </div>

      {/* 日志列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
        {loading ? (
          <p style={{ textAlign: 'center', color: 'var(--color-clay-brown)', padding: 'var(--space-lg)' }}>
            加载中...
          </p>
        ) : logs.length === 0 ? (
          <p style={{ textAlign: 'center', color: 'var(--color-clay-brown)', padding: 'var(--space-lg)' }}>
            暂无审计日志
          </p>
        ) : (
          logs.map((log) => {
            const sevStyle = SEVERITY_STYLES[log.severity] || { bg: coachColors.lavenderGray, label: log.severity };
            return (
              <div
                key={log.event_id}
                className="animate-slide-up"
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 'var(--space-md)',
                  padding: 'var(--space-md)',
                  background: 'var(--color-cream-paper)',
                  borderRadius: 'var(--radius-md)',
                  borderLeft: `3px solid ${sevStyle.bg}`,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: sevStyle.bg,
                    color: '#fff',
                    whiteSpace: 'nowrap',
                    minWidth: 60,
                    textAlign: 'center',
                  }}
                >
                  {sevStyle.label}
                </span>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, color: 'var(--color-deep-mocha)' }}>{log.summary}</p>
                  <p style={{ fontSize: 11, color: 'var(--color-clay-brown)', marginTop: 'var(--space-xs)' }}>
                    {log.timestamp_utc} · {log.trace_id ? `trace: ${log.trace_id.slice(0, 8)}...` : ''}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 分页 */}
      {total > pageSize && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            style={{
              padding: 'var(--space-xs) var(--space-md)',
              border: `1px solid ${coachColors.lavenderGray}`,
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              cursor: page <= 1 ? 'default' : 'pointer',
              opacity: page <= 1 ? 0.4 : 1,
              fontSize: 13,
            }}
          >
            上一页
          </button>
          <span style={{ fontSize: 13, color: 'var(--color-clay-brown)', alignSelf: 'center' }}>
            {page} / {Math.ceil(total / pageSize)}
          </span>
          <button
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => onPageChange(page + 1)}
            style={{
              padding: 'var(--space-xs) var(--space-md)',
              border: `1px solid ${coachColors.lavenderGray}`,
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              cursor: page >= Math.ceil(total / pageSize) ? 'default' : 'pointer',
              opacity: page >= Math.ceil(total / pageSize) ? 0.4 : 1,
              fontSize: 13,
            }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
