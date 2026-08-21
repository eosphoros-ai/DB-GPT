import assert from 'node:assert/strict';
import test from 'node:test';

import type { SessionFileSnapshot, SessionFilesSendSnapshot } from './types';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as homeAdapter from './home-adapter.ts';

const { REACT_HISTORY_PAYLOAD_VERSION, extInfoForSend, parseViewContextFiles, snapshotsFromInputFiles } = homeAdapter;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const wireEntry = (overrides: Record<string, unknown> = {}): SessionFileSnapshot => ({
  file_id: 'sf_alpha',
  name: 'sales.csv',
  size: 4096,
  media_type: 'text/csv',
  kind: 'table',
  status: 'ready',
  ordinal: 0,
  error_code: null,
  ...overrides,
});

const buildSendSnapshot = (overrides: Partial<SessionFilesSendSnapshot> = {}): SessionFilesSendSnapshot => {
  const base: SessionFilesSendSnapshot = {
    sessionId: 'conv-1',
    fileIds: Object.freeze(['sf_alpha', 'sf_beta']),
    snapshotById: Object.freeze({
      sf_alpha: Object.freeze({
        file_id: 'sf_alpha',
        name: 'sales.csv',
        size: 4096,
        media_type: 'text/csv',
        kind: 'table',
        status: 'ready',
        ordinal: 0,
        error_code: null,
      } as SessionFileSnapshot),
      sf_beta: Object.freeze({
        file_id: 'sf_beta',
        name: 'report.pdf',
        size: 2048,
        media_type: 'application/pdf',
        kind: 'document',
        status: 'preview_failed',
        ordinal: 1,
        error_code: 'PREVIEW_TIMEOUT',
      } as SessionFileSnapshot),
    }),
  };
  return Object.freeze({ ...base, ...overrides });
};

// ---------------------------------------------------------------------------
// snapshotsFromInputFiles — v2 input_files -> frozen snapshots
// ---------------------------------------------------------------------------

test('snapshotsFromInputFiles maps v2 wire entries preserving fields and order', () => {
  const snapshots = snapshotsFromInputFiles([
    wireEntry(),
    wireEntry({
      file_id: 'sf_beta',
      name: 'report.pdf',
      size: 2048,
      media_type: 'application/pdf',
      kind: 'document',
      status: 'preview_failed',
      ordinal: 1,
      error_code: 'PREVIEW_TIMEOUT',
    }),
  ]);
  assert.equal(snapshots.length, 2);
  assert.deepEqual(
    snapshots.map(s => s.file_id),
    ['sf_alpha', 'sf_beta'],
  );
  assert.equal(snapshots[0].name, 'sales.csv');
  assert.equal(snapshots[0].size, 4096);
  assert.equal(snapshots[0].media_type, 'text/csv');
  assert.equal(snapshots[0].kind, 'table');
  assert.equal(snapshots[0].status, 'ready');
  assert.equal(snapshots[0].ordinal, 0);
  assert.equal(snapshots[1].status, 'preview_failed');
  assert.equal(snapshots[1].error_code, 'PREVIEW_TIMEOUT');
});

test('snapshotsFromInputFiles keeps share-scrubbed entries display-only (display_key, no file_id)', () => {
  const snapshots = snapshotsFromInputFiles([
    {
      display_key: 'file-1',
      name: 'sales.csv',
      size: 4096,
      media_type: 'text/csv',
      kind: 'table',
      status: 'ready',
      ordinal: 0,
    },
  ]);
  assert.equal(snapshots.length, 1);
  // The adapter must never invent a usable server id: the display key is
  // non-resolvable by design and becomes the render identity.
  assert.equal(snapshots[0].file_id, 'file-1');
  assert.equal(snapshots[0].name, 'sales.csv');
});

test('snapshotsFromInputFiles degrades invalid or missing input safely', () => {
  // Non-array inputs degrade to an empty list.
  for (const bad of [undefined, null, {}, 'nope', 42]) {
    assert.deepEqual(snapshotsFromInputFiles(bad), []);
  }
  const snapshots = snapshotsFromInputFiles([
    null,
    'oops',
    42,
    {
      file_id: 'sf_valid',
      name: 'ok.csv',
      size: 10,
      media_type: 'text/csv',
      kind: 'table',
      status: 'ready',
      ordinal: 0,
    },
    { name: '' }, // blank name cannot render: skipped
    { file_id: 'sf_no_name' }, // missing name cannot render: skipped
    {
      // Malformed fields degrade deterministically instead of throwing.
      file_id: 'sf_weird',
      name: 'weird.bin',
      size: 'not-a-number',
      media_type: 7,
      kind: null,
      status: 'evil_status',
      ordinal: 'x',
    },
  ]);
  assert.equal(snapshots.length, 2);
  assert.equal(snapshots[0].file_id, 'sf_valid');
  const weird = snapshots[1];
  assert.equal(weird.file_id, 'sf_weird');
  assert.equal(weird.size, 0);
  assert.equal(weird.media_type, '');
  assert.equal(weird.kind, '');
  assert.equal(weird.status, 'ready');
  assert.equal(typeof weird.ordinal, 'number');
});

test('snapshotsFromInputFiles synthesizes a non-resolvable id when both file_id and display_key are missing', () => {
  const snapshots = snapshotsFromInputFiles([
    { name: 'a.csv', size: 1, ordinal: 0 },
    { name: 'b.csv', size: 2, ordinal: 1 },
  ]);
  assert.equal(snapshots.length, 2);
  assert.ok(snapshots[0].file_id);
  assert.ok(snapshots[1].file_id);
  assert.notEqual(snapshots[0].file_id, snapshots[1].file_id);
  // Synthetic ids must never look like a server-side session file id.
  assert.ok(!snapshots[0].file_id.startsWith('sf_'));
});

// ---------------------------------------------------------------------------
// snapshotsFromInputFiles — store immutability
// ---------------------------------------------------------------------------

test('snapshotsFromInputFiles returns a deeply frozen store (mutation-proof)', () => {
  const snapshots = snapshotsFromInputFiles([wireEntry()]);
  assert.ok(Object.isFrozen(snapshots));
  assert.ok(snapshots.every(snapshot => Object.isFrozen(snapshot)));
  // Module content runs in strict mode: mutation attempts throw TypeError.
  assert.throws(() => {
    (snapshots as unknown as SessionFileSnapshot[]).push(wireEntry());
  }, TypeError);
  assert.throws(() => {
    snapshots[0].name = 'mutated.csv';
  }, TypeError);
  assert.equal(snapshots[0].name, 'sales.csv');
});

// ---------------------------------------------------------------------------
// parseViewContextFiles — v2 parse vs v1 legacy bridge
// ---------------------------------------------------------------------------

test('parseViewContextFiles parses a v2 history payload into frozen snapshots', () => {
  const result = parseViewContextFiles(
    JSON.stringify({
      version: REACT_HISTORY_PAYLOAD_VERSION,
      type: 'react-agent',
      final_content: 'done',
      steps: [],
      input_files: [wireEntry()],
    }),
  );
  assert.ok(result);
  assert.equal(result.version, 2);
  assert.equal(result.inputFiles.length, 1);
  assert.equal(result.inputFiles[0].file_id, 'sf_alpha');
  assert.ok(Object.isFrozen(result.inputFiles));
});

test('parseViewContextFiles keeps v1 payloads snapshot-free (pre-attachment protocol)', () => {
  const result = parseViewContextFiles(
    JSON.stringify({ version: 1, type: 'react-agent', final_content: 'done', steps: [] }),
  );
  assert.ok(result);
  assert.equal(result.version, 1);
  // v1 never yields snapshots: it predates file attachments entirely.
  assert.deepEqual(result.inputFiles, []);
});

test('parseViewContextFiles returns null for unusable contexts', () => {
  for (const bad of [
    undefined,
    null,
    42,
    '',
    'not json',
    JSON.stringify('just a string'),
    JSON.stringify({ type: 'other', version: 2 }),
    JSON.stringify({ type: 'react-agent', version: 3 }),
  ]) {
    assert.equal(parseViewContextFiles(bad), null);
  }
  // A v2 payload without input_files still parses, with an empty snapshot list.
  const result = parseViewContextFiles(
    JSON.stringify({ version: 2, type: 'react-agent', final_content: 'x', steps: [] }),
  );
  assert.ok(result);
  assert.deepEqual(result.inputFiles, []);
});

// ---------------------------------------------------------------------------
// extInfoForSend — zero-file regression + file_ids wiring
// ---------------------------------------------------------------------------

test('extInfoForSend reproduces the legacy payload byte-for-byte when no files are attached', () => {
  // Legacy file_path flow (example cards / old uploads) stays untouched.
  const legacyFile = { file_path: '/data/python_uploads/u1/sales.csv', skill_id: 'csv-data-analysis' };
  assert.equal(JSON.stringify(extInfoForSend(legacyFile, null)), JSON.stringify(legacyFile));
  assert.deepEqual(extInfoForSend(legacyFile, null), legacyFile);
  // Pure-text flow: empty ext_info stays empty (no file_ids, no session_id).
  assert.deepEqual(extInfoForSend({}, null), {});
  assert.deepEqual(extInfoForSend(null, null), {});
  assert.deepEqual(extInfoForSend(undefined, undefined), {});
  // An empty send snapshot must also stay regression-identical to legacy.
  const empty = buildSendSnapshot({ fileIds: Object.freeze([]), snapshotById: Object.freeze({}) });
  assert.equal(JSON.stringify(extInfoForSend(legacyFile, empty)), JSON.stringify(legacyFile));
});

test('extInfoForSend wires file_ids + session_id without mutating the base payload', () => {
  const base = Object.freeze({ skill_id: 'csv-data-analysis' });
  const snapshot = buildSendSnapshot();
  const extInfo = extInfoForSend(base, snapshot);
  assert.deepEqual(extInfo.skill_id, 'csv-data-analysis');
  assert.deepEqual(extInfo.file_ids, ['sf_alpha', 'sf_beta']);
  assert.equal(extInfo.session_id, 'conv-1');
  // Frozen base is never mutated by the builder.
  assert.deepEqual(base, { skill_id: 'csv-data-analysis' });
  // file_ids is an owned copy, not the frozen reference.
  assert.notEqual(extInfo.file_ids, snapshot.fileIds);
});

test('extInfoForSend embeds display-safe task file snapshots (no usable ids, no paths)', () => {
  const extInfo = extInfoForSend({}, buildSendSnapshot());
  const inputFiles = extInfo.input_files as Array<Record<string, unknown>>;
  assert.equal(inputFiles.length, 2);
  assert.deepEqual(
    inputFiles.map(f => f.display_key),
    ['file-1', 'file-2'],
  );
  for (const file of inputFiles) {
    // Display metadata only: the frozen-copy list must be re-parseable by
    // snapshotsFromInputFiles and must never carry a resolvable file_id.
    assert.ok(!('file_id' in file));
    assert.ok(!('file_path' in file));
  }
  assert.equal(inputFiles[0].name, 'sales.csv');
  assert.equal(inputFiles[0].size, 4096);
  assert.equal(inputFiles[1].status, 'preview_failed');
  // Round-trip: the same adapter parses the embedded snapshots back.
  const roundTrip = snapshotsFromInputFiles(inputFiles);
  assert.equal(roundTrip.length, 2);
  assert.equal(roundTrip[0].file_id, 'file-1');
});

test('extInfoForSend keeps legacy file_path when only the legacy flow is used', () => {
  // Regression guard: file_path and file_ids must never coexist. The legacy
  // path passes no snapshot, so file_path survives untouched.
  const legacy = { file_path: '/data/python_uploads/u1/sales.csv' };
  const extInfo = extInfoForSend(legacy, null);
  assert.equal(extInfo.file_path, '/data/python_uploads/u1/sales.csv');
  assert.ok(!('file_ids' in extInfo));
});

// ---------------------------------------------------------------------------
// Legacy example-file protocol (Task12 gap): file_path stays the sole wire key
// ---------------------------------------------------------------------------

test('snapshotFromLegacyFile renders the removed FileAttachment as a display-only snapshot', () => {
  const snapshot = homeAdapter.snapshotFromLegacyFile({ name: 'sales.csv', size: 4096, type: 'text/csv' });
  // Same non-resolvable `legacy:` identity as the deleted one-item bridge;
  // the server-side file_path must never leak into a render snapshot.
  assert.equal(snapshot.file_id, 'legacy:sales.csv');
  assert.ok(!snapshot.file_id.startsWith('sf_'));
  assert.equal(snapshot.name, 'sales.csv');
  assert.equal(snapshot.size, 4096);
  assert.equal(snapshot.media_type, 'text/csv');
  assert.equal(snapshot.status, 'ready');
  assert.equal(snapshot.ordinal, 0);
  assert.ok(!('file_path' in snapshot));
  assert.ok(Object.isFrozen(snapshot));
});

test('LegacyAttachedFile remains the minimal public back-compat attachment shape', () => {
  const attachment: homeAdapter.LegacyAttachedFile = {
    name: 'report.pdf',
    size: 2048,
    type: 'application/pdf',
  };
  const snapshot = homeAdapter.snapshotFromLegacyFile(attachment);
  assert.equal(snapshot.name, 'report.pdf');
  assert.equal(snapshot.media_type, 'application/pdf');
});

test('extInfoForSend sends a staged legacy file via file_path alone (no session-file keys)', () => {
  const snapshot = homeAdapter.snapshotWithLegacyFile(
    buildSendSnapshot({ fileIds: Object.freeze([]), snapshotById: Object.freeze({}) }),
    { name: 'sales.csv', size: 4096, media_type: 'text/csv', file_path: '/data/python_uploads/u1/sales.csv' },
  );
  assert.ok(snapshot.legacyFile);
  assert.ok(Object.isFrozen(snapshot.legacyFile));
  const extInfo = extInfoForSend({}, snapshot);
  assert.equal(extInfo.file_path, '/data/python_uploads/u1/sales.csv');
  // The legacy protocol never mixes with the session-file (file_ids) protocol.
  assert.ok(!('file_ids' in extInfo));
  assert.ok(!('session_id' in extInfo));
  assert.ok(!('input_files' in extInfo));
});

test('extInfoForSend refuses to mix a staged legacy file with session file_ids', () => {
  const mixed = homeAdapter.snapshotWithLegacyFile(buildSendSnapshot(), {
    name: 'sales.csv',
    size: 4096,
    media_type: 'text/csv',
    file_path: '/data/python_uploads/u1/sales.csv',
  });
  assert.throws(() => extInfoForSend({}, mixed), /SESSION_FILES_MIXED_PROTOCOL/);
});

test('snapshotsForSend renders a staged legacy file as the message attachment', () => {
  const snapshot = homeAdapter.snapshotWithLegacyFile(
    buildSendSnapshot({ fileIds: Object.freeze([]), snapshotById: Object.freeze({}) }),
    { name: 'sales.csv', size: 4096, media_type: 'text/csv', file_path: '/data/python_uploads/u1/sales.csv' },
  );
  const attachments = homeAdapter.snapshotsForSend(snapshot);
  assert.equal(attachments.length, 1);
  assert.equal(attachments[0].name, 'sales.csv');
  assert.equal(attachments[0].file_id, 'legacy:sales.csv');
  assert.ok(Object.isFrozen(attachments));
});

test('snapshotsForSend keeps session uploads in send order', () => {
  const attachments = homeAdapter.snapshotsForSend(buildSendSnapshot());
  assert.deepEqual(
    attachments.map(s => s.file_id),
    ['sf_alpha', 'sf_beta'],
  );
});
