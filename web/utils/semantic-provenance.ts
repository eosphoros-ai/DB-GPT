import type { QueryArtifactPayload } from './query-export';

/** Promote authoritative semantic tool observations, never model-written IDs. */
export interface SemanticSource {
  key: string;
  kind: 'metric' | 'business' | 'table';
  connId: string;
  dsId: number;
  id: number;
  name: string;
  version?: number;
  tableName?: string;
  columnName?: string;
  snapshot: Record<string, any>;
}

export function decodeSemanticValue(value: unknown): any {
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export interface QuerySource {
  key: string;
  artifactId: string;
  payload: QueryArtifactPayload;
}

export interface SemanticReadGap {
  key: string;
  connId: string;
  dsId?: number;
  action: string;
  status: string;
}

type ProvenanceStep = { id: string; action?: string; status: string };
type ProvenanceOutputs = Record<string, { content: unknown }[]>;

/** Walk complete confirmed observations, including both engines' parallel envelopes. */
function visitConfirmedObservations(
  steps: ProvenanceStep[],
  outputs: ProvenanceOutputs,
  consume: (value: Record<string, any>, action: string) => void,
): void {
  const visit = (raw: unknown, action: string, depth: number) => {
    if (depth > 8) return;
    const value = decodeSemanticValue(raw);
    if (!value || typeof value !== 'object' || value.success === false) return;
    if (Array.isArray(value)) {
      value.forEach(item => visit(item, action, depth + 1));
    } else if (Array.isArray(value.chunks)) {
      value.chunks.forEach((c: any) => visit(c.content, action, depth + 1));
    } else if (typeof value.name === 'string' && ('observation' in value || 'content' in value)) {
      visit(value.observation ?? value.content, value.name, depth + 1);
    } else {
      consume(value, action);
    }
  };
  for (const step of steps) {
    if (!['done', 'completed'].includes(step.status)) continue;
    for (const output of outputs[step.id] ?? []) visit(output.content, step.action ?? '', 0);
  }
}

/** SQL reads remain traceable even when a database has no published semantic definitions. */
export function querySourcesFromExecution(steps: ProvenanceStep[], outputs: ProvenanceOutputs): QuerySource[] {
  const found = new Map<string, QuerySource>();
  visitConfirmedObservations(steps, outputs, (value, action) => {
    const execution = value.execution;
    if (
      found.size >= 100 ||
      action !== 'sql_query' ||
      execution?.tool !== 'sql_query' ||
      execution.status !== 'succeeded' ||
      typeof execution.artifact_id !== 'string' ||
      !execution.artifact_id ||
      typeof execution.started_at !== 'string' ||
      !Number.isFinite(Date.parse(execution.started_at)) ||
      !Number.isFinite(execution.duration_ms) ||
      execution.duration_ms < 0 ||
      typeof value.sql !== 'string' ||
      !value.sql.trim() ||
      typeof value.db_name !== 'string' ||
      !value.db_name ||
      !Array.isArray(value.columns) ||
      !value.columns.every((c: unknown) => typeof c === 'string') ||
      !Array.isArray(value.rows) ||
      !value.rows.every(Array.isArray)
    )
      return;
    const key = `${value.db_name}:query:${execution.artifact_id}`;
    found.set(key, { key, artifactId: execution.artifact_id, payload: value as QueryArtifactPayload });
  });
  return [...found.values()];
}

/** Preserve missing-definition receipts without promoting them to governed sources. */
export function semanticReadGapsFromExecution(steps: ProvenanceStep[], outputs: ProvenanceOutputs): SemanticReadGap[] {
  const found = new Map<string, SemanticReadGap>();
  visitConfirmedObservations(steps, outputs, (value, action) => {
    if (
      found.size >= 100 ||
      !['semantic_get_metric', 'semantic_search_metrics', 'semantic_search_business', 'semantic_get_metadata'].includes(
        action,
      ) ||
      value.source !== 'semantic_center' ||
      !['empty', 'not_found', 'not_published', 'version_not_found', 'space_not_found'].includes(value.status) ||
      typeof value.conn_id !== 'string' ||
      !value.conn_id
    )
      return;
    const key = `${value.conn_id}:${action}:${value.status}`;
    found.set(key, {
      key,
      connId: value.conn_id,
      dsId: Number.isSafeInteger(value.ds_id) && value.ds_id > 0 ? value.ds_id : undefined,
      action,
      status: value.status,
    });
  });
  return [...found.values()];
}

export function semanticSourcesFromExecution(
  steps: { id: string; action?: string; status: string }[],
  outputs: Record<string, { content: unknown }[]>,
): SemanticSource[] {
  const found = new Map<string, SemanticSource>();
  visitConfirmedObservations(steps, outputs, (value, action) => {
    if (
      found.size >= 100 ||
      value.source !== 'semantic_center' ||
      value.status !== 'ok' ||
      typeof value.conn_id !== 'string' ||
      !Number.isSafeInteger(value.ds_id) ||
      value.ds_id <= 0
    )
      return;
    const rows = value.metric ? [value.metric] : Array.isArray(value.items) ? value.items : [];
    for (const row of rows) {
      if (!row || typeof row !== 'object') continue;
      if (!Number.isSafeInteger(row.id) || row.id <= 0) continue;
      let kind: SemanticSource['kind'];
      if (action === 'semantic_get_metric' || action === 'semantic_search_metrics') {
        if (
          row.status !== 'published' ||
          !Number.isSafeInteger(row.version) ||
          row.version < 1 ||
          row.citation !== `semantic::${value.conn_id}/metric/${row.id}@v${row.version}`
        )
          continue;
        kind = 'metric';
      } else if (action === 'semantic_search_business' && row.status === 'published') {
        kind = 'business';
      } else if (action === 'semantic_get_metadata' && row.status === 'active') {
        kind = 'table';
      } else continue;
      const name = kind === 'metric' ? row.metric_name : kind === 'business' ? row.entry_name : row.table_name;
      if (typeof name !== 'string' || !name) continue;
      const key = `${value.conn_id}:${kind}:${row.id}:${row.version ?? ''}`;
      found.set(key, {
        key,
        kind,
        connId: value.conn_id,
        dsId: value.ds_id,
        id: row.id,
        name,
        version: row.version,
        tableName: row.table_name,
        columnName: row.column_name,
        snapshot: row,
      });
    }
  });
  return [...found.values()];
}

/** Only link unambiguous references supported by this answer's observations. */
export function matchSemanticSource(text: string, sources: SemanticSource[]): SemanticSource | undefined {
  const token = text.trim();
  const matches = sources.filter(source =>
    source.kind === 'metric'
      ? token === `${source.id}@v${source.version}` || token === source.snapshot.citation
      : token === source.name || token === `${source.tableName}.${source.columnName}`,
  );
  return matches.length === 1 ? matches[0] : undefined;
}

export function splitSemanticReferenceSection(content: string, sources: SemanticSource[]) {
  const heading = /^#{1,6}\s+[^\n]*(?:引用溯源|引用来源|参考来源|Semantic sources)[^\n]*$/im.exec(content);
  if (
    !heading ||
    !sources.some(
      source =>
        source.kind === 'metric' &&
        (content.slice(heading.index).includes(`${source.id}@v${source.version}`) ||
          content.slice(heading.index).includes(source.snapshot.citation)),
    )
  ) {
    return { answer: content, notes: '' };
  }
  const tail = content.slice(heading.index + heading[0].length);
  const next = /\n#{1,6}\s+/.exec(tail);
  return {
    answer: content.slice(0, heading.index).trimEnd() + (next ? tail.slice(next.index) : ''),
    notes: tail.slice(0, next?.index ?? tail.length).trim(),
  };
}

export function semanticCenterLink(
  source: SemanticSource,
  tab = source.kind === 'metric' ? 'metrics' : source.kind === 'business' ? 'entries' : 'catalog',
): string {
  const query = new URLSearchParams({ ds: String(source.dsId), tab });
  if (source.kind === 'metric' && tab === 'metrics') {
    query.set('metric', String(source.id));
    query.set('version', String(source.version));
  }
  return `/construct/semantic?${query}`;
}
