import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GatePipeline } from '../../src/components/admin/GatePipeline';

const mockData = {
  gates: [
    { id: 1, name: 'Agency Gate', status: 'pass' as const, metric: 'premise_rewrite_rate' },
    { id: 2, name: 'Excursion Gate', status: 'warn' as const, metric: 'exploration_evidence_count' },
    { id: 3, name: 'Learning Gate', status: 'pass' as const, metric: 'no_assist_trajectory' },
    { id: 4, name: 'Relational Gate', status: 'pass' as const, metric: 'compliance_signal_score' },
    { id: 5, name: 'Causal Gate', status: 'pass' as const, metric: 'causal_diagnostics_triple' },
    { id: 6, name: 'Audit Gate', status: 'block' as const, metric: 'audit_health' },
    { id: 7, name: 'Framing Gate', status: 'pass' as const, metric: 'framing_audit_pass' },
    { id: 8, name: 'Window Gate', status: 'pass' as const, metric: 'window_schema_version_consistency' },
  ],
  overall: 'block' as const,
};

describe('GatePipeline', () => {
  it('renders all 8 gates', () => {
    render(<GatePipeline data={mockData} />);
    expect(screen.getByText('Agency Gate')).toBeDefined();
    expect(screen.getByText('Window Gate')).toBeDefined();
  });

  it('shows overall status', () => {
    render(<GatePipeline data={mockData} />);
    expect(screen.getByText(/已阻断/)).toBeDefined();
  });

  it('shows AND logic hint', () => {
    render(<GatePipeline data={mockData} />);
    expect(screen.getByText(/AND 逻辑/)).toBeDefined();
  });

  it('expands gate detail on click', () => {
    render(<GatePipeline data={mockData} />);
    fireEvent.click(screen.getByText('Agency Gate'));
    expect(screen.getByText(/检测用户是否频繁改写/)).toBeDefined();
  });

  it('shows placeholder when data empty', () => {
    render(<GatePipeline data={{} as any} />);
    expect(screen.getByText('门禁数据暂未加载')).toBeDefined();
  });
});
