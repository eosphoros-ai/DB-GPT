/**
 * Pure reducer for session-file drafts.
 *
 * Validation, upload, and preview are orthogonal sub-states:
 * a validation failure blocks queueing, an upload failure hard-blocks
 * sending, and a preview failure is only a soft warning.
 */

import type {
  CapabilitiesSource,
  DraftFile,
  LegacyServerFile,
  SessionFileSnapshot,
  SessionFilesSendSnapshot,
  UploadCapabilities,
} from './types';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { DEFAULT_UPLOAD_CAPABILITIES } from './types.ts';

export interface SessionFilesState {
  sessionId: string | null;
  files: DraftFile[];
  capabilities: UploadCapabilities | null;
  capabilitiesSource: CapabilitiesSource;
  /**
   * Legacy server-preloaded file (example cards). Mutually exclusive with
   * `files`: the legacy file_path protocol never mixes with session file_ids.
   */
  legacyFile: LegacyServerFile | null;
}

export const initialSessionFilesState = (): SessionFilesState => ({
  sessionId: null,
  files: [],
  capabilities: null,
  capabilitiesSource: 'fallback',
  legacyFile: null,
});

export interface AddInput {
  clientId: string;
  file: File;
}

export type SessionFilesAction =
  | { type: 'bind_session'; sessionId: string }
  | {
      type: 'capabilities';
      capabilities: UploadCapabilities;
      source: CapabilitiesSource;
    }
  | { type: 'add'; inputs: AddInput[] }
  | { type: 'remove'; clientId: string }
  | { type: 'upload_start'; clientId: string; attempt: number }
  | { type: 'upload_progress'; clientId: string; attempt: number; progress: number }
  | {
      type: 'upload_done';
      clientId: string;
      attempt: number;
      snapshot: SessionFileSnapshot;
    }
  | { type: 'upload_failed'; clientId: string; attempt: number; error: string }
  | { type: 'upload_cancelled'; clientId: string; attempt: number }
  | { type: 'retry'; clientId: string }
  | { type: 'preview_start'; clientId: string }
  | { type: 'preview_ready'; clientId: string }
  | { type: 'preview_failed'; clientId: string; error: string }
  | { type: 'rehydrate'; sessionId: string; snapshots: SessionFileSnapshot[] }
  | { type: 'set_legacy'; file: LegacyServerFile }
  | { type: 'clear_legacy' }
  | { type: 'clear_turn' }
  | { type: 'reset_session' };

export const identityOf = (file: File): { name: string; size: number; lastModified: number } => ({
  name: file.name,
  size: file.size,
  lastModified: file.lastModified,
});

const identityKey = (identity: { name: string; size: number; lastModified: number }): string =>
  `${identity.name}::${identity.size}::${identity.lastModified}`;

const makeDraft = (clientId: string, file: File): DraftFile => ({
  clientId,
  file,
  identity: identityOf(file),
  validation: { status: 'ok', error: null },
  upload: { status: 'queued', progress: 0, attempt: 0, error: null },
  preview: { status: 'idle', error: null },
  snapshot: null,
});

const snapshotToDraft = (snapshot: SessionFileSnapshot): DraftFile => {
  const failed = snapshot.status === 'failed';
  return {
    clientId: `server:${snapshot.file_id}`,
    file: null,
    identity: { name: snapshot.name, size: snapshot.size, lastModified: 0 },
    validation: { status: 'ok', error: null },
    upload: {
      status: failed ? 'failed' : 'done',
      progress: failed ? 0 : 1,
      attempt: 1,
      error: failed ? (snapshot.error_code ?? 'failed') : null,
    },
    preview: {
      status: snapshot.status === 'ready' ? 'ready' : snapshot.status === 'preview_failed' ? 'preview_failed' : 'idle',
      error: snapshot.status === 'preview_failed' ? (snapshot.error_code ?? null) : null,
    },
    snapshot,
  };
};

/**
 * Plan a batch add against the current drafts and capabilities.
 * Pure: duplicates (by identity), over-count and over-byte picks become
 * invalid/blocked drafts; everything else stays queued. Order is preserved.
 */
export function planAddDrafts(args: {
  existing: readonly DraftFile[];
  files: readonly File[];
  capabilities: UploadCapabilities;
  createClientId?: () => string;
}): DraftFile[] {
  const { existing, files, capabilities } = args;
  let fallbackCounter = 0;
  const createClientId =
    args.createClientId ??
    (() =>
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `draft-${Date.now()}-${fallbackCounter++}`);

  const seen = new Set(existing.map(draft => identityKey(draft.identity)));
  let acceptedCount = existing.filter(draft => draft.validation.status === 'ok').length;
  let acceptedBytes = existing
    .filter(draft => draft.validation.status === 'ok')
    .reduce((sum, draft) => sum + draft.identity.size, 0);

  return files.map(file => {
    const draft = makeDraft(createClientId(), file);
    const key = identityKey(draft.identity);
    if (seen.has(key)) {
      draft.validation = { status: 'invalid', error: 'DUPLICATE_FILE' };
      draft.upload = { ...draft.upload, status: 'blocked' };
    } else if (file.size > capabilities.max_file_bytes) {
      draft.validation = { status: 'invalid', error: 'FILE_TOO_LARGE' };
      draft.upload = { ...draft.upload, status: 'blocked' };
    } else if (acceptedCount + 1 > capabilities.max_files_per_upload) {
      draft.validation = { status: 'invalid', error: 'TOO_MANY_FILES' };
      draft.upload = { ...draft.upload, status: 'blocked' };
    } else if (acceptedBytes + file.size > capabilities.max_upload_bytes) {
      draft.validation = { status: 'invalid', error: 'REQUEST_TOO_LARGE' };
      draft.upload = { ...draft.upload, status: 'blocked' };
    } else {
      seen.add(key);
      acceptedCount += 1;
      acceptedBytes += file.size;
    }
    return draft;
  });
}

const mapDraft = (
  state: SessionFilesState,
  clientId: string,
  fn: (draft: DraftFile) => DraftFile,
): SessionFilesState => {
  const index = state.files.findIndex(draft => draft.clientId === clientId);
  if (index < 0) return state; // Stale signal for a removed draft: ignore.
  const files = state.files.slice();
  files[index] = fn(files[index]);
  return { ...state, files };
};

export function sessionFilesReducer(state: SessionFilesState, action: SessionFilesAction): SessionFilesState {
  switch (action.type) {
    case 'bind_session':
      return { ...state, sessionId: action.sessionId };

    case 'capabilities':
      return { ...state, capabilities: action.capabilities, capabilitiesSource: action.source };

    case 'add': {
      // Legacy file_path and session file_ids are mutually exclusive: while a
      // legacy example file is staged, local picks are refused wholesale.
      if (state.legacyFile) return state;
      const capabilities = state.capabilities ?? DEFAULT_UPLOAD_CAPABILITIES;
      const planned = planAddDrafts({
        existing: state.files,
        files: action.inputs.map(input => input.file),
        capabilities,
      });
      // Caller-supplied clientIds win (planned order matches input order).
      const drafts = planned.map((draft, index) => ({
        ...draft,
        clientId: action.inputs[index]?.clientId ?? draft.clientId,
      }));
      // The reducer stays authoritative on duplicates, even if the caller
      // planned against stale state.
      const seen = new Set(state.files.map(draft => identityKey(draft.identity)));
      const accepted = drafts.filter(draft => {
        const key = identityKey(draft.identity);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      return { ...state, files: [...state.files, ...accepted] };
    }

    case 'remove':
      return { ...state, files: state.files.filter(draft => draft.clientId !== action.clientId) };

    case 'upload_start':
      return mapDraft(state, action.clientId, draft =>
        draft.upload.status !== 'queued'
          ? draft
          : patchUpload(draft, { status: 'uploading', attempt: action.attempt, progress: 0, error: null }),
      );

    case 'upload_progress':
      return mapDraft(state, action.clientId, draft =>
        draft.upload.status !== 'uploading' || draft.upload.attempt !== action.attempt
          ? draft
          : patchUpload(draft, { progress: Math.min(1, Math.max(0, action.progress)) }),
      );

    case 'upload_done':
      return mapDraft(state, action.clientId, draft =>
        draft.upload.status !== 'uploading' || draft.upload.attempt !== action.attempt
          ? draft
          : {
              ...patchUpload(draft, { status: 'done', progress: 1, error: null }),
              snapshot: action.snapshot,
            },
      );

    case 'upload_failed':
      return mapDraft(state, action.clientId, draft =>
        draft.upload.status !== 'uploading' || draft.upload.attempt !== action.attempt
          ? draft
          : patchUpload(draft, { status: 'failed', error: action.error }),
      );

    case 'upload_cancelled':
      return mapDraft(state, action.clientId, draft =>
        (draft.upload.status !== 'uploading' && draft.upload.status !== 'queued') ||
        draft.upload.attempt !== action.attempt
          ? draft
          : patchUpload(draft, { status: 'cancelled', progress: 0 }),
      );

    case 'retry':
      return mapDraft(state, action.clientId, draft =>
        draft.upload.status !== 'failed' ? draft : patchUpload(draft, { status: 'queued', progress: 0, error: null }),
      );

    case 'preview_start':
      return mapDraft(state, action.clientId, draft =>
        draft.upload.status !== 'done' ? draft : patchPreview(draft, { status: 'loading', error: null }),
      );

    case 'preview_ready':
      return mapDraft(state, action.clientId, draft =>
        draft.preview.status !== 'loading' ? draft : patchPreview(draft, { status: 'ready', error: null }),
      );

    case 'preview_failed':
      return mapDraft(state, action.clientId, draft =>
        draft.preview.status !== 'loading'
          ? draft
          : patchPreview(draft, { status: 'preview_failed', error: action.error }),
      );

    case 'rehydrate': {
      const drafts = action.snapshots
        .filter(snapshot => snapshot.status !== 'deleted')
        .slice()
        .sort((a, b) => a.ordinal - b.ordinal)
        .map(snapshotToDraft);
      return { ...state, sessionId: action.sessionId, files: drafts, legacyFile: null };
    }

    case 'set_legacy': {
      // Mutually exclusive with local drafts; re-staging is idempotent —
      // the first staged example file wins until explicitly cleared.
      if (state.files.length > 0 || state.legacyFile) return state;
      return { ...state, legacyFile: { ...action.file } };
    }

    case 'clear_legacy':
      return { ...state, legacyFile: null };

    case 'clear_turn':
      return { ...state, files: [], legacyFile: null };

    case 'reset_session':
      return { ...state, sessionId: null, files: [], legacyFile: null };

    default:
      return state;
  }
}

const patchUpload = (draft: DraftFile, patch: Partial<DraftFile['upload']>): DraftFile => ({
  ...draft,
  upload: { ...draft.upload, ...patch },
});

const patchPreview = (draft: DraftFile, patch: Partial<DraftFile['preview']>): DraftFile => ({
  ...draft,
  preview: { ...draft.preview, ...patch },
});

/** Upload failures are the only hard gate for sending. */
export function hasHardFailures(state: SessionFilesState): boolean {
  return state.files.some(draft => draft.upload.status === 'failed');
}

/**
 * Build the immutable, insertion-ordered send snapshot.
 * Throws when any draft has a hard (upload) failure. A staged legacy file is
 * carried through so the send path can resend it via the legacy file_path
 * protocol; the reducer's mixing guards already keep legacy and drafts
 * mutually exclusive, so the two never appear together here.
 */
export function buildSendSnapshot(state: SessionFilesState, sessionId: string): SessionFilesSendSnapshot {
  const failed = state.files.filter(draft => draft.upload.status === 'failed');
  if (failed.length > 0) {
    const names = failed.map(draft => draft.identity.name).join(', ');
    throw new Error(`SESSION_FILES_HARD_FAILURE: resolve failed uploads before send (${names})`);
  }
  const uploaded = state.files.filter(
    (draft): draft is DraftFile & { snapshot: SessionFileSnapshot } => draft.snapshot !== null,
  );
  const fileIds = Object.freeze(uploaded.map(draft => draft.snapshot.file_id));
  const snapshotById = Object.freeze(
    Object.fromEntries(uploaded.map(draft => [draft.snapshot.file_id, Object.freeze({ ...draft.snapshot })])),
  );
  const legacyFile = state.legacyFile ? Object.freeze({ ...state.legacyFile }) : null;
  return Object.freeze({ sessionId, fileIds, snapshotById, legacyFile });
}
