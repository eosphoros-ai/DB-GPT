import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DashboardRefreshFrequencyInput, {
  buildDashboardIntervalCron,
  describeDashboardScheduleCron,
  parseDashboardRefreshFrequency,
} from './DashboardRefreshFrequencyInput';

describe('DashboardRefreshFrequencyInput', () => {
  it('round-trips supported preset and custom frequencies', () => {
    expect(parseDashboardRefreshFrequency('*/5 * * * *').mode).toBe('every-5-minutes');
    expect(parseDashboardRefreshFrequency('*/2 * * * *')).toMatchObject({
      mode: 'custom',
      count: 2,
      unit: 'minute',
    });
    expect(parseDashboardRefreshFrequency('0 */3 * * *')).toMatchObject({
      mode: 'custom',
      count: 3,
      unit: 'hour',
    });
    expect(buildDashboardIntervalCron(15, 'minute')).toBe('*/15 * * * *');
    expect(buildDashboardIntervalCron(2, 'day')).toBe('0 0 */2 * *');
    expect(describeDashboardScheduleCron('0 6 * * *')).toBe('每天 06:00');
  });

  it('shows one unified selector with the actual scheduler limit', () => {
    render(<DashboardRefreshFrequencyInput value='*/5 * * * *' onChange={vi.fn()} />);

    expect(screen.getByText('每 5 分钟')).toBeTruthy();
    expect(screen.getByText(/最短 1 分钟/)).toBeTruthy();
  });

  it('preserves an unsupported legacy cron until the user chooses a replacement', () => {
    render(<DashboardRefreshFrequencyInput value='0 8 * * 1' onChange={vi.fn()} />);
    expect(screen.getByText(/当前会原样保留/)).toBeTruthy();
    expect(screen.getByText(/现有计划/)).toBeTruthy();
  });
});
