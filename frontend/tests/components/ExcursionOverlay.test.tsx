import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ExcursionOverlay } from '../../src/components/chat/ExcursionOverlay';

describe('ExcursionOverlay', () => {
  it('renders nothing when inactive', () => {
    const { container } = render(<ExcursionOverlay active={false} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders excursion indicator when active', () => {
    render(<ExcursionOverlay active={true} />);
    expect(screen.getByText('探索模式')).toBeDefined();
  });

  it('shows exit button when onExit provided', () => {
    const onExit = vi.fn();
    render(<ExcursionOverlay active={true} onExit={onExit} />);
    fireEvent.click(screen.getByText('退出'));
    expect(onExit).toHaveBeenCalled();
  });

  it('does not show exit button without onExit', () => {
    render(<ExcursionOverlay active={true} />);
    expect(screen.queryByText('退出')).toBeNull();
  });
});
