import type { DashboardSchemaV1, DashboardWidget } from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import fixture from '../../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/tests/layout-template-cases.json';
import { dashboardHistoryReducer } from './dashboard-editor-history';
import { makeUnconfiguredWidget } from './dashboard-editor-model';
import {
  applyDashboardLayoutTemplate,
  DASHBOARD_LAYOUT_TEMPLATES,
  templateDashboardLayout,
} from './dashboard-layout-templates';
import { LAYOUT_TEMPLATES_ENABLED } from './dashboard-release-features';
import { DASHBOARD_TEMPLATES } from './dashboard-templates';

const widgets = fixture.widgets.map(item => ({
  ...makeUnconfiguredWidget(item.type as DashboardWidget['type'], 'sales'),
  id: item.id,
}));
const schema: DashboardSchemaV1 = {
  schema_version: '1.4',
  dashboard: {
    id: 'layout-test',
    title: 'Test',
    description: '',
    data_source_id: 'sales',
    status: 'draft',
    theme: { preset: 'warm', mode: 'dark', overrides: { card_radius: 20 } },
  },
  metric_context: { grain: 'month', source_notes: ['verified fixture'] },
  widgets,
  filters: [],
  layouts: { columns: 12, desktop: [], mobile_strategy: 'stack' },
  metadata: { agent: { generated: false }, compatibility: {} },
};

describe('dashboard layout templates', () => {
  it.each(DASHBOARD_LAYOUT_TEMPLATES)('$id matches the shared generation/editor contract', template => {
    const layout = templateDashboardLayout(widgets, template.id);
    expect(layout.map(item => [item.widget_id, item.x, item.y, item.w, item.h])).toEqual(fixture.expected[template.id]);
  });

  it.each(DASHBOARD_LAYOUT_TEMPLATES)('$id fits arbitrary widget counts without overlaps or lost widgets', template => {
    for (let count = 0; count <= 24; count++) {
      for (const types of [['kpi'], ['table'], ['line'], ['kpi', 'line', 'table', 'bar']] as const) {
        const entries = Array.from({ length: count }, (_, i) => ({ id: String(i), type: types[i % types.length] }));
        const layout = templateDashboardLayout(entries, template.id);
        expect(new Set(layout.map(item => item.widget_id)).size).toBe(count);
        layout.forEach((item, i) => {
          expect([item.x, item.y, item.w, item.h].every(Number.isInteger)).toBe(true);
          expect(item.x + item.w).toBeLessThanOrEqual(12);
          expect(item.w).toBeGreaterThanOrEqual(item.min_w!);
          expect(item.h).toBeGreaterThanOrEqual(item.min_h!);
          layout.slice(i + 1).forEach(other => {
            expect(
              item.x < other.x + other.w &&
                other.x < item.x + item.w &&
                item.y < other.y + other.h &&
                other.y < item.y + item.h,
            ).toBe(false);
          });
        });
      }
    }
  });

  it('uses the displayed visualization and gives gauges chart height', () => {
    const gauge = { ...widgets[1], presentation: { ...widgets[1].presentation!, visualization: 'gauge' as const } };
    const [placed] = templateDashboardLayout([gauge], 'metric-overview');
    expect(placed.h).toBe(6);
  });

  it('changes only layout and opted-in appearance, preserves the mode and can undo atomically', () => {
    const before = JSON.stringify(schema);
    const history = dashboardHistoryReducer(
      { past: [], present: schema, future: [] },
      {
        type: 'set',
        update: current => applyDashboardLayoutTemplate(current, 'operations-detail'),
      },
    );
    expect(JSON.stringify(schema)).toBe(before);
    expect(history.present.widgets).toBe(schema.widgets);
    expect(history.present.filters).toBe(schema.filters);
    expect(history.present.metric_context).toBe(schema.metric_context);
    expect(history.present.metadata).toBe(schema.metadata);
    expect(history.present.dashboard.theme).toMatchObject({
      preset: 'clarity',
      mode: 'dark',
      overrides: { density: 'compact' },
    });
    expect(dashboardHistoryReducer(history, { type: 'undo' }).present).toEqual(schema);
    expect(applyDashboardLayoutTemplate(schema, 'trend-focus', false).dashboard).toBe(schema.dashboard);
  });

  it('retains the deferred families but never injects them into released business prompts', () => {
    expect(LAYOUT_TEMPLATES_ENABLED).toBe(false);
    expect(new Set(DASHBOARD_TEMPLATES.map(template => template.layoutId)).size).toBe(3);
    DASHBOARD_TEMPLATES.forEach(template => {
      expect(template.prompt).not.toContain('layout_template');
      expect(template.prompt).toContain('等待我确认');
    });
  });
});
