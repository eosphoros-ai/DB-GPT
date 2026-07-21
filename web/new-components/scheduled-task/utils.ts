/**
 * 定时任务相关的共享工具函数
 */

import i18n from '@/app/i18n';

/** 将 cron 表达式转为友好描述 */
export function cronToLabel(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
  const weekKeyMap: Record<string, string> = {
    '0': 'scheduled.cron.sun',
    '1': 'scheduled.cron.mon',
    '2': 'scheduled.cron.tue',
    '3': 'scheduled.cron.wed',
    '4': 'scheduled.cron.thu',
    '5': 'scheduled.cron.fri',
    '6': 'scheduled.cron.sat',
    '7': 'scheduled.cron.sun',
  };
  if (hour === '*' && dayOfMonth === '*' && dayOfWeek === '*') {
    return i18n.t('scheduled.cron.labelHourly', { minute });
  }
  const time = `${hour}:${String(minute).padStart(2, '0')}`;
  if (dayOfMonth === '*' && dayOfWeek === '*') {
    return i18n.t('scheduled.cron.labelDaily', { time });
  }
  if (dayOfMonth === '*' && dayOfWeek !== '*') {
    const weekday = weekKeyMap[dayOfWeek] ? i18n.t(weekKeyMap[dayOfWeek]) : dayOfWeek;
    return i18n.t('scheduled.cron.labelWeekly', { weekday, time });
  }
  if (dayOfWeek === '*' && dayOfMonth !== '*') {
    return i18n.t('scheduled.cron.labelMonthly', { day: dayOfMonth, time });
  }
  return cron;
}
