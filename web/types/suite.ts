/** Display snapshot of the suite and shortcut attached to one sent message. */
export interface SuiteMessageReference {
  name: string;
  display: string;
  command?: string;
}

export interface SuiteRecommendedQuestion {
  text: string;
  text_en?: string;
  /** Short display title for the inline composer prefix. */
  title?: string;
  title_en?: string;
  hint?: string;
  hint_en?: string;
  /** Named example database; omitted questions use the selected session database. */
  database_name?: string;
  command?: string;
}

export interface SuiteCommand {
  name: string;
  /** Translated label only; requests always use name. */
  display_en?: string;
  display?: string;
  aliases?: string[];
  description?: string;
  description_en?: string;
  summary?: string;
  skill?: string;
  example?: string;
  prefill?: string;
  prefill_en?: string;
}

export interface SuiteSkill {
  name: string;
  display?: string;
  display_en?: string;
  description?: string;
  description_en?: string;
  user_invocable?: boolean;
}

/**
 * Expert-suite (scenario suite) types mirrored from the backend registry
 * (`GET /api/v1/suites`, dbgpt_serve/plugins).  The manifest_snapshot is a
 * derived, rebuildable projection of plugin.json or legacy suite.yaml.
 * It never contains the SOP body.
 */
export interface SuiteManifestSnapshot {
  package_format?: 'qwenwork-plugin' | 'scenario-suite';
  display?: string;
  display_en?: string;
  icon?: string;
  scenario_id?: string;
  execution?: string;
  description?: string;
  description_en?: string;
  routing?: {
    keywords?: string[];
    specificity?: number;
  };
  recommended_questions?: SuiteRecommendedQuestion[];
  commands?: SuiteCommand[];
  tools?: { allow?: string[]; deny?: string[] };
  artifacts?: string[];
  context_defaults?: Record<string, any>;
  semantic?: Record<string, any>;
  output_contract?: string;
  skills?: string[];
  skill_details?: SuiteSkill[];
}

export interface SuiteItem {
  id: number;
  name: string;
  display?: string;
  icon?: string;
  scenario_id?: string;
  version: string;
  source: 'official' | 'enterprise' | 'market' | string;
  execution?: string;
  status: 'installed' | 'enabled' | 'disabled' | string;
  workspace_id?: string | null;
  package_path?: string;
  package_digest?: string;
  manifest_snapshot?: SuiteManifestSnapshot;
  readme?: string | null;
  readme_locales?: Record<string, string> | null;
  skill_details?: SuiteSkill[] | null;
  use_count?: number;
  user_name?: string | null;
}
