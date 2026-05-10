/** SlideToConfirm — 非阻断式滑动确认面板.

 * 设计文档第 2.2 节 — 脉冲确认组件.
 * 用户向右滑动滑块完成确认，增加仪式感。
 */
import { useState, useRef, useCallback, type MouseEvent, type TouchEvent } from 'react';

interface SlideToConfirmProps {
  acceptLabel?: string;
  onConfirm: () => void;
  color?: string;
}

export function SlideToConfirm({
  acceptLabel = '滑动确认',
  onConfirm,
  color,
}: SlideToConfirmProps) {
  const [offset, setOffset] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  const getMaxOffset = () => {
    if (!trackRef.current) return 200;
    return trackRef.current.clientWidth - 52;
  };

  const handleStart = useCallback(() => {
    if (confirmed) return;
  }, [confirmed]);

  const handleMove = useCallback((clientX: number) => {
    if (confirmed || !trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const max = getMaxOffset();
    const x = Math.max(0, Math.min(clientX - rect.left - 26, max));
    setOffset(x);
    if (x >= max * 0.9) {
      setConfirmed(true);
      onConfirm();
    }
  }, [confirmed, onConfirm]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    handleMove(e.clientX);
  }, [handleMove]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    handleMove(e.touches[0].clientX);
  }, [handleMove]);

  const handleEnd = useCallback(() => {
    if (!confirmed) setOffset(0);
  }, [confirmed]);

  const trackColor = color || 'var(--color-soft-blue)';

  return (
    <div
      style={{
        position: 'relative',
        height: 52,
        borderRadius: 26,
        background: 'var(--color-lavender-gray)',
        overflow: 'hidden',
        userSelect: 'none',
        touchAction: 'none',
      }}
      ref={trackRef}
      onMouseDown={handleStart}
      onMouseMove={handleMouseMove}
      onMouseUp={handleEnd}
      onMouseLeave={handleEnd}
      onTouchStart={handleStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleEnd}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          height: '100%',
          width: offset + 26,
          background: confirmed ? 'var(--color-sage-green)' : trackColor,
          borderRadius: 26,
          transition: confirmed ? 'background 0.3s ease' : 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: offset,
          top: 4,
          width: 44,
          height: 44,
          borderRadius: '50%',
          background: 'var(--color-warm-white)',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 600,
          fontSize: 18,
          color: 'var(--color-deep-mocha)',
          cursor: 'grab',
          transition: confirmed ? 'left 0.2s ease' : 'none',
        }}
      >
        {confirmed ? '✓' : '→'}
      </div>
      {!confirmed && (
        <span
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            color: 'var(--color-deep-mocha)',
            fontSize: 14,
            pointerEvents: 'none',
          }}
        >
          {acceptLabel}
        </span>
      )}
    </div>
  );
}
