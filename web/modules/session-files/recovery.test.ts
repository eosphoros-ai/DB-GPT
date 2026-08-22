import assert from 'node:assert/strict';
import test from 'node:test';

import type { SessionFileSnapshot } from './types';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as recovery from './recovery.ts';

const { displayOnlySnapshots, legacyFilePathDisplayName, parseShareViewPayload, scheduledTaskFiles } = recovery;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Real server minted ids always carry the `sf_` prefix; public payloads must
 * never expose one. */
const PRIVATE_FILE_ID = 'sf_9f8b7c6a5b4c3d2e1f2a3b4c5d6e7f';

const displayEntry = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
  display_key: 'file-1',
  name: 'sales_q1.csv',
  size: 18234,
  media_type: 'text/csv',
  kind: 'table',
  status: 'ready',
  ordinal: 0,
  ...overrides,
});

/** A v2 view payload in the share-scrubbed wire shape (display_key only). */
const shareV2Context = (inputFiles: unknown): string =>
  JSON.stringify({
    version: 2,
    type: 'react-agent',
    final_content: 'analysis answer',
    steps: [],
    input_files: inputFiles,
  });

// ---------------------------------------------------------------------------
// Public share v2 snapshots: names/status render, private ids never do
// ---------------------------------------------------------------------------

test('public v2 snapshots render names and statuses keyed by non-resolvable display keys', () => {
  const snapshots = displayOnlySnapshots([
    displayEntry(),
    displayEntry({
      display_key: 'file-2',
      name: 'notes.md',
      size: 100,
      media_type: 'text/markdown',
      kind: 'document',
      status: 'preview_failed',
      ordinal: 1,
    }),
  ]);

  assert.equal(snapshots.length, 2);
  assert.equal(snapshots[0].name, 'sales_q1.csv');
  assert.equal(snapshots[0].status, 'ready');
  assert.equal(snapshots[1].name, 'notes.md');
  assert.equal(snapshots[1].status, 'preview_failed');
  // Render identities are the non-resolvable display keys, never server ids.
  assert.deepEqual(
    snapshots.map(s => s.file_id),
    ['file-1', 'file-2'],
  );
});

test('public surface strips a leaked private file id instead of honoring it', () => {
  // A stored payload entry polluted with a usable server id (server-side bug
  // or maliciously crafted content) must never regain click-through power on
  // the public surface: the id is stripped down to a synthetic placeholder.
  const snapshots = displayOnlySnapshots([displayEntry({ file_id: PRIVATE_FILE_ID, display_key: undefined })]);

  assert.equal(snapshots.length, 1);
  assert.equal(snapshots[0].name, 'sales_q1.csv');
  assert.equal(snapshots[0].status, 'ready');
  assert.notEqual(snapshots[0].file_id, PRIVATE_FILE_ID);
  assert.ok(snapshots[0].file_id.length > 0);
});

test('no public snapshot identity can address the private preview/download endpoints', () => {
  const snapshots = displayOnlySnapshots([
    displayEntry(),
    displayEntry({ display_key: 'file-2', name: 'b.csv', ordinal: 1, file_id: PRIVATE_FILE_ID }),
    displayEntry({ display_key: 'file-3', name: 'c.csv', ordinal: 2, storage_uri: 'dbgpt-fs://secret' }),
  ]);

  assert.equal(snapshots.length, 3);
  const serialized = JSON.stringify(snapshots);
  assert.ok(!serialized.includes(PRIVATE_FILE_ID));
  assert.ok(!serialized.includes('dbgpt-fs://'));
  for (const snapshot of snapshots) {
    // Server-resolvable ids always start with `sf_`; none may survive.
    assert.ok(
      !snapshot.file_id.startsWith('sf_'),
      `public snapshot id must be non-resolvable, got ${snapshot.file_id}`,
    );
    // The view model carries metadata only — no url/path fields whatsoever.
    assert.deepEqual(Object.keys(snapshot).sort(), [
      'error_code',
      'file_id',
      'kind',
      'media_type',
      'name',
      'ordinal',
      'size',
      'status',
    ]);
  }
});

test('public snapshots stay frozen (mutation-proof)', () => {
  const snapshots = displayOnlySnapshots([displayEntry()]);
  assert.ok(Object.isFrozen(snapshots));
  assert.ok(Object.isFrozen(snapshots[0]));
  assert.throws(() => {
    (snapshots as unknown as SessionFileSnapshot[]).push(snapshots[0]);
  }, TypeError);
});

// ---------------------------------------------------------------------------
// Share replay payload gate: react history versions 1 and 2 only
// ---------------------------------------------------------------------------

test('share replay accepts react history payloads of versions 1 and 2', () => {
  const v1 = parseShareViewPayload(
    JSON.stringify({ version: 1, type: 'react-agent', final_content: 'legacy', steps: [] }),
  );
  const v2 = parseShareViewPayload(shareV2Context([displayEntry()]));

  assert.ok(v1);
  assert.equal(v1.version, 1);
  assert.ok(v2);
  assert.equal(v2.version, 2);
});

test('share replay rejects unsupported payloads without throwing', () => {
  for (const bad of [
    undefined,
    null,
    42,
    '',
    'not json',
    JSON.stringify('just a string'),
    JSON.stringify({ type: 'other', version: 2 }),
    JSON.stringify({ type: 'react-agent', version: 3 }),
    JSON.stringify({ type: 'react-agent' }),
  ]) {
    assert.equal(parseShareViewPayload(bad), null);
  }
});

test('share v1 payload yields no attachment snapshots (legacy display stays)', () => {
  const parsed = parseShareViewPayload(
    JSON.stringify({ version: 1, type: 'react-agent', final_content: 'legacy', steps: [] }),
  );
  assert.ok(parsed);
  assert.deepEqual(displayOnlySnapshots((parsed.payload as Record<string, unknown>).input_files), []);
});

test('share v2 payload resolves to display-only snapshots', () => {
  const parsed = parseShareViewPayload(shareV2Context([displayEntry()]));
  assert.ok(parsed);
  const snapshots = displayOnlySnapshots((parsed.payload as Record<string, unknown>).input_files);
  assert.equal(snapshots.length, 1);
  assert.equal(snapshots[0].name, 'sales_q1.csv');
  assert.equal(snapshots[0].file_id, 'file-1');
});

// ---------------------------------------------------------------------------
// Scheduled task v2 payload: frozen file list rendering
// ---------------------------------------------------------------------------

test('scheduled v2 payload renders the frozen file list in frozen order', () => {
  const files = scheduledTaskFiles({
    file_ids: ['sf_task_a', 'sf_task_b'],
    session_id: 'conv-1',
    input_files: [
      displayEntry(),
      displayEntry({ display_key: 'file-2', name: 'q2.xlsx', kind: 'table', status: 'ready', ordinal: 1 }),
    ],
  });

  assert.equal(files.length, 2);
  assert.deepEqual(
    files.map(f => f.name),
    ['sales_q1.csv', 'q2.xlsx'],
  );
  // The task-scoped file_ids used at replay are never render identities.
  for (const file of files) {
    assert.ok(!file.file_id.startsWith('sf_'));
  }
});

test('scheduled task files degrade safely for legacy or malformed payloads', () => {
  for (const extInfo of [undefined, null, {}, [], 42, { input_files: 'nope' }]) {
    assert.deepEqual(scheduledTaskFiles(extInfo), []);
  }
  // Legacy tasks carry file_path only: the frozen list stays empty.
  assert.deepEqual(scheduledTaskFiles({ file_path: '/data/python_uploads/alice/report.csv' }), []);
});

// ---------------------------------------------------------------------------
// Legacy task file_path: display-only basename, never a URL or full path
// ---------------------------------------------------------------------------

test('legacy task file_path renders display-only as a basename', () => {
  assert.equal(legacyFilePathDisplayName('/data/python_uploads/alice/report.csv'), 'report.csv');
  assert.equal(legacyFilePathDisplayName('python_uploads/alice/季度报表.csv'), '季度报表.csv');
  assert.equal(legacyFilePathDisplayName('report.csv'), 'report.csv');
});

test('legacy task file_path handles windows separators without leaking the path', () => {
  const label = legacyFilePathDisplayName('C:\\work\\python_uploads\\alice\\sales 2024.csv');
  assert.equal(label, 'sales 2024.csv');
  assert.ok(!String(label).includes('\\'));
  assert.ok(!String(label).includes('/'));
});

test('legacy task file_path yields null for malformed input', () => {
  for (const bad of [undefined, null, 42, {}, [], '', '   ']) {
    assert.equal(legacyFilePathDisplayName(bad), null);
  }
});
