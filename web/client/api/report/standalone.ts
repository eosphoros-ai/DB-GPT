import type { BrowserRenderObservation, ReportEvidenceDetail, ReportRun } from '@/types/report';

type Result<T> = { success: boolean; data: T; err_msg?: string | null };

const apiBaseUrl = (process.env.API_BASE_URL ?? '').replace(/\/$/, '');
const reportPath = (reportId: string) => `${apiBaseUrl}/api/v1/reports/${encodeURIComponent(reportId)}`;

const getJson = async <T>(path: string): Promise<Result<T>> => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<Result<T>>;
};

export const getStandaloneReportRun = (reportId: string, runId: string) =>
  getJson<ReportRun>(`${reportPath(reportId)}/runs/${encodeURIComponent(runId)}`);
export const getStandaloneBlockEvidence = (reportId: string, runId: string, blockId: string) =>
  getJson<ReportEvidenceDetail[]>(
    `${reportPath(reportId)}/runs/${encodeURIComponent(runId)}/blocks/${encodeURIComponent(blockId)}/evidence`,
  );

const runPath = (reportId: string, runId: string) => `${reportPath(reportId)}/runs/${encodeURIComponent(runId)}`;
export const getRenderObservations = (reportId: string, runId: string) =>
  getJson<BrowserRenderObservation[]>(`${runPath(reportId, runId)}/render-observations`);
export const saveRenderObservation = async (
  reportId: string,
  runId: string,
  observation: BrowserRenderObservation,
): Promise<Result<BrowserRenderObservation>> => {
  const response = await fetch(`${runPath(reportId, runId)}/render-observations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(observation),
  });
  if (!response.ok) throw new Error(`Render observation could not be saved (${response.status})`);
  return response.json();
};
export const downloadReportContent = async (
  reportId: string,
  runId: string,
  artifactId: string,
  part: string,
  observationId?: string,
) => {
  const path = observationId
    ? `${runPath(reportId, runId)}/render-observations/${encodeURIComponent(artifactId)}/${encodeURIComponent(observationId)}/content`
    : `${runPath(reportId, runId)}/artifacts/${encodeURIComponent(artifactId)}/content?part=${encodeURIComponent(part)}`;
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Snapshot download failed (${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `${artifactId}-${part}.${
    part === 'source' || part === 'output'
      ? response.headers
          .get('content-disposition')
          ?.match(/filename="?([^";]+)/)?.[1]
          ?.split('.')
          .pop() || 'bin'
      : 'json'
  }`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
};
