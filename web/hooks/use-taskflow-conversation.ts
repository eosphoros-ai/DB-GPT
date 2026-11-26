import { generationApi } from '@/client/api/taskflow-generation';
import type { EditingSnapshot, GenerationRequest, GenerationSession } from '@/types/taskflow-generation';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * The canvas stays the local source of truth. Serialized synchronization makes
 * every generation/save/run flush preceding manual edits before using versions.
 */
export function useTaskflowConversation(
  snapshot: EditingSnapshot,
  enabled: boolean,
  storageKey: string,
  onSnapshot: (snapshot: EditingSnapshot) => void,
) {
  const [session, setSession] = useState<GenerationSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(snapshot);
  latest.current = snapshot;
  const current = useRef<GenerationSession | null>(null);
  const initialize = useRef<Promise<GenerationSession> | null>(null);
  const syncQueue = useRef<Promise<unknown>>(Promise.resolve());
  const mounted = useRef(true);
  const activePoll = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSnapshotRef = useRef(onSnapshot);
  onSnapshotRef.current = onSnapshot;

  const accept = useCallback(
    (state: GenerationSession, apply = false) => {
      current.current = state;
      if (mounted.current) {
        setSession(state);
        if (apply) onSnapshotRef.current(state.snapshot);
      }
      localStorage.setItem(storageKey, state.session_id);
      if (state.snapshot.meta.uid)
        localStorage.setItem(`taskflow-session:${state.snapshot.meta.uid}`, state.session_id);
      return state;
    },
    [storageKey],
  );

  const ensure = useCallback(async () => {
    if (current.current) return current.current;
    if (!initialize.current) {
      initialize.current = (async () => {
        const sid = localStorage.getItem(storageKey);
        if (sid) {
          try {
            return accept(await generationApi(`/${sid}`, undefined, 'GET'), true);
          } catch (err: any) {
            // Only a missing/deleted session is safe to replace.
            if (!err.message.includes('不存在')) throw err;
            localStorage.removeItem(storageKey);
          }
        }
        const state = await generationApi(
          '',
          latest.current.meta.uid ? { flow_uid: latest.current.meta.uid } : { snapshot: latest.current },
        );
        return accept(state, true);
      })();
      initialize.current.catch(() => {
        initialize.current = null;
      });
    }
    return initialize.current;
  }, [accept, storageKey]);

  const sync = useCallback(async () => {
    const operation = syncQueue.current
      .catch(() => {})
      .then(async () => {
        const state = await ensure();
        const local = latest.current;
        if (JSON.stringify(local) === JSON.stringify(state.snapshot)) return state;
        const result = await generationApi(
          `/${state.session_id}/draft`,
          {
            expected_draft_revision: state.draft_revision,
            snapshot: local,
          },
          'PUT',
        );
        return accept(result);
      });
    syncQueue.current = operation;
    return operation;
  }, [ensure, accept]);

  useEffect(() => {
    if (enabled) void ensure().catch(err => setError(err.message));
  }, [enabled, ensure]);

  const serialized = JSON.stringify(snapshot);
  const hasSession = !!session;
  useEffect(() => {
    if (!enabled || !hasSession) return;
    const timer = setTimeout(() => {
      void sync().catch(err => setError(err.message));
    }, 450);
    return () => clearTimeout(timer);
  }, [serialized, enabled, hasSession, sync]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (activePoll.current) clearTimeout(activePoll.current);
    };
  }, []);

  const poll = useCallback(
    (sid: string, rid: string, baseSnapshot: string) => {
      const check = async () => {
        if (!mounted.current) return;
        try {
          const state = await generationApi(`/${sid}`, undefined, 'GET');
          const request = state.requests[rid];
          const apply =
            request?.status === 'succeeded' &&
            state.draft_revision !== current.current?.draft_revision &&
            JSON.stringify(latest.current) === baseSnapshot;
          accept(state, apply);
          if (request?.status === 'running') {
            activePoll.current = setTimeout(check, 900);
          } else {
            setBusy(false);
            if (request?.status === 'failed') setError(request.error || '生成失败');
          }
        } catch (err: any) {
          setError(err.message);
          // Query the original request after a transient disconnect; never submit
          // another generation implicitly.
          activePoll.current = setTimeout(check, 2500);
        }
      };
      void check();
    },
    [accept],
  );

  const resumed = useRef(false);
  useEffect(() => {
    if (!session || resumed.current) return;
    resumed.current = true;
    const req = Object.values(session.requests).find(item => item.status === 'running');
    if (req) {
      setBusy(true);
      poll(session.session_id, req.request_id, JSON.stringify(latest.current));
    }
  }, [session, poll]);

  const send = useCallback(
    async (
      text: string,
      model: string,
      local: boolean,
      replace: boolean,
      answers: Record<string, string>,
      selectedId: string | null,
    ) => {
      setBusy(true);
      setError(null);
      try {
        const state = await sync();
        const baseSnapshot = JSON.stringify(latest.current);
        const request = await generationApi<GenerationRequest>(`/${state.session_id}/messages`, {
          client_message_id: crypto.randomUUID(),
          expected_draft_revision: state.draft_revision,
          expected_context_revision: state.context_revision,
          text,
          model,
          answers,
          replace_candidate: replace,
          scope: local ? { type: 'nodes', node_ids: [selectedId] } : { type: 'flow' },
        });
        poll(state.session_id, request.request_id, baseSnapshot);
        return true;
      } catch (err: any) {
        setError(err.message);
        setBusy(false);
        return false;
      }
    },
    [sync, poll],
  );

  const action = useCallback(
    async (name: 'apply' | 'discard' | 'undo' | 'cancel') => {
      setError(null);
      setBusy(true);
      try {
        const state = name === 'cancel' ? await ensure() : await sync();
        const active = Object.values(state.requests).find(req => req.status === 'running');
        const path =
          name === 'cancel'
            ? `/requests/${active?.request_id}/cancel`
            : name === 'undo'
              ? '/undo'
              : `/candidates/${state.candidate?.candidate_id}/${name}`;
        const baseSnapshot = JSON.stringify(latest.current);
        const result = await generationApi(`/${state.session_id}${path}`, {});
        accept(result, (name === 'apply' || name === 'undo') && JSON.stringify(latest.current) === baseSnapshot);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setBusy(false);
      }
    },
    [ensure, sync, accept],
  );

  const save = useCallback(
    async (publish: boolean) => {
      const state = await sync();
      const result = await generationApi(`/${state.session_id}/save`, {
        expected_draft_revision: state.draft_revision,
        publish,
      });
      accept(result, true);
      return result;
    },
    [sync, accept],
  );

  const refresh = useCallback(async () => {
    const state = await ensure();
    return accept(await generationApi(`/${state.session_id}`, undefined, 'GET'));
  }, [ensure, accept]);

  return { session, busy, error, send, action, sync, save, refresh };
}
