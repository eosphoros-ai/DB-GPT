/**
 * Public API of the session-files module.
 *
 * Everything outside this directory must import from `@/modules/session-files`
 * (this barrel) rather than deep paths. Files not re-exported here —
 * `reducer.ts`, `upload-queue.ts` — are private implementation details and may
 * be reorganized without notice.
 */

// UI components
export { default as AttachmentMessageCards } from './AttachmentMessageCards';
export { default as AttachmentMessageGroup } from './AttachmentMessageGroup';
export {
  ATTACHMENT_PREVIEW_DRAWER_STYLES,
  default as AttachmentPreview,
  AttachmentPreviewCloseButton,
  AttachmentPreviewPanelTitle,
} from './AttachmentPreview';
export type { AttachmentPreviewProps } from './AttachmentPreview';
export { default as AttachmentRail, AttachmentRailAddButton, AttachmentRailCompactAddButton } from './AttachmentRail';
export type { AttachmentRailProps } from './AttachmentRail';

// State orchestration hook
export { useSessionFiles } from './use-session-files';
export type { StageLegacyForSendResult, UseSessionFiles, UseSessionFilesOptions } from './use-session-files';

// API seam
export { SessionFilesApiError, previewFile, sessionFilesApi } from './api';

// View-model + page adapters
export type { RailPreviewState } from './AttachmentRail';
export {
  PREVIEW_DESKTOP_MIN_WIDTH,
  PREVIEW_DRAWER_MAX_WIDTH,
  PREVIEW_FULLSCREEN_MAX_WIDTH,
} from './attachment-view-model';
export type { RailItem } from './attachment-view-model';
export { extInfoForSend, snapshotsForSend, snapshotsFromInputFiles } from './home-adapter';
export { displayOnlySnapshots, legacyFilePathDisplayName, parseShareViewPayload, scheduledTaskFiles } from './recovery';
export type { ShareViewPayload } from './recovery';

// Wire types + server-driven constants
export { DEFAULT_UPLOAD_CAPABILITIES } from './types';
export type {
  CapabilitiesResult,
  CapabilitiesSource,
  DraftFile,
  LegacyServerFile,
  SessionFilePreviewSnapshot,
  SessionFileSnapshot,
  SessionFileStatus,
  SessionFilesApi,
  SessionFilesSendSnapshot,
  UploadCapabilities,
} from './types';
