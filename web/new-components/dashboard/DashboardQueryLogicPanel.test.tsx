import { getDashboardQueryLogic } from '@/client/api/dashboard';
import type { DashboardFilter, DashboardWidget } from '@/types/dashboard';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { describe, expect, it, vi } from 'vitest';
import DashboardQueryLogicPanel, { widgetQueryParameters } from './DashboardQueryLogicPanel';

vi.mock('@/client/api/dashboard', () => ({ getDashboardQueryLogic: vi.fn() }));

const widget = {
  id: 'revenue',
  query: {
    sql: 'SELECT SUM(amount) AS value FROM sales WHERE year = :year',
    data_source_id: 'demo',
    max_rows: 100,
    default_parameters: { year: 2024 },
    filter_parameters: { year: 'year', dates: { start_parameter: 'start', end_parameter: 'end' } },
  },
} as unknown as DashboardWidget;
const filters = [
  { id: 'year', type: 'select', default: 2025 },
  { id: 'dates', type: 'date_range', default: null },
] as DashboardFilter[];

describe('query calculation logic', () => {
  it('preserves explicit clearing, dates, and parameter default precedence', () => {
    expect(widgetQueryParameters(widget, filters, { year: null, dates: ['2026-01-01', '2026-12-31'] })).toEqual({
      year: null,
      start: '2026-01-01',
      end: '2026-12-31',
    });
    expect(widgetQueryParameters(widget, filters, {})).toEqual({ year: 2025, start: null, end: null });
    expect(widgetQueryParameters(widget, [{ ...filters[0], default: null }], {})).toEqual({
      year: 2024,
      start: null,
      end: null,
    });
  });

  it('keeps the actual SQL readable when parsing is unavailable', async () => {
    vi.mocked(getDashboardQueryLogic).mockRejectedValue(new Error('offline'));
    render(
      <App>
        <DashboardQueryLogicPanel dashboardId='board' widget={widget} filters={filters} values={{ year: 2026 }} />
      </App>,
    );
    expect(screen.getByLabelText('图表实际 SQL').textContent).toContain('SUM(amount)');
    expect(await screen.findByText(/暂时无法解析计算步骤/)).toBeTruthy();
    expect(screen.getByText('2026')).toBeTruthy();
  });

  it('refreshes the calculation description when the query is edited', async () => {
    vi.mocked(getDashboardQueryLogic).mockResolvedValue({
      data: { success: true, data: { tables: ['sales'], stages: [], set_operations: [] } },
    } as never);
    const view = render(
      <App>
        <DashboardQueryLogicPanel dashboardId='board' widget={widget} filters={filters} values={{}} />
      </App>,
    );
    await waitFor(() => expect(getDashboardQueryLogic).toHaveBeenCalledWith('board', widget.query.sql, 'demo'));
    const changed = { ...widget, query: { ...widget.query, sql: 'SELECT COUNT(*) FROM orders' } };
    view.rerender(
      <App>
        <DashboardQueryLogicPanel dashboardId='board' widget={changed} filters={filters} values={{}} />
      </App>,
    );
    await waitFor(() => expect(getDashboardQueryLogic).toHaveBeenCalledWith('board', changed.query.sql, 'demo'));
    expect(screen.getByLabelText('图表实际 SQL').textContent).toContain('COUNT(*)');
  });
});
