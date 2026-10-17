import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import useChat from './use-chat';

const transport = vi.hoisted(() => ({ onmessage: undefined as undefined | ((event: { data: string }) => void) }));
vi.mock('@/utils', () => ({ getUserId: () => 'test-user' }));
vi.mock('@/app/chat-context', async () => ({
  ChatContext: (await import('react')).createContext({ scene: 'chat_react_agent' }),
}));
vi.mock('@/app/i18n', () => ({ default: { t: (key: string) => key } }));
vi.mock('@microsoft/fetch-event-source', () => ({
  EventStreamContentType: 'text/event-stream',
  fetchEventSource: vi.fn(async (_url, options) => {
    transport.onmessage = options.onmessage;
  }),
}));
afterEach(() => vi.unstubAllGlobals());

it('chat transport routes original shapes and reordered events to the right reply', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify({ success: true, data: { success: true, request_id: 'B' } })));
  vi.stubGlobal('fetch', fetch);
  const view = renderHook(() => useChat({}));
  await act(async () => {
    await view.result.current.chat({ chatId: 'conversation', data: { user_input: 'ask' }, onMessage: vi.fn() });
  });
  act(() => {
    for (const payload of [
      { type: 'question.asked', request_id: 'A', conv_id: 'conversation', questions: ['First'], sequence: 1 },
      { type: 'question.asked', request_id: 'B', conv_id: 'conversation', questions: [null, 'Second'], sequence: 2 },
      { type: 'question.replied', request_id: 'A' },
      { type: 'question.rejected', request_id: 'A' },
    ])
      transport.onmessage!({ data: JSON.stringify(payload) });
  });
  expect(view.result.current.pendingQuestion?.request_id).toBe('B');
  await act(async () => {
    await view.result.current.replyQuestion('B', [[], ['Second answer']]);
  });
  expect(fetch.mock.calls[0][0]).toContain('/question/B/reply');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ answers: [[], ['Second answer']] });
});
