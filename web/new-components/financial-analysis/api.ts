import type { ApiResponse } from '@/client/api';
import { GET, POST } from '@/client/api';
import type { FinancialExport, ReportData, ReportQuestionAnswer, SourceDocument } from './types';

export interface FinancialRunStatus {
  id: string;
  session_id: string;
  file_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  stage: string;
  error: string | null;
  report_ready?: boolean;
  analysis_status?: 'running' | 'completed' | 'partial' | 'failed' | null;
  created_at: string;
  completed_at?: string | null;
  title?: string;
  fiscal_period?: string | null;
}
export interface FinancialRunHistory {
  items: FinancialRunStatus[];
  total: number;
  page: number;
  page_size: number;
}
const base = '/api/v1/financial-analysis/runs';
export async function listRuns(page: number, signal: AbortSignal) {
  return unwrap(await GET<unknown, FinancialRunHistory>(base, { page, page_size: 10 }, { signal }));
}
export async function listExports(sessionId: string, runId: string, signal: AbortSignal) {
  return unwrap(
    await GET<unknown, FinancialExport[]>(
      `${base}/${encodeURIComponent(runId)}/exports`,
      { session_id: sessionId },
      { signal },
    ),
  );
}
export async function createExport(sessionId: string, runId: string, revision: string, format: 'json' | 'html') {
  return unwrap(
    await POST<unknown, FinancialExport>(`${base}/${encodeURIComponent(runId)}/exports`, {
      session_id: sessionId,
      revision,
      format,
    }),
  );
}
export async function downloadExport(sessionId: string, runId: string, file: FinancialExport) {
  const blob = await sourceBlob(
    sessionId,
    `${base}/${encodeURIComponent(runId)}/exports/${encodeURIComponent(file.id)}`,
    file.format === 'json' ? 'application/json' : 'text/html',
  );
  saveBlob(blob, file.file_name);
}
function unwrap<T>(response: ApiResponse<T>): T {
  if (!response.data.success) throw new Error(response.data.err_msg || '财报请求失败');
  return response.data.data;
}
export async function createRun(sessionId: string, fileId: string, requestId: string) {
  return unwrap(
    await POST<unknown, FinancialRunStatus>(base, {
      session_id: sessionId,
      file_ids: [fileId],
      request_id: requestId,
    }),
  );
}
export async function getRun(sessionId: string, runId: string, signal?: AbortSignal) {
  return unwrap(
    await GET<unknown, FinancialRunStatus>(
      `${base}/${encodeURIComponent(runId)}`,
      { session_id: sessionId },
      { signal },
    ),
  );
}
export async function getReport(sessionId: string, runId: string, signal?: AbortSignal) {
  return unwrap(
    await GET<unknown, ReportData>(
      `${base}/${encodeURIComponent(runId)}/report`,
      { session_id: sessionId },
      { signal },
    ),
  );
}
export async function getLatestReport(sessionId: string, signal?: AbortSignal) {
  return unwrap(
    await GET<unknown, ReportData | null>(`${base}/latest`, { session_id: sessionId }, { signal }),
  );
}
export function requestError(error: unknown): string {
  const value = error as { response?: { data?: { err_msg?: string } }; message?: string };
  return value?.response?.data?.err_msg || value?.message || '请求失败，请重试';
}

export async function askQuestion(
  sessionId: string,
  runId: string,
  revision: string,
  question: string,
  signal: AbortSignal,
) {
  try {
    return unwrap(
      await POST<unknown, ReportQuestionAnswer>(
        `${base}/${encodeURIComponent(runId)}/questions`,
        { session_id: sessionId, revision, question },
        { signal, timeout: 70000 },
      ),
    );
  } catch (cause) {
    throw new Error(requestError(cause));
  }
}

async function sourceBlob(sessionId: string, path: string, type: string, signal?: AbortSignal): Promise<Blob> {
  try {
    const response = await GET(path, { session_id: sessionId }, { responseType: 'blob', signal });
    const blob = response.data as unknown as Blob;
    if (!(blob instanceof Blob) || blob.type.split(';')[0] !== type) throw new Error('文件响应格式错误');
    return blob;
  } catch (cause) {
    const data = (cause as { response?: { data?: unknown } })?.response?.data;
    if (data instanceof Blob) {
      let message: string | undefined;
      try {
        message = JSON.parse(await data.text()).err_msg;
      } catch {
        /* Not a JSON error envelope. */
      }
      if (message) throw new Error(message);
    }
    throw new Error(requestError(cause));
  }
}

const sourcePath = (runId: string, documentId: string) =>
  `${base}/${encodeURIComponent(runId)}/documents/${encodeURIComponent(documentId)}`;

export const getSourcePage = (
  sessionId: string,
  runId: string,
  documentId: string,
  page: number,
  signal: AbortSignal,
) => sourceBlob(sessionId, `${sourcePath(runId, documentId)}/pages/${page}`, 'image/png', signal);

export async function downloadSource(sessionId: string, runId: string, source: SourceDocument) {
  const blob = await sourceBlob(sessionId, `${sourcePath(runId, source.id)}/download`, 'application/pdf');
  saveBlob(blob, source.fileName);
}

function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  try {
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
