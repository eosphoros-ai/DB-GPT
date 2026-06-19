import { Input, Radio, Select, Space, TimePicker, Typography } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Text } = Typography;

type Preset = 'hourly' | 'daily' | 'weekly' | 'monthly' | 'custom';

interface CronInputProps {
  value: string;
  onChange: (cron: string) => void;
}

// Weekday options — labelKey is an i18n key resolved at render time; value is
// the cron day-of-week number (0 = Sunday). Kept as a module constant since
// the values never change; only the displayed label is locale-dependent.
const WEEKDAYS = [
  { value: '1', labelKey: 'scheduled.cron.mon' },
  { value: '2', labelKey: 'scheduled.cron.tue' },
  { value: '3', labelKey: 'scheduled.cron.wed' },
  { value: '4', labelKey: 'scheduled.cron.thu' },
  { value: '5', labelKey: 'scheduled.cron.fri' },
  { value: '6', labelKey: 'scheduled.cron.sat' },
  { value: '0', labelKey: 'scheduled.cron.sun' },
];

/** Infer preset and params from a cron expression for external value initialization */
function parseCron(cron: string): {
  preset: Preset;
  time: Dayjs;
  weekday: string;
  day: number;
} {
  const parts = cron.trim().split(/\s+/);
  const defaults = {
    time: dayjs('09:00', 'HH:mm'),
    weekday: '1',
    day: 1,
  };

  if (parts.length !== 5) {
    return { preset: 'custom', ...defaults };
  }

  const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
  const min = Number(minute);
  const hr = Number(hour);
  const time = dayjs(`${String(hr).padStart(2, '0')}:${String(min).padStart(2, '0')}`, 'HH:mm');

  // hourly: N * * * *
  if (hour === '*' && dayOfMonth === '*' && dayOfWeek === '*') {
    return { preset: 'hourly', time: dayjs(`00:${String(min).padStart(2, '0')}`, 'HH:mm'), weekday: '1', day: 1 };
  }
  // daily: M H * * *
  if (dayOfMonth === '*' && dayOfWeek === '*' && !isNaN(hr)) {
    return { preset: 'daily', time, weekday: '1', day: 1 };
  }
  // weekly: M H * * W
  if (dayOfMonth === '*' && dayOfWeek !== '*' && !isNaN(hr)) {
    return { preset: 'weekly', time, weekday: dayOfWeek, day: 1 };
  }
  // monthly: M H D * *
  if (dayOfMonth !== '*' && dayOfWeek === '*' && !isNaN(hr)) {
    return { preset: 'monthly', time, weekday: '1', day: Number(dayOfMonth) };
  }

  return { preset: 'custom', ...defaults };
}

/** Build a cron expression */
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

const CronInput: React.FC<CronInputProps> = ({ value, onChange }) => {
  const { t } = useTranslation();
  // Use a lazy initializer to parse initial state from value on mount.
  // Drawer's destroyOnClose remounts this component on each open; if internal state
  // were initialized with fixed defaults (daily/09:00), and the mounted value equals
  // the previous leftover value (prevValueRef comparison skips parse), the buildCron
  // effect below would backfill defaults and overwrite the correct cron with "daily at 9:00".
  // Aligning with value on mount prevents that backfill.
  const [preset, setPreset] = useState<Preset>(() => parseCron(value || '0 9 * * *').preset);
  const [time, setTime] = useState<Dayjs>(() => parseCron(value || '0 9 * * *').time);
  const [weekday, setWeekday] = useState(() => parseCron(value || '0 9 * * *').weekday);
  const [day, setDay] = useState(() => parseCron(value || '0 9 * * *').day);
  const [custom, setCustom] = useState(value || '0 9 * * *');

  // Sync internal state when external value changes (e.g. editing a different task)
  const prevValueRef = React.useRef(value);
  useEffect(() => {
    if (value !== prevValueRef.current) {
      prevValueRef.current = value;
      const parsed = parseCron(value || '0 9 * * *');
      setPreset(parsed.preset);
      setTime(parsed.time);
      setWeekday(parsed.weekday);
      setDay(parsed.day);
      setCustom(value || '0 9 * * *');
    }
  }, [value]);

  useEffect(() => {
    const cron = buildCron(preset, time, weekday, day, custom);
    if (cron !== value) {
      onChange(cron);
    }
  }, [preset, time, weekday, day, custom]);

  const previewError = useMemo(() => {
    if (preset !== 'custom') return null;
    const parts = custom.trim().split(/\s+/);
    if (parts.length !== 5) return t('scheduled.cron.invalidParts');
    return null;
  }, [preset, custom, t]);

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
      <Radio.Group value={preset} onChange={e => setPreset(e.target.value)}>
        <Radio value='hourly'>{t('scheduled.cron.hourly')}</Radio>
        <Radio value='daily'>{t('scheduled.cron.daily')}</Radio>
        <Radio value='weekly'>{t('scheduled.cron.weekly')}</Radio>
        <Radio value='monthly'>{t('scheduled.cron.monthly')}</Radio>
        <Radio value='custom'>{t('scheduled.cron.custom')}</Radio>
      </Radio.Group>

      {preset !== 'custom' && (
        <Space>
          {preset === 'weekly' && (
            <Select value={weekday} style={{ width: 100 }} options={weekdayOptions} onChange={setWeekday} />
          )}
          {preset === 'monthly' && (
            <Select
              value={String(day)}
              style={{ width: 100 }}
              options={monthDayOptions}
              onChange={v => setDay(Number(v))}
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
              onChange={v => setTime(dayjs(`00:${String(v).padStart(2, '0')}`, 'HH:mm'))}
            />
          ) : (
            <TimePicker value={time} format='HH:mm' onChange={v => v && setTime(v)} allowClear={false} />
          )}
        </Space>
      )}

      {preset === 'custom' && (
        <Input
          value={custom}
          onChange={e => setCustom(e.target.value)}
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
