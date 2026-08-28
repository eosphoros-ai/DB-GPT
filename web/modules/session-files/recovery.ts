/**
 * Recovery view-model for the public share page and scheduled-task surfaces.
 *
 * Owner-side history resolves real `sf_…` server ids so previews can call the
 * auth-protected endpoints. The surfaces served by this module must never do
 * that:
 *
 * - the public share page renders names/statuses only; a snapshot identity is
 *   always the non-resolvable `display_key` (or a synthetic placeholder), so
 *   no component can construct a preview/download URL from a share payload —
 *   even if a stored payload was polluted with a real private ``file_id``;
 * - scheduled-task surfaces render the frozen `ext_info.input_files` list the
 *   same way (metadata only), while the replay-time task-scoped `file_ids`
 *   stay server-side;
 * - legacy tasks keep `ext_info.file_path` display-only: only the basename is
 *   shown, and it is never turned into a URL.
 *
 * Everything here is DOM/JSX-free so it can be verified with `node --test`
 * (recovery.test.ts); the .tsx pages only wire these results into Ant Design.
 */

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { REACT_HISTORY_PAYLOAD_VERSION, snapshotsFromInputFiles } from './home-adapter.ts';
import type { SessionFileSnapshot } from './types';

// ---------------------------------------------------------------------------
// Display-only snapshots (share page + scheduled task surfaces)
// ---------------------------------------------------------------------------

/**
 * Drop a stored `file_id` before parsing so the base adapter can never adopt
 * a resolvable identity. Non-entry values pass through untouched (the base
 * parser skips them deterministically).
 */
function stripPrivateIdentity(entry: unknown): unknown {
  if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) return entry;
  const wire = { ...(entry as Record<string, unknown>) };
  delete wire.file_id;
  return wire;
}

/**
 * Parse wire `input_files` entries into frozen snapshots whose identity is
 * never a server-resolvable id. Display-keyed entries keep their
 * `display_key`; entries that wrongly carry a private `file_id` are
 * identity-stripped and fall back to a synthetic placeholder; names, sizes,
 * statuses and ordinals render unchanged either way.
 */
export function displayOnlySnapshots(inputFiles: unknown): readonly SessionFileSnapshot[] {
  if (!Array.isArray(inputFiles)) return Object.freeze([]);
  return snapshotsFromInputFiles(inputFiles.map(stripPrivateIdentity));
}

// ---------------------------------------------------------------------------
// Share replay payload gate
// ---------------------------------------------------------------------------

export interface ShareViewPayload {
  version: 1 | 2;
  /** The parsed react-agent payload; callers narrow the fields they render. */
  payload: Record<string, unknown>;
}

/**
 * Accept react history versions 1 and 2 for public replay. Anything else
 * (malformed JSON, non-react-agent payloads, unknown future versions)
 * yields null so the replay page can skip the message without crashing.
 */
export function parseShareViewPayload(context: unknown): ShareViewPayload | null {
  if (typeof context !== 'string' || !context) return null;
  let payload: unknown;
  try {
    payload = JSON.parse(context);
  } catch {
    return null;
  }
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) return null;
  const wire = payload as Record<string, unknown>;
  if (wire.type !== 'react-agent') return null;
  if (wire.version === 1) return { version: 1, payload: wire };
  if (wire.version === REACT_HISTORY_PAYLOAD_VERSION) {
    return { version: 2, payload: wire };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Scheduled task surfaces
// ---------------------------------------------------------------------------

/**
 * Render-model of a task payload's frozen file list
 * (`payload.ext_info.input_files`). The replay-time task-scoped
 * `ext_info.file_ids` are server-side keys and are never surfaced here;
 * legacy tasks (which carry only `file_path`) render an empty list.
 */
export function scheduledTaskFiles(extInfo: unknown): readonly SessionFileSnapshot[] {
  if (typeof extInfo !== 'object' || extInfo === null || Array.isArray(extInfo)) {
    return Object.freeze([]);
  }
  return displayOnlySnapshots((extInfo as Record<string, unknown>).input_files);
}

/**
 * Display-only label for a legacy task's `ext_info.file_path`: just the
 * basename. The full server path is never rendered into a URL, link or
 * download affordance. Malformed values yield null so the row can hide.
 */
export function legacyFilePathDisplayName(filePath: unknown): string | null {
  if (typeof filePath !== 'string' || !filePath.trim()) return null;
  const segments = filePath.split(/[\\/]+/).filter(segment => segment.length > 0);
  return segments.length > 0 ? segments[segments.length - 1] : null;
}
