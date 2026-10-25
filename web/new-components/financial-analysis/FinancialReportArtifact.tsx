import { Alert, Button, Spin } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import FinancialReportView from './FinancialReportView';
import type { FinancialReportReference } from './agent-artifact';
import {
  askQuestion,
  configureComparison,
  createExport,
  downloadExport,
  downloadSource,
  getReport,
  getRun,
  getSourcePage,
  listExports,
  listRevisions,
  requestError,
  resumeComparison,
} from './api';
import type { FinancialCitationTarget } from './report-citations';
import type {
  ComparisonAccess,
  FinancialReportData,
  ReportExportAccess,
  ReportQuestionAccess,
  ReportRevisionAccess,
  SourcePreviewAccess,
} from './types';

export async function downloadFinancialReport(ref: FinancialReportReference) {
  const report = await getReport(
    ref.sessionId,
    ref.runId,
    undefined,
    ref.published === false ? undefined : ref.revision,
  );
  const file = await createExport(ref.sessionId, ref.runId, report.revision, 'html');
  await downloadExport(ref.sessionId, ref.runId, file);
}

/** Render in the current agent's Computer panel; no route or second chat rail. */
const FinancialReportArtifact: React.FC<{
  reference: FinancialReportReference;
  citationTarget?: FinancialCitationTarget | null;
  busy?: boolean;
  onTopicRetry?: (reference: FinancialReportReference, topicId: string) => void;
}> = ({ reference, citationTarget, busy, onTopicRetry }) => {
  const { sessionId, runId, revision } = reference;
  const [loaded, setLoaded] = useState<{ scope: string; data: FinancialReportData } | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [awaitingAction, setAwaitingAction] = useState(false);
  const [selection, setSelection] = useState<{ runId: string; revision?: string }>();
  const pinnedRevision =
    citationTarget?.revision ||
    (selection?.runId === runId ? selection.revision : reference.published === false ? undefined : revision);
  const scope = `${sessionId}:${runId}:${pinnedRevision || 'draft'}`;
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setError('');
    const refresh = async () => {
      let keepPolling = !!busy;
      try {
        const data = await getReport(sessionId, runId, controller.signal, pinnedRevision);
        if (controller.signal.aborted) return;
        setLoaded({ scope, data });
        if (awaitingAction && !pinnedRevision) {
          const status = await getRun(sessionId, runId, controller.signal);
          keepPolling ||= ['pending', 'running'].includes(status.status) || status.stage === 'agent_topics';
          if (!keepPolling && !controller.signal.aborted) setAwaitingAction(false);
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(requestError(cause));
          setAwaitingAction(false);
        }
      } finally {
        if (keepPolling && !controller.signal.aborted) timer = setTimeout(() => void refresh(), 2000);
      }
    };
    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [sessionId, runId, scope, pinnedRevision, retry, busy, awaitingAction]);
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
  const questionAccess = useMemo<ReportQuestionAccess>(
    () => ({
      ask: (question, reportRevision, signal) => askQuestion(sessionId, runId, reportRevision, question, signal),
    }),
    [sessionId, runId],
  );
  const revisionAccess = useMemo<ReportRevisionAccess>(
    () => ({
      selectedRevision: pinnedRevision,
      list: signal => listRevisions(sessionId, runId, signal),
      select: selected => setSelection({ runId, revision: selected }),
    }),
    [sessionId, runId, pinnedRevision],
  );
  const comparisonAccess = useMemo<ComparisonAccess>(
    () => ({
      configure: async (config, currentRevision) => {
        const next = await configureComparison(sessionId, runId, currentRevision, config);
        setLoaded({ scope, data: next });
        setAwaitingAction(true);
      },
      resume: async (currentRevision, resolutions) => {
        await resumeComparison(sessionId, runId, currentRevision, resolutions);
        setAwaitingAction(true);
        setRetry(value => value + 1);
      },
    }),
    [sessionId, runId, scope],
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
    <FinancialReportView
      data={loaded.data}
      citationTarget={citationTarget}
      embedded
      sourceAccess={sourceAccess}
      exportAccess={exportAccess}
      questionAccess={questionAccess}
      revisionAccess={revisionAccess}
      comparisonAccess={loaded.data.mode === 'comparison' && !pinnedRevision ? comparisonAccess : undefined}
      busy={busy}
      onTopicRetry={onTopicRetry ? topicId => onTopicRetry(reference, topicId) : undefined}
    />
  );
};

export default FinancialReportArtifact;
