import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';

import type { SessionFileSnapshot, SessionFilesApi, UploadCapabilities } from './types';
import type { UseSessionFiles } from './use-session-files';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { extInfoForSend, snapshotsForSend } from './home-adapter.ts';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { useSessionFiles } from './use-session-files.ts';

/**
 * Minimal hooks runtime so the orchestration hook can be tested with
 * node:test only (no extra test framework). Supports the hooks the module
 * uses: useReducer/useState/useRef/useCallback. Dispatch re-renders
 * synchronously by default; selected tests defer it to reproduce React's
 * event-batching window and exercise captured page renders.
 */
const REACT_INTERNALS = (
  React as unknown as {
    __SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED: {
      ReactCurrentDispatcher: { current: unknown };
    };
  }
).__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;

interface StateCell {
  kind: 'reducer' | 'ref';
  value: unknown;
  dispatch?: (action: unknown) => void;
}

function renderHook<Result>(
  hookFactory: () => Result,
  options: { batchReducerDispatch?: boolean } = {},
): { result: { readonly current: Result } } {
  const cells: StateCell[] = [];
  let cursor = 0;
  let current!: Result;
  let renderQueued = false;

  const dispatcher = {
    useReducer<S, A>(
      reducer: (state: S, action: A) => S,
      initialArg: S,
      init?: (arg: S) => S,
    ): [S, (action: A) => void] {
      const index = cursor++;
      if (!cells[index]) {
        const cell: StateCell = {
          kind: 'reducer',
          value: init ? init(initialArg) : initialArg,
        };
        cell.dispatch = (action: unknown) => {
          cell.value = reducer(cell.value as S, action as A);
          if (!options.batchReducerDispatch) {
            rerender();
          } else if (!renderQueued) {
            renderQueued = true;
            setImmediate(() => {
              renderQueued = false;
              rerender();
            });
          }
        };
        cells[index] = cell;
      }
      const cell = cells[index];
      return [cell.value as S, cell.dispatch as (action: A) => void];
    },
    useState<S>(initial: S | (() => S)): [S, (value: S | ((prev: S) => S)) => void] {
      return dispatcher.useReducer(
        (state: S, action: S | ((prev: S) => S)) =>
          typeof action === 'function' ? (action as (prev: S) => S)(state) : action,
        undefined as unknown as S,
        () => (typeof initial === 'function' ? (initial as () => S)() : initial),
      );
    },
    useRef<T>(initial: T): { current: T } {
      const index = cursor++;
      if (!cells[index]) {
        cells[index] = { kind: 'ref', value: { current: initial } };
      }
      return cells[index].value as { current: T };
    },
    useCallback<T extends (...args: never[]) => unknown>(fn: T): T {
      cursor++;
      return fn;
    },
    useEffect(fn: () => unknown): void {
      // Cleanup-only effect (unmount aborts). This harness has no unmount
      // step, so consume the hook slot, run the setup (a no-op for
      // cleanup-only effects), and drop the returned cleanup. Real unmount
      // behavior is covered by component tests.
      cursor++;
      void fn();
    },
  };

  function rerender(): void {
    cursor = 0;
    const previous = REACT_INTERNALS.ReactCurrentDispatcher.current;
    REACT_INTERNALS.ReactCurrentDispatcher.current = dispatcher;
    try {
      current = hookFactory();
    } finally {
      REACT_INTERNALS.ReactCurrentDispatcher.current = previous;
    }
  }

  rerender();
  return {
    result: {
      get current() {
        return current;
      },
    },
  };
}

// ---------------------------------------------------------------------------
// Test doubles
// ---------------------------------------------------------------------------

const CAPS: UploadCapabilities = {
  max_files_per_upload: 5,
  max_file_bytes: 1024,
  max_upload_bytes: 10 * 1024,
  max_owner_bytes: 10 * 1024 * 1024,
  upload_request_timeout_seconds: 180,
  upload_concurrency: 3,
  supported_extensions: ['.csv'],
};

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise(resolve => setImmediate(resolve));

interface UploadCall {
  sessionId: string;
  files: readonly File[];
  signal?: AbortSignal;
  onProgress?: (ratio: number) => void;
  gate: Deferred<SessionFileSnapshot[]>;
}

function snapOf(fileId: string, name: string, ordinal: number, size = 10): SessionFileSnapshot {
  return {
    file_id: fileId,
    name,
    size,
    media_type: 'text/csv',
    kind: 'csv',
    status: 'ready',
    ordinal,
    error_code: null,
  };
}

function makeFile(name: string, size = 10, lastModified = 1): File {
  return new File([new Uint8Array(size)], name, { lastModified });
}

interface FakeApi extends SessionFilesApi {
  uploads: UploadCall[];
  listCalls: string[];
  deleted: string[];
}

function makeFakeApi(overrides: Partial<SessionFilesApi> = {}): FakeApi {
  const uploads: UploadCall[] = [];
  const listCalls: string[] = [];
  const deleted: string[] = [];
  return {
    uploads,
    listCalls,
    deleted,
    async fetchCapabilities() {
      return { capabilities: CAPS, source: 'server' };
    },
    uploadFiles(params) {
      const gate = deferred<SessionFileSnapshot[]>();
      uploads.push({ ...params, gate });
      const { signal } = params;
      if (!signal) return gate.promise;
      // Mirror the real adapter: aborting the signal rejects the request.
      return Promise.race([
        gate.promise,
        new Promise<SessionFileSnapshot[]>((_, reject) => {
          const onAbort = () => reject(new DOMException('The operation was aborted.', 'AbortError'));
          if (signal.aborted) {
            onAbort();
            return;
          }
          signal.addEventListener('abort', onAbort, { once: true });
        }),
      ]);
    },
    async listFiles(sessionId: string) {
      listCalls.push(sessionId);
      return [];
    },
    async deleteFile(_sessionId: string, fileId: string) {
      deleted.push(fileId);
    },
    ...overrides,
  };
}

function setup(api: FakeApi = makeFakeApi(), options: { batchReducerDispatch?: boolean } = {}) {
  let seq = 0;
  const harness = renderHook(
    () =>
      useSessionFiles({
        api,
        createClientId: () => `c${seq++}`,
      }),
    options,
  );
  return { api, ...harness };
}

async function flush(): Promise<void> {
  await tick();
  await tick();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test('addFiles validates, queues and uploads; done snapshot lands on the draft', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv')], 'sess-1');
  assert.equal(result.current.files.length, 1);
  assert.equal(result.current.files[0].clientId, 'c0');
  assert.equal(result.current.sessionId, 'sess-1');
  assert.equal(result.current.files[0].upload.status, 'uploading');
  assert.equal(result.current.isUploading, true);
  assert.equal(api.uploads.length, 1);
  assert.equal(api.uploads[0].sessionId, 'sess-1');

  api.uploads[0].onProgress?.(0.25);
  await flush();
  api.uploads[0].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  await flush();

  const draft = result.current.files[0];
  assert.equal(draft.upload.status, 'done');
  assert.equal(draft.snapshot?.file_id, 'sf_a');
  assert.equal(result.current.isUploading, false);
  assert.equal(result.current.hasHardFailures, false);
});

test('failed upload hard-blocks prepare until retry succeeds with the same clientId', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv')], 'sess-1');
  api.uploads[0].gate.reject(new Error('connection reset'));
  await flush();

  assert.equal(result.current.files[0].upload.status, 'failed');
  assert.equal(result.current.hasHardFailures, true);
  await assert.rejects(() => result.current.prepare('sess-1'), /SESSION_FILES_HARD_FAILURE/);

  const retried = result.current.retryFailed();
  assert.deepEqual(retried, ['c0']);
  assert.equal(result.current.files[0].clientId, 'c0');
  assert.equal(api.uploads.length, 2);

  api.uploads[1].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  await flush();

  const snapshot = await result.current.prepare('sess-1');
  assert.deepEqual([...snapshot.fileIds], ['sf_a']);
  assert.equal(result.current.files[0].upload.status, 'done');
});

test('prepare waits for in-flight uploads before returning the frozen snapshot', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv'), makeFile('b.csv')], 'sess-1');
  assert.equal(api.uploads.length, 2);

  let preparedValue: unknown = null;
  const prepared = result.current.prepare('sess-1').then(value => {
    preparedValue = value;
    return value;
  });

  await flush();
  assert.equal(preparedValue, null, 'prepare must not resolve while uploads are in flight');

  api.uploads[1].gate.resolve([snapOf('sf_b', 'b.csv', 2)]);
  await flush();
  assert.equal(preparedValue, null);

  api.uploads[0].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  const snapshot = await prepared;
  assert.deepEqual([...snapshot.fileIds], ['sf_a', 'sf_b']);

  assert.equal(Object.isFrozen(snapshot), true);
  assert.equal(Object.isFrozen(snapshot.fileIds), true);
  assert.equal(Object.isFrozen(snapshot.snapshotById), true);
  assert.equal(Object.isFrozen(snapshot.snapshotById['sf_a']), true);
});

test('old closures never read stale state (prepare via a captured handle)', async () => {
  const { api, result } = setup();
  const firstHandle: UseSessionFiles = result.current;

  await firstHandle.addFiles([makeFile('a.csv')], 'sess-1');
  api.uploads[0].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  await flush();

  // Many renders happened since firstHandle was captured; prepare through it
  // must still observe the latest state.
  const snapshot = await firstHandle.prepare('sess-1');
  assert.deepEqual([...snapshot.fileIds], ['sf_a']);
});

test('send snapshot stays immutable against caller mutation attempts', async () => {
  const { api, result } = setup();
  await result.current.addFiles([makeFile('a.csv')], 'sess-1');
  api.uploads[0].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  await flush();

  const snapshot = await result.current.prepare('sess-1');
  const before = JSON.stringify(snapshot);
  try {
    (snapshot.fileIds as string[]).push('evil');
  } catch {
    /* strict mode throws */
  }
  try {
    (snapshot.snapshotById as Record<string, unknown>)['evil'] = {};
  } catch {
    /* strict mode throws */
  }
  assert.equal(JSON.stringify(snapshot), before);
});

test('cancel aborts the request, excludes the file from send and is not retryable', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv'), makeFile('b.csv')], 'sess-1');
  const [a] = result.current.files.map(f => f.clientId);

  result.current.cancel(a);
  assert.equal(result.current.files[0].upload.status, 'cancelled');
  assert.equal(api.uploads[0].signal?.aborted, true);

  api.uploads[1].onProgress?.(0.5);
  api.uploads[1].gate.resolve([snapOf('sf_b', 'b.csv', 2)]);
  await flush();

  assert.deepEqual(result.current.retryFailed(), []);
  const snapshot = await result.current.prepare('sess-1');
  assert.deepEqual([...snapshot.fileIds], ['sf_b']);
});

test('remove drops the in-flight draft and stale completions are ignored', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv'), makeFile('b.csv')], 'sess-1');
  const [a] = result.current.files.map(f => f.clientId);

  result.current.remove(a);
  assert.deepEqual(
    result.current.files.map(f => f.clientId),
    ['c1'],
  );
  assert.equal(api.uploads[0].signal?.aborted, true);

  // The aborted request settles late — nothing may resurrect the removed file.
  api.uploads[0].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  api.uploads[1].gate.resolve([snapOf('sf_b', 'b.csv', 2)]);
  await flush();

  assert.equal(result.current.files.length, 1);
  assert.equal(result.current.files[0].snapshot?.file_id, 'sf_b');
});

test('preview failure is a soft warning and never blocks prepare', async () => {
  const { api, result } = setup(
    makeFakeApi({
      async previewFile() {
        throw new Error('preview exploded');
      },
    }),
  );

  await result.current.addFiles([makeFile('a.csv')], 'sess-1');
  api.uploads[0].gate.resolve([snapOf('sf_a', 'a.csv', 1)]);
  await flush();

  const draft = result.current.files[0];
  assert.equal(draft.preview.status, 'preview_failed');
  assert.equal(draft.upload.status, 'done');

  const snapshot = await result.current.prepare('sess-1');
  assert.deepEqual([...snapshot.fileIds], ['sf_a']);
});

test('rehydrateFromServer restores the conversation-scoped drafts from server list', async () => {
  const { api, result } = setup(
    makeFakeApi({
      async listFiles(sessionId: string) {
        assert.equal(sessionId, 'sess-9');
        return [snapOf('sf_2', 'two.csv', 2), snapOf('sf_1', 'one.csv', 1)];
      },
    }),
  );

  await result.current.rehydrateFromServer('sess-9');

  assert.deepEqual(
    result.current.files.map(f => [f.snapshot?.file_id, f.upload.status]),
    [
      ['sf_1', 'done'],
      ['sf_2', 'done'],
    ],
  );
  assert.equal(api.uploads.length, 0, 'rehydrated drafts must not re-upload');
  assert.deepEqual(
    result.current.files.map(file => file.preview.status),
    ['ready', 'ready'],
  );

  const snapshot = await result.current.prepare('sess-9');
  assert.deepEqual([...snapshot.fileIds], ['sf_1', 'sf_2']);
});

test('clearTurn empties the draft list and aborts in-flight uploads', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv')], 'sess-1');
  result.current.clearTurn();

  assert.equal(result.current.files.length, 0);
  assert.equal(api.uploads[0].signal?.aborted, true);
  assert.equal(result.current.sessionId, 'sess-1', 'session scope survives turn cleanup');

  api.uploads[0].gate.reject(new Error('aborted'));
  await flush();
  assert.equal(result.current.files.length, 0);

  const snapshot = await result.current.prepare('sess-1');
  assert.deepEqual([...snapshot.fileIds], []);
});

test('resetSession aborts in-flight uploads and detaches the session scope', async () => {
  const { api, result } = setup();

  await result.current.addFiles([makeFile('a.csv')], 'sess-1');
  result.current.resetSession();

  assert.equal(result.current.files.length, 0);
  assert.equal(result.current.sessionId, null);
  assert.equal(api.uploads[0].signal?.aborted, true);

  api.uploads[0].gate.reject(new Error('aborted'));
  await flush();
  assert.equal(result.current.files.length, 0);
  assert.equal(result.current.sessionId, null);
});

test('a late rehydrate cannot restore files after resetSession', async () => {
  const listGate = deferred<SessionFileSnapshot[]>();
  const { result } = setup(
    makeFakeApi({
      listFiles: () => listGate.promise,
    }),
  );

  const rehydrate = result.current.rehydrateFromServer('sess-old');
  result.current.resetSession();
  listGate.resolve([snapOf('sf_old', 'old.csv', 1)]);
  await rehydrate;
  await flush();

  assert.equal(result.current.sessionId, null);
  assert.equal(result.current.files.length, 0);
});

test('overlapping rehydrates are latest-wins across conversation switches', async () => {
  const firstList = deferred<SessionFileSnapshot[]>();
  const secondList = deferred<SessionFileSnapshot[]>();
  const { result } = setup(
    makeFakeApi({
      listFiles: sessionId => (sessionId === 'sess-first' ? firstList.promise : secondList.promise),
    }),
  );

  const first = result.current.rehydrateFromServer('sess-first');
  const second = result.current.rehydrateFromServer('sess-second');
  secondList.resolve([snapOf('sf_second', 'second.csv', 1)]);
  await second;
  firstList.resolve([snapOf('sf_first', 'first.csv', 1)]);
  await first;
  await flush();

  assert.equal(result.current.sessionId, 'sess-second');
  assert.deepEqual(
    result.current.files.map(file => file.snapshot?.file_id),
    ['sf_second'],
  );
});

test('resetSession prevents a pending addFiles call from launching an old-session upload', async () => {
  const capabilitiesGate = deferred<{ capabilities: UploadCapabilities; source: 'server' }>();
  const { api, result } = setup(
    makeFakeApi({
      fetchCapabilities: () => capabilitiesGate.promise,
    }),
  );

  const add = result.current.addFiles([makeFile('old.csv')], 'sess-old');
  result.current.resetSession();
  capabilitiesGate.resolve({ capabilities: CAPS, source: 'server' });
  await add;
  await flush();

  assert.equal(api.uploads.length, 0);
  assert.equal(result.current.sessionId, null);
  assert.equal(result.current.files.length, 0);
});

// ---------------------------------------------------------------------------
// Legacy example-file staging (Task12 gap)
// ---------------------------------------------------------------------------

const LEGACY_FILE = {
  name: 'sales.csv',
  size: 4096,
  media_type: 'text/csv',
  file_path: '/data/python_uploads/u1/sales.csv',
};

test('stageLegacyForSend atomically stages a server-preloaded example file and returns its send snapshot', async () => {
  const { result } = setup();
  const staged = result.current.stageLegacyForSend(LEGACY_FILE, 'sess-legacy');
  assert.equal(staged.ok, true);
  assert.equal(result.current.legacyFile?.file_path, '/data/python_uploads/u1/sales.csv');

  // The staged legacy file rides the legacy file_path protocol: no uploads.
  assert.ok(staged.ok);
  const snapshot = staged.snapshot;
  assert.deepEqual([...snapshot.fileIds], []);
  assert.equal(snapshot.legacyFile?.file_path, '/data/python_uploads/u1/sales.csv');
  assert.equal(Object.isFrozen(snapshot), true);

  result.current.clearTurn();
  assert.equal(result.current.legacyFile, null);
});

test('an example file is sent from the captured page render before React flushes the staged rail state', async () => {
  const { result } = setup(makeFakeApi(), { batchReducerDispatch: true });
  const capturedPageRender = result.current;

  const staged = capturedPageRender.stageLegacyForSend(LEGACY_FILE, 'sess-legacy');
  assert.ok(staged.ok);
  assert.equal(capturedPageRender.legacyFile, null, 'the captured page render must remain stale until React flushes');

  const snapshot = staged.snapshot;
  const extInfo = extInfoForSend({ skill_id: 'financial-report-analyzer' }, snapshot);

  assert.equal(extInfo.file_path, LEGACY_FILE.file_path);
  assert.equal(extInfo.file_ids, undefined);
  assert.deepEqual(
    snapshotsForSend(snapshot).map(file => file.name),
    [LEGACY_FILE.name],
  );
});

test('atomic legacy staging blocks conflicting examples and local uploads before React flushes', async () => {
  const { api, result } = setup(makeFakeApi(), { batchReducerDispatch: true });
  const capturedPageRender = result.current;

  assert.equal(capturedPageRender.stageLegacyForSend(LEGACY_FILE, 'sess-legacy').ok, true);

  const conflicting = capturedPageRender.stageLegacyForSend(
    {
      ...LEGACY_FILE,
      name: 'report.pdf',
      media_type: 'application/pdf',
      file_path: '/data/python_uploads/u1/report.pdf',
    },
    'sess-legacy',
  );
  assert.equal(conflicting.ok, false);
  assert.match(conflicting.error ?? '', /SESSION_FILES_LEGACY_CONFLICT/);

  await capturedPageRender.addFiles([makeFile('local.csv')], 'sess-legacy');
  assert.equal(api.uploads.length, 0, 'legacy file_path must block same-tick file_ids uploads');
});

test('legacy staging wins while addFiles is waiting for upload capabilities and prevents an orphan upload', async () => {
  const capabilities = deferred<{ capabilities: UploadCapabilities; source: 'server' }>();
  const api = makeFakeApi({
    fetchCapabilities: () => capabilities.promise,
  });
  const { result } = setup(api);

  const adding = result.current.addFiles([makeFile('local.csv')], 'sess-legacy');
  assert.equal(api.uploads.length, 0, 'the local upload must still be waiting for capabilities');

  const staged = result.current.stageLegacyForSend(LEGACY_FILE, 'sess-legacy');
  assert.equal(staged.ok, true);

  capabilities.resolve({ capabilities: CAPS, source: 'server' });
  await adding;

  assert.equal(api.uploads.length, 0, 'a reducer-rejected draft must never launch an invisible upload');
  assert.equal(result.current.files.length, 0);
  assert.equal(result.current.legacyFile?.file_path, LEGACY_FILE.file_path);
});

test('a dispatched local upload blocks legacy staging before React flushes the draft state', async () => {
  const { api, result } = setup(makeFakeApi(), { batchReducerDispatch: true });
  const capturedPageRender = result.current;

  await capturedPageRender.addFiles([makeFile('local.csv')], 'sess-1');
  assert.equal(api.uploads.length, 1);
  assert.equal(capturedPageRender.files.length, 0, 'the captured page render must still be stale');

  const staged = capturedPageRender.stageLegacyForSend(LEGACY_FILE, 'sess-1');
  assert.equal(staged.ok, false);
  assert.match(staged.error ?? '', /SESSION_FILES_MIXED_PROTOCOL/);

  api.uploads[0].gate.reject(new Error('test cleanup'));
  await flush();
});

test('legacy staging refuses to mix with local uploads in both directions', async () => {
  const { result } = setup();

  // Legacy staged first: local picks are refused (file_path vs file_ids).
  assert.equal(result.current.stageLegacyForSend(LEGACY_FILE, 'sess-1').ok, true);
  await result.current.addFiles([makeFile('local.csv')], 'sess-1');
  assert.equal(result.current.files.length, 0);

  result.current.clearLegacyFile();
  assert.equal(result.current.legacyFile, null);

  // Local drafts first: staging legacy is refused.
  await result.current.addFiles([makeFile('local.csv')], 'sess-1');
  const refused = result.current.stageLegacyForSend(LEGACY_FILE, 'sess-1');
  assert.equal(refused.ok, false);
  assert.match(refused.error ?? '', /SESSION_FILES_MIXED_PROTOCOL/);
  assert.equal(result.current.legacyFile, null);

  // Malformed legacy payloads are rejected before staging.
  result.current.clearTurn();
  assert.equal(
    result.current.stageLegacyForSend({ name: 'x.csv', size: 1, media_type: '', file_path: '' }, 'sess-1').ok,
    false,
  );
});
