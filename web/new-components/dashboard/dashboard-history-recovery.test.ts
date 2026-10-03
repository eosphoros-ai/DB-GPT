import type { DashboardListItem } from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import { dashboardGenerationFromHistoryRef, enrichHistoryWithDashboardRefs } from './dashboard-history-recovery';

const dashboard = (overrides: Partial<DashboardListItem> = {}): DashboardListItem => ({
  id: 'dashboard-sales',
  title: '销售看板',
  description: '',
  data_source_id: 'sales',
  conversation_id: 'conversation-1',
  source_turn_id: 'turn-sales',
  origin: 'task',
  asset_state: 'saved',
  saved_at: '2026-08-24T00:00:00Z',
  current_revision: 3,
  status: 'draft',
  updated_at: '2026-08-24T00:00:00Z',
  ...overrides,
});

const view = (finalContent: string, sourceTurnId?: string) => ({
  role: 'view',
  context: JSON.stringify({
    version: 1,
    type: 'react-agent',
    final_content: finalContent,
    steps: sourceTurnId ? [{ id: 'step', source_turn_id: sourceTurnId }] : [],
    dashboard_refs: [],
  }),
});

describe('enrichHistoryWithDashboardRefs', () => {
  it('recovers a dashboard card from the asset table', () => {
    const result = enrichHistoryWithDashboardRefs([view('完成', 'turn-sales')], [dashboard()]);
    const payload = JSON.parse(result[0].context);

    expect(payload.dashboard_refs).toEqual([
      expect.objectContaining({
        dashboard_id: 'dashboard-sales',
        source_turn_id: 'turn-sales',
        current_revision: 3,
        editor_path: '/dashboards/dashboard-sales',
      }),
    ]);
  });

  it('keeps multiple dashboards on their matching Agent rounds', () => {
    const result = enrichHistoryWithDashboardRefs(
      [view('销售', 'turn-sales'), view('利润', 'turn-profit')],
      [dashboard(), dashboard({ id: 'dashboard-profit', source_turn_id: 'turn-profit', title: '利润看板' })],
    );

    expect(JSON.parse(result[0].context).dashboard_refs[0].dashboard_id).toBe('dashboard-sales');
    expect(JSON.parse(result[1].context).dashboard_refs[0].dashboard_id).toBe('dashboard-profit');
  });

  it('does not duplicate references already persisted in history', () => {
    const message = view('完成', 'turn-sales');
    const payload = JSON.parse(message.context);
    payload.dashboard_refs = [{ dashboard_id: 'dashboard-sales', title: '已有看板' }];
    message.context = JSON.stringify(payload);

    const result = enrichHistoryWithDashboardRefs([message], [dashboard()]);
    expect(JSON.parse(result[0].context).dashboard_refs).toHaveLength(1);
  });

  it('falls back to the last structured answer for legacy records without a source turn', () => {
    const result = enrichHistoryWithDashboardRefs(
      [view('第一轮'), view('最后一轮')],
      [dashboard({ source_turn_id: null })],
    );

    expect(JSON.parse(result[0].context).dashboard_refs).toEqual([]);
    expect(JSON.parse(result[1].context).dashboard_refs[0].dashboard_id).toBe('dashboard-sales');
  });
});

describe('dashboardGenerationFromHistoryRef', () => {
  it('restores an awaiting-confirmation plan without claiming widget validation', () => {
    const state = dashboardGenerationFromHistoryRef({
      dashboard_id: 'dashboard-pending',
      title: '待确认看板',
      status: 'awaiting_confirmation',
      data_source_id: 'olist_ecommerce_demo',
      current_revision: 1,
      total_widgets: 2,
      validated_widgets: 2,
      confirmation_prompt: '[[confirm-dashboard:dashboard-pending]] confirm',
      revision_prompt: '[[revise-dashboard-plan:dashboard-pending]] revise: ',
      plan: {
        business_theme: '履约',
        widgets: [
          { id: 'orders', title: '订单', type: 'kpi' },
          { id: 'delivery', title: '履约', type: 'line' },
        ],
      },
    });

    expect(state).toEqual(
      expect.objectContaining({
        status: 'awaiting_confirmation',
        totalWidgets: 2,
        validatedWidgets: 0,
        confirmationPrompt: '[[confirm-dashboard:dashboard-pending]] confirm',
      }),
    );
    expect(state?.plan?.widgets).toHaveLength(2);
  });

  it('does not expose a broken confirmation state when old history lacks its plan', () => {
    expect(
      dashboardGenerationFromHistoryRef({
        dashboard_id: 'legacy-pending',
        status: 'awaiting_confirmation',
      })?.status,
    ).toBe('created');
  });
});
