import { DashboardFilter } from '@/types/dashboard';
import dayjs, { Dayjs } from 'dayjs';

export const resolveDashboardFilterValue = (
  filter: DashboardFilter,
  supplied: unknown,
  now: Dayjs = dayjs(),
): unknown => {
  if (supplied !== undefined && supplied !== null) return supplied;
  if (filter.type !== 'date_range' || !filter.relative_date) return filter.default;

  const anchor = now.startOf('day');
  return [
    anchor.add(filter.relative_date.start_offset_days, 'day').format('YYYY-MM-DD'),
    anchor.add(filter.relative_date.end_offset_days, 'day').format('YYYY-MM-DD'),
  ];
};

export const initialDashboardFilterValues = (
  filters: DashboardFilter[],
  now: Dayjs = dayjs(),
): Record<string, unknown> =>
  Object.fromEntries(filters.map(filter => [filter.id, resolveDashboardFilterValue(filter, undefined, now)]));

export const refreshDashboardFilterValues = (
  filters: DashboardFilter[],
  current: Record<string, unknown>,
  now: Dayjs = dayjs(),
): Record<string, unknown> =>
  Object.fromEntries(
    filters.map(filter => [
      filter.id,
      resolveDashboardFilterValue(filter, filter.relative_date ? undefined : current[filter.id], now),
    ]),
  );

export const scheduleDashboardFilterValues = (
  filters: DashboardFilter[],
  current: Record<string, unknown>,
): Record<string, unknown> =>
  Object.fromEntries(filters.filter(filter => !filter.relative_date).map(filter => [filter.id, current[filter.id]]));
