import { saveDashboardCover } from '@/client/api/dashboard';
import { interfaceThemeVariables } from '@/lib/interface-tokens';
import type { DashboardRecord, DashboardSnapshot } from '@/types/dashboard';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import DashboardRenderer from './DashboardRenderer';
import { resolveDashboardTheme } from './dashboard-appearance';
import { captureDashboardCover } from './dashboard-cover-capture';

/** An isolated document avoids duplicating editor controls in the live page. */
export default function DashboardCoverCapture({
  record,
  snapshot,
  onComplete,
}: {
  record: DashboardRecord;
  snapshot: DashboardSnapshot;
  onComplete?: (image: string | null, error?: string) => void;
}) {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const [finished, setFinished] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const appearance = resolveDashboardTheme(record.schema.dashboard.theme);
  useEffect(() => {
    if (!target) return;
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const doc = target.ownerDocument;
        const loads = Array.from(document.head.querySelectorAll('link[rel="stylesheet"],style')).map(node => {
          const clone = node.cloneNode(true) as HTMLLinkElement;
          if (node instanceof HTMLLinkElement) clone.href = node.href;
          const loaded =
            node instanceof HTMLLinkElement
              ? new Promise<void>((resolve, reject) => {
                  clone.onload = () => resolve();
                  clone.onerror = () => reject(new Error('预览样式加载失败'));
                })
              : Promise.resolve();
          doc.head.appendChild(clone);
          return loaded;
        });
        await Promise.race([
          Promise.all(loads),
          new Promise((_, reject) => setTimeout(() => reject(new Error('预览样式加载超时，请重试')), 15000)),
        ]);
        // Give charts one complete layout/paint after fonts and styles settle.
        await doc.fonts.ready;
        await new Promise(resolve => setTimeout(resolve, 1200));
        if (!active || !root.current) return;
        const image = await captureDashboardCover(root.current);
        if (!active) return;
        const response = await saveDashboardCover(record.id, record.current_revision, image);
        if (!response.data.success) throw new Error(response.data.err_msg || '预览保存失败');
        if (active) {
          setFinished(true);
          onComplete?.(image);
        }
      } catch (e) {
        if (active) {
          setFinished(true);
          onComplete?.(null, e instanceof Error ? e.message : '预览生成失败');
        }
      }
    }, 700);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [target, record.id, record.current_revision, onComplete]);
  if (finished) return null;
  return (
    <iframe
      title='生成看板预览'
      aria-hidden='true'
      tabIndex={-1}
      style={{ position: 'fixed', left: -20000, top: 0, width: 1200, height: 1000, border: 0, pointerEvents: 'none' }}
      srcDoc='<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"></body></html>'
      onLoad={e => setTarget(e.currentTarget.contentDocument?.body || null)}
    >
      {target &&
        createPortal(
          <div
            ref={root}
            style={{
              ...interfaceThemeVariables(appearance),
              width: 1200,
              padding: 18,
              background: 'var(--app-background)',
              color: 'var(--app-text)',
            }}
          >
            <DashboardRenderer schema={record.schema} snapshot={snapshot} />
          </div>,
          target,
        )}
    </iframe>
  );
}
