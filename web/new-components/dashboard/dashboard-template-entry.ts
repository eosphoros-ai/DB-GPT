import { ADAPTED_SKILLS } from '@/new-components/skills/skill-catalog';
import { dashboardText as dt } from './dashboard-i18n';

export function dashboardTemplatePrompt(name: string) {
  return `${dt(ADAPTED_SKILLS[name].prompt)} ${dt('请加载 {{name}} 技能作为视觉参考，并按 dashboard-builder 工作流创建原生可编辑数据看板。先结合我选择的数据源规划指标和筛选条件，所有数值来自实际查询。', { name })}`;
}

/** Resolve gallery links without executing a request before the user selects data. */
export function dashboardTemplateEntry(query: Record<string, string | string[] | undefined>) {
  const name = query.skill;
  if (
    query.creation_mode !== 'dashboard' ||
    typeof name !== 'string' ||
    !Object.prototype.hasOwnProperty.call(ADAPTED_SKILLS, name)
  ) {
    return null;
  }
  const design = ADAPTED_SKILLS[name];
  return {
    name,
    title: design.title,
    prompt:
      typeof query.skill_prompt === 'string' && query.skill_prompt.trim()
        ? query.skill_prompt
        : dashboardTemplatePrompt(name),
  };
}
