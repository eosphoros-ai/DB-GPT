import { Button, List, Space, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import type { FinancialRunHistory, FinancialRunStatus } from './api';
import { financialText, useFinancialLocale } from './i18n';

const statusText = (run: FinancialRunStatus) => {
  if (run.lifecycle?.publicationStatus === 'published') return financialText('financial.report_generated');
  if (run.analysis_status === 'running') return financialText('financial.data_ready_analyzing');
  if (run.analysis_status === 'partial') return financialText('financial.partial_analysis');
  if (run.analysis_status === 'failed') return financialText('financial.data_available_analysis_incomplete_2');
  return {
    pending: financialText('financial.queued'),
    running: financialText('financial.processing_2'),
    failed: financialText('financial.processing_failed'),
    completed: financialText('financial.completed'),
  }[run.status];
};

const ReportHistory: React.FC<{
  load: (page: number, signal: AbortSignal) => Promise<FinancialRunHistory>;
  onOpen: (run: FinancialRunStatus) => void;
}> = ({ load, onOpen }) => {
  useFinancialLocale();
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<FinancialRunHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setResult(null);
    load(page, controller.signal)
      .then(value => {
        if (!controller.signal.aborted) setResult(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(financialText('financial.failed_to_load_history_please_retry'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [load, page, attempt]);
  return (
    <section aria-label={financialText('financial.report_history')}>
      <Typography.Title level={4}>{financialText('financial.report_history')}</Typography.Title>
      {error ? (
        <Space>
          <span>{error}</span>
          <Button onClick={() => setAttempt(value => value + 1)}>{financialText('financial.retry')}</Button>
        </Space>
      ) : (
        <List
          loading={loading}
          dataSource={result?.items || []}
          locale={{ emptyText: financialText('financial.no_saved_reports') }}
          renderItem={run => (
            <List.Item
              actions={[
                <Button key='open' type='link' onClick={() => onOpen(run)}>
                  {run.report_ready ? financialText('financial.open_report') : financialText('financial.view_task')}
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={run.title || financialText('financial.financial_analysis_task')}
                description={financialText('financial.valuevalue_value', {
                  value1: run.fiscal_period ? financialText('financial.value', { value1: run.fiscal_period }) : '',
                  value2: statusText(run),
                  value3: new Date(run.created_at).toLocaleString(),
                })}
              />
            </List.Item>
          )}
        />
      )}
      <Space>
        <Button disabled={loading || page === 1} onClick={() => setPage(value => value - 1)}>
          {financialText('financial.previous_page')}
        </Button>
        <span>
          {financialText('financial.page_2')}
          {page} {financialText('financial.page')}
          {result ? financialText('financial.value_records', { value1: result.total }) : ''}
        </span>
        <Button
          disabled={loading || !result || page * result.page_size >= result.total}
          onClick={() => setPage(value => value + 1)}
        >
          {financialText('financial.next_page')}
        </Button>
        <Button disabled={loading} onClick={() => setAttempt(value => value + 1)}>
          {financialText('financial.refresh')}
        </Button>
      </Space>
    </section>
  );
};
export default ReportHistory;
