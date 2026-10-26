import { uploadFiles } from '@/modules/session-files/api';
import { Alert, Button, Card, Select, Space, Spin, Typography } from 'antd';
import { useRouter } from 'next/router';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import FinancialReportView from './FinancialReportView';
import ReportHistory from './ReportHistory';
import type { FinancialRunStatus } from './api';
import {
  askQuestion,
  configureComparison,
  createComparison,
  createExport,
  createRun,
  downloadExport,
  downloadSource,
  getReport,
  getRun,
  getSourcePage,
  listExports,
  listRevisions,
  listRuns,
  requestError,
  resumeComparison,
  retryComparisonTopic,
} from './api';
import { financialText, useFinancialLocale } from './i18n';
import { createRequestId } from './request-id';
import type {
  ComparisonAccess,
  FinancialReportData,
  ReportExportAccess,
  ReportQuestionAccess,
  ReportRevisionAccess,
  SourcePreviewAccess,
} from './types';

const stageLabels: Record<string, string> = {
  get queued() {
    return financialText('financial.awaiting_analysis');
  },
  get extract() {
    return financialText('financial.reading_pdf_and_extracting_financial_facts');
  },
  get calculate() {
    return financialText('financial.calculating_financial_metrics');
  },
  get save() {
    return financialText('financial.saving_report');
  },
  get analyze() {
    return financialText('financial.financial_data_is_ready_generating_model_analysis');
  },
  get completed() {
    return financialText('financial.analysis_complete');
  },
};

const FinancialAnalysisRoute: React.FC = () => {
  useFinancialLocale();
  const router = useRouter();
  const runId = typeof router.query.run_id === 'string' ? router.query.run_id : '';
  const sessionId = typeof router.query.session_id === 'string' ? router.query.session_id : '';
  const revision = typeof router.query.revision === 'string' ? router.query.revision : undefined;
  const reportScope = `${sessionId}:${runId}:${revision || 'current'}`;
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'report' | 'peer' | 'trend'>('report');
  const [baselineIndex, setBaselineIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const attempt = useRef<{ sessionId: string; fileIds: string[]; requestId: string; retryOf?: string } | null>(null);
  const [error, setError] = useState('');
  const [run, setRun] = useState<FinancialRunStatus | null>(null);
  const [data, setData] = useState<FinancialReportData | null>(null);
  const [loadedScope, setLoadedScope] = useState('');
  const [retry, setRetry] = useState(0);
  const sourceAccess = useMemo<SourcePreviewAccess>(
    () => ({
      loadPage: (documentId, page, signal) => getSourcePage(sessionId, runId, documentId, page, signal),
      download: document => downloadSource(sessionId, runId, document),
    }),
    [sessionId, runId],
  );
  const questionAccess = useMemo<ReportQuestionAccess>(
    () => ({ ask: (question, revision, signal) => askQuestion(sessionId, runId, revision, question, signal) }),
    [sessionId, runId],
  );
  const exportAccess = useMemo<ReportExportAccess>(
    () => ({
      list: signal => listExports(sessionId, runId, signal),
      create: async (format, revision) => {
        try {
          return await createExport(sessionId, runId, revision, format);
        } catch (cause) {
          throw new Error(requestError(cause));
        }
      },
      download: file => downloadExport(sessionId, runId, file),
    }),
    [sessionId, runId],
  );
  const comparisonAccess = useMemo<ComparisonAccess>(
    () => ({
      configure: async (config, revision) => {
        setData(await configureComparison(sessionId, runId, revision, config));
        setRetry(value => value + 1);
      },
      resume: async (revision, resolutions) => {
        await resumeComparison(sessionId, runId, revision, resolutions);
        setRetry(value => value + 1);
      },
    }),
    [sessionId, runId],
  );
  const revisionAccess = useMemo<ReportRevisionAccess>(
    () => ({
      selectedRevision: revision,
      list: signal => listRevisions(sessionId, runId, signal),
      select: selected => {
        const query: Record<string, string> = { session_id: sessionId, run_id: runId };
        if (selected) query.revision = selected;
        void router.replace({ pathname: '/financial-analysis', query });
      },
    }),
    [sessionId, runId, revision, router],
  );

  useEffect(() => {
    setRun(null);
    setError('');
    if (!router.isReady || !runId || !sessionId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const status = await getRun(sessionId, runId, controller.signal);
        if (controller.signal.aborted) return;
        setRun(status);
        if (status.report_ready || status.status === 'completed') {
          const report = await getReport(sessionId, runId, controller.signal, revision);
          if (!controller.signal.aborted) {
            setData(report);
            setLoadedScope(reportScope);
            setError('');
            if (
              !revision &&
              (report.analysis?.status === 'running' ||
                status.status === 'running' ||
                status.status === 'pending' ||
                status.stage === 'agent_topics')
            )
              timer = setTimeout(poll, 1500);
          }
        } else if (status.status !== 'failed') {
          timer = setTimeout(poll, 1500);
        }
      } catch (cause) {
        if (!controller.signal.aborted) setError(requestError(cause));
      }
    };
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [router.isReady, runId, sessionId, revision, reportScope, retry]);

  const submit = async (previous?: FinancialRunStatus) => {
    if (busyRef.current || (!files.length && !previous)) return;
    busyRef.current = true;
    setBusy(true);
    setError('');
    try {
      if (previous?.mode === 'comparison') {
        await resumeComparison(
          previous.session_id,
          previous.id,
          data?.report.run.id === previous.id ? data.revision : undefined,
        );
        setRetry(value => value + 1);
        return;
      }
      if (previous && attempt.current?.retryOf !== previous.id) {
        attempt.current = {
          sessionId: previous.session_id,
          fileIds: [previous.file_id],
          requestId: createRequestId(),
          retryOf: previous.id,
        };
      } else if (!attempt.current) {
        const nextSession = `financial-${createRequestId()}`;
        if ((mode === 'report' && files.length !== 1) || (mode !== 'report' && (files.length < 2 || files.length > 5)))
          throw new Error(
            financialText('financial.single_report_analysis_requires_one_pdf_comparison_requires_two_to_f'),
          );
        const uploaded = await uploadFiles({ sessionId: nextSession, files });
        if (uploaded.length !== files.length) throw new Error(financialText('financial.some_files_failed_to_upload'));
        attempt.current = {
          sessionId: nextSession,
          fileIds: uploaded.map(item => item.file_id),
          requestId: createRequestId(),
        };
      }
      const next = attempt.current!;
      const created =
        previous || mode === 'report'
          ? await createRun(next.sessionId, next.fileIds[0], next.requestId)
          : await createComparison(next.sessionId, next.fileIds, next.requestId, {
              kind: mode,
              baseline_file_id: next.fileIds[baselineIndex],
            });
      await router.push({ pathname: '/financial-analysis', query: { run_id: created.id, session_id: next.sessionId } });
    } catch (cause) {
      setError(requestError(cause));
    } finally {
      setBusy(false);
      busyRef.current = false;
    }
  };
  const startNew = () => {
    attempt.current = null;
    setFiles([]);
    setError('');
    void router.push('/financial-analysis');
  };
  const activeRun = run?.id === runId && run.session_id === sessionId ? run : null;
  if (data && loadedScope === reportScope && data.report.run.id === runId)
    return (
      <FinancialReportView
        data={data}
        onNewReport={startNew}
        sourceAccess={sourceAccess}
        questionAccess={questionAccess}
        exportAccess={exportAccess}
        revisionAccess={revisionAccess}
        comparisonAccess={data.mode === 'comparison' && !revision ? comparisonAccess : undefined}
        onTopicRetry={
          data.mode === 'comparison' && !revision
            ? topicId => {
                void retryComparisonTopic(sessionId, runId, data.revision, topicId)
                  .then(() => setRetry(value => value + 1))
                  .catch(cause => setError(requestError(cause)));
              }
            : undefined
        }
        analysisActions={{
          retry: () => {
            if (activeRun) void submit(activeRun);
          },
          refresh: () => setRetry(value => value + 1),
          busy,
          error,
        }}
      />
    );
  const invalidLink = !!runId !== !!sessionId;
  return (
    <main className='mx-auto max-w-3xl p-8'>
      <Card>
        <Space direction='vertical' size='large' className='w-full'>
          <Typography.Title level={2}>{financialText('financial.financial_report_analysis')}</Typography.Title>
          {!router.isReady ? (
            <Spin />
          ) : runId || sessionId ? (
            <>
              {invalidLink ? (
                <Alert
                  type='error'
                  message={financialText('financial.the_report_link_is_incomplete_upload_again_or_use_a_complete_link')}
                />
              ) : (
                <>
                  {activeRun?.status === 'failed' ? (
                    <Alert
                      type='error'
                      message={financialText('financial.analysis_incomplete')}
                      description={activeRun.error || financialText('financial.please_retry_the_analysis')}
                    />
                  ) : (
                    !error && (
                      <Space>
                        <Spin />
                        <span>
                          {stageLabels[activeRun?.stage || 'queued'] || financialText('financial.loading_task')}
                        </span>
                      </Space>
                    )
                  )}
                  <Typography.Paragraph type='secondary'>
                    {financialText('financial.the_task_runs_in_the_background_keep_this_link_to_return_after_refre')}
                  </Typography.Paragraph>
                  {activeRun?.status === 'failed' && (
                    <Button loading={busy} onClick={() => void submit(activeRun)}>
                      {financialText('financial.reanalyze')}
                    </Button>
                  )}
                </>
              )}
              <Button onClick={startNew} disabled={busy}>
                {financialText('financial.analyze_another_report')}
              </Button>
            </>
          ) : (
            <>
              <Typography.Paragraph>
                {financialText('financial.upload_text_based_chinese_annual_report_pdfs_choose_single_report_an')}
              </Typography.Paragraph>
              <label>
                {financialText('financial.analysis_mode')}{' '}
                <Select
                  aria-label={financialText('financial.analysis_mode')}
                  value={mode}
                  disabled={busy}
                  onChange={value => {
                    setMode(value);
                    attempt.current = null;
                  }}
                  options={[
                    { value: 'report', label: financialText('financial.single_report') },
                    { value: 'peer', label: financialText('financial.compare_companies_in_the_same_year') },
                    { value: 'trend', label: financialText('financial.compare_years_for_one_company') },
                  ]}
                />
              </label>
              <label>
                {financialText('financial.select_annual_report_pdfs')}
                <input
                  className='block mt-3'
                  type='file'
                  accept='.pdf,application/pdf'
                  multiple={mode !== 'report'}
                  disabled={busy}
                  onChange={event => {
                    setFiles(Array.from(event.target.files || []));
                    setBaselineIndex(0);
                    attempt.current = null;
                    setError('');
                  }}
                />
              </label>
              {mode !== 'report' && files.length > 0 && (
                <label>
                  {financialText('financial.baseline_report')}{' '}
                  <Select
                    aria-label={financialText('financial.baseline_report')}
                    value={baselineIndex}
                    disabled={busy}
                    onChange={value => {
                      setBaselineIndex(value);
                      attempt.current = null;
                    }}
                    options={files.map((file, index) => ({ value: index, label: file.name }))}
                  />
                </label>
              )}
              <Button type='primary' loading={busy} disabled={!files.length} onClick={() => void submit()}>
                {busy
                  ? financialText('financial.uploading_and_creating_task')
                  : financialText('financial.start_analysis')}
              </Button>
              <ReportHistory
                load={listRuns}
                onOpen={previous => {
                  attempt.current = null;
                  void router.push({
                    pathname: '/financial-analysis',
                    query: { run_id: previous.id, session_id: previous.session_id },
                  });
                }}
              />
            </>
          )}
          {error && (
            <Alert
              type='error'
              message={error}
              action={
                runId && sessionId ? (
                  <Button onClick={() => setRetry(value => value + 1)}>{financialText('financial.reload')}</Button>
                ) : undefined
              }
            />
          )}
        </Space>
      </Card>
    </main>
  );
};
export default FinancialAnalysisRoute;
