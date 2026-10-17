import type { DashboardListItem } from '@/types/dashboard';
import type { DashboardGenerationState } from './DashboardGenerationCard';

type HistoryMessage = {
  role: string;
  context: string;
  order?: number;
  model_name?: string;
};

const asDashboardRef = (dashboard: DashboardListItem) => ({
  dashboard_id: dashboard.id,
  title: dashboard.title,
  conversation_id: dashboard.conversation_id,
  source_turn_id: dashboard.source_turn_id,
  status: dashboard.status,
  data_source_id: dashboard.data_source_id,
  asset_state: dashboard.asset_state,
  current_revision: dashboard.current_revision,
  editor_path: `/dashboards/${dashboard.id}`,
});

export const dashboardGenerationFromHistoryRef = (ref: any): DashboardGenerationState | null => {
  if (typeof ref?.dashboard_id !== 'string') return null;

  const hasPendingPlan =
    ref.status === 'awaiting_confirmation' &&
    ref.plan &&
    typeof ref.plan === 'object' &&
    typeof ref.confirmation_prompt === 'string';
  const totalWidgets = Number(ref.total_widgets || ref.plan?.widgets?.length || 0);

  return {
    status: hasPendingPlan ? 'awaiting_confirmation' : 'created',
    title: ref.title || '数据看板',
    totalWidgets,
    validatedWidgets: hasPendingPlan ? 0 : Number(ref.validated_widgets || totalWidgets),
    failedWidgets: Number(ref.failed_widgets || 0),
    widgetStates: {},
    dashboardId: ref.dashboard_id,
    sourceTurnId: ref.source_turn_id,
    assetState: ref.asset_state === 'saved' ? 'saved' : 'generated',
    dataSourceId: ref.data_source_id,
    currentRevision: Number(ref.current_revision || 1),
    editorPath: ref.editor_path || `/dashboards/${ref.dashboard_id}`,
    confirmationPrompt: hasPendingPlan ? ref.confirmation_prompt : undefined,
    revisionPrompt: hasPendingPlan ? ref.revision_prompt : undefined,
    plan: hasPendingPlan ? ref.plan : undefined,
  };
};

/**
 * Restore dashboard cards from the dashboard asset table when an older final
 * chat message did not persist `dashboard_refs`.
 *
 * A source turn id is used first so multiple dashboards in one conversation
 * stay attached to the correct Agent round.  Older records without that id are
 * attached to the last React-Agent answer instead of being silently lost.
 */
export const enrichHistoryWithDashboardRefs = (
  historyMessages: HistoryMessage[],
  dashboards: DashboardListItem[],
): HistoryMessage[] => {
  if (dashboards.length === 0) return historyMessages;

  const next = historyMessages.map(message => ({ ...message }));
  const payloads = new Map<number, Record<string, any>>();
  const existingDashboardIds = new Set<string>();

  next.forEach((message, index) => {
    if (message.role !== 'view') return;
    try {
      const payload = JSON.parse(message.context);
      if (payload?.version !== 1 || payload?.type !== 'react-agent') return;
      payloads.set(index, payload);
      for (const ref of Array.isArray(payload.dashboard_refs) ? payload.dashboard_refs : []) {
        if (typeof ref?.dashboard_id === 'string') existingDashboardIds.add(ref.dashboard_id);
      }
    } catch {
      // A legacy plain-text answer cannot host the structured dashboard card.
    }
  });

  const fallbackIndex = [...payloads.keys()].at(-1);
  if (fallbackIndex === undefined) return historyMessages;

  for (const dashboard of dashboards) {
    if (existingDashboardIds.has(dashboard.id)) continue;
    const sourceTurnId = dashboard.source_turn_id;
    const targetIndex =
      (sourceTurnId
        ? [...payloads.keys()].reverse().find(index => next[index].context.includes(sourceTurnId))
        : undefined) ?? fallbackIndex;
    const payload = payloads.get(targetIndex);
    if (!payload) continue;
    payload.dashboard_refs = [
      ...(Array.isArray(payload.dashboard_refs) ? payload.dashboard_refs : []),
      asDashboardRef(dashboard),
    ];
    existingDashboardIds.add(dashboard.id);
  }

  for (const [index, payload] of payloads) {
    next[index] = { ...next[index], context: JSON.stringify(payload) };
  }
  return next;
};
