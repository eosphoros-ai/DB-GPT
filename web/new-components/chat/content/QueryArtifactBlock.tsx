/**
 * QueryArtifactBlock — first-class data artifact for SQL result sets.
 *
 * Mockup form (data-agent-product-mockup ws-query view): two stacked
 * full-width cards — a dark SQL block (copy / edit & re-run) and a result
 * table card with CSV / Excel export. Rendered inline in the conversation
 * stream (react rounds) and inside TaskFlow node cards (flow rounds).
 */
import {
  CheckOutlined,
  CopyOutlined,
  EditOutlined,
  FileExcelOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  TableOutlined,
} from '@ant-design/icons';
import { message } from 'antd';
import cls from 'classnames';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { downloadQueryCsv, downloadQueryXlsx, type QueryArtifactPayload } from '@/utils/query-export';

const PREVIEW_ROWS = 50;

const SQL_TOKEN_RE =
  /(--[^\n]*)|('(?:[^']|'')*')|(\b(?:SUM|COUNT|AVG|MAX|MIN|ROUND|COALESCE|IFNULL)\s*\()|(\b(?:SELECT|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|AS|AND|OR|NOT|IN|IS|NULL|LIKE|BETWEEN|EXISTS|DISTINCT|UNION|ALL|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|CASE|WHEN|THEN|ELSE|END|ASC|DESC)\b)|(\b\d+(?:\.\d+)?\b)/gi;

const TOKEN_CLASS = [
  'italic text-[#7d8590]', // comment
  'text-[#7ee787]', // string literal
  'text-[#fbbf24]', // aggregate / function
  'text-[#ff7b72] font-semibold', // keyword
  'text-[#79c0ff]', // number
];

function highlightSql(sql: string) {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const match of sql.matchAll(SQL_TOKEN_RE)) {
    const idx = match.index ?? 0;
    if (idx > last) nodes.push(sql.slice(last, idx));
    const groupIdx = match.slice(1).findIndex(g => g !== undefined);
    nodes.push(
      <span key={key++} className={TOKEN_CLASS[groupIdx] ?? ''}>
        {match[0]}
      </span>,
    );
    last = idx + match[0].length;
  }
  if (last < sql.length) nodes.push(sql.slice(last));
  return nodes;
}

function isNumericColumn(rows: any[][], col: number): boolean {
  let seen = false;
  for (const row of rows) {
    const v = row?.[col];
    if (v == null || v === '') continue;
    seen = true;
    if (typeof v === 'number') continue;
    if (typeof v === 'string' && v.trim() !== '' && !isNaN(Number(v))) continue;
    return false;
  }
  return seen;
}

function formatCell(v: any): string {
  if (v == null) return '';
  if (typeof v === 'number') {
    return Number.isInteger(v)
      ? v.toLocaleString('en-US')
      : v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(v);
}

export interface QueryArtifactBlockProps {
  payload: QueryArtifactPayload;
  /** Edit & re-run: resolves with the new query payload (parent appends it
   *  as a new artifact). Absent = read-only block. */
  onRerun?: (sql: string, dbName?: string) => Promise<QueryArtifactPayload>;
  fileName?: string;
  className?: string;
}

export default function QueryArtifactBlock({ payload, onRerun, fileName, className }: QueryArtifactBlockProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(payload.sql || '');
  const [running, setRunning] = useState(false);

  const columns = useMemo(() => payload.columns || [], [payload.columns]);
  const rows = useMemo(() => payload.rows || [], [payload.rows]);
  const totalCount = payload.row_count ?? rows.length;
  const numericCols = useMemo(() => columns.map((_, i) => isNumericColumn(rows, i)), [columns, rows]);
  const previewRows = rows.slice(0, PREVIEW_ROWS);
  const exportName = fileName || 'query_result';

  const copySql = () => {
    navigator.clipboard.writeText(payload.sql || '').then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const runDraft = async () => {
    if (!onRerun || running) return;
    const sql = draft.trim();
    if (!sql) return;
    setRunning(true);
    try {
      await onRerun(sql, payload.db_name);
      setEditing(false);
    } catch (e: any) {
      message.error(e?.message || t('qa_rerun_failed', '重跑失败'));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className={cls('flex flex-col gap-3 w-full', className)}>
      {/* ── SQL card ─────────────────────────────────────────────── */}
      <div className='border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] bg-white dark:bg-[#111217] overflow-hidden shadow-[0_1px_2px_rgba(20,20,15,.05),0_4px_16px_rgba(20,20,15,.04)]'>
        <div className='px-4 py-2.5 flex items-center gap-2 border-b border-[#efefeb] dark:border-[#232220]'>
          <span className='h-[22px] px-2 rounded-[6px] bg-[#e8f1ff] dark:bg-[#0069fe22] text-[#0069fe] text-[11px] font-semibold inline-flex items-center flex-none'>
            {t('qa_sql_chip', 'SQL')}
          </span>
          <span className='text-[13px] font-medium text-[#1c1c1a] dark:text-[#e6e4df] truncate'>
            {t('qa_sql_title', '生成语句 · 可编辑/复制')}
          </span>
          <span className='ml-auto flex items-center gap-3 flex-none'>
            {onRerun && !editing && (
              <button
                type='button'
                onClick={() => {
                  setDraft(payload.sql || '');
                  setEditing(true);
                }}
                className='inline-flex items-center gap-1 text-[12.5px] text-[#0069fe] hover:opacity-80'
              >
                <EditOutlined className='text-[11px]' />
                {t('qa_edit', '编辑')}
              </button>
            )}
            <button
              type='button'
              onClick={copySql}
              className='inline-flex items-center gap-1 text-[12.5px] text-[#0069fe] hover:opacity-80'
            >
              {copied ? <CheckOutlined className='text-[11px]' /> : <CopyOutlined className='text-[11px]' />}
              {copied ? t('qa_copied', '已复制') : t('qa_copy', '复制')}
            </button>
          </span>
        </div>
        <div className='p-4'>
          {editing ? (
            <div className='flex flex-col gap-2'>
              <textarea
                value={draft}
                onChange={e => setDraft(e.target.value)}
                rows={Math.min(12, Math.max(3, draft.split('\n').length + 1))}
                spellCheck={false}
                className='w-full rounded-lg bg-[#0d1520] text-[#e6edf3] font-mono text-[13px] leading-6 p-4 outline-none border border-[#22304a] focus:border-[#0069fe] resize-y'
              />
              <div className='flex items-center gap-2'>
                <button
                  type='button'
                  disabled={running || !draft.trim()}
                  onClick={runDraft}
                  className='h-7 px-3 inline-flex items-center gap-1.5 rounded-md bg-[#0069fe] text-white text-[12.5px] font-medium hover:opacity-90 disabled:opacity-50'
                >
                  {running ? (
                    <LoadingOutlined className='text-[11px]' />
                  ) : (
                    <PlayCircleOutlined className='text-[12px]' />
                  )}
                  {running ? t('qa_running', '运行中…') : t('qa_run', '运行')}
                </button>
                <button
                  type='button'
                  disabled={running}
                  onClick={() => setEditing(false)}
                  className='h-7 px-3 rounded-md border border-[#e6e6e2] dark:border-[#2a2925] text-[12.5px] text-[#55554f] dark:text-[#a8a59e] hover:bg-[#f4f4f0] dark:hover:bg-white/[.06]'
                >
                  {t('qa_cancel', '取消')}
                </button>
              </div>
            </div>
          ) : (
            <pre className='rounded-lg bg-[#0d1520] text-[#e6edf3] font-mono text-[13px] leading-6 p-4 overflow-x-auto whitespace-pre-wrap break-words'>
              {highlightSql(payload.sql || '')}
            </pre>
          )}
        </div>
      </div>

      {/* ── Result card ──────────────────────────────────────────── */}
      <div className='border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] bg-white dark:bg-[#111217] overflow-hidden shadow-[0_1px_2px_rgba(20,20,15,.05),0_4px_16px_rgba(20,20,15,.04)]'>
        <div className='px-4 py-2.5 flex items-center gap-2 border-b border-[#efefeb] dark:border-[#232220]'>
          <span className='h-[22px] px-2 rounded-[6px] bg-[#fff3e6] dark:bg-[#f59e0b22] text-[#d97706] text-[11px] font-semibold inline-flex items-center flex-none'>
            {t('qa_result_chip', '结果')}
          </span>
          <span className='text-[13px] font-medium text-[#1c1c1a] dark:text-[#e6e4df] truncate'>
            {t('qa_result_title', '查询结果 · {{count}} 行', { count: totalCount })}
          </span>
          <span className='ml-auto flex items-center gap-3 flex-none'>
            <button
              type='button'
              onClick={() => downloadQueryCsv(payload, exportName)}
              className='text-[12.5px] text-[#0069fe] hover:opacity-80'
            >
              {t('qa_export_csv', '导出 CSV')} ›
            </button>
            <button
              type='button'
              onClick={() => downloadQueryXlsx(payload, exportName)}
              className='inline-flex items-center gap-1 text-[12.5px] text-[#0069fe] hover:opacity-80'
            >
              <FileExcelOutlined className='text-[11px]' />
              {t('qa_export_xlsx', '导出 Excel')} ›
            </button>
          </span>
        </div>
        {rows.length === 0 ? (
          <div className='px-4 py-6 flex items-center justify-center gap-2 text-[12.5px] text-[#8b8b84] dark:text-[#7c7972]'>
            <TableOutlined />
            {t('qa_empty', '查询返回空结果')}
          </div>
        ) : (
          <>
            {/* Fixed-height scroll body: 60+ row result sets must not stretch
                the card across screens; the header row stays pinned. */}
            <div className='overflow-auto max-h-[380px]'>
              <table className='w-full text-[13px] text-[#1c1c1a] dark:text-[#e6e4df]'>
                <thead>
                  <tr className='text-[#8b8b84] dark:text-[#7c7972]'>
                    {columns.map((col, i) => (
                      <th
                        key={`${col}-${i}`}
                        className={cls(
                          'sticky top-0 z-10 bg-[#f7f7f5] dark:bg-[#17181c] px-4 py-2.5 font-medium text-left whitespace-nowrap',
                          numericCols[i] && 'text-right',
                        )}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className='border-t border-[#f0f0ec] dark:border-[#232220] hover:bg-[#fafaf7] dark:hover:bg-white/[.03]'
                    >
                      {columns.map((_, cIdx) => (
                        <td
                          key={cIdx}
                          className={cls(
                            'px-4 py-2.5 whitespace-nowrap font-mono text-[12.5px]',
                            numericCols[cIdx] ? 'text-right' : 'text-left',
                          )}
                        >
                          {formatCell(row?.[cIdx])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rows.length > PREVIEW_ROWS && (
              <div className='px-4 py-2 border-t border-[#f0f0ec] dark:border-[#232220] text-[12px] text-[#8b8b84] dark:text-[#7c7972]'>
                {t('qa_preview_note', '仅显示前 {{count}} 行 · 导出获取全量', {
                  count: PREVIEW_ROWS,
                })}
              </div>
            )}
            {payload.truncated && (
              <div className='px-4 py-2 border-t border-[#f0f0ec] dark:border-[#232220] text-[12px] text-[#d97706]'>
                {t('qa_truncated_note', '结果已截断至前 {{kept}} 行（共 {{count}} 行）', {
                  kept: rows.length,
                  count: totalCount,
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
