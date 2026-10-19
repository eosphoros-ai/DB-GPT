import type { DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import {
  buildDashboardFilterFieldCandidates,
  buildDashboardFilterParameterCandidates,
  normalizeDashboardFilterParameter,
  recommendDashboardDateFilterParameters,
  recommendDashboardFilterParameter,
  sqlUsesNamedParameter,
} from './dashboard-filter-config';

const schema = {
  widgets: [
    {
      id: 'store-ranking',
      title: '门店排行',
      query: { output_fields: [{ name: 'Store' }, { name: 'sales' }] },
    },
  ],
} as DashboardSchemaV1;

const snapshot = {
  dashboard_id: 'filter-test',
  refreshed_at: '2026-09-09T14:30:00',
  filters: {},
  widgets: {
    'store-ranking': {
      widget_id: 'store-ranking',
      row_count: 3,
      truncated: false,
      duration_ms: 0,
      refreshed_at: '2026-09-09T14:30:00',
      columns: ['Store', 'sales'],
      rows: [
        [1, 20],
        [2, 10],
        [1, 5],
      ],
    },
  },
} satisfies DashboardSnapshot;

describe('dashboard filter configuration helpers', () => {
  it('discovers stable unique options from the current dashboard data', () => {
    const candidates = buildDashboardFilterFieldCandidates(schema, snapshot);
    expect(candidates.find(candidate => candidate.field === 'Store')?.options).toEqual([
      { label: '1', value: 1 },
      { label: '2', value: 2 },
    ]);
  });

  it('normalizes user-facing fields into safe named parameters', () => {
    expect(normalizeDashboardFilterParameter(' store ids ')).toBe('store_ids');
    expect(normalizeDashboardFilterParameter('门店')).toBe('filter_value');
  });

  it('recognizes real named parameters without confusing PostgreSQL casts', () => {
    expect(sqlUsesNamedParameter('SELECT * FROM sales WHERE store IN (:store_ids)', 'store_ids')).toBe(true);
    expect(sqlUsesNamedParameter('SELECT value::text FROM sales', 'text')).toBe(false);
    expect(sqlUsesNamedParameter('SELECT :store_ids_extra', 'store_ids')).toBe(false);
  });

  it('discovers SQL parameters and recommends the one matching the selected field', () => {
    schema.widgets[0].query.sql =
      'SELECT Store, SUM(sales) AS sales FROM sales WHERE Store IN (:store_ids) AND Date >= :start_date GROUP BY Store';
    const candidates = buildDashboardFilterParameterCandidates(schema);
    expect(candidates).toEqual(['start_date', 'store_ids']);
    expect(recommendDashboardFilterParameter('stores', 'Store', candidates)).toBe('store_ids');
  });

  it('discovers a complete date range without limiting the option list', () => {
    const dateSchema = {
      widgets: [
        {
          id: 'trend',
          title: '销售趋势',
          query: { output_fields: [{ name: 'sale_date', type: 'date' }] },
        },
      ],
    } as DashboardSchemaV1;
    const dateSnapshot = {
      dashboard_id: 'filter-test',
      refreshed_at: '2026-09-09T14:30:00',
      filters: {},
      widgets: {
        trend: {
          widget_id: 'trend',
          row_count: 3,
          truncated: false,
          duration_ms: 0,
          refreshed_at: '2026-09-09T14:30:00',
          columns: ['sale_date'],
          rows: [['2024-02-01'], ['2023-01-15'], ['2024-12-31T09:00:00Z']],
        },
      },
    } satisfies DashboardSnapshot;

    expect(buildDashboardFilterFieldCandidates(dateSchema, dateSnapshot)[0]).toMatchObject({
      field: 'sale_date',
      dataTypes: ['date'],
      dateRange: ['2023-01-15', '2024-12-31'],
      rangeIsPartial: false,
    });
  });

  it('marks a discovered date range as partial when the source result was truncated', () => {
    const dateSchema = {
      widgets: [
        {
          id: 'trend',
          title: '销售趋势',
          query: { output_fields: [{ name: 'sale_date', type: 'date' }] },
        },
      ],
    } as DashboardSchemaV1;
    const truncatedSnapshot = {
      dashboard_id: 'filter-test',
      refreshed_at: '2026-09-09T14:30:00',
      filters: {},
      widgets: {
        trend: {
          widget_id: 'trend',
          row_count: 2,
          duration_ms: 0,
          refreshed_at: '2026-09-09T14:30:00',
          columns: ['sale_date'],
          rows: [['2024-02-01'], ['2024-02-29']],
          truncated: true,
        },
      },
    } satisfies DashboardSnapshot;

    expect(buildDashboardFilterFieldCandidates(dateSchema, truncatedSnapshot)[0]).toMatchObject({
      dateRange: ['2024-02-01', '2024-02-29'],
      rangeIsPartial: true,
    });
  });

  it('recommends distinct start and end parameters for a date filter', () => {
    expect(
      recommendDashboardDateFilterParameters('date_range', 'date', ['store_ids', 'end_date', 'start_date']),
    ).toEqual({ startParameter: 'start_date', endParameter: 'end_date' });
  });
});
