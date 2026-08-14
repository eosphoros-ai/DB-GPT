/**
 * Composer attachment strip.
 *
 * This is the draft-only surface that lives inside the home composer, above
 * the textarea. It follows the multi-file mockup: fixed-width file cards,
 * two-row wrapping, clear upload/parsing/error states, inline progress, a
 * folded "+N" remainder, and an optional add-file card owned by the caller.
 */

import { CheckCircleFilled, CloseOutlined, LoadingOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { Alert, Drawer, Spin, Tooltip } from 'antd';
import classNames from 'classnames';
import React, { ReactNode, memo, useEffect, useMemo, useState } from 'react';

import AttachmentPreview, { FileKindIcon } from './AttachmentPreview';
import type { RailItem } from './attachment-view-model';
import {
  PREVIEW_DESKTOP_MIN_WIDTH,
  REDUCED_MOTION_CLASS,
  aggregateUploadProgress,
  canPreviewItem,
  canRetry,
  collapseRail,
  formatBytes,
  isHardFailure,
  motionClassName,
  progressPercent,
  removeAriaLabel,
  resolvePreviewOverlay,
  retryAriaLabel,
  toLegacyRailItem,
  toRailItems,
} from './attachment-view-model';
import type { DraftFile, LegacyServerFile, SessionFilePreviewSnapshot } from './types';

/** Live preview state pushed down by the parent; fetching stays outside. */
export interface RailPreviewState {
  snapshot: SessionFilePreviewSnapshot | null;
  loading: boolean;
  error: string | null;
  /** Display size of the previewed file (bytes). */
  size?: number;
}

export interface AttachmentRailProps {
  drafts: readonly DraftFile[];
  /**
   * Legacy server-preloaded example files (read-only). Mutually exclusive
   * with local drafts in the session-files state machine.
   */
  legacyFiles?: readonly LegacyServerFile[];
  onRemove?: (clientId: string) => void;
  onRetry?: (clientId: string) => void;
  onPreview?: (item: RailItem) => void;
  onLegacyPreview?: (file: LegacyServerFile) => void;
  onClearAll?: () => void;
  /** Optional upload entry rendered as the final dashed card. */
  addControl?: ReactNode;
  /** When set, the rail renders the overlay preview (Drawer below 1024px). */
  preview?: RailPreviewState | null;
  onClosePreview?: () => void;
  className?: string;
}

/** SSR-safe viewport width; defaults to desktop before hydration. */
function useViewportWidth(): number {
  const [width, setWidth] = useState<number>(() =>
    typeof window === 'undefined' ? PREVIEW_DESKTOP_MIN_WIDTH : window.innerWidth,
  );
  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return width;
}

/** SSR-safe `prefers-reduced-motion: reduce` media listener. */
function usePrefersReducedMotion(): boolean {
  const query = '(prefers-reduced-motion: reduce)';
  const [reduced, setReduced] = useState<boolean>(
    () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia(query);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    setReduced(media.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

const FILE_CARD_WIDTH = 'w-[228px] max-w-full';

const statusErrorText = (error: string | null): string => {
  const map: Record<string, string> = {
    DUPLICATE_FILE: '重复文件',
    FILE_TOO_LARGE: '超过大小限制',
    TOO_MANY_FILES: '文件数量超限',
    REQUEST_TOO_LARGE: '总大小超限',
  };
  return error ? map[error] || error : '上传失败';
};

const BaseFileCard: React.FC<{
  name: string;
  mediaType?: string;
  kind?: string;
  tone: 'ready' | 'uploading' | 'parsing' | 'error' | 'legacy';
  status: ReactNode;
  title?: string;
  onClick?: () => void;
  children?: ReactNode;
}> = memo(({ name, mediaType, kind, tone, status, title, onClick, children }) => (
  <div
    role={onClick ? 'button' : undefined}
    tabIndex={onClick ? 0 : undefined}
    onClick={onClick}
    onKeyDown={event => {
      if (!onClick) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick();
      }
    }}
    title={title}
    className={classNames(
      'group relative flex min-h-[52px] items-center gap-2.5 rounded-xl border px-3 py-2 transition-all duration-200',
      FILE_CARD_WIDTH,
      onClick && 'cursor-pointer',
      tone === 'ready' &&
        'border-slate-200 bg-white hover:border-emerald-300 dark:border-slate-700/60 dark:bg-[#212226] dark:hover:border-emerald-700',
      tone === 'legacy' &&
        'border-slate-200 bg-slate-50/70 hover:border-emerald-300 dark:border-slate-700/60 dark:bg-[#212226] dark:hover:border-emerald-700',
      tone === 'uploading' &&
        'overflow-hidden border-blue-300 bg-blue-50/50 dark:border-blue-700/70 dark:bg-blue-900/15',
      tone === 'parsing' &&
        'overflow-hidden border-amber-300 bg-amber-50/50 dark:border-amber-700/70 dark:bg-amber-900/15',
      tone === 'error' && 'border-red-300 bg-red-50/60 dark:border-red-800/70 dark:bg-red-900/15',
    )}
  >
    <div
      className={classNames(
        'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-[15px]',
        tone === 'error'
          ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
          : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
      )}
    >
      <FileKindIcon name={name} mediaType={mediaType} kind={kind} className='text-base' />
    </div>
    <div className='min-w-0 flex-1'>
      <div className='truncate text-[13px] font-medium text-slate-800 dark:text-slate-100' title={name}>
        {name}
      </div>
      <div className='mt-0.5 flex min-w-0 items-center gap-1 text-[11px] text-slate-400 dark:text-slate-500'>
        {status}
      </div>
    </div>
    {children}
  </div>
));

BaseFileCard.displayName = 'BaseFileCard';

const LegacyRailItemCard: React.FC<{
  file: LegacyServerFile;
  onPreview?: (file: LegacyServerFile) => void;
}> = memo(({ file, onPreview }) => {
  const item = toLegacyRailItem(file);
  return (
    <BaseFileCard
      name={item.name}
      mediaType={item.mediaType}
      tone='legacy'
      title={item.name}
      onClick={onPreview ? () => onPreview(file) : undefined}
      status={
        <>
          <CheckCircleFilled className='text-emerald-500' />
          <span className='truncate'>已就绪 · {formatBytes(item.size)}</span>
        </>
      }
    />
  );
});

LegacyRailItemCard.displayName = 'LegacyRailItemCard';

const RailItemCard: React.FC<{
  item: RailItem;
  onRemove?: (clientId: string) => void;
  onRetry?: (clientId: string) => void;
  onPreview?: (item: RailItem) => void;
}> = memo(({ item, onRemove, onRetry, onPreview }) => {
  const failed = isHardFailure(item);
  const previewable = !!onPreview && canPreviewItem(item);
  const percent = progressPercent(item.uploadProgress);
  const parsing = item.uploadStatus === 'done' && item.previewStatus === 'loading';
  const tone = failed
    ? 'error'
    : item.uploadStatus === 'uploading' || item.uploadStatus === 'queued'
      ? 'uploading'
      : parsing
        ? 'parsing'
        : 'ready';

  const status = failed ? (
    <span className='truncate text-red-600 dark:text-red-400'>{statusErrorText(item.error)}</span>
  ) : item.uploadStatus === 'queued' ? (
    <span className='truncate text-blue-600 dark:text-blue-400'>等待上传</span>
  ) : item.uploadStatus === 'uploading' ? (
    <span className='truncate text-blue-600 dark:text-blue-400'>上传中 {percent}%</span>
  ) : parsing ? (
    <span className='truncate text-amber-600 dark:text-amber-400'>正在解析...</span>
  ) : item.previewStatus === 'preview_failed' ? (
    <span className='truncate text-amber-600 dark:text-amber-400'>已就绪 · 预览不可用</span>
  ) : (
    <>
      <CheckCircleFilled className='text-emerald-500' />
      <span className='truncate'>已就绪 · {formatBytes(item.size)}</span>
    </>
  );

  return (
    <BaseFileCard
      name={item.name}
      mediaType={item.mediaType}
      tone={tone}
      title={item.error ?? item.name}
      onClick={previewable ? () => onPreview?.(item) : undefined}
      status={status}
    >
      {canRetry(item) && onRetry && (
        <Tooltip title='重试上传'>
          <button
            type='button'
            aria-label={retryAriaLabel(item.name)}
            onClick={event => {
              event.stopPropagation();
              onRetry(item.clientId);
            }}
            className='h-6 flex-shrink-0 rounded-md bg-red-100 px-1.5 text-[11px] leading-none text-red-600 transition hover:bg-red-200 dark:bg-red-900/40 dark:text-red-400'
          >
            <ReloadOutlined className='mr-1 text-[10px]' />
            重试
          </button>
        </Tooltip>
      )}
      {onRemove && (
        <Tooltip title='移除文件'>
          <button
            type='button'
            aria-label={removeAriaLabel(item.name)}
            onClick={event => {
              event.stopPropagation();
              onRemove(item.clientId);
            }}
            className={classNames(
              'flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-[11px] text-slate-500 transition hover:bg-red-500 hover:text-white dark:bg-slate-700',
              !failed && item.uploadStatus !== 'uploading' && 'opacity-0 group-hover:opacity-100',
            )}
          >
            <CloseOutlined className='text-[10px]' />
          </button>
        </Tooltip>
      )}
      {item.uploadStatus === 'uploading' && (
        <div
          className='absolute bottom-0 left-0 h-[2px] bg-blue-500 transition-[width] duration-200'
          style={{ width: `${percent}%` }}
        />
      )}
      {parsing && <div className='session-files-indeterminate absolute bottom-0 left-0 h-[2px] w-1/3 bg-amber-500' />}
    </BaseFileCard>
  );
});

RailItemCard.displayName = 'RailItemCard';

const AttachmentRail: React.FC<AttachmentRailProps> = ({
  drafts,
  legacyFiles,
  onRemove,
  onRetry,
  onPreview,
  onLegacyPreview,
  onClearAll,
  addControl,
  preview,
  onClosePreview,
  className,
}) => {
  const [expanded, setExpanded] = useState(false);
  const viewportWidth = useViewportWidth();
  const prefersReducedMotion = usePrefersReducedMotion();

  const items = useMemo(() => toRailItems(drafts), [drafts]);
  const uploading = items.some(item => item.uploadStatus === 'uploading' || item.uploadStatus === 'queued');
  const aggregatePercent = progressPercent(aggregateUploadProgress(items));
  const { visible, hiddenCount } = useMemo(
    () => (expanded ? { visible: items, hiddenCount: 0 } : collapseRail(items)),
    [items, expanded],
  );
  const overlay = resolvePreviewOverlay(viewportWidth);
  const legacyCount = legacyFiles?.length ?? 0;
  const totalCount = items.length + legacyCount;
  const totalBytes =
    items.reduce((sum, item) => sum + item.size, 0) + (legacyFiles ?? []).reduce((sum, file) => sum + file.size, 0);
  const canShowFoldControls = items.length > visible.length || expanded;

  if (totalCount === 0 && !preview) return null;

  return (
    <div
      aria-live='polite'
      data-component='attachment-rail'
      className={classNames('w-full', motionClassName(prefersReducedMotion), className)}
    >
      <style>{`
        @keyframes sessionFilesIndeterminate { 0% { transform: translateX(-110%); } 100% { transform: translateX(320%); } }
        .session-files-indeterminate { animation: sessionFilesIndeterminate 1.4s ease-in-out infinite; }
        .${REDUCED_MOTION_CLASS},.${REDUCED_MOTION_CLASS} *{animation:none!important;transition:none!important;}
      `}</style>

      {totalCount > 0 && (
        <div className='mb-2 flex items-center justify-between px-1 text-[11px] font-medium text-slate-400 dark:text-slate-500'>
          <span>
            已添加 {totalCount} 个文件 · 共 {formatBytes(totalBytes)}
          </span>
          <div className='flex items-center gap-3'>
            {uploading && (
              <span role='status' aria-live='polite' aria-label={`Overall upload progress ${aggregatePercent}%`}>
                上传中 {aggregatePercent}%
              </span>
            )}
            {onClearAll && (
              <button type='button' onClick={onClearAll} className='transition hover:text-red-500'>
                全部移除
              </button>
            )}
          </div>
        </div>
      )}

      <div className='flex max-h-[136px] flex-wrap gap-2 overflow-y-auto pr-1'>
        {legacyFiles?.map(file => (
          <LegacyRailItemCard key={`legacy:${file.file_path}`} file={file} onPreview={onLegacyPreview} />
        ))}
        {visible.map(item => (
          <RailItemCard key={item.clientId} item={item} onRemove={onRemove} onRetry={onRetry} onPreview={onPreview} />
        ))}
        {hiddenCount > 0 && (
          <button
            type='button'
            aria-label={`Show ${hiddenCount} more attachments`}
            onClick={() => setExpanded(true)}
            className={classNames(
              'flex min-h-[52px] items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-[13px] text-slate-600 transition hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800/50 dark:text-slate-300 dark:hover:bg-slate-800',
              FILE_CARD_WIDTH,
            )}
          >
            还有 {hiddenCount} 个文件 · 展开
          </button>
        )}
        {expanded && canShowFoldControls && (
          <button
            type='button'
            onClick={() => setExpanded(false)}
            className={classNames(
              'flex min-h-[52px] items-center justify-center rounded-xl border border-slate-200 px-3 py-2 text-[13px] text-slate-500 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800/60',
              FILE_CARD_WIDTH,
            )}
          >
            收起
          </button>
        )}
        {addControl && <div className={classNames('session-file-add-control', FILE_CARD_WIDTH)}>{addControl}</div>}
      </div>

      {preview && overlay.mode !== 'right-panel' && (
        <Drawer
          open
          placement='right'
          destroyOnClose
          width={overlay.mode === 'fullscreen' ? '100%' : overlay.width}
          title={preview.snapshot?.name ?? '附件预览'}
          onClose={onClosePreview}
          className={overlay.mode === 'fullscreen' ? 'attachment-preview-fullscreen' : undefined}
        >
          {preview.loading ? (
            <div className='flex h-40 items-center justify-center'>
              <Spin indicator={<LoadingOutlined spin />} />
            </div>
          ) : preview.error ? (
            <Alert type='error' showIcon message='Preview failed' description={preview.error} />
          ) : (
            <AttachmentPreview snapshot={preview.snapshot} size={preview.size} />
          )}
        </Drawer>
      )}
    </div>
  );
};

AttachmentRail.displayName = 'AttachmentRail';

export const AttachmentRailAddButton: React.FC<{ label?: string }> = ({ label = '添加文件' }) => (
  <button
    type='button'
    className='flex min-h-[52px] w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-slate-300 px-3 py-2 text-[13px] text-slate-400 transition hover:border-slate-400 hover:text-slate-500 dark:border-slate-600 dark:hover:border-slate-500'
  >
    <PlusOutlined className='text-[13px]' />
    {label}
  </button>
);

export default memo(AttachmentRail);
