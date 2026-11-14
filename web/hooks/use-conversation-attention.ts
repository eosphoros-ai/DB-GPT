import { useCallback, useEffect, useRef, useState } from 'react';

export interface UnviewedResult {
  resultId: string;
  completedAt: number;
}
export type ConversationAttention = Record<string, UnviewedResult>;

export const attentionStorageKey = (userId: string) => `dbgpt:unviewed-results:v1:${userId || 'default'}`;

export function readAttention(key: string): ConversationAttention {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([id, value]) => {
        const item = value as UnviewedResult;
        return id && item && typeof item.resultId === 'string' && Number.isFinite(item.completedAt);
      }),
    ) as ConversationAttention;
  } catch {
    return {};
  }
}

/** A completion is acknowledged only after its result is rendered in a foreground page. */
export function useConversationAttention(userId: string) {
  const key = attentionStorageKey(userId);
  const [unviewedResults, setUnviewedResults] = useState<ConversationAttention>({});
  const current = useRef<ConversationAttention>({});
  useEffect(() => {
    current.current = readAttention(key);
    setUnviewedResults(current.current);
    const onStorage = (event: StorageEvent) => {
      if (event.key === key || event.key === null) {
        current.current = readAttention(key);
        setUnviewedResults(current.current);
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [key]);

  const update = useCallback(
    (mutate: (value: ConversationAttention) => ConversationAttention) => {
      // Read before writing so one tab does not overwrite another tab's completions.
      let value = current.current;
      try {
        // Probe storage separately: unavailable storage uses the in-memory state.
        localStorage.getItem(key);
        value = readAttention(key);
      } catch {
        /* Storage is unavailable. */
      }
      const next = mutate(value);
      const bounded = Object.fromEntries(
        Object.entries(next)
          .sort((a, b) => b[1].completedAt - a[1].completedAt)
          .slice(0, 500),
      );
      try {
        localStorage.setItem(key, JSON.stringify(bounded));
      } catch {
        // Storage may be disabled; the current page still keeps the status.
      }
      current.current = bounded;
      setUnviewedResults(bounded);
    },
    [key],
  );

  const markConvCompleted = useCallback(
    (id: string, resultId: string) => {
      if (!id || !resultId) return;
      update(value =>
        value[id]?.resultId === resultId
          ? value
          : {
              ...value,
              [id]: { resultId, completedAt: Date.now() },
            },
      );
    },
    [update],
  );
  const markConvViewed = useCallback(
    (id: string, resultId: string) => {
      update(value => {
        // A delayed acknowledgement must not clear a newer completion.
        if (value[id]?.resultId !== resultId) return value;
        const next = { ...value };
        delete next[id];
        return next;
      });
    },
    [update],
  );
  const clearConvAttention = useCallback(
    (id: string) => {
      update(value => {
        const next = { ...value };
        delete next[id];
        return next;
      });
    },
    [update],
  );
  return { unviewedResults, markConvCompleted, markConvViewed, clearConvAttention };
}

export function useForegroundResultAcknowledgement(
  conversationId: string | null,
  completion: UnviewedResult | undefined,
  resultReady: boolean,
  acknowledge: (id: string, resultId: string) => void,
) {
  useEffect(() => {
    if (!conversationId || !completion || !resultReady) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = () => {
      if (timer) clearTimeout(timer);
      if (document.visibilityState !== 'visible' || !document.hasFocus()) return;
      timer = setTimeout(() => {
        if (document.visibilityState === 'visible' && document.hasFocus()) {
          acknowledge(conversationId, completion.resultId);
        }
      }, 1000);
    };
    check();
    window.addEventListener('focus', check);
    document.addEventListener('visibilitychange', check);
    return () => {
      if (timer) clearTimeout(timer);
      window.removeEventListener('focus', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, [conversationId, completion, resultReady, acknowledge]);
}
