import {
  DashboardAnnotationApplyResponse,
  DashboardAnnotationIntent,
  DashboardAnnotationIntentResolution,
  DashboardAnnotationRecord,
  DashboardArtifactBundle,
  DashboardAssetState,
  DashboardAssistantContext,
  DashboardAuditRecord,
  DashboardCollaborationTicket,
  DashboardEditVersionDetail,
  DashboardEditVersionRecord,
  DashboardListItem,
  DashboardListPage,
  DashboardMemberRecord,
  DashboardOperationLogRecord,
  DashboardOperationRequest,
  DashboardOperationResponse,
  DashboardOrigin,
  DashboardPermissionRecord,
  DashboardPublishResponse,
  DashboardQueryLogic,
  DashboardRecord,
  DashboardRevisionRecord,
  DashboardRole,
  DashboardSchedule,
  DashboardScheduleCreate,
  DashboardScheduleRun,
  DashboardScheduleUpdate,
  DashboardSchemaV1,
  DashboardSelectionTarget,
  DashboardShareRecord,
  DashboardSnapshot,
  DashboardStatus,
  DashboardTargetResolution,
  DashboardValidationResult,
  DashboardWidgetResult,
  PublicDashboardFilterResponse,
  PublicDashboardSnapshot,
} from '@/types/dashboard';
import { DELETE, GET, POST, PUT } from '../index';

const PREFIX = '/api/v1/dashboards';
export const ensureDashboardAssistantTask = (id: string) =>
  POST<Record<string, never>, { conversation_id: string }>(`${PREFIX}/${id}/assistant-task`, {});

export const getDashboardJsonSchema = () => GET<null, Record<string, unknown>>(`${PREFIX}/schema`);

export interface DashboardListParams {
  search?: string;
  folder_id?: string;
  status?: DashboardStatus;
  conversation_id?: string;
  origin?: DashboardOrigin;
  exclude_origin?: DashboardOrigin;
  asset_state?: DashboardAssetState;
  include_generated?: boolean;
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}

export const listDashboards = (params: Omit<DashboardListParams, 'search' | 'limit' | 'offset'> = {}) =>
  GET<typeof params, DashboardListItem[]>(PREFIX, params);

export const pageDashboards = (params: DashboardListParams) =>
  GET<typeof params, DashboardListPage>(`${PREFIX}/page`, params);

export const getDashboard = (dashboardId: string) => GET<null, DashboardRecord>(`${PREFIX}/${dashboardId}`);

export const resolveDashboardTarget = (dashboardId: string, reference: string, selectedWidgetId?: string | null) =>
  POST<{ reference: string; selected_widget_id?: string }, DashboardTargetResolution>(
    `${PREFIX}/${dashboardId}/resolve-target`,
    {
      reference,
      ...(selectedWidgetId ? { selected_widget_id: selectedWidgetId } : {}),
    },
  );

export const getDashboardArtifacts = (dashboardId: string) =>
  GET<null, DashboardArtifactBundle>(`${PREFIX}/${dashboardId}/artifacts`);

export const exportDashboardProject = (dashboardId: string) =>
  GET<null, Blob>(`${PREFIX}/${dashboardId}/export`, undefined, { responseType: 'blob' });

export const getLatestDashboardSnapshot = (dashboardId: string) =>
  GET<null, DashboardSnapshot>(`${PREFIX}/${dashboardId}/snapshot`);

export const createDashboard = (
  schema: DashboardSchemaV1,
  conversationId?: string,
  options: { origin?: DashboardOrigin; asset_state?: DashboardAssetState; source_turn_id?: string } = {},
) =>
  POST<
    {
      schema: DashboardSchemaV1;
      conversation_id?: string;
      source_turn_id?: string;
      origin?: DashboardOrigin;
      asset_state?: DashboardAssetState;
    },
    DashboardRecord
  >(PREFIX, {
    schema,
    conversation_id: conversationId,
    ...options,
  });

export const updateDashboard = (dashboardId: string, schema: DashboardSchemaV1, expectedRevision: number) =>
  PUT<{ schema: DashboardSchemaV1; expected_revision: number }, DashboardRecord>(`${PREFIX}/${dashboardId}`, {
    schema,
    expected_revision: expectedRevision,
  });

export const copyDashboard = (dashboardId: string, title?: string) =>
  POST<{ title?: string }, DashboardRecord>(`${PREFIX}/${dashboardId}/copy`, title ? { title } : {});

export const archiveDashboard = (dashboardId: string, expectedRevision: number) =>
  POST<{ expected_revision: number }, DashboardRecord>(`${PREFIX}/${dashboardId}/archive`, {
    expected_revision: expectedRevision,
  });

export const restoreDashboard = (dashboardId: string, expectedRevision: number) =>
  POST<{ expected_revision: number }, DashboardRecord>(`${PREFIX}/${dashboardId}/restore`, {
    expected_revision: expectedRevision,
  });

export const listDashboardEditVersions = (dashboardId: string, limit = 200, offset = 0) =>
  GET<{ limit: number; offset: number }, DashboardEditVersionRecord[]>(`${PREFIX}/${dashboardId}/versions`, {
    limit,
    offset,
  });

export const getDashboardEditVersion = (dashboardId: string, revision: number) =>
  GET<null, DashboardEditVersionDetail>(`${PREFIX}/${dashboardId}/versions/${revision}`);

export const restoreDashboardEditVersion = (dashboardId: string, revision: number, expectedRevision: number) =>
  POST<{ expected_revision: number }, DashboardRecord>(`${PREFIX}/${dashboardId}/versions/${revision}/restore`, {
    expected_revision: expectedRevision,
  });

export const listDashboardRevisions = (dashboardId: string) =>
  GET<null, DashboardRevisionRecord[]>(`${PREFIX}/${dashboardId}/revisions`);

export const restoreDashboardRevision = (dashboardId: string, publishedRevision: number, expectedRevision: number) =>
  POST<{ expected_revision: number }, DashboardRecord>(
    `${PREFIX}/${dashboardId}/revisions/${publishedRevision}/restore`,
    { expected_revision: expectedRevision },
  );

export const applyDashboardOperation = (dashboardId: string, request: DashboardOperationRequest) =>
  POST<DashboardOperationRequest, DashboardOperationResponse>(`${PREFIX}/${dashboardId}/operations`, request);

export const listDashboardOperations = (dashboardId: string, afterRevision = 0, limit = 200) =>
  GET<{ after_revision: number; limit: number }, DashboardOperationLogRecord[]>(`${PREFIX}/${dashboardId}/operations`, {
    after_revision: afterRevision,
    limit,
  });

export const listDashboardAnnotations = (dashboardId: string, limit = 100, offset = 0) =>
  GET<{ limit: number; offset: number }, DashboardAnnotationRecord[]>(`${PREFIX}/${dashboardId}/annotations`, {
    limit,
    offset,
  });

export const resolveDashboardAnnotationIntents = (
  dashboardId: string,
  items: Array<{ draft_id: string; prompt: string; target: DashboardSelectionTarget }>,
  model?: string,
  context: DashboardAssistantContext = {},
  signal?: AbortSignal,
) =>
  POST<{ items: typeof items; model?: string } & DashboardAssistantContext, DashboardAnnotationIntentResolution>(
    `${PREFIX}/${dashboardId}/annotation-intents`,
    { items, ...(model ? { model } : {}), ...context },
    { signal },
  );

export const getDashboardQueryLogic = (dashboardId: string, sql: string, dataSourceId: string) =>
  POST<{ sql: string; data_source_id: string }, DashboardQueryLogic>(`${PREFIX}/${dashboardId}/query-logic`, {
    sql,
    data_source_id: dataSourceId,
  });

export const createDashboardAnnotation = (
  dashboardId: string,
  request: {
    base_revision: number;
    target: DashboardSelectionTarget;
    prompt: string;
    intent: DashboardAnnotationIntent;
    conversation_id?: string;
    source_turn_id?: string;
  },
) => POST<typeof request, DashboardAnnotationRecord>(`${PREFIX}/${dashboardId}/annotations`, request);

export const generateDashboardAnnotationProposal = (
  dashboardId: string,
  annotationId: string,
  model?: string,
  signal?: AbortSignal,
  userPrompt?: string,
) =>
  POST<{ model?: string; user_prompt?: string }, DashboardAnnotationRecord>(
    `${PREFIX}/${dashboardId}/annotations/${annotationId}/generate`,
    { ...(model ? { model } : {}), ...(userPrompt ? { user_prompt: userPrompt } : {}) },
    { signal, timeout: 400000 },
  );

export const applyDashboardAnnotation = (
  dashboardId: string,
  annotationId: string,
  request: { expected_revision: number; operation_id: string; client_id: string },
) =>
  POST<typeof request, DashboardAnnotationApplyResponse>(
    `${PREFIX}/${dashboardId}/annotations/${annotationId}/apply`,
    request,
  );

export const rejectDashboardAnnotation = (dashboardId: string, annotationId: string) =>
  POST<Record<string, never>, DashboardAnnotationRecord>(
    `${PREFIX}/${dashboardId}/annotations/${annotationId}/reject`,
    {},
  );

export const applyDashboardAnnotationBatch = (id: string, annotation_ids: string[], expected_revision: number) =>
  POST<
    { annotation_ids: string[]; expected_revision: number; operation_id: string; client_id: string },
    { annotations: DashboardAnnotationRecord[]; operation: DashboardOperationResponse }
  >(`${PREFIX}/${id}/annotations/apply-batch`, {
    annotation_ids,
    expected_revision,
    operation_id: `annotation-batch-${crypto.randomUUID()}`,
    client_id: `dashboard-editor-${id}`,
  });

export const createDashboardCollaborationTicket = (dashboardId: string, clientId: string) =>
  POST<{ client_id: string }, DashboardCollaborationTicket>(`${PREFIX}/${dashboardId}/collaboration-ticket`, {
    client_id: clientId,
  });

export const validateDashboard = (
  dashboardId: string,
  schema: DashboardSchemaV1,
  filters: Record<string, unknown>,
  executeQueries = true,
  requirePublicationBindings = false,
) =>
  POST<
    {
      schema: DashboardSchemaV1;
      filters: Record<string, unknown>;
      execute_queries: boolean;
      require_publication_bindings: boolean;
    },
    DashboardValidationResult
  >(`${PREFIX}/${dashboardId}/validate`, {
    schema,
    filters,
    execute_queries: executeQueries,
    require_publication_bindings: requirePublicationBindings,
  });

export const previewDashboardWidget = (
  dashboardId: string,
  widgetId: string,
  filters: Record<string, unknown>,
  schema: DashboardSchemaV1,
) =>
  POST<{ filters: Record<string, unknown>; schema: DashboardSchemaV1 }, DashboardWidgetResult>(
    `${PREFIX}/${dashboardId}/widgets/${widgetId}/preview`,
    { filters, schema },
  );

export const refreshDashboard = (dashboardId: string, filters: Record<string, unknown>) =>
  POST<{ filters: Record<string, unknown> }, DashboardSnapshot>(`${PREFIX}/${dashboardId}/refresh`, { filters });

export const publishDashboard = (
  dashboardId: string,
  expectedRevision: number,
  filters: Record<string, unknown>,
  allowStaticWidgets = false,
) =>
  POST<
    { expected_revision: number; filters: Record<string, unknown>; allow_static_widgets: boolean },
    DashboardPublishResponse
  >(`${PREFIX}/${dashboardId}/publish`, {
    expected_revision: expectedRevision,
    filters,
    allow_static_widgets: allowStaticWidgets,
  });

export const listDashboardPublications = (dashboardId: string) =>
  GET<null, DashboardShareRecord[]>(`${PREFIX}/${dashboardId}/publications`);

export const rotateDashboardPublication = (
  dashboardId: string,
  publishedRevision: number,
  shareExpiresInSeconds?: number,
) =>
  POST<{ share_expires_in_seconds?: number }, DashboardPublishResponse>(
    `${PREFIX}/${dashboardId}/publications/${publishedRevision}/rotate`,
    shareExpiresInSeconds ? { share_expires_in_seconds: shareExpiresInSeconds } : {},
  );

export const revokeDashboardPublication = (dashboardId: string, publishedRevision: number) =>
  DELETE<null, boolean>(`${PREFIX}/${dashboardId}/publications/${publishedRevision}`);

export const getPublicDashboard = (token: string) =>
  GET<null, PublicDashboardSnapshot>(`/api/v1/public/dashboards/${encodeURIComponent(token)}`);

export const filterPublicDashboard = (token: string, filters: Record<string, unknown>) =>
  POST<{ filters: Record<string, unknown> }, PublicDashboardFilterResponse>(
    `/api/v1/public/dashboards/${encodeURIComponent(token)}/filter`,
    { filters },
  );

export const getDashboardPermissions = (dashboardId: string) =>
  GET<null, DashboardPermissionRecord>(`${PREFIX}/${dashboardId}/permissions`);

export const listDashboardMembers = (dashboardId: string) =>
  GET<null, DashboardMemberRecord[]>(`${PREFIX}/${dashboardId}/members`);

export const upsertDashboardMember = (dashboardId: string, principalId: string, role: DashboardRole) =>
  PUT<{ principal_id: string; role: DashboardRole }, DashboardMemberRecord>(
    `${PREFIX}/${dashboardId}/members/${encodeURIComponent(principalId)}`,
    { principal_id: principalId, role },
  );

export const removeDashboardMember = (dashboardId: string, principalId: string) =>
  DELETE<null, boolean>(`${PREFIX}/${dashboardId}/members/${encodeURIComponent(principalId)}`);

export const listDashboardAudit = (dashboardId: string, limit = 100, offset = 0) =>
  GET<{ limit: number; offset: number }, DashboardAuditRecord[]>(`${PREFIX}/${dashboardId}/audit`, {
    limit,
    offset,
  });

export const listDashboardSchedules = (dashboardId: string) =>
  GET<null, DashboardSchedule[]>(`${PREFIX}/${dashboardId}/schedules`);

export const createDashboardSchedule = (dashboardId: string, request: DashboardScheduleCreate) =>
  POST<DashboardScheduleCreate, DashboardSchedule>(`${PREFIX}/${dashboardId}/schedules`, request);

export const updateDashboardSchedule = (dashboardId: string, scheduleId: string, request: DashboardScheduleUpdate) =>
  PUT<DashboardScheduleUpdate, DashboardSchedule>(`${PREFIX}/${dashboardId}/schedules/${scheduleId}`, request);

export const toggleDashboardSchedule = (dashboardId: string, scheduleId: string, enabled: boolean) =>
  POST<{ enabled: boolean }, DashboardSchedule>(`${PREFIX}/${dashboardId}/schedules/${scheduleId}/toggle`, {
    enabled,
  });

export const deleteDashboardSchedule = (dashboardId: string, scheduleId: string) =>
  DELETE<null, boolean>(`${PREFIX}/${dashboardId}/schedules/${scheduleId}`);

export const runDashboardSchedule = (dashboardId: string, scheduleId: string) =>
  POST<null, DashboardScheduleRun>(`${PREFIX}/${dashboardId}/schedules/${scheduleId}/run`);

export const listDashboardScheduleRuns = (dashboardId: string, scheduleId: string, limit = 50, offset = 0) =>
  GET<{ limit: number; offset: number }, DashboardScheduleRun[]>(
    `${PREFIX}/${dashboardId}/schedules/${scheduleId}/runs`,
    { limit, offset },
  );

export interface DashboardFolder {
  id: string;
  name: string;
  count?: number;
}
export interface DashboardCover {
  available: boolean;
  image?: string;
  revision?: number;
  captured_at?: string;
  stale?: boolean;
}
export const getDashboardCover = (id: string) => GET<null, DashboardCover>(`${PREFIX}/${id}/cover`);
export const saveDashboardCover = (id: string, expected_revision: number, image: string) =>
  PUT<{ expected_revision: number; image: string }, { saved: boolean }>(`${PREFIX}/${id}/cover`, {
    expected_revision,
    image,
  });
export const listDashboardFolders = () => GET<null, DashboardFolder[]>('/api/v1/dashboard-folders');
export const createDashboardFolder = (name: string) =>
  POST<{ name: string }, DashboardFolder>('/api/v1/dashboard-folders', { name });
export const renameDashboardFolder = (id: string, name: string) =>
  PUT<{ name: string }, DashboardFolder>(`/api/v1/dashboard-folders/${id}`, { name });
export const deleteDashboardFolder = (id: string) =>
  DELETE<null, { deleted: boolean }>(`/api/v1/dashboard-folders/${id}`);
export const moveDashboardToFolder = (id: string, folder_id: string | null) =>
  PUT<{ folder_id: string | null }, { moved: boolean }>(`${PREFIX}/${id}/folder`, { folder_id });
export interface DashboardLiveShareStatus {
  active: boolean;
  share_path?: string | null;
  snapshot_share_path?: string | null;
  expires_at?: string | null;
  published_revision?: number | null;
  public_base_url?: string;
}
export const createDashboardLiveShare = (id: string) =>
  POST<Record<string, never>, DashboardLiveShareStatus>(`${PREFIX}/${id}/live-share`, {});
export const getDashboardLiveShare = (id: string) => GET<null, DashboardLiveShareStatus>(`${PREFIX}/${id}/live-share`);
export interface DashboardSchedulerStatus {
  running: boolean;
  message: string;
}
export const getDashboardSchedulerStatus = (id: string) =>
  GET<null, DashboardSchedulerStatus>(`${PREFIX}/${id}/scheduler-status`);
export const revokeDashboardLiveShare = (id: string) =>
  DELETE<null, { revoked: boolean }>(`${PREFIX}/${id}/live-share`);

export interface TemplateSourceField {
  table: string;
  column: string;
}
export interface TemplateSourceJoin {
  table: string;
  left: TemplateSourceField;
  right_column: string;
}
export interface TemplateSourceMapping {
  table: string;
  fields: Record<string, TemplateSourceField>;
  joins: TemplateSourceJoin[];
  date_format: 'iso' | 'dmy';
  unit: string;
  interval: 'week' | 'month';
  grain: 'store_week' | 'order' | 'order_line' | 'payment' | 'incident' | 'measurement' | 'student' | 'product';
}
export interface TemplateSourceInfo {
  data_source_id: string;
  dialect: string;
  tables: { name: string; columns: { name: string; type: string }[] }[];
  roles: { id: string; label: string; required: boolean; hint: string }[];
  grain: TemplateSourceMapping['grain'];
  builtin_available: boolean;
}
export interface TemplatePreview {
  schema: DashboardSchemaV1;
  snapshot: DashboardSnapshot;
  validation: {
    records: number | null;
    widgets: number;
    filter_checks: number;
    publication_equivalent: boolean;
    grain: string;
  };
  adaptation?: { prompt?: string; changes?: string[]; model?: string };
}
export const inspectTemplateSource = (id: string, data_source_id: string) =>
  GET<{ data_source_id: string }, TemplateSourceInfo>(`/api/v1/dashboard-catalog/${id}/source`, { data_source_id });
export const previewDashboardTemplate = (id: string, data_source_id: string, mapping?: TemplateSourceMapping) =>
  POST<{ data_source_id: string; mapping?: TemplateSourceMapping }, TemplatePreview>(
    `/api/v1/dashboard-catalog/${id}/preview`,
    { data_source_id, mapping },
  );
export const generateDashboardTemplate = (
  id: string,
  data_source_id: string,
  mapping?: TemplateSourceMapping,
  schema?: DashboardSchemaV1,
) =>
  POST<{ data_source_id: string; mapping?: TemplateSourceMapping; schema?: DashboardSchemaV1 }, DashboardRecord>(
    `/api/v1/dashboard-catalog/${id}/generate`,
    { data_source_id, mapping, schema },
  );

export interface DashboardTemplateFeatures {
  template_id: string;
  title: string;
  prompt: string;
  widgets: Array<{ id: string; title: string; visualization: string }>;
}
export const getDashboardTemplateFeatures = (id: string) =>
  GET<null, DashboardTemplateFeatures>(`/api/v1/dashboard-catalog/${id}/features`);
export const adaptDashboardTemplate = (id: string, data_source_id: string, prompt: string, model?: string) =>
  POST<{ data_source_id: string; prompt: string; model?: string }, TemplatePreview>(
    `/api/v1/dashboard-catalog/${id}/adapt`,
    { data_source_id, prompt, model },
    { timeout: 360000 },
  );
