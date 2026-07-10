/**
 * 定时任务相关的共享工具函数
 */

/** 将 cron 表达式转为友好中文描述 */
export function cronToLabel(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
  const weekMap: Record<string, string> = {
    '0': '周日',
    '1': '周一',
    '2': '周二',
    '3': '周三',
    '4': '周四',
    '5': '周五',
    '6': '周六',
    '7': '周日',
  };
  if (hour === '*' && dayOfMonth === '*' && dayOfWeek === '*') {
    return `每小时第 ${minute} 分钟`;
  }
  if (dayOfMonth === '*' && dayOfWeek === '*') {
    return `每天 ${hour}:${String(minute).padStart(2, '0')}`;
  }
  if (dayOfMonth === '*' && dayOfWeek !== '*') {
    return `每${weekMap[dayOfWeek] ?? `周${dayOfWeek}`} ${hour}:${String(minute).padStart(2, '0')}`;
  }
  if (dayOfWeek === '*' && dayOfMonth !== '*') {
    return `每月 ${dayOfMonth} 号 ${hour}:${String(minute).padStart(2, '0')}`;
  }
  return cron;
}
