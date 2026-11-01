import { describe, expect, it } from 'vitest';
import {
  applyDashboardGenerationToMessages,
  createDashboardGenerationEventGate,
  reduceDashboardGeneration,
  reduceDashboardGenerations,
} from './dashboard-generation-state';

describe('dashboard SSE state reducer', () => {
  it('also blocks imperative navigation for a late created event after timeout', () => {
    const accept = createDashboardGenerationEventGate();
    const identity = { dashboard_id: 'plan', generation_id: 'old' };
    expect(accept({ ...identity, type: 'dashboard.generation.started' })).toBe(true);
    expect(accept({ ...identity, type: 'dashboard.generation.failed' })).toBe(true);
    expect(accept({ ...identity, type: 'dashboard.created' })).toBe(false);
    expect(accept({ ...identity, type: 'dashboard.updated' })).toBe(false);
    expect(accept({ ...identity, type: 'dashboard.generation.started', generation_id: 'new' })).toBe(true);
    expect(accept({ ...identity, type: 'dashboard.generation.failed' })).toBe(false);
    expect(accept({ ...identity, type: 'dashboard.created', generation_id: 'new' })).toBe(true);
  });

  it('replays the persisted timeout as failure, not as a created dashboard', () => {
    const event = JSON.parse(
      JSON.stringify({
        type: 'dashboard.generation.failed',
        dashboard_id: 'plan',
        generation_id: 'run',
        total_widgets: 3,
        validated_widgets: 1,
        validated_widget_ids: ['sales'],
        pending_widget_ids: ['trend', 'stores'],
        message: '超时',
        saved_revision: 2,
        saved_widget_ids: ['sales'],
        editor_path: '/dashboards/plan',
      }),
    );
    const states = reduceDashboardGenerations([], event);
    expect(states).toHaveLength(1);
    expect(states[0]).toMatchObject({
      status: 'failed',
      savedRevision: 2,
      savedWidgetIds: ['sales'],
      validatedWidgets: 1,
    });
  });

  it('keeps trial evidence on timeout and ignores late events from closed and older runs', () => {
    let state = reduceDashboardGeneration(undefined, {
      type: 'dashboard.generation.started',
      dashboard_id: 'plan',
      generation_id: 'old',
      total_widgets: 3,
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.widget.validated',
      widget_id: 'sales',
      generation_id: 'old',
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.generation.failed',
      dashboard_id: 'plan',
      generation_id: 'old',
      message: '超时',
      validated_widget_ids: ['sales'],
      pending_widget_ids: ['trend', 'stores'],
      editor_path: '/dashboards/plan',
    });
    expect(state).toMatchObject({ status: 'failed', validatedWidgets: 1, validatedWidgetIds: ['sales'] });
    for (const type of ['dashboard.widget.validated', 'dashboard.created', 'dashboard.plan.completed']) {
      expect(reduceDashboardGeneration(state, { type, widget_id: 'trend', generation_id: 'old' })).toBe(state);
    }
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.generation.started',
      dashboard_id: 'plan',
      generation_id: 'new',
    });
    expect(state).toMatchObject({ status: 'generating', validatedWidgets: 0, generationId: 'new' });
    expect(state?.validatedWidgetIds).toBeUndefined();
    expect(
      reduceDashboardGeneration(state, {
        type: 'dashboard.generation.failed',
        generation_id: 'old',
        message: '旧超时',
      }),
    ).toBe(state);
  });

  it('carries only the matching card into the active SQL round, preserving other boards and history', () => {
    const plan = reduceDashboardGeneration(undefined, {
      type: 'dashboard.plan.awaiting_confirmation',
      dashboard_id: 'plan-a',
      current_revision: 1,
    })!;
    const other = { ...plan, dashboardId: 'plan-b' };
    const messages = [
      { id: 'old', role: 'view', context: '旧总结', dashboardGenerations: [plan, other] },
      { id: 'new', role: 'view', context: '', dashboardGenerations: [] },
    ];
    const moved = applyDashboardGenerationToMessages(messages, 'new', {
      type: 'dashboard.generation.started',
      dashboard_id: 'plan-a',
      current_revision: 1,
    });
    expect(moved[0].context).toBe('旧总结');
    expect(moved[0].dashboardGenerations.map(item => item.dashboardId)).toEqual(['plan-b']);
    expect(moved[1].dashboardGenerations).toHaveLength(1);
    expect(moved[1].dashboardGenerations[0]).toMatchObject({ dashboardId: 'plan-a', status: 'generating' });
    const done = applyDashboardGenerationToMessages(moved, 'new', {
      type: 'dashboard.created',
      dashboard_id: 'plan-a',
    });
    expect(done[1].dashboardGenerations).toHaveLength(1);
    expect(done[1].dashboardGenerations[0].status).toBe('created');
    expect(messages[0].dashboardGenerations).toHaveLength(2);
  });

  it('starts confirmation SQL in a new round and updates the existing plan card', () => {
    let states = reduceDashboardGenerations([], {
      type: 'dashboard.plan.awaiting_confirmation',
      dashboard_id: 'bound',
      source_turn_id: 'planning-turn',
      current_revision: 3,
      total_widgets: 2,
      confirmation_prompt: 'confirm revision 3',
    });
    states = reduceDashboardGenerations(states, {
      type: 'dashboard.generation.started',
      dashboard_id: 'bound',
      source_turn_id: 'planning-turn',
      current_revision: 3,
      title: 'Confirmed plan',
      total_widgets: 2,
    });
    expect(states).toHaveLength(1);
    expect(states[0]).toMatchObject({ status: 'generating', currentRevision: 3, totalWidgets: 2 });
    expect(states[0].confirmationPrompt).toBeUndefined();
    expect(
      reduceDashboardGenerations([], {
        type: 'dashboard.generation.started',
        dashboard_id: 'bound',
        current_revision: 3,
        total_widgets: 2,
      })[0],
    ).toMatchObject({ status: 'generating', dashboardId: 'bound' });
    states = reduceDashboardGenerations(states, {
      type: 'dashboard.created',
      dashboard_id: 'bound',
      validated_widgets: 2,
    });
    expect(states).toHaveLength(1);
    expect(states[0]).toMatchObject({ status: 'created', dashboardId: 'bound', validatedWidgets: 2 });
  });

  it('ends incomplete generation visibly without fabricating a created asset', () => {
    const state = reduceDashboardGeneration(undefined, {
      type: 'dashboard.generation.failed',
      dashboard_id: 'failed',
      message: '本次生成未完成',
    });
    expect(state).toMatchObject({ status: 'failed', dashboardId: 'failed', errorMessage: '本次生成未完成' });
    expect(state?.editorPath).toBeUndefined();
    expect(state?.validatedWidgets).toBe(0);
  });

  it('tracks plan, independent widget outcomes, and the editor link', () => {
    let state = reduceDashboardGeneration(undefined, {
      type: 'dashboard.plan.started',
      title: 'Walmart overview',
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.plan.completed',
      title: 'Walmart overview',
      total_widgets: 2,
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.widget.validated',
      widget_id: 'sales-kpi',
      title: 'Total sales',
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.widget.failed',
      widget_id: 'broken-chart',
      title: 'Broken chart',
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.created',
      dashboard_id: 'dashboard-1',
      title: 'Walmart overview',
      total_widgets: 2,
      validated_widgets: 1,
      failed_widgets: 1,
      editor_path: '/dashboards/dashboard-1',
    });

    expect(state).toMatchObject({
      status: 'created',
      dashboardId: 'dashboard-1',
      editorPath: '/dashboards/dashboard-1',
      totalWidgets: 2,
      validatedWidgets: 1,
      failedWidgets: 1,
    });
  });

  it('ignores widget events until a plan has started', () => {
    expect(
      reduceDashboardGeneration(undefined, {
        type: 'dashboard.widget.validated',
        widget_id: 'orphan',
      }),
    ).toBeUndefined();
  });

  it('keeps the plan paused until confirmation and tracks later updates', () => {
    let state = reduceDashboardGeneration(undefined, {
      type: 'dashboard.plan.started',
      title: 'Review me',
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.plan.awaiting_confirmation',
      dashboard_id: 'plan-1',
      current_revision: 1,
      confirmation_prompt: '[[confirm-dashboard:plan-1]] confirm',
      revision_prompt: '[[revise-dashboard-plan:plan-1]] revise: ',
      plan: { metrics: ['sales'], widgets: [{ id: 'sales', title: 'Sales', type: 'kpi' }] },
    });
    state = reduceDashboardGeneration(state, {
      type: 'dashboard.plan.completed',
      total_widgets: 1,
    });
    expect(state).toMatchObject({
      status: 'awaiting_confirmation',
      dashboardId: 'plan-1',
      currentRevision: 1,
    });

    const updated = reduceDashboardGeneration(undefined, {
      type: 'dashboard.updated',
      dashboard_id: 'plan-1',
      title: 'Updated by Agent',
      total_widgets: 1,
      current_revision: 3,
      editor_path: '/dashboards/plan-1',
    });
    expect(updated).toMatchObject({
      status: 'created',
      dashboardId: 'plan-1',
      currentRevision: 3,
    });
  });

  it('keeps dashboards from different task turns as separate cards', () => {
    let states = reduceDashboardGenerations([], {
      type: 'dashboard.plan.started',
      title: 'Sales dashboard',
      source_turn_id: 'turn-sales',
    });
    states = reduceDashboardGenerations(states, {
      type: 'dashboard.created',
      dashboard_id: 'dashboard-sales',
      title: 'Sales dashboard',
      source_turn_id: 'turn-sales',
      asset_state: 'generated',
    });
    states = reduceDashboardGenerations(states, {
      type: 'dashboard.created',
      dashboard_id: 'dashboard-profit',
      title: 'Profit dashboard',
      source_turn_id: 'turn-profit',
      asset_state: 'generated',
    });
    states = reduceDashboardGenerations(states, {
      type: 'dashboard.updated',
      dashboard_id: 'dashboard-sales',
      title: 'Updated sales dashboard',
      source_turn_id: 'turn-sales',
      asset_state: 'saved',
      current_revision: 2,
    });

    expect(states).toHaveLength(2);
    expect(states[0]).toMatchObject({
      dashboardId: 'dashboard-sales',
      sourceTurnId: 'turn-sales',
      assetState: 'saved',
      currentRevision: 2,
    });
    expect(states[1]).toMatchObject({
      dashboardId: 'dashboard-profit',
      sourceTurnId: 'turn-profit',
      assetState: 'generated',
    });
  });
});
