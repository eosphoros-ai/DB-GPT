import { RefObject, useEffect, useState } from 'react';

/** The flex body's content box already subtracts measured header/evidence/footer. */
export function useWidgetContentSize(ref: RefObject<HTMLElement>) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = (width: number, height: number) => {
      const next = { width: Math.max(0, Math.floor(width)), height: Math.max(0, Math.floor(height)) };
      setSize(previous => (previous.width === next.width && previous.height === next.height ? previous : next));
    };
    const style = getComputedStyle(element);
    update(
      element.clientWidth - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0),
      element.clientHeight - (parseFloat(style.paddingTop) || 0) - (parseFloat(style.paddingBottom) || 0),
    );
    const observer = new ResizeObserver(entries => {
      const entry = entries.find(item => item.target === element);
      if (entry) update(entry.contentRect.width, entry.contentRect.height);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}
