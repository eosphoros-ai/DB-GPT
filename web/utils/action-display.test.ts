import assert from 'node:assert/strict';
import test from 'node:test';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { buildActionDisplayText } from './action-display.ts';

const rawThought =
  'The parallel execution returned results for 3 tasks. One task was not executed due to concurrency limit.';

test('uses action reason instead of leaking raw thought when intention is absent', () => {
  assert.equal(
    buildActionDisplayText({
      actionIntention: undefined,
      actionReason: '执行订单月份分析查询',
      thought: rawThought,
    }),
    '执行订单月份分析查询',
  );
});

test('does not display raw thought when user-facing fields are absent', () => {
  assert.equal(
    buildActionDisplayText({
      actionIntention: undefined,
      actionReason: undefined,
      thought: rawThought,
    }),
    undefined,
  );
});

test('keeps concise intention and reason on separate lines', () => {
  assert.equal(
    buildActionDisplayText({
      actionIntention: '继续查询',
      actionReason: '执行剩余月份分析',
      thought: rawThought,
    }),
    '继续查询\n执行剩余月份分析',
  );
});
