import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import { AVAILABLE_CATALOG, GALLERY_DESIGN_SKILL_IDS } from './dashboard-catalog';
import { dashboardText as dt } from './dashboard-i18n';

/** These helpers are loaded by the dashboard workflow, not chosen as chat tasks. */
export const DASHBOARD_INTERNAL_SKILLS = new Set([
  'dashboard-design',
  ...Object.keys(ADAPTED_SKILLS),
  'dashboard-chart-configuration',
  'dashboard-filter-configuration',
  'dashboard-collaboration',
]);

export function dashboardTemplatePrompt(name: string) {
  return `${dt(ADAPTED_SKILLS[name].prompt)} ${dt('请根据实际字段调整指标，保留所选模板的布局与配色；先展示计划，确认后再生成看板。')}`;
}

/** Resolve gallery links without executing a request before the user selects data. */
export function dashboardTemplateEntry(query: Record<string, string | string[] | undefined>) {
  if (query.creation_mode !== 'dashboard') return null;
  const template = AVAILABLE_CATALOG.find(item => item.id === query.template);
  if (template) {
    return {
      name: 'dashboard-builder',
      selection: `catalog:${template.id}`,
      title: template.title,
      prompt: dt(template.prompt),
    };
  }
  const name = query.skill;
  if (typeof name !== 'string' || !GALLERY_DESIGN_SKILL_IDS.has(name)) {
    return null;
  }
  const design = ADAPTED_SKILLS[name];
  return {
    name,
    selection: `design:${name}`,
    title: design.title,
    prompt:
      typeof query.skill_prompt === 'string' && query.skill_prompt.trim()
        ? query.skill_prompt
        : dashboardTemplatePrompt(name),
  };
}
