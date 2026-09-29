import { DashboardAnomalyEvidence as DashboardAnomalyEvidenceType } from '@/types/dashboard';
import { CheckCircleOutlined, QuestionCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { Tag } from 'antd';

interface DashboardAnomalyEvidenceProps {
  evidence: DashboardAnomalyEvidenceType[];
}

const baselineLabels = {
  previous_period: '上一周期',
  rolling_average: '滚动平均',
  target_value: '业务目标值',
} as const;

const reasonLabels: Record<string, string> = {
  query_error: '查询执行失败',
  value_field_missing: '指标字段不存在',
  time_field_missing: '时间字段不存在',
  no_data: '没有数据',
  current_value_missing: '当前值缺失或不是数值',
  baseline_value_missing: '基线值缺失或不是数值',
  target_value_missing: '尚未配置业务目标值',
  insufficient_data: '样本不足',
  zero_denominator: '基线为零，无法计算变化比例',
  threshold_missing: '尚未配置阈值',
  detector_error: '检测程序无法完成计算',
};

const formatNumber = (value?: number | null) =>
  value == null
    ? '—'
    : new Intl.NumberFormat('zh-CN', {
        maximumFractionDigits: 4,
      }).format(value);

const formatRatio = (value?: number | null) =>
  value == null
    ? '—'
    : new Intl.NumberFormat('zh-CN', {
        style: 'percent',
        maximumFractionDigits: 2,
      }).format(value);

const formatThreshold = (item: DashboardAnomalyEvidenceType) => {
  if (item.threshold.value == null) return '未配置';
  return item.threshold.mode === 'relative_change'
    ? formatRatio(item.threshold.value)
    : formatNumber(item.threshold.value);
};

const formatRange = (start?: string | null, end?: string | null) => {
  if (!start && !end) return '—';
  if (!end || start === end) return start || end || '—';
  return `${start || '—'} 至 ${end}`;
};

const StatusTag = ({ status }: Pick<DashboardAnomalyEvidenceType, 'status'>) => {
  if (status === 'anomaly') {
    return (
      <Tag color='error' icon={<WarningOutlined />}>
        异常
      </Tag>
    );
  }
  if (status === 'normal') {
    return (
      <Tag color='success' icon={<CheckCircleOutlined />}>
        正常
      </Tag>
    );
  }
  return (
    <Tag color='warning' icon={<QuestionCircleOutlined />}>
      无法判断
    </Tag>
  );
};

export default function DashboardAnomalyEvidence({ evidence }: DashboardAnomalyEvidenceProps) {
  if (!evidence.length) return null;
  const anomalyCount = evidence.filter(item => item.status === 'anomaly').length;
  const indeterminateCount = evidence.filter(item => item.status === 'indeterminate').length;
  const summary = anomalyCount
    ? `检测到 ${anomalyCount} 条异常`
    : indeterminateCount
      ? `${indeterminateCount} 条规则无法判断`
      : `${evidence.length} 条规则均正常`;

  return (
    <details
      className={`mx-3 mb-2 rounded-md border px-3 py-2 text-xs ${
        anomalyCount
          ? 'border-red-200 bg-red-50/80 dark:border-red-900 dark:bg-red-950/20'
          : indeterminateCount
            ? 'border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/20'
            : 'border-green-200 bg-green-50/60 dark:border-green-900 dark:bg-green-950/20'
      }`}
      data-testid='dashboard-anomaly-evidence'
    >
      <summary className='flex cursor-pointer list-none items-center gap-2 font-medium'>
        <StatusTag status={anomalyCount ? 'anomaly' : indeterminateCount ? 'indeterminate' : 'normal'} />
        <span>{summary}</span>
        <span className='ml-auto text-gray-400'>展开判断依据</span>
      </summary>
      <div className='mt-3 space-y-3'>
        {evidence.map(item => (
          <section key={item.rule_id} className='rounded border border-black/5 bg-white/70 p-3 dark:bg-black/10'>
            <div className='mb-2 flex items-center gap-2'>
              <StatusTag status={item.status} />
              <strong>{item.rule_label}</strong>
              <span className='text-gray-400'>基线：{baselineLabels[item.baseline]}</span>
            </div>
            {item.status === 'indeterminate' && (
              <div className='mb-2 rounded bg-amber-100/70 px-2 py-1 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200'>
                无法判断：{reasonLabels[item.reason_code || ''] || item.reason || '证据不完整'}
              </div>
            )}
            <dl className='grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-gray-600 dark:text-gray-300'>
              <dt>当前值</dt>
              <dd>{formatNumber(item.current_value)}</dd>
              <dt>基线值</dt>
              <dd>{formatNumber(item.baseline_value)}</dd>
              <dt>绝对变化</dt>
              <dd>{formatNumber(item.absolute_change)}</dd>
              <dt>变化比例</dt>
              <dd>{formatRatio(item.change_ratio)}</dd>
              <dt>阈值</dt>
              <dd>{formatThreshold(item)}</dd>
              <dt>当前时间范围</dt>
              <dd>{formatRange(item.comparison_time_range.current_start, item.comparison_time_range.current_end)}</dd>
              <dt>基线时间范围</dt>
              <dd>{formatRange(item.comparison_time_range.baseline_start, item.comparison_time_range.baseline_end)}</dd>
              <dt>样本量</dt>
              <dd>{item.sample_size}</dd>
              <dt>命中的规则</dt>
              <dd className='break-all font-mono'>{item.matched_rule}</dd>
            </dl>
          </section>
        ))}
      </div>
    </details>
  );
}
