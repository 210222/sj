import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PulsePanel } from '../../src/components/chat/PulsePanel';

describe('PulsePanel', () => {
  it('renders the statement text', () => {
    render(
      <PulsePanel
        statement="我注意到这一步对你的影响较大。"
        acceptLabel="我接受"
        rewriteLabel="我改写前提"
        blockingMode="hard"
        onAccept={vi.fn()}
        onRewrite={vi.fn()}
      />,
    );
    expect(screen.getByText(/我注意到这一步对你/)).toBeDefined();
  });

  it('renders slide track in hard mode', () => {
    render(
      <PulsePanel
        statement="确认吗？"
        acceptLabel="我接受"
        rewriteLabel="我改写前提"
        blockingMode="hard"
        onAccept={vi.fn()}
        onRewrite={vi.fn()}
      />,
    );
    expect(screen.getByText('我接受')).toBeDefined();
  });

  it('renders rewrite ghost button in hard mode', () => {
    render(
      <PulsePanel
        statement="确认吗？"
        acceptLabel="我接受"
        rewriteLabel="我改写前提"
        blockingMode="hard"
        onAccept={vi.fn()}
        onRewrite={vi.fn()}
      />,
    );
    expect(screen.getByText('我改写前提')).toBeDefined();
  });

  it('does not render slide track in soft mode', () => {
    render(
      <PulsePanel
        statement="这是一条软提示。"
        acceptLabel="我接受"
        rewriteLabel="我改写"
        blockingMode="soft"
        onAccept={vi.fn()}
        onRewrite={vi.fn()}
      />,
    );
    // soft 模式显示提示信息，无滑动确认交互
    expect(screen.queryByText('我接受')).toBeNull();
  });

  it('shows rewrite input on ghost button click', () => {
    render(
      <PulsePanel
        statement="确认吗？"
        acceptLabel="我接受"
        rewriteLabel="我改写前提"
        blockingMode="hard"
        onAccept={vi.fn()}
        onRewrite={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText('我改写前提'));
    // 出现输入框
    expect(screen.getByPlaceholderText('输入你的想法...')).toBeDefined();
  });
});
