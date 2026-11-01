/** Capture the actual shared renderer, including its chart canvases. */
export async function captureDashboardCover(element: HTMLElement): Promise<string> {
  const { default: html2canvas } = await import('html2canvas');
  const document = element.ownerDocument;
  await document.fonts.ready;
  const colors = new Map<string, string>();
  const probe = document.createElement('canvas');
  probe.width = 1;
  probe.height = 1;
  const context = probe.getContext('2d')!;
  const rgb = (input: string) => {
    if (!colors.has(input)) {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = input;
      context.fillRect(0, 0, 1, 1);
      const p = context.getImageData(0, 0, 1, 1).data;
      colors.set(input, `rgba(${p[0]},${p[1]},${p[2]},${p[3] / 255})`);
    }
    return colors.get(input)!;
  };
  const originals = [element, ...element.querySelectorAll<HTMLElement>('*')];
  const nodeKey = 'data-dashboard-cover-node';
  const priorKeys = originals.map(node => node.getAttribute(nodeKey));
  originals.forEach((node, index) => node.setAttribute(nodeKey, String(index)));
  const colorProps = [
    'color',
    'background-color',
    'border-top-color',
    'border-right-color',
    'border-bottom-color',
    'border-left-color',
    'outline-color',
    'text-decoration-color',
  ];
  const computed = originals.map(node => {
    const style = document.defaultView!.getComputedStyle(node);
    return { colors: colorProps.map(p => [p, rgb(style.getPropertyValue(p))]), background: style.backgroundImage };
  });
  // html2canvas measures fonts with a hidden 1px inline image in the host
  // document. Tailwind's block-image reset otherwise shifts text baselines.
  const metricStyle = globalThis.document.createElement('style');
  metricStyle.textContent =
    'body > div[style*="visibility: hidden"][style*="white-space: nowrap"] > img[width="1"][height="1"] { display: inline-block !important; }';
  globalThis.document.head.appendChild(metricStyle);
  try {
    const canvas = await html2canvas(element, {
      width: 1200,
      height: Math.min(750, element.scrollHeight),
      scale: 0.8,
      windowWidth: 1440,
      windowHeight: 1000,
      logging: false,
      backgroundColor: null,
      useCORS: true,
      onclone: (_doc, clone) => {
        // Canvas/SVG cloning may change the DOM order. Match the actual source
        // node so a neighbouring card's fill or text color cannot be applied.
        [clone, ...clone.querySelectorAll<HTMLElement>(`[${nodeKey}]`)].forEach(node => {
          const key = node.getAttribute(nodeKey);
          const value = key === null ? undefined : computed[Number(key)];
          if (!value || !node.style) return;
          value.colors.forEach(([p, c]) => node.style.setProperty(p, c, 'important'));
          node.style.setProperty('box-shadow', 'none', 'important');
          node.style.setProperty('text-shadow', 'none', 'important');
          if (/color-mix|color\(/.test(value.background))
            node.style.setProperty('background-image', 'none', 'important');
        });
      },
    });
    return canvas.toDataURL('image/png');
  } finally {
    metricStyle.remove();
    originals.forEach((node, index) => {
      if (priorKeys[index] === null) node.removeAttribute(nodeKey);
      else node.setAttribute(nodeKey, priorKeys[index]!);
    });
  }
}
