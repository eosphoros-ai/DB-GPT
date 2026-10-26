import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getPublicDashboard: vi.fn(),
  filterPublicDashboard: vi.fn(),
}));

vi.mock('@/client/api', () => ({
  getPublicDashboard: api.getPublicDashboard,
  filterPublicDashboard: api.filterPublicDashboard,
}));

vi.mock('next/router', () => ({
  useRouter: () => ({ query: { token: 'public-token' } }),
}));

vi.mock('next/head', () => ({
  default: ({ children }: { children: ReactNode }) => children,
}));

vi.mock('antd', () => ({
  Alert: ({ message, description }: { message: ReactNode; description?: ReactNode }) => (
    <div>
      <span>{message}</span>
      <span>{description}</span>
    </div>
  ),
  Spin: () => <span>loading</span>,
  Tag: ({ children }: { children: ReactNode }) => <span>{children}</span>,
  ConfigProvider: ({ children }: { children: ReactNode }) => children,
  theme: { darkAlgorithm: {}, defaultAlgorithm: {} },
}));

vi.mock('@/new-components/dashboard', () => ({
  DashboardFilters: ({ onChange }: { onChange: (filters: Record<string, unknown>) => void }) => (
    <button type='button' onClick={() => onChange({ stores: [1, 2] })}>
      change-filters
    </button>
  ),
  DashboardRenderer: ({ snapshot }: { snapshot: { widgets: { value: { rows: unknown[][] } } } }) => (
    <div>rendered-value:{String(snapshot.widgets.value.rows[0][0])}</div>
  ),
}));

import DashboardSharePage from '../../pages/dashboard-share/[token]';

const published = {
  dashboard_id: 'dashboard-1',
  published_revision: 2,
  published_at: '2026-08-17T10:00:00Z',
  schema: {
    schema_version: '1.3',
    dashboard: {
      id: 'dashboard-1',
      title: 'Shared dashboard',
      description: 'Frozen data with interactive filters',
      data_source_id: 'demo',
    },
    metric_context: { grain: 'store-week', data_freshness: 'published' },
    filters: [
      {
        id: 'stores',
        type: 'multi-select',
        label: 'Stores',
        field: 'store',
      },
    ],
    widgets: [],
    layouts: { columns: 12, desktop: [], mobile_strategy: 'stack' },
    metadata: { agent: { generated: false }, compatibility: {} },
  },
  snapshot: {
    dashboard_id: 'dashboard-1',
    refreshed_at: '2026-08-17T10:00:00Z',
    filters: {},
    widgets: {
      value: {
        widget_id: 'value',
        columns: ['value'],
        rows: [[10]],
        row_count: 1,
        truncated: false,
        duration_ms: 0,
        refreshed_at: '2026-08-17T10:00:00Z',
      },
    },
    publication_datasets: {},
  },
};

const apiResponse = (data: unknown) => Promise.resolve({ data: { data } });

describe('DashboardSharePage', () => {
  beforeEach(() => {
    api.getPublicDashboard.mockReturnValue(apiResponse(published));
    api.filterPublicDashboard.mockReturnValue(
      apiResponse({
        snapshot: {
          ...published.snapshot,
          filters: { stores: [1, 2] },
          widgets: {
            value: { ...published.snapshot.widgets.value, rows: [[25]] },
          },
        },
        unsupported_widget_ids: [],
      }),
    );
  });

  it('filters the immutable publication dataset and redraws the shared page', async () => {
    render(<DashboardSharePage />);

    expect(await screen.findByText('rendered-value:10')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'change-filters' }));

    await waitFor(() =>
      expect(api.filterPublicDashboard).toHaveBeenCalledWith('public-token', {
        stores: [1, 2],
      }),
    );
    expect(await screen.findByText('rendered-value:25')).toBeTruthy();
    expect(screen.getByText(/不会连接生产数据库/)).toBeTruthy();
  });

  it('keeps the last successful snapshot when public filtering fails', async () => {
    api.filterPublicDashboard.mockRejectedValueOnce(new Error('invalid public filter'));
    render(<DashboardSharePage />);

    expect(await screen.findByText('rendered-value:10')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'change-filters' }));

    expect(await screen.findByText('筛选发布快照失败')).toBeTruthy();
    expect(screen.getByText(/已保留上一次成功显示的结果/)).toBeTruthy();
    expect(screen.getByText('rendered-value:10')).toBeTruthy();
  });

  it('does not report missing publication bindings when the dashboard has no filters', async () => {
    api.getPublicDashboard.mockReturnValueOnce(
      apiResponse({
        ...published,
        schema: {
          ...published.schema,
          filters: [],
          widgets: [
            {
              id: 'value',
              type: 'kpi',
              title: 'Value',
              query: { output_fields: [] },
              encoding: { value: 'value' },
            },
          ],
        },
      }),
    );

    render(<DashboardSharePage />);

    expect(await screen.findByText('rendered-value:10')).toBeTruthy();
    expect(screen.queryByText('这个发布版本不能完整响应筛选')).toBeNull();
    expect(screen.queryByText(/可调整筛选条件/)).toBeNull();
  });

  it('uses only the visual theme frozen in the published schema', async () => {
    api.getPublicDashboard.mockReturnValueOnce(
      apiResponse({
        ...published,
        schema: {
          ...published.schema,
          schema_version: '1.4',
          dashboard: {
            ...published.schema.dashboard,
            theme: { preset: 'graphite', mode: 'dark', overrides: {} },
          },
        },
      }),
    );

    render(<DashboardSharePage />);
    expect(await screen.findByText('rendered-value:10')).toBeTruthy();
    const root = document.querySelector('[data-dashboard-theme="graphite"]') as HTMLElement;
    expect(root.dataset.dashboardMode).toBe('dark');
    expect(root.style.getPropertyValue('--dashboard-theme-canvas')).toBe('#111317');
    expect(document.querySelector('meta[name="theme-color"]')?.getAttribute('content')).toBe('#111317');
  });

  it('explains that an old publication must be republished when bindings are missing', async () => {
    api.getPublicDashboard.mockReturnValueOnce(
      apiResponse({
        ...published,
        schema: {
          ...published.schema,
          filters: [
            {
              id: 'stores',
              type: 'multi-select',
              label: 'Stores',
              field: 'store',
            },
          ],
          widgets: [
            {
              id: 'value',
              type: 'kpi',
              title: 'Value',
              query: { output_fields: [] },
              encoding: { value: 'value' },
            },
          ],
        },
      }),
    );

    render(<DashboardSharePage />);

    expect(await screen.findByText('这个发布版本不能完整响应筛选')).toBeTruthy();
    expect(screen.getByText(/重新发布一个新版本/)).toBeTruthy();
  });
});
