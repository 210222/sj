/** GatePipeline — 8 门禁流水线管理员全展开视图.

 * 设计文档第 3.3 节:
 * - 干预文本节点依序通过不同治理检查点
 * - 通过点=绿色(PASS), 阻断门限=橙色(WARN)或红色(BLOCK)
 * - 支持点击下钻查看具体违反的风险策略算法
 * - 左上角固定整体状态指示器
 */
import { useState } from 'react';
import { coachColors, semanticColors } from '../../styles/theme';
import type { AdminGatesResponse } from '../../types/api';

interface GatePipelineProps {
  data: AdminGatesResponse;
}

const GATE_DESCRIPTIONS: Record<number, string> = {
  1: '检测用户是否频繁改写系统前提假设',
  2: '追踪探索行为的证据深度和频率',
  3: '评估无辅助场景下的独立思考轨迹',
  4: '监测用户对教练建议的顺从信号',
  5: '因果推断三诊断 (平衡/负控制/安慰剂)',
  6: '审计事件日志健康度评分',
  7: '独立框架思维审计通过率',
  8: '窗口期 schema 版本一致性检查',
};

const STATUS_INDICATOR: Record<string, { icon: string; color: string; pulse: boolean }> = {
  pass: { icon: '●', color: semanticColors.pass, pulse: false },
  warn: { icon: '⚠', color: semanticColors.warn, pulse: true },
  block: { icon: '●', color: semanticColors.block, pulse: true },
};

export function GatePipeline({ data }: GatePipelineProps) {
  const [expandedGate, setExpandedGate] = useState<number | null>(null);

  if (!data || !data.gates) {
    return (
      <div style={{ padding: 'var(--space-lg)', textAlign: 'center', color: 'var(--color-clay-brown)' }}>
        门禁数据暂未加载
      </div>
    );
  }

  return (
    <div style={{ background: 'var(--color-warm-white)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-lg)', boxShadow: 'var(--shadow-card)' }}>
      {/* F 型布局 — 左上角固定整体状态 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
        <div
          className={data.overall === 'block' ? 'animate-glow' : ''}
          style={{
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: data.overall === 'pass' ? semanticColors.pass : data.overall === 'warn' ? semanticColors.warn : semanticColors.block,
            boxShadow: data.overall !== 'pass' ? `0 0 8px ${semanticColors.warn}` : undefined,
          }}
        />
        <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-deep-mocha)' }}>
          治理门禁 — {data.overall === 'pass' ? '全部通过' : data.overall === 'warn' ? '存在警告' : '已阻断'}
        </h3>
        <span style={{ fontSize: 12, color: 'var(--color-clay-brown)', marginLeft: 'var(--space-xs)' }}>
          AND 逻辑 — 8 道门禁全部 pass 才允许升档
        </span>
      </div>

      {/* 门禁列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
        {data.gates.map((gate) => {
          const indicator = STATUS_INDICATOR[gate.status] || STATUS_INDICATOR.pass;
          const isExpanded = expandedGate === gate.id;

          return (
            <div key={gate.id}>
              <button
                onClick={() => setExpandedGate(isExpanded ? null : gate.id)}
                className={indicator.pulse ? 'animate-pulse-in' : ''}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-md)',
                  width: '100%',
                  padding: 'var(--space-md)',
                  background: isExpanded ? 'var(--color-cream-paper)' : 'transparent',
                  border: `1px solid ${isExpanded ? coachColors.lavenderGray : 'transparent'}`,
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'background var(--transition-fast)',
                }}
              >
                {/* 状态指示器 */}
                <span
                  style={{
                    color: indicator.color,
                    fontSize: indicator.pulse ? 18 : 14,
                    animation: indicator.pulse ? 'glowBreathe 2s ease-in-out infinite' : undefined,
                  }}
                >
                  {indicator.icon}
                </span>

                {/* Gate 信息 */}
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                    <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-deep-mocha)' }}>
                      {gate.name}
                    </span>
                    <span style={{
                      fontSize: 10,
                      padding: '1px 6px',
                      borderRadius: 8,
                      background: indicator.color,
                      color: '#fff',
                      textTransform: 'uppercase',
                    }}>
                      {gate.status}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--color-clay-brown)' }}>
                    指标: {gate.metric}
                  </span>
                </div>

                {/* 展开指示 */}
                <span style={{ fontSize: 12, color: 'var(--color-clay-brown)' }}>
                  {isExpanded ? '▲' : '▼'}
                </span>
              </button>

              {/* 下钻详情 */}
              {isExpanded && (
                <div
                  className="animate-slide-up"
                  style={{
                    marginLeft: 'var(--space-xl)',
                    marginTop: 'var(--space-xs)',
                    marginBottom: 'var(--space-sm)',
                    padding: 'var(--space-md)',
                    background: 'var(--color-cream-paper)',
                    borderRadius: 'var(--radius-md)',
                    border: `1px solid ${coachColors.lavenderGray}`,
                  }}
                >
                  <p style={{ fontSize: 13, color: 'var(--color-deep-mocha)', marginBottom: 'var(--space-sm)' }}>
                    {GATE_DESCRIPTIONS[gate.id] || '门禁详情'}
                  </p>
                  {gate.detail && (
                    <pre style={{ fontSize: 11, color: 'var(--color-clay-brown)', whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(gate.detail, null, 2)}
                    </pre>
                  )}
                  {/* 迷你趋势指示 */}
                  <div style={{ marginTop: 'var(--space-sm)' }}>
                    <span style={{ fontSize: 11, color: 'var(--color-clay-brown)' }}>
                      历史趋势: 暂无数据 (需持续运维窗口)
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
