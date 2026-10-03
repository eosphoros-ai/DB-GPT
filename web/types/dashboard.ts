export type DashboardSchemaVersion = '1.0' | '1.1' | '1.2' | '1.3' | '1.4';
export type DashboardStatus = 'draft' | 'published' | 'archived';
export type DashboardOrigin = 'task' | 'manual' | 'template';
export type DashboardAssetState = 'generated' | 'saved';
export type DashboardRole = 'viewer' | 'editor' | 'owner';
export type DashboardAction = 'view' | 'edit' | 'query' | 'publish' | 'manage_access' | 'manage_schedule';
export type DashboardWidgetType = 'kpi' | 'line' | 'bar' | 'pie' | 'table';
export type DashboardVisualization =
  | 'kpi'
  | 'line'
  | 'area'
  | 'column'
  | 'bar'
  | 'stacked_column'
  | 'pie'
  | 'donut'
  | 'scatter'
  | 'dual_axis'
  | 'heatmap'
  | 'cohort'
  | 'gauge'
  | 'funnel'
  | 'treemap'
  | 'radar'
  | 'waterfall'
  | 'geo_map'
  | 'table';
export type DashboardSortDirection = 'default' | 'ascending' | 'descending';
export type DashboardSelectionKind =
  | 'dashboard'
  | 'widget'
  | 'filter'
  | 'chart_datum'
  | 'chart_series'
  | 'table_column'
  | 'table_cell';
export type DashboardAnnotationStatus = 'pending' | 'proposed' | 'applied' | 'rejected' | 'invalidated';
export type DashboardAnnotationIntent = 'modify' | 'explain' | 'anomaly';
export interface DashboardAssistantContext {
  message?: string;
  conversation?: string;
  view_context?: Record<string, unknown>;
}
export interface DashboardAnnotationIntentResolution {
  reply?: string | null;
  model?: string | null;
  items: Array<{
    draft_id: string;
    tasks: Array<{ intent: DashboardAnnotationIntent; prompt: string }>;
    question?: string | null;
    answered?: boolean;
  }>;
}
export interface DashboardQueryLogic {
  tables: string[];
  set_operations: string[];
  stages: Array<{
    label: string;
    expressions: string[];
    group_by: string[];
    where?: string | null;
    having?: string | null;
    joins: string[];
    order_by?: string | null;
    limit?: string | null;
  }>;
}
export type DashboardAnomalyBaseline = 'previous_period' | 'rolling_average' | 'target_value';
export type DashboardAnomalyThresholdMode = 'relative_change' | 'absolute_change';
export type DashboardAnomalyDirection = 'two_sided' | 'above' | 'below';
export type DashboardAnomalyStatus = 'anomaly' | 'normal' | 'indeterminate';
export type DashboardPublicationFilterOperator = 'auto' | 'equal' | 'less_than_or_equal' | 'greater_than_or_equal';
export type DashboardPublicationAggregation =
  | 'sum'
  | 'average'
  | 'count'
  | 'count_distinct'
  | 'minimum'
  | 'maximum'
  | 'first'
  | 'ratio';
export type DashboardFilterType = 'date_range' | 'select' | 'multi_select' | 'text' | 'number_range';
export type DashboardFieldType = 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'datetime' | 'unknown';
export type DashboardMetricAggregation =
  | 'sum'
  | 'average'
  | 'count'
  | 'count_distinct'
  | 'minimum'
  | 'maximum'
  | 'ratio'
  | 'none';
export type DashboardSemanticDefinitionSource = 'catalog' | 'user_confirmed' | 'model_inferred';
export type DashboardThemePreset = 'clarity' | 'ocean' | 'warm' | 'graphite' | 'clean' | 'business_blue';
export type DashboardThemeMode = 'light' | 'dark';
export type DashboardThemeFontScale = 'compact' | 'standard' | 'large';
export type DashboardThemeDensity = 'compact' | 'comfortable' | 'spacious';
export type DashboardThemeShadow = 'none' | 'soft' | 'elevated';
export type DashboardThemeKpiStyle = 'quiet' | 'accent' | 'solid';
export type DashboardThemeTableStyle = 'plain' | 'striped' | 'divided';

export interface DashboardThemeOverrides {
  primary_color?: string | null;
  font_scale?: DashboardThemeFontScale | null;
  density?: DashboardThemeDensity | null;
  card_radius?: number | null;
  card_shadow?: DashboardThemeShadow | null;
  chart_palette?: string[] | null;
  kpi_style?: DashboardThemeKpiStyle | null;
  table_style?: DashboardThemeTableStyle | null;
}

export interface DashboardVisualTheme {
  preset?: DashboardThemePreset | null;
  mode?: DashboardThemeMode | null;
  overrides?: DashboardThemeOverrides;
}

export interface DashboardDescriptor {
  id: string;
  title: string;
  description: string;
  data_source_id: string;
  status: DashboardStatus;
  theme?: DashboardVisualTheme;
  refresh_policy?: {
    refresh_on_open: boolean;
    interval_seconds?: number | null;
  };
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MetricContext {
  grain: string;
  time_range?: string | null;
  data_freshness?: string | null;
  source_notes: string[];
  metrics?: DashboardMetricDefinition[];
  dimensions?: DashboardDimensionDefinition[];
}

export interface DashboardMetricDefinition {
  id: string;
  name: string;
  business_definition: string;
  aggregation: DashboardMetricAggregation;
  unit?: string | null;
  grain?: string | null;
  source_field?: string | null;
  definition_source: DashboardSemanticDefinitionSource;
}

export interface DashboardDimensionDefinition {
  id: string;
  name: string;
  business_definition: string;
  field?: string | null;
  data_type: DashboardFieldType;
  definition_source: DashboardSemanticDefinitionSource;
}

export interface DashboardFilterOption {
  label: string;
  value: unknown;
}

export interface DashboardFilter {
  id: string;
  type: DashboardFilterType;
  label: string;
  field: string;
  default: unknown;
  options: DashboardFilterOption[];
  relative_date?: {
    anchor: 'today';
    start_offset_days: number;
    end_offset_days: number;
  } | null;
}

export interface DashboardOutputField {
  name: string;
  type: DashboardFieldType;
  label?: string | null;
  nullable: boolean;
}

export interface FilterParameterBinding {
  parameter?: string | null;
  start_parameter?: string | null;
  end_parameter?: string | null;
}

export interface DashboardLastExecution {
  status: string;
  executed_at?: string | null;
  duration_ms?: number | null;
  row_count?: number | null;
  error?: string | null;
}

export type DashboardFederationMode = 'union_all' | 'join';
export type DashboardFederationJoinType = 'inner' | 'left';

export interface DashboardFederatedSourceQuery {
  alias: string;
  data_source_id: string;
  sql: string;
  filter_parameters: Record<string, string | FilterParameterBinding>;
  default_parameters: Record<string, unknown>;
  column_mapping: Record<string, string>;
  timeout_seconds: number;
  max_rows: number;
}

export interface DashboardFederatedJoin {
  left_alias: string;
  right_alias: string;
  left_field: string;
  right_field: string;
  join_type: DashboardFederationJoinType;
}

export interface DashboardFederatedQuery {
  mode: DashboardFederationMode;
  sources: DashboardFederatedSourceQuery[];
  join?: DashboardFederatedJoin | null;
  max_output_rows: number;
}

export interface DashboardQueryBinding {
  data_source_id: string;
  sql?: string | null;
  federation?: DashboardFederatedQuery | null;
  filter_parameters: Record<string, string | FilterParameterBinding>;
  default_parameters: Record<string, unknown>;
  output_fields: DashboardOutputField[];
  timeout_seconds: number;
  max_rows: number;
  grain?: string | null;
  refresh_time?: string | null;
  last_execution: DashboardLastExecution;
  lineage?: DashboardQueryLineage;
}

export interface DashboardQueryLineageSource {
  data_source_id: string;
  tables: string[];
  columns: string[];
}

export interface DashboardQueryLineage {
  sources: DashboardQueryLineageSource[];
}

export interface DashboardChartEncoding {
  x?: string | null;
  y?: string | null;
  value?: string | null;
  series?: string | null;
  category?: string | null;
  angle?: string | null;
  color?: string | null;
  y2?: string | null;
  row?: string | null;
  column?: string | null;
  target?: string | null;
  columns: string[];
}

export interface DashboardDefaultSort {
  field?: string | null;
  direction: DashboardSortDirection;
}

export interface DashboardPresentation {
  visualization?: DashboardVisualization | null;
  orientation?: 'vertical' | 'horizontal' | null;
  stacked: boolean;
  smooth: boolean;
  top_n?: number | null;
  colors: string[];
  unit?: string | null;
  currency?: string | null;
  precision?: number | null;
  percentage: boolean;
  show_legend?: boolean | null;
  show_grid?: boolean | null;
  default_sort: DashboardDefaultSort;
}

export interface DashboardPublicationFilterBinding {
  field: string;
  operator: DashboardPublicationFilterOperator;
}

export interface DashboardPublicationMeasure {
  source_field: string;
  output_field: string;
  aggregation: DashboardPublicationAggregation;
  denominator_field?: string | null;
  scale?: number;
}

export interface DashboardPublicationSort {
  field: string;
  direction: DashboardSortDirection;
}

export interface DashboardPublicationBinding {
  query: DashboardQueryBinding;
  filter_fields: Record<string, string | DashboardPublicationFilterBinding>;
  group_by: string[];
  measures: DashboardPublicationMeasure[];
  output_columns: string[];
  row_mode: boolean;
  sort: DashboardPublicationSort[];
  max_output_rows: number;
}

export interface DashboardWidgetError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface DashboardAnomalyThreshold {
  mode: DashboardAnomalyThresholdMode;
  value?: number | null;
}

export interface DashboardAnomalyRule {
  id: string;
  label: string;
  baseline: DashboardAnomalyBaseline;
  value_field: string;
  time_field?: string | null;
  direction: DashboardAnomalyDirection;
  threshold: DashboardAnomalyThreshold;
  rolling_window: number;
  target_value?: number | null;
  min_samples: number;
  enabled: boolean;
}

export interface DashboardAnomalyComparisonRange {
  current_start?: string | null;
  current_end?: string | null;
  baseline_start?: string | null;
  baseline_end?: string | null;
}

export interface DashboardAnomalyEvidence {
  rule_id: string;
  rule_label: string;
  status: DashboardAnomalyStatus;
  baseline: DashboardAnomalyBaseline;
  current_value?: number | null;
  baseline_value?: number | null;
  absolute_change?: number | null;
  change_ratio?: number | null;
  threshold: DashboardAnomalyThreshold;
  comparison_time_range: DashboardAnomalyComparisonRange;
  sample_size: number;
  matched_rule: string;
  reason_code?: string | null;
  reason?: string | null;
}

export interface DashboardWidget {
  id: string;
  type: DashboardWidgetType;
  title: string;
  description: string;
  query: DashboardQueryBinding;
  encoding: DashboardChartEncoding;
  style: Record<string, unknown>;
  presentation?: DashboardPresentation;
  publication?: DashboardPublicationBinding | null;
  metric_ids?: string[];
  dimension_ids?: string[];
  anomaly_rules?: DashboardAnomalyRule[];
  error?: DashboardWidgetError | null;
}

export interface DashboardLayoutItem {
  widget_id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  min_w?: number | null;
  min_h?: number | null;
  max_w?: number | null;
  max_h?: number | null;
}

export interface DashboardSchemaV1 {
  schema_version: DashboardSchemaVersion;
  dashboard: DashboardDescriptor;
  metric_context: MetricContext;
  filters: DashboardFilter[];
  widgets: DashboardWidget[];
  layouts: {
    columns: 12;
    desktop: DashboardLayoutItem[];
    mobile_strategy: 'stack' | string;
  };
  metadata: {
    conversation_id?: string | null;
    source_turn_id?: string | null;
    agent: {
      generated: boolean;
      model_name?: string | null;
      prompt?: string | null;
      generated_at?: string | null;
    };
    compatibility: Record<string, unknown>;
  };
}

export interface DashboardRecord {
  id: string;
  owner_id: string;
  conversation_id?: string | null;
  source_turn_id?: string | null;
  origin: DashboardOrigin;
  asset_state: DashboardAssetState;
  saved_at?: string | null;
  current_revision: number;
  status: DashboardStatus;
  schema: DashboardSchemaV1;
  created_at: string;
  updated_at: string;
}

export interface DashboardArtifactFile {
  path: string;
  language: string;
  content: string;
}

export interface DashboardArtifactBundle {
  dashboard_id: string;
  root: string;
  generated_at: string;
  files: DashboardArtifactFile[];
}

export type DashboardPatchOp = 'add' | 'replace' | 'remove';

export interface DashboardPatchOperation {
  op: DashboardPatchOp;
  path: string;
  value?: unknown;
}

export interface DashboardOperationRequest {
  operation_id: string;
  client_id: string;
  expected_revision: number;
  promote_to_asset?: boolean;
  operations: DashboardPatchOperation[];
}

export interface DashboardOperationLogRecord {
  dashboard_id: string;
  operation_id: string;
  client_id: string;
  actor_id: string;
  base_revision: number;
  applied_revision: number;
  operations: DashboardPatchOperation[];
  created_at: string;
}

export interface DashboardOperationResponse {
  dashboard: DashboardRecord;
  operation: DashboardOperationLogRecord;
  replayed: boolean;
}

export interface DashboardSelectionTarget {
  kind: DashboardSelectionKind;
  widget_id?: string | null;
  filter_id?: string | null;
  label: string;
  datum_key: Record<string, unknown>;
  series?: string | null;
  column?: string | null;
  row_key: Record<string, unknown>;
  value?: unknown;
}

export type DashboardTargetResolutionStatus = 'resolved' | 'needs_clarification';

export interface DashboardTargetCandidate {
  widget_id: string;
  label: string;
}

export interface DashboardTargetResolution {
  status: DashboardTargetResolutionStatus;
  target?: DashboardSelectionTarget | null;
  candidates: DashboardTargetCandidate[];
  question?: string | null;
  matched_by?: string | null;
}

export interface DashboardStablePatchOperation {
  op: DashboardPatchOp;
  path: string;
  value?: unknown;
}

export interface DashboardChangeProposal {
  summary: string;
  operations: DashboardPatchOperation[];
  stable_operations: DashboardStablePatchOperation[];
  before: string[];
  after: string[];
  validation: DashboardValidationResult;
  preview_schema: DashboardSchemaV1;
}

export interface DashboardAnnotationRecord {
  id: string;
  dashboard_id: string;
  actor_id: string;
  conversation_id?: string | null;
  source_turn_id?: string | null;
  base_revision: number;
  target: DashboardSelectionTarget;
  prompt: string;
  intent: DashboardAnnotationIntent;
  status: DashboardAnnotationStatus;
  proposal?: DashboardChangeProposal | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
}

export interface DashboardAnnotationApplyResponse {
  annotation: DashboardAnnotationRecord;
  operation: DashboardOperationResponse;
}

export interface DashboardCollaborationTicket {
  ticket: string;
  websocket_path: string;
  expires_at: string;
}

export interface DashboardParticipant {
  actor_id: string;
  client_id: string;
}

export interface DashboardListItem {
  id: string;
  title: string;
  description: string;
  data_source_id: string;
  conversation_id?: string | null;
  source_turn_id?: string | null;
  origin: DashboardOrigin;
  asset_state: DashboardAssetState;
  saved_at?: string | null;
  current_revision: number;
  status: DashboardStatus;
  updated_at: string;
}

export interface DashboardListPage {
  items: DashboardListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardMemberRecord {
  dashboard_id: string;
  principal_id: string;
  role: DashboardRole;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DashboardPermissionRecord {
  dashboard_id: string;
  actor_id: string;
  role: DashboardRole;
  actions: DashboardAction[];
}

export interface DashboardAuditRecord {
  id: number;
  dashboard_id: string;
  actor_id: string;
  action: string;
  target_type: string;
  target_id?: string | null;
  details: Record<string, unknown>;
  request_id?: string | null;
  created_at: string;
}

export interface DashboardRevisionRecord {
  dashboard_id: string;
  published_revision: number;
  published_at: string;
}

export interface DashboardEditVersionRecord {
  dashboard_id: string;
  revision: number;
  source: string;
  actor_id: string;
  operation_id?: string | null;
  created_at: string;
}

export interface DashboardEditVersionDetail extends DashboardEditVersionRecord {
  schema: DashboardSchemaV1;
}

export interface DashboardShareRecord {
  id: number;
  dashboard_id: string;
  published_revision: number;
  created_by: string;
  created_at: string;
  expires_at?: string | null;
  revoked_at?: string | null;
  active: boolean;
}

export interface DashboardValidationIssue {
  path: string;
  code: string;
  message: string;
  severity: string;
}

export interface DashboardValidationResult {
  valid: boolean;
  issues: DashboardValidationIssue[];
  widget_status: Record<string, string>;
}

export interface DashboardWidgetResult {
  widget_id: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
  refreshed_at: string;
  anomalies?: DashboardAnomalyEvidence[];
  error?: DashboardWidgetError | null;
}

export interface DashboardSnapshot {
  dashboard_id: string;
  refreshed_at: string;
  filters: Record<string, unknown>;
  widgets: Record<string, DashboardWidgetResult>;
}

export interface DashboardPublishResponse {
  dashboard_id: string;
  published_revision: number;
  share_token: string;
  share_path: string;
  latest_share_path?: string | null;
  published_at: string;
  expires_at?: string | null;
}

export interface PublicDashboardSnapshot {
  dashboard_id: string;
  published_revision: number;
  schema: DashboardSchemaV1;
  snapshot: DashboardSnapshot;
  published_at: string;
  is_latest_link: boolean;
  data_mode?: 'snapshot' | 'live';
  refresh_interval?: number;
  stale?: boolean;
  refresh_error?: string | null;
}

export interface PublicDashboardFilterResponse {
  snapshot: DashboardSnapshot;
  unsupported_widget_ids: string[];
  stale?: boolean;
  refresh_error?: string | null;
}

export interface DashboardRefreshSchedulePayload {
  version: number;
  dashboard_id: string;
  filters: Record<string, unknown>;
  publish_after_refresh: boolean;
  timeout_seconds: number;
  max_attempts: number;
}

export interface DashboardSchedule {
  task_id: string;
  task_name: string;
  description?: string | null;
  task_type: 'dashboard_refresh';
  cron_expression: string;
  payload: DashboardRefreshSchedulePayload;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  owner_id?: string | null;
  next_run_time?: string | null;
}

export type DashboardScheduleRunStatus = 'running' | 'success' | 'partial_success' | 'failed' | 'timeout';

export interface DashboardScheduleRun {
  run_id: string;
  task_id: string;
  started_at?: string | null;
  finished_at?: string | null;
  status: DashboardScheduleRunStatus;
  result_summary?: string | null;
  error_message?: string | null;
  output_resource_id?: string | null;
  attempt_count: number;
  result?: Record<string, unknown> | null;
}

export interface DashboardScheduleCreate {
  task_name: string;
  description?: string | null;
  cron_expression: string;
  filters: Record<string, unknown>;
  publish_after_refresh: boolean;
  timeout_seconds: number;
  max_attempts: number;
}

export type DashboardScheduleUpdate = Partial<DashboardScheduleCreate>;
