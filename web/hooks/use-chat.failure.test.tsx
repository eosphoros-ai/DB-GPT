import { act, renderHook } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import useChat from './use-chat';

const transport = vi.hoisted(() => ({ calls: [] as { url: string; options: any }[] }));
vi.mock('@/utils', () => ({ getUserId: () => 'test-user' }));
vi.mock('@/app/chat-context', async () => ({
  ChatContext: (await import('react')).createContext({ scene: 'chat_react_agent' }),
}));
vi.mock('@/app/i18n', () => ({ default: { t: (key: string) => key } }));
vi.mock('@microsoft/fetch-event-source', () => ({
  EventStreamContentType: 'text/event-stream',
  fetchEventSource: vi.fn(async (url, options) => {
    transport.calls.push({ url, options });
  }),
}));
beforeEach(() => {
  transport.calls = [];
});
const emit = (payload: unknown, index = transport.calls.length - 1) =>
  act(() => transport.calls[index].options.onmessage({ data: JSON.stringify(payload) }));
const failure = {
  type: 'dashboard.generation.failed',
  dashboard_id: 'board',
  generation_id: 'run',
  summary: 'operations[0].value：replace 必须提供 value。',
  stage_label: '生成批注修改提案',
  retry_hint: '本轮已停止；重新发起本次操作。',
};

it('selects the registered ReAct endpoint and preserves user/model/data-source binding', async () => {
  const view = renderHook(() => useChat({}));
  const data = {
    user_input: '修改图表',
    model_name: 'deepseek-v4-flash',
    select_param: 'Walmart_Sales',
    chat_mode: 'chat_react_agent',
  };
  await act(() => view.result.current.chat({ chatId: 'C', data, onMessage: vi.fn() }));
  expect(transport.calls[0].url).toBe('/api/v1/chat/react-agent');
  expect(JSON.parse(transport.calls[0].options.body)).toMatchObject({ ...data, conv_uid: 'C' });
  expect(transport.calls[0].options.headers['user-id']).toBe('test-user');
});

it.each(['chat_normal', 'chat_agent', 'chat_flow'])('keeps %s on the completions endpoint', async chat_mode => {
  const view = renderHook(() => useChat({}));
  const onMessage = vi.fn();
  await act(() => view.result.current.chat({ chatId: 'C', data: { user_input: 'ask', chat_mode }, onMessage }));
  expect(transport.calls[0].url).toBe('/api/v1/chat/completions');
  emit({ choices: [{ message: { content: '正常回答' } }] });
  expect(onMessage).toHaveBeenCalledWith('正常回答');
});

it('honours an explicit endpoint and only completes typed agent messages on done', async () => {
  const view = renderHook(() => useChat({ queryAgentURL: '/custom-agent' }));
  const onMessage = vi.fn(),
    onDone = vi.fn();
  await act(() => view.result.current.chat({ chatId: 'C', data: { user_input: 'ask' }, onMessage, onDone }));
  expect(transport.calls[0].url).toBe('/custom-agent');
  emit({ type: 'tool_start', name: 'sql' });
  expect(onMessage).not.toHaveBeenCalled();
  expect(onDone).not.toHaveBeenCalled();
  emit({ type: 'final', content: '最终回答', citations: [] });
  expect(onMessage).toHaveBeenCalledExactlyOnceWith('最终回答');
  emit({ type: 'done' });
  emit({ type: 'done' });
  expect(onDone).toHaveBeenCalledOnce();
});

it('shows the exact structured failure, stops loading even without done, never turns it into a question', async () => {
  const view = renderHook(() => useChat({}));
  const onMessage = vi.fn(),
    onDone = vi.fn(),
    onDashboardEvent = vi.fn();
  await act(() =>
    view.result.current.chat({ chatId: 'C', data: { user_input: 'ask' }, onMessage, onDone, onDashboardEvent }),
  );
  emit(failure);
  emit({ type: 'question.asked', request_id: 'technical', conv_id: 'C', questions: ['Why parse failed?'] });
  emit({ type: 'dashboard.created', dashboard_id: 'board', generation_id: 'run' });
  emit({ type: 'final', content: 'late final' });
  emit({ type: 'done' });
  expect(onDashboardEvent).toHaveBeenCalledExactlyOnceWith(failure);
  expect(onDone).toHaveBeenCalledOnce();
  expect(onMessage).not.toHaveBeenCalled();
  expect(view.result.current.pendingQuestion).toBeNull();
});

it('late old failures, questions and close cannot clear or overwrite the new request', async () => {
  const view = renderHook(() => useChat({}));
  const old = { onMessage: vi.fn(), onDone: vi.fn(), onClose: vi.fn(), onDashboardEvent: vi.fn() };
  const next = { onMessage: vi.fn(), onDone: vi.fn(), onDashboardEvent: vi.fn() };
  await act(() => view.result.current.chat({ chatId: 'C', data: { user_input: 'first' }, ...old }));
  emit(failure);
  await act(() => view.result.current.chat({ chatId: 'C', data: { user_input: 'second' }, ...next }));
  emit({ type: 'question.asked', request_id: 'B', conv_id: 'C', questions: [null, '新问题'] });
  emit(failure, 0);
  emit({ type: 'question.replied', request_id: 'B' }, 0);
  act(() => transport.calls[0].options.onclose());
  expect(view.result.current.pendingQuestion?.request_id).toBe('B');
  expect(old.onClose).not.toHaveBeenCalled();
  expect(old.onDone).toHaveBeenCalledOnce();
  expect(next.onDone).not.toHaveBeenCalled();
  expect(next.onDashboardEvent).not.toHaveBeenCalled();
});

it('rejects stale generation IDs within the current transport', async () => {
  const view = renderHook(() => useChat({}));
  const onDashboardEvent = vi.fn(),
    onDone = vi.fn();
  await act(() =>
    view.result.current.chat({
      chatId: 'C',
      data: { user_input: 'ask' },
      onMessage: vi.fn(),
      onDashboardEvent,
      onDone,
    }),
  );
  emit({ type: 'dashboard.generation.started', dashboard_id: 'board', generation_id: 'new-run' });
  emit(failure);
  expect(onDashboardEvent).toHaveBeenCalledOnce();
  expect(onDone).not.toHaveBeenCalled();
});

it('routes typed errors to failure, not a question or undefined answer', async () => {
  const view = renderHook(() => useChat({}));
  const onMessage = vi.fn(),
    onError = vi.fn();
  await act(() => view.result.current.chat({ chatId: 'C', data: { user_input: 'ask' }, onMessage, onError }));
  emit({ type: 'error', message: '工具参数错误' });
  emit({ type: 'question.asked', request_id: 'technical', questions: ['Why?'] });
  expect(onError).toHaveBeenCalledExactlyOnceWith('工具参数错误');
  expect(onMessage).not.toHaveBeenCalled();
  expect(view.result.current.pendingQuestion).toBeNull();
});
