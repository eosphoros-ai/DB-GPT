import { ChatContext } from '@/app/chat-context';
import {
  apiInterceptors,
  getObservabilityAgents,
  getObservabilityHealth,
  getObservabilityMetrics,
  getObservabilityModelUsage,
  searchObservabilityTraces,
  type TraceSummary,
} from '@/client/api';
import { Chart } from '@berryv/g2-react';
import { useRequest } from 'ahooks';
import { Card, Empty, Spin, Table, Tag } from 'antd';
import moment from 'moment';
import { useRouter } from 'next/router';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

function Kpi({ title, value, hint }: { title: string; value: React.ReactNode; hint?: string }) {
  return (
    <Card size='small' className='flex-1'>
      <div className='text-xs text-gray-400'>{title}</div>
      <div className='text-2xl font-semibold text-gray-800 dark:text-gray-100 mt-1'>{value}</div>
      {hint && <div className='text-xs text-gray-400 mt-1'>{hint}</div>}
    </Card>
  );
}

export default function ObservabilityOverviewPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const { mode } = useContext(ChatContext);
  const now = useMemo(() => new Date(), []);
  const start = useMemo(() => new Date(now.getTime() - 24 * 3600 * 1000), [now]);
  const startIso = start.toISOString();
  const endIso = now.toISOString();

  const { data: agentsTuple } = useRequest(async () =>
    apiInterceptors(getObservabilityAgents({ time_from: startIso, time_to: endIso })),
  );
  const agents = agentsTuple?.[1] || [];

  const { loading: healthLoading, data: healthTuple } = useRequest(async () =>
    apiInterceptors(getObservabilityHealth({ time_from: startIso, time_to: endIso })),
  );
  const health = healthTuple?.[1] || [];

  const { loading: tracesLoading, data: tracesTuple } = useRequest(async () =>
    apiInterceptors(searchObservabilityTraces({ limit: 10, min_span_count: 5 })),
  );
  const traces = tracesTuple?.[1] || [];

  const { loading: metricsLoading, data: metricsTuple } = useRequest(async () =>
    apiInterceptors(
      getObservabilityMetrics({
        metric: 'event_volume',
        start: startIso,
        end: endIso,
        granularity: 'hour',
      }),
    ),
  );
  const metrics = metricsTuple?.[1];
  const chartData = (metrics?.points || []).map(p => ({
    name: moment(p.timestamp).format('HH:mm'),
    value: p.value,
  }));

  // Tokens (24h): sum of token_rate across buckets
  const { loading: tokensLoading, data: tokensTuple } = useRequest(async () =>
    apiInterceptors(
      getObservabilityMetrics({
        metric: 'token_rate',
        start: startIso,
        end: endIso,
        granularity: 'hour',
      }),
    ),
  );
  const tokenPoints = tokensTuple?.[1]?.points || [];
  const totalTokens = tokenPoints.reduce((s, p) => s + p.value, 0);

  // Latency P95 (24h): max p95 across buckets is the headline; trend chart below
  const { loading: latencyLoading, data: latencyTuple } = useRequest(async () =>
    apiInterceptors(
      getObservabilityMetrics({
        metric: 'latency_p95',
        start: startIso,
        end: endIso,
        granularity: 'hour',
      }),
    ),
  );
  const latencyPoints = latencyTuple?.[1]?.points || [];
  const maxLatency = latencyPoints.reduce((m, p) => Math.max(m, p.value), 0);
  const latencyChartData = latencyPoints.map(p => ({
    name: moment(p.timestamp).format('HH:mm'),
    value: Math.round(p.value),
  }));

  // AntCC-style token breakdown: per-model aggregates from /models/usage.
  const { loading: modelUsageLoading, data: modelUsageTuple } = useRequest(async () =>
    apiInterceptors(getObservabilityModelUsage({ time_from: startIso, time_to: endIso })),
  );
  const modelUsage = (modelUsageTuple?.[1] || []).filter(m => m.total_tokens > 0 || m.call_count > 0);
  const tokenInput = modelUsage.reduce((s, m) => s + m.prompt_tokens, 0);
  const tokenOutput = modelUsage.reduce((s, m) => s + m.completion_tokens, 0);
  const tokenCacheHit = modelUsage.reduce((s, m) => s + m.cache_hit_tokens, 0);
  const tokenCacheMiss = modelUsage.reduce((s, m) => s + m.cache_miss_tokens, 0);
  const tokenGrand = modelUsage.reduce((s, m) => s + m.total_tokens, 0);

  const totalEvents = health.reduce((s, h) => s + h.event_count, 0);
  const errorCount = health.reduce((s, h) => s + h.error_rate * h.event_count, 0);
  const errorRate = totalEvents ? (errorCount / totalEvents) * 100 : 0;

  const traceColumns = [
    {
      title: t('observability_trace_id') || 'Trace',
      dataIndex: 'trace_id',
      render: (id: string) => (
        <a className='text-blue-500' onClick={() => router.push(`/observability/traces/${id}`)}>
          {id.slice(0, 12)}…
        </a>
      ),
    },
    { title: t('observability_operation') || 'Operation', dataIndex: 'root_operation_name' },
    {
      title: t('observability_status') || 'Status',
      dataIndex: 'status',
      render: (s: string) => <Tag color={s === 'ERROR' ? 'red' : 'green'}>{s || 'OK'}</Tag>,
    },
    {
      title: t('observability_duration') || 'Duration',
      dataIndex: 'duration_ms',
      render: (d?: number) => (d != null ? `${(d / 1000).toFixed(2)}s` : '-'),
    },
    { title: t('observability_spans') || 'Spans', dataIndex: 'span_count' },
    {
      title: t('observability_time') || 'Time',
      dataIndex: 'start_time',
      render: (s?: string) => (s ? moment(s).fromNow() : '-'),
    },
  ];

  return (
    <div className='flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light overflow-y-auto'>
      <div className='px-6 py-5 border-b border-gray-100 dark:border-gray-800'>
        <h1 className='text-xl font-semibold text-gray-800 dark:text-gray-100'>
          {t('observability_overview') || 'Observability · Overview'}
        </h1>
        <div className='text-xs text-gray-400 mt-1'>{t('observability_last_24h') || 'Last 24 hours'}</div>
      </div>

      <div className='px-6 py-4 space-y-4'>
        <div className='flex gap-4 flex-wrap'>
          <Kpi title={t('observability_agents') || 'Agents'} value={agents.length} />
          <Kpi title={t('observability_events') || 'Events (24h)'} value={totalEvents} />
          <Kpi
            title={t('observability_tokens') || 'Tokens (24h)'}
            value={totalTokens.toLocaleString()}
            hint={tokensLoading ? '…' : undefined}
          />
          <Kpi
            title={t('observability_latency') || 'Latency P95'}
            value={maxLatency ? `${(maxLatency / 1000).toFixed(2)}s` : '-'}
            hint={latencyLoading ? '…' : undefined}
          />
          <Kpi title={t('observability_error_rate') || 'Error rate'} value={`${errorRate.toFixed(1)}%`} />
        </div>

        {/* AntCC-style token breakdown panel */}
        <Card size='small' title={t('observability_token_total') || 'Token usage (input + cache + output)'}>
          <Spin spinning={modelUsageLoading}>
            <div className='flex gap-4 flex-wrap'>
              <div className='flex-1 min-w-[150px] rounded-lg bg-gray-50 dark:bg-gray-800/60 p-4'>
                <div className='text-xs text-gray-400'>{t('observability_input_tokens') || 'Input Tokens'}</div>
                <div className='text-2xl font-semibold mt-1 text-gray-800 dark:text-gray-100'>
                  {tokenInput.toLocaleString()}
                </div>
              </div>
              <div className='flex-1 min-w-[150px] rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4'>
                <div className='text-xs text-gray-400'>{t('observability_output_tokens') || 'Output Tokens'}</div>
                <div className='text-2xl font-semibold mt-1 text-gray-800 dark:text-gray-100'>
                  {tokenOutput.toLocaleString()}
                </div>
              </div>
              <div className='flex-1 min-w-[150px] rounded-lg bg-emerald-50 dark:bg-emerald-900/20 p-4'>
                <div className='text-xs text-gray-400'>{t('observability_cache_hit_tokens') || 'Cache-hit Tokens'}</div>
                <div className='text-2xl font-semibold mt-1 text-gray-800 dark:text-gray-100'>
                  {tokenCacheHit.toLocaleString()}
                </div>
              </div>
              <div className='flex-1 min-w-[150px] rounded-lg bg-violet-50 dark:bg-violet-900/20 p-4'>
                <div className='text-xs text-gray-400'>
                  {t('observability_cache_miss_tokens') || 'Cache-miss Tokens'}
                </div>
                <div className='text-2xl font-semibold mt-1 text-gray-800 dark:text-gray-100'>
                  {tokenCacheMiss.toLocaleString()}
                </div>
              </div>
            </div>
            <div className='text-xs text-gray-400 mt-3'>
              {t('observability_token_total') || 'Token usage'}: <b>{tokenGrand.toLocaleString()}</b>
            </div>
          </Spin>
        </Card>

        <Card size='small' title={t('observability_model_usage') || 'Model usage'}>
          <Spin spinning={modelUsageLoading}>
            <Table
              size='small'
              pagination={false}
              dataSource={modelUsage}
              rowKey='model_name'
              columns={[
                { title: t('observability_model') || 'Model', dataIndex: 'model_name' },
                { title: t('observability_calls') || 'Calls', dataIndex: 'call_count' },
                {
                  title: t('observability_input_tokens') || 'Input',
                  dataIndex: 'prompt_tokens',
                  render: (v: number) => v.toLocaleString(),
                },
                {
                  title: t('observability_output_tokens') || 'Output',
                  dataIndex: 'completion_tokens',
                  render: (v: number) => v.toLocaleString(),
                },
                {
                  title: 'Total',
                  dataIndex: 'total_tokens',
                  render: (v: number) => v.toLocaleString(),
                },
                {
                  title: t('observability_avg_latency') || 'Avg latency',
                  dataIndex: 'avg_duration_ms',
                  render: (v?: number) => (v != null ? `${(v / 1000).toFixed(2)}s` : '-'),
                },
              ]}
            />
          </Spin>
        </Card>

        <div className='flex gap-4'>
          <Card size='small' className='flex-1' title={t('observability_event_volume') || 'Event volume (24h)'}>
            <Spin spinning={metricsLoading}>
              {chartData.length === 0 ? (
                <Empty />
              ) : (
                <div className='h-[280px]'>
                  <Chart
                    style={{ height: '100%' }}
                    options={{
                      autoFit: true,
                      theme: mode,
                      type: 'line',
                      data: chartData,
                      encode: { x: 'name', y: 'value', shape: 'smooth' },
                      axis: { x: { labelAutoRotate: false, title: false }, y: { title: false } },
                    }}
                  />
                </div>
              )}
            </Spin>
          </Card>
          <Card size='small' className='flex-1' title={t('observability_latency_trend') || 'Latency trend (P95)'}>
            <Spin spinning={latencyLoading}>
              {latencyChartData.length === 0 ? (
                <Empty />
              ) : (
                <div className='h-[280px]'>
                  <Chart
                    style={{ height: '100%' }}
                    options={{
                      autoFit: true,
                      theme: mode,
                      type: 'line',
                      data: latencyChartData,
                      encode: { x: 'name', y: 'value', shape: 'smooth' },
                      axis: {
                        x: { labelAutoRotate: false, title: false },
                        y: { title: false },
                      },
                    }}
                  />
                </div>
              )}
            </Spin>
          </Card>
        </div>

        <Card size='small' title={t('observability_agent_health') || 'Agent health'}>
          <Spin spinning={healthLoading}>
            <Table
              size='small'
              pagination={false}
              dataSource={health}
              rowKey='agent_name'
              columns={[
                { title: t('observability_agent') || 'Agent', dataIndex: 'agent_name' },
                { title: t('observability_events') || 'Events', dataIndex: 'event_count' },
                {
                  title: t('observability_error_rate') || 'Error rate',
                  dataIndex: 'error_rate',
                  render: (r: number) => `${(r * 100).toFixed(1)}%`,
                },
              ]}
            />
          </Spin>
        </Card>

        <Card size='small' title={t('observability_recent_traces') || 'Recent traces'}>
          <Spin spinning={tracesLoading}>
            <Table
              size='small'
              pagination={false}
              dataSource={traces as TraceSummary[]}
              rowKey='trace_id'
              columns={traceColumns as any}
            />
          </Spin>
        </Card>
      </div>
    </div>
  );
}
