import definitions from './dashboard-template-definitions.json';
import release from './dashboard-verified-release.json';
import type { TemplatePreviewData } from './DashboardTemplatePreview';

export type CreationMode = 'analysis' | 'dashboard' | 'files' | 'skill';
export const CREATION_MODES: { id: CreationMode; label: string; placeholder: string }[] = [
  { id: 'analysis', label: '智能分析', placeholder: '描述你想分析的问题，或选择数据库开始…' },
  { id: 'dashboard', label: '数据看板', placeholder: '选择数据库，描述你需要的指标、趋势与看板…' },
  { id: 'files', label: '文件分析', placeholder: '上传 CSV、Excel 等文件，描述你想了解的内容…' },
  { id: 'skill', label: '技能', placeholder: '选择一个技能，再输入需要完成的任务…' },
];

export interface CatalogTemplate {
  id: string;
  title: string;
  category: string;
  description: string;
  sourceNames: string[];
  prompt: string;
  style?: string;
}

// Retire gallery entries only. Existing saved dashboards and their sources remain usable.
export const RETIRED_TEMPLATE_IDS = new Set(['cardio-journal', 'olist-orders']);
export const CATALOG_CANDIDATES: CatalogTemplate[] = definitions.filter(item => !RETIRED_TEMPLATE_IDS.has(item.id));

interface VerifiedTemplate {
  id: string;
  source: string;
  dashboardId: string;
  revision: number;
  evidence: string;
  preview?: string;
  previewData?: TemplatePreviewData;
}
interface VerifiedMode {
  id: CreationMode;
  evidence: string;
}
const verifiedTemplates = release.templates as VerifiedTemplate[];
const verifiedModes = release.modes as VerifiedMode[];
// Only a separate local acceptance build exposes candidates. Release builds
// have no query-string or localStorage override for unverified capabilities.
export const LAYOUT_ACCEPTANCE_BUILD = process.env.NEXT_PUBLIC_LAYOUT_ACCEPTANCE === '1';
export const AVAILABLE_CREATION_MODES = CREATION_MODES.filter(
  mode => LAYOUT_ACCEPTANCE_BUILD || verifiedModes.some(proof => proof.id === mode.id && proof.evidence),
);
export const AVAILABLE_CATALOG = CATALOG_CANDIDATES.filter(
  template =>
    LAYOUT_ACCEPTANCE_BUILD ||
    verifiedTemplates.some(
      proof =>
        proof.id === template.id &&
        proof.source &&
        proof.dashboardId &&
        proof.evidence &&
        (proof.preview || proof.previewData),
    ),
);
export const TEMPLATE_GALLERY_ENABLED = AVAILABLE_CATALOG.length >= 2;
export const catalogProof = (id: string) => verifiedTemplates.find(proof => proof.id === id);
