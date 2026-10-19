import type { DashboardSchemaV1, DashboardSnapshot, DashboardWidget, DashboardWidgetType } from '@/types/dashboard';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const grid = vi.hoisted(() => ({ width: 1200 }));

vi.mock('@/new-components/charts', () => ({
  AdvancedChart: ({
    config,
  }: {
    config: {
      chartType: string;
      smooth?: boolean;
      innerRadius?: number;
      colors?: string[];
      showGrid?: boolean;
      visualTheme?: { mode: string; text: string };
    };
  }) => (
    <div
      data-testid={`chart-${config.chartType}`}
      data-smooth={String(config.smooth)}
      data-inner-radius={String(config.innerRadius)}
      data-colors={config.colors?.join(',') || ''}
      data-show-grid={String(config.showGrid)}
      data-theme-mode={config.visualTheme?.mode || ''}
    >
      {config.chartType}
    </div>
  ),
}));

vi.mock('react-grid-layout', () => ({
  default: ({ children }: { children: ReactNode }) => <div data-testid='grid'>{children}</div>,
  useContainerWidth: () => ({ width: grid.width, containerRef: { current: null }, mounted: true }),
  verticalCompactor: {},
}));

import DashboardRenderer from './DashboardRenderer';
import { makeUnconfiguredWidget } from './dashboard-editor-model';

const widget = (id: string, type: DashboardWidgetType): DashboardWidget => {
  const fields =
    type === 'kpi'
      ? [{ name: 'value', type: 'number' as const, label: 'Value', nullable: true }]
      : [
          { name: 'category', type: 'string' as const, label: 'Category', nullable: true },
          { name: 'value', type: 'number' as const, label: 'Value', nullable: true },
        ];
  return {
    id,
    type,
    title: `${type} widget`,
    description: '',
    query: {
      data_source_id: 'demo',
      sql: 'SELECT 1',
      filter_parameters: {},
      default_parameters: {},
      output_fields: fields,
      timeout_seconds: 30,
      max_rows: 100,
      last_execution: { status: 'succeeded' },
    },
    encoding:
      type === 'kpi'
        ? { value: 'value', columns: [] }
        : type === 'pie'
          ? { category: 'category', color: 'category', angle: 'value', columns: [] }
          : type === 'table'
            ? { columns: ['category', 'value'] }
            : { x: 'category', y: 'value', columns: [] },
    style: {},
  };
};

const widgets = [
  widget('kpi', 'kpi'),
  widget('line', 'line'),
  widget('bar', 'bar'),
  widget('pie', 'pie'),
  widget('table', 'table'),
];

const schema: DashboardSchemaV1 = {
  schema_version: '1.0',
  dashboard: {
    id: 'dashboard-1',
    title: 'Five widgets',
    description: '',
    data_source_id: 'demo',
    status: 'draft',
    theme: {},
  },
  metric_context: { grain: '', source_notes: [] },
  filters: [],
  widgets,
  layouts: {
    columns: 12,
    desktop: widgets.map((item, index) => ({
      widget_id: item.id,
      x: (index % 2) * 6,
      y: Math.floor(index / 2) * 4,
      w: 6,
      h: 4,
    })),
    mobile_strategy: 'stack',
  },
  metadata: { agent: { generated: false }, compatibility: {} },
};

const snapshot: DashboardSnapshot = {
  dashboard_id: 'dashboard-1',
  refreshed_at: new Date().toISOString(),
  filters: {},
  widgets: Object.fromEntries(
    widgets.map(item => [
      item.id,
      {
        widget_id: item.id,
        columns: item.type === 'kpi' ? ['value'] : ['category', 'value'],
        rows: item.type === 'kpi' ? [[1234]] : [['A', 10]],
        row_count: 1,
        truncated: false,
        duration_ms: 3,
        refreshed_at: new Date().toISOString(),
      },
    ]),
  ),
};

describe('DashboardRenderer', () => {
  afterEach(() => {
    grid.width = 1200;
  });

  it.each([1200, 600])('follows the selected layout reading order at %i pixels', width => {
    grid.width = width;
    const reordered = {
      ...schema,
      layouts: {
        ...schema.layouts,
        desktop: [...schema.layouts.desktop].reverse().map((item, index) => ({ ...item, x: 0, y: index * 4 })),
      },
    };
    const { container } = render(<DashboardRenderer schema={reordered} snapshot={snapshot} />);
    expect(
      Array.from(container.querySelectorAll('[data-dashboard-widget-id]')).map(element =>
        element.getAttribute('data-dashboard-widget-id'),
      ),
    ).toEqual(['table', 'pie', 'bar', 'line', 'kpi']);
  });

  it('renders KPI, line, bar, pie, and table widgets from one schema', () => {
    render(<DashboardRenderer schema={schema} snapshot={snapshot} />);

    expect(screen.getByText('1,234')).toBeTruthy();
    expect(screen.getByTestId('chart-line')).toBeTruthy();
    expect(screen.getByTestId('chart-column')).toBeTruthy();
    expect(screen.getByTestId('chart-donut')).toBeTruthy();
    expect(screen.getByText('Category')).toBeTruthy();
  });

  it('clearly marks a widget anomaly and exposes its deterministic evidence', () => {
    const anomalySnapshot: DashboardSnapshot = {
      ...snapshot,
      widgets: {
        ...snapshot.widgets,
        kpi: {
          ...snapshot.widgets.kpi,
          anomalies: [
            {
              rule_id: 'kpi-drop',
              rule_label: 'KPI 环比下降',
              status: 'anomaly',
              baseline: 'previous_period',
              current_value: 80,
              baseline_value: 100,
              absolute_change: -20,
              change_ratio: -0.2,
              threshold: { mode: 'relative_change', value: 0.1 },
              comparison_time_range: {
                current_start: '2026-08',
                baseline_start: '2026-07',
              },
              sample_size: 2,
              matched_rule: 'change_ratio <= -0.1',
            },
          ],
        },
      },
    };

    render(
      <DashboardRenderer
        schema={{
          ...schema,
          widgets: [widgets[0]],
          layouts: { ...schema.layouts, desktop: [schema.layouts.desktop[0]] },
        }}
        snapshot={anomalySnapshot}
      />,
    );

    expect(screen.getByText('检测到 1 条异常')).toBeTruthy();
    expect(screen.getByText('KPI 环比下降')).toBeTruthy();
    expect(document.querySelector('[data-dashboard-widget-id="kpi"]')?.className).toContain('border-[var(--app-danger)]');
  });

  it('applies KPI number formatting stored in widget style', () => {
    const styledSchema: DashboardSchemaV1 = {
      ...schema,
      widgets: schema.widgets.map(item =>
        item.id === 'kpi' ? { ...item, style: { prefix: '$', suffix: ' M', precision: 1 } } : item,
      ),
    };
    const styledSnapshot: DashboardSnapshot = {
      ...snapshot,
      widgets: {
        ...snapshot.widgets,
        kpi: { ...snapshot.widgets.kpi, rows: [[1234.56]] },
      },
    };

    render(<DashboardRenderer schema={styledSchema} snapshot={styledSnapshot} />);

    expect(screen.getByText('$1,234.6 M')).toBeTruthy();
  });

  it('renders fiscal_year=2024 unchanged but revenue=391035 with grouping', () => {
    const table = { ...widget('table-numbers', 'table'), encoding: { columns: ['fiscal_year', 'revenue'] } };
    table.query = {
      ...table.query,
      output_fields: [
        { name: 'fiscal_year', type: 'integer', nullable: false },
        { name: 'revenue', type: 'number', nullable: false },
      ],
    };
    render(
      <DashboardRenderer
        schema={{
          ...schema,
          widgets: [table],
          layouts: { ...schema.layouts, desktop: [{ widget_id: table.id, x: 0, y: 0, w: 12, h: 5 }] },
        }}
        snapshot={{
          ...snapshot,
          widgets: {
            [table.id]: {
              ...snapshot.widgets.table,
              widget_id: table.id,
              columns: ['fiscal_year', 'revenue'],
              rows: [[2024, 391035]],
            },
          },
        }}
      />,
    );
    expect(screen.getByText('2024', { exact: true })).toBeTruthy();
    expect(screen.getByText('391,035', { exact: true })).toBeTruthy();
    expect(screen.queryByText('2,024', { exact: true })).toBeNull();
  });

  it('applies Schema 1.3 percentage formatting without a fake currency prefix', () => {
    const percentageSchema: DashboardSchemaV1 = {
      ...schema,
      schema_version: '1.3',
      widgets: schema.widgets.map(item =>
        item.id === 'kpi'
          ? {
              ...item,
              presentation: {
                visualization: 'kpi',
                orientation: null,
                stacked: false,
                smooth: true,
                top_n: null,
                colors: [],
                unit: null,
                currency: '$',
                precision: 1,
                percentage: true,
                show_legend: null,
                show_grid: null,
                default_sort: { field: null, direction: 'default' },
              },
            }
          : item,
      ),
    };
    const percentageSnapshot: DashboardSnapshot = {
      ...snapshot,
      widgets: { ...snapshot.widgets, kpi: { ...snapshot.widgets.kpi, rows: [[0.236]] } },
    };

    render(<DashboardRenderer schema={percentageSchema} snapshot={percentageSnapshot} />);

    expect(screen.getByText('23.6%')).toBeTruthy();
  });

  it('passes schema style into line and donut chart configuration', () => {
    const styledSchema: DashboardSchemaV1 = {
      ...schema,
      widgets: schema.widgets.map(item => {
        if (item.id === 'line') return { ...item, style: { smooth: false } };
        if (item.id === 'pie') return { ...item, style: { innerRadius: 0.55 } };
        return item;
      }),
    };

    render(<DashboardRenderer schema={styledSchema} snapshot={snapshot} />);

    expect(screen.getByTestId('chart-line').getAttribute('data-smooth')).toBe('false');
    expect(screen.getByTestId('chart-donut').getAttribute('data-inner-radius')).toBe('0.55');
  });

  it('passes user-selected colors and grid visibility into the chart renderer', () => {
    const styledSchema: DashboardSchemaV1 = {
      ...schema,
      schema_version: '1.3',
      widgets: schema.widgets.map(item =>
        item.id === 'line'
          ? {
              ...item,
              presentation: {
                visualization: 'line',
                orientation: 'vertical',
                stacked: false,
                smooth: true,
                top_n: null,
                colors: ['#123456', '#ABCDEF'],
                unit: null,
                currency: null,
                precision: null,
                percentage: false,
                show_legend: true,
                show_grid: false,
                default_sort: { field: null, direction: 'default' },
              },
            }
          : item,
      ),
    };

    render(<DashboardRenderer schema={styledSchema} snapshot={snapshot} />);

    expect(screen.getByTestId('chart-line').getAttribute('data-colors')).toBe('#123456,#ABCDEF');
    expect(screen.getByTestId('chart-line').getAttribute('data-show-grid')).toBe('false');
  });

  it('applies a saved visual theme to cards, charts, KPI, table, and layout root', () => {
    const themedSchema: DashboardSchemaV1 = {
      ...schema,
      schema_version: '1.4',
      dashboard: {
        ...schema.dashboard,
        theme: { preset: 'graphite', mode: 'dark', overrides: {} },
      },
    };

    render(<DashboardRenderer schema={themedSchema} snapshot={snapshot} />);

    const root = document.querySelector('[data-dashboard-theme="graphite"]') as HTMLElement;
    expect(root).toBeTruthy();
    expect(root.dataset.dashboardMode).toBe('dark');
    expect(root.style.getPropertyValue('--dashboard-theme-card')).toBe('#1B1E24');
    expect(screen.getByTestId('chart-line').getAttribute('data-colors')).toContain('#91A0FF');
    expect(screen.getByTestId('chart-line').getAttribute('data-theme-mode')).toBe('dark');
    expect(document.querySelector('[data-dashboard-kpi-style="quiet"]')).toBeTruthy();
    expect(document.querySelector('[data-dashboard-table-style="striped"]')).toBeTruthy();
  });

  it('shows separate visual and SQL actions for an editable widget', () => {
    const onEditWidget = vi.fn();
    const onOpenQueryEditor = vi.fn();
    render(
      <DashboardRenderer
        schema={{
          ...schema,
          widgets: [widgets[0]],
          layouts: { ...schema.layouts, desktop: [schema.layouts.desktop[0]] },
        }}
        editable
        onEditWidget={onEditWidget}
        onOpenWidgetQueryEditor={onOpenQueryEditor}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '编辑可视化设置' }));
    expect(onEditWidget).toHaveBeenCalledWith('kpi');

    fireEvent.click(screen.getByRole('button', { name: 'SQL 与参数设置' }));
    expect(onOpenQueryEditor).toHaveBeenCalledWith('kpi');
  });

  it('opens manual settings for only the selected widget from its edit icon', () => {
    const onEditWidget = vi.fn();
    const onSelectAnnotationTarget = vi.fn();
    render(
      <DashboardRenderer
        schema={{
          ...schema,
          widgets: [widgets[0]],
          layouts: { ...schema.layouts, desktop: [schema.layouts.desktop[0]] },
        }}
        editable
        onEditWidget={onEditWidget}
        onSelectAnnotationTarget={onSelectAnnotationTarget}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '编辑可视化设置' }));

    expect(onEditWidget).toHaveBeenCalledWith('kpi');
    expect(onSelectAnnotationTarget).not.toHaveBeenCalled();
  });

  it('turns the same widget action into a component annotation while annotation mode is active', () => {
    const onEditWidget = vi.fn();
    const onSelectAnnotationTarget = vi.fn();
    render(
      <DashboardRenderer
        schema={{
          ...schema,
          widgets: [widgets[0]],
          layouts: { ...schema.layouts, desktop: [schema.layouts.desktop[0]] },
        }}
        editable
        annotationMode
        onEditWidget={onEditWidget}
        onSelectAnnotationTarget={onSelectAnnotationTarget}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '批注此组件' }));

    expect(onEditWidget).not.toHaveBeenCalled();
    expect(onSelectAnnotationTarget).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'widget', widget_id: 'kpi' }),
      expect.any(Object),
    );
  });

  it('labels a new zero-row widget as unconfigured instead of showing fake data', () => {
    const newWidget = makeUnconfiguredWidget('table', 'demo', 'new-table');
    const onRequestAgentWidgetConfiguration = vi.fn();
    const onOpenWidgetQueryEditor = vi.fn();
    render(
      <DashboardRenderer
        schema={{
          ...schema,
          widgets: [newWidget],
          layouts: {
            ...schema.layouts,
            desktop: [{ widget_id: newWidget.id, x: 0, y: 0, w: 12, h: 5 }],
          },
        }}
        editable
        onRequestAgentWidgetConfiguration={onRequestAgentWidgetConfiguration}
        onOpenWidgetQueryEditor={onOpenWidgetQueryEditor}
      />,
    );

    expect(screen.getByText('尚未配置查询')).toBeTruthy();
    expect(screen.getByText('选择数据助理自动生成查询与字段映射，或直接手动编写 SQL。')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '让数据助理配置' }));
    expect(onRequestAgentWidgetConfiguration).toHaveBeenCalledWith(newWidget.id, expect.any(Object));

    fireEvent.click(screen.getByRole('button', { name: '手动配置 SQL' }));
    expect(onOpenWidgetQueryEditor).toHaveBeenCalledWith(newWidget.id);
  });
});
