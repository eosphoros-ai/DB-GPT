/**
 * Shared utility functions for scheduled tasks
 */

/** Convert a cron expression to a friendly English description */
export function cronToLabel(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
  const weekMap: Record<string, string> = {
    '0': 'Sunday',
    '1': 'Monday',
    '2': 'Tuesday',
    '3': 'Wednesday',
    '4': 'Thursday',
    '5': 'Friday',
    '6': 'Saturday',
    '7': 'Sunday',
  };
  if (hour === '*' && dayOfMonth === '*' && dayOfWeek === '*') {
    return `At minute ${minute} of every hour`;
  }
  if (dayOfMonth === '*' && dayOfWeek === '*') {
    return `Daily at ${hour}:${String(minute).padStart(2, '0')}`;
  }
  if (dayOfMonth === '*' && dayOfWeek !== '*') {
    return `Every ${weekMap[dayOfWeek] ?? `week ${dayOfWeek}`} at ${hour}:${String(minute).padStart(2, '0')}`;
  }
  if (dayOfWeek === '*' && dayOfMonth !== '*') {
    return `Monthly on day ${dayOfMonth} at ${hour}:${String(minute).padStart(2, '0')}`;
  }
  return cron;
}
