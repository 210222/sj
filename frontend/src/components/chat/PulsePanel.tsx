/** PulsePanel — 非阻断式滑动确认面板.

 * 设计文档第 2.2 节:
 * - 不是 Modal 阻断弹窗
 * - 当前对话气泡区域细微纵向位移
 * - 底部平滑升起毛玻璃确认容器 (backdrop-filter: blur)
 * - "接受"通过滑动滑块完成，"重写"为次级幽灵按钮
 */
import { useState } from 'react';
import { SlideToConfirm } from '../shared/SlideToConfirm';
import { coachColors } from '../../styles/theme';

interface PulsePanelProps {
  statement: string;
  acceptLabel: string;
  rewriteLabel: string;
  blockingMode: string;
  onAccept: () => void;
  onRewrite: (content: string) => void;
}

export function PulsePanel({
  statement,
  acceptLabel,
  rewriteLabel,
  blockingMode,
  onAccept,
  onRewrite,
}: PulsePanelProps) {
  const [showRewriteInput, setShowRewriteInput] = useState(false);
  const [rewriteText, setRewriteText] = useState('');
  const isSoft = blockingMode === 'soft';

  const handleRewriteSubmit = () => {
    if (rewriteText.trim()) {
      onRewrite(rewriteText.trim());
      setShowRewriteInput(false);
      setRewriteText('');
    }
  };

  return (
    <div
      className="animate-slide-up"
      style={{
        padding: 'var(--space-lg)',
        margin: 'var(--space-md)',
        borderRadius: 'var(--radius-lg)',
        background: isSoft
          ? 'rgba(254, 221, 216, 0.15)'
          : 'rgba(245, 241, 234, 0.85)',
        backdropFilter: isSoft ? undefined : 'blur(12px)',
        boxShadow: 'var(--shadow-elevated)',
        border: `1px solid ${isSoft ? coachColors.coralCandy : coachColors.lavenderGray}`,
      }}
    >
      <p
        style={{
          fontSize: 15,
          lineHeight: 1.7,
          color: 'var(--color-deep-mocha)',
          marginBottom: 'var(--space-md)',
          textAlign: 'center',
        }}
      >
        {statement}
      </p>

      {isSoft ? (
        // 旁路软提示 — 珊瑚糖色高亮标记
        <div
          style={{
            borderLeft: `3px solid ${coachColors.coralCandy}`,
            padding: 'var(--space-sm) var(--space-md)',
            fontSize: 13,
            color: 'var(--color-clay-brown)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          这是一条高影响建议，你可以随时调整方向。
        </div>
      ) : (
        <>
          {/* 滑动确认 */}
          <SlideToConfirm
            acceptLabel={acceptLabel}
            onConfirm={onAccept}
            color={coachColors.sageGreen}
          />

          {/* 重写 — 幽灵按钮 */}
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 'var(--space-md)' }}>
            {showRewriteInput ? (
              <div style={{ display: 'flex', gap: 'var(--space-sm)', width: '100%' }}>
                <input
                  type="text"
                  value={rewriteText}
                  onChange={(e) => setRewriteText(e.target.value)}
                  placeholder="输入你的想法..."
                  autoFocus
                  style={{
                    flex: 1,
                    padding: 'var(--space-sm) var(--space-md)',
                    border: `1px solid ${coachColors.lavenderGray}`,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-warm-white)',
                    fontSize: 14,
                    outline: 'none',
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleRewriteSubmit();
                    if (e.key === 'Escape') setShowRewriteInput(false);
                  }}
                />
                <button
                  onClick={handleRewriteSubmit}
                  style={{
                    padding: 'var(--space-sm) var(--space-md)',
                    background: coachColors.softBlue,
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    color: coachColors.deepMocha,
                    fontSize: 14,
                  }}
                >
                  确认
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowRewriteInput(true)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-clay-brown)',
                  fontSize: 13,
                  opacity: 0.7,
                  cursor: 'pointer',
                  textDecoration: 'underline',
                }}
              >
                {rewriteLabel}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
