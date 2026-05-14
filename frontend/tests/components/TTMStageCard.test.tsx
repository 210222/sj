import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TTMStageCard } from '../../src/components/dashboard/TTMStageCard';

const mockData = {
  precontemplation: 0.1,
  contemplation: 0.3,
  preparation: 0.6,
  action: 0.4,
  maintenance: 0.1,
  current_stage: 'preparation',
};

describe('TTMStageCard', () => {
  it('renders stage labels', () => {
    render(<TTMStageCard data={mockData} />);
    expect(screen.getByText('前意向')).toBeDefined();
    expect(screen.getByText('意向')).toBeDefined();
    expect(screen.getAllByText('准备').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('行动')).toBeDefined();
    expect(screen.getByText('维持')).toBeDefined();
  });

  it('shows current stage', () => {
    render(<TTMStageCard data={mockData} />);
    expect(screen.getByText('当前阶段:')).toBeDefined();
  });

  it('shows placeholder when data is empty', () => {
    render(<TTMStageCard data={{ current_stage: '' } as any} />);
    expect(screen.getByText('TTM 阶段数据暂未可用')).toBeDefined();
  });
});
