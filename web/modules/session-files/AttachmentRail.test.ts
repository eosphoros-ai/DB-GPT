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
  buildPreviewScopeSummary,
  canPreviewItem,
  canPreviewSnapshot,
  canRetry,
  collapseCompactRail,
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
  resolveCompactRailLimit,
  resolvePreviewOverlay,
  retryAriaLabel,
  shouldShowComfortableSummary,
  summarizeCompactRailStatus,
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

test('hides only the redundant single-draft summary in comfortable mode', () => {
  assert.equal(shouldShowComfortableSummary({ totalCount: 0, legacyCount: 0, hasPerItemRemove: true }), false);
  assert.equal(shouldShowComfortableSummary({ totalCount: 1, legacyCount: 0, hasPerItemRemove: true }), false);
  assert.equal(shouldShowComfortableSummary({ totalCount: 2, legacyCount: 0, hasPerItemRemove: true }), true);
  assert.equal(shouldShowComfortableSummary({ totalCount: 1, legacyCount: 1, hasPerItemRemove: false }), true);
  assert.equal(shouldShowComfortableSummary({ totalCount: 1, legacyCount: 0, hasPerItemRemove: false }), true);
});

// ---------------------------------------------------------------------------
// Compact rail: container-aware 1 / 2 / 3 item layout
// ---------------------------------------------------------------------------

test('uses the compact rail container width rather than viewport breakpoints', () => {
  assert.equal(resolveCompactRailLimit(Number.NaN), 0);
  assert.equal(resolveCompactRailLimit(0), 0);
  assert.equal(resolveCompactRailLimit(279), 0);
  assert.equal(resolveCompactRailLimit(280), 1);
  assert.equal(resolveCompactRailLimit(319), 1);
  assert.equal(resolveCompactRailLimit(320), 2);
  assert.equal(resolveCompactRailLimit(559), 2);
  assert.equal(resolveCompactRailLimit(560), 3);
});

test('keeps newest compact attachments visible and folds older entries into +N', () => {
  const files = ['a.csv', 'b.csv', 'c.csv', 'd.csv'];
  const extraNarrow = collapseCompactRail(files, 240);
  assert.deepEqual(extraNarrow, {
    visible: [],
    hidden: files,
    hiddenCount: 4,
  });

  const narrow = collapseCompactRail(files, 300);
  assert.deepEqual(narrow, {
    visible: ['d.csv'],
    hidden: ['a.csv', 'b.csv', 'c.csv'],
    hiddenCount: 3,
  });

  const medium = collapseCompactRail(files, 400);
  assert.deepEqual(medium, {
    visible: ['c.csv', 'd.csv'],
    hidden: ['a.csv', 'b.csv'],
    hiddenCount: 2,
  });

  const wide = collapseCompactRail(files, 600);
  assert.deepEqual(wide, {
    visible: ['b.csv', 'c.csv', 'd.csv'],
    hidden: ['a.csv'],
    hiddenCount: 1,
  });
  assert.deepEqual(files, ['a.csv', 'b.csv', 'c.csv', 'd.csv']);
});

test('does not create a compact remainder at or below the measured capacity', () => {
  const files = ['a.csv', 'b.csv'];
  assert.deepEqual(collapseCompactRail(files, 600), {
    visible: files,
    hidden: [],
    hiddenCount: 0,
  });
  assert.deepEqual(collapseCompactRail([], 320), {
    visible: [],
    hidden: [],
    hiddenCount: 0,
  });
});

test('summarizes processing and failures hidden behind the compact +N control', () => {
  const items = toRailItems([
    makeDraft({ clientId: 'queued', upload: { status: 'queued' } }),
    makeDraft({ clientId: 'uploading', upload: { status: 'uploading', progress: 0.5 } }),
    makeDraft({ clientId: 'parsing', upload: { status: 'done' }, preview: { status: 'loading' } }),
    makeDraft({ clientId: 'failed', upload: { status: 'failed' } }),
    makeDraft({
      clientId: 'blocked',
      validation: { status: 'invalid', error: 'bad type' },
      upload: { status: 'blocked' },
    }),
    makeDraft({ clientId: 'warning', upload: { status: 'done' }, preview: { status: 'preview_failed' } }),
    makeDraft({ clientId: 'ready', upload: { status: 'done' }, preview: { status: 'ready' } }),
  ]);
  assert.deepEqual(summarizeCompactRailStatus(items), {
    errorCount: 2,
    processingCount: 3,
    warningCount: 1,
  });
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

  assert.equal(normalizeTablePreview({ columns: 'x' }), null);
  assert.equal(normalizeTablePreview({ rows: 'nope' }), null);
  assert.equal(normalizeTablePreview({ rows: [] }), null);
});

test('normalizes CSV/TSV payloads whose first row is the header', () => {
  // Inspector `_parse_delimited` output: { encoding, delimiter, rows } — no
  // explicit `columns`; the first row carries the header.
  const normalized = normalizeTablePreview({
    encoding: 'utf-8',
    delimiter: ',',
    rows: [
      ['TrackId', 'Name', 'Milliseconds'],
      ['1', 'For Those About To Rock', '343719'],
      ['2', 'Balls to the Wall', '342562'],
    ],
  });
  assert.deepEqual(normalized, {
    columns: ['TrackId', 'Name', 'Milliseconds'],
    rows: [
      ['1', 'For Those About To Rock', '343719'],
      ['2', 'Balls to the Wall', '342562'],
    ],
  });

  // Header-only file degrades to zero data rows, not a rejection.
  assert.deepEqual(normalizeTablePreview({ rows: [['a', 'b']] }), { columns: ['a', 'b'], rows: [] });
  // Non-string header cells are stringified (xlsx headers may be numeric/null).
  assert.deepEqual(
    normalizeTablePreview({
      rows: [
        [1, null],
        ['x', 'y'],
      ],
    }),
    {
      columns: ['1', ''],
      rows: [['x', 'y']],
    },
  );
  // A malformed row must never reach AttachmentPreview as a non-array.
  assert.deepEqual(normalizeTablePreview({ rows: [['a', 'b'], null, ['x']] }), {
    columns: ['a', 'b'],
    rows: [
      [undefined, undefined],
      ['x', undefined],
    ],
  });
});

test('normalizes xlsx workbook payloads from the first sheet', () => {
  // Inspector `_parse_xlsx`/`_parse_xls` output: { sheets: [{ name, rows }] }.
  const normalized = normalizeTablePreview({
    sheets: [
      {
        name: 'Sheet1',
        rows: [
          ['city', 'sales'],
          ['hz', 10],
          ['sh', 20],
        ],
      },
      { name: 'Sheet2', rows: [['ignored']] },
    ],
  });
  assert.deepEqual(normalized, {
    columns: ['city', 'sales'],
    rows: [
      ['hz', 10],
      ['sh', 20],
    ],
  });

  assert.equal(normalizeTablePreview({ sheets: [] }), null);
  assert.equal(normalizeTablePreview({ sheets: [{ name: 'S', rows: [] }] }), null);
  assert.deepEqual(normalizeTablePreview({ sheets: [{ name: 'S', rows: [['a'], null] }] }), {
    columns: ['a'],
    rows: [[undefined]],
  });
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

test('describes table preview rows without treating truncated as a row-only limit', () => {
  assert.deepEqual(buildPreviewScopeSummary({ mode: 'table', truncated: false, visibleRows: 7 }), {
    labelKey: 'session_files_scope_table_rows',
    labelParams: { count: 7 },
    partial: false,
    hintKey: null,
  });
  assert.deepEqual(buildPreviewScopeSummary({ mode: 'table', truncated: true, visibleRows: 1 }), {
    labelKey: 'session_files_scope_table_rows',
    labelParams: { count: 1 },
    partial: true,
    hintKey: 'session_files_scope_truncated_hint',
  });
  assert.equal(
    buildPreviewScopeSummary({ mode: 'table', truncated: false, visibleRows: 20 })?.labelKey,
    'session_files_scope_table_rows',
  );
  assert.equal(
    buildPreviewScopeSummary({ mode: 'table', truncated: false, visibleRows: 0 })?.labelKey,
    'session_files_scope_table_empty',
  );
});

test('describes text and document preview scope in user-facing language', () => {
  assert.equal(buildPreviewScopeSummary({ mode: 'text', truncated: false })?.labelKey, 'session_files_scope_content');
  assert.equal(
    buildPreviewScopeSummary({ mode: 'document', truncated: false })?.labelKey,
    'session_files_scope_document',
  );
  assert.equal(
    buildPreviewScopeSummary({ mode: 'document', truncated: true })?.labelKey,
    'session_files_scope_document',
  );
  assert.deepEqual(buildPreviewScopeSummary({ mode: 'empty', truncated: true }), {
    labelKey: 'session_files_scope_limited',
    partial: true,
    hintKey: 'session_files_scope_truncated_hint',
  });
  assert.equal(buildPreviewScopeSummary({ mode: 'empty', truncated: false }), null);
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
