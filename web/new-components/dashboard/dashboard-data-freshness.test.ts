import type { DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';
import { expect, test } from 'vitest';
import { dashboardDataThrough } from './dashboard-data-freshness';
const schema = {
  widgets: [
    {
      id: 'trend',
      query: {
        output_fields: [
          { name: 'order_date', type: 'date' },
          { name: 'amount', type: 'number' },
        ],
      },
    },
  ],
} as DashboardSchemaV1;
const snapshot = (rows: unknown[][]): DashboardSnapshot => ({
  dashboard_id: 'freshness-test',
  filters: {},
  refreshed_at: '2026-09-09T14:30:00',
  widgets: {
    trend: {
      widget_id: 'trend',
      columns: ['order_date', 'amount'],
      rows,
      row_count: rows.length,
      truncated: false,
      duration_ms: 0,
      refreshed_at: '2026-09-09T14:30:00',
    },
  },
});
test('business date stays historical despite a current query timestamp', () => {
  expect(
    dashboardDataThrough(
      schema,
      snapshot([
        ['2012-09-01', 4],
        ['2012-09-07', 6],
      ]),
    ),
  ).toBe('2012-09-07');
});
test('no dates, invalid dates and empty results do not invent a cutoff', () => {
  expect(
    dashboardDataThrough(
      schema,
      snapshot([
        ['2026-02-31', 4],
        [null, 5],
        ['123456', 6],
      ]),
    ),
  ).toBeNull();
  expect(dashboardDataThrough(schema, snapshot([]))).toBeNull();
});
test('monthly aggregation preserves month precision', () => {
  expect(
    dashboardDataThrough(
      schema,
      snapshot([
        ['2026-07', 4],
        ['2026-08', 5],
      ]),
    ),
  ).toBe('2026-08');
});
