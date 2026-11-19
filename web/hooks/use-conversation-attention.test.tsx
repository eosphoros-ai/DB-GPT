import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  attentionStorageKey,
  readAttention,
  useConversationAttention,
  useForegroundResultAcknowledgement,
} from './use-conversation-attention';

beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('view acknowledgement', () => {
  it('waits until results have loaded and the tab is visible and focused', () => {
    vi.useFakeTimers();
    const ack = vi.fn();
    const completion = { resultId: 'result', completedAt: 1 };
    vi.spyOn(document, 'hasFocus').mockReturnValue(true);
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    const view = renderHook(({ ready }) => useForegroundResultAcknowledgement('conv', completion, ready, ack), {
      initialProps: { ready: false },
    });
    act(() => vi.advanceTimersByTime(2000));
    expect(ack).not.toHaveBeenCalled();
    view.rerender({ ready: true });
    act(() => vi.advanceTimersByTime(2000));
    expect(ack).not.toHaveBeenCalled();
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    act(() => vi.advanceTimersByTime(1000));
    expect(ack).toHaveBeenCalledExactlyOnceWith('conv', 'result');
  });

  it('cancels viewing when switching away or losing focus', () => {
    vi.useFakeTimers();
    const ack = vi.fn();
    const completion = { resultId: 'result', completedAt: 1 };
    const focus = vi.spyOn(document, 'hasFocus').mockReturnValue(true);
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
    const view = renderHook(({ id }) => useForegroundResultAcknowledgement(id, completion, true, ack), {
      initialProps: { id: 'conv' as string | null },
    });
    view.rerender({ id: null });
    act(() => vi.advanceTimersByTime(1000));
    expect(ack).not.toHaveBeenCalled();
    view.rerender({ id: 'conv' });
    focus.mockReturnValue(false);
    act(() => vi.advanceTimersByTime(1000));
    expect(ack).not.toHaveBeenCalled();
  });
});

describe('completed conversation attention', () => {
  it('persists a completed result until it is acknowledged', () => {
    const first = renderHook(() => useConversationAttention('alice'));
    act(() => first.result.current.markConvCompleted('conv-1', 'result-1'));
    expect(first.result.current.unviewedResults['conv-1'].resultId).toBe('result-1');
    first.unmount();
    const restored = renderHook(() => useConversationAttention('alice'));
    expect(restored.result.current.unviewedResults['conv-1'].resultId).toBe('result-1');
    act(() => restored.result.current.markConvViewed('conv-1', 'result-1'));
    expect(restored.result.current.unviewedResults).toEqual({});
    expect(readAttention(attentionStorageKey('alice'))).toEqual({});
  });

  it('does not let viewing an old result acknowledge a new completion', () => {
    const { result } = renderHook(() => useConversationAttention('alice'));
    act(() => result.current.markConvCompleted('conv-1', 'old'));
    act(() => result.current.markConvCompleted('conv-1', 'new'));
    act(() => result.current.markConvViewed('conv-1', 'old'));
    expect(result.current.unviewedResults['conv-1'].resultId).toBe('new');
  });

  it('merges other tabs and synchronizes read acknowledgements', () => {
    const { result } = renderHook(() => useConversationAttention('alice'));
    act(() => result.current.markConvCompleted('first', 'r1'));
    const key = attentionStorageKey('alice');
    const values = readAttention(key);
    values.second = { resultId: 'r2', completedAt: Date.now() };
    localStorage.setItem(key, JSON.stringify(values));
    act(() => result.current.markConvCompleted('third', 'r3'));
    expect(Object.keys(result.current.unviewedResults)).toHaveLength(3);
    localStorage.setItem(key, '{}');
    act(() => window.dispatchEvent(new StorageEvent('storage', { key })));
    expect(result.current.unviewedResults).toEqual({});
    act(() => result.current.markConvCompleted('fourth', 'r4'));
    expect(Object.keys(result.current.unviewedResults)).toEqual(['fourth']);
  });

  it('isolates users and clears deleted or restarted tasks', () => {
    const alice = renderHook(() => useConversationAttention('alice'));
    act(() => alice.result.current.markConvCompleted('conv', 'r1'));
    const bob = renderHook(() => useConversationAttention('bob'));
    expect(bob.result.current.unviewedResults).toEqual({});
    act(() => alice.result.current.clearConvAttention('conv'));
    expect(alice.result.current.unviewedResults).toEqual({});
  });

  it('ignores corrupt storage and invalid records', () => {
    const key = attentionStorageKey('alice');
    localStorage.setItem(key, '{invalid');
    expect(readAttention(key)).toEqual({});
    localStorage.setItem(key, JSON.stringify({ bad: {}, good: { resultId: 'r1', completedAt: 1 } }));
    expect(Object.keys(readAttention(key))).toEqual(['good']);
  });
});
