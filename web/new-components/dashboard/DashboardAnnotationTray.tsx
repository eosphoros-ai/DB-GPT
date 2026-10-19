import { CommentOutlined, DeleteOutlined, EditOutlined, SendOutlined } from '@ant-design/icons';
import { Badge, Button, Empty, Popover } from 'antd';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import type { DashboardAnnotationDraft } from './dashboard-assistant';
import type { SavedDashboardAnnotation } from './dashboard-assistant-session';
import styles from './DashboardAssistantPanel.module.css';

const positionKey = 'dashboard-annotation-tray-position:v1';
type Position = { x: number; y: number };

export default function DashboardAnnotationTray({
  themeStyle,
  saved,
  draftCount,
  open,
  running,
  onOpenChange,
  onEdit,
  onRemove,
  onSend,
}: {
  themeStyle?: CSSProperties;
  saved: SavedDashboardAnnotation[];
  draftCount: number;
  open: boolean;
  running: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: (draft: DashboardAnnotationDraft) => void;
  onRemove: (id: string) => void;
  onSend: () => void;
}) {
  const anchor = useRef<HTMLDivElement>(null);
  const drag = useRef<{ pointerId: number; start: Position; origin: Position; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const [host, setHost] = useState<HTMLElement | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [dragging, setDragging] = useState(false);
  const constrain = (next: Position): Position => {
    const rect = anchor.current?.getBoundingClientRect();
    return {
      x: Math.max(8, Math.min(next.x, window.innerWidth - (rect?.width || 128) - 8)),
      y: Math.max(8, Math.min(next.y, window.innerHeight - (rect?.height || 40) - 8)),
    };
  };
  const remember = (next: Position) => {
    try {
      localStorage.setItem(positionKey, JSON.stringify(next));
    } catch {
      /* Dragging still works when storage is unavailable. */
    }
  };
  useEffect(() => {
    const frame = requestAnimationFrame(() => setHost(document.body));
    return () => cancelAnimationFrame(frame);
  }, []);
  useEffect(() => {
    if (!host) return;
    const frame = requestAnimationFrame(() => {
      try {
        const savedPosition = JSON.parse(localStorage.getItem(positionKey) || 'null');
        if (Number.isFinite(savedPosition?.x) && Number.isFinite(savedPosition?.y))
          setPosition(constrain(savedPosition));
      } catch {
        /* Use the default bottom-right position. */
      }
    });
    const resize = () => setPosition(current => (current ? constrain(current) : null));
    window.addEventListener('resize', resize);
    const observer = new ResizeObserver(resize);
    if (anchor.current) observer.observe(anchor.current);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      observer.disconnect();
    };
  }, [host]);
  if (!host) return null;
  return createPortal(
    <div
      ref={anchor}
      className={styles.trayAnchor}
      style={{
        ...themeStyle,
        ...(position ? { left: position.x, top: position.y, right: 'auto', bottom: 'auto' } : {}),
      }}
    >
      <Popover
        open={open}
        onOpenChange={onOpenChange}
        trigger='click'
        placement='top'
        overlayStyle={themeStyle}
        overlayInnerStyle={{ background: 'var(--app-surface)', color: 'var(--app-text)' }}
        title='本次保存的批注'
        content={
          <div className={styles.tray} data-testid='annotation-tray'>
            <div className={styles.trayList}>
              {saved.map((item, index) => (
                <article key={item.id} className={styles.annotation} data-testid='annotation-queue-item'>
                  <div className={styles.annotationHeader}>
                    <span>{index + 1}.</span>
                    <strong>{item.target.label}</strong>
                    {item.state !== 'sent' && (
                      <>
                        <Button
                          type='text'
                          size='small'
                          aria-label={`编辑 ${item.target.label} 批注`}
                          icon={<EditOutlined />}
                          disabled={running}
                          onClick={() => {
                            onOpenChange(false);
                            onEdit(item);
                          }}
                        />
                        <Button
                          type='text'
                          size='small'
                          danger
                          aria-label={`删除 ${item.target.label} 批注`}
                          icon={<DeleteOutlined />}
                          disabled={running}
                          onClick={() => onRemove(item.id)}
                        />
                      </>
                    )}
                  </div>
                  <small>
                    {item.dashboardTitle} · {item.chartType} ·{' '}
                    {item.state === 'saved' ? '已保存' : item.state === 'discussing' ? '对话中补充' : '已发送'}
                  </small>
                  <p>{item.content}</p>
                </article>
              ))}
              {!saved.length && (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='在图表上保存批注，会自动记录到这里' />
              )}
            </div>
            <Button
              type='primary'
              aria-label={`一起发送给 AI（${draftCount} 条）`}
              icon={<SendOutlined />}
              disabled={!draftCount || running}
              onClick={onSend}
            >
              一起发送给 AI（{draftCount} 条）
            </Button>
          </div>
        }
      >
        <Button
          className={styles.trayButton}
          data-testid='annotation-tray-trigger'
          data-dragging={dragging}
          title='点击查看批注；拖动可移动位置，Alt + 方向键微调'
          onPointerDown={event => {
            if (event.button !== 0 || !event.isPrimary) return;
            const rect = anchor.current!.getBoundingClientRect();
            suppressClick.current = false;
            drag.current = {
              pointerId: event.pointerId,
              start: { x: event.clientX, y: event.clientY },
              origin: { x: rect.left, y: rect.top },
              moved: false,
            };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={event => {
            const current = drag.current;
            if (!current || current.pointerId !== event.pointerId) return;
            const dx = event.clientX - current.start.x;
            const dy = event.clientY - current.start.y;
            if (!current.moved && Math.hypot(dx, dy) < 5) return;
            if (!current.moved) {
              current.moved = true;
              setDragging(true);
              onOpenChange(false);
            }
            event.preventDefault();
            setPosition(constrain({ x: current.origin.x + dx, y: current.origin.y + dy }));
          }}
          onPointerUp={event => {
            const current = drag.current;
            if (!current || current.pointerId !== event.pointerId) return;
            if (current.moved) {
              suppressClick.current = true;
              const next = constrain({
                x: current.origin.x + event.clientX - current.start.x,
                y: current.origin.y + event.clientY - current.start.y,
              });
              setPosition(next);
              remember(next);
            }
            drag.current = null;
            setDragging(false);
          }}
          onLostPointerCapture={() => {
            drag.current = null;
            setDragging(false);
          }}
          onPointerCancel={() => {
            suppressClick.current = true;
            drag.current = null;
            setDragging(false);
          }}
          onClickCapture={event => {
            if (!suppressClick.current || event.detail === 0) return;
            event.preventDefault();
            event.stopPropagation();
            suppressClick.current = false;
          }}
          onKeyDown={event => {
            if (!event.altKey || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
            event.preventDefault();
            const rect = anchor.current!.getBoundingClientRect();
            const step = event.shiftKey ? 40 : 10;
            const next = constrain({
              x: rect.left + (event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0),
              y: rect.top + (event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0),
            });
            setPosition(next);
            remember(next);
            onOpenChange(false);
          }}
          aria-label={`本次批注 ${saved.length} 条`}
          aria-expanded={open}
          icon={<CommentOutlined />}
        >
          批注 <Badge count={saved.length} showZero color='var(--app-accent)' />
        </Button>
      </Popover>
    </div>,
    host,
  );
}
