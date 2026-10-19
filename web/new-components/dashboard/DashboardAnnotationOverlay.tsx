import { statusTagStyle } from '@/lib/interface-tokens';
import { DashboardAnnotationRecord, DashboardSelectionTarget } from '@/types/dashboard';
import { CheckOutlined, CloseOutlined, CommentOutlined, DragOutlined, LoadingOutlined } from '@ant-design/icons';
import { Alert, Button, Input, Select, Tag } from 'antd';
import {
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';

export interface DashboardAnnotationSelection {
  target: DashboardSelectionTarget;
  anchor: DOMRect;
  suggestedPrompt?: string;
  draftId?: string;
}

interface DashboardAnnotationOverlayProps {
  themeStyle?: CSSProperties;
  selection: DashboardAnnotationSelection | null;
  annotations: DashboardAnnotationRecord[];
  creating?: boolean;
  applyingId?: string | null;
  onTargetChange: (target: DashboardSelectionTarget) => void;
  onCreate: (prompt: string) => Promise<void>;
  onApply: (annotation: DashboardAnnotationRecord) => Promise<void>;
  onReject: (annotation: DashboardAnnotationRecord) => Promise<void>;
  onClose: () => void;
}

const kindLabels: Record<DashboardSelectionTarget['kind'], string> = {
  dashboard: '整个看板',
  widget: '整个组件',
  filter: '当前全局筛选器',
  chart_datum: '当前数据点',
  chart_series: '当前系列',
  table_column: '当前表格列',
  table_cell: '当前单元格',
};

const sameTarget = (left: DashboardSelectionTarget, right: DashboardSelectionTarget) =>
  (left.widget_id ?? null) === (right.widget_id ?? null) &&
  (left.filter_id ?? null) === (right.filter_id ?? null) &&
  left.kind === right.kind &&
  (left.series ?? null) === (right.series ?? null) &&
  (left.column ?? null) === (right.column ?? null) &&
  JSON.stringify(left.datum_key) === JSON.stringify(right.datum_key) &&
  JSON.stringify(left.row_key) === JSON.stringify(right.row_key);

const makeScopeOptions = (target: DashboardSelectionTarget) => {
  const options: { label: string; value: DashboardSelectionTarget['kind'] }[] = [
    { label: kindLabels[target.kind], value: target.kind },
  ];
  if (target.kind === 'filter' || target.kind === 'dashboard') return options;
  if (target.kind === 'chart_datum' && target.series) {
    options.push({ label: `整个系列：${target.series}`, value: 'chart_series' });
  }
  if (target.kind !== 'widget') options.push({ label: '整个组件', value: 'widget' });
  return options;
};

const VIEWPORT_MARGIN = 12;
const PANEL_WIDTH = 360;
const ESTIMATED_PANEL_HEIGHT = 360;

interface OverlayPosition {
  left: number;
  top: number;
}

const clamp = (value: number, minimum: number, maximum: number) =>
  Math.max(minimum, Math.min(Math.max(minimum, maximum), value));

const initialOverlayPosition = (anchor: Pick<DOMRect, 'left' | 'right' | 'top'>): OverlayPosition => {
  const availableWidth = Math.max(0, window.innerWidth - VIEWPORT_MARGIN * 2);
  const panelWidth = Math.min(PANEL_WIDTH, availableWidth);
  const panelHeight = Math.min(ESTIMATED_PANEL_HEIGHT, Math.max(0, window.innerHeight - VIEWPORT_MARGIN * 2));
  const rightCandidate = anchor.right + 10;
  const leftCandidate = anchor.left - panelWidth - 10;
  const left =
    rightCandidate + panelWidth <= window.innerWidth - VIEWPORT_MARGIN
      ? rightCandidate
      : leftCandidate >= VIEWPORT_MARGIN
        ? leftCandidate
        : clamp(anchor.left, VIEWPORT_MARGIN, window.innerWidth - panelWidth - VIEWPORT_MARGIN);

  return {
    left,
    top: clamp(anchor.top, VIEWPORT_MARGIN, window.innerHeight - panelHeight - VIEWPORT_MARGIN),
  };
};

const clampOverlayPosition = (position: OverlayPosition, panel: HTMLDivElement | null): OverlayPosition => {
  const availableWidth = Math.max(0, window.innerWidth - VIEWPORT_MARGIN * 2);
  const availableHeight = Math.max(0, window.innerHeight - VIEWPORT_MARGIN * 2);
  const rect = panel?.getBoundingClientRect();
  const panelWidth = rect?.width || Math.min(PANEL_WIDTH, availableWidth);
  const panelHeight = rect?.height || Math.min(ESTIMATED_PANEL_HEIGHT, availableHeight);

  return {
    left: clamp(position.left, VIEWPORT_MARGIN, window.innerWidth - panelWidth - VIEWPORT_MARGIN),
    top: clamp(position.top, VIEWPORT_MARGIN, window.innerHeight - panelHeight - VIEWPORT_MARGIN),
  };
};

export default function DashboardAnnotationOverlay({
  themeStyle,
  selection,
  annotations,
  creating,
  applyingId,
  onTargetChange,
  onCreate,
  onApply,
  onReject,
  onClose,
}: DashboardAnnotationOverlayProps) {
  const [expanded, setExpanded] = useState(
    Boolean(selection?.draftId || selection?.suggestedPrompt) ||
      !annotations.some(item => selection && sameTarget(item.target, selection.target)),
  );
  const [prompt, setPrompt] = useState(selection?.suggestedPrompt || '');
  const [position, setPosition] = useState<OverlayPosition>({ left: VIEWPORT_MARGIN, top: VIEWPORT_MARGIN });
  const panelRef = useRef<HTMLDivElement>(null);
  const dragStateRef = useRef<{ pointerId: number; offsetX: number; offsetY: number } | null>(null);

  const isOpen = Boolean(selection);
  const anchorLeft = selection?.anchor.left ?? 0;
  const anchorRight = selection?.anchor.right ?? 0;
  const anchorTop = selection?.anchor.top ?? 0;

  useEffect(() => {
    if (!isOpen || typeof window === 'undefined') return;
    const frame = window.requestAnimationFrame(() => {
      setPosition(initialOverlayPosition({ left: anchorLeft, right: anchorRight, top: anchorTop }));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [anchorLeft, anchorRight, anchorTop, isOpen]);

  useEffect(() => {
    if (!isOpen || typeof window === 'undefined') return;

    const keepInsideViewport = () => {
      setPosition(current => clampOverlayPosition(current, panelRef.current));
    };
    const frame = window.requestAnimationFrame(keepInsideViewport);
    const observer =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(() => {
            keepInsideViewport();
          });
    if (panelRef.current) observer?.observe(panelRef.current);
    window.addEventListener('resize', keepInsideViewport);

    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener('resize', keepInsideViewport);
    };
  }, [isOpen]);

  const related = useMemo(
    () => (selection ? annotations.filter(item => sameTarget(item.target, selection.target)) : []),
    [annotations, selection],
  );
  const latest = related[0] || null;

  if (!selection || typeof document === 'undefined') return null;
  const scopeOptions = makeScopeOptions(selection.target);

  const beginDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    dragStateRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  };

  const continueDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    setPosition(
      clampOverlayPosition(
        {
          left: event.clientX - dragState.offsetX,
          top: event.clientY - dragState.offsetY,
        },
        panelRef.current,
      ),
    );
    event.preventDefault();
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragStateRef.current?.pointerId !== event.pointerId) return;
    dragStateRef.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  };

  const moveWithKeyboard = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const distance = event.shiftKey ? 24 : 8;
    const offsets: Partial<Record<typeof event.key, OverlayPosition>> = {
      ArrowLeft: { left: -distance, top: 0 },
      ArrowRight: { left: distance, top: 0 },
      ArrowUp: { left: 0, top: -distance },
      ArrowDown: { left: 0, top: distance },
    };
    const offset = offsets[event.key];
    if (!offset) return;
    setPosition(current =>
      clampOverlayPosition({ left: current.left + offset.left, top: current.top + offset.top }, panelRef.current),
    );
    event.preventDefault();
  };

  const changeScope = (kind: DashboardSelectionTarget['kind']) => {
    if (kind === selection.target.kind) return;
    if (selection.target.kind === 'filter') return;
    if (kind === 'widget') {
      onTargetChange({
        kind,
        widget_id: selection.target.widget_id,
        label: `组件：${selection.target.widget_id}`,
        datum_key: {},
        row_key: {},
      });
      return;
    }
    if (kind === 'chart_series') {
      onTargetChange({
        ...selection.target,
        kind,
        label: `系列：${selection.target.series}`,
        datum_key: {},
        value: undefined,
      });
    }
  };

  return createPortal(
    <div
      ref={panelRef}
      data-testid='dashboard-annotation-overlay'
      className='fixed z-[1200] flex max-h-[calc(100vh-24px)] w-[360px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] shadow-2xl'
      style={{ ...themeStyle, color: 'var(--app-text)', left: position.left, top: position.top }}
      role='dialog'
      aria-label='看板批注'
    >
      <div
        className='flex flex-none cursor-move touch-none select-none items-center gap-2 border-b border-[var(--app-border)] px-4 py-3'
        role='button'
        tabIndex={0}
        aria-label='拖动批注窗口'
        title='拖动批注窗口；也可使用方向键移动'
        onPointerDown={beginDrag}
        onPointerMove={continueDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={moveWithKeyboard}
      >
        <DragOutlined className='text-[var(--app-muted)]' />
        <CommentOutlined className='text-[var(--app-accent)]' />
        <strong className='min-w-0 flex-1 truncate text-sm'>添加批注</strong>
        <span className='hidden text-xs font-normal text-[var(--app-muted)] sm:inline'>拖动</span>
        <Button
          aria-label='关闭批注'
          type='text'
          size='small'
          icon={<CloseOutlined />}
          onPointerDown={event => event.stopPropagation()}
          onClick={onClose}
        />
      </div>
      <div data-testid='dashboard-annotation-scroll-area' className='min-h-0 flex-1 space-y-3 overflow-y-auto p-4'>
        <div className='border-l-2 border-[var(--app-accent)] pl-3 text-xs text-[var(--app-muted)]'>
          <div className='font-medium'>{selection.target.label}</div>
        </div>

        {scopeOptions.length > 1 && (
          <label className='block text-xs text-[var(--app-muted)]'>
            批注范围
            <Select
              aria-label='批注修改范围'
              className='mt-1 w-full'
              value={selection.target.kind}
              options={scopeOptions}
              onChange={changeScope}
            />
          </label>
        )}

        {!expanded && !latest && (
          <Button type='primary' block icon={<CommentOutlined />} onClick={() => setExpanded(true)}>
            添加批注
          </Button>
        )}

        {(expanded || !latest) && (
          <div className={expanded ? 'block' : 'hidden'}>
            <Input.TextArea
              autoFocus
              aria-label='批注内容'
              value={prompt}
              autoSize={{ minRows: 3, maxRows: 7 }}
              maxLength={4000}
              showCount
              placeholder='例如：把这个门店系列改成横向条形图，并按销售额降序。'
              onChange={event => setPrompt(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Escape') onClose();
                if (
                  event.key === 'Enter' &&
                  (event.metaKey || event.ctrlKey) &&
                  !event.nativeEvent.isComposing &&
                  prompt.trim() &&
                  !creating
                ) {
                  event.preventDefault();
                  void onCreate(prompt.trim());
                }
              }}
            />
            <div className='mt-8 flex justify-end gap-2'>
              <Button onClick={onClose}>取消</Button>
              <Button
                type='primary'
                loading={creating}
                disabled={!prompt.trim()}
                onClick={async () => {
                  await onCreate(prompt.trim());
                  setPrompt('');
                  setExpanded(false);
                }}
              >
                保存批注
              </Button>
            </div>
          </div>
        )}

        {latest && (
          <div className='space-y-3'>
            <div className='flex items-center gap-2'>
              <Tag
                style={statusTagStyle(
                  latest.status === 'proposed'
                    ? 'accent'
                    : latest.status === 'applied'
                      ? 'success'
                      : latest.status === 'invalidated'
                        ? 'danger'
                        : 'warning',
                )}
              >
                {latest.status === 'pending'
                  ? '等待 Agent 提案'
                  : latest.status === 'proposed'
                    ? '变更待确认'
                    : latest.status === 'applied'
                      ? '已应用'
                      : latest.status === 'rejected'
                        ? '已放弃'
                        : '已失效'}
              </Tag>
              {latest.status === 'pending' && <LoadingOutlined className='text-[var(--app-accent)]' />}
            </div>
            <div className='rounded-lg border border-[var(--app-border)] p-3 text-sm'>
              <div className='text-xs text-[var(--app-muted)]'>你的要求</div>
              <p className='mt-1 whitespace-pre-wrap'>{latest.prompt}</p>
            </div>
            {latest.proposal && (
              <div className='rounded-lg border border-[var(--app-border)] bg-[var(--app-accent-soft)] p-3'>
                <div className='text-xs font-semibold text-[var(--app-accent)]'>Agent 变更方案</div>
                <p className='mt-1 text-sm'>{latest.proposal.summary}</p>
                <div className='mt-3 grid grid-cols-2 gap-2 text-xs'>
                  <div className='rounded bg-[var(--app-surface)] p-2'>
                    <div className='mb-1 font-medium text-[var(--app-muted)]'>修改前</div>
                    {latest.proposal.before.length
                      ? latest.proposal.before.map(item => <div key={item}>• {item}</div>)
                      : '以当前草稿为准'}
                  </div>
                  <div className='rounded bg-[var(--app-surface)] p-2'>
                    <div className='mb-1 font-medium text-[var(--app-muted)]'>修改后</div>
                    {latest.proposal.after.length
                      ? latest.proposal.after.map(item => <div key={item}>• {item}</div>)
                      : '见方案摘要'}
                  </div>
                </div>
                {latest.proposal.validation.valid ? (
                  <Alert className='mt-3' type='success' showIcon message='Schema 与受影响查询已验证' />
                ) : (
                  <Alert className='mt-3' type='error' showIcon message='验证未通过，不能应用' />
                )}
                {latest.status === 'proposed' && (
                  <div className='mt-3 flex justify-end gap-2'>
                    <Button
                      aria-label='放弃提案'
                      icon={<CloseOutlined />}
                      disabled={!!applyingId}
                      onClick={() => void onReject(latest)}
                    >
                      放弃
                    </Button>
                    <Button
                      aria-label='应用到草稿'
                      type='primary'
                      icon={<CheckOutlined />}
                      loading={applyingId === latest.id}
                      disabled={!latest.proposal.validation.valid}
                      onClick={() => void onApply(latest)}
                    >
                      应用到草稿
                    </Button>
                  </div>
                )}
              </div>
            )}
            {latest.status === 'invalidated' && !latest.proposal && (
              <Alert
                type='error'
                showIcon
                message='数据助理未生成有效方案'
                description='这次提案未通过 Patch 或查询校验，已停止等待。请重新提交更明确的要求，或改用手动配置。'
              />
            )}
            {latest.status !== 'pending' && latest.status !== 'proposed' && (
              <Button block onClick={() => setExpanded(true)}>
                再写一条批注
              </Button>
            )}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
