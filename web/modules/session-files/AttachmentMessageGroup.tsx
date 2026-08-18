/**
 * Read-only attachment cards rendered inside a historical user message.
 *
 * Accepts immutable `SessionFileSnapshot[]` (server contract; legacy
 * attachments arrive via `snapshotFromLegacyFile`, which produces the same
 * display-only shape), renders them sorted by `ordinal`, and surfaces a soft
 * amber warning for `preview_failed` files (readable but not previewable)
 * plus a hard red flag for failed ones.
 * Cards never expose destructive actions — history is read-only.
 */

import { ExclamationCircleFilled } from '@ant-design/icons';
import classNames from 'classnames';
import React, { memo, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { FileKindIcon } from './AttachmentPreview';
import { canPreviewSnapshot, formatBytes } from './attachment-view-model';
import type { SessionFileSnapshot } from './types';

export interface AttachmentMessageGroupProps {
  /** Immutable display snapshots for the message. */
  files?: readonly SessionFileSnapshot[];
  /** Optional preview trigger wired by the hosting chat layout. */
  onPreview?: (snapshot: SessionFileSnapshot) => void;
  className?: string;
}

const AttachmentMessageGroup: React.FC<AttachmentMessageGroupProps> = ({ files, onPreview, className }) => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const ordered = useMemo(() => [...(files ?? [])].sort((a, b) => a.ordinal - b.ordinal), [files]);

  if (ordered.length === 0) return null;

  const visible = expanded ? ordered : ordered.slice(0, 2);
  const hiddenCount = Math.max(ordered.length - visible.length, 0);

  return (
    <div
      className={classNames('flex flex-wrap items-center gap-2', className)}
      data-component='attachment-message-group'
    >
      {visible.map(file => {
        const previewable = !!onPreview && canPreviewSnapshot(file.status);
        return (
          <button
            type='button'
            key={file.file_id}
            className={classNames(
              'inline-flex max-w-[190px] items-center gap-2 rounded-full border px-2.5 py-1.5 text-left text-[13px] transition-colors',
              'border-slate-200 bg-slate-50/80 text-slate-700 hover:border-slate-300 hover:bg-white dark:border-slate-700/70 dark:bg-[#212226] dark:text-slate-200 dark:hover:border-slate-600',
              previewable ? 'cursor-pointer' : 'cursor-default',
              file.status === 'failed' &&
                'border-red-200 bg-red-50 text-red-600 dark:border-red-800/70 dark:bg-red-900/15',
            )}
            onClick={previewable ? () => onPreview(file) : undefined}
            aria-disabled={!previewable}
            title={file.name}
          >
            <div
              className={classNames(
                'flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full',
                file.status === 'failed'
                  ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
                  : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400',
              )}
            >
              <FileKindIcon name={file.name} mediaType={file.media_type} kind={file.kind} className='text-[12px]' />
            </div>
            <span className='min-w-0 truncate font-medium'>{file.name}</span>
            {file.status === 'preview_failed' && (
              <span
                className='flex flex-shrink-0 items-center gap-1 text-[11px] text-amber-500 dark:text-amber-400'
                title={t('session_files_preview_unavailable_hint')}
              >
                <ExclamationCircleFilled />
              </span>
            )}
            {file.status === 'failed' && (
              <span className='flex flex-shrink-0 items-center gap-1 text-[11px] text-red-500 dark:text-red-400'>
                <ExclamationCircleFilled />
              </span>
            )}
            <span className='sr-only'>{formatBytes(file.size)}</span>
          </button>
        );
      })}
      {hiddenCount > 0 && (
        <button
          type='button'
          onClick={() => setExpanded(true)}
          className='inline-flex h-8 items-center rounded-full border border-dashed border-slate-300 bg-white/70 px-3 text-[12px] font-medium text-slate-500 transition hover:border-slate-400 hover:bg-white dark:border-slate-700 dark:bg-[#212226] dark:text-slate-400'
        >
          +{hiddenCount}
        </button>
      )}
      {expanded && ordered.length > 2 && (
        <button
          type='button'
          onClick={() => setExpanded(false)}
          className='inline-flex h-8 items-center rounded-full border border-slate-200 bg-white/70 px-3 text-[12px] text-slate-400 transition hover:text-slate-600 dark:border-slate-700 dark:bg-[#212226] dark:hover:text-slate-200'
        >
          {t('session_files_collapse')}
        </button>
      )}
    </div>
  );
};

AttachmentMessageGroup.displayName = 'AttachmentMessageGroup';

export default memo(AttachmentMessageGroup);
