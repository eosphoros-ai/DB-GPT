/**
 * Types for the session-files module.
 *
 * Wire types mirror the backend contract of dbgpt_serve.session_file:
 * - SessionFileResponse (packages/dbgpt-serve/.../api/schemas.py)
 * - SessionFileCapabilitiesResponse / SessionFilePreviewResponse
 * Local draft types model the client-side upload/preview state machines,
 * which are orthogonal by design.
 */

/** Backend lifecycle status (dbgpt_serve.session_file.domain.SessionFileStatus). */
export type SessionFileStatus = 'uploading' | 'inspecting' | 'ready' | 'preview_failed' | 'failed' | 'deleted';

/** Backend snapshot of one session file (SessionFileResponse). */
export interface SessionFileSnapshot {
  file_id: string;
  name: string;
  size: number;
  media_type: string;
  kind: string;
  status: SessionFileStatus;
  /** Upload order within the scope. */
  ordinal: number;
  error_code?: string | null;
}

/** Backend preview payload (SessionFilePreviewResponse); adapter only. */
export interface SessionFilePreviewSnapshot {
  file_id: string;
  name: string;
  media_type: string;
  kind: string;
  status: SessionFileStatus;
  truncated: boolean;
  preview: Record<string, unknown>;
  error_code?: string | null;
}

/** Server-owned upload limits (SessionFileCapabilitiesResponse). */
export interface UploadCapabilities {
  max_files_per_upload: number;
  max_file_bytes: number;
  max_upload_bytes: number;
  max_owner_bytes: number;
  upload_request_timeout_seconds: number;
  upload_concurrency: number;
  supported_extensions: string[];
}

/** Conservative defaults mirroring ServeConfig; used when /capabilities is unreachable. */
export const DEFAULT_UPLOAD_CAPABILITIES: UploadCapabilities = {
  max_files_per_upload: 20,
  max_file_bytes: 100 * 1024 * 1024,
  max_upload_bytes: 500 * 1024 * 1024,
  max_owner_bytes: 1024 * 1024 * 1024,
  upload_request_timeout_seconds: 180,
  upload_concurrency: 3,
  supported_extensions: [
    '.csv',
    '.tsv',
    '.xls',
    '.xlsx',
    '.json',
    '.jsonl',
    '.parquet',
    '.pdf',
    '.doc',
    '.docx',
    '.pptx',
    '.md',
    '.txt',
  ],
};

export type CapabilitiesSource = 'server' | 'fallback';

export interface CapabilitiesResult {
  capabilities: UploadCapabilities;
  source: CapabilitiesSource;
  /** Present when the server could not be honored and defaults were used. */
  error?: unknown;
}

/** Adapter seam implemented by api.ts; injected into the hook for testability. */
export interface SessionFilesApi {
  uploadFiles(params: {
    sessionId: string;
    files: readonly File[];
    signal?: AbortSignal;
    onProgress?: (ratio: number) => void;
    timeoutMs?: number;
  }): Promise<SessionFileSnapshot[]>;
  listFiles(sessionId: string): Promise<SessionFileSnapshot[]>;
  deleteFile(sessionId: string, fileId: string): Promise<void>;
  fetchCapabilities(): Promise<CapabilitiesResult>;
  /** Optional: preview endpoints exist server-side; the adapter keeps the seam ready. */
  previewFile?(sessionId: string, fileId: string): Promise<SessionFilePreviewSnapshot>;
}

/** Identity used to detect duplicate local picks. */
export interface FileIdentity {
  name: string;
  size: number;
  lastModified: number;
}

/** Client-side upload state machine (orthogonal to validation and preview). */
export type UploadPhase =
  | 'queued'
  | 'uploading'
  | 'done'
  | 'failed'
  | 'cancelled'
  /** Validation rejected the file; it never enters the upload queue. */
  | 'blocked';

/** Client-side preview state machine (orthogonal to upload). */
export type PreviewPhase = 'idle' | 'loading' | 'ready' | 'preview_failed';

export type ValidationStatus = 'ok' | 'invalid';

export interface DraftFile {
  /** Stable client-side id; kept across retries. */
  clientId: string;
  /** Local bytes; null for drafts rehydrated from the server list. */
  file: File | null;
  identity: FileIdentity;
  validation: { status: ValidationStatus; error: string | null };
  upload: {
    status: UploadPhase;
    /** 0..1 */
    progress: number;
    /** Monotonic per-draft attempt token; stale completions carry an old token. */
    attempt: number;
    error: string | null;
  };
  preview: { status: PreviewPhase; error: string | null };
  /** Server snapshot once uploaded (or rehydrated). */
  snapshot: SessionFileSnapshot | null;
}

/**
 * Legacy server-side file preloaded by an example card. The file already
 * exists on the server (identified only by its path), so it is displayed
 * read-only in the composer rail and resent verbatim via the legacy
 * `ext_info.file_path` protocol — mutually exclusive with `file_ids`.
 */
export interface LegacyServerFile {
  name: string;
  size: number;
  media_type: string;
  /** Server-side path echoed back as ext_info.file_path (legacy protocol). */
  file_path: string;
}

/** Immutable, ordered payload handed to the send flow. */
export interface SessionFilesSendSnapshot {
  readonly sessionId: string;
  readonly fileIds: readonly string[];
  readonly snapshotById: Readonly<Record<string, SessionFileSnapshot>>;
  /** Legacy staged file for this send; mutually exclusive with `fileIds`. */
  readonly legacyFile?: LegacyServerFile | null;
}
