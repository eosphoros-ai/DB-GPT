/**
 * Read-only preview renderer for one session file.
 *
 * Renders a header (icon/name/size + human preview scope), a soft warning banner
 * for `preview_failed` snapshots, and a payload body routed by
 * `resolvePreviewMode`: table → Ant Table, text/markdown → <pre>,
 * document → metadata + extracted text. Empty/malformed payloads degrade to a
 * graceful empty state instead of crashing.
 *
 * Also exports the shared `FileKindIcon` used by the rail and the history
 * message group so all three surfaces show identical file metaphors.
 */

import {
  CloseOutlined,
  EyeOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePptOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { Alert, Descriptions, Table, Tooltip } from 'antd';
import classNames from 'classnames';
import React, { memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { FileIconKey } from './attachment-view-model';
import {
  buildPreviewScopeSummary,
  fileIconKey,
  formatBytes,
  normalizeDocumentPreview,
  normalizeTablePreview,
  normalizeTextPreview,
  resolvePreviewMode,
} from './attachment-view-model';
import type { SessionFilePreviewSnapshot } from './types';

/** Shared type-driven file icon (table/image/slide/text/generic). */
export const FileKindIcon: React.FC<{
  name?: string;
  mediaType?: string;
  kind?: string;
  className?: string;
}> = ({ name, mediaType, kind, className }) => {
  const key: FileIconKey = fileIconKey({ name, mediaType, kind });
  switch (key) {
    case 'table':
      return <FileExcelOutlined className={classNames('text-green-600', className)} />;
    case 'image':
      return <FileImageOutlined className={classNames('text-pink-500', className)} />;
    case 'slide':
      return <FilePptOutlined className={classNames('text-orange-500', className)} />;
    case 'text':
      return <FileTextOutlined className={classNames('text-blue-500', className)} />;
    default:
      return <FileOutlined className={classNames('text-gray-500', className)} />;
  }
};

/** JSON-ish cell values must never reach React children raw. */
function renderPreviewCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export interface AttachmentPreviewProps {
  /** Server preview payload; null/undefined renders the empty state. */
  snapshot?: SessionFilePreviewSnapshot | null;
  /** Optional byte size shown under the file name. */
  size?: number;
  className?: string;
}

/** Shared compact spacing for the home and responsive preview Drawers. */
export const ATTACHMENT_PREVIEW_DRAWER_STYLES = {
  header: { minHeight: 48, padding: '8px 12px' },
  body: { padding: 12 },
};

/** Consistent title used by the home Drawer and the in-chat right panel. */
export const AttachmentPreviewPanelTitle: React.FC = () => {
  const { t } = useTranslation();
  return (
    <div className='flex min-w-0 items-center gap-2'>
      <span className='flex h-7 w-7 flex-none items-center justify-center rounded-md bg-blue-50 text-[13px] text-blue-600 dark:bg-blue-950/45 dark:text-blue-300'>
        <EyeOutlined aria-hidden='true' />
      </span>
      <span className='truncate text-[13px] font-medium text-slate-700 dark:text-slate-200'>
        {t('session_files_preview_title')}
      </span>
    </div>
  );
};

/** A visible dismiss action that stays neutral until the user interacts. */
export const AttachmentPreviewCloseButton: React.FC<{ onClose: () => void; className?: string }> = ({
  onClose,
  className,
}) => {
  const { t } = useTranslation();
  return (
    <Tooltip title={t('session_files_close_preview_tooltip')} placement='left'>
      <button
        type='button'
        aria-label={t('session_files_close_preview_aria')}
        aria-keyshortcuts='Escape'
        onClick={onClose}
        className={classNames(
          'group inline-flex h-11 flex-none items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-600 shadow-[0_1px_2px_rgba(15,23,42,0.05)] outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-200 hover:border-red-200 hover:bg-red-50/80 hover:text-red-600 hover:shadow-[0_2px_8px_rgba(15,23,42,0.07)] focus-visible:ring-2 focus-visible:ring-blue-500/35 active:scale-[0.97] dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:border-red-900/70 dark:hover:bg-red-950/40 dark:hover:text-red-300 sm:h-8',
          className,
        )}
      >
        <CloseOutlined aria-hidden='true' className='text-[11px]' />
        <span>{t('session_files_close')}</span>
      </button>
    </Tooltip>
  );
};

const PRE_TEXT_CLASS =
  'max-h-[480px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-3 text-xs leading-relaxed text-gray-700 dark:bg-gray-800 dark:text-gray-300';

const AttachmentPreview: React.FC<AttachmentPreviewProps> = ({ snapshot, size, className }) => {
  const { t } = useTranslation();
  const mode = useMemo(
    () =>
      resolvePreviewMode({
        kind: snapshot?.kind,
        mediaType: snapshot?.media_type,
        preview: snapshot?.preview ?? null,
      }),
    [snapshot],
  );
  const table = useMemo(() => (mode === 'table' ? normalizeTablePreview(snapshot?.preview) : null), [mode, snapshot]);
  const text = useMemo(() => (mode === 'text' ? normalizeTextPreview(snapshot?.preview) : null), [mode, snapshot]);
  const documentData = useMemo(
    () => (mode === 'document' ? normalizeDocumentPreview(snapshot?.preview) : null),
    [mode, snapshot],
  );
  const scopeSummary = useMemo(
    () =>
      buildPreviewScopeSummary({
        mode,
        truncated: snapshot?.truncated ?? false,
        visibleRows: table?.rows.length,
      }),
    [mode, snapshot?.truncated, table?.rows.length],
  );

  if (!snapshot) {
    return (
      <div className={classNames('px-3 py-4 text-sm text-gray-400 dark:text-gray-500', className)}>
        {t('session_files_no_preview')}
      </div>
    );
  }

  const metadataEntries = documentData ? Object.entries(documentData.metadata) : [];

  const visibleScopeLabel =
    mode === 'table'
      ? table?.rows.length
        ? t('session_files_rows_preview', { count: table.rows.length })
        : t('session_files_no_data_rows')
      : scopeSummary
        ? t(scopeSummary.labelKey, scopeSummary.labelParams)
        : undefined;

  return (
    <div className={classNames('flex flex-col gap-2', className)} data-component='attachment-preview'>
      {/* File identity and the exact scope visible in this preview. */}
      <div className='flex min-w-0 flex-wrap items-center gap-2.5 rounded-lg border border-slate-200/80 bg-slate-50/65 px-2.5 py-2 dark:border-white/10 dark:bg-white/[0.035]'>
        <div className='flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white text-base shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-slate-200/70 dark:bg-white/[0.06] dark:ring-white/10'>
          <FileKindIcon
            name={snapshot.name}
            mediaType={snapshot.media_type}
            kind={snapshot.kind}
            className='text-base'
          />
        </div>
        <div className='flex min-w-[140px] flex-1 items-baseline gap-1.5'>
          <div
            className='min-w-0 truncate text-sm font-semibold text-slate-800 dark:text-slate-100'
            title={snapshot.name}
          >
            {snapshot.name}
          </div>
          {typeof size === 'number' && (
            <div className='flex-none text-[11px] text-slate-400 dark:text-slate-500'>· {formatBytes(size)}</div>
          )}
        </div>
        {scopeSummary && (
          <Tooltip title={scopeSummary.hintKey ? t(scopeSummary.hintKey) : undefined} placement='bottom'>
            <span
              tabIndex={scopeSummary.partial ? 0 : undefined}
              aria-label={
                scopeSummary.partial
                  ? t('session_files_partial_aria', {
                      label: t(scopeSummary.labelKey, scopeSummary.labelParams),
                      hint: scopeSummary.hintKey ? t(scopeSummary.hintKey) : '',
                    })
                  : t(scopeSummary.labelKey, scopeSummary.labelParams)
              }
              className='inline-flex h-7 flex-none items-center gap-1.5 rounded-md border border-blue-100 bg-blue-50/75 px-2 text-[11px] font-medium text-blue-700 outline-none focus-visible:ring-2 focus-visible:ring-blue-500/30 dark:border-blue-900/60 dark:bg-blue-950/35 dark:text-blue-300'
            >
              <EyeOutlined aria-hidden='true' className='text-[11px]' />
              <span>{visibleScopeLabel}</span>
              {scopeSummary.partial && (
                <>
                  <span aria-hidden='true' className='mx-0.5 h-3 w-px bg-blue-200 dark:bg-blue-800' />
                  <InfoCircleOutlined aria-hidden='true' className='text-[11px]' />
                  <span>{t('session_files_partial')}</span>
                </>
              )}
            </span>
          </Tooltip>
        )}
      </div>

      {/* preview_failed is a soft warning: the uploaded file is still analyzable */}
      {snapshot.status === 'preview_failed' && (
        <Alert
          type='warning'
          showIcon
          message={t('session_files_preview_unavailable_title')}
          description={
            snapshot.error_code
              ? t('session_files_preview_failed_with_code', { code: snapshot.error_code })
              : t('session_files_preview_failed_no_code')
          }
        />
      )}

      {mode === 'table' && table && (
        <Table<Record<string, unknown>>
          className='overflow-hidden rounded-xl border border-slate-200/80 dark:border-white/10'
          size='small'
          scroll={{ x: true }}
          // Session-file previews are normally bounded to 20 rows; the legacy
          // adapter can expose more, so preserve its compact pagination.
          pagination={table.rows.length > 50 ? { pageSize: 50, size: 'small', hideOnSinglePage: true } : false}
          columns={table.columns.map((column, index) => ({
            title: column,
            dataIndex: `col${index}`,
            key: `col${index}`,
            ellipsis: true,
            render: renderPreviewCell,
          }))}
          dataSource={table.rows.map((row, rowIndex) => {
            const record: Record<string, unknown> = { key: rowIndex };
            table.columns.forEach((_, colIndex) => {
              record[`col${colIndex}`] = row[colIndex];
            });
            return record;
          })}
        />
      )}

      {mode === 'text' && text !== null && <pre className={PRE_TEXT_CLASS}>{text}</pre>}

      {mode === 'document' && documentData && (
        <div className='flex flex-col gap-2'>
          {metadataEntries.length > 0 && (
            <Descriptions
              size='small'
              column={1}
              bordered
              items={metadataEntries.map(([key, value]) => ({
                key,
                label: key,
                children: renderPreviewCell(value),
              }))}
            />
          )}
          {documentData.text !== null && <pre className={PRE_TEXT_CLASS}>{documentData.text}</pre>}
        </div>
      )}

      {mode === 'empty' && (
        <div className='rounded-xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-400 dark:border-white/10 dark:text-slate-500'>
          {snapshot.truncated ? t('session_files_preview_limited') : t('session_files_no_preview')}
        </div>
      )}
    </div>
  );
};

AttachmentPreview.displayName = 'AttachmentPreview';
AttachmentPreviewPanelTitle.displayName = 'AttachmentPreviewPanelTitle';
AttachmentPreviewCloseButton.displayName = 'AttachmentPreviewCloseButton';
FileKindIcon.displayName = 'FileKindIcon';

export default memo(AttachmentPreview);
