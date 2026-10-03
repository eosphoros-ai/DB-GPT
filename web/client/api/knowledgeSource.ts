/**
 * Knowledge source API client (bindings under the knowledge v2 prefix).
 */
import { KsConnectorMeta, KsResource, KsSourceBinding, KsSyncLog, KsSyncSummary } from '@/types/knowledgeSource';
import { DELETE, GET, POST, PUT } from './index';

const base = (spaceId: string | number) => `/api/v2/serve/knowledge/spaces/${spaceId}/knowledge_sources`;

export const listConnectorTypes = () => {
  return GET<null, Record<string, KsConnectorMeta>>('/api/v2/serve/knowledge/knowledge_sources/types');
};

export const listSourceBindings = (spaceId: string | number) => {
  return GET<null, KsSourceBinding[]>(`${base(spaceId)}`);
};

export interface KsCreateParams {
  name?: string;
  type: string;
  config: Record<string, string>;
  target_resource_ids: string[];
  interval_minutes: number;
  sync_mode: string;
  conflict_strategy: string;
  sync_deletions: boolean;
}

export const createSourceBinding = (spaceId: string | number, data: KsCreateParams) => {
  return POST<KsCreateParams, KsSourceBinding>(base(spaceId), data);
};

export const updateSourceBinding = (
  spaceId: string | number,
  sourceId: number,
  data: Partial<KsCreateParams> & { status?: string },
) => {
  return PUT<Partial<KsCreateParams> & { status?: string }, boolean>(`${base(spaceId)}/${sourceId}`, data);
};

export const deleteSourceBinding = (spaceId: string | number, sourceId: number) => {
  return DELETE<null, boolean>(`${base(spaceId)}/${sourceId}`);
};

export const listSourceResources = (spaceId: string | number, sourceId: number, parentId = '') => {
  return GET<{ parent_id: string }, KsResource[]>(`${base(spaceId)}/${sourceId}/resources`, { parent_id: parentId });
};

export const triggerSourceSync = (spaceId: string | number, sourceId: number) => {
  return POST<null, KsSyncSummary>(`${base(spaceId)}/${sourceId}/sync`);
};

export const pauseSourceBinding = (spaceId: string | number, sourceId: number) => {
  return POST<null, boolean>(`${base(spaceId)}/${sourceId}/pause`);
};

export const resumeSourceBinding = (spaceId: string | number, sourceId: number) => {
  return POST<null, boolean>(`${base(spaceId)}/${sourceId}/resume`);
};

export const listSourceLogs = (spaceId: string | number, sourceId: number) => {
  return GET<null, KsSyncLog[]>(`${base(spaceId)}/${sourceId}/logs`);
};
