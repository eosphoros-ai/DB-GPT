import type { DashboardFilter } from '@/types/dashboard';
import dayjs from 'dayjs';
import { describe, expect, it } from 'vitest';
import {
  initialDashboardFilterValues,
  refreshDashboardFilterValues,
  scheduleDashboardFilterValues,
} from './dashboard-relative-date';

const filters: DashboardFilter[] = [
  {
    id: 'dates',
    type: 'date_range',
    label: '日期',
    field: 'sale_date',
    default: ['2020-01-01', '2020-01-31'],
    options: [],
    relative_date: { anchor: 'today', start_offset_days: -6, end_offset_days: 0 },
  },
  {
    id: 'region',
    type: 'select',
    label: '区域',
    field: 'region',
    default: 'all',
    options: [],
  },
];

describe('dashboard relative date values', () => {
  it('resolves rolling dates from the execution day', () => {
    expect(initialDashboardFilterValues(filters, dayjs('2026-08-30'))).toEqual({
      dates: ['2026-08-24', '2026-08-30'],
      region: 'all',
    });
    expect(
      refreshDashboardFilterValues(
        filters,
        { dates: ['2026-01-01', '2026-01-07'], region: 'north' },
        dayjs('2026-09-02'),
      ),
    ).toEqual({ dates: ['2026-08-27', '2026-09-02'], region: 'north' });
  });

  it('omits relative dates from schedules so the server recomputes them', () => {
    expect(scheduleDashboardFilterValues(filters, { dates: ['stale', 'stale'], region: 'south' })).toEqual({
      region: 'south',
    });
  });
});
