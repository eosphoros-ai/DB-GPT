import { uploadFiles } from '@/modules/session-files/api';
import { Alert, Button, Card, Space, Spin, Typography } from 'antd';
import { useRouter } from 'next/router';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import FinancialAnalysisPage from './FinancialAnalysisPage';
import ReportHistory from './ReportHistory';
import type { FinancialRunStatus } from './api';
import {
  askQuestion,
  createExport,
  createRun,
  downloadExport,
  downloadSource,
  getReport,
  getRun,
  getSourcePage,
  listExports,
  listRuns,
  requestError,
} from './api';
import type { ReportData, ReportExportAccess, ReportQuestionAccess, SourcePreviewAccess } from './types';

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
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const attempt = useRef<{ sessionId: string; fileId: string; requestId: string; retryOf?: string } | null>(null);
  const [error, setError] = useState('');
  const [run, setRun] = useState<FinancialRunStatus | null>(null);
  const [data, setData] = useState<ReportData | null>(null);
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
          const report = await getReport(sessionId, runId, controller.signal);
          if (!controller.signal.aborted) {
            setData(report);
            setLoadedScope(`${sessionId}:${runId}`);
            setError('');
            if (report.analysis?.status === 'running') timer = setTimeout(poll, 1500);
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
  }, [router.isReady, runId, sessionId, retry]);

  const submit = async (previous?: FinancialRunStatus) => {
    if (busyRef.current || (!file && !previous)) return;
    busyRef.current = true;
    setBusy(true);
    setError('');
    try {
      if (previous && attempt.current?.retryOf !== previous.id) {
        attempt.current = {
          sessionId: previous.session_id,
          fileId: previous.file_id,
          requestId: crypto.randomUUID(),
          retryOf: previous.id,
        };
      } else if (!attempt.current) {
        const nextSession = `financial-${crypto.randomUUID()}`;
        const uploaded = await uploadFiles({ sessionId: nextSession, files: [file!] });
        if (!uploaded[0]) throw new Error('文件上传失败');
        attempt.current = { sessionId: nextSession, fileId: uploaded[0].file_id, requestId: crypto.randomUUID() };
      }
      const next = attempt.current!;
      const created = await createRun(next.sessionId, next.fileId, next.requestId);
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
    setFile(null);
    setError('');
    void router.push('/financial-analysis');
  };
  const activeRun = run?.id === runId && run.session_id === sessionId ? run : null;
  if (data && loadedScope === `${sessionId}:${runId}` && data.report.run.id === runId)
    return (
      <FinancialAnalysisPage
        data={data}
        onNewReport={startNew}
        sourceAccess={sourceAccess}
        questionAccess={questionAccess}
        exportAccess={exportAccess}
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
                上传中文文本型年度报告 PDF，提取财务数据并查看计算过程与来源。自动提取结果需要核对。
              </Typography.Paragraph>
              <label>
                选择年度报告 PDF
                <input
                  className='block mt-3'
                  type='file'
                  accept='.pdf,application/pdf'
                  disabled={busy}
                  onChange={event => {
                    setFile(event.target.files?.[0] || null);
                    attempt.current = null;
                    setError('');
                  }}
                />
              </label>
              <Button type='primary' loading={busy} disabled={!file} onClick={() => void submit()}>
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
