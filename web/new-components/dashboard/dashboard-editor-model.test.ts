import { describe, expect, it } from 'vitest';

import {
  hasConfiguredDashboardWidgets,
  isWidgetQueryUnconfigured,
  makeUnconfiguredVisualizationWidget,
  makeUnconfiguredWidget,
  normalizeUnconfiguredVisualizationWidget,
  updateWidgetOutputFields,
} from './dashboard-editor-model';

describe('dashboard editor model', () => {
  it.each(['kpi', 'line', 'bar', 'pie', 'table'] as const)(
    'creates a safe zero-row placeholder for a new %s widget',
    type => {
      const widget = makeUnconfiguredWidget(type, 'demo', `${type}-new`);

      expect(widget.query.sql).toContain('WHERE 1 = 0');
      expect(widget.query.sql).not.toContain('示例');
      expect(isWidgetQueryUnconfigured(widget)).toBe(true);
    },
  );

  it.each([
    ['kpi', ['value']],
    ['line', ['x', 'y']],
    ['area', ['x', 'y']],
    ['column', ['x', 'y']],
    ['bar', ['x', 'y']],
    ['stacked_column', ['x', 'y']],
    ['pie', ['angle']],
    ['donut', ['angle']],
    ['scatter', ['x', 'y']],
    ['dual_axis', ['x', 'y', 'y2']],
    ['heatmap', ['row', 'column', 'value']],
    ['gauge', ['value']],
    ['funnel', ['x', 'y']],
    ['treemap', ['x', 'y']],
    ['radar', ['x', 'y']],
    ['waterfall', ['x', 'y']],
    ['geo_map', ['x', 'y']],
    ['table', []],
  ] as const)('creates a saveable unconfigured %s visualization draft', (visualization, required) => {
    const widget = makeUnconfiguredVisualizationWidget(visualization, 'demo', `${visualization}-new`);
    const declared = new Set(widget.query.output_fields.map(field => field.name));

    expect(isWidgetQueryUnconfigured(widget)).toBe(true);
    for (const key of required) {
      const field = widget.encoding[key];
      expect(field).toBeTruthy();
      expect(declared.has(String(field))).toBe(true);
    }
  });

  it('stops treating a widget as unconfigured after the user supplies SQL', () => {
    const widget = makeUnconfiguredWidget('table', 'demo', 'table-new');
    widget.query.sql = 'SELECT store, sales FROM sales';

    expect(isWidgetQueryUnconfigured(widget)).toBe(false);
  });

  it('repairs a heatmap draft created by an older editor without touching real queries', () => {
    const legacy = makeUnconfiguredWidget('bar', 'demo', 'legacy-heatmap');
    legacy.presentation = {
      visualization: 'heatmap',
      stacked: false,
      smooth: false,
      colors: [],
      percentage: false,
      default_sort: { direction: 'ascending' },
    };
    expect(legacy.encoding).toMatchObject({ x: 'category', y: 'value' });

    const repaired = normalizeUnconfiguredVisualizationWidget(legacy);
    expect(repaired.encoding).toMatchObject({ row: 'category', column: 'category', value: 'value' });

    const configured = { ...legacy, query: { ...legacy.query, sql: 'SELECT month, store, sales FROM facts' } };
    expect(normalizeUnconfiguredVisualizationWidget(configured)).toBe(configured);
  });

  it.each([
    'SELECT 0 AS value',
    "SELECT 'Unavailable' AS category, 0 AS value",
    "SELECT 'Query generation failed' AS message",
  ])('recognizes legacy agent failure placeholders: %s', sql => {
    const widget = makeUnconfiguredWidget('table', 'demo', 'legacy-failure');
    widget.query.sql = sql;

    expect(isWidgetQueryUnconfigured(widget)).toBe(true);
  });

  it('only auto-loads a draft when at least one component has a real query', () => {
    const placeholder = makeUnconfiguredWidget('table', 'demo', 'placeholder');
    const configured = makeUnconfiguredWidget('bar', 'demo', 'configured');
    configured.query.sql = 'SELECT store, SUM(sales) AS sales FROM sales GROUP BY store';

    expect(hasConfiguredDashboardWidgets([placeholder])).toBe(false);
    expect(hasConfiguredDashboardWidgets([placeholder, configured])).toBe(true);
  });

  it('deduplicates output fields and gives a new table an immediately usable column mapping', () => {
    const widget = makeUnconfiguredWidget('table', 'demo', 'table-new');
    const updated = updateWidgetOutputFields(widget, ['store', ' sales ', 'store', '']);

    expect(updated.query.output_fields.map(field => field.name)).toEqual(['store', 'sales']);
    expect(updated.encoding.columns).toEqual(['store', 'sales']);
  });

  it('preserves compatible chart mappings and repairs removed ones', () => {
    const widget = makeUnconfiguredWidget('line', 'demo', 'line-new');
    widget.encoding = { x: 'category', y: 'value', columns: [] };

    const compatible = updateWidgetOutputFields(widget, ['category', 'value', 'region']);
    expect(compatible.encoding).toMatchObject({ x: 'category', y: 'value' });

    const repaired = updateWidgetOutputFields(widget, ['month', 'sales']);
    expect(repaired.encoding).toMatchObject({ x: 'month', y: 'sales' });
  });
});
