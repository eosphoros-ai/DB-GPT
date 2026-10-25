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
import type {
  ComparisonAccess,
  FinancialReportData,
  ReportExportAccess,
  ReportQuestionAccess,
  ReportRevisionAccess,
  SourcePreviewAccess,
} from './types';

const stageLabels: Record<string, string> = {
  queued: '等待分析',
  extract: '正在读取 PDF 并提取财务事实',
  calculate: '正在计算财务指标',
  save: '正在保存报告',
  analyze: '财务数据已就绪，正在生成模型分析',
  completed: '分析完成',
};

const FinancialAnalysisRoute: React.FC = () => {
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
          requestId: crypto.randomUUID(),
          retryOf: previous.id,
        };
      } else if (!attempt.current) {
        const nextSession = `financial-${crypto.randomUUID()}`;
        if ((mode === 'report' && files.length !== 1) || (mode !== 'report' && (files.length < 2 || files.length > 5)))
          throw new Error('单报告需一份 PDF，对比需两到五份 PDF。');
        const uploaded = await uploadFiles({ sessionId: nextSession, files });
        if (uploaded.length !== files.length) throw new Error('文件未全部上传成功');
        attempt.current = {
          sessionId: nextSession,
          fileIds: uploaded.map(item => item.file_id),
          requestId: crypto.randomUUID(),
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
          <Typography.Title level={2}>财报分析</Typography.Title>
          {!router.isReady ? (
            <Spin />
          ) : runId || sessionId ? (
            <>
              {invalidLink ? (
                <Alert type='error' message='报告链接不完整，请重新上传或使用完整链接。' />
              ) : (
                <>
                  {activeRun?.status === 'failed' ? (
                    <Alert type='error' message='分析未完成' description={activeRun.error || '请重新分析'} />
                  ) : (
                    !error && (
                      <Space>
                        <Spin />
                        <span>{stageLabels[activeRun?.stage || 'queued'] || '正在读取任务'}</span>
                      </Space>
                    )
                  )}
                  <Typography.Paragraph type='secondary'>
                    任务会在后台处理；保留此页面链接，刷新后可继续查看。
                  </Typography.Paragraph>
                  {activeRun?.status === 'failed' && (
                    <Button loading={busy} onClick={() => void submit(activeRun)}>
                      重新分析
                    </Button>
                  )}
                </>
              )}
              <Button onClick={startNew} disabled={busy}>
                分析另一份报告
              </Button>
            </>
          ) : (
            <>
              <Typography.Paragraph>
                上传中文文本型年度报告 PDF，选择单报告或明确的对比任务，查看计算过程与来源。自动提取结果需要核对。
              </Typography.Paragraph>
              <label>
                分析方式{' '}
                <Select
                  aria-label='分析方式'
                  value={mode}
                  disabled={busy}
                  onChange={value => {
                    setMode(value);
                    attempt.current = null;
                  }}
                  options={[
                    { value: 'report', label: '单报告分析' },
                    { value: 'peer', label: '同年度多公司对比' },
                    { value: 'trend', label: '同公司跨年对比' },
                  ]}
                />
              </label>
              <label>
                选择年度报告 PDF
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
                  基准报告{' '}
                  <Select
                    aria-label='基准报告'
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
                {busy ? '正在上传并创建任务' : '开始分析'}
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
                runId && sessionId ? <Button onClick={() => setRetry(value => value + 1)}>重新读取</Button> : undefined
              }
            />
          )}
        </Space>
      </Card>
    </main>
  );
};
export default FinancialAnalysisRoute;
