import { sanitizeEmbeddedReportHtml } from './ReportIframe';

const nextFrame = (source: Document) =>
  new Promise<void>(resolve => {
    const view = source.defaultView;
    if (view?.requestAnimationFrame) {
      view.requestAnimationFrame(() => resolve());
      return;
    }
    window.setTimeout(resolve, 0);
  });

export const waitForReportPaint = async (source: Document) => {
  const fonts = (source as Document & { fonts?: FontFaceSet }).fonts;
  try {
    await fonts?.ready;
  } catch {
    // Font readiness must not prevent a user from exporting the report.
  }
  // Native DB-GPT charts are mounted by React after the srcdoc iframe loads.
  // Two frames let the portal commit and its canvas paint before snapshotting.
  await nextFrame(source);
  await nextFrame(source);
};

const replaceCanvasesWithImages = (snapshot: HTMLHtmlElement, source: Document) => {
  const sourceCanvases = Array.from(source.querySelectorAll('canvas'));
  const snapshotCanvases = Array.from(snapshot.querySelectorAll('canvas'));
  snapshotCanvases.forEach((canvas, index) => {
    const sourceCanvas = sourceCanvases[index];
    if (!sourceCanvas) return;
    try {
      const image = snapshot.ownerDocument.createElement('img');
      image.src = sourceCanvas.toDataURL('image/png');
      image.width = sourceCanvas.width;
      image.height = sourceCanvas.height;
      image.alt = sourceCanvas.getAttribute('aria-label') || '分析图表';
      image.style.cssText =
        'display:block;max-width:100%;width:' +
        (sourceCanvas.clientWidth || sourceCanvas.width) +
        'px;height:' +
        (sourceCanvas.clientHeight || sourceCanvas.height) +
        'px;';
      canvas.replaceWith(image);
    } catch {
      // A tainted third-party canvas cannot be serialized. Keep the original
      // canvas in the snapshot so the browser still gets its best print attempt.
    }
  });
};

/** Remove report-review controls and their implementation metadata from exports. */
const stripEvidenceDecorations = (snapshot: HTMLElement) => {
  snapshot.querySelectorAll('[data-dbgpt-evidence-control="true"]').forEach(node => node.remove());
  snapshot.querySelectorAll<HTMLElement>('[data-dbgpt-artifacts]').forEach(node => {
    node.classList.remove('dbgpt-evidence-host', 'dbgpt-evidence-host--reserve-corner', 'dbgpt-evidence-value');
    node.style.removeProperty('padding-right');
    [...node.attributes].forEach(attribute => {
      if (attribute.name.startsWith('data-dbgpt-')) node.removeAttribute(attribute.name);
    });
  });
};

/** Exports include all folded data and remove viewport-only table clipping. */
const expandReportContent = (snapshot: HTMLElement) => {
  snapshot.querySelectorAll('details').forEach(details => details.setAttribute('open', ''));
  const containers = new Set<HTMLElement>();
  snapshot.querySelectorAll('details, table').forEach(node => {
    let container = node.parentElement;
    while (container) {
      containers.add(container);
      container = container.parentElement;
    }
  });
  containers.forEach(container => {
    container.classList.add('dbgpt-export-data-container');
    container.style.setProperty('height', 'auto', 'important');
    container.style.setProperty('max-height', 'none', 'important');
    container.style.setProperty('overflow', 'visible', 'important');
  });
  snapshot.querySelectorAll<HTMLElement>('th, td').forEach(cell => {
    const text = cell.textContent?.trim() || '';
    const numeric = /^(?:[A-Z]{3}|R\$|[$€£¥])?\s*[+-]?\d[\d.,]*(?:\s*[%‰]|\s*[A-Z]{3})?$/.test(text);
    const date = /^\d{4}-\d{2}(?:-\d{2})?$/.test(text);
    if (numeric || date) {
      cell.style.setProperty('white-space', 'nowrap', 'important');
      cell.style.setProperty('overflow-wrap', 'normal', 'important');
      cell.style.setProperty('word-break', 'normal', 'important');
    }
  });
  const style = snapshot.ownerDocument.createElement('style');
  style.textContent = `
    details { height: auto !important; max-height: none !important; overflow: visible !important; }
    table { width: 100% !important; min-width: 0 !important; max-width: 100% !important; table-layout: auto !important; }
    th, td { white-space: normal !important; word-break: normal !important; overflow-wrap: anywhere; }
    @media print {
      @page { margin: 12mm; }
      .dbgpt-export-data-container { display: block !important; width: auto !important; min-width: 0 !important; max-width: none !important; }
      table { font-size: 9pt !important; }
      th, td { padding: 4px 6px !important; }
      th { position: static !important; }
      thead { display: table-header-group; }
      tr { break-inside: avoid; }
    }
  `;
  snapshot.querySelector('head')?.appendChild(style);
};

const renderedReportSnapshot = async (iframe: HTMLIFrameElement): Promise<string | undefined> => {
  const source = iframe.contentDocument;
  if (!source?.documentElement) return undefined;
  await waitForReportPaint(source);
  const snapshot = source.documentElement.cloneNode(true) as HTMLHtmlElement;
  snapshot.querySelectorAll('script').forEach(script => script.remove());
  stripEvidenceDecorations(snapshot);
  replaceCanvasesWithImages(snapshot, source);
  expandReportContent(snapshot);
  return '<!DOCTYPE html>' + snapshot.outerHTML;
};

/** Serialize the current rendered report as a standalone, presentation-only HTML file. */
export const exportRenderedReportHtml = async (iframe: HTMLIFrameElement): Promise<string | undefined> => {
  try {
    return await renderedReportSnapshot(iframe);
  } catch {
    return undefined;
  }
};

/** Clean a saved HTML report when an iframe preview is not available yet. */
export const cleanReportHtmlForExport = (html: string): string => {
  const document = new DOMParser().parseFromString(sanitizeEmbeddedReportHtml(html), 'text/html');
  const snapshot = document.documentElement;
  snapshot.querySelectorAll('script').forEach(script => script.remove());
  stripEvidenceDecorations(snapshot);
  expandReportContent(snapshot);
  return '<!DOCTYPE html>' + snapshot.outerHTML;
};

/**
 * Print a stable snapshot of the report iframe.
 *
 * Browser print can race with React portals mounted into the report iframe.
 * Snapshotting the painted iframe and serializing canvas charts as images makes
 * the PDF output match what the user sees, without changing the live report.
 */
export const printRenderedReport = async (iframe: HTMLIFrameElement): Promise<boolean> => {
  const printWindow = window.open('', '_blank');
  const source = iframe.contentDocument;
  if (!printWindow || !source?.documentElement) {
    printWindow?.close();
    return false;
  }

  try {
    const snapshot = await renderedReportSnapshot(iframe);
    if (!snapshot) throw new Error('Report document is unavailable');
    printWindow.document.open();
    printWindow.document.write(snapshot);
    printWindow.document.close();
    await new Promise(resolve => window.setTimeout(resolve, 80));
    printWindow.focus();
    printWindow.print();
    printWindow.addEventListener('afterprint', () => printWindow.close(), { once: true });
    return true;
  } catch {
    printWindow.close();
    return false;
  }
};
