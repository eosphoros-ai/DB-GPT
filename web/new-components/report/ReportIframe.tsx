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
  onFrameReady?: () => void;
  /** Legacy/user HTML may execute only in an opaque-origin sandbox. */
  isolated?: boolean;
};

const apiBaseUrl = (process.env.API_BASE_URL ?? '').replace(/\/$/, '');

/** Resolve backend-owned report images before placing the report in srcdoc. */
export const resolveReportAssetUrls = (html: string): string =>
  html.replace(/\bsrc\s*=\s*(["'])\/images\//gi, (_whole, quote: string) => `src=${quote}${apiBaseUrl}/images/`);

/**
 * Report HTML is model-produced content.  Keep its document structure and
 * styles, but remove executable input before mounting it in our same-origin
 * iframe. Scripts can be preserved for an isolated preview or an explicitly
 * trusted server template; HTML markers never establish trust.
 */
export const sanitizeEmbeddedReportHtml = (html: string, preserveScripts = false): string => {
  const normalized = normalizeReportHtml(html);
  // SSR cannot draw a report. Keep its text inert until the browser can parse
  // attributes and character references with the same DOM rules as the iframe.
  if (typeof DOMParser === 'undefined')
    return normalized.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const document = new DOMParser().parseFromString(normalized, 'text/html');
  document.querySelectorAll('iframe,object,embed,base,meta[http-equiv]').forEach(node => node.remove());
  if (!preserveScripts) document.querySelectorAll('script').forEach(node => node.remove());
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

/** Only height and print commands cross the opaque-origin preview boundary. */
export const prepareIsolatedReportHtml = (html: string): string => {
  const bridge = `<script>(function(){
    function measure(){parent.postMessage({type:'dbgpt-preview-height',height:Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)},'*');}
    addEventListener('load',function(){measure();new ResizeObserver(measure).observe(document.body);});
    addEventListener('message',function(event){
      if(event.source!==parent||!event.data)return;
      if(event.data.type==='dbgpt-preview-print')window.print();
      if(event.data.type==='dbgpt-preview-export'){
        var copy=document.documentElement.cloneNode(true);
        copy.querySelectorAll('script').forEach(function(node){node.remove();});
        var canvases=document.querySelectorAll('canvas');
        copy.querySelectorAll('canvas').forEach(function(node,index){try{
          var image=document.createElement('img');image.src=canvases[index].toDataURL();
          image.style.cssText='max-width:100%;height:auto';node.replaceWith(image);
        }catch(error){}});
        parent.postMessage({type:'dbgpt-preview-exported',id:event.data.id,html:'<!DOCTYPE html>'+copy.outerHTML},'*');
      }
    });
  })();</script>`;
  return html.includes('</body>') ? html.replace('</body>', `${bridge}</body>`) : html + bridge;
};

/** Read a presentation snapshot through messages, never through parent DOM access. */
export const exportIsolatedReportHtml = (iframe: HTMLIFrameElement): Promise<string | undefined> =>
  new Promise(resolve => {
    const id = window.crypto.randomUUID();
    const finish = (html?: string) => {
      window.clearTimeout(timer);
      window.removeEventListener('message', receive);
      resolve(html);
    };
    const receive = (event: MessageEvent) => {
      if (
        event.source !== iframe.contentWindow ||
        event.data?.type !== 'dbgpt-preview-exported' ||
        event.data.id !== id
      )
        return;
      if (typeof event.data.html === 'string') finish(event.data.html);
    };
    const timer = window.setTimeout(() => finish(), 5000);
    window.addEventListener('message', receive);
    iframe.contentWindow?.postMessage({ type: 'dbgpt-preview-export', id }, '*');
  });

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
  onFrameReady,
  isolated = false,
}) => {
  const ownedRef = useRef<HTMLIFrameElement>(null);
  const ref = iframeRef || ownedRef;
  const [height, setHeight] = useState(minHeight);
  const cleanupRef = useRef<() => void>();
  const content = makeDocumentContentSized(isolated ? prepareIsolatedReportHtml(srcDoc) : srcDoc);

  const measure = useCallback(() => {
    const document = ref.current?.contentDocument;
    if (!document?.body) return;
    const next = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, minHeight);
    setHeight(Math.min(next, maxHeight));
  }, [maxHeight, minHeight, ref]);

  const onLoad = useCallback(() => {
    onFrameReady?.();
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
  }, [measure, onDocumentReady, onFrameReady, ref]);

  useEffect(() => {
    return () => {
      cleanupRef.current?.();
      cleanupRef.current = undefined;
    };
  }, [content]);

  useEffect(() => {
    if (!isolated) return;
    const receive = (event: MessageEvent) => {
      if (event.source !== ref.current?.contentWindow || event.data?.type !== 'dbgpt-preview-height') return;
      const next = event.data.height;
      if (typeof next === 'number' && Number.isFinite(next)) setHeight(Math.min(Math.max(next, minHeight), maxHeight));
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [isolated, minHeight, maxHeight, ref]);

  return (
    <iframe
      ref={ref}
      title={title}
      srcDoc={content}
      sandbox={isolated ? 'allow-scripts allow-modals' : 'allow-scripts allow-same-origin allow-modals'}
      className={`block w-full border-0 bg-white ${className}`}
      style={{ height }}
      onLoad={onLoad}
    />
  );
};

export default ReportIframe;
