import { Button, List, Space, Typography } from 'antd';
import React, { useEffect, useState } from 'react';
import type { FinancialRunHistory, FinancialRunStatus } from './api';

const statusText = (run: FinancialRunStatus) => {
  if (run.lifecycle?.publicationStatus === 'published') return '报告已生成';
  if (run.analysis_status === 'running') return '数据已就绪，分析中';
  if (run.analysis_status === 'partial') return '部分分析';
  if (run.analysis_status === 'failed') return '数据可用，分析未完成';
  return { pending: '等待处理', running: '处理中', failed: '处理失败', completed: '已完成' }[run.status];
};

const ReportHistory: React.FC<{
  load: (page: number, signal: AbortSignal) => Promise<FinancialRunHistory>;
  onOpen: (run: FinancialRunStatus) => void;
}> = ({ load, onOpen }) => {
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
        if (!controller.signal.aborted) setError('历史记录读取失败，请重试。');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [load, page, attempt]);
  return (
    <section aria-label='历史报告'>
      <Typography.Title level={4}>历史报告</Typography.Title>
      {error ? (
        <Space>
          <span>{error}</span>
          <Button onClick={() => setAttempt(value => value + 1)}>重试</Button>
        </Space>
      ) : (
        <List
          loading={loading}
          dataSource={result?.items || []}
          locale={{ emptyText: '暂无历史报告' }}
          renderItem={run => (
            <List.Item
              actions={[
                <Button key='open' type='link' onClick={() => onOpen(run)}>
                  {run.report_ready ? '打开报告' : '查看任务'}
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={run.title || '财报分析任务'}
                description={`${run.fiscal_period ? `${run.fiscal_period} 年 · ` : ''}${statusText(run)} · ${new Date(run.created_at).toLocaleString()}`}
              />
            </List.Item>
          )}
        />
      )}
      <Space>
        <Button disabled={loading || page === 1} onClick={() => setPage(value => value - 1)}>
          上一页
        </Button>
        <span>
          第 {page} 页{result ? ` · 共 ${result.total} 条` : ''}
        </span>
        <Button
          disabled={loading || !result || page * result.page_size >= result.total}
          onClick={() => setPage(value => value + 1)}
        >
          下一页
        </Button>
        <Button disabled={loading} onClick={() => setAttempt(value => value + 1)}>
          刷新
        </Button>
      </Space>
    </section>
  );
};
export default ReportHistory;
