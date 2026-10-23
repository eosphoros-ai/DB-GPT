import { GET, POST } from './index';

export interface SemanticSpace {
  id: number;
  conn_id: string;
  conn_name: string;
  db_type: string;
  status: string;
  space_name: string;
  embedding_model?: string;
  table_count?: number;
  chunk_count?: number;
  last_sync_at?: string | null;
}

export interface SemanticTable {
  id: number;
  table_name: string;
  table_comment?: string;
  table_type: string;
  row_count_est?: number;
  is_whitelisted: boolean;
  is_sensitive: boolean;
  status: string;
}

export interface SemanticColumn {
  id: number;
  column_name: string;
  column_type?: string;
  column_comment?: string;
  is_pk: boolean;
  is_enum: boolean;
  status: string;
}

export interface SemanticEntry {
  id: number;
  entry_type: string;
  target_id?: number;
  entry_name?: string;
  entry_comment?: string;
  synonyms?: string;
  status: string;
  version: number;
  confidence?: number;
  provenance: string;
  publish_version?: number;
}

export interface SemanticMetric {
  id: number;
  metric_name: string;
  metric_comment?: string;
  metric_type: string;
  formula?: string;
  dimensions?: string;
  status: string;
  version: number;
  provenance: string;
  suite_id?: string;
  publish_version?: number;
}

export interface SemanticExample {
  id: number;
  example_name?: string;
  question?: string;
  sql_text?: string;
  source: string;
  use_count: number;
  status: string;
}

export interface SemanticRelation {
  id: number;
  left_table_id?: number;
  left_column_id?: number;
  right_table_id?: number;
  right_column_id?: number;
  relation_type: string;
  join_condition?: string;
  confidence?: number;
}

export interface SemanticRule {
  id: number;
  rule_name?: string;
  rule_type: string;
  rule_definition?: string;
  priority: number;
  status: string;
}

export interface SemanticCoverage {
  ds_id: number;
  tables: number;
  whitelisted: number;
  tables_annotated: number;
  coverage_pct: number;
  entries: Record<string, number>;
  metrics: Record<string, number>;
}

/** Semantic center (S9 client). */
export const getSemanticSpaces = () => GET<null, SemanticSpace[]>('/api/v1/semantic/spaces');

export const getSemanticSpace = (id: number) =>
  GET<null, SemanticSpace>(`/api/v1/semantic/spaces/${id}`);

export const postSemanticActivate = (
  id: number,
  data: { sampling_limit?: number; run_draft_generation?: boolean; embedding_model?: string },
) => POST<typeof data, { ds_id: number; status: string; whitelist: number }>(`/api/v1/semantic/spaces/${id}/activate`, data);

export const postSemanticBackfill = () =>
  POST<null, { synced: string[]; failed: string[] }>('/api/v1/semantic/spaces/backfill');

export const postSemanticDrafts = (id: number) =>
  POST<null, { entries: Record<string, number>; metrics: Record<string, number> }>(
    `/api/v1/semantic/spaces/${id}/drafts`,
  );

export const postSemanticExample = (
  id: number,
  data: { question: string; sql_text: string; example_name?: string; explanation?: string; source?: string },
) => POST<typeof data, { id: number; status: string }>(`/api/v1/semantic/spaces/${id}/examples`, data);

export const postSemanticSync = (id: number, data?: { db_name?: string }) =>
  POST<typeof data, Record<string, number>>(`/api/v1/semantic/spaces/${id}/sync`, data ?? {});

export const getSemanticCoverage = (id: number) =>
  GET<null, SemanticCoverage>(`/api/v1/semantic/spaces/${id}/coverage`);

export const getSemanticTables = (id: number) =>
  GET<null, SemanticTable[]>(`/api/v1/semantic/spaces/${id}/tables`);

export const getSemanticColumns = (tableId: number, dsId: number) =>
  GET<{ ds_id: number }, SemanticColumn[]>(`/api/v1/semantic/tables/${tableId}/columns`, {
    ds_id: dsId,
  });

export const getSemanticEntries = (id: number, status?: string) =>
  GET<{ status?: string }, SemanticEntry[]>(`/api/v1/semantic/spaces/${id}/entries`, {
    status,
  });

export const postEntryReview = (
  entryId: number,
  data: { action: 'confirm' | 'modify' | 'reject'; updates?: Record<string, unknown> },
) => POST<typeof data, { entry_id: number; status: string }>(`/api/v1/semantic/entries/${entryId}/review`, data);

export const getSemanticMetrics = (id: number, status?: string) =>
  GET<{ status?: string }, SemanticMetric[]>(`/api/v1/semantic/spaces/${id}/metrics`, {
    status,
  });

export const postMetricPublish = (metricId: number, data?: { change_note?: string }) =>
  POST<typeof data, { metric_id: number; version: number }>(`/api/v1/semantic/metrics/${metricId}/publish`, data ?? {});

export const getSemanticExamples = (id: number) =>
  GET<null, SemanticExample[]>(`/api/v1/semantic/spaces/${id}/examples`);

export const getSemanticRelations = (id: number) =>
  GET<null, SemanticRelation[]>(`/api/v1/semantic/spaces/${id}/relations`);

export const getSemanticRules = (id: number) =>
  GET<null, SemanticRule[]>(`/api/v1/semantic/spaces/${id}/rules`);

export const postRuleStatus = (ruleId: number, status: string) =>
  POST<{ status: string }, { rule_id: number; status: string }>(`/api/v1/semantic/rules/${ruleId}/status`, {
    status,
  });
