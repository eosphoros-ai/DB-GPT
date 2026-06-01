import ClientErrorBoundary from '@/components/common/ClientErrorBoundary';
import React, { useMemo } from 'react';

const MAX_HTML_CHARS = 4_000_000;

const resolveHtmlImageUrls = (html: string): string => {
  const base = process.env.API_BASE_URL || '';
  if (!base || !html) return html;
  return html.replace(/(src\s*=\s*["'])\/images\//gi, `$1${base}/images/`);
};

export function extractHtmlContent(content: unknown): string {
  if (typeof content === 'string') return content;
  if (content && typeof content === 'object') {
    const o = content as Record<string, unknown>;
    if (typeof o.html === 'string') return o.html;
    if (typeof o.content === 'string') return o.content;
  }
  return '';
}

const SafeHtmlPreview: React.FC<{ content: unknown; artifactId?: string }> = ({ content, artifactId }) => {
  const srcDoc = useMemo(() => {
    const raw = extractHtmlContent(content);
    if (!raw.trim()) return '';
    if (raw.length > MAX_HTML_CHARS) {
      return `<!DOCTYPE html><html><body><p>HTML слишком большой для предпросмотра (${raw.length} символов).</p></body></html>`;
    }
    return resolveHtmlImageUrls(raw);
  }, [content]);

  if (!srcDoc) {
    return (
      <div className='flex items-center justify-center h-full p-8 text-sm text-gray-500 dark:text-gray-400'>
        Нет HTML для отображения.
      </div>
    );
  }

  return (
    <ClientErrorBoundary>
      <iframe
        key={artifactId || srcDoc.length}
        title='html-preview'
        srcDoc={srcDoc}
        sandbox='allow-scripts allow-same-origin allow-modals'
        className='w-full flex-1 bg-white'
        style={{ border: 'none', minHeight: 600 }}
      />
    </ClientErrorBoundary>
  );
};

export default SafeHtmlPreview;
