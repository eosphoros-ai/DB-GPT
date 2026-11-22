import type { SuiteItem } from '@/types/suite';

export type SuiteCategory = 'all' | 'query' | 'analysis' | 'financial' | 'metadata' | 'ops' | 'other';
export type SuiteSourceFilter = 'official' | 'enterprise' | 'installed' | 'market';

const builtins: Record<string, { title: string; description: string; category: SuiteCategory }> = {
  'db-analysis': { title: 'plugins_name_analysis', description: 'plugins_desc_analysis', category: 'analysis' },
  'db-query': { title: 'plugins_name_query', description: 'plugins_desc_query', category: 'query' },
  'financial-analysis': {
    title: 'plugins_name_financial',
    description: 'plugins_desc_financial',
    category: 'financial',
  },
  'metadata-architecture-expert': {
    title: 'plugins_name_metadata',
    description: 'plugins_desc_metadata',
    category: 'metadata',
  },
  'sql-optimization-expert': { title: 'plugins_name_sql', description: 'plugins_desc_sql', category: 'ops' },
};

export function getBuiltinPresentation(suite: SuiteItem) {
  return suite.source === 'official' ? builtins[suite.name] : undefined;
}

export function getSuiteCategory(suite: SuiteItem): SuiteCategory {
  const builtin = getBuiltinPresentation(suite);
  if (builtin) return builtin.category;
  const scenario = suite.scenario_id || suite.manifest_snapshot?.scenario_id;
  return ['query', 'analysis', 'financial', 'metadata', 'ops'].includes(scenario || '')
    ? (scenario as SuiteCategory)
    : 'other';
}

export function isInstalledSuite(suite: SuiteItem): boolean {
  return ['installed', 'enabled', 'disabled'].includes(suite.status);
}

export function matchesSuiteSource(suite: SuiteItem, filter: SuiteSourceFilter): boolean {
  return filter === 'installed' ? isInstalledSuite(suite) : suite.source === filter;
}

const artifactLabels: Record<string, string> = {
  dataset_card: 'plugins_artifact_dataset',
  chart: 'plugins_artifact_chart',
  conclusion_card: 'plugins_artifact_conclusion',
  report: 'plugins_artifact_report',
  dashboard: 'plugins_artifact_dashboard',
  citation: 'plugins_artifact_citation',
  sql_card: 'plugins_artifact_sql',
  result_table: 'plugins_artifact_table',
  financial_report: 'plugins_artifact_financial',
};

export function artifactPresentation(
  artifact: NonNullable<NonNullable<SuiteItem['manifest_snapshot']>['artifacts']>[number],
  language: string,
): { label: string; translationKey?: string } {
  if (typeof artifact === 'string') return { label: artifact, translationKey: artifactLabels[artifact] };
  return {
    label: (language.toLowerCase().startsWith('en') && artifact.name_en) || artifact.name || artifact.type,
  };
}
