import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressTimeline } from '../../src/components/dashboard/ProgressTimeline';

const mockData = {
  total_sessions: 42,
  total_turns: 310,
  no_assist_avg: 0.68,
  last_active_utc: '2026-05-04T10:00:00Z',
};

describe('ProgressTimeline', () => {
  it('renders session count', () => {
    render(<ProgressTimeline data={mockData} />);
    expect(screen.getByText('42')).toBeDefined();
    expect(screen.getByText('总会话数')).toBeDefined();
  });

  it('renders turn count', () => {
    render(<ProgressTimeline data={mockData} />);
    expect(screen.getByText('310')).toBeDefined();
  });

  it('renders no_assist_avg as percentage', () => {
    render(<ProgressTimeline data={mockData} />);
    expect(screen.getByText('68%')).toBeDefined();
  });

  it('renders milestone for ttm stage', () => {
    render(<ProgressTimeline data={mockData} ttmStage="action" />);
    expect(screen.getByText('付诸行动')).toBeDefined();
  });

  it('renders default milestone when stage unknown', () => {
    render(<ProgressTimeline data={mockData} />);
    expect(screen.getByText('旅程开始')).toBeDefined();
  });
});
