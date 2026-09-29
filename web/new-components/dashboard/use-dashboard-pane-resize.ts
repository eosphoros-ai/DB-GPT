import { useEffect, useId, useRef, useState, type HTMLAttributes } from 'react';

const STORAGE_KEY = 'dbgpt-dashboard-pane-widths-v1';
const DEFAULTS = { components: 218, assistant: 320, visual: 304, query: 420 };
type PaneKey = keyof typeof DEFAULTS;
type Side = 'left' | 'right';
const clamp = (value: number, min: number, max: number) => Math.round(Math.min(max, Math.max(min, value)));

export function useDashboardPaneResize({
  libraryMode,
  settingsMode,
  leftVisible,
  rightVisible,
  compact,
}: {
  libraryMode: 'components' | 'assistant';
  settingsMode: 'visual' | 'query';
  leftVisible: boolean;
  rightVisible: boolean;
  compact: boolean;
}) {
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(1280);
  const [widths, setWidths] = useState(DEFAULTS);
  const [loaded, setLoaded] = useState(false);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ side: Side; x: number; width: number } | null>(null);
  const id = useId();
  const leftId = `${id}-library`;
  const rightId = `${id}-settings`;

  useEffect(() => {
    // Restore browser preferences after hydration, before enabling persistence.
    const frame = requestAnimationFrame(() => {
      try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        setWidths(
          Object.fromEntries(
            Object.entries(DEFAULTS).map(([key, fallback]) => [
              key,
              typeof saved[key] === 'number' && Number.isFinite(saved[key]) ? clamp(saved[key], 180, 1200) : fallback,
            ]),
          ) as typeof DEFAULTS,
        );
      } catch {
        /* A blocked or outdated preference must not prevent editing. */
      }
      setLoaded(true);
    });
    return () => cancelAnimationFrame(frame);
  }, []);
  useEffect(() => {
    if (!loaded || dragging) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(widths));
    } catch {
      /* Optional browser preference. */
    }
  }, [widths, loaded, dragging]);
  useEffect(() => {
    const node = workspaceRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!dragging) return;
    const { cursor, userSelect } = document.body.style;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.body.style.cursor = cursor;
      document.body.style.userSelect = userSelect;
    };
  }, [dragging]);

  const minLeft = Math.min(libraryMode === 'assistant' ? 260 : 180, Math.max(160, containerWidth - 44));
  const minRight = Math.min(260, Math.max(160, containerWidth - 44));
  // Reserve room for the canvas and collapsed rails on desktop; compact panels overlay it.
  const budget = Math.max(0, containerWidth - 320 - (leftVisible ? 0 : 34) - (rightVisible ? 0 : 34));
  let left = clamp(widths[libraryMode], minLeft, compact ? Math.max(minLeft, containerWidth - 44) : 1200);
  let right = clamp(widths[settingsMode], minRight, compact ? Math.max(minRight, containerWidth - 44) : 1200);
  if (!compact) {
    const total = (leftVisible ? left : 0) + (rightVisible ? right : 0);
    const minimum = (leftVisible ? minLeft : 0) + (rightVisible ? minRight : 0);
    if (total > budget && total > minimum) {
      const ratio = Math.max(0, (budget - minimum) / (total - minimum));
      left = Math.round(minLeft + (left - minLeft) * ratio);
      right = Math.round(minRight + (right - minRight) * ratio);
    }
  }
  const bounds = (side: Side) => {
    const min = side === 'left' ? minLeft : minRight;
    const other = side === 'left' ? (rightVisible ? right : 0) : leftVisible ? left : 0;
    return { min, max: Math.max(min, compact ? containerWidth - 44 : budget - other) };
  };
  const resize = (side: Side, value: number) => {
    const { min, max } = bounds(side);
    const key: PaneKey = side === 'left' ? libraryMode : settingsMode;
    // Commit the other visible size too, so dragging never moves the opposite divider.
    setWidths(current => ({ ...current, [libraryMode]: left, [settingsMode]: right, [key]: clamp(value, min, max) }));
  };
  const stop = () => {
    drag.current = null;
    setDragging(false);
  };
  const separatorProps = (side: Side): HTMLAttributes<HTMLDivElement> => {
    const { min, max } = bounds(side);
    const width = side === 'left' ? left : right;
    return {
      role: 'separator',
      tabIndex: 0,
      'aria-orientation': 'vertical',
      'aria-label': side === 'left' ? '调整左侧编辑栏宽度' : '调整右侧设置与 SQL 栏宽度',
      'aria-controls': side === 'left' ? leftId : rightId,
      'aria-valuemin': min,
      'aria-valuemax': max,
      'aria-valuenow': width,
      title: '拖动调整宽度；双击恢复；方向键微调',
      style: side === 'left' ? { left: left - 5 } : { right: right - 5 },
      onPointerDown: event => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus();
        event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = { side, x: event.clientX, width };
        setDragging(true);
      },
      onPointerMove: event => {
        const active = drag.current;
        if (active?.side !== side) return;
        resize(side, active.width + (event.clientX - active.x) * (side === 'left' ? 1 : -1));
      },
      onPointerUp: stop,
      onPointerCancel: stop,
      onLostPointerCapture: stop,
      onDoubleClick: () => resize(side, DEFAULTS[side === 'left' ? libraryMode : settingsMode]),
      onKeyDown: event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const step = (event.shiftKey ? 40 : 10) * (side === 'left' ? 1 : -1);
        resize(
          side,
          event.key === 'Home' ? min : event.key === 'End' ? max : width + (event.key === 'ArrowRight' ? step : -step),
        );
      },
    };
  };
  return { workspaceRef, left, right, leftId, rightId, separatorProps };
}
