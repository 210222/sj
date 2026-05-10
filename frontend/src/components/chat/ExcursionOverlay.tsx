/** ExcursionOverlay — 全局暗调主题切换.

 * 设计文档第 2.3 节:
 * - 不仅仅是文本框提示语变更
 * - 全局主题切换: 白底→深色"沉浸暗调"
 * - 屏幕边缘微弱光晕发光效果
 * - 对话气泡边界曲率改变
 * - CSS transition 300ms
 */
import { useEffect } from 'react';
import { coachColors } from '../../styles/theme';

interface ExcursionOverlayProps {
  active: boolean;
  onExit?: () => void;
}

export function ExcursionOverlay({ active, onExit }: ExcursionOverlayProps) {
  useEffect(() => {
    const root = document.documentElement;
    if (active) {
      root.style.setProperty('--transition-base', 'background 300ms ease');
      root.style.setProperty('--color-bg', coachColors.charcoal);
      root.style.setProperty('--color-text', coachColors.creamPaper);
      root.style.setProperty('--color-bubble-user', coachColors.clayBrown);
      root.style.setProperty('--color-bubble-coach', coachColors.warmSand);
      root.style.setProperty('--border-radius-bubble', '20px');
    } else {
      root.style.setProperty('--color-bg', coachColors.warmWhite);
      root.style.setProperty('--color-text', coachColors.deepMocha);
      root.style.setProperty('--color-bubble-user', coachColors.lavenderGray);
      root.style.setProperty('--color-bubble-coach', coachColors.softBlue);
      root.style.setProperty('--border-radius-bubble', '');
    }
    return () => {
      if (active) {
        root.style.setProperty('--color-bg', coachColors.warmWhite);
        root.style.setProperty('--color-text', coachColors.deepMocha);
        root.style.setProperty('--color-bubble-user', coachColors.lavenderGray);
        root.style.setProperty('--color-bubble-coach', coachColors.softBlue);
      }
    };
  }, [active]);

  if (!active) return null;

  return (
    <>
      {/* 屏幕边缘光晕 */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          pointerEvents: 'none',
          zIndex: 10,
          boxShadow: `inset 0 0 80px 20px ${coachColors.sageGreen}20`,
        }}
      />

      {/* 远足指示器 */}
      <div
        style={{
          position: 'fixed',
          top: 'var(--space-md)',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 100,
          padding: 'var(--space-sm) var(--space-lg)',
          background: 'rgba(47, 44, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          borderRadius: 'var(--radius-lg)',
          color: coachColors.creamPaper,
          fontSize: 14,
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
        }}
      >
        <span style={{ color: coachColors.sageGreen }}>✦</span>
        探索模式
        {onExit && (
          <button
            onClick={onExit}
            style={{
              marginLeft: 'var(--space-sm)',
              background: 'transparent',
              border: `1px solid ${coachColors.creamPaper}`,
              borderRadius: 'var(--radius-sm)',
              color: coachColors.creamPaper,
              padding: '2px 10px',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            退出
          </button>
        )}
      </div>
    </>
  );
}
