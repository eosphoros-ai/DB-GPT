/**
 * Knowledge source (external doc platforms) types — mirrors backend
 * knowledge_source/api.py + base.py contract layer.
 */
export interface KsAuthField {
  key: string;
  label: string;
  required: boolean;
  secret: boolean;
  placeholder?: string;
  hint?: string;
}

export interface KsConnectorMeta {
  name: string;
  icon: string;
  description: string;
  supports_incremental: boolean;
  resource_noun: string;
  auth_fields: KsAuthField[];
}

export interface KsResource {
  external_id: string;
  title: string;
  parent_id: string | null;
  has_children: boolean;
  resource_type: string;
}

export interface KsSourceBinding {
  id: number;
  space_id: number;
  name: string;
  type: string;
  target_resource_ids: string[];
  interval_minutes: number;
  sync_mode: string;
  conflict_strategy: string;
  sync_deletions: boolean;
  status: 'active' | 'paused' | 'running' | 'error';
  has_cursor: boolean;
  last_sync_at: string | null;
  error_message: string | null;
  gmt_modified?: string | null;
}

export interface KsSyncSummary {
  status: string;
  trigger: string;
  mode: string;
  items_created: number;
  items_updated: number;
  items_skipped: number;
  items_failed: number;
  error?: string | null;
}

export interface KsSyncLog {
  id: number;
  trigger: string;
  mode: string;
  items_created: number;
  items_updated: number;
  items_skipped: number;
  items_failed: number;
  status: string;
  error?: string | null;
  started_at: string | null;
  finished_at: string | null;
}
