import assert from 'node:assert/strict';
import test from 'node:test';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { restoreSubAgentStates } from './use-subagent-stream.ts';

test('restores structured sub-agent state from a history payload', () => {
  const restored = restoreSubAgentStates([
    {
      agent_id: 'sub_d1_0',
      name: 'Country distribution',
      goal: 'Analyze users by country',
      status: 'done',
      lane: 0,
      batch_id: 1,
      artifact_count: 1,
      artifacts: [{ type: 'image', url: '/images/country.png', title: 'Country chart' }],
      result: 'USA has 5 users.',
      elapsed_ms: 1200,
      steps: [
        {
          action: 'sql_query',
          intention: 'Count users by country',
          sql: 'SELECT country, COUNT(*) FROM users GROUP BY country',
          chunks: [{ output_type: 'markdown', content: '| USA | 5 |' }],
        },
      ],
    },
  ]);

  assert.deepEqual(restored, {
    sub_d1_0: {
      agentId: 'sub_d1_0',
      name: 'Country distribution',
      goal: 'Analyze users by country',
      status: 'done',
      lane: 0,
      batchId: 1,
      artifactCount: 1,
      artifacts: [{ type: 'image', url: '/images/country.png', title: 'Country chart' }],
      result: 'USA has 5 users.',
      elapsedMs: 1200,
      steps: [
        {
          action: 'sql_query',
          label: '查询数据库',
          intention: 'Count users by country',
          sql: 'SELECT country, COUNT(*) FROM users GROUP BY country',
          chunks: [{ output_type: 'markdown', content: '| USA | 5 |' }],
        },
      ],
    },
  });
});

test('keeps legacy history compatible when sub-agent state is absent', () => {
  assert.deepEqual(restoreSubAgentStates(undefined), {});
});
