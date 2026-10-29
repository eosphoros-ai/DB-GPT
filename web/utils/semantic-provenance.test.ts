import { describe, expect, it } from 'vitest';
import {
  matchSemanticSource,
  querySourcesFromExecution,
  semanticCenterLink,
  semanticReadGapsFromExecution,
  semanticSourcesFromExecution,
  splitSemanticReferenceSection,
} from './semantic-provenance';

const metric = {
  source: 'semantic_center',
  status: 'ok',
  ds_id: 3,
  conn_id: 'commerce',
  metric: {
    id: 17,
    metric_name: '净实收',
    version: 1,
    status: 'published',
    citation: 'semantic::commerce/metric/17@v1',
    metric_definition: { lineage: { sources: ['refunds.freight_cents'] } },
  },
};
const read = (content: unknown, action = 'semantic_get_metric', status = 'done') =>
  semanticSourcesFromExecution([{ id: 's1', action, status }], { s1: [{ content }] });

const query = {
  sql: 'SELECT document FROM metric_definitions',
  db_name: 'commerce',
  columns: ['document'],
  rows: [['口径文档快照']],
  row_count: 1,
  execution: {
    status: 'succeeded',
    started_at: '2026-10-29T09:51:16+00:00',
    duration_ms: 16,
    tool: 'sql_query',
    artifact_id: 'sql-test-1',
  },
};
const missing = { ...metric, status: 'empty', metric: undefined, items: [] };

describe('semantic source promotion', () => {
  it('traces direct and parallel SQL reads with their exact database, document and execution identity', () => {
    const steps = [
      { id: 's1', action: 'sql_query', status: 'done' },
      { id: 's2', action: 'parallel', status: 'completed' },
    ];
    const outputs = {
      s1: [{ content: query }],
      s2: [
        {
          content: JSON.stringify([
            {
              name: 'sql_query',
              content: 'truncated preview',
              observation: JSON.stringify({ chunks: [{ output_type: 'query', content: query }] }),
            },
          ]),
        },
      ],
    };
    const sources = querySourcesFromExecution(steps, outputs);
    expect(sources).toHaveLength(1);
    expect(sources[0].artifactId).toBe('sql-test-1');
    expect(sources[0].payload).toEqual(query);
    expect(semanticSourcesFromExecution(steps, outputs)).toEqual([]);
  });
  it('rejects failed, unexecuted, malformed and unrelated observations as SQL evidence', () => {
    const readQuery = (content: unknown, action = 'sql_query', status = 'done') =>
      querySourcesFromExecution([{ id: 's', action, status }], { s: [{ content }] });
    expect(readQuery(query, 'bash')).toEqual([]);
    expect(readQuery(query, 'sql_query', 'running')).toEqual([]);
    expect(readQuery({ ...query, execution: undefined })).toEqual([]);
    expect(readQuery({ ...query, execution: { ...query.execution, status: 'failed' } })).toEqual([]);
    expect(readQuery({ ...query, execution: { ...query.execution, artifact_id: null } })).toEqual([]);
    expect(readQuery({ ...query, execution: { ...query.execution, started_at: 'invalid' } })).toEqual([]);
    expect(readQuery({ ...query, db_name: '' })).toEqual([]);
    expect(readQuery({ ...query, rows: [null] })).toEqual([]);
    expect(readQuery({ success: false, chunks: [{ content: query }] })).toEqual([]);
    expect(readQuery(JSON.stringify(query).slice(0, -1))).toEqual([]);
  });
  it('keeps missing published definitions visible as receipts, separate from source records', () => {
    const steps = [{ id: 's', action: 'parallel', status: 'done' }];
    const outputs = {
      s: [
        {
          content: [
            { name: 'semantic_search_metrics', observation: missing },
            { name: 'semantic_search_business', observation: missing },
            { name: 'semantic_search_metrics', observation: missing },
            { name: 'bash', observation: missing },
          ],
        },
      ],
    };
    const gaps = semanticReadGapsFromExecution(steps, outputs);
    expect(gaps).toHaveLength(2);
    expect(gaps[0]).toMatchObject({ connId: 'commerce', dsId: 3, status: 'empty' });
    expect(semanticSourcesFromExecution(steps, outputs)).toEqual([]);
    expect(querySourcesFromExecution(steps, outputs)).toEqual([]);
  });
  it('preserves the exact version and field lineage from real tool observations', () => {
    const sources = read(JSON.stringify(metric));
    expect(sources).toHaveLength(1);
    expect(sources[0].snapshot.metric_definition.lineage.sources).toEqual(['refunds.freight_cents']);
    expect(matchSemanticSource('17@v1', sources)).toBe(sources[0]);
    expect(matchSemanticSource('17@v2', sources)).toBeUndefined();
    expect(semanticCenterLink(sources[0])).toBe('/construct/semantic?ds=3&tab=metrics&metric=17&version=1');
  });
  it('handles PI chunks, parallel results and duplicate observations', () => {
    const wrapper = JSON.stringify([
      {
        name: 'semantic_get_metric',
        observation: {
          chunks: [{ content: JSON.stringify(metric) }, { content: JSON.stringify(metric) }],
        },
      },
    ]);
    expect(read(wrapper, 'parallel')).toHaveLength(1);
  });
  it('rejects model text, failed tools, drafts, mismatched scopes and truncated JSON', () => {
    expect(read('指标17@v1净实收')).toEqual([]);
    expect(read(metric, 'bash')).toEqual([]);
    expect(read(metric, 'semantic_get_metric', 'failed')).toEqual([]);
    expect(read({ ...metric, status: 'not_published' })).toEqual([]);
    expect(read({ ...metric, conn_id: 'other' })).toEqual([]);
    expect(read({ ...metric, metric: { ...metric.metric, status: 'draft' } })).toEqual([]);
    expect(read(JSON.stringify(metric).slice(0, -1))).toEqual([]);
    expect(read({ ...metric, metric: null, items: [null] })).toEqual([]);
  });
  it('does not resolve ambiguous IDs across two connections', () => {
    const sources = [
      ...read(metric),
      ...read({
        ...metric,
        conn_id: 'other',
        ds_id: 4,
        metric: { ...metric.metric, citation: 'semantic::other/metric/17@v1' },
      }),
    ];
    expect(matchSemanticSource('17@v1', sources)).toBeUndefined();
  });
  it('moves verified prose references into notes without dropping evidence gaps', () => {
    const content = '## 结果\n338元\n## 八、引用溯源\n指标 `17@v1`\n证据缺口：无调度任务\n## 后续\n检查';
    const split = splitSemanticReferenceSection(content, read(metric));
    expect(split.answer).toContain('338元');
    expect(split.answer).toContain('## 后续');
    expect(split.answer).not.toContain('引用溯源');
    expect(split.notes).toContain('无调度任务');
    expect(splitSemanticReferenceSection(content, []).answer).toBe(content);
  });
});
