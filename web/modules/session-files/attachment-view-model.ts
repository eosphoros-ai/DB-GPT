/**
 * Pure view-model helpers for the session-files UI components.
 *
 * This module intentionally stays DOM/JSX-free: every helper that the rail,
 * the history card group and the preview renderer depend on is derived here
 * so it can be verified with `node --test` under Node's type stripping
 * (AttachmentRail.test.ts). The .tsx components only wire these results into
 * Ant Design JSX.
 */

import type { DraftFile, LegacyServerFile, PreviewPhase, SessionFileStatus, UploadPhase } from './types';

// ---------------------------------------------------------------------------
// Rail item view model
// ---------------------------------------------------------------------------

/** Flattened, render-ready view of one DraftFile row in the rail. */
export interface RailItem {
  clientId: string;
  name: string;
  size: number;
  mediaType: string;
  uploadStatus: UploadPhase;
  /** 0..1 */
  uploadProgress: number;
  previewStatus: PreviewPhase;
  /** Hard failure reason (upload or validation), if any. */
  error: string | null;
  /** Server file id once the upload completed. */
  fileId: string | null;
}

export function toRailItems(drafts: readonly DraftFile[]): RailItem[] {
  return drafts.map(draft => ({
    clientId: draft.clientId,
    name: draft.identity.name,
    size: draft.identity.size,
    mediaType: draft.file?.type || draft.snapshot?.media_type || '',
    uploadStatus: draft.upload.status,
    uploadProgress: draft.upload.progress,
    previewStatus: draft.preview.status,
    error: draft.validation.status === 'invalid' ? draft.validation.error : draft.upload.error,
    fileId: draft.snapshot?.file_id ?? null,
  }));
}

/**
 * Read-only rail entry for a legacy server-preloaded file (example cards).
 * It claims no upload state, retry, or preview: the card renders name, size
 * and a server badge only, and the `legacy:` key is non-resolvable.
 */
export interface LegacyRailItem {
  key: string;
  name: string;
  size: number;
  mediaType: string;
}

export function toLegacyRailItem(file: LegacyServerFile): LegacyRailItem {
  return {
    key: `legacy:${file.file_path}`,
    name: file.name,
    size: file.size,
    mediaType: file.media_type,
  };
}

// ---------------------------------------------------------------------------
// Status labels (upload and preview stay orthogonal)
// ---------------------------------------------------------------------------

export const UPLOAD_STATUS_LABELS: Record<UploadPhase, string> = Object.freeze({
  queued: 'Queued',
  uploading: 'Uploading',
  done: 'Ready',
  failed: 'Upload failed',
  cancelled: 'Cancelled',
  blocked: 'Blocked',
});

export const PREVIEW_STATUS_LABELS: Record<PreviewPhase, string> = Object.freeze({
  idle: '',
  loading: 'Loading preview',
  ready: 'Preview ready',
  preview_failed: 'Preview unavailable',
});

/** Hard failures (upload/validation) render destructive and demand attention. */
export function isHardFailure(item: Pick<RailItem, 'uploadStatus'>): boolean {
  return item.uploadStatus === 'failed' || item.uploadStatus === 'blocked';
}

/** Only real upload failures can be retried; validation-blocked items cannot. */
export function canRetry(item: Pick<RailItem, 'uploadStatus'>): boolean {
  return item.uploadStatus === 'failed';
}

// ---------------------------------------------------------------------------
// Aggregate progress (deterministic aria-valuenow source)
// ---------------------------------------------------------------------------

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
}

/**
 * Mean upload progress across in-flight items (queued → 0, uploading → its
 * ratio, done → 1). Failed/cancelled/blocked items are excluded; 0 when the
 * queue is idle so the bar can hide without flickering.
 */
export function aggregateUploadProgress(items: readonly Pick<RailItem, 'uploadStatus' | 'uploadProgress'>[]): number {
  let total = 0;
  let count = 0;
  for (const item of items) {
    if (item.uploadStatus === 'done') {
      total += 1;
      count += 1;
    } else if (item.uploadStatus === 'uploading' || item.uploadStatus === 'queued') {
      total += clamp01(item.uploadProgress);
      count += 1;
    }
  }
  return count === 0 ? 0 : total / count;
}

/** Integer percent for `aria-valuenow`; deterministic for screen readers. */
export function progressPercent(ratio: number): number {
  return Math.round(clamp01(ratio) * 100);
}

// ---------------------------------------------------------------------------
// Accessibility names
// ---------------------------------------------------------------------------

export function removeAriaLabel(name: string): string {
  return `Remove ${name}`;
}

export function retryAriaLabel(name: string): string {
  return `Retry upload for ${name}`;
}

// ---------------------------------------------------------------------------
// First rows + "+N" collapse
// ---------------------------------------------------------------------------

/** Rows (one per item) shown before the remainder collapses into `+N`. */
export const RAIL_MAX_VISIBLE = 6;

export function collapseRail<T>(
  items: readonly T[],
  maxVisible = RAIL_MAX_VISIBLE,
): { visible: readonly T[]; hiddenCount: number } {
  if (items.length <= maxVisible) {
    return { visible: items, hiddenCount: 0 };
  }
  return { visible: items.slice(0, maxVisible), hiddenCount: items.length - maxVisible };
}

/**
 * A single removable draft already communicates its own metadata and remove
 * action. Multi-file and legacy sets keep the summary for count/total and the
 * legacy-only clear affordance.
 */
export function shouldShowComfortableSummary(input: {
  totalCount: number;
  legacyCount: number;
  hasPerItemRemove: boolean;
}): boolean {
  if (input.totalCount <= 0) return false;
  return input.totalCount > 1 || input.legacyCount > 0 || !input.hasPerItemRemove;
}

// ---------------------------------------------------------------------------
// Compact composer rail
// ---------------------------------------------------------------------------

/**
 * Compact mode reserves room for the overflow manager and add-file control.
 * These breakpoints intentionally use the rail's own measured width rather
 * than the viewport: the inference panel may be narrow on a desktop screen.
 */
export function resolveCompactRailLimit(containerWidth: number): 0 | 1 | 2 | 3 {
  const width = Number.isFinite(containerWidth) ? Math.max(0, containerWidth) : 0;
  if (width < 280) return 0;
  if (width < 320) return 1;
  if (width < 560) return 2;
  return 3;
}

export interface CompactRailLayout<T> {
  /** Most recently added entries kept visible beside the add control. */
  visible: readonly T[];
  /** Older entries represented by the +N manager. */
  hidden: readonly T[];
  hiddenCount: number;
}

/**
 * Keep the newest entries visible so adding a file always gives immediate
 * visual confirmation. Hidden entries retain their original ordering.
 */
export function collapseCompactRail<T>(items: readonly T[], containerWidth: number): CompactRailLayout<T> {
  const limit = resolveCompactRailLimit(containerWidth);
  const hiddenCount = Math.max(0, items.length - limit);
  return {
    visible: items.slice(hiddenCount),
    hidden: items.slice(0, hiddenCount),
    hiddenCount,
  };
}

export interface CompactRailStatusSummary {
  errorCount: number;
  processingCount: number;
  warningCount: number;
}

/** Status signal displayed on +N so folded failures never disappear. */
export function summarizeCompactRailStatus(
  items: readonly Pick<RailItem, 'uploadStatus' | 'previewStatus'>[],
): CompactRailStatusSummary {
  return items.reduce<CompactRailStatusSummary>(
    (summary, item) => {
      if (isHardFailure(item)) summary.errorCount += 1;
      else if (
        item.uploadStatus === 'queued' ||
        item.uploadStatus === 'uploading' ||
        (item.uploadStatus === 'done' && item.previewStatus === 'loading')
      ) {
        summary.processingCount += 1;
      } else if (item.previewStatus === 'preview_failed') {
        summary.warningCount += 1;
      }
      return summary;
    },
    { errorCount: 0, processingCount: 0, warningCount: 0 },
  );
}

// ---------------------------------------------------------------------------
// Preview eligibility
// ---------------------------------------------------------------------------

/** Drafts: only a completed upload with a settled preview may be previewed. */
export function canPreviewItem(item: Pick<RailItem, 'uploadStatus' | 'previewStatus'>): boolean {
  return item.uploadStatus === 'done' && (item.previewStatus === 'ready' || item.previewStatus === 'preview_failed');
}

/** Snapshots (history cards): same rule on the server lifecycle status. */
export function canPreviewSnapshot(status: SessionFileStatus): boolean {
  return status === 'ready' || status === 'preview_failed';
}

// ---------------------------------------------------------------------------
// Overlay breakpoint selection
// ---------------------------------------------------------------------------

export const PREVIEW_DESKTOP_MIN_WIDTH = 1024;
export const PREVIEW_FULLSCREEN_MAX_WIDTH = 640;
export const PREVIEW_DRAWER_MAX_WIDTH = 720;
export const PREVIEW_DRAWER_VIEWPORT_RATIO = 0.9;

export type PreviewOverlayLayout = { mode: 'right-panel' } | { mode: 'drawer'; width: number } | { mode: 'fullscreen' };

/**
 * Desktop (≥1024px) reuses the chat right panel; tablet (640–1023px) opens an
 * overlay Drawer of `min(720px, 90vw)`; phones (<640px) go fullscreen so the
 * chat column never gets squeezed.
 */
export function resolvePreviewOverlay(viewportWidth: number): PreviewOverlayLayout {
  if (viewportWidth >= PREVIEW_DESKTOP_MIN_WIDTH) return { mode: 'right-panel' };
  if (viewportWidth >= PREVIEW_FULLSCREEN_MAX_WIDTH) {
    return {
      mode: 'drawer',
      width: Math.min(PREVIEW_DRAWER_MAX_WIDTH, Math.round(viewportWidth * PREVIEW_DRAWER_VIEWPORT_RATIO)),
    };
  }
  return { mode: 'fullscreen' };
}

// ---------------------------------------------------------------------------
// Reduced motion
// ---------------------------------------------------------------------------

/** Applied to the rail root; CSS under this class disables animations. */
export const REDUCED_MOTION_CLASS = 'session-files-reduced-motion';

export function motionClassName(prefersReducedMotion: boolean): string {
  return prefersReducedMotion ? REDUCED_MOTION_CLASS : '';
}

// ---------------------------------------------------------------------------
// Formatting + icon selection
// ---------------------------------------------------------------------------

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes)) return '0 B';
  const KB = 1024;
  const MB = KB * 1024;
  const GB = MB * 1024;
  if (bytes < KB) return `${bytes} B`;
  if (bytes < MB) return `${(bytes / KB).toFixed(2)} KB`;
  if (bytes < GB) return `${(bytes / MB).toFixed(2)} MB`;
  return `${(bytes / GB).toFixed(2)} GB`;
}

export type FileIconKey = 'table' | 'image' | 'slide' | 'text' | 'file';

const TABLE_EXTS = new Set(['csv', 'tsv', 'xls', 'xlsx', 'parquet', 'json', 'jsonl']);
const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp']);
const SLIDE_EXTS = new Set(['ppt', 'pptx']);
const TEXT_EXTS = new Set(['txt', 'md', 'markdown', 'log', 'doc', 'docx', 'rtf', 'pdf']);

export function fileIconKey(input: { name?: string; mediaType?: string; kind?: string }): FileIconKey {
  const mediaType = (input.mediaType ?? '').toLowerCase();
  if (
    input.kind === 'table' ||
    mediaType.includes('spreadsheet') ||
    mediaType.includes('excel') ||
    mediaType.includes('csv')
  ) {
    return 'table';
  }
  if (mediaType.startsWith('image/')) return 'image';
  if (mediaType.includes('presentation')) return 'slide';
  const ext = (input.name ?? '').toLowerCase().split('.').pop() ?? '';
  if (TABLE_EXTS.has(ext)) return 'table';
  if (IMAGE_EXTS.has(ext)) return 'image';
  if (SLIDE_EXTS.has(ext)) return 'slide';
  if (
    TEXT_EXTS.has(ext) ||
    mediaType.startsWith('text/') ||
    mediaType.includes('pdf') ||
    mediaType.includes('word') ||
    mediaType.includes('markdown')
  ) {
    return 'text';
  }
  return 'file';
}

// ---------------------------------------------------------------------------
// Preview payload normalization (AttachmentPreview)
// ---------------------------------------------------------------------------

export type PreviewMode = 'table' | 'text' | 'document' | 'empty';

/**
 * User-facing scope shown beside the previewed file metadata. The view-model
 * stays i18n-agnostic: it returns translation keys (+ interpolation params)
 * and the React layer renders them through `t()` — same pattern as
 * `typeLabelKey` in AttachmentMessageCards.
 */
export interface PreviewScopeSummary {
  labelKey:
    | 'session_files_scope_limited'
    | 'session_files_scope_table_empty'
    | 'session_files_scope_table_rows'
    | 'session_files_scope_document'
    | 'session_files_scope_content';
  labelParams?: { count: number };
  partial: boolean;
  hintKey: 'session_files_scope_truncated_hint' | null;
}

/**
 * Describe what is visibly rendered without pretending `truncated` means a
 * row-only limit. The backend may truncate rows, columns, sheets, pages or
 * bytes, so table row counts always come from the normalized visible rows.
 */
export function buildPreviewScopeSummary(input: {
  mode: PreviewMode;
  truncated: boolean;
  visibleRows?: number;
}): PreviewScopeSummary | null {
  const hintKey: PreviewScopeSummary['hintKey'] = input.truncated ? 'session_files_scope_truncated_hint' : null;

  if (input.mode === 'empty') {
    return input.truncated
      ? {
          labelKey: 'session_files_scope_limited',
          partial: true,
          hintKey,
        }
      : null;
  }

  if (input.mode === 'table') {
    const rows = Number.isFinite(input.visibleRows) ? Math.max(0, Math.floor(input.visibleRows ?? 0)) : 0;
    return rows === 0
      ? {
          labelKey: 'session_files_scope_table_empty',
          partial: input.truncated,
          hintKey,
        }
      : {
          labelKey: 'session_files_scope_table_rows',
          labelParams: { count: rows },
          partial: input.truncated,
          hintKey,
        };
  }

  return {
    labelKey: input.mode === 'document' ? 'session_files_scope_document' : 'session_files_scope_content',
    partial: input.truncated,
    hintKey,
  };
}

export interface TablePreviewData {
  columns: string[];
  rows: unknown[][];
}

export interface DocumentPreviewData {
  metadata: Record<string, unknown>;
  text: string | null;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Columns + rows arrays (or record rows) aligned to the column order. */
/** Header cells may be numbers/null (xlsx); table columns must be strings. */
const headerCellText = (cell: unknown): string => {
  if (cell === null || cell === undefined) return '';
  return String(cell);
};

export function normalizeTablePreview(preview: Record<string, unknown> | null | undefined): TablePreviewData | null {
  if (!isPlainRecord(preview)) return null;

  // Shape A — explicit columns (JSON/JSONL inspector output). Rows may be
  // arrays or records keyed by column name.
  const columns = preview.columns;
  if (Array.isArray(columns) && !columns.some(column => typeof column !== 'string')) {
    const typedColumns = columns as string[];
    const rows = preview.rows;
    if (!Array.isArray(rows)) return null;
    const normalizedRows: unknown[][] = rows.map(row => {
      if (Array.isArray(row)) {
        return typedColumns.map((_, index) => row[index]);
      }
      if (isPlainRecord(row)) {
        return typedColumns.map(column => row[column]);
      }
      return typedColumns.map(() => undefined);
    });
    return { columns: typedColumns, rows: normalizedRows };
  }

  // Shape B — raw delimited rows (CSV/TSV inspector output: no `columns`,
  // the first row is the header, mirroring spreadsheet conventions).
  const rawRows = preview.rows;
  if (Array.isArray(rawRows) && rawRows.length > 0 && Array.isArray(rawRows[0])) {
    const header = (rawRows[0] as unknown[]).map(headerCellText);
    const rows = rawRows
      .slice(1)
      .map(row => (Array.isArray(row) ? header.map((_, index) => row[index]) : header.map(() => undefined)));
    return { columns: header, rows };
  }

  // Shape C — workbook sheets (XLSX/XLS inspector output). The first sheet
  // represents the table; its first row is the header.
  const sheets = preview.sheets;
  if (Array.isArray(sheets) && sheets.length > 0) {
    const first = sheets[0];
    if (isPlainRecord(first) && Array.isArray(first.rows) && first.rows.length > 0 && Array.isArray(first.rows[0])) {
      const header = (first.rows[0] as unknown[]).map(headerCellText);
      const rows = first.rows
        .slice(1)
        .map(row => (Array.isArray(row) ? header.map((_, index) => row[index]) : header.map(() => undefined)));
      return { columns: header, rows };
    }
  }

  return null;
}

/** Plain text body of a text/markdown preview (`text` or `content`). */
export function normalizeTextPreview(preview: Record<string, unknown> | null | undefined): string | null {
  if (!isPlainRecord(preview)) return null;
  if (typeof preview.text === 'string') return preview.text;
  if (typeof preview.content === 'string') return preview.content;
  return null;
}

/** Document metadata plus optional extracted body text. */
export function normalizeDocumentPreview(
  preview: Record<string, unknown> | null | undefined,
): DocumentPreviewData | null {
  if (!isPlainRecord(preview)) return null;
  const metadata =
    isPlainRecord(preview.metadata) && Object.keys(preview.metadata).length > 0 ? preview.metadata : null;
  const text =
    typeof preview.text === 'string' ? preview.text : typeof preview.content === 'string' ? preview.content : null;
  if (!metadata && text === null) return null;
  return { metadata: metadata ?? {}, text };
}

/**
 * Route a preview payload to a render mode. Empty/missing payloads never
 * pretend to be renderable — the component shows a graceful empty state.
 */
export function resolvePreviewMode(input: {
  kind?: string;
  mediaType?: string;
  preview?: Record<string, unknown> | null;
}): PreviewMode {
  const preview = input.preview;
  if (!isPlainRecord(preview) || Object.keys(preview).length === 0) return 'empty';

  const kind = input.kind ?? '';
  const media = (input.mediaType ?? '').toLowerCase();

  const isTableLike =
    kind === 'table' || media.includes('csv') || media.includes('spreadsheet') || media.includes('excel');
  if (isTableLike) return normalizeTablePreview(preview) ? 'table' : 'empty';

  const isDocumentLike =
    kind === 'document' || media.includes('pdf') || media.includes('word') || media.includes('presentation');
  if (isDocumentLike) return normalizeDocumentPreview(preview) ? 'document' : 'empty';

  const isTextLike = kind === 'text' || kind === 'markdown' || media.startsWith('text/');
  if (isTextLike) return normalizeTextPreview(preview) !== null ? 'text' : 'empty';

  // Unknown kind: opportunistically match the payload shape.
  if (normalizeTablePreview(preview)) return 'table';
  if (normalizeTextPreview(preview) !== null) return 'text';
  if (normalizeDocumentPreview(preview)) return 'document';
  return 'empty';
}
