/** RiskDashboard — 风险评估面板.

 * 管理聚焦(Management by Exception):
 *  快速识别死锁或潜在危害交互.
 *  每个风险条目附带陈述句结论。
 */
import { semanticColors } from '../../styles/theme';

interface RiskItem {
  id: string;
  category: string;
  severity: 'high' | 'medium' | 'low';
  summary: string;
  recommendation: string;
}

interface RiskDashboardProps {
  risks?: RiskItem[];
}

const SEVERITY_CONFIG = {
  high: { color: semanticColors.block, label: '高风险' },
  medium: { color: semanticColors.warn, label: '中风险' },
  low: { color: semanticColors.info, label: '低风险' },
};

const DEFAULT_RISKS: RiskItem[] = [
  {
    id: 'r1',
    category: '合规',
    severity: 'low',
    summary: '单用户架构 — 巴士因子=1',
    recommendation: '引入第二开发者前保持现状',
  },
  {
    id: 'r2',
    category: '性能',
    severity: 'medium',
    summary: 'MMRT 低流量时样本不足',
    recommendation: '样本不足时诊断自动 pass，无需干预',
  },
  {
    id: 'r3',
    category: '运维',
    severity: 'low',
    summary: '无 CI/CD pipeline — 本地单用户运行',
    recommendation: '当前阶段不需要自动化构建',
  },
];

export function RiskDashboard({ risks }: RiskDashboardProps) {
  const items = risks && risks.length > 0 ? risks : DEFAULT_RISKS;

  return (
    <div style={{ background: 'var(--color-warm-white)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-lg)', boxShadow: 'var(--shadow-card)' }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-deep-mocha)', marginBottom: 'var(--space-md)' }}>
        风险评估
      </h3>

      {/* F 型 — 高危条目置顶 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
        {items
          .sort((a, b) => {
            const order = { high: 0, medium: 1, low: 2 };
            return order[a.severity] - order[b.severity];
          })
          .map((risk) => {
            const sev = SEVERITY_CONFIG[risk.severity];
            return (
              <div
                key={risk.id}
                className="animate-slide-up"
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 'var(--space-md)',
                  padding: 'var(--space-md)',
                  background: 'var(--color-cream-paper)',
                  borderRadius: 'var(--radius-md)',
                  borderLeft: `3px solid ${sev.color}`,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: sev.color,
                    color: '#fff',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {sev.label}
                </span>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-deep-mocha)' }}>
                    {risk.summary}
                  </p>
                  {/* 图表+陈述句组合 */}
                  <p style={{ fontSize: 12, color: 'var(--color-clay-brown)', marginTop: 'var(--space-xs)' }}>
                    → {risk.recommendation}
                  </p>
                </div>
                <span style={{ fontSize: 11, color: 'var(--color-clay-brown)' }}>
                  {risk.category}
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}
