/**
 * Composer attachment strip.
 *
 * This is the draft-only surface that lives inside the home composer, above
 * the textarea. It follows the multi-file mockup: fixed-width file cards,
 * two-row wrapping, clear upload/parsing/error states, inline progress, a
 * folded "+N" remainder, and an optional add-file card owned by the caller.
 */

import {
  CheckCircleFilled,
  CloseOutlined,
  DeleteOutlined,
  ExclamationCircleFilled,
  LoadingOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Alert, Drawer, Popconfirm, Popover, Spin, Tooltip } from 'antd';
import classNames from 'classnames';
import React, { ReactNode, memo, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import AttachmentPreview, {
  ATTACHMENT_PREVIEW_DRAWER_STYLES,
  AttachmentPreviewCloseButton,
  AttachmentPreviewPanelTitle,
  FileKindIcon,
} from './AttachmentPreview';
import type { RailItem } from './attachment-view-model';
import {
  PREVIEW_DESKTOP_MIN_WIDTH,
  REDUCED_MOTION_CLASS,
  aggregateUploadProgress,
  canPreviewItem,
  canRetry,
  collapseCompactRail,
  collapseRail,
  formatBytes,
  isHardFailure,
  motionClassName,
  progressPercent,
  removeAriaLabel,
  resolvePreviewOverlay,
  retryAriaLabel,
  shouldShowComfortableSummary,
  summarizeCompactRailStatus,
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
  /**
   * Layout density. 'comfortable' (default) renders the mockup's 228px file
   * cards for the wide home composer; 'compact' renders single-line chips for
   * the narrow chat composer, where the full card row would dominate the box.
   */
  density?: 'comfortable' | 'compact';
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

/** Error code → i18n key; callers render through `t()`. Unknown codes pass through raw. */
const statusErrorKey = (
  error: string | null,
):
  | 'session_files_error_duplicate'
  | 'session_files_error_too_large'
  | 'session_files_error_too_many'
  | 'session_files_error_request_too_large'
  | 'session_files_error_upload_failed'
  | null => {
  if (!error) return 'session_files_error_upload_failed';
  switch (error) {
    case 'DUPLICATE_FILE':
      return 'session_files_error_duplicate';
    case 'FILE_TOO_LARGE':
      return 'session_files_error_too_large';
    case 'TOO_MANY_FILES':
      return 'session_files_error_too_many';
    case 'REQUEST_TOO_LARGE':
      return 'session_files_error_request_too_large';
    default:
      return null;
  }
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
      'group relative flex h-11 items-center gap-2 rounded-lg border px-2.5 py-1.5 outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-blue-500/30',
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
        'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-[14px]',
        tone === 'error'
          ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
          : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
      )}
    >
      <FileKindIcon name={name} mediaType={mediaType} kind={kind} className='text-[14px]' />
    </div>
    <div className='min-w-0 flex-1'>
      <div className='truncate text-[13px] font-medium text-slate-800 dark:text-slate-100' title={name}>
        {name}
      </div>
      <div className='mt-0.5 flex min-w-0 items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400'>
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
  const { t } = useTranslation();
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
          <span className='truncate'>{t('session_files_ready', { size: formatBytes(item.size) })}</span>
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
  const { t } = useTranslation();
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

  const errorKey = statusErrorKey(item.error);
  const status = failed ? (
    <span className='truncate text-red-600 dark:text-red-400'>{errorKey ? t(errorKey) : item.error}</span>
  ) : item.uploadStatus === 'queued' ? (
    <span className='truncate text-blue-600 dark:text-blue-400'>{t('session_files_waiting_upload')}</span>
  ) : item.uploadStatus === 'uploading' ? (
    <span className='truncate text-blue-600 dark:text-blue-400'>
      {t('session_files_uploading_progress', { percent })}
    </span>
  ) : parsing ? (
    <span className='truncate text-amber-600 dark:text-amber-400'>{t('session_files_parsing')}</span>
  ) : item.previewStatus === 'preview_failed' ? (
    <span className='truncate text-amber-600 dark:text-amber-400'>{t('session_files_ready_preview_unavailable')}</span>
  ) : (
    <>
      <CheckCircleFilled className='text-emerald-500' />
      <span className='truncate'>{t('session_files_ready', { size: formatBytes(item.size) })}</span>
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
        <Tooltip title={t('session_files_retry_upload')}>
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
            {t('session_files_retry')}
          </button>
        </Tooltip>
      )}
      {onRemove && (
        <Tooltip title={t('session_files_remove_file')}>
          <button
            type='button'
            aria-label={removeAriaLabel(item.name)}
            onClick={event => {
              event.stopPropagation();
              onRemove(item.clientId);
            }}
            className={classNames(
              'flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-[11px] text-slate-500 outline-none transition hover:bg-red-500 hover:text-white focus-visible:ring-2 focus-visible:ring-red-500/30 dark:bg-slate-700',
              !failed &&
                item.uploadStatus !== 'uploading' &&
                'opacity-60 group-hover:opacity-100 focus-visible:opacity-100',
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

/** Compact composer item: one quiet, container-aware file token. */
const CompactFileChip: React.FC<{
  item: RailItem;
  onRemove?: (clientId: string) => void;
  onRetry?: (clientId: string) => void;
  onPreview?: (item: RailItem) => void;
}> = memo(({ item, onRemove, onRetry, onPreview }) => {
  const { t } = useTranslation();
  const failed = isHardFailure(item);
  const previewable = !!onPreview && canPreviewItem(item);
  const percent = progressPercent(item.uploadProgress);
  const uploading = item.uploadStatus === 'uploading' || item.uploadStatus === 'queued';
  const parsing = item.uploadStatus === 'done' && item.previewStatus === 'loading';
  const processing = uploading || parsing;
  const errorKey = statusErrorKey(item.error);
  const errorText = errorKey ? t(errorKey) : item.error;

  return (
    <div
      role='group'
      aria-label={item.name}
      aria-busy={processing}
      data-state={failed ? 'error' : uploading ? 'uploading' : parsing ? 'parsing' : 'ready'}
      className={classNames(
        'session-file-compact-item group relative flex h-8 min-w-[88px] max-w-[156px] shrink items-center overflow-hidden rounded-full border pr-1 text-[12px] transition-[background-color,border-color,color] duration-150',
        failed
          ? 'border-red-200 bg-red-50/75 text-red-700 hover:border-red-300 dark:border-red-900/60 dark:bg-red-950/25 dark:text-red-300'
          : processing
            ? 'border-blue-200 bg-blue-50/55 text-slate-700 hover:border-blue-300 dark:border-blue-900/60 dark:bg-blue-950/25 dark:text-slate-200'
            : 'border-emerald-200/90 bg-emerald-50/80 text-emerald-800 hover:border-emerald-300 hover:bg-emerald-50 dark:border-emerald-800/60 dark:bg-emerald-950/30 dark:text-emerald-200 dark:hover:border-emerald-700/70 dark:hover:bg-emerald-950/40',
      )}
      title={`${item.name} · ${formatBytes(item.size)}${errorText ? ` · ${errorText}` : ''}`}
    >
      <button
        type='button'
        disabled={!previewable}
        aria-label={previewable ? t('session_files_preview_name', { name: item.name }) : undefined}
        onClick={() => onPreview?.(item)}
        className={classNames(
          'flex h-full min-w-0 items-center gap-1.5 rounded-l-full pl-1.5 pr-1 outline-none focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:ring-offset-1 active:scale-[0.985]',
          previewable ? 'cursor-pointer' : 'cursor-default',
        )}
      >
        <span
          className={classNames(
            'flex h-5 w-5 flex-none items-center justify-center rounded-md bg-white/90 text-[12px] shadow-[0_1px_1px_rgba(15,23,42,0.06)] dark:bg-white/[0.08] dark:shadow-none',
            failed && '!bg-red-100 dark:!bg-red-900/35',
          )}
        >
          <FileKindIcon name={item.name} mediaType={item.mediaType} className='text-[12px]' />
        </span>
        <span className='max-w-[96px] truncate font-medium tracking-[-0.005em]'>{item.name}</span>
      </button>
      {uploading && (
        <span className='flex flex-none items-center gap-1 px-0.5 text-[10px] font-medium tabular-nums text-blue-600 dark:text-blue-300'>
          <LoadingOutlined className='text-[9px]' />
          {percent}%
        </span>
      )}
      {parsing && (
        <span className='flex flex-none items-center gap-1 px-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-300'>
          <LoadingOutlined className='text-[9px]' />
          {t('session_files_parsing_short')}
        </span>
      )}
      {item.previewStatus === 'preview_failed' && !failed && (
        <span
          className='flex flex-none items-center px-0.5 text-[10px] text-amber-500 dark:text-amber-400'
          title={t('session_files_preview_unavailable_hint')}
        >
          <ExclamationCircleFilled />
        </span>
      )}
      {failed && canRetry(item) && onRetry && (
        <button
          type='button'
          aria-label={retryAriaLabel(item.name)}
          onClick={event => {
            event.stopPropagation();
            onRetry(item.clientId);
          }}
          className='flex h-6 w-6 flex-none items-center justify-center rounded-full text-[10px] text-red-500 outline-none transition-colors hover:bg-red-100 hover:text-red-700 focus-visible:ring-2 focus-visible:ring-red-500/30 active:scale-95 dark:hover:bg-red-900/35'
        >
          <ReloadOutlined />
        </button>
      )}
      {onRemove && (
        <button
          type='button'
          aria-label={removeAriaLabel(item.name)}
          onClick={event => {
            event.stopPropagation();
            onRemove(item.clientId);
          }}
          className='flex h-6 w-6 flex-none items-center justify-center rounded-full text-[10px] text-emerald-600/55 outline-none transition-[background-color,color,opacity,transform] hover:bg-red-50 hover:text-red-500 focus-visible:ring-2 focus-visible:ring-blue-500/30 active:scale-90 dark:text-emerald-400/55 dark:hover:bg-red-950/35 dark:hover:text-red-300'
        >
          <CloseOutlined className='text-[10px]' />
        </button>
      )}
      {item.uploadStatus === 'uploading' && (
        <div
          role='progressbar'
          aria-label={t('session_files_upload_progress_aria', { name: item.name })}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className='absolute inset-x-0 bottom-0 h-[2px] origin-left bg-blue-500/85 transition-transform duration-200 ease-out'
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      )}
      {parsing && <div className='session-files-indeterminate absolute bottom-0 left-0 h-[2px] w-1/3 bg-blue-500/80' />}
    </div>
  );
});

CompactFileChip.displayName = 'CompactFileChip';

/** Legacy example file as a compact read-only chip (no remove, no upload state). */
const CompactLegacyChip: React.FC<{
  file: LegacyServerFile;
  onPreview?: (file: LegacyServerFile) => void;
}> = memo(({ file, onPreview }) => {
  const item = toLegacyRailItem(file);
  return (
    <div
      role={onPreview ? 'button' : undefined}
      tabIndex={onPreview ? 0 : undefined}
      onClick={onPreview ? () => onPreview(file) : undefined}
      onKeyDown={event => {
        if (!onPreview) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onPreview(file);
        }
      }}
      title={item.name}
      className={classNames(
        'session-file-compact-item inline-flex h-8 min-w-[88px] max-w-[156px] shrink items-center gap-1.5 rounded-full border border-emerald-200/90 bg-emerald-50/80 pl-1.5 pr-2.5 text-[12px] text-emerald-800 outline-none transition-[background-color,border-color] duration-150 hover:border-emerald-300 hover:bg-emerald-50 focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:ring-offset-1 active:scale-[0.985]',
        onPreview && 'cursor-pointer',
        'dark:border-emerald-800/60 dark:bg-emerald-950/30 dark:text-emerald-200 dark:hover:border-emerald-700/70 dark:hover:bg-emerald-950/40',
      )}
    >
      <span className='flex h-5 w-5 flex-none items-center justify-center rounded-md bg-white/90 shadow-[0_1px_1px_rgba(15,23,42,0.06)] dark:bg-white/[0.08] dark:shadow-none'>
        <FileKindIcon name={item.name} mediaType={item.mediaType} className='text-[12px]' />
      </span>
      <span className='max-w-[116px] truncate font-medium tracking-[-0.005em]'>{item.name}</span>
    </div>
  );
});

CompactLegacyChip.displayName = 'CompactLegacyChip';

type CompactRailEntry =
  | { type: 'legacy'; key: string; file: LegacyServerFile }
  | { type: 'draft'; key: string; item: RailItem };

const CompactOverflowDraftRow: React.FC<{
  item: RailItem;
  onRemove?: (clientId: string) => void;
  onRetry?: (clientId: string) => void;
  onPreview?: (item: RailItem) => void;
}> = memo(({ item, onRemove, onRetry, onPreview }) => {
  const { t } = useTranslation();
  const failed = isHardFailure(item);
  const previewable = !!onPreview && canPreviewItem(item);
  const percent = progressPercent(item.uploadProgress);
  const uploading = item.uploadStatus === 'uploading' || item.uploadStatus === 'queued';
  const parsing = item.uploadStatus === 'done' && item.previewStatus === 'loading';

  const errorKey = statusErrorKey(item.error);
  const status = failed
    ? errorKey
      ? t(errorKey)
      : item.error
    : item.uploadStatus === 'queued'
      ? t('session_files_waiting_upload')
      : item.uploadStatus === 'uploading'
        ? t('session_files_uploading_progress', { percent })
        : parsing
          ? t('session_files_parsing_short')
          : item.previewStatus === 'preview_failed'
            ? t('session_files_ready_preview_unavailable')
            : t('session_files_ready', { size: formatBytes(item.size) });

  return (
    <div
      className={classNames(
        'group flex min-h-11 items-center gap-2 rounded-xl border border-transparent px-2 py-1.5 transition-colors',
        failed
          ? 'bg-red-50/70 hover:border-red-100 dark:bg-red-950/20 dark:hover:border-red-900/50'
          : 'hover:border-slate-100 hover:bg-slate-50/90 dark:hover:border-white/[0.06] dark:hover:bg-white/[0.035]',
      )}
    >
      <button
        type='button'
        disabled={!previewable}
        aria-label={previewable ? t('session_files_preview_name', { name: item.name }) : undefined}
        onClick={() => onPreview?.(item)}
        className={classNames(
          'flex min-w-0 flex-1 items-center gap-2 text-left outline-none focus-visible:rounded-lg focus-visible:ring-2 focus-visible:ring-blue-500/30',
          previewable ? 'cursor-pointer' : 'cursor-default',
        )}
      >
        <span
          className={classNames(
            'flex h-8 w-8 flex-none items-center justify-center rounded-lg border bg-white text-sm shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:bg-white/[0.05] dark:shadow-none',
            failed
              ? 'border-red-100 text-red-500 dark:border-red-900/50 dark:text-red-400'
              : uploading || parsing
                ? 'border-blue-100 text-blue-500 dark:border-blue-900/50 dark:text-blue-300'
                : 'border-emerald-100 text-emerald-600 dark:border-emerald-900/50 dark:text-emerald-300',
          )}
        >
          <FileKindIcon name={item.name} mediaType={item.mediaType} className='text-sm' />
        </span>
        <span className='min-w-0 flex-1'>
          <span className='block truncate text-[13px] font-medium text-slate-800 dark:text-slate-100' title={item.name}>
            {item.name}
          </span>
          <span
            className={classNames(
              'mt-0.5 block truncate text-[11px]',
              failed
                ? 'text-red-500 dark:text-red-400'
                : uploading || parsing
                  ? 'text-blue-500 dark:text-blue-300'
                  : item.previewStatus === 'preview_failed'
                    ? 'text-amber-500 dark:text-amber-400'
                    : 'text-slate-400 dark:text-slate-500',
            )}
          >
            {status}
          </span>
        </span>
      </button>
      {failed && canRetry(item) && onRetry && (
        <Tooltip title={t('session_files_retry_upload')}>
          <button
            type='button'
            aria-label={retryAriaLabel(item.name)}
            onClick={() => onRetry(item.clientId)}
            className='flex h-7 w-7 flex-none items-center justify-center rounded-lg text-[12px] text-red-500 outline-none transition-colors hover:bg-red-100 focus-visible:ring-2 focus-visible:ring-red-500/30 dark:hover:bg-red-900/35'
          >
            <ReloadOutlined />
          </button>
        </Tooltip>
      )}
      {onRemove && (
        <Tooltip title={t('session_files_remove_file')}>
          <button
            type='button'
            aria-label={removeAriaLabel(item.name)}
            onClick={() => onRemove(item.clientId)}
            className='flex h-7 w-7 flex-none items-center justify-center rounded-lg text-[11px] text-slate-400 outline-none transition-[background-color,color,transform] hover:bg-red-50 hover:text-red-500 focus-visible:ring-2 focus-visible:ring-blue-500/30 active:scale-90 dark:text-slate-500 dark:hover:bg-red-950/35 dark:hover:text-red-300'
          >
            <CloseOutlined />
          </button>
        </Tooltip>
      )}
    </div>
  );
});

CompactOverflowDraftRow.displayName = 'CompactOverflowDraftRow';

const CompactOverflowLegacyRow: React.FC<{
  file: LegacyServerFile;
  onPreview?: (file: LegacyServerFile) => void;
}> = memo(({ file, onPreview }) => {
  const { t } = useTranslation();
  const item = toLegacyRailItem(file);
  return (
    <button
      type='button'
      disabled={!onPreview}
      aria-label={onPreview ? t('session_files_preview_name', { name: item.name }) : undefined}
      onClick={() => onPreview?.(file)}
      className={classNames(
        'flex min-h-11 w-full items-center gap-2 rounded-xl border border-transparent px-2 py-1.5 text-left outline-none transition-colors hover:border-slate-100 hover:bg-slate-50/90 focus-visible:ring-2 focus-visible:ring-blue-500/30 dark:hover:border-white/[0.06] dark:hover:bg-white/[0.035]',
        onPreview ? 'cursor-pointer' : 'cursor-default',
      )}
    >
      <span className='flex h-8 w-8 flex-none items-center justify-center rounded-lg border border-emerald-100 bg-white text-sm text-emerald-600 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-emerald-900/50 dark:bg-white/[0.05] dark:text-emerald-300 dark:shadow-none'>
        <FileKindIcon name={item.name} mediaType={item.mediaType} className='text-sm' />
      </span>
      <span className='min-w-0 flex-1'>
        <span className='block truncate text-[13px] font-medium text-slate-800 dark:text-slate-100' title={item.name}>
          {item.name}
        </span>
        <span className='mt-0.5 block truncate text-[11px] text-slate-400 dark:text-slate-500'>
          {t('session_files_ready', { size: formatBytes(item.size) })}
        </span>
      </span>
    </button>
  );
});

CompactOverflowLegacyRow.displayName = 'CompactOverflowLegacyRow';

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
  density = 'comfortable',
}) => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [compactOverflowOpen, setCompactOverflowOpen] = useState(false);
  const [compactRailWidth, setCompactRailWidth] = useState(0);
  const compactRailRef = useRef<HTMLDivElement>(null);
  const compactOverflowButtonRef = useRef<HTMLButtonElement>(null);
  const compactPanelId = useId();
  const viewportWidth = useViewportWidth();
  const prefersReducedMotion = usePrefersReducedMotion();
  const compact = density === 'compact';

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
  const compactEntries = useMemo<CompactRailEntry[]>(
    () => [
      ...(legacyFiles ?? []).map(file => ({
        type: 'legacy' as const,
        key: `legacy:${file.file_path}`,
        file,
      })),
      ...items.map(item => ({ type: 'draft' as const, key: item.clientId, item })),
    ],
    [items, legacyFiles],
  );
  const compactLayout = useMemo(
    () => collapseCompactRail(compactEntries, compactRailWidth),
    [compactEntries, compactRailWidth],
  );
  const compactHiddenState = useMemo(
    () =>
      summarizeCompactRailStatus(
        compactLayout.hidden
          .filter((entry): entry is Extract<CompactRailEntry, { type: 'draft' }> => entry.type === 'draft')
          .map(entry => entry.item),
      ),
    [compactLayout.hidden],
  );
  const showCompactManager = compactLayout.hiddenCount > 0;
  // Compact mode keeps a fixed one-line footprint; each token carries its own
  // state and the count is available to assistive technology below.
  // One removable draft already exposes name, status, size and its remove
  // action in the card. Keep the summary for multi-file sets and legacy files,
  // whose read-only card relies on “全部移除” as its clear affordance.
  const showSummaryRow =
    !compact &&
    shouldShowComfortableSummary({
      totalCount,
      legacyCount,
      hasPerItemRemove: !!onRemove,
    });

  useEffect(() => {
    if (!compact) return;
    const node = compactRailRef.current;
    if (!node) return;

    const updateWidth = () => {
      const nextWidth = Math.floor(node.getBoundingClientRect().width);
      setCompactRailWidth(current => (current === nextWidth ? current : nextWidth));
    };

    updateWidth();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(updateWidth);
      observer.observe(node);
      return () => observer.disconnect();
    }

    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, [compact]);

  useEffect(() => {
    if (totalCount <= 1) setCompactOverflowOpen(false);
  }, [totalCount]);

  useEffect(() => {
    if (!compactOverflowOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setCompactOverflowOpen(false);
      compactOverflowButtonRef.current?.focus();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [compactOverflowOpen]);

  if (totalCount === 0 && !preview) return null;

  const handleCompactDraftPreview = (item: RailItem) => {
    setCompactOverflowOpen(false);
    onPreview?.(item);
  };

  const handleCompactLegacyPreview = (file: LegacyServerFile) => {
    setCompactOverflowOpen(false);
    onLegacyPreview?.(file);
  };

  const compactPanelWidth = Math.min(compactRailWidth || 360, compactRailWidth >= 640 ? 520 : 360);
  const compactManagerContent = (
    <section
      id={compactPanelId}
      role='region'
      aria-label={t('session_files_round_attachments_aria', { count: totalCount })}
      style={{ width: compactPanelWidth }}
      className='overflow-hidden rounded-[14px] bg-white dark:bg-[#202126]'
    >
      <div className='flex h-12 items-center justify-between border-b border-slate-100 px-3 dark:border-white/[0.07]'>
        <div className='flex items-center gap-2'>
          <span className='text-[13px] font-semibold text-slate-800 dark:text-slate-100'>
            {t('session_files_round_attachments')}
          </span>
          <span className='rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-slate-500 dark:bg-white/[0.07] dark:text-slate-400'>
            {totalCount}
          </span>
        </div>
        {onClearAll && totalCount > 1 && (
          <Popconfirm
            title={t('session_files_remove_all_confirm_title')}
            description={t('session_files_remove_all_confirm_desc')}
            okText={t('session_files_remove_all')}
            cancelText={t('session_files_cancel')}
            okButtonProps={{ danger: true }}
            placement='topRight'
            onConfirm={() => {
              setCompactOverflowOpen(false);
              onClearAll();
            }}
          >
            <button
              type='button'
              className='flex h-7 items-center gap-1 rounded-lg px-2 text-[11px] font-medium text-slate-400 outline-none transition-colors hover:bg-red-50 hover:text-red-500 focus-visible:ring-2 focus-visible:ring-red-500/25 dark:text-slate-500 dark:hover:bg-red-950/30 dark:hover:text-red-300'
            >
              <DeleteOutlined className='text-[11px]' />
              {t('session_files_remove_all')}
            </button>
          </Popconfirm>
        )}
      </div>
      <div
        className={classNames(
          'grid max-h-[236px] gap-0.5 overflow-y-auto p-1.5',
          compactRailWidth >= 640 ? 'grid-cols-2' : 'grid-cols-1',
        )}
      >
        {compactEntries.map(entry =>
          entry.type === 'legacy' ? (
            <CompactOverflowLegacyRow
              key={entry.key}
              file={entry.file}
              onPreview={onLegacyPreview ? handleCompactLegacyPreview : undefined}
            />
          ) : (
            <CompactOverflowDraftRow
              key={entry.key}
              item={entry.item}
              onRemove={onRemove}
              onRetry={onRetry}
              onPreview={onPreview ? handleCompactDraftPreview : undefined}
            />
          ),
        )}
      </div>
      <div className='border-t border-slate-100 px-3 py-2 text-[10px] text-slate-400 dark:border-white/[0.07] dark:text-slate-500'>
        {t('session_files_total_size_hint', { size: formatBytes(totalBytes) })}
      </div>
    </section>
  );

  const compactManager = showCompactManager ? (
    <Popover
      trigger='click'
      placement='topLeft'
      arrow={false}
      open={compactOverflowOpen}
      onOpenChange={setCompactOverflowOpen}
      content={compactManagerContent}
      overlayInnerStyle={{ padding: 0, borderRadius: 14, overflow: 'hidden' }}
      overlayClassName='session-files-compact-popover'
    >
      <button
        ref={compactOverflowButtonRef}
        type='button'
        aria-expanded={compactOverflowOpen}
        aria-controls={compactPanelId}
        aria-label={t('session_files_more_attachments_aria', { hidden: compactLayout.hiddenCount, total: totalCount })}
        title={t('session_files_more_files_title', { count: compactLayout.hiddenCount })}
        className={classNames(
          'session-file-compact-item relative flex h-8 min-w-8 flex-none items-center justify-center rounded-full border px-2 text-[11px] font-semibold tabular-nums outline-none transition-[background-color,border-color,color,transform] focus-visible:ring-2 focus-visible:ring-blue-500/30 active:scale-95',
          compactHiddenState.errorCount > 0
            ? 'border-red-200 bg-red-50 text-red-600 hover:border-red-300 hover:bg-red-100/70 dark:border-red-900/60 dark:bg-red-950/25 dark:text-red-300'
            : compactHiddenState.processingCount > 0
              ? 'border-blue-200 bg-blue-50/70 text-blue-600 hover:border-blue-300 hover:bg-blue-50 dark:border-blue-900/60 dark:bg-blue-950/25 dark:text-blue-300'
              : compactHiddenState.warningCount > 0
                ? 'border-amber-200 bg-amber-50/70 text-amber-600 hover:border-amber-300 hover:bg-amber-50 dark:border-amber-900/60 dark:bg-amber-950/25 dark:text-amber-300'
                : 'border-slate-200 bg-slate-50/90 text-slate-600 hover:border-slate-300 hover:bg-white dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:bg-white/[0.07]',
        )}
      >
        +{compactLayout.hiddenCount}
        {(compactHiddenState.errorCount > 0 ||
          compactHiddenState.processingCount > 0 ||
          compactHiddenState.warningCount > 0) && (
          <span
            aria-hidden='true'
            className={classNames(
              'absolute right-0 top-0 h-2 w-2 rounded-full border-2 border-white dark:border-[#1e1f24]',
              compactHiddenState.errorCount > 0
                ? 'bg-red-500'
                : compactHiddenState.processingCount > 0
                  ? 'bg-blue-500'
                  : 'bg-amber-500',
            )}
          />
        )}
      </button>
    </Popover>
  ) : null;

  return (
    <div
      aria-live={compact ? undefined : 'polite'}
      data-component='attachment-rail'
      data-density={density}
      className={classNames('w-full', motionClassName(prefersReducedMotion), className)}
    >
      <style>{`
        @keyframes sessionFilesIndeterminate { 0% { transform: translateX(-110%); } 100% { transform: translateX(320%); } }
        @keyframes sessionFileCompactEnter { from { opacity: 0; transform: translateY(-2px) scale(.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
        .session-files-indeterminate { animation: sessionFilesIndeterminate 1.4s ease-in-out infinite; }
        .session-file-compact-item { animation: sessionFileCompactEnter 160ms cubic-bezier(.22,1,.36,1) both; }
        .session-file-add-control,.session-file-add-control .ant-upload-wrapper,.session-file-add-control .ant-upload,.session-file-add-control .ant-upload-select { flex: none !important; white-space: nowrap !important; }
        .session-file-add-control .ant-upload,.session-file-add-control .ant-upload-select { display: flex !important; }
        .session-file-add-control-comfortable,.session-file-add-control-comfortable .ant-upload-wrapper,.session-file-add-control-comfortable .ant-upload,.session-file-add-control-comfortable .ant-upload-select { height: 44px !important; }
        .session-file-add-control-comfortable .ant-upload-wrapper,.session-file-add-control-comfortable .ant-upload,.session-file-add-control-comfortable .ant-upload-select { align-items: stretch !important; display: flex !important; }
        .session-files-compact-popover .ant-popover-inner { border: 1px solid rgba(226,232,240,.92); box-shadow: 0 18px 44px rgba(15,23,42,.14),0 4px 12px rgba(15,23,42,.06); }
        .dark .session-files-compact-popover .ant-popover-inner { border-color: rgba(255,255,255,.08); box-shadow: 0 20px 48px rgba(0,0,0,.42); }
        .session-files-visually-hidden { position: absolute !important; width: 1px !important; height: 1px !important; padding: 0 !important; margin: -1px !important; overflow: hidden !important; clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important; }
        @media (prefers-reduced-motion: reduce) { .session-files-compact-popover,.session-files-compact-popover * { animation: none !important; transition: none !important; } }
        .${REDUCED_MOTION_CLASS},.${REDUCED_MOTION_CLASS} *{animation:none!important;transition:none!important;}
      `}</style>

      {compact && (
        <span className='session-files-visually-hidden' role='status' aria-live='polite' aria-atomic='true'>
          {uploading
            ? t('session_files_uploading_aria', { count: totalCount, percent: aggregatePercent })
            : t('session_files_added_aria', { count: totalCount })}
        </span>
      )}

      {showSummaryRow && (
        <div className='mb-1.5 flex items-center justify-between px-0.5 text-[11px] font-medium text-slate-500/80 dark:text-slate-400'>
          <span>{t('session_files_added_summary', { count: totalCount, size: formatBytes(totalBytes) })}</span>
          <div className='flex items-center gap-3'>
            {uploading && (
              <span role='status' aria-live='polite' aria-label={`Overall upload progress ${aggregatePercent}%`}>
                {t('session_files_uploading_progress', { percent: aggregatePercent })}
              </span>
            )}
            {onClearAll && (
              <button type='button' onClick={onClearAll} className='transition hover:text-red-500'>
                {t('session_files_remove_all')}
              </button>
            )}
          </div>
        </div>
      )}

      {compact ? (
        <div
          ref={compactRailRef}
          className='flex min-h-9 w-full min-w-0 items-center gap-1.5 py-0.5'
          role='group'
          aria-label={t('session_files_round_attachments')}
        >
          <div className='flex min-w-0 shrink items-center gap-1.5 overflow-hidden'>
            {compactManager}
            {compactLayout.visible.map(entry =>
              entry.type === 'legacy' ? (
                <CompactLegacyChip key={entry.key} file={entry.file} onPreview={onLegacyPreview} />
              ) : (
                <CompactFileChip
                  key={entry.key}
                  item={entry.item}
                  onRemove={onRemove}
                  onRetry={onRetry}
                  onPreview={onPreview}
                />
              ),
            )}
          </div>
          {addControl && <div className='session-file-add-control flex flex-none whitespace-nowrap'>{addControl}</div>}
        </div>
      ) : (
        <div className='flex max-h-[108px] flex-wrap items-start gap-1.5 overflow-y-auto pr-1'>
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
                'flex h-11 items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1.5 text-[12px] text-slate-600 transition hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800/50 dark:text-slate-300 dark:hover:bg-slate-800',
                FILE_CARD_WIDTH,
              )}
            >
              {t('session_files_expand_more', { count: hiddenCount })}
            </button>
          )}
          {expanded && canShowFoldControls && (
            <button
              type='button'
              onClick={() => setExpanded(false)}
              className={classNames(
                'flex h-11 items-center justify-center rounded-lg border border-slate-200 px-2.5 py-1.5 text-[12px] text-slate-500 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800/60',
                FILE_CARD_WIDTH,
              )}
            >
              {t('session_files_collapse')}
            </button>
          )}
          {addControl && (
            <div className='session-file-add-control session-file-add-control-comfortable flex h-11 w-auto max-w-full items-stretch'>
              {addControl}
            </div>
          )}
        </div>
      )}

      {preview && overlay.mode !== 'right-panel' && (
        <Drawer
          open
          placement='right'
          destroyOnClose
          closable={false}
          width={overlay.mode === 'fullscreen' ? '100%' : overlay.width}
          title={<AttachmentPreviewPanelTitle />}
          extra={onClosePreview ? <AttachmentPreviewCloseButton onClose={onClosePreview} /> : null}
          styles={ATTACHMENT_PREVIEW_DRAWER_STYLES}
          onClose={onClosePreview}
          className={overlay.mode === 'fullscreen' ? 'attachment-preview-fullscreen' : undefined}
        >
          {preview.loading ? (
            <div className='flex h-40 items-center justify-center'>
              <Spin indicator={<LoadingOutlined spin />} />
            </div>
          ) : preview.error ? (
            <Alert type='error' showIcon message={t('session_files_preview_failed')} description={preview.error} />
          ) : (
            <AttachmentPreview snapshot={preview.snapshot} size={preview.size} />
          )}
        </Drawer>
      )}
    </div>
  );
};

AttachmentRail.displayName = 'AttachmentRail';

/** Compact-density upload entry placed directly after the final file token. */
export const AttachmentRailCompactAddButton: React.FC<{ label?: string }> = ({ label }) => {
  const { t } = useTranslation();
  return (
    <Tooltip title={t('session_files_add_more')}>
      <button
        type='button'
        aria-label={t('session_files_add_more')}
        className='flex h-8 flex-none items-center justify-center gap-1 whitespace-nowrap rounded-full border border-dashed border-slate-300/90 bg-white/45 px-2.5 text-[12px] font-medium text-slate-500 outline-none transition-[background-color,border-color,color,transform] hover:border-blue-300 hover:bg-blue-50/60 hover:text-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500/30 active:scale-[0.97] dark:border-white/15 dark:bg-white/[0.025] dark:text-slate-400 dark:hover:border-blue-700/70 dark:hover:bg-blue-950/35 dark:hover:text-blue-300'
      >
        <PlusOutlined className='text-[11px]' />
        <span>{label ?? t('session_files_add')}</span>
      </button>
    </Tooltip>
  );
};

export const AttachmentRailAddButton: React.FC<{ label?: string }> = ({ label }) => {
  const { t } = useTranslation();
  return (
    <button
      type='button'
      className='flex h-11 min-w-[104px] items-center justify-center gap-1.5 rounded-lg border border-dashed border-slate-300 bg-slate-50/35 px-3 py-1.5 text-[12px] text-slate-400 outline-none transition-[background-color,border-color,color,transform] hover:border-blue-300 hover:bg-blue-50/50 hover:text-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500/30 active:scale-[0.98] dark:border-slate-600 dark:bg-white/[0.02] dark:hover:border-blue-700 dark:hover:bg-blue-950/30 dark:hover:text-blue-300'
    >
      <PlusOutlined className='text-[12px]' />
      {label ?? t('session_files_add_files')}
    </button>
  );
};

export default memo(AttachmentRail);
