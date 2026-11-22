import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import ExecutionProcessPanel from './ExecutionProcessPanel';
import FinancialAnalysisRoute from './FinancialAnalysisRoute';
import type FinancialReportView from './FinancialReportView';
import { ReportDataProvider } from './ReportDataContext';
import { syntheticComparison } from './comparison/synthetic-fixture';
import { financialText } from './i18n';

const { getRun, getReport, resumeComparison, retryComparisonTopic, router } = vi.hoisted(() => ({
  getRun: vi.fn(),
  getReport: vi.fn(),
  resumeComparison: vi.fn(),
  retryComparisonTopic: vi.fn(),
  router: {
    isReady: true,
    query: { session_id: 'scope', run_id: '12345678-1234-4234-8234-123456789012' },
    push: vi.fn(),
    replace: vi.fn(),
  },
}));

vi.mock('next/router', () => ({ useRouter: () => router }));
vi.mock('@/modules/session-files/api', () => ({ uploadFiles: vi.fn() }));
vi.mock('./api', async importOriginal => ({
  ...(await importOriginal<typeof import('./api')>()),
  getRun,
  getReport,
  resumeComparison,
  retryComparisonTopic,
}));
vi.mock('./FinancialReportView', () => ({
  default: ({ data, analysisActions, onTopicRetry }: ComponentProps<typeof FinancialReportView>) => (
    <ReportDataProvider data={data}>
      <h1>{data.report.title}</h1>
      <button onClick={() => onTopicRetry?.('profitability')}>Retry topic</button>
      <ExecutionProcessPanel onStepSelect={() => {}} analysisActions={analysisActions} />
    </ReportDataProvider>
  ),
}));

beforeEach(() => {
  const data = syntheticComparison();
  data.steps = [
    {
      id: 'extract',
      order: 1,
      type: 'read',
      title: 'Extract',
      detail: '',
      status: 'completed',
      capability: 'existing',
    },
  ];
  getReport.mockResolvedValue(data);
  getRun.mockResolvedValue({
    id: data.report.run.id,
    session_id: 'scope',
    mode: 'comparison',
    status: 'completed',
    stage: 'completed',
    report_ready: true,
  });
});

it.each(['topic', 'files'])(
  'shows a failed comparison %s retry and reloads without discarding the report',
  async action => {
    const failure = `${action} retry failed`;
    retryComparisonTopic.mockRejectedValue(new Error(failure));
    resumeComparison.mockRejectedValue(new Error(failure));
    render(<FinancialAnalysisRoute />);
    const title = syntheticComparison().report.title;
    await screen.findByRole('heading', { name: title });
    fireEvent.click(
      screen.getByRole('button', {
        name: action === 'topic' ? 'Retry topic' : financialText('financial.resume_or_retry_incomplete_files'),
      }),
    );
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(failure);
    expect(screen.getByRole('heading', { name: title })).toBeTruthy();
    const data = syntheticComparison();
    if (action === 'topic') {
      expect(retryComparisonTopic).toHaveBeenCalledWith('scope', data.report.run.id, data.revision, 'profitability');
      expect(resumeComparison).not.toHaveBeenCalled();
    } else {
      expect(resumeComparison).toHaveBeenCalledWith('scope', data.report.run.id, data.revision);
      expect(retryComparisonTopic).not.toHaveBeenCalled();
    }
    fireEvent.click(screen.getByRole('button', { name: financialText('financial.reload') }));
    await waitFor(() => expect(getReport).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('heading', { name: title })).toBeTruthy();
  },
);
