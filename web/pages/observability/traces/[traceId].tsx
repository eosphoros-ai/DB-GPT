import { apiInterceptors, getObservabilityTrace, type SpanNode } from '@/client/api';
import { useRequest } from 'ahooks';
import { Card, Descriptions, Empty, Spin, Tag, Typography } from 'antd';
import moment from 'moment';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Text } = Typography;

function SpanRow({ node, depth = 0 }: { node: SpanNode; depth?: number }) {
  const [expanded, setExpanded] = useState(false);
  const isError = node.status === 'ERROR';
  const isLLM = (node.operation_name || '').includes('llm') || (node.operation_name || '').includes('LLM');
  const hasMeta = node.metadata && Object.keys(node.metadata).length > 0;
  return (
    <div>
      <div
        className='flex items-center gap-2 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-800 rounded cursor-pointer'
        style={{ paddingLeft: depth * 22 }}
        onClick={() => setExpanded(v => !v)}
      >
        {hasMeta ? (
          <span className='text-[10px] text-gray-400 select-none'>{expanded ? '▾' : '▸'}</span>
        ) : (
          <span className='w-3' />
        )}
        <Tag color={isError ? 'red' : isLLM ? 'blue' : 'default'}>{node.span_type || 'span'}</Tag>
        <Text className='text-sm text-gray-700 dark:text-gray-200' ellipsis={{ tooltip: node.operation_name }}>
          {node.operation_name || node.span_id}
        </Text>
        {node.model_name && <Tag color='geekblue'>{node.model_name}</Tag>}
        {node.tool_name && <Tag color='cyan'>{node.tool_name}</Tag>}
        {node.duration_ms != null && <span className='text-xs text-gray-400'>{node.duration_ms}ms</span>}
        {node.total_tokens != null && <span className='text-xs text-gray-400'>{node.total_tokens} tok</span>}
      </div>

      {expanded && (
        <div
          className='ml-4 mb-1 rounded bg-gray-50 dark:bg-gray-800/60 p-2 space-y-1'
          style={{ marginLeft: depth * 22 + 16 }}
        >
          <div className='font-mono text-[11px] text-gray-500'>
            span_id: <span className='text-gray-700 dark:text-gray-300'>{node.span_id}</span>
          </div>
          <div className='font-mono text-[11px] text-gray-500'>
            parent_span_id: <span className='text-gray-700 dark:text-gray-300'>{node.parent_span_id || '—'}</span>
          </div>
          {node.agent_name && (
            <div className='font-mono text-[11px] text-gray-500'>
              agent: <span className='text-gray-700 dark:text-gray-300'>{node.agent_name}</span>
            </div>
          )}
          {node.cost != null && (
            <div className='font-mono text-[11px] text-gray-500'>
              cost: <span className='text-gray-700 dark:text-gray-300'>${node.cost}</span>
            </div>
          )}
          {isError && node.error && (
            <div className='text-[11px] text-red-500'>
              error: {typeof node.error === 'string' ? node.error : JSON.stringify(node.error, null, 2)}
            </div>
          )}
          {hasMeta && (
            <details className='text-[11px]'>
              <summary className='cursor-pointer text-gray-400'>metadata</summary>
              <pre className='mt-1 font-mono text-gray-600 dark:text-gray-300 bg-white/60 dark:bg-black/20 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-60'>
                {JSON.stringify(node.metadata, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}

      {(node.children || []).map(child => (
        <SpanRow key={child.span_id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export default function TraceDetailPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const { traceId } = router.query;

  const { loading, data } = useRequest(
    async () => {
      if (!traceId) return [null, null] as const;
      return apiInterceptors(getObservabilityTrace(traceId as string));
    },
    { refreshDeps: [traceId] },
  );
  const trace = data?.[1];

  return (
    <div className='flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light overflow-y-auto'>
      <div className='px-6 py-5 border-b border-gray-100 dark:border-gray-800'>
        <h1 className='text-xl font-semibold text-gray-800 dark:text-gray-100'>
          {t('observability_trace') || 'Trace'}
        </h1>
        <div className='text-xs text-gray-400 mt-1 font-mono'>{traceId as string}</div>
      </div>
      <div className='px-6 py-4 space-y-4'>
        <Spin spinning={loading}>
          {!loading && !trace ? (
            <Empty description={t('observability_no_trace') || 'Trace not found'} />
          ) : trace ? (
            <>
              <Card size='small'>
                <Descriptions size='small' column={2}>
                  <Descriptions.Item label={t('observability_status') || 'Status'}>
                    <Tag color={trace.status === 'ERROR' ? 'red' : 'green'}>{trace.status || 'OK'}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('observability_spans') || 'Spans'}>{trace.span_count}</Descriptions.Item>
                  <Descriptions.Item label={t('observability_duration') || 'Duration'}>
                    {trace.duration_ms != null ? `${(trace.duration_ms / 1000).toFixed(2)}s` : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('observability_time') || 'Start'}>
                    {trace.start_time ? moment(trace.start_time).format('YYYY-MM-DD HH:mm:ss') : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('observability_conversation_id') || 'Conversation ID'} span={2}>
                    {trace.conversation_id ? (
                      <Text code copyable className='text-xs'>
                        {trace.conversation_id}
                      </Text>
                    ) : (
                      <span className='text-gray-400'>—</span>
                    )}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
              <Card size='small' title={t('observability_span_tree') || 'Span tree'}>
                {trace.root ? <SpanRow node={trace.root} /> : <Empty />}
              </Card>
            </>
          ) : null}
        </Spin>
      </div>
    </div>
  );
}
