import type { DashboardAnomalyRule, DashboardWidgetResult } from '@/types/dashboard';
import { DeleteOutlined, PlusOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { Alert, Button, Input, InputNumber, Select, Switch } from 'antd';

interface Props {
  rules: DashboardAnomalyRule[];
  fields: Array<{ value: string; label: string; type?: string }>;
  result?: DashboardWidgetResult;
  onChange: (rules: DashboardAnomalyRule[]) => void;
}
const baselines = [
  { value: 'previous_period', label: '上一周期' },
  { value: 'rolling_average', label: '最近几期平均值' },
  { value: 'target_value', label: '业务目标值' },
];
const directions = [
  { value: 'below', label: '下降达到' },
  { value: 'above', label: '上升达到' },
  { value: 'two_sided', label: '涨跌达到' },
];

export default function DashboardAnomalyRuleEditor({ rules, fields, result, onChange }: Props) {
  const update = (id: string, patch: Partial<DashboardAnomalyRule>) =>
    onChange(rules.map(rule => (rule.id === id ? { ...rule, ...patch } : rule)));
  const metricFields = fields.filter(field => !field.type || ['number', 'integer', 'unknown'].includes(field.type));
  const dateFields = fields.filter(
    field => /date|time/i.test(field.type || '') || /date|month|period|日期|时间/i.test(field.value),
  );
  const add = () =>
    onChange([
      ...rules,
      {
        id: `anomaly-rule-${Date.now().toString(36)}-${rules.length + 1}`,
        label: `异常规则 ${rules.length + 1}`,
        baseline: 'previous_period',
        value_field: (metricFields[0] || fields[0])?.value || '',
        time_field: dateFields[0]?.value || null,
        direction: 'below',
        threshold: { mode: 'relative_change', value: null },
        rolling_window: 3,
        target_value: null,
        min_samples: 2,
        enabled: true,
      },
    ]);
  return (
    <div className='space-y-3 rounded-lg border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-3'>
      <div className='flex flex-wrap items-center gap-2'>
        <SafetyCertificateOutlined />
        <strong className='flex-1 text-xs'>指标异常提醒</strong>
        <Button size='small' icon={<PlusOutlined />} onClick={add}>
          添加规则
        </Button>
      </div>
      <p className='text-xs leading-5 text-[var(--app-muted)]'>
        设定“指标相对基线上升或下降多少算异常”。刷新数据后显示结果与依据；AI 可解释依据，判定由程序执行。
      </p>
      {!rules.length && (
        <Alert type='info' showIcon message='尚未配置规则。例：销售额比上一天下降达到 20%，标记异常。' />
      )}
      {rules.map(rule => {
        const metricName = fields.find(field => field.value === rule.value_field)?.label || rule.value_field || '指标';
        const baseline = baselines.find(item => item.value === rule.baseline)?.label;
        const threshold =
          rule.threshold.value == null
            ? '待填阈值'
            : `${Number((rule.threshold.value * (rule.threshold.mode === 'relative_change' ? 100 : 1)).toFixed(6))}${rule.threshold.mode === 'relative_change' ? '%' : ''}`;
        const count = result?.rows.filter(row => {
          const i = result.columns.indexOf(rule.value_field);
          return i >= 0 && row[i] != null && row[i] !== '' && Number.isFinite(Number(row[i]));
        }).length;
        const needed = Math.max(
          rule.min_samples,
          rule.baseline === 'previous_period' ? 2 : rule.baseline === 'rolling_average' ? rule.rolling_window + 1 : 1,
        );
        return (
          <section
            key={rule.id}
            className='space-y-3 rounded border border-[var(--app-border)] bg-[var(--app-surface)] p-3'
          >
            <div className='flex items-center gap-2'>
              <Input
                size='small'
                aria-label={`${rule.label}名称`}
                value={rule.label}
                onChange={e => update(rule.id, { label: e.target.value })}
              />
              <Switch
                size='small'
                aria-label={`${rule.label}启用状态`}
                checked={rule.enabled}
                onChange={enabled => update(rule.id, { enabled })}
              />
              <Button
                size='small'
                type='text'
                danger
                aria-label={`删除 ${rule.label}`}
                icon={<DeleteOutlined />}
                onClick={() => onChange(rules.filter(item => item.id !== rule.id))}
              />
            </div>
            <p className='rounded bg-[var(--app-surface-muted)] p-2 text-xs leading-5' aria-label='规则含义'>
              当 {metricName} 比{baseline}
              {directions.find(item => item.value === rule.direction)?.label} {threshold}，标记异常。
            </p>
            <div className='grid grid-cols-2 gap-3 text-xs text-[var(--app-muted)]'>
              <label>
                监测指标
                <Select
                  className='mt-1 w-full'
                  size='small'
                  value={rule.value_field || undefined}
                  options={metricFields.length ? metricFields : fields}
                  onChange={value_field => update(rule.id, { value_field })}
                />
              </label>
              <label>
                比较基线
                <Select
                  className='mt-1 w-full'
                  size='small'
                  value={rule.baseline}
                  options={baselines}
                  onChange={baseline => update(rule.id, { baseline })}
                />
              </label>
              <label>
                变化方向
                <Select
                  className='mt-1 w-full'
                  size='small'
                  value={rule.direction}
                  options={directions}
                  onChange={direction => update(rule.id, { direction })}
                />
              </label>
              <label>
                {rule.threshold.mode === 'relative_change' ? '变化达到（%）' : '变化达到（绝对值）'}
                <InputNumber
                  className='mt-1 w-full'
                  size='small'
                  min={0}
                  aria-label={`${rule.label}阈值`}
                  placeholder='例如 20'
                  status={rule.enabled && rule.threshold.value == null ? 'warning' : undefined}
                  value={
                    rule.threshold.value == null
                      ? null
                      : rule.threshold.value * (rule.threshold.mode === 'relative_change' ? 100 : 1)
                  }
                  onChange={value =>
                    update(rule.id, {
                      threshold: {
                        ...rule.threshold,
                        value:
                          value == null ? null : Number(value) / (rule.threshold.mode === 'relative_change' ? 100 : 1),
                      },
                    })
                  }
                />
              </label>
              {rule.baseline === 'rolling_average' && (
                <label>
                  平均最近几期
                  <InputNumber
                    className='mt-1 w-full'
                    min={2}
                    max={100}
                    value={rule.rolling_window}
                    onChange={value => update(rule.id, { rolling_window: Number(value || 2) })}
                  />
                </label>
              )}
              {rule.baseline === 'target_value' && (
                <label>
                  目标值
                  <InputNumber
                    className='mt-1 w-full'
                    value={rule.target_value}
                    placeholder='必须配置'
                    onChange={target_value => update(rule.id, { target_value })}
                  />
                </label>
              )}
            </div>
            {rule.enabled && rule.threshold.value == null && (
              <Alert type='warning' showIcon message='请填写阈值后再判断异常，例如填 20 表示 20%。' />
            )}
            {rule.enabled && count != null && count < needed && (
              <Alert
                type='info'
                showIcon
                message={`当前有 ${count} 条有效数据，这项比较至少需要 ${needed} 条；请查询包含多个周期的数据。`}
              />
            )}
            <details className='text-xs text-[var(--app-muted)]'>
              <summary className='cursor-pointer'>高级设置 · 时间顺序、比较方式和样本量</summary>
              <div className='mt-3 grid grid-cols-2 gap-3'>
                <label className='col-span-2'>
                  时间字段
                  <Select
                    className='mt-1 w-full'
                    size='small'
                    allowClear
                    value={rule.time_field || undefined}
                    placeholder='使用查询结果的行顺序'
                    options={dateFields.length ? dateFields : fields}
                    onChange={time_field => update(rule.id, { time_field: time_field || null })}
                  />
                  <span className='mt-1 block leading-5'>
                    {rule.time_field
                      ? '按这个字段从旧到新比较；重复周期应先在查询中汇总。'
                      : '当前比较最后一行与前面的行，请确保查询按时间从旧到新排列。'}
                  </span>
                </label>
                <label>
                  比较方式
                  <Select
                    className='mt-1 w-full'
                    size='small'
                    value={rule.threshold.mode}
                    options={[
                      { value: 'relative_change', label: '百分比变化' },
                      { value: 'absolute_change', label: '绝对值变化' },
                    ]}
                    onChange={mode => update(rule.id, { threshold: { mode, value: null } })}
                  />
                </label>
                <label>
                  最少有效数据条数
                  <InputNumber
                    className='mt-1 w-full'
                    size='small'
                    min={1}
                    max={1000}
                    value={rule.min_samples}
                    onChange={value => update(rule.id, { min_samples: Number(value || 1) })}
                  />
                </label>
              </div>
            </details>
          </section>
        );
      })}
    </div>
  );
}
