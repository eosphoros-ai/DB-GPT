import { dashboardText as dt, useDashboardTranslation } from '@/new-components/dashboard/dashboard-i18n';
import { Alert, Input, InputNumber, Select, Space, Typography } from 'antd';

const { Text } = Typography;

type FrequencyMode =
  | 'every-minute'
  | 'every-5-minutes'
  | 'every-10-minutes'
  | 'every-30-minutes'
  | 'hourly'
  | 'daily'
  | 'custom'
  | 'legacy';
type IntervalUnit = 'minute' | 'hour' | 'day';

interface ParsedFrequency {
  mode: FrequencyMode;
  count: number;
  unit: IntervalUnit;
  time: string;
}

interface DashboardRefreshFrequencyInputProps {
  value: string;
  onChange: (cron: string) => void;
}

const presetCron: Partial<Record<FrequencyMode, string>> = {
  'every-minute': '* * * * *',
  'every-5-minutes': '*/5 * * * *',
  'every-10-minutes': '*/10 * * * *',
  'every-30-minutes': '*/30 * * * *',
  hourly: '0 * * * *',
};

export const parseDashboardRefreshFrequency = (cron: string): ParsedFrequency => {
  const normalized = cron.trim().replace(/\s+/g, ' ');
  const preset = Object.entries(presetCron).find(([, value]) => value === normalized)?.[0] as FrequencyMode | undefined;
  if (preset) return { mode: preset, count: 5, unit: 'minute', time: '06:00' };

  const daily = normalized.match(/^(\d{1,2}) (\d{1,2}) \* \* \*$/);
  if (daily) {
    const minute = Number(daily[1]);
    const hour = Number(daily[2]);
    if (minute <= 59 && hour <= 23) {
      return {
        mode: 'daily',
        count: 1,
        unit: 'day',
        time: `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`,
      };
    }
  }

  const minuteInterval = normalized.match(/^\*\/(\d{1,2}) \* \* \* \*$/);
  if (minuteInterval && Number(minuteInterval[1]) >= 1 && Number(minuteInterval[1]) <= 59) {
    return { mode: 'custom', count: Number(minuteInterval[1]), unit: 'minute', time: '06:00' };
  }
  const hourInterval = normalized.match(/^0 \*\/(\d{1,2}) \* \* \*$/);
  if (hourInterval && Number(hourInterval[1]) >= 1 && Number(hourInterval[1]) <= 23) {
    return { mode: 'custom', count: Number(hourInterval[1]), unit: 'hour', time: '06:00' };
  }
  const dayInterval = normalized.match(/^0 0 \*\/(\d{1,2}) \* \*$/);
  if (dayInterval && Number(dayInterval[1]) >= 1 && Number(dayInterval[1]) <= 28) {
    return { mode: 'custom', count: Number(dayInterval[1]), unit: 'day', time: '06:00' };
  }
  return { mode: 'legacy', count: 5, unit: 'minute', time: '06:00' };
};

export const buildDashboardIntervalCron = (count: number, unit: IntervalUnit) => {
  const safeCount = Math.max(1, Math.floor(Number.isFinite(count) ? count : 1));
  if (unit === 'minute') return safeCount === 1 ? '* * * * *' : `*/${Math.min(59, safeCount)} * * * *`;
  if (unit === 'hour') return safeCount === 1 ? '0 * * * *' : `0 */${Math.min(23, safeCount)} * * *`;
  return safeCount === 1 ? '0 0 * * *' : `0 0 */${Math.min(28, safeCount)} * *`;
};

export const describeDashboardScheduleCron = (cron: string) => {
  const parsed = parseDashboardRefreshFrequency(cron);
  const labels: Partial<Record<FrequencyMode, string>> = {
    'every-minute': dt('每 1 分钟'),
    'every-5-minutes': dt('每 5 分钟'),
    'every-10-minutes': dt('每 10 分钟'),
    'every-30-minutes': dt('每 30 分钟'),
    hourly: dt('每 1 小时'),
  };
  if (labels[parsed.mode]) return labels[parsed.mode] as string;
  if (parsed.mode === 'daily') return dt('每天 {{value0}}', { value0: parsed.time });
  if (parsed.mode === 'custom') {
    const unit = parsed.unit === 'minute' ? dt('分钟') : parsed.unit === 'hour' ? dt('小时') : dt('天');
    return dt('每 {{value0}} {{value1}}', { value0: parsed.count, value1: unit });
  }
  return dt('现有计划（{{value0}}）', { value0: cron });
};

export default function DashboardRefreshFrequencyInput({ value, onChange }: DashboardRefreshFrequencyInputProps) {
  useDashboardTranslation();
  const parsed = parseDashboardRefreshFrequency(value);

  const selectMode = (mode: FrequencyMode) => {
    if (mode === 'daily') onChange('0 6 * * *');
    // Start from a non-preset value so the custom controls remain visible
    // after the controlled value is parsed on the next render.
    else if (mode === 'custom') onChange('*/2 * * * *');
    else if (presetCron[mode]) onChange(presetCron[mode] as string);
  };

  const updateDailyTime = (time: string) => {
    const [hour, minute] = time.split(':').map(Number);
    if (Number.isInteger(hour) && Number.isInteger(minute)) onChange(`${minute} ${hour} * * *`);
  };

  return (
    <div className='space-y-3' data-testid='dashboard-refresh-frequency-input'>
      <Select
        className='w-full'
        aria-label={dt('刷新频率')}
        value={parsed.mode}
        options={[
          { value: 'every-minute', label: dt('每 1 分钟') },
          { value: 'every-5-minutes', label: dt('每 5 分钟') },
          { value: 'every-10-minutes', label: dt('每 10 分钟') },
          { value: 'every-30-minutes', label: dt('每 30 分钟') },
          { value: 'hourly', label: dt('每 1 小时') },
          { value: 'daily', label: dt('每天固定时间') },
          { value: 'custom', label: dt('自定义间隔') },
          ...(parsed.mode === 'legacy'
            ? [{ value: 'legacy', label: dt('保留现有频率：{{value0}}', { value0: value }) }]
            : []),
        ]}
        onChange={selectMode}
      />

      {parsed.mode === 'daily' && (
        <label className='block text-xs text-gray-500'>
          {dt('每天执行时间')}
          <Input
            aria-label={dt('每天执行时间')}
            type='time'
            value={parsed.time}
            onChange={event => updateDailyTime(event.target.value)}
          />
        </label>
      )}

      {parsed.mode === 'custom' && (
        <Space.Compact block>
          <InputNumber
            className='w-full'
            aria-label={dt('自定义间隔数值')}
            min={1}
            max={parsed.unit === 'minute' ? 59 : parsed.unit === 'hour' ? 23 : 28}
            precision={0}
            value={parsed.count}
            onChange={count => onChange(buildDashboardIntervalCron(Number(count || 1), parsed.unit))}
          />
          <Select
            className='w-28'
            aria-label={dt('自定义间隔单位')}
            value={parsed.unit}
            options={[
              { value: 'minute', label: dt('分钟') },
              { value: 'hour', label: dt('小时') },
              { value: 'day', label: dt('天') },
            ]}
            onChange={unit => onChange(buildDashboardIntervalCron(parsed.count, unit))}
          />
        </Space.Compact>
      )}

      {parsed.mode === 'legacy' && (
        <Alert type='warning' showIcon message={dt('这是旧计划的表达式，当前会原样保留；选择上方任一频率即可替换。')} />
      )}
      <Text type='secondary'>
        {dt('当前：')}
        {describeDashboardScheduleCron(value)}
        {dt('。最短 1 分钟；后台调度器不支持秒级执行。')}
      </Text>
    </div>
  );
}
