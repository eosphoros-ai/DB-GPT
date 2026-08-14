/**
 * Read-only preview renderer for one session file.
 *
 * Renders a header (icon/name/size + truncated badge), a soft warning banner
 * for `preview_failed` snapshots, and a payload body routed by
 * `resolvePreviewMode`: table → Ant Table, text/markdown → <pre>,
 * document → metadata + extracted text. Empty/malformed payloads degrade to a
 * graceful empty state instead of crashing.
 *
 * Also exports the shared `FileKindIcon` used by the rail and the history
 * message group so all three surfaces show identical file metaphors.
 */

import {
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePptOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { Alert, Descriptions, Table, Tag } from 'antd';
import classNames from 'classnames';
import React, { memo, useMemo } from 'react';

import type { FileIconKey } from './attachment-view-model';
import {
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

const PRE_TEXT_CLASS =
  'max-h-[480px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-3 text-xs leading-relaxed text-gray-700 dark:bg-gray-800 dark:text-gray-300';

const AttachmentPreview: React.FC<AttachmentPreviewProps> = ({ snapshot, size, className }) => {
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

  if (!snapshot) {
    return (
      <div className={classNames('px-3 py-4 text-sm text-gray-400 dark:text-gray-500', className)}>
        No preview available.
      </div>
    );
  }

  const metadataEntries = documentData ? Object.entries(documentData.metadata) : [];

  return (
    <div className={classNames('flex flex-col gap-3', className)} data-component='attachment-preview'>
      {/* Header: icon + name (+size) + truncated badge */}
      <div className='flex min-w-0 items-center gap-2.5'>
        <div className='flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-green-50 dark:bg-green-900/30'>
          <FileKindIcon
            name={snapshot.name}
            mediaType={snapshot.media_type}
            kind={snapshot.kind}
            className='text-base'
          />
        </div>
        <div className='min-w-0 flex-1'>
          <div className='truncate text-sm font-medium text-gray-800 dark:text-gray-200' title={snapshot.name}>
            {snapshot.name}
          </div>
          {typeof size === 'number' && (
            <div className='text-[11px] text-gray-400 dark:text-gray-500'>{formatBytes(size)}</div>
          )}
        </div>
        {snapshot.truncated && <Tag color='warning'>Truncated</Tag>}
      </div>

      {/* preview_failed is a soft warning: the uploaded file is still analyzable */}
      {snapshot.status === 'preview_failed' && (
        <Alert
          type='warning'
          showIcon
          message='Preview unavailable'
          description={
            snapshot.error_code
              ? `The file was uploaded, but its preview could not be generated (${snapshot.error_code}). The original file can still be analyzed.`
              : 'The file was uploaded, but its preview could not be generated. The original file can still be analyzed.'
          }
        />
      )}

      {mode === 'table' && table && (
        <Table<Record<string, unknown>>
          size='small'
          scroll={{ x: true }}
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
        <div className='px-3 py-4 text-sm text-gray-400 dark:text-gray-500'>No preview available.</div>
      )}
    </div>
  );
};

AttachmentPreview.displayName = 'AttachmentPreview';
FileKindIcon.displayName = 'FileKindIcon';

export default memo(AttachmentPreview);
