import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useQuestionSession } from './use-question-session';

vi.mock('@/utils', () => ({ getUserId: () => 'test-user' }));
afterEach(() => vi.unstubAllGlobals());
const ask = (request_id: string, questions: unknown[] = [`${request_id} question`]) => ({
  type: 'question.asked',
  request_id,
  conv_id: 'conversation',
  questions,
});
const ok = (request_id: string) => new Response(JSON.stringify({ success: true, data: { success: true, request_id } }));

it.each(['reply', 'reject'] as const)('late %s HTTP completion cannot clear B or transfer A answers', async action => {
  let finish!: (response: Response) => void;
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>(resolve => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce(ok('B'));
  vi.stubGlobal('fetch', fetch);
  const view = renderHook(() => useQuestionSession());
  act(() => {
    view.result.current.handleQuestionEvent(ask('A'));
  });
  let inFlight!: Promise<void>;
  act(() => {
    inFlight =
      action === 'reply'
        ? view.result.current.replyQuestion('A', [['A answer']])
        : view.result.current.rejectQuestion('A');
  });
  act(() => {
    view.result.current.handleQuestionEvent(ask('B', [null, 'B second']));
    view.result.current.handleQuestionEvent({ type: 'question.rejected', request_id: 'A' });
  });
  await act(async () => {
    finish(ok('A'));
    await inFlight;
  });
  expect(view.result.current.pendingQuestion?.request_id).toBe('B');
  await act(async () => {
    await view.result.current.replyQuestion('B', [[], ['B second answer']]);
  });
  const [url, options] = fetch.mock.calls[1];
  expect(url).toContain('/question/B/reply');
  expect(JSON.parse(options.body)).toEqual({ answers: [[], ['B second answer']] });
  expect(view.result.current.pendingQuestion).toBeNull();
});

it('rejects compressed/shifted answers before any HTTP request', async () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const view = renderHook(() => useQuestionSession());
  act(() => {
    view.result.current.handleQuestionEvent(ask('A', [null, 'Second']));
  });
  await expect(view.result.current.replyQuestion('A', [['Second answer']])).rejects.toThrow('数量不一致');
  expect(fetch).not.toHaveBeenCalled();
  expect(view.result.current.pendingQuestion?.request_id).toBe('A');
});

it('rejects submitting a stale form and keeps business failure recoverable', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: false, err_msg: 'not pending' })));
  vi.stubGlobal('fetch', fetch);
  const view = renderHook(() => useQuestionSession());
  act(() => {
    view.result.current.handleQuestionEvent(ask('B'));
  });
  await expect(view.result.current.replyQuestion('A', [['wrong']])).rejects.toThrow('已更新');
  expect(fetch).not.toHaveBeenCalled();
  await expect(view.result.current.replyQuestion('B', [['right']])).rejects.toThrow('未提交成功');
  expect(view.result.current.pendingQuestion?.request_id).toBe('B');
});
