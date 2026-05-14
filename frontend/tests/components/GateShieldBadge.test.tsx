import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GateShieldBadge } from '../../src/components/dashboard/GateShieldBadge';

describe('GateShieldBadge', () => {
  it('renders pass message', () => {
    render(<GateShieldBadge overall="pass" />);
    expect(screen.getByText('系统守护中')).toBeDefined();
    expect(screen.getByText('一切运行顺畅，你可以自由探索')).toBeDefined();
  });

  it('renders warn message', () => {
    render(<GateShieldBadge overall="warn" />);
    expect(screen.getByText('正在留意')).toBeDefined();
  });

  it('renders block message', () => {
    render(<GateShieldBadge overall="block" />);
    expect(screen.getByText('已保护')).toBeDefined();
  });

  it('uses custom blocked message', () => {
    render(<GateShieldBadge overall="block" blockedMessage="自定义阻断提示" />);
    expect(screen.getByText('自定义阻断提示')).toBeDefined();
  });

  it('uses AI coach tone — no technical terms', () => {
    render(<GateShieldBadge overall="block" />);
    // 确保不包含技术术语
    expect(screen.queryByText(/gate/i)).toBeNull();
    expect(screen.queryByText(/pipeline/i)).toBeNull();
    expect(screen.queryByText(/audit/i)).toBeNull();
    expect(screen.queryByText(/P0/i)).toBeNull();
  });
});
