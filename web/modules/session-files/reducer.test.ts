import assert from 'node:assert/strict';
import test from 'node:test';

import type { SessionFilesAction, SessionFilesState } from './reducer';
import type { SessionFileSnapshot, UploadCapabilities } from './types';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as reducerModule from './reducer.ts';

const { buildSendSnapshot, hasHardFailures, initialSessionFilesState, planAddDrafts, sessionFilesReducer } =
  reducerModule;

const CAPS: UploadCapabilities = {
  max_files_per_upload: 3,
  max_file_bytes: 100,
  max_upload_bytes: 250,
  max_owner_bytes: 1024,
  upload_request_timeout_seconds: 180,
  upload_concurrency: 3,
  supported_extensions: ['.csv'],
};

function makeFile(name: string, size: number, lastModified = 1): File {
  return new File([new Uint8Array(size)], name, { lastModified });
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

let idCounter = 0;
const nextId = () => `c${idCounter++}`;

function withCaps(state: SessionFilesState): SessionFilesState {
  return sessionFilesReducer(state, {
    type: 'capabilities',
    capabilities: CAPS,
    source: 'server',
  });
}

function apply(state: SessionFilesState, ...actions: SessionFilesAction[]): SessionFilesState {
  return actions.reduce(sessionFilesReducer, state);
}

function addFiles(state: SessionFilesState, ...files: File[]): SessionFilesState {
  return sessionFilesReducer(state, {
    type: 'add',
    inputs: files.map(file => ({ clientId: nextId(), file })),
  });
}

test('add accepts a batch in order with orthogonal initial states', () => {
  const before = idCounter;
  const state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10), makeFile('b.csv', 20));

  assert.equal(state.files.length, 2);
  assert.deepEqual(
    state.files.map(f => f.clientId),
    [`c${before}`, `c${before + 1}`],
  );
  assert.deepEqual(
    state.files.map(f => f.identity),
    [
      { name: 'a.csv', size: 10, lastModified: 1 },
      { name: 'b.csv', size: 20, lastModified: 1 },
    ],
  );
  for (const draft of state.files) {
    assert.equal(draft.validation.status, 'ok');
    assert.equal(draft.validation.error, null);
    assert.equal(draft.upload.status, 'queued');
    assert.equal(draft.upload.progress, 0);
    assert.equal(draft.preview.status, 'idle');
    assert.equal(draft.snapshot, null);
  }
});

test('rejects duplicate identity (name,size,lastModified) across separate adds', () => {
  const first = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10, 7));
  // Same identity, different File instance.
  const second = addFiles(first, makeFile('a.csv', 10, 7), makeFile('b.csv', 10, 7));

  assert.equal(second.files.length, 2);
  assert.equal(second.files[0].identity.name, 'a.csv');
  assert.equal(second.files[1].identity.name, 'b.csv');
});

test('rejects duplicate identity within a single batch', () => {
  const state = addFiles(
    withCaps(initialSessionFilesState()),
    makeFile('a.csv', 10, 7),
    makeFile('a.csv', 10, 7),
    makeFile('b.csv', 10, 7),
  );

  assert.equal(state.files.length, 2);
  assert.deepEqual(
    state.files.map(f => f.identity.name),
    ['a.csv', 'b.csv'],
  );
});

test('marks files over max_files_per_upload as invalid without blocking valid siblings', () => {
  const state = addFiles(
    withCaps(initialSessionFilesState()),
    makeFile('a.csv', 10),
    makeFile('b.csv', 10),
    makeFile('c.csv', 10),
    makeFile('d.csv', 10),
  );

  assert.equal(state.files.length, 4);
  assert.equal(state.files[3].validation.status, 'invalid');
  assert.equal(state.files[3].validation.error, 'TOO_MANY_FILES');
  assert.equal(state.files[3].upload.status, 'blocked');
  assert.equal(state.files[2].validation.status, 'ok');
  assert.equal(state.files[2].upload.status, 'queued');
});

test('marks oversized file invalid (FILE_TOO_LARGE) and excludes it from byte quota', () => {
  const state = addFiles(withCaps(initialSessionFilesState()), makeFile('big.csv', 101), makeFile('ok.csv', 90));

  assert.equal(state.files[0].validation.status, 'invalid');
  assert.equal(state.files[0].validation.error, 'FILE_TOO_LARGE');
  assert.equal(state.files[0].upload.status, 'blocked');
  // Second file still fits the aggregate budget because the oversized one
  // does not consume quota.
  assert.equal(state.files[1].validation.status, 'ok');
});

test('marks files invalid when the aggregate exceeds max_upload_bytes', () => {
  const state = addFiles(
    withCaps(initialSessionFilesState()),
    makeFile('a.csv', 100),
    makeFile('b.csv', 100),
    makeFile('c.csv', 60),
  );

  assert.equal(state.files[0].validation.status, 'ok');
  assert.equal(state.files[1].validation.status, 'ok');
  assert.equal(state.files[2].validation.status, 'invalid');
  assert.equal(state.files[2].validation.error, 'REQUEST_TOO_LARGE');
});

test('upload lifecycle: queued -> uploading -> progress -> done with snapshot', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10));
  const id = state.files[0].clientId;

  state = apply(state, { type: 'upload_start', clientId: id, attempt: 1 });
  assert.equal(state.files[0].upload.status, 'uploading');
  assert.equal(state.files[0].upload.attempt, 1);

  state = apply(state, { type: 'upload_progress', clientId: id, attempt: 1, progress: 0.5 });
  assert.equal(state.files[0].upload.progress, 0.5);

  const snapshot = snapOf('sf_a', 'a.csv', 1);
  state = apply(state, { type: 'upload_done', clientId: id, attempt: 1, snapshot });
  assert.equal(state.files[0].upload.status, 'done');
  assert.equal(state.files[0].upload.progress, 1);
  assert.equal(state.files[0].snapshot, snapshot);
  // Upload completion must not disturb the orthogonal preview state.
  assert.equal(state.files[0].preview.status, 'idle');
});

test('stale completion is ignored after cancel (attempt guard)', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10));
  const id = state.files[0].clientId;

  state = apply(
    state,
    { type: 'upload_start', clientId: id, attempt: 1 },
    { type: 'upload_cancelled', clientId: id, attempt: 1 },
  );
  assert.equal(state.files[0].upload.status, 'cancelled');

  // Late failure from the aborted request must not resurrect the file.
  state = apply(state, {
    type: 'upload_failed',
    clientId: id,
    attempt: 1,
    error: 'network',
  });
  assert.equal(state.files[0].upload.status, 'cancelled');

  // A done from the stale attempt is ignored as well.
  state = apply(state, {
    type: 'upload_done',
    clientId: id,
    attempt: 1,
    snapshot: snapOf('sf_a', 'a.csv', 1),
  });
  assert.equal(state.files[0].upload.status, 'cancelled');
  assert.equal(state.files[0].snapshot, null);
});

test('remove discards the draft and late completions are a no-op', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10), makeFile('b.csv', 10));
  const [a, b] = state.files.map(f => f.clientId);

  state = apply(state, { type: 'upload_start', clientId: a, attempt: 1 });
  state = apply(state, { type: 'remove', clientId: a });
  assert.deepEqual(
    state.files.map(f => f.clientId),
    [b],
  );

  // Stale signal for the removed file: nothing happens, sibling untouched.
  state = apply(state, {
    type: 'upload_done',
    clientId: a,
    attempt: 1,
    snapshot: snapOf('sf_a', 'a.csv', 1),
  });
  assert.equal(state.files.length, 1);
  assert.equal(state.files[0].clientId, b);
  assert.equal(state.files[0].upload.status, 'queued');
});

test('retry keeps clientId and re-enables a fresh upload attempt', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10));
  const id = state.files[0].clientId;

  state = apply(
    state,
    { type: 'upload_start', clientId: id, attempt: 1 },
    { type: 'upload_failed', clientId: id, attempt: 1, error: 'boom' },
  );
  assert.equal(state.files[0].upload.status, 'failed');
  assert.equal(state.files[0].upload.error, 'boom');

  state = apply(state, { type: 'retry', clientId: id });
  assert.equal(state.files[0].clientId, id);
  assert.equal(state.files[0].upload.status, 'queued');
  assert.equal(state.files[0].upload.error, null);
  assert.equal(state.files[0].upload.progress, 0);

  state = apply(state, { type: 'upload_start', clientId: id, attempt: 2 });
  assert.equal(state.files[0].upload.status, 'uploading');
  assert.equal(state.files[0].upload.attempt, 2);
});

test('failed upload is a hard gate; preview_failed is only a soft warning', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10), makeFile('b.csv', 10));
  const [a, b] = state.files.map(f => f.clientId);

  state = apply(
    state,
    { type: 'upload_start', clientId: a, attempt: 1 },
    { type: 'upload_done', clientId: a, attempt: 1, snapshot: snapOf('sf_a', 'a.csv', 1) },
    { type: 'preview_start', clientId: a },
    { type: 'preview_failed', clientId: a, error: 'PREVIEW_NOT_READY' },
    { type: 'upload_start', clientId: b, attempt: 1 },
    { type: 'upload_failed', clientId: b, attempt: 1, error: 'boom' },
  );

  assert.equal(state.files[0].preview.status, 'preview_failed');
  assert.equal(state.files[1].upload.status, 'failed');
  assert.equal(hasHardFailures(state), true);
  assert.throws(() => buildSendSnapshot(state, 'sess-1'), /SESSION_FILES_HARD_FAILURE/);

  // Resolve the hard failure -> preview_failed alone must not block sending.
  state = apply(state, { type: 'remove', clientId: b });
  assert.equal(hasHardFailures(state), false);
  const snapshot = buildSendSnapshot(state, 'sess-1');
  assert.deepEqual(snapshot.fileIds, ['sf_a']);
});

test('send snapshot is frozen and ordered by insertion, not completion order', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10), makeFile('b.csv', 10));
  const [a, b] = state.files.map(f => f.clientId);

  // Complete in reverse order; insertion order must still win.
  state = apply(
    state,
    { type: 'upload_start', clientId: b, attempt: 1 },
    { type: 'upload_done', clientId: b, attempt: 1, snapshot: snapOf('sf_b', 'b.csv', 2) },
    { type: 'upload_start', clientId: a, attempt: 1 },
    { type: 'upload_done', clientId: a, attempt: 1, snapshot: snapOf('sf_a', 'a.csv', 1) },
  );

  const prepared = buildSendSnapshot(state, 'sess-9');
  assert.equal(prepared.sessionId, 'sess-9');
  assert.deepEqual([...prepared.fileIds], ['sf_a', 'sf_b']);
  assert.deepEqual(Object.keys(prepared.snapshotById), ['sf_a', 'sf_b']);

  assert.equal(Object.isFrozen(prepared), true);
  assert.equal(Object.isFrozen(prepared.fileIds), true);
  assert.equal(Object.isFrozen(prepared.snapshotById), true);
  assert.equal(Object.isFrozen(prepared.snapshotById['sf_a']), true);

  const before = JSON.stringify(prepared);
  try {
    (prepared.fileIds as string[]).push('evil');
  } catch {
    /* frozen arrays throw in strict mode */
  }
  try {
    (prepared.snapshotById as Record<string, unknown>)['evil'] = {};
  } catch {
    /* frozen record throws in strict mode */
  }
  assert.equal(JSON.stringify(prepared), before);
});

test('rehydrate rebuilds drafts from the server list ordered by ordinal', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('local.csv', 10));
  state = apply(state, {
    type: 'rehydrate',
    sessionId: 'sess-2',
    snapshots: [snapOf('sf_2', 'two.csv', 2), snapOf('sf_1', 'one.csv', 1)],
  });

  assert.equal(state.sessionId, 'sess-2');
  assert.deepEqual(
    state.files.map(f => [f.snapshot?.file_id, f.upload.status, f.validation.status]),
    [
      ['sf_1', 'done', 'ok'],
      ['sf_2', 'done', 'ok'],
    ],
  );
  // Rehydrated drafts carry no local File bytes but stay sendable.
  assert.equal(state.files[0].file, null);
  assert.equal(state.files[0].preview.status, 'ready');
  assert.deepEqual(buildSendSnapshot(state, 'sess-2').fileIds, ['sf_1', 'sf_2']);
  // Server snapshot failure state is preserved as a hard gate.
  state = apply(state, {
    type: 'rehydrate',
    sessionId: 'sess-3',
    snapshots: [{ ...snapOf('sf_x', 'x.csv', 1), status: 'failed', error_code: 'FILE_TOO_LARGE' }],
  });
  assert.equal(state.files[0].upload.status, 'failed');
  assert.equal(hasHardFailures(state), true);
});

test('clear_turn empties drafts but keeps session and capabilities', () => {
  let state = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10));
  state = apply(state, { type: 'bind_session', sessionId: 'sess-1' });
  state = apply(state, { type: 'clear_turn' });

  assert.equal(state.files.length, 0);
  assert.equal(state.sessionId, 'sess-1');
  assert.equal(state.capabilities, CAPS);
});

test('planAddDrafts is a pure preview consistent with the reducer add', () => {
  const existing: SessionFilesState['files'] = [];
  const files = [makeFile('a.csv', 10), makeFile('huge.csv', 500)];
  let i = 0;
  const drafts = planAddDrafts({
    existing,
    files,
    capabilities: CAPS,
    createClientId: () => `p${i++}`,
  });

  assert.deepEqual(
    drafts.map(d => [d.clientId, d.validation.status, d.upload.status]),
    [
      ['p0', 'ok', 'queued'],
      ['p1', 'invalid', 'blocked'],
    ],
  );
});

// ---------------------------------------------------------------------------
// Legacy example-file staging (Task12 gap): mutually exclusive with drafts
// ---------------------------------------------------------------------------

const LEGACY_FILE = {
  name: 'sales.csv',
  size: 4096,
  media_type: 'text/csv',
  file_path: '/data/python_uploads/u1/sales.csv',
};

test('set_legacy stages a server-preloaded file and local picks are refused while staged', () => {
  const state = apply(initialSessionFilesState(), { type: 'set_legacy', file: LEGACY_FILE });
  assert.equal(state.legacyFile?.file_path, '/data/python_uploads/u1/sales.csv');
  // Adding a local draft while a legacy file is staged must be a no-op:
  // legacy file_path and session file_ids are mutually exclusive protocols.
  const blocked = addFiles(withCaps(state), makeFile('local.csv', 10));
  assert.equal(blocked.files.length, 0);
  assert.equal(blocked.legacyFile?.file_path, LEGACY_FILE.file_path);
});

test('set_legacy is refused while drafts exist and re-staging is idempotent', () => {
  const withDraft = addFiles(withCaps(initialSessionFilesState()), makeFile('a.csv', 10));
  const refused = apply(withDraft, { type: 'set_legacy', file: LEGACY_FILE });
  assert.equal(refused.legacyFile, null);
  assert.equal(refused.files.length, 1);

  const staged = apply(initialSessionFilesState(), { type: 'set_legacy', file: LEGACY_FILE });
  const reStaged = apply(staged, { type: 'set_legacy', file: { ...LEGACY_FILE, file_path: '/other.csv' } });
  assert.equal(reStaged.legacyFile?.file_path, LEGACY_FILE.file_path);
});

test('buildSendSnapshot carries a staged legacy file for the legacy file_path send', () => {
  const staged = apply(initialSessionFilesState(), { type: 'set_legacy', file: LEGACY_FILE });
  const snapshot = buildSendSnapshot(staged, 'sess-legacy');
  assert.deepEqual(snapshot.fileIds, []);
  assert.equal(snapshot.legacyFile?.file_path, '/data/python_uploads/u1/sales.csv');
  assert.ok(Object.isFrozen(snapshot.legacyFile));
});

test('clear_turn and clear_legacy unstage the legacy example file', () => {
  const staged = apply(initialSessionFilesState(), { type: 'set_legacy', file: LEGACY_FILE });
  assert.equal(apply(staged, { type: 'clear_turn' }).legacyFile, null);
  const restaged = apply(initialSessionFilesState(), { type: 'set_legacy', file: LEGACY_FILE });
  assert.equal(apply(restaged, { type: 'clear_legacy' }).legacyFile, null);
});
