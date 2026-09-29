import type { DashboardGenerationState, DashboardWidgetGenerationStatus } from './DashboardGenerationCard';

export interface DashboardGenerationEvent {
  type: string;
  title?: string;
  widget_id?: string;
  total_widgets?: number;
  validated_widgets?: number;
  failed_widgets?: number;
  dashboard_id?: string;
  source_turn_id?: string;
  asset_state?: 'generated' | 'saved';
  editor_path?: string;
  data_source_id?: string;
  current_revision?: number;
  confirmation_prompt?: string;
  revision_prompt?: string;
  message?: string;
  summary?: string;
  generation_id?: string;
  limit_seconds?: number;
  stage_label?: string;
  stage?: string;
  validated_widget_ids?: string[];
  pending_widget_ids?: string[];
  saved_widget_ids?: string[];
  saved_revision?: number;
  retry_hint?: string;
  plan?: DashboardGenerationState['plan'];
}

/** Gate imperative page effects as well as React state updates for one SSE run. */
export const createDashboardGenerationEventGate = () => {
  const runs = new Map<string, { id?: string; closed: boolean }>();
  return (event: DashboardGenerationEvent): boolean => {
    const key = event.dashboard_id || event.source_turn_id;
    if (!key) return true;
    if (event.type === 'dashboard.generation.started') {
      runs.set(key, { id: event.generation_id, closed: false });
      return true;
    }
    const run = runs.get(key);
    if (run?.id && event.generation_id && run.id !== event.generation_id) return false;
    if (
      run?.closed &&
      (event.type.startsWith('dashboard.widget.') ||
        event.type === 'dashboard.created' ||
        event.type === 'dashboard.updated' ||
        event.type === 'dashboard.generation.progress' ||
        event.type === 'dashboard.plan.completed')
    )
      return false;
    if (event.type === 'dashboard.generation.failed') {
      runs.set(key, { id: event.generation_id || run?.id, closed: true });
    }
    return true;
  };
};

export const reduceDashboardGeneration = (
  current: DashboardGenerationState | undefined,
  event: DashboardGenerationEvent,
): DashboardGenerationState | undefined => {
  // A closed run stays closed; late events cannot revive its spinner or erase
  // the next run's progress. A user-initiated start acquires a new generation id.
  if (
    event.type !== 'dashboard.generation.started' &&
    event.generation_id &&
    current?.generationId &&
    event.generation_id !== current.generationId
  )
    return current;
  if (
    current?.status === 'failed' &&
    (event.type.startsWith('dashboard.widget.') ||
      event.type === 'dashboard.generation.progress' ||
      event.type === 'dashboard.created' ||
      event.type === 'dashboard.plan.completed')
  )
    return current;
  if (event.type === 'dashboard.generation.started' || event.type === 'dashboard.generation.failed') {
    const failed = event.type === 'dashboard.generation.failed';
    return {
      ...current,
      status: event.type === 'dashboard.generation.failed' ? 'failed' : 'generating',
      title: event.title || current?.title || '数据看板',
      totalWidgets: Number(event.total_widgets ?? current?.totalWidgets ?? 0),
      validatedWidgets: failed ? (event.validated_widgets ?? current?.validatedWidgets ?? 0) : 0,
      failedWidgets: failed ? (event.failed_widgets ?? current?.failedWidgets ?? 0) : 0,
      widgetStates: failed ? current?.widgetStates || {} : {},
      activeWidgetTitle: undefined,
      dashboardId: event.dashboard_id || current?.dashboardId,
      sourceTurnId: event.source_turn_id || current?.sourceTurnId,
      dataSourceId: event.data_source_id || current?.dataSourceId,
      currentRevision: event.current_revision ?? current?.currentRevision,
      confirmationPrompt: undefined,
      revisionPrompt: failed ? event.revision_prompt : undefined,
      errorMessage: failed ? event.summary || event.message : undefined,
      generationId: event.generation_id || current?.generationId,
      limitSeconds: event.limit_seconds ?? current?.limitSeconds,
      stageLabel: failed ? event.stage_label : undefined,
      validatedWidgetIds: failed ? event.validated_widget_ids : undefined,
      pendingWidgetIds: failed ? event.pending_widget_ids : undefined,
      savedWidgetIds: failed ? event.saved_widget_ids : undefined,
      savedRevision: failed ? event.saved_revision : undefined,
      retryHint: failed ? event.retry_hint : undefined,
      editorPath: failed ? event.editor_path || current?.editorPath : undefined,
      plan: event.plan || current?.plan,
    };
  }
  if (event.type === 'dashboard.plan.started') {
    return {
      status: 'planning',
      title: event.title || '正在生成数据看板',
      totalWidgets: 0,
      validatedWidgets: 0,
      failedWidgets: 0,
      widgetStates: {},
      sourceTurnId: event.source_turn_id,
    };
  }
  if (event.type === 'dashboard.plan.awaiting_confirmation') {
    return {
      ...(current || {
        status: 'planning' as const,
        title: event.title || '数据看板计划',
        totalWidgets: 0,
        validatedWidgets: 0,
        failedWidgets: 0,
        widgetStates: {},
      }),
      status: 'awaiting_confirmation',
      title: event.title || current?.title || '数据看板计划',
      totalWidgets: Number(event.total_widgets || event.plan?.widgets?.length || 0),
      dashboardId: event.dashboard_id,
      sourceTurnId: event.source_turn_id || current?.sourceTurnId,
      assetState: event.asset_state || current?.assetState,
      dataSourceId: event.data_source_id,
      currentRevision: Number(event.current_revision || 1),
      confirmationPrompt: event.confirmation_prompt,
      revisionPrompt: event.revision_prompt,
      plan: event.plan,
    };
  }
  if (event.type === 'dashboard.updated') {
    return {
      ...(current || {
        status: 'created' as const,
        title: event.title || '数据看板已更新',
        totalWidgets: Number(event.total_widgets || 0),
        validatedWidgets: Number(event.total_widgets || 0),
        failedWidgets: 0,
        widgetStates: {},
      }),
      status: 'created',
      title: event.title || current?.title || '数据看板已更新',
      totalWidgets: Number(event.total_widgets || current?.totalWidgets || 0),
      dashboardId: event.dashboard_id,
      sourceTurnId: event.source_turn_id || current?.sourceTurnId,
      assetState: event.asset_state || current?.assetState,
      editorPath: event.editor_path || `/dashboards/${event.dashboard_id}`,
      currentRevision: Number(event.current_revision || current?.currentRevision || 1),
    };
  }
  if (!current) return undefined;
  if (event.type === 'dashboard.generation.progress') return current;
  if (event.type === 'dashboard.plan.completed') {
    return {
      ...current,
      status: current.status === 'awaiting_confirmation' ? current.status : 'generating',
      title: event.title || current.title,
      totalWidgets: Number(event.total_widgets || 0),
    };
  }
  if (
    event.type === 'dashboard.widget.started' ||
    event.type === 'dashboard.widget.validated' ||
    event.type === 'dashboard.widget.failed'
  ) {
    const widgetId = String(event.widget_id || 'unknown');
    const nextStatus: DashboardWidgetGenerationStatus =
      event.type === 'dashboard.widget.started'
        ? 'running'
        : event.type === 'dashboard.widget.validated'
          ? 'validated'
          : 'failed';
    const widgetStates = { ...current.widgetStates, [widgetId]: nextStatus };
    const values = Object.values(widgetStates);
    return {
      ...current,
      status: 'generating',
      activeWidgetTitle: event.title || current.activeWidgetTitle,
      totalWidgets: Number(event.total_widgets || current.totalWidgets),
      validatedWidgets: values.filter(value => value === 'validated').length,
      failedWidgets: values.filter(value => value === 'failed').length,
      widgetStates,
    };
  }
  if (event.type === 'dashboard.created') {
    return {
      ...current,
      status: 'created',
      title: event.title || current.title,
      totalWidgets: Number(event.total_widgets || current.totalWidgets),
      validatedWidgets: Number(event.validated_widgets ?? current.validatedWidgets),
      failedWidgets: Number(event.failed_widgets ?? current.failedWidgets),
      dashboardId: event.dashboard_id,
      sourceTurnId: event.source_turn_id || current.sourceTurnId,
      assetState: event.asset_state || current.assetState || 'generated',
      editorPath: event.editor_path || `/dashboards/${event.dashboard_id}`,
    };
  }
  return current;
};

const matchesGeneration = (state: DashboardGenerationState, event: DashboardGenerationEvent) => {
  if (event.dashboard_id && state.dashboardId === event.dashboard_id) return true;
  return Boolean(event.source_turn_id && state.sourceTurnId === event.source_turn_id);
};

/** Keep separate Dashboard cards when one task turn creates or updates more than one board. */
export const reduceDashboardGenerations = (
  current: DashboardGenerationState[],
  event: DashboardGenerationEvent,
): DashboardGenerationState[] => {
  const index = current.findIndex(state => matchesGeneration(state, event));
  const seed =
    index >= 0
      ? current[index]
      : event.type === 'dashboard.created' || event.type === 'dashboard.updated'
        ? {
            status: 'generating' as const,
            title: event.title || '数据看板',
            totalWidgets: Number(event.total_widgets || 0),
            validatedWidgets: Number(event.validated_widgets || 0),
            failedWidgets: Number(event.failed_widgets || 0),
            widgetStates: {},
            sourceTurnId: event.source_turn_id,
          }
        : undefined;
  const next = reduceDashboardGeneration(seed, event);
  if (!next) return current;
  if (index < 0) return [...current, next];
  return current.map((state, stateIndex) => (stateIndex === index ? next : state));
};

type GenerationMessage = {
  id?: string;
  role: string;
  dashboardGeneration?: DashboardGenerationState;
  dashboardGenerations?: DashboardGenerationState[];
};

/** Carry the same card into the SQL turn; the previous round auto-collapses. */
export const applyDashboardGenerationToMessages = <T extends GenerationMessage>(
  messages: T[],
  responseId: string,
  event: DashboardGenerationEvent,
): T[] => {
  const statesOf = (message: T) =>
    message.dashboardGenerations || (message.dashboardGeneration ? [message.dashboardGeneration] : []);
  const source = messages.find(
    message => message.role === 'view' && statesOf(message).some(state => matchesGeneration(state, event)),
  );
  const move = event.type === 'dashboard.generation.started' && source?.id !== responseId;
  const targetId = move ? responseId : source?.id || responseId;
  const carried = move && source ? statesOf(source).filter(state => matchesGeneration(state, event)) : [];
  return messages.map(message => {
    if (message.role !== 'view') return message;
    if (message.id === targetId)
      return {
        ...message,
        dashboardGeneration: undefined,
        dashboardGenerations: reduceDashboardGenerations([...statesOf(message), ...carried], event),
      };
    if (move && message.id === source?.id)
      return {
        ...message,
        dashboardGeneration: undefined,
        dashboardGenerations: statesOf(message).filter(state => !matchesGeneration(state, event)),
      };
    return message;
  });
};
