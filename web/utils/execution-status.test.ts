import { describe, expect, it } from 'vitest';
import { executionStatus } from './execution-status';

describe('execution completion status', () => {
  const done = { action: 'prepare_financial_report', status: 'done' };
  const failed = { action: 'review_financial_report', status: 'failed' };

  it('does not show success after a failed review, even with saved output', () => {
    expect(executionStatus([done, failed], false)).toBe('partial');
    expect(executionStatus([failed], false)).toBe('failed');
  });

  it('honors interrupted and failed history when the saved tools all succeeded', () => {
    expect(executionStatus([done], false, [], 'failed')).toBe('failed');
    expect(executionStatus([done], false, [], 'interrupted')).toBe('incomplete');
  });

  it('does not treat uncompleted planned stages as success', () => {
    expect(executionStatus([done], false, [{ status: 'error' }])).toBe('partial');
    expect(executionStatus([done], false, [{ status: 'pending' }])).toBe('incomplete');
    expect(executionStatus([done], false, [{ status: 'cancelled' }])).toBe('incomplete');
  });

  it('keeps running during retries and completes a successful execution', () => {
    expect(executionStatus([done, failed], true)).toBe('running');
    expect(executionStatus([{ status: 'running' }])).toBe('running');
    expect(executionStatus([done], false, [{ status: 'completed' }])).toBe('done');
  });
});
