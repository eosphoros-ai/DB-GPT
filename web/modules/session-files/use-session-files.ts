/**
 * React orchestration for session-file drafts.
 *
 * State lives in the pure reducer; the network lives behind the injected
 * SessionFilesApi seam; concurrency is owned by UploadQueue. Everything that
 * must survive re-renders (latest state, api, attempt tokens, capabilities
 * promise) lives in refs so captured callbacks never read stale closures.
 */

import { useCallback, useEffect, useReducer, useRef } from 'react';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as reducerModule from './reducer.ts';
import type {
  DraftFile,
  LegacyServerFile,
  SessionFileSnapshot,
  SessionFilesApi,
  SessionFilesSendSnapshot,
  UploadCapabilities,
} from './types';
import type { QueueSettledStatus } from './upload-queue';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { MAX_UPLOAD_CONCURRENCY, UploadQueue } from './upload-queue.ts';

export interface UseSessionFilesOptions {
  api: SessionFilesApi;
  concurrency?: number;
  /** Injectable for deterministic tests; defaults to crypto.randomUUID. */
  createClientId?: () => string;
}

export type StageLegacyForSendResult = { ok: true; snapshot: SessionFilesSendSnapshot } | { ok: false; error: string };

const isValidLegacyFile = (file: LegacyServerFile): boolean =>
  !!file && typeof file.file_path === 'string' && !!file.file_path.trim() && !!file.name?.trim();

const isSameLegacyFile = (left: LegacyServerFile, right: LegacyServerFile): boolean =>
  left.name === right.name &&
  left.size === right.size &&
  left.media_type === right.media_type &&
  left.file_path === right.file_path;

export interface UseSessionFiles {
  files: readonly DraftFile[];
  sessionId: string | null;
  capabilities: UploadCapabilities | null;
  capabilitiesSource: 'server' | 'fallback';
  hasHardFailures: boolean;
  isUploading: boolean;
  /**
   * Legacy server-preloaded file staged by an example card (read-only in the
   * rail). Mutually exclusive with local drafts: while staged, `addFiles` is
   * refused; while drafts exist, `stageLegacyForSend` is refused.
   */
  legacyFile: LegacyServerFile | null;
  addFiles: (incoming: File[] | ArrayLike<File>, sessionId: string) => Promise<void>;
  remove: (clientId: string) => void;
  cancel: (clientId: string) => void;
  retryFailed: () => string[];
  /**
   * Atomically stage a legacy server-preloaded example and return the frozen
   * snapshot for this send. The returned snapshot is authoritative even when
   * React has not committed the rail-state dispatch yet.
   */
  stageLegacyForSend: (file: LegacyServerFile, sessionId: string) => StageLegacyForSendResult;
  /** Unstage the legacy example file without touching drafts. */
  clearLegacyFile: () => void;
  /** Wait for in-flight uploads and return the frozen, ordered send payload. */
  prepare: (sessionId: string) => Promise<SessionFilesSendSnapshot>;
  /** Rebuild drafts from the server list for a conversation (switch-resilient). */
  rehydrateFromServer: (sessionId: string) => Promise<SessionFileSnapshot[]>;
  /** Clear the current turn's drafts while keeping the session scope. */
  clearTurn: () => void;
}

export function useSessionFiles(options: UseSessionFilesOptions): UseSessionFiles {
  const { api, concurrency = MAX_UPLOAD_CONCURRENCY } = options;
  const [state, dispatch] = useReducer(
    reducerModule.sessionFilesReducer,
    undefined,
    reducerModule.initialSessionFilesState,
  );

  const stateRef = useRef(state);
  stateRef.current = state;

  const apiRef = useRef(api);
  apiRef.current = api;

  const defaultClientId = () =>
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `draft-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const createClientIdRef = useRef(options.createClientId ?? defaultClientId);
  createClientIdRef.current = options.createClientId ?? defaultClientId;

  const queueRef = useRef<UploadQueue<SessionFileSnapshot> | null>(null);
  if (!queueRef.current) {
    queueRef.current = new UploadQueue<SessionFileSnapshot>({ concurrency });
  }

  // Monotonic attempt tokens per draft resist stale completions.
  const attemptsRef = useRef(new Map<string, number>());
  const capabilitiesPromiseRef = useRef<Promise<UploadCapabilities> | null>(null);

  // Abort every in-flight upload when the owning component unmounts so
  // requests do not run to completion (wasting bandwidth and leaving orphan
  // files) after the UI that owns them is gone.
  useEffect(
    () => () => {
      queueRef.current?.cancelAll();
      attemptsRef.current.clear();
    },
    [],
  );

  const settleUpload = useCallback(
    (
      draft: DraftFile,
      sessionId: string,
      attempt: number,
      promise: Promise<{
        clientId: string;
        status: QueueSettledStatus;
        value?: SessionFileSnapshot;
        error?: unknown;
      }>,
    ) => {
      void promise.then(result => {
        if (attemptsRef.current.get(draft.clientId) !== attempt) return; // stale attempt
        if (result.status === 'done' && result.value) {
          const snapshot = result.value;
          dispatch({ type: 'upload_done', clientId: draft.clientId, attempt, snapshot });
          const previewFile = apiRef.current.previewFile;
          if (!previewFile) return;
          // Preview is orthogonal: a failure here is only a soft warning.
          dispatch({ type: 'preview_start', clientId: draft.clientId });
          void previewFile
            .call(apiRef.current, sessionId, snapshot.file_id)
            .then(() => dispatch({ type: 'preview_ready', clientId: draft.clientId }))
            .catch((error: unknown) =>
              dispatch({
                type: 'preview_failed',
                clientId: draft.clientId,
                error: error instanceof Error ? error.message : String(error),
              }),
            );
          return;
        }
        if (result.status === 'failed') {
          dispatch({
            type: 'upload_failed',
            clientId: draft.clientId,
            attempt,
            error: result.error instanceof Error ? result.error.message : String(result.error),
          });
        }
        // 'cancelled' results are already reflected by the cancel action.
      });
    },
    [],
  );

  const launchUpload = useCallback(
    (draft: DraftFile, sessionId: string) => {
      const file = draft.file;
      if (!file || draft.validation.status !== 'ok') return;
      const queue = queueRef.current!;
      const attempt = (attemptsRef.current.get(draft.clientId) ?? 0) + 1;
      attemptsRef.current.set(draft.clientId, attempt);
      dispatch({ type: 'upload_start', clientId: draft.clientId, attempt });

      const uploadTimeoutSeconds = stateRef.current.capabilities?.upload_request_timeout_seconds;
      const promise = queue.enqueue(draft.clientId, async signal => {
        const snapshots = await apiRef.current.uploadFiles({
          sessionId,
          files: [file],
          signal,
          timeoutMs: uploadTimeoutSeconds != null ? uploadTimeoutSeconds * 1000 : undefined,
          onProgress: ratio => {
            if (attemptsRef.current.get(draft.clientId) !== attempt) return;
            dispatch({
              type: 'upload_progress',
              clientId: draft.clientId,
              attempt,
              progress: ratio,
            });
          },
        });
        const snapshot = snapshots[0];
        if (!snapshot) throw new Error('Upload response contained no file snapshot.');
        return snapshot;
      });
      settleUpload(draft, sessionId, attempt, promise);
    },
    [settleUpload],
  );

  const ensureCapabilities = useCallback((): Promise<UploadCapabilities> => {
    const existing = stateRef.current.capabilities;
    if (existing) return Promise.resolve(existing);
    if (!capabilitiesPromiseRef.current) {
      capabilitiesPromiseRef.current = apiRef.current.fetchCapabilities().then(result => {
        const action = { type: 'capabilities' as const, capabilities: result.capabilities, source: result.source };
        stateRef.current = reducerModule.sessionFilesReducer(stateRef.current, action);
        dispatch(action);
        return result.capabilities;
      });
    }
    return capabilitiesPromiseRef.current;
  }, []);

  const addFiles = useCallback(
    async (incoming: File[] | ArrayLike<File>, sessionId: string): Promise<void> => {
      const files = Array.from(incoming as ArrayLike<File>);
      if (files.length === 0) return;
      // Legacy example file staged: refuse mixing with the file_ids protocol.
      if (stateRef.current.legacyFile) return;
      if (stateRef.current.sessionId !== sessionId) {
        const action = { type: 'bind_session' as const, sessionId };
        stateRef.current = reducerModule.sessionFilesReducer(stateRef.current, action);
        dispatch(action);
      }
      const capabilities = await ensureCapabilities();
      // Capabilities may require a network round-trip. A legacy example can
      // be staged while that request is in flight, so re-check the protocol
      // intent before planning drafts or launching any uploads.
      if (stateRef.current.legacyFile) return;
      const drafts = reducerModule.planAddDrafts({
        existing: stateRef.current.files,
        files,
        capabilities,
        createClientId: () => createClientIdRef.current(),
      });
      if (drafts.length === 0) return;
      const action = {
        type: 'add' as const,
        inputs: drafts.map(draft => ({ clientId: draft.clientId, file: draft.file! })),
      };
      const current = stateRef.current;
      const projected = reducerModule.sessionFilesReducer(current, action);
      const existingClientIds = new Set(current.files.map(draft => draft.clientId));
      const acceptedClientIds = new Set(
        projected.files.filter(draft => !existingClientIds.has(draft.clientId)).map(draft => draft.clientId),
      );
      stateRef.current = projected;
      dispatch(action);
      for (const draft of drafts) {
        if (acceptedClientIds.has(draft.clientId)) {
          launchUpload(draft, sessionId);
        }
      }
    },
    [dispatch, ensureCapabilities, launchUpload],
  );

  const stageLegacyForSend = useCallback((file: LegacyServerFile, sessionId: string): StageLegacyForSendResult => {
    if (!isValidLegacyFile(file)) {
      return { ok: false, error: 'LEGACY_FILE_INVALID' };
    }
    if (!sessionId?.trim()) {
      return { ok: false, error: 'SESSION_SCOPE_INVALID: a conversation id is required' };
    }

    const current = stateRef.current;
    if (current.files.length > 0) {
      // file_path and file_ids are mutually exclusive server-side.
      return {
        ok: false,
        error: 'SESSION_FILES_MIXED_PROTOCOL: remove local uploads before staging a legacy example file',
      };
    }
    if (current.legacyFile && !isSameLegacyFile(current.legacyFile, file)) {
      return {
        ok: false,
        error: 'SESSION_FILES_LEGACY_CONFLICT: remove the staged example file before selecting another one',
      };
    }

    // Project the exact reducer state synchronously and build the immutable
    // send snapshot from that projection. React dispatch remains responsible
    // only for committing the same state to the attachment rail.
    let projected = current;
    if (projected.sessionId !== sessionId) {
      projected = reducerModule.sessionFilesReducer(projected, { type: 'bind_session', sessionId });
    }
    if (!projected.legacyFile) {
      projected = reducerModule.sessionFilesReducer(projected, { type: 'set_legacy', file });
    }

    // Keep callback reads authoritative during React's batched window. The
    // queued reducer actions below commit the identical projection to the UI.
    stateRef.current = projected;

    if (current.sessionId !== sessionId) {
      dispatch({ type: 'bind_session', sessionId });
    }
    if (!current.legacyFile) {
      dispatch({ type: 'set_legacy', file });
    }

    return { ok: true, snapshot: reducerModule.buildSendSnapshot(projected, sessionId) };
  }, []);

  const clearLegacyFile = useCallback(() => {
    dispatch({ type: 'clear_legacy' });
  }, []);

  const remove = useCallback((clientId: string) => {
    queueRef.current!.cancel(clientId);
    attemptsRef.current.delete(clientId);
    // Best-effort server delete for already-uploaded files. A missing/failed
    // delete must not block the local card removal, but leaving the file on
    // the server would let it resurrect on the next rehydrate and keep feeding
    // the agent's file_ids.
    const draft = stateRef.current.files.find(item => item.clientId === clientId);
    const sessionId = stateRef.current.sessionId;
    if (draft?.snapshot?.file_id && sessionId) {
      void apiRef.current.deleteFile(sessionId, draft.snapshot.file_id).catch(() => undefined);
    }
    dispatch({ type: 'remove', clientId });
  }, []);

  const cancel = useCallback((clientId: string) => {
    queueRef.current!.cancel(clientId);
    dispatch({ type: 'upload_cancelled', clientId, attempt: attemptsRef.current.get(clientId) ?? 0 });
  }, []);

  const retryFailed = useCallback((): string[] => {
    const sessionId = stateRef.current.sessionId;
    const failed = stateRef.current.files.filter(draft => draft.upload.status === 'failed');
    for (const draft of failed) {
      dispatch({ type: 'retry', clientId: draft.clientId });
      if (sessionId) launchUpload(draft, sessionId);
    }
    return failed.map(draft => draft.clientId);
  }, [launchUpload]);

  const prepare = useCallback(async (sessionId: string): Promise<SessionFilesSendSnapshot> => {
    const bound = stateRef.current.sessionId;
    if (bound && bound !== sessionId) {
      throw new Error(`SESSION_SCOPE_MISMATCH: bound to ${bound}, requested ${sessionId}`);
    }
    await queueRef.current!.drain();
    return reducerModule.buildSendSnapshot(stateRef.current, sessionId);
  }, []);

  const rehydrateFromServer = useCallback(async (sessionId: string): Promise<SessionFileSnapshot[]> => {
    queueRef.current!.cancelAll();
    attemptsRef.current.clear();
    const snapshots = await apiRef.current.listFiles(sessionId);
    dispatch({ type: 'rehydrate', sessionId, snapshots });
    return snapshots;
  }, []);

  const clearTurn = useCallback(() => {
    queueRef.current!.cancelAll();
    attemptsRef.current.clear();
    dispatch({ type: 'clear_turn' });
  }, []);

  return {
    files: state.files,
    sessionId: state.sessionId,
    capabilities: state.capabilities,
    capabilitiesSource: state.capabilitiesSource,
    hasHardFailures: reducerModule.hasHardFailures(state),
    isUploading: state.files.some(draft => draft.upload.status === 'uploading' || draft.upload.status === 'queued'),
    legacyFile: state.legacyFile,
    addFiles,
    stageLegacyForSend,
    clearLegacyFile,
    remove,
    cancel,
    retryFailed,
    prepare,
    rehydrateFromServer,
    clearTurn,
  };
}
