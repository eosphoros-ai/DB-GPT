/**
 * Expert-suite (scenario suite) types mirrored from the backend registry
 * (`GET /api/v1/suites`, dbgpt_serve/plugins).  The manifest_snapshot is a
 * derived, rebuildable projection of suite.yaml — never the SOP body.
 */
export interface SuiteManifestSnapshot {
  display?: string;
  display_en?: string;
  icon?: string;
  scenario_id?: string;
  execution?: string;
  description?: string;
  routing?: {
    keywords?: string[];
    specificity?: number;
  };
  recommended_questions?: { text: string; hint?: string }[];
  commands?: { name: string; description?: string }[];
  tools?: { allow?: string[]; deny?: string[] };
  artifacts?: string[];
  context_defaults?: Record<string, any>;
  semantic?: Record<string, any>;
  output_contract?: string;
  skills?: string[];
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
  use_count?: number;
  user_name?: string | null;
}
