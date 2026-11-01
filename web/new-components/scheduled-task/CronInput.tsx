import { Input, Radio, Select, Space, TimePicker, Typography } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Text } = Typography;

type Preset = 'hourly' | 'daily' | 'weekly' | 'monthly' | 'custom';

interface CronInputProps {
  value?: string;
  onChange?: (cron: string) => void;
}

// Named weekdays avoid Unix/APScheduler's different numeric weekday origins.
const WEEKDAYS = [
  { value: 'mon', labelKey: 'scheduled.cron.mon' },
  { value: 'tue', labelKey: 'scheduled.cron.tue' },
  { value: 'wed', labelKey: 'scheduled.cron.wed' },
  { value: 'thu', labelKey: 'scheduled.cron.thu' },
  { value: 'fri', labelKey: 'scheduled.cron.fri' },
  { value: 'sat', labelKey: 'scheduled.cron.sat' },
  { value: 'sun', labelKey: 'scheduled.cron.sun' },
] as const;

/** 从 cron 表达式反推 preset 和参数，用于初始化时同步外部 value */
function parseCron(cron: string): {
  preset: Preset;
  time: Dayjs;
  weekday: string;
  day: number;
} {
  const parts = cron.trim().split(/\s+/);
  const defaults = {
    time: dayjs().hour(9).minute(0).second(0).millisecond(0),
    weekday: 'mon',
    day: 1,
  };

  if (parts.length !== 5) {
    return { preset: 'custom', ...defaults };
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
  const min = Number(minute);
  const hr = Number(hour);
  if (month !== '*' || !/^\d+$/.test(minute) || min < 0 || min > 59) {
    return { preset: 'custom', ...defaults };
  }
  const time = defaults.time.hour(hour === '*' ? 0 : hr).minute(min);

  // hourly: N * * * *
  if (hour === '*' && dayOfMonth === '*' && dayOfWeek === '*') {
    return { preset: 'hourly', time, weekday: 'mon', day: 1 };
  }
  if (!/^\d+$/.test(hour) || hr < 0 || hr > 23) return { preset: 'custom', ...defaults };
  // daily: M H * * *
  if (dayOfMonth === '*' && dayOfWeek === '*' && !isNaN(hr)) {
    return { preset: 'daily', time, weekday: 'mon', day: 1 };
  }
  // weekly: M H * * W
  const weekday = /^[0-6]$/.test(dayOfWeek) ? WEEKDAYS[Number(dayOfWeek)].value : dayOfWeek.toLowerCase();
  if (dayOfMonth === '*' && WEEKDAYS.some(item => item.value === weekday)) {
    return { preset: 'weekly', time, weekday, day: 1 };
  }
  // monthly: M H D * *
  if (/^\d+$/.test(dayOfMonth) && Number(dayOfMonth) >= 1 && Number(dayOfMonth) <= 31 && dayOfWeek === '*') {
    return { preset: 'monthly', time, weekday: 'mon', day: Number(dayOfMonth) };
  }

  return { preset: 'custom', ...defaults };
}

/** 组装 cron 表达式 */
function buildCron(preset: Preset, time: Dayjs, weekday: string, day: number, custom: string): string {
  switch (preset) {
    case 'hourly':
      return `${time.minute()} * * * *`;
    case 'daily':
      return `${time.minute()} ${time.hour()} * * *`;
    case 'weekly':
      return `${time.minute()} ${time.hour()} * * ${weekday}`;
    case 'monthly':
      return `${time.minute()} ${time.hour()} ${day} * *`;
    case 'custom':
      return custom;
  }
}

const CronInput: React.FC<CronInputProps> = ({ value = '0 9 * * *', onChange }) => {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => ({ value, ...parseCron(value), custom: value }));
  // A different task supplies a new authoritative expression. Never emit a
  // default or rewrite custom cron merely because the editor was opened.
  let current = draft;
  if (draft.value !== value) {
    current = { value, ...parseCron(value), custom: value };
    setDraft(current);
  }
  const { preset, time, weekday, day, custom } = current;
  const change = (patch: Partial<Omit<typeof draft, 'value'>>) => {
    const next = { ...current, ...patch };
    const cron = buildCron(next.preset, next.time, next.weekday, next.day, next.custom);
    setDraft({ ...next, value: cron });
    onChange?.(cron);
  };

  const previewError =
    preset === 'custom' && custom.trim().split(/\s+/).length !== 5 ? t('scheduled.cron.invalidParts') : null;

  // Locale-aware option lists (labels resolved via i18n; values are cron parts).
  const weekdayOptions = useMemo(() => WEEKDAYS.map(w => ({ value: w.value, label: t(w.labelKey) })), [t]);
  const monthDayOptions = useMemo(
    () =>
      Array.from({ length: 31 }, (_, i) => ({
        value: String(i + 1),
        label: t('scheduled.cron.dayOfMonth', { day: i + 1 }),
      })),
    [t],
  );

  const displayCron = preset === 'custom' ? custom : buildCron(preset, time, weekday, day, custom);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <Radio.Group value={preset} onChange={e => change({ preset: e.target.value })}>
        <Radio value='hourly'>{t('scheduled.cron.hourly')}</Radio>
        <Radio value='daily'>{t('scheduled.cron.daily')}</Radio>
        <Radio value='weekly'>{t('scheduled.cron.weekly')}</Radio>
        <Radio value='monthly'>{t('scheduled.cron.monthly')}</Radio>
        <Radio value='custom'>{t('scheduled.cron.custom')}</Radio>
      </Radio.Group>

      {preset !== 'custom' && (
        <Space>
          {preset === 'weekly' && (
            <Select
              aria-label='执行星期'
              value={weekday}
              style={{ width: 100 }}
              options={weekdayOptions}
              onChange={weekday => change({ weekday })}
            />
          )}
          {preset === 'monthly' && (
            <Select
              value={String(day)}
              style={{ width: 100 }}
              options={monthDayOptions}
              onChange={v => change({ day: Number(v) })}
            />
          )}
          {preset === 'hourly' ? (
            <Select
              value={String(time.minute())}
              style={{ width: 120 }}
              options={Array.from({ length: 60 }, (_, i) => ({
                value: String(i),
                label: t('scheduled.cron.minuteOfHour', { minute: i }),
              }))}
              onChange={v => change({ time: time.hour(0).minute(Number(v)) })}
            />
          ) : (
            <TimePicker
              aria-label='执行时间'
              value={time}
              format='HH:mm'
              onChange={v => v && change({ time: v })}
              allowClear={false}
            />
          )}
        </Space>
      )}

      {preset === 'custom' && (
        <Input
          value={custom}
          aria-label='Cron 表达式'
          onChange={e => change({ custom: e.target.value })}
          placeholder={t('scheduled.cron.customPlaceholder')}
          status={previewError ? 'error' : undefined}
        />
      )}

      {previewError ? (
        <Text type='danger'>{previewError}</Text>
      ) : (
        <Text type='secondary'>{t('scheduled.cron.preview', { cron: displayCron })}</Text>
      )}
    </div>
  );
};

export default CronInput;
