/** Shared edit-source label mapping (zh-first, i18n key based). */
export const EDIT_SOURCE_LABELS: Record<string, { key: string; antdColor: string }> = {
  pipeline: { key: 'wiki_source_pipeline', antdColor: 'default' },
  agent: { key: 'wiki_source_agent', antdColor: 'purple' },
  user: { key: 'wiki_source_user', antdColor: 'cyan' },
  revert: { key: 'wiki_source_revert', antdColor: 'volcano' },
};
