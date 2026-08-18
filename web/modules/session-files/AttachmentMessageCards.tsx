/**
 * Read-only attachment cards for a historical user message — card variant.
 *
 * Same visual language as the knowledge/skill/database attachment cards next
 * to it (icon tile + file name + "type · size" sub-line), which was the
 * pre-multi-file message layout. `AttachmentMessageGroup` (pill chips) stays
 * for compact metadata surfaces like the scheduled-task detail page.
 *
 * Cards are read-only: no remove/retry, an optional preview click.
 */

import { ExclamationCircleFilled } from '@ant-design/icons';
import classNames from 'classnames';
import React, { memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { FileKindIcon } from './AttachmentPreview';
import { canPreviewSnapshot, formatBytes } from './attachment-view-model';
import type { SessionFileSnapshot } from './types';

export interface AttachmentMessageCardsProps {
  /** Immutable display snapshots for the message. */
  files?: readonly SessionFileSnapshot[];
  /** Optional preview trigger wired by the hosting chat layout. */
  onPreview?: (snapshot: SessionFileSnapshot) => void;
  className?: string;
}

/** Extension/MIME → i18n label key, mirroring the legacy single-file card. */
const typeLabelKey = (
  name: string,
  mediaType?: string,
):
  | 'file_type_spreadsheet'
  | 'file_type_pdf'
  | 'file_type_image'
  | 'file_type_word'
  | 'file_type_text'
  | 'file_type_generic' => {
  const ext = name.toLowerCase().split('.').pop() || '';
  if (['xlsx', 'xls'].includes(ext) || mediaType?.includes('spreadsheet') || mediaType?.includes('excel'))
    return 'file_type_spreadsheet';
  if (ext === 'csv' || mediaType?.includes('csv')) return 'file_type_spreadsheet';
  if (ext === 'pdf' || mediaType?.includes('pdf')) return 'file_type_pdf';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mediaType?.includes('image'))
    return 'file_type_image';
  if (['doc', 'docx'].includes(ext) || mediaType?.includes('word')) return 'file_type_word';
  if (['txt', 'md'].includes(ext) || mediaType?.includes('text')) return 'file_type_text';
  return 'file_type_generic';
};

const AttachmentMessageCards: React.FC<AttachmentMessageCardsProps> = ({ files, onPreview, className }) => {
  const { t } = useTranslation();
  const ordered = useMemo(() => [...(files ?? [])].sort((a, b) => a.ordinal - b.ordinal), [files]);

  if (ordered.length === 0) return null;

  return (
    <div className={classNames('flex flex-col gap-2', className)} data-component='attachment-message-cards'>
      {ordered.map(file => {
        const previewable = !!onPreview && canPreviewSnapshot(file.status);
        const failed = file.status === 'failed';
        return (
          <div
            key={file.file_id}
            role={previewable ? 'button' : undefined}
            tabIndex={previewable ? 0 : undefined}
            onClick={previewable ? () => onPreview(file) : undefined}
            onKeyDown={event => {
              if (!previewable) return;
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onPreview?.(file);
              }
            }}
            className={classNames(
              'flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border shadow-sm',
              failed
                ? 'border-red-200 bg-red-50/60 dark:border-red-800/70 dark:bg-red-900/15'
                : 'border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e]',
              previewable && 'cursor-pointer transition-colors hover:border-gray-300 dark:hover:border-gray-600',
            )}
            title={file.name}
          >
            <div
              className={classNames(
                'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                failed
                  ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
                  : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
              )}
            >
              <FileKindIcon name={file.name} mediaType={file.media_type} kind={file.kind} className='text-base' />
            </div>
            <div className='min-w-0 flex-1'>
              <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>{file.name}</div>
              <div className='text-[11px] text-gray-400 dark:text-gray-500 flex items-center gap-1.5'>
                <span className='truncate'>
                  {t(typeLabelKey(file.name, file.media_type))} · {formatBytes(file.size)}
                </span>
                {file.status === 'preview_failed' && (
                  <span
                    className='flex flex-shrink-0 items-center text-amber-500 dark:text-amber-400'
                    title={t('session_files_preview_unavailable_hint')}
                  >
                    <ExclamationCircleFilled />
                  </span>
                )}
                {failed && (
                  <span className='flex flex-shrink-0 items-center text-red-500 dark:text-red-400'>
                    <ExclamationCircleFilled />
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

AttachmentMessageCards.displayName = 'AttachmentMessageCards';

export default memo(AttachmentMessageCards);
