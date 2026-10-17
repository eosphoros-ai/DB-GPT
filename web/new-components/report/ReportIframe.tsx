import React, { useCallback, useEffect, useRef, useState } from 'react';
import { normalizeReportHtml } from './report-html';

type ReportIframeProps = {
  srcDoc: string;
  title?: string;
  iframeRef?: React.RefObject<HTMLIFrameElement>;
  minHeight?: number;
  maxHeight?: number;
  className?: string;
  onDocumentReady?: (document: Document) => void;
};

const apiBaseUrl = (process.env.API_BASE_URL ?? '').replace(/\/$/, '');

/** Resolve backend-owned report images before placing the report in srcdoc. */
export const resolveReportAssetUrls = (html: string): string =>
  html.replace(/\bsrc\s*=\s*(["'])\/images\//gi, (_whole, quote: string) => `src=${quote}${apiBaseUrl}/images/`);

/**
 * Report HTML is model-produced content.  Keep its document structure and
 * styles, but remove executable input before mounting it in our same-origin
 * iframe.  The report bridge is injected separately by trusted application
 * code after this sanitization step.
 */
export const sanitizeEmbeddedReportHtml = (html: string, allowTrustedTemplateScripts = false): string => {
  const normalized = normalizeReportHtml(html);
  // SSR cannot draw a report. Keep its text inert until the browser can parse
  // attributes and character references with the same DOM rules as the iframe.
  if (typeof DOMParser === 'undefined')
    return normalized.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const document = new DOMParser().parseFromString(normalized, 'text/html');
  document.querySelectorAll('iframe,object,embed,base,meta[http-equiv]').forEach(node => node.remove());
  if (!allowTrustedTemplateScripts) document.querySelectorAll('script').forEach(node => node.remove());
  document.querySelectorAll('*').forEach(node => {
    [...node.attributes].forEach(attribute => {
      const key = attribute.name.toLowerCase();
      // URL schemes must be checked after removing ASCII controls and spaces.
      // eslint-disable-next-line no-control-regex
      const url = attribute.value.replace(/[\u0000-\u0020]/g, '').toLowerCase();
      if (
        key.startsWith('on') ||
        key === 'srcdoc' ||
        (['href', 'src', 'xlink:href', 'action', 'formaction'].includes(key) &&
          /^(?:javascript:|vbscript:|data:text\/html)/.test(url))
      )
        node.removeAttribute(attribute.name);
    });
  });
  return '<!DOCTYPE html>' + document.documentElement.outerHTML;
};

/**
 * A report occasionally uses a viewport-sized hero (`100vh`).  In srcdoc the
 * viewport is the iframe itself, which creates a height feedback loop: the
 * document never grows beyond its initial height and the rest looks blank.
 * Make the document content-sized before the shared height observer measures
 * it.  This is deliberately presentation-only; persisted report HTML is not
 * changed.
 */
const makeDocumentContentSized = (html: string): string => {
  const reset = '<style>html,body{height:auto!important;min-height:0!important;overflow:visible!important}</style>';
  if (/<\/head>/i.test(html)) return html.replace(/<\/head>/i, `${reset}</head>`);
  if (/<body[^>]*>/i.test(html)) return html.replace(/(<body[^>]*>)/i, `$1${reset}`);
  return `${reset}${html}`;
};

/** Shared lifecycle for every HTML-report preview in the application. */
export const ReportIframe: React.FC<ReportIframeProps> = ({
  srcDoc,
  title = '分析报告',
  iframeRef,
  minHeight = 320,
  maxHeight = 6000,
  className = '',
  onDocumentReady,
}) => {
  const ownedRef = useRef<HTMLIFrameElement>(null);
  const ref = iframeRef || ownedRef;
  const [height, setHeight] = useState(minHeight);
  const cleanupRef = useRef<() => void>();
  const content = makeDocumentContentSized(srcDoc);

  const measure = useCallback(() => {
    const document = ref.current?.contentDocument;
    if (!document?.body) return;
    const next = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, minHeight);
    setHeight(Math.min(next, maxHeight));
  }, [maxHeight, minHeight, ref]);

  const onLoad = useCallback(() => {
    const document = ref.current?.contentDocument;
    if (!document) return;
    cleanupRef.current?.();
    onDocumentReady?.(document);
    measure();
    // The document body is only guaranteed to be the new srcdoc body after
    // load. Observe here (rather than only in a parent effect) so charts that
    // mount after onLoad enlarge the iframe instead of being clipped.
    const observer = new ResizeObserver(measure);
    if (document.body) observer.observe(document.body);
    const timers = [80, 300, 900].map(delay => window.setTimeout(measure, delay));
    cleanupRef.current = () => {
      observer.disconnect();
      timers.forEach(window.clearTimeout);
    };
  }, [measure, onDocumentReady, ref]);

  useEffect(() => {
    return () => {
      cleanupRef.current?.();
      cleanupRef.current = undefined;
    };
  }, [content]);

  return (
    <iframe
      ref={ref}
      title={title}
      srcDoc={content}
      sandbox='allow-scripts allow-same-origin allow-modals'
      className={`block w-full border-0 bg-white ${className}`}
      style={{ height }}
      onLoad={onLoad}
    />
  );
};

export default ReportIframe;
