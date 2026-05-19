import { useEffect, useRef, useState } from 'react';

interface Props {
  content: { expressions?: Array<{ id?: string; latex?: string; color?: string }> };
}

export function DesmosRenderer({ content }: Props) {
  const boardRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import('desmos').then((Desmos) => {
      if (cancelled) return;
      try {
        if (!boardRef.current) return;
        const calculator = Desmos.default.GraphingCalculator(boardRef.current, {
          expressions: false, settingsMenu: false, zoomButtons: true,
        });
        const exprs = content.expressions || [];
        for (const e of exprs) {
          calculator.setExpression({ id: e.id || undefined, latex: e.latex, color: e.color || undefined });
        }
      } catch { if (!cancelled) setError(true); }
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [content]);

  if (error) {
    const exprs = content.expressions || [];
    return (
      <div style={{ padding: 10, background: '#f5f5f0', borderRadius: 6, fontSize: 12, opacity: 0.8 }}>
        <div style={{ marginBottom: 4, color: '#c9a04a' }}>Desmos 加载失败</div>
        {exprs.map((e, i) => (
          <div key={i} style={{ fontFamily: 'monospace' }}>{e.latex}</div>
        ))}
      </div>
    );
  }

  return <div ref={boardRef} style={{ width: '100%', height: 380, borderRadius: 8 }} />;
}
