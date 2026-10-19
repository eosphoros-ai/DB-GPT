/**
 * Shared image/HTML URL resolution for chat content components.
 *
 * Generated image artifacts store backend-relative URLs like
 * `/images/xxx.png`. In dev mode the page is served by the Next dev
 * server (e.g. :3000) while those files are served by the dbgpt
 * backend (API_BASE_URL, e.g. :5670), so relative `<img src>` would
 * 404. These helpers prefix the backend origin so thumbnails and
 * report-embedded charts render.
 */

/** Resolve image paths like `/images/xxx.png` to full backend URLs in dev mode */
export const resolveImageUrl = (src: string): string => {
  if (!src) return src;
  if (/^https?:\/\//.test(src)) return src;
  if (src.startsWith('/images/')) {
    const base = process.env.API_BASE_URL || '';
    return base ? `${base}${src}` : src;
  }
  return src;
};

/** Replace `/images/...` references inside HTML content with full backend URLs */
export const resolveHtmlImageUrls = (html: string): string => {
  const base = process.env.API_BASE_URL || '';
  if (!base || !html) return html;
  return html.replace(/(src\s*=\s*["'])\/images\//gi, `$1${base}/images/`);
};
