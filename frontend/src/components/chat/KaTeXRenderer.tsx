import { useEffect, useRef, useState } from 'react';

interface Props {
  content: string;
}

export function KaTeXRenderer({ content }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import('katex').then((katex) => {
      if (cancelled) return;
      try {
        const html = katex.default.renderToString(content, { throwOnError: false, displayMode: true });
        if (!cancelled && ref.current) {
          ref.current.innerHTML = html;
        }
      } catch { if (!cancelled) setError(true); }
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [content]);

  if (error) {
    return (
      <div style={{ padding: 10, background: '#f5f5f0', borderRadius: 6, fontSize: 13, opacity: 0.8 }}>
        {content}
      </div>
    );
  }

  return <div ref={ref} style={{ overflowX: 'auto' }} />;
}
