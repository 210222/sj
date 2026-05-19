import { useEffect, useState } from 'react';

interface Props {
  content: string;
  language?: string;
}

export function PrismRenderer({ content, language = 'python' }: Props) {
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const lang = language || 'python';
    Promise.all([
      import('prismjs'),
      import(`prismjs/components/prism-${lang}`).catch(() => null),
    ]).then(([prism]) => {
      if (cancelled) return;
      try {
        const grammar = prism.default.languages[lang];
        if (grammar) {
          setHtml(prism.default.highlight(content, grammar, lang));
        } else {
          setHtml(content);
        }
      } catch { if (!cancelled) setError(true); }
    }).catch(() => { if (!cancelled) setError(true); });

    return () => { cancelled = true; };
  }, [content, language]);

  if (error || !html) {
    return (
      <div style={{ padding: 10, background: '#f5f5f0', borderRadius: 6, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', overflowX: 'auto' }}>
        {content}
      </div>
    );
  }

  return (
    <pre style={{ padding: 10, background: '#f5f5f0', borderRadius: 6, fontSize: 12, overflowX: 'auto' }}>
      <code dangerouslySetInnerHTML={{ __html: html }} />
    </pre>
  );
}
