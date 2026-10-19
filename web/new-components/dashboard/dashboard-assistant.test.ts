import type {
  DashboardAnnotationRecord,
  DashboardRecord,
  DashboardSchemaV1,
  DashboardSnapshot,
} from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import {
  buildDashboardAssistantContext,
  buildDashboardAssistantPrompt,
  hasDashboardAnnotationWorkflowMarker,
  makeDashboardAnnotationDraft,
  resolveDashboardAnnotationDrafts,
} from './dashboard-assistant';

const record = {
  id: 'dashboard-1',
  schema: { dashboard: { title: 'Sales' } },
} as DashboardRecord;

const annotation = (id: string, label: string): DashboardAnnotationRecord =>
  ({
    id,
    target: { kind: 'widget', widget_id: label, label, datum_key: {}, row_key: {} },
    prompt: `request ${label}`,
  }) as DashboardAnnotationRecord;

describe('dashboard assistant batch prompt', () => {
  it('does not give a new natural-language draft a default modification intent', () => {
    expect(makeDashboardAnnotationDraft(annotation('1', 'sales').target).intent).toBeUndefined();
  });

  it('splits mixed requests while retaining the exact selected target', () => {
    const draft = {
      ...makeDashboardAnnotationDraft(annotation('1', 'sales').target),
      content: '改成柱状图，并解释下降原因',
    };
    const resolved = resolveDashboardAnnotationDrafts([draft], {
      items: [
        {
          draft_id: draft.id,
          tasks: [
            { intent: 'modify', prompt: '改成柱状图' },
            { intent: 'anomaly', prompt: '解释下降原因' },
          ],
        },
      ],
    });
    expect(resolved.map(item => item.intent)).toEqual(['modify', 'anomaly']);
    expect(resolved.every(item => item.target === draft.target)).toBe(true);
  });

  it('continues clear tasks and leaves ambiguous items for a separate question', () => {
    const drafts = ['sales', 'margin'].map(id => ({
      ...makeDashboardAnnotationDraft(annotation(id, id).target),
      content: '这个不对',
    }));
    expect(
      resolveDashboardAnnotationDrafts(drafts, {
        items: [
          { draft_id: drafts[0].id, tasks: [{ intent: 'modify', prompt: '修改标题' }] },
          { draft_id: drafts[1].id, tasks: [], question: '需要改哪里？' },
        ],
      }),
    ).toMatchObject([{ target: { widget_id: 'sales' }, intent: 'modify', content: '修改标题' }]);
    expect(() => resolveDashboardAnnotationDrafts(drafts, { items: [] })).toThrow('未覆盖全部批注');
  });
  it('supports a useful conversational reply without manufacturing modifications', () => {
    const draft = { ...makeDashboardAnnotationDraft(annotation('1', 'sales').target), content: '有什么建议' };
    expect(
      resolveDashboardAnnotationDrafts([draft], {
        reply: '收入卡建议标注当前筛选的时间范围。',
        items: [{ draft_id: draft.id, tasks: [], answered: true }],
      }),
    ).toEqual([]);
    expect(() =>
      resolveDashboardAnnotationDrafts([draft], {
        items: [{ draft_id: draft.id, tasks: [], answered: true }],
      }),
    ).toThrow('不完整');
  });
  it('sends actual filters, unsaved titles and bounded result samples', () => {
    const schema = {
      dashboard: { title: '销售' },
      filters: [],
      layouts: { desktop: [] },
      widgets: [
        {
          id: 'sales',
          title: '修改中的收入',
          type: 'kpi',
          query: { sql: 'SELECT SUM(sales) AS value FROM orders' },
          encoding: {},
        },
      ],
    } as unknown as DashboardSchemaV1;
    const snapshot = {
      refreshed_at: '2026-09-19',
      widgets: {
        sales: {
          columns: ['value'],
          rows: Array.from({ length: 100 }, (_, index) => ({ value: index })),
          row_count: 100,
        },
      },
    } as unknown as DashboardSnapshot;
    const context = buildDashboardAssistantContext(schema, { year: '1997' }, snapshot);
    expect(context.filter_values).toEqual({ year: '1997' });
    expect(context.widgets).toMatchObject([
      {
        title: '修改中的收入',
        result: {
          row_count: 100,
          rows_sample: [{ value: 0 }, { value: 1 }, { value: 2 }, { value: 3 }, { value: 4 }, { value: 5 }],
        },
      },
    ]);
    expect(context.result_note).toContain('不是全量数据');
  });
  it('recognizes both scoped and legacy persisted annotation continuations', () => {
    expect(hasDashboardAnnotationWorkflowMarker('[[dashboard-annotation:dashboard-1:annotation-1]] continue')).toBe(
      true,
    );
    expect(hasDashboardAnnotationWorkflowMarker('[[dashboard-annotation:annotation-1]] continue')).toBe(true);
    expect(hasDashboardAnnotationWorkflowMarker('ordinary dashboard request')).toBe(false);
  });

  it('keeps multiple persisted annotations and their intents in one safe prompt', () => {
    const prompt = buildDashboardAssistantPrompt(
      record,
      [
        { annotation: annotation('annotation-modify', 'sales'), intent: 'modify' },
        { annotation: annotation('annotation-explain', 'margin'), intent: 'explain' },
        { annotation: annotation('annotation-anomaly', 'orders'), intent: 'anomaly' },
      ],
      {
        orders: {
          widget_id: 'orders',
          columns: [],
          rows: [],
          row_count: 0,
          truncated: false,
          duration_ms: 0,
          refreshed_at: '2026-08-31T00:00:00Z',
          anomalies: [
            {
              rule_id: 'orders-drop',
              rule_label: '订单下降',
              status: 'anomaly',
              baseline: 'previous_period',
              current_value: 80,
              baseline_value: 100,
              absolute_change: -20,
              change_ratio: -0.2,
              threshold: { mode: 'relative_change', value: 0.1 },
              comparison_time_range: {},
              sample_size: 2,
              matched_rule: 'change_ratio <= -0.1',
            },
          ],
        },
      },
    );

    expect(prompt).toContain('[[dashboard-annotation:dashboard-1:annotation-modify]]');
    expect(prompt).toContain('[[dashboard-annotation:dashboard-1:annotation-explain]]');
    expect(prompt).toContain('[[dashboard-annotation:dashboard-1:annotation-anomaly]]');
    expect(prompt).toContain('annotation_id：annotation-modify');
    expect(prompt).not.toContain('annotation_id：annotation-explain');
    expect(prompt).toContain('程序异常证据（只读）');
    expect(prompt).toContain('"rule_id":"orders-drop"');
    expect(prompt).toContain('不得凭文字猜测、重算、覆盖或改变程序结论');
    expect(prompt).toContain('不得调用任何看板修改工具');
    expect(prompt).toContain('不要直接保存');
  });
});
