import { useEffect, useRef, useState } from 'react';

interface Props {
  content: string;
}

export function MermaidRenderer({ content }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import('mermaid').then((mermaid) => {
      if (cancelled) return;
      mermaid.default.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });
      const id = `mermaid-${Math.random().toString(36).slice(2)}`;
      mermaid.default.render(id, content).then(({ svg }) => {
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) { svgEl.style.width = '100%'; svgEl.style.height = 'auto'; }
        }
      }).catch(() => { if (!cancelled) setError(true); });
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [content]);

  if (error) {
    return (
      <div style={{ padding: 10, background: '#f5f5f0', borderRadius: 6, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', opacity: 0.8 }}>
        {content}
      </div>
    );
  }

  return <div ref={containerRef} style={{ width: '100%', overflowX: 'auto' }} />;
}
