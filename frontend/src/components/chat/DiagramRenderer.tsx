import { useState, Suspense, lazy, useCallback, useEffect } from 'react';

const MermaidRenderer = lazy(() => import('./MermaidRenderer').then(m => ({ default: m.MermaidRenderer })));
const KaTeXRenderer = lazy(() => import('./KaTeXRenderer').then(m => ({ default: m.KaTeXRenderer })));
const DesmosRenderer = lazy(() => import('./DesmosRenderer').then(m => ({ default: m.DesmosRenderer })));
const PrismRenderer = lazy(() => import('./PrismRenderer').then(m => ({ default: m.PrismRenderer })));

interface Props {
  diagram?: { type: string; content: any; language?: string };
}

function FallbackBlock({ text }: { text: string }) {
  return (
    <div style={{ padding: 10, background: '#f5f5f0', borderRadius: 6, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap', overflowX: 'auto', opacity: 0.7 }}>
      {text}
    </div>
  );
}

function DiagramContent({ diagram }: Props) {
  const fallback = <FallbackBlock text={typeof diagram?.content === 'string' ? diagram.content : JSON.stringify(diagram?.content ?? {}, null, 2)} />;

  if (!diagram) return fallback;

  switch (diagram.type) {
    case 'mermaid':
      return <Suspense fallback={fallback}><MermaidRenderer content={String(diagram.content)} /></Suspense>;
    case 'katex':
      return <Suspense fallback={fallback}><KaTeXRenderer content={String(diagram.content)} /></Suspense>;
    case 'desmos':
      return <Suspense fallback={fallback}><DesmosRenderer content={diagram.content} /></Suspense>;
    case 'prism':
      return <Suspense fallback={fallback}><PrismRenderer content={String(diagram.content)} language={diagram.language} /></Suspense>;
    default:
      return fallback;
  }
}

function DiagramLightbox({ diagram, onClose }: { diagram: Props['diagram']; onClose: () => void }) {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.85)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
    >
      <button
        onClick={onClose}
        style={{
          position: 'absolute', top: 16, right: 20,
          background: 'none', border: 'none', color: '#fff',
          fontSize: 28, cursor: 'pointer', lineHeight: 1,
        }}
      >✕</button>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '95vw', maxHeight: '90vh', overflow: 'auto', background: '#fff', borderRadius: 10, padding: 20 }}
      >
        <DiagramContent diagram={diagram} />
      </div>
    </div>
  );
}

export function DiagramRenderer({ diagram }: Props) {
  const [zoomed, setZoomed] = useState(false);

  const handleClick = useCallback(() => {
    if (diagram && !zoomed) setZoomed(true);
  }, [diagram, zoomed]);

  if (!diagram) return null;

  try {
    return (
      <>
        <div onClick={handleClick} style={{ cursor: 'zoom-in' }}>
          <DiagramContent diagram={diagram} />
        </div>
        {zoomed && (
          <DiagramLightbox diagram={diagram} onClose={() => setZoomed(false)} />
        )}
      </>
    );
  } catch {
    return <FallbackBlock text={typeof diagram.content === 'string' ? diagram.content : JSON.stringify(diagram.content)} />;
  }
}
