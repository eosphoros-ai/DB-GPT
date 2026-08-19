/**
 * Server adapter for /api/v1/agent/files.
 *
 * This module is the only place that talks HTTP; it reuses the shared
 * authenticated axios client from client/api (User-Id header is injected by
 * that client's request interceptor — no Authorization handling here) and in
 * the project's existing Result-envelope style
 * (`AxiosResponse<ResponseType<T>>`) rather than introducing a new idiom.
 *
 * The session-files orchestration interacts with the network exclusively
 * through the `SessionFilesApi` interface in types.ts, so this adapter is a
 * drop-in and stays out of the node test path (tests use a fake adapter).
 *
 * Endpoint reference (packages/dbgpt-serve/.../session_file/api/endpoints.py):
 *   POST   /api/v1/agent/files                      -> Result<SessionFileResponse[]>
 *   GET    /api/v1/agent/files?session_id=          -> Result<SessionFileResponse[]>
 *   GET    /api/v1/agent/files/capabilities         -> Result<SessionFileCapabilitiesResponse>
 *   GET    /api/v1/agent/files/{file_id}/preview    -> Result<SessionFilePreviewResponse>
 *   DELETE /api/v1/agent/files/{file_id}?session_id= -> Result<{ file_id }>
 */

import type { ApiResponse } from '../../client/api';
import { DELETE, GET, POST } from '../../client/api';

import type {
  CapabilitiesResult,
  SessionFilePreviewSnapshot,
  SessionFileSnapshot,
  SessionFilesApi,
  UploadCapabilities,
} from './types';
// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import { DEFAULT_UPLOAD_CAPABILITIES } from './types.ts';

const BASE = '/api/v1/agent/files';

/** Domain error carrying the backend's stable error code when present. */
export class SessionFilesApiError extends Error {
  readonly errCode: string | null;
  readonly statusCode?: number;

  constructor(message: string, errCode: string | null = null, statusCode?: number) {
    super(message);
    this.name = 'SessionFilesApiError';
    this.errCode = errCode;
    this.statusCode = statusCode;
  }
}

/** Unwrap the Result envelope, matching the existing style of client/api consumers. */
function unwrap<T>(response: ApiResponse<T>): T {
  const envelope = response?.data;
  if (!envelope || envelope.success !== true) {
    throw new SessionFilesApiError(envelope?.err_msg ?? 'Session file request failed.', envelope?.err_code ?? null);
  }
  return envelope.data;
}

/**
 * Upload 1..N files for a session in one multipart request
 * (form fields: `session_id`, repeated `files`). The orchestrator calls this
 * per draft so a single failure never implicates sibling uploads.
 */
export async function uploadFiles(params: {
  sessionId: string;
  files: readonly File[];
  signal?: AbortSignal;
  onProgress?: (ratio: number) => void;
  timeoutMs?: number;
}): Promise<SessionFileSnapshot[]> {
  const form = new FormData();
  form.append('session_id', params.sessionId);
  for (const file of params.files) {
    form.append('files', file, file.name);
  }
  const response = await POST<FormData, SessionFileSnapshot[]>(BASE, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    signal: params.signal,
    timeout: params.timeoutMs ?? 180000,
    onUploadProgress: event => {
      if (params.onProgress && event.total) {
        params.onProgress(Math.min(1, event.loaded / event.total));
      }
    },
  });
  return unwrap<SessionFileSnapshot[]>(response);
}

/** List the session's files in stable upload order. */
export async function listFiles(sessionId: string): Promise<SessionFileSnapshot[]> {
  const response = await GET<{ session_id: string }, SessionFileSnapshot[]>(BASE, {
    session_id: sessionId,
  });
  return unwrap<SessionFileSnapshot[]>(response);
}

/** Delete one file within the session scope. */
export async function deleteFile(sessionId: string, fileId: string): Promise<void> {
  const response = await DELETE<{ session_id: string }, { file_id: string }>(`${BASE}/${encodeURIComponent(fileId)}`, {
    session_id: sessionId,
  });
  unwrap<{ file_id: string }>(response);
}

/**
 * Server-owned upload limits. Falls back to conservative defaults when the
 * endpoint is unreachable, but keeps source='fallback' (plus the error) so
 * callers can honor the server when it comes back.
 */
export async function fetchCapabilities(): Promise<CapabilitiesResult> {
  try {
    const response = await GET<{ session_id?: string }, UploadCapabilities>(`${BASE}/capabilities`);
    return { capabilities: unwrap<UploadCapabilities>(response), source: 'server' };
  } catch (error) {
    return { capabilities: DEFAULT_UPLOAD_CAPABILITIES, source: 'fallback', error };
  }
}

/** Preview payload for an uploaded file. Adapter seam kept ready for Task follow-ups. */
export async function previewFile(sessionId: string, fileId: string): Promise<SessionFilePreviewSnapshot> {
  const response = await GET<{ session_id: string }, SessionFilePreviewSnapshot>(
    `${BASE}/${encodeURIComponent(fileId)}/preview`,
    { session_id: sessionId },
  );
  return unwrap<SessionFilePreviewSnapshot>(response);
}

/** Default adapter instance for wiring into useSessionFiles({ api }). */
export const sessionFilesApi: SessionFilesApi = {
  uploadFiles,
  listFiles,
  deleteFile,
  fetchCapabilities,
  previewFile,
};
