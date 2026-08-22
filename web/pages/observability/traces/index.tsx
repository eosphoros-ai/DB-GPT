import { apiInterceptors, searchObservabilityTraces } from '@/client/api';
import { useRequest } from 'ahooks';
import { Input, Pagination, Spin, Table, Tag } from 'antd';
import moment from 'moment';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

const PAGE_SIZE = 20;

export default function ObservabilityTracesPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string | undefined>();

  const { loading, data, run } = useRequest(
    async (p: number) =>
      apiInterceptors(
        searchObservabilityTraces({
          status,
          min_span_count: 5,
          limit: PAGE_SIZE,
          offset: (p - 1) * PAGE_SIZE,
        }),
      ),
    {
      defaultParams: [1],
      refreshDeps: [status],
    },
  );
  const traces = data?.[1] || [];
  const hasMore = traces.length === PAGE_SIZE;

  return (
    <div className='flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light'>
      <div className='flex items-center justify-between px-6 py-5 border-b border-gray-100 dark:border-gray-800'>
        <h1 className='text-xl font-semibold text-gray-800 dark:text-gray-100'>
          {t('observability_traces') || 'Observability · Traces'}
        </h1>
        <Input
          placeholder={t('observability_filter_status') || 'filter status: OK / ERROR'}
          allowClear
          className='w-[220px]'
          onChange={e => {
            const v = e.target.value?.trim().toUpperCase();
            setStatus(v && (v === 'OK' || v === 'ERROR') ? v : undefined);
            setPage(1);
          }}
        />
      </div>
      <div className='flex-1 overflow-y-auto px-6 py-4'>
        <Spin spinning={loading}>
          <Table
            size='small'
            pagination={false}
            dataSource={traces}
            rowKey='trace_id'
            onRow={record => ({
              onClick: () => router.push(`/observability/traces/${record.trace_id}`),
              style: { cursor: 'pointer' },
            })}
            columns={[
              {
                title: 'Trace',
                dataIndex: 'trace_id',
                render: (id: string) => <span className='text-blue-500'>{id.slice(0, 16)}…</span>,
              },
              { title: 'Operation', dataIndex: 'root_operation_name' },
              { title: 'Agent', dataIndex: 'agent_name' },
              {
                title: 'Status',
                dataIndex: 'status',
                render: (s: string) => <Tag color={s === 'ERROR' ? 'red' : 'green'}>{s || 'OK'}</Tag>,
              },
              {
                title: 'Duration',
                dataIndex: 'duration_ms',
                render: (d?: number) => (d != null ? `${(d / 1000).toFixed(2)}s` : '-'),
              },
              { title: 'Spans', dataIndex: 'span_count' },
              { title: 'Model', dataIndex: 'model_name' },
              {
                title: 'Time',
                dataIndex: 'start_time',
                render: (s?: string) => (s ? moment(s).fromNow() : '-'),
              },
            ]}
          />
        </Spin>
      </div>
      <div className='flex justify-end px-6 py-4 border-t border-gray-100 dark:border-gray-800'>
        <Pagination
          current={page}
          pageSize={PAGE_SIZE}
          total={page * PAGE_SIZE + (hasMore ? PAGE_SIZE : 0)}
          showSizeChanger={false}
          onChange={p => {
            setPage(p);
            run(p);
          }}
        />
      </div>
    </div>
  );
}
