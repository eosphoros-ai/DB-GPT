import {
  dashboardDateLocale,
  dashboardText as dt,
  useDashboardTranslation,
} from '@/new-components/dashboard/dashboard-i18n';
import { DashboardAnomalyEvidence as DashboardAnomalyEvidenceType } from '@/types/dashboard';
import { CheckCircleOutlined, QuestionCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { Tag } from 'antd';

interface DashboardAnomalyEvidenceProps {
  evidence: DashboardAnomalyEvidenceType[];
}

const baselineLabels = {
  get previous_period() {
    return dt('上一周期');
  },
  get rolling_average() {
    return dt('滚动平均');
  },
  get target_value() {
    return dt('业务目标值');
  },
} as const;

const reasonLabels: Record<string, string> = {
  get query_error() {
    return dt('查询执行失败');
  },
  get value_field_missing() {
    return dt('指标字段不存在');
  },
  get time_field_missing() {
    return dt('时间字段不存在');
  },
  get no_data() {
    return dt('没有数据');
  },
  get current_value_missing() {
    return dt('当前值缺失或不是数值');
  },
  get baseline_value_missing() {
    return dt('基线值缺失或不是数值');
  },
  get target_value_missing() {
    return dt('尚未配置业务目标值');
  },
  get insufficient_data() {
    return dt('样本不足');
  },
  get zero_denominator() {
    return dt('基线为零，无法计算变化比例');
  },
  get threshold_missing() {
    return dt('尚未配置阈值');
  },
  get detector_error() {
    return dt('检测程序无法完成计算');
  },
};

const formatNumber = (value?: number | null) =>
  value == null
    ? '—'
    : new Intl.NumberFormat(dashboardDateLocale(), {
        maximumFractionDigits: 4,
      }).format(value);

const formatRatio = (value?: number | null) =>
  value == null
    ? '—'
    : new Intl.NumberFormat(dashboardDateLocale(), {
        style: 'percent',
        maximumFractionDigits: 2,
      }).format(value);

const formatThreshold = (item: DashboardAnomalyEvidenceType) => {
  if (item.threshold.value == null) return dt('未配置');
  return item.threshold.mode === 'relative_change'
    ? formatRatio(item.threshold.value)
    : formatNumber(item.threshold.value);
};

const formatRange = (start?: string | null, end?: string | null) => {
  if (!start && !end) return '—';
  if (!end || start === end) return start || end || '—';
  return dt('{{value0}} 至 {{value1}}', { value0: start || '—', value1: end });
};

const StatusTag = ({ status }: Pick<DashboardAnomalyEvidenceType, 'status'>) => {
  useDashboardTranslation();
  if (status === 'anomaly') {
    return (
      <Tag color='error' icon={<WarningOutlined />}>
        {dt('异常')}
      </Tag>
    );
  }
  if (status === 'normal') {
    return (
      <Tag color='success' icon={<CheckCircleOutlined />}>
        {dt('正常')}
      </Tag>
    );
  }
  return (
    <Tag color='warning' icon={<QuestionCircleOutlined />}>
      {dt('无法判断')}
    </Tag>
  );
};

export default function DashboardAnomalyEvidence({ evidence }: DashboardAnomalyEvidenceProps) {
  useDashboardTranslation();
  if (!evidence.length) return null;
  const anomalyCount = evidence.filter(item => item.status === 'anomaly').length;
  const indeterminateCount = evidence.filter(item => item.status === 'indeterminate').length;
  const summary = anomalyCount
    ? dt('检测到 {{value0}} 条异常', { value0: anomalyCount })
    : indeterminateCount
      ? dt('{{value0}} 条规则无法判断', { value0: indeterminateCount })
      : dt('{{value0}} 条规则均正常', { value0: evidence.length });

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
        <span className='ml-auto text-gray-400'>{dt('展开判断依据')}</span>
      </summary>
      <div className='mt-3 space-y-3'>
        {evidence.map(item => (
          <section key={item.rule_id} className='rounded border border-black/5 bg-white/70 p-3 dark:bg-black/10'>
            <div className='mb-2 flex items-center gap-2'>
              <StatusTag status={item.status} />
              <strong>{item.rule_label}</strong>
              <span className='text-gray-400'>
                {dt('基线：')}
                {baselineLabels[item.baseline]}
              </span>
            </div>
            {item.status === 'indeterminate' && (
              <div className='mb-2 rounded bg-amber-100/70 px-2 py-1 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200'>
                {dt('无法判断：')}
                {reasonLabels[item.reason_code || ''] || item.reason || dt('证据不完整')}
              </div>
            )}
            <dl className='grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-gray-600 dark:text-gray-300'>
              <dt>{dt('当前值')}</dt>
              <dd>{formatNumber(item.current_value)}</dd>
              <dt>{dt('基线值')}</dt>
              <dd>{formatNumber(item.baseline_value)}</dd>
              <dt>{dt('绝对变化')}</dt>
              <dd>{formatNumber(item.absolute_change)}</dd>
              <dt>{dt('变化比例')}</dt>
              <dd>{formatRatio(item.change_ratio)}</dd>
              <dt>{dt('阈值')}</dt>
              <dd>{formatThreshold(item)}</dd>
              <dt>{dt('当前时间范围')}</dt>
              <dd>{formatRange(item.comparison_time_range.current_start, item.comparison_time_range.current_end)}</dd>
              <dt>{dt('基线时间范围')}</dt>
              <dd>{formatRange(item.comparison_time_range.baseline_start, item.comparison_time_range.baseline_end)}</dd>
              <dt>{dt('样本量')}</dt>
              <dd>{item.sample_size}</dd>
              <dt>{dt('命中的规则')}</dt>
              <dd className='break-all font-mono'>{item.matched_rule}</dd>
            </dl>
          </section>
        ))}
      </div>
    </details>
  );
}
