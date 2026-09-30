import { Alert, Button, Spin } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import FinancialAnalysisPage from './FinancialAnalysisPage';
import type { FinancialReportReference } from './agent-artifact';
import {
  createExport,
  downloadExport,
  downloadSource,
  getReport,
  getSourcePage,
  listExports,
  requestError,
} from './api';
import type { ReportData, ReportExportAccess, SourcePreviewAccess } from './types';

export async function downloadFinancialReport(ref: FinancialReportReference) {
  const report = await getReport(ref.sessionId, ref.runId);
  const file = await createExport(ref.sessionId, ref.runId, report.revision, 'html');
  await downloadExport(ref.sessionId, ref.runId, file);
}

/** Render in the current agent's Computer panel; no route or second chat rail. */
const FinancialReportArtifact: React.FC<{
  reference: FinancialReportReference;
  busy?: boolean;
  onTopicRetry?: (reference: FinancialReportReference, topicId: string) => void;
}> = ({ reference, busy, onTopicRetry }) => {
  const { sessionId, runId, revision } = reference;
  const [loaded, setLoaded] = useState<{ scope: string; data: ReportData } | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const scope = `${sessionId}:${runId}:${revision}`;
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setError('');
    const refresh = () =>
      void getReport(sessionId, runId, controller.signal)
        .then(data => {
          if (!controller.signal.aborted) setLoaded({ scope, data });
        })
        .catch(cause => {
          if (!controller.signal.aborted) setError(requestError(cause));
        })
        .finally(() => {
          if (busy && !controller.signal.aborted) timer = setTimeout(refresh, 2000);
        });
    refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [sessionId, runId, scope, retry, busy]);
  const sourceAccess = useMemo<SourcePreviewAccess>(
    () => ({
      loadPage: (documentId, page, signal) => getSourcePage(sessionId, runId, documentId, page, signal),
      download: document => downloadSource(sessionId, runId, document),
    }),
    [sessionId, runId],
  );
  const exportAccess = useMemo<ReportExportAccess>(
    () => ({
      list: signal => listExports(sessionId, runId, signal),
      create: (format, reportRevision) => createExport(sessionId, runId, reportRevision, format),
      download: file => downloadExport(sessionId, runId, file),
    }),
    [sessionId, runId],
  );
  if (error)
    return (
      <Alert type='error' message={error} action={<Button onClick={() => setRetry(v => v + 1)}>重新读取报告</Button>} />
    );
  if (!loaded || loaded.scope !== scope)
    return (
      <div className='p-6'>
        <Spin /> 正在读取智能体财报结果
      </div>
    );
  return (
    <FinancialAnalysisPage
      data={loaded.data}
      embedded
      sourceAccess={sourceAccess}
      exportAccess={exportAccess}
      busy={busy}
      onTopicRetry={onTopicRetry ? topicId => onTopicRetry(reference, topicId) : undefined}
    />
  );
};

export default FinancialReportArtifact;
