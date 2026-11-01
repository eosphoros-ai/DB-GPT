import { DashboardSchemaV1 } from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import { makeDashboardSaveOperation, resolveDashboardWebSocketUrl } from './dashboard-collaboration';
import { makeUnconfiguredVisualizationWidget } from './dashboard-editor-model';

const schema = {
  schema_version: '1.0',
  dashboard: {
    id: 'dashboard-1',
    title: 'Sales',
    description: '',
    data_source_id: 'sales',
    status: 'draft',
    theme: {},
  },
  metric_context: { grain: '', source_notes: [] },
  filters: [],
  widgets: [],
  layouts: { columns: 12, desktop: [], mobile_strategy: 'stack' },
  metadata: { agent: { generated: false }, compatibility: {} },
} satisfies DashboardSchemaV1;

describe('dashboard collaboration save operation', () => {
  it('only emits editable schema paths with the current revision', () => {
    const request = makeDashboardSaveOperation(schema, 7, 'browser-a');
    expect(request.expected_revision).toBe(7);
    expect(request.client_id).toBe('browser-a');
    expect(request.promote_to_asset).toBe(true);
    expect(request.operations.map(item => item.path)).toEqual([
      '/schema_version',
      '/dashboard/title',
      '/dashboard/description',
      '/dashboard/theme',
      '/metric_context',
      '/filters',
      '/widgets',
      '/layouts',
      '/metadata/compatibility',
    ]);
    expect(request.operations.some(item => item.path.includes('status'))).toBe(false);
    expect(request.operations.some(item => item.path.includes('data_source_id'))).toBe(false);
  });

  it('persists a legacy dashboard schema upgrade together with presentation widgets', () => {
    const upgraded = {
      ...schema,
      schema_version: '1.3',
      widgets: [
        {
          ...makeUnconfiguredVisualizationWidget('heatmap', 'sales', 'heatmap-1'),
          title: 'Heatmap',
        },
      ],
    } satisfies DashboardSchemaV1;

    const request = makeDashboardSaveOperation(upgraded, 7, 'browser-a');

    expect(request.operations[0]).toEqual({ op: 'replace', path: '/schema_version', value: '1.3' });
    expect(request.operations.find(item => item.path === '/widgets')?.value).toEqual(upgraded.widgets);
  });

  it('can persist generated edits without promoting them into the asset library', () => {
    const request = makeDashboardSaveOperation(schema, 7, 'browser-a', false);
    expect(request.promote_to_asset).toBe(false);
  });
});

describe('dashboard collaboration websocket URL', () => {
  it('uses the configured backend host during split frontend/backend development', () => {
    expect(
      resolveDashboardWebSocketUrl(
        '/api/v1/dashboards/dashboard-1/collaboration/ws',
        'ticket with spaces',
        'http://127.0.0.1:5672',
        'http://127.0.0.1:5682',
      ),
    ).toBe('ws://127.0.0.1:5672/api/v1/dashboards/dashboard-1/collaboration/ws?ticket=ticket+with+spaces');
  });

  it('falls back to the current HTTPS origin when no API base URL is configured', () => {
    expect(resolveDashboardWebSocketUrl('/ws/dashboard', 'abc', '', 'https://dashboard.example.com')).toBe(
      'wss://dashboard.example.com/ws/dashboard?ticket=abc',
    );
  });
});
