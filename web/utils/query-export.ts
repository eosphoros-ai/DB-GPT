/**
 * Client-side exporters for query artifacts (SQL result sets).
 *
 * CSV carries a UTF-8 BOM so Excel opens Chinese content without garbling;
 * xlsx goes through the official SheetJS build (web dependency ``xlsx``).
 * Both export the full in-memory row set carried by the artifact payload
 * (the backend caps it at 2000 rows and flags ``truncated``).
 */
import * as XLSX from 'xlsx';

export interface QueryArtifactPayload {
  sql: string;
  columns: string[];
  rows: any[][];
  row_count?: number;
  truncated?: boolean;
  db_name?: string;
  execution?: {
    status: 'succeeded' | 'failed';
    started_at: string;
    duration_ms: number;
    tool: string;
    artifact_id?: string | null;
    error?: string;
  };
}

function csvCell(value: any): string {
  if (value == null) return '';
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildQueryCsv(payload: QueryArtifactPayload): string {
  const columns = payload.columns || [];
  const lines = [columns.map(csvCell).join(',')];
  for (const row of payload.rows || []) {
    lines.push(columns.map((_, i) => csvCell(row?.[i])).join(','));
  }
  return lines.join('\r\n');
}

function triggerDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

function withExt(fileName: string, ext: string): string {
  const bare = (fileName || 'query').replace(/\.(csv|xlsx|xls)$/i, '');
  return `${bare}.${ext}`;
}

export function downloadQueryCsv(payload: QueryArtifactPayload, fileName: string) {
  const blob = new Blob(['\uFEFF' + buildQueryCsv(payload)], {
    type: 'text/csv;charset=utf-8',
  });
  triggerDownload(blob, withExt(fileName, 'csv'));
}

export function downloadQueryXlsx(payload: QueryArtifactPayload, fileName: string) {
  const aoa: any[][] = [payload.columns || [], ...(payload.rows || [])];
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Query');
  const out = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
  const blob = new Blob([out], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  triggerDownload(blob, withExt(fileName, 'xlsx'));
}
