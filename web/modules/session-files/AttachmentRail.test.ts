import assert from 'node:assert/strict';
import test from 'node:test';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as viewModel from './attachment-view-model.ts';
import type { DraftFile, SessionFileSnapshot } from './types';

const {
  PREVIEW_STATUS_LABELS,
  RAIL_MAX_VISIBLE,
  REDUCED_MOTION_CLASS,
  UPLOAD_STATUS_LABELS,
  aggregateUploadProgress,
  canPreviewItem,
  canPreviewSnapshot,
  canRetry,
  collapseRail,
  fileIconKey,
  formatBytes,
  isHardFailure,
  motionClassName,
  normalizeDocumentPreview,
  normalizeTablePreview,
  normalizeTextPreview,
  progressPercent,
  removeAriaLabel,
  resolvePreviewMode,
  resolvePreviewOverlay,
  retryAriaLabel,
  toLegacyRailItem,
  toRailItems,
} = viewModel;

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

function makeDraft(overrides: {
  clientId?: string;
  name?: string;
  size?: number;
  fileType?: string;
  validation?: DraftFile['validation'];
  upload?: Partial<DraftFile['upload']>;
  preview?: Partial<DraftFile['preview']>;
  snapshot?: SessionFileSnapshot | null;
}): DraftFile {
  return {
    clientId: overrides.clientId ?? 'client-1',
    file: null,
    identity: { name: overrides.name ?? 'report.csv', size: overrides.size ?? 2048, lastModified: 1700000000000 },
    validation: overrides.validation ?? { status: 'ok', error: null },
    upload: { status: 'queued', progress: 0, attempt: 0, error: null, ...(overrides.upload ?? {}) },
    preview: { status: 'idle', error: null, ...(overrides.preview ?? {}) },
    snapshot: overrides.snapshot ?? null,
  };
}

function makeSnapshot(overrides: Partial<SessionFileSnapshot>): SessionFileSnapshot {
  return {
    file_id: 'file-1',
    name: 'report.csv',
    size: 2048,
    media_type: 'text/csv',
    kind: 'table',
    status: 'ready',
    ordinal: 0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Status labels (upload and preview are independent)
// ---------------------------------------------------------------------------

test('maps every upload phase to a user-facing label', () => {
  assert.deepEqual(
    { ...UPLOAD_STATUS_LABELS },
    {
      queued: 'Queued',
      uploading: 'Uploading',
      done: 'Ready',
      failed: 'Upload failed',
      cancelled: 'Cancelled',
      blocked: 'Blocked',
    },
  );
});

test('maps every preview phase to a label, keeping preview_failed a soft warning', () => {
  assert.deepEqual(
    { ...PREVIEW_STATUS_LABELS },
    {
      idle: '',
      loading: 'Loading preview',
      ready: 'Preview ready',
      preview_failed: 'Preview unavailable',
    },
  );
  assert.notEqual(PREVIEW_STATUS_LABELS.preview_failed, UPLOAD_STATUS_LABELS.failed);
});

// ---------------------------------------------------------------------------
// Hard failure / retry classification
// ---------------------------------------------------------------------------

test('flags failed and validation-blocked items as hard failures', () => {
  const failed = toRailItems([makeDraft({ upload: { status: 'failed', error: 'boom' } })])[0];
  const blocked = toRailItems([
    makeDraft({ validation: { status: 'invalid', error: 'bad type' }, upload: { status: 'blocked' } }),
  ])[0];
  const ready = toRailItems([makeDraft({ upload: { status: 'done' } })])[0];
  const uploading = toRailItems([makeDraft({ upload: { status: 'uploading', progress: 0.4 } })])[0];

  assert.equal(isHardFailure(failed), true);
  assert.equal(isHardFailure(blocked), true);
  assert.equal(isHardFailure(ready), false);
  assert.equal(isHardFailure(uploading), false);
});

test('allows retry only for failed uploads, never for validation-blocked items', () => {
  const failed = toRailItems([makeDraft({ upload: { status: 'failed' } })])[0];
  const blocked = toRailItems([
    makeDraft({ validation: { status: 'invalid', error: 'bad type' }, upload: { status: 'blocked' } }),
  ])[0];
  const uploading = toRailItems([makeDraft({ upload: { status: 'uploading' } })])[0];

  assert.equal(canRetry(failed), true);
  assert.equal(canRetry(blocked), false);
  assert.equal(canRetry(uploading), false);
});

// ---------------------------------------------------------------------------
// Aggregate progress (deterministic aria-valuenow source)
// ---------------------------------------------------------------------------

test('aggregates progress across queued, uploading and done items', () => {
  const items = toRailItems([
    makeDraft({ clientId: 'a', upload: { status: 'uploading', progress: 0.5 } }),
    makeDraft({ clientId: 'b', upload: { status: 'done', progress: 1 } }),
    makeDraft({ clientId: 'c', upload: { status: 'queued', progress: 0 } }),
  ]);
  assert.ok(Math.abs(aggregateUploadProgress(items) - 0.5) < 1e-9);
  assert.equal(progressPercent(aggregateUploadProgress(items)), 50);
});

test('excludes failed/cancelled/blocked items and returns 0 when nothing is in flight', () => {
  const items = toRailItems([
    makeDraft({ clientId: 'a', upload: { status: 'uploading', progress: 0.5 } }),
    makeDraft({ clientId: 'b', upload: { status: 'failed', progress: 0.9 } }),
    makeDraft({ clientId: 'c', upload: { status: 'cancelled', progress: 0.3 } }),
  ]);
  assert.equal(aggregateUploadProgress(items), 0.5);
  assert.equal(progressPercent(aggregateUploadProgress(items)), 50);

  const failedOnly = toRailItems([makeDraft({ upload: { status: 'failed' } })]);
  assert.equal(aggregateUploadProgress(failedOnly), 0);
  assert.equal(aggregateUploadProgress([]), 0);
});

test('clamps out-of-range progress ratios', () => {
  const items = toRailItems([
    makeDraft({ clientId: 'a', upload: { status: 'uploading', progress: 1.4 } }),
    makeDraft({ clientId: 'b', upload: { status: 'uploading', progress: -1 } }),
  ]);
  assert.ok(Math.abs(aggregateUploadProgress(items) - 0.5) < 1e-9);
  assert.equal(progressPercent(1), 100);
  assert.equal(progressPercent(0.335), 34);
  assert.equal(progressPercent(0), 0);
});

// ---------------------------------------------------------------------------
// Accessibility names
// ---------------------------------------------------------------------------

test('builds file-specific aria labels for remove and retry buttons', () => {
  assert.equal(removeAriaLabel('quarterly sales.csv'), 'Remove quarterly sales.csv');
  assert.equal(retryAriaLabel('quarterly sales.csv'), 'Retry upload for quarterly sales.csv');
  assert.ok(removeAriaLabel('report.pdf').includes('report.pdf'));
  assert.ok(retryAriaLabel('report.pdf').includes('report.pdf'));
});

// ---------------------------------------------------------------------------
// First-six plus "+N" collapse
// ---------------------------------------------------------------------------

test('collapses rail items beyond the first rows into a +N remainder', () => {
  assert.equal(RAIL_MAX_VISIBLE, 6);
  const drafts = Array.from({ length: 7 }, (_, i) => makeDraft({ clientId: `c${i}`, name: `f${i}.csv` }));
  const items = toRailItems(drafts);
  const { visible, hiddenCount } = collapseRail(items);
  assert.equal(hiddenCount, 1);
  assert.deepEqual(
    visible.map(item => item.clientId),
    ['c0', 'c1', 'c2', 'c3', 'c4', 'c5'],
  );
});

test('keeps every item visible at or below the visible cap', () => {
  const four = toRailItems(Array.from({ length: 4 }, (_, i) => makeDraft({ clientId: `c${i}` })));
  assert.deepEqual(collapseRail(four), { visible: four, hiddenCount: 0 });
  assert.deepEqual(collapseRail([]), { visible: [], hiddenCount: 0 });
});

// ---------------------------------------------------------------------------
// Preview eligibility
// ---------------------------------------------------------------------------

test('allows preview for ready and preview_failed items only', () => {
  assert.equal(
    canPreviewItem(toRailItems([makeDraft({ upload: { status: 'done' }, preview: { status: 'ready' } })])[0]),
    true,
  );
  assert.equal(
    canPreviewItem(toRailItems([makeDraft({ upload: { status: 'done' }, preview: { status: 'preview_failed' } })])[0]),
    true,
  );
  assert.equal(canPreviewItem(toRailItems([makeDraft({ upload: { status: 'uploading', progress: 0.7 } })])[0]), false);
  assert.equal(canPreviewItem(toRailItems([makeDraft({ upload: { status: 'failed' } })])[0]), false);
  assert.equal(
    canPreviewItem(toRailItems([makeDraft({ upload: { status: 'done' }, preview: { status: 'idle' } })])[0]),
    false,
  );
  assert.equal(
    canPreviewItem(toRailItems([makeDraft({ upload: { status: 'done' }, preview: { status: 'loading' } })])[0]),
    false,
  );
});

test('mirrors snapshot eligibility for history cards', () => {
  assert.equal(canPreviewSnapshot('ready'), true);
  assert.equal(canPreviewSnapshot('preview_failed'), true);
  assert.equal(canPreviewSnapshot('failed'), false);
  assert.equal(canPreviewSnapshot('uploading'), false);
  assert.equal(canPreviewSnapshot('inspecting'), false);
  assert.equal(canPreviewSnapshot('deleted'), false);
});

// ---------------------------------------------------------------------------
// Overlay breakpoint selection
// ---------------------------------------------------------------------------

test('selects the right panel on desktop widths', () => {
  assert.deepEqual(resolvePreviewOverlay(1440), { mode: 'right-panel' });
  assert.deepEqual(resolvePreviewOverlay(1024), { mode: 'right-panel' });
});

test('selects a Drawer of min(720px, 90vw) on tablet widths', () => {
  assert.deepEqual(resolvePreviewOverlay(1023), { mode: 'drawer', width: 720 });
  assert.deepEqual(resolvePreviewOverlay(768), { mode: 'drawer', width: 691 });
  assert.deepEqual(resolvePreviewOverlay(700), { mode: 'drawer', width: 630 });
  assert.deepEqual(resolvePreviewOverlay(640), { mode: 'drawer', width: 576 });
});

test('selects fullscreen below 640px', () => {
  assert.deepEqual(resolvePreviewOverlay(639), { mode: 'fullscreen' });
  assert.deepEqual(resolvePreviewOverlay(375), { mode: 'fullscreen' });
});

// ---------------------------------------------------------------------------
// Reduced motion
// ---------------------------------------------------------------------------

test('exposes a truthy motion class only when reduced motion is preferred', () => {
  assert.equal(motionClassName(true), REDUCED_MOTION_CLASS);
  assert.ok(motionClassName(true));
  assert.equal(motionClassName(false), '');
});

// ---------------------------------------------------------------------------
// Display formatting + icons
// ---------------------------------------------------------------------------

test('formats bytes into a human readable size', () => {
  assert.equal(formatBytes(0), '0 B');
  assert.equal(formatBytes(512), '512 B');
  assert.equal(formatBytes(2048), '2.00 KB');
  assert.equal(formatBytes(1.5 * 1024 * 1024), '1.50 MB');
  assert.equal(formatBytes(2 * 1024 * 1024 * 1024), '2.00 GB');
});

test('picks an icon per file type with spreadsheet priority', () => {
  assert.equal(fileIconKey({ name: 'sales.csv' }), 'table');
  assert.equal(fileIconKey({ name: 'book.xlsx' }), 'table');
  assert.equal(fileIconKey({ name: 'plot.png' }), 'image');
  assert.equal(fileIconKey({ name: 'deck.pptx' }), 'slide');
  assert.equal(fileIconKey({ name: 'notes.md' }), 'text');
  assert.equal(fileIconKey({ name: 'archive.bin', mediaType: 'application/octet-stream' }), 'file');
});

// ---------------------------------------------------------------------------
// DraftItem view mapping
// ---------------------------------------------------------------------------

test('flattens drafts into rail items carrying identity, ids and errors', () => {
  const withSnapshot = toRailItems([
    makeDraft({
      clientId: 'a',
      name: 'real.csv',
      size: 4096,
      upload: { status: 'done', progress: 1 },
      snapshot: makeSnapshot({ file_id: 'srv-1', media_type: 'text/csv' }),
    }),
  ])[0];
  assert.equal(withSnapshot.fileId, 'srv-1');
  assert.equal(withSnapshot.mediaType, 'text/csv');
  assert.equal(withSnapshot.name, 'real.csv');
  assert.equal(withSnapshot.size, 4096);
  assert.equal(withSnapshot.error, null);

  const failed = toRailItems([makeDraft({ clientId: 'b', upload: { status: 'failed', error: 'boom' } })])[0];
  assert.equal(failed.fileId, null);
  assert.equal(failed.error, 'boom');

  const invalid = toRailItems([
    makeDraft({ clientId: 'c', validation: { status: 'invalid', error: 'unsupported' }, upload: { error: null } }),
  ])[0];
  assert.equal(invalid.error, 'unsupported');
});

// ---------------------------------------------------------------------------
// Preview payload normalization (AttachmentPreview)
// ---------------------------------------------------------------------------

test('routes table previews for spreadsheet kinds', () => {
  const mode = resolvePreviewMode({
    kind: 'table',
    mediaType: 'text/csv',
    preview: { columns: ['a', 'b'], rows: [[1, 2]] },
  });
  assert.equal(mode, 'table');
});

test('routes text previews for markdown/text kinds', () => {
  assert.equal(
    resolvePreviewMode({ kind: 'markdown', mediaType: 'text/markdown', preview: { text: '# Title' } }),
    'text',
  );
  assert.equal(resolvePreviewMode({ kind: 'text', mediaType: 'text/plain', preview: { content: 'log line' } }), 'text');
});

test('routes document previews for pdf/word kinds even without body text', () => {
  assert.equal(
    resolvePreviewMode({ kind: 'document', mediaType: 'application/pdf', preview: { metadata: { pages: 3 } } }),
    'document',
  );
});

test('falls back to an empty mode when payload is missing or malformed', () => {
  assert.equal(resolvePreviewMode({ kind: 'table', mediaType: 'text/csv', preview: {} }), 'empty');
  assert.equal(resolvePreviewMode({ kind: 'text', mediaType: 'text/plain', preview: null }), 'empty');
  assert.equal(resolvePreviewMode({ kind: 'table', mediaType: 'text/csv', preview: { rows: 'nope' } }), 'empty');
  assert.equal(resolvePreviewMode({ mediaType: 'application/octet-stream', preview: { blob: true } }), 'empty');
});

test('normalizes array and record rows into column-ordered arrays', () => {
  const normalized = normalizeTablePreview({
    columns: ['a', 'b'],
    rows: [
      [1, 2],
      [3, 4],
    ],
  });
  assert.deepEqual(normalized, {
    columns: ['a', 'b'],
    rows: [
      [1, 2],
      [3, 4],
    ],
  });

  const fromRecords = normalizeTablePreview({ columns: ['a', 'b'], rows: [{ b: 2, a: 1 }] });
  assert.deepEqual(fromRecords, { columns: ['a', 'b'], rows: [[1, 2]] });

  assert.equal(normalizeTablePreview({ rows: [[1]] }), null);
  assert.equal(normalizeTablePreview({ columns: 'x' }), null);
});

test('extracts plain text from text/markdown payloads', () => {
  assert.equal(normalizeTextPreview({ text: 'hello' }), 'hello');
  assert.equal(normalizeTextPreview({ content: 'markdown body' }), 'markdown body');
  assert.equal(normalizeTextPreview({}), null);
});

test('extracts metadata and optional body text from document payloads', () => {
  assert.deepEqual(normalizeDocumentPreview({ metadata: { pages: 2, author: 'ant' }, text: 'body' }), {
    metadata: { pages: 2, author: 'ant' },
    text: 'body',
  });
  assert.deepEqual(normalizeDocumentPreview({ metadata: { pages: 2 } }), { metadata: { pages: 2 }, text: null });
  assert.equal(normalizeDocumentPreview({}), null);
});

// ---------------------------------------------------------------------------
// Read-only legacy rail item (Task12 gap)
// ---------------------------------------------------------------------------

test('toLegacyRailItem maps a server-preloaded file to a read-only rail entry', () => {
  const item = toLegacyRailItem({
    name: 'sales.csv',
    size: 4096,
    media_type: 'text/csv',
    file_path: '/data/python_uploads/u1/sales.csv',
  });
  // Read-only by construction: no preview, retry, or upload state is claimed.
  assert.equal(item.key, 'legacy:/data/python_uploads/u1/sales.csv');
  assert.equal(item.name, 'sales.csv');
  assert.equal(item.size, 4096);
  assert.equal(item.mediaType, 'text/csv');
});
