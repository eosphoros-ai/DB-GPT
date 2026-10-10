/** Embed report <img> resources before saving HTML. Scripts/styles are unchanged. */
export async function createHtmlDownloadBlob(html: string): Promise<Blob> {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const apiBase = new URL(process.env.API_BASE_URL || '/', window.location.href);
  const base = new URL(doc.querySelector('base[href]')?.getAttribute('href') || '.', apiBase);
  const images = Array.from(doc.querySelectorAll('img[src]'));
  const cache = new Map<string, Promise<string>>();

  const embed = (src: string): Promise<string> => {
    if (src.startsWith('data:')) return Promise.resolve(src);
    const url = new URL(src, base).href;
    let pending = cache.get(url);
    if (!pending) {
      pending = (async () => {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 20_000);
        try {
          const response = await fetch(url, { signal: controller.signal });
          if (!response.ok) throw new Error(`Image download failed (${response.status})`);
          const blob = await response.blob();
          if (!blob.type.startsWith('image/') || !blob.size) throw new Error('Invalid report image');
          return await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result));
            reader.onerror = () => reject(new Error('Could not read report image'));
            reader.readAsDataURL(blob);
          });
        } finally {
          window.clearTimeout(timeout);
        }
      })();
      cache.set(url, pending);
    }
    return pending;
  };

  await Promise.all(
    images.map(async img => {
      const src = img.getAttribute('src');
      if (!src) return;
      img.setAttribute('src', await embed(src));
      // Use the embedded fallback at every viewport, including <picture>.
      img.removeAttribute('srcset');
      img.removeAttribute('sizes');
      img
        .closest('picture')
        ?.querySelectorAll('source')
        .forEach(source => source.remove());
      img.removeAttribute('loading');
    }),
  );
  if (!doc.querySelector('meta[charset]')) {
    const charset = doc.createElement('meta');
    charset.setAttribute('charset', 'utf-8');
    doc.head.prepend(charset);
  }
  return new Blob(['<!DOCTYPE html>\n', doc.documentElement.outerHTML], { type: 'text/html;charset=utf-8' });
}
