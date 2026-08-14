/**
 * Home-page adapter for the session-files module.
 *
 * Pure, network-free bridge between the chat wire payloads and the module's
 * UI contract:
 *
 * - history payload v2 `input_files` → frozen `SessionFileSnapshot[]` (one
 *   entry per file attached to a turn). Owner-side history carries the real
 *   `file_id`; public share pages and frozen scheduled-task snapshots carry
 *   the non-resolvable `display_key` instead, and this module never invents a
 *   usable server id;
 * - legacy v1 history carries no file snapshot: parsing a v1 payload returns
 *   an empty list, so those messages render without attachment cards;
 * - legacy example files (preloaded on the server via `/api/v1/examples/use`)
 *   are staged as frozen `LegacyServerFile`s on the send snapshot and resent
 *   verbatim through the legacy `file_path` protocol. `snapshotFromLegacyFile`
 *   renders them display-only and `extInfoForSend` refuses to mix them with
 *   session `file_ids`;
 * - the send-path ext_info builder is regression-safe: with zero files it
 *   reproduces the legacy file_path / plain-text payload byte-for-byte (no
 *   `file_ids`/`session_id` keys appear).
 */

import type { LegacyServerFile, SessionFileSnapshot, SessionFileStatus, SessionFilesSendSnapshot } from './types';

/** History payload version carrying the public `input_files` snapshot. */
export const REACT_HISTORY_PAYLOAD_VERSION = 2;

const SESSION_FILE_STATUSES: readonly SessionFileStatus[] = [
  'uploading',
  'inspecting',
  'ready',
  'preview_failed',
  'failed',
  'deleted',
];

function toSnapshot(entry: unknown, index: number): SessionFileSnapshot | null {
  if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) return null;
  const wire = entry as Record<string, unknown>;

  const name = wire.name;
  if (typeof name !== 'string' || !name) return null;

  // Owner history carries the real file_id; share-scrubbed and frozen-task
  // entries carry the non-resolvable display_key. When both are missing a
  // synthesised ordinal key keeps rendering deterministic without ever
  // resembling a usable server id.
  const rawId = wire.file_id ?? wire.display_key;
  const fileId = typeof rawId === 'string' && rawId ? rawId : `anonymous-attachment-${index + 1}`;

  const size = typeof wire.size === 'number' && Number.isFinite(wire.size) && wire.size >= 0 ? wire.size : 0;
  const status =
    typeof wire.status === 'string' && (SESSION_FILE_STATUSES as readonly string[]).includes(wire.status)
      ? (wire.status as SessionFileStatus)
      : 'ready';
  return Object.freeze({
    file_id: fileId,
    name,
    size,
    media_type: typeof wire.media_type === 'string' ? wire.media_type : '',
    kind: typeof wire.kind === 'string' ? wire.kind : '',
    status,
    ordinal: Number.isInteger(wire.ordinal) ? (wire.ordinal as number) : index,
    error_code: typeof wire.error_code === 'string' ? wire.error_code : null,
  });
}

/**
 * Parse the public `input_files` snapshot of a history payload v2 (or an
 * `ext_info.input_files` task freeze list) into frozen snapshots. Anything
 * invalid degrades safely: non-arrays yield an empty list and malformed
 * entries are skipped, so a corrupt payload can never break the page.
 */
export function snapshotsFromInputFiles(inputFiles: unknown): readonly SessionFileSnapshot[] {
  if (!Array.isArray(inputFiles)) return Object.freeze([]);
  const snapshots: SessionFileSnapshot[] = [];
  inputFiles.forEach((entry, index) => {
    const snapshot = toSnapshot(entry, index);
    if (snapshot) snapshots.push(snapshot);
  });
  return Object.freeze(snapshots);
}

/** Files attached to one human turn, as restored from a view payload. */
export interface ViewContextFiles {
  version: 1 | 2;
  inputFiles: readonly SessionFileSnapshot[];
}

/**
 * Read the files attached to a turn from a view (react-agent) history
 * payload. v1 predates file snapshots, so it returns an empty list and
 * those messages render without attachment cards. Non-JSON payloads and
 * non-react-agent contexts return null.
 */
export function parseViewContextFiles(context: unknown): ViewContextFiles | null {
  if (typeof context !== 'string' || !context) return null;
  let payload: unknown;
  try {
    payload = JSON.parse(context);
  } catch {
    return null;
  }
  if (typeof payload !== 'object' || payload === null) return null;
  const wire = payload as Record<string, unknown>;
  if (wire.type !== 'react-agent') return null;
  if (wire.version === 1) return { version: 1, inputFiles: Object.freeze([]) };
  if (wire.version === REACT_HISTORY_PAYLOAD_VERSION) {
    return { version: 2, inputFiles: snapshotsFromInputFiles(wire.input_files) };
  }
  return null;
}

/**
 * Minimal public back-compat form of the legacy one-item attachment that used
 * to be declared as `FileAttachment` inside pages/index.tsx. Provided here so
 * all legacy-file handling flows through this adapter seam.
 */
export interface LegacyAttachedFile {
  name: string;
  size: number;
  type: string;
}

/**
 * Render a legacy file (FileAttachment / staged example file) as a
 * display-only snapshot. The `legacy:` identity is non-resolvable by design
 * and the server-side `file_path` is never surfaced, so nothing built from
 * this snapshot can reach the file endpoints.
 */
export function snapshotFromLegacyFile(file: LegacyAttachedFile): SessionFileSnapshot {
  return Object.freeze({
    file_id: `legacy:${file.name}`,
    name: file.name,
    size: file.size,
    media_type: file.type,
    kind: '',
    status: 'ready',
    ordinal: 0,
    error_code: null,
  });
}

/**
 * Return a copy of a send snapshot with a legacy example file staged. The
 * caller guarantees the mutual exclusion (no `fileIds` while a legacy file is
 * present); `extInfoForSend` still re-checks before building the payload.
 */
export function snapshotWithLegacyFile(
  snapshot: SessionFilesSendSnapshot,
  file: LegacyServerFile,
): SessionFilesSendSnapshot {
  return Object.freeze({ ...snapshot, legacyFile: Object.freeze({ ...file }) });
}

/** Display snapshots attached to the sent human message, in send order. */
export function snapshotsForSend(snapshot: SessionFilesSendSnapshot): readonly SessionFileSnapshot[] {
  const attachments = snapshot.fileIds.map(fileId => snapshot.snapshotById[fileId]);
  const legacy = snapshot.legacyFile;
  if (legacy) {
    // The mixing guard in extInfoForSend keeps `attachments` empty here, so
    // the legacy card is the only attachment appended.
    attachments.push(snapshotFromLegacyFile({ name: legacy.name, size: legacy.size, type: legacy.media_type }));
  }
  return Object.freeze(attachments);
}

/**
 * Build the send-time ext_info. Zero files reproduce the legacy payload
 * exactly (no `file_ids`/`session_id` keys), preserving the byte-for-byte
 * file_path / plain-text regression contract. With files it adds:
 *
 * - `file_ids`: ordered ids from the frozen send snapshot (the backend
 *   conflicts check forbids combining this with `file_path`, which the caller
 *   therefore only emits on the legacy path);
 * - `session_id`: the owning conversation id, required so a later
 *   "save as scheduled task" can freeze these session-scoped files;
 * - `input_files`: display-safe snapshots in the exact share-scrub shape
 *   (`display_key` + public metadata, never a resolvable id or path), so the
 *   scheduled-task surfaces can render what will be frozen.
 *
 * A staged legacy example file instead adds only `file_path`; mixing it with
 * `file_ids` throws SESSION_FILES_MIXED_PROTOCOL before any payload is built.
 */
export function extInfoForSend(
  base: Record<string, any> | null | undefined,
  snapshot: SessionFilesSendSnapshot | null | undefined,
): Record<string, any> {
  const safeBase: Record<string, any> = base ?? {};
  if (!snapshot) {
    return { ...safeBase };
  }
  const legacy = snapshot.legacyFile ?? null;
  if (legacy) {
    if (snapshot.fileIds.length > 0) {
      throw new Error('SESSION_FILES_MIXED_PROTOCOL: legacy file_path cannot be combined with session file_ids');
    }
    return { ...safeBase, file_path: legacy.file_path };
  }
  if (snapshot.fileIds.length === 0) {
    return { ...safeBase };
  }
  return {
    ...safeBase,
    file_ids: [...snapshot.fileIds],
    session_id: snapshot.sessionId,
    input_files: snapshot.fileIds.map((fileId, index) => {
      const file = snapshot.snapshotById[fileId];
      return {
        display_key: `file-${index + 1}`,
        name: file.name,
        size: file.size,
        media_type: file.media_type,
        kind: file.kind,
        status: file.status,
        ordinal: file.ordinal,
      };
    }),
  };
}
