import i18n from '@/app/i18n';

type TFunc = (key: string, options?: Record<string, unknown>) => string;

/** Exact backend / legacy UI labels → i18n keys */
const EXACT_LABEL_KEYS: Record<string, string> = {
  思考中: 'thinking',
  正在思考中: 'thinking',
  Thinking: 'Thinking',
  'Thought/Action/Observation': 'react_step_detail',
  'Thought / Action / Observation': 'react_step_detail',
  'Мысль / действие / результат': 'react_step_detail',
  正在查询数据库信息: 'agent_status_sql_query',
  正在生成分析代码: 'agent_status_code',
  '正在生成并渲染 HTML 报告': 'agent_status_html',
  正在更新任务计划: 'agent_status_todo',
  正在执行分析脚本: 'agent_status_script',
  加载技能: 'section_skill_loading',
  看来出现了错误: 'agent_phrase_error_occurred',
  '看来出现了错误。': 'agent_phrase_error_occurred',
  返回最终结果: 'agent_phase_final_result',
};

/** Replace frequent Chinese fragments inside streamed thoughts (RU/EN UI only). */
const PHRASE_REPLACEMENTS: Array<{ pattern: RegExp; key: string }> = [
  { pattern: /看来出现了错误[。.]?/g, key: 'agent_phrase_error_occurred' },
  { pattern: /现在需要/g, key: 'agent_phrase_now_need' },
  { pattern: /接下来/g, key: 'agent_phrase_next' },
  { pattern: /让我尝试/g, key: 'agent_phrase_let_me_try' },
  { pattern: /让我/g, key: 'agent_phrase_let_me' },
  { pattern: /我需要/g, key: 'agent_phrase_i_need' },
  { pattern: /好的[，,]/g, key: 'agent_phrase_ok' },
];

const shouldLocalize = (): boolean => {
  const lang = (i18n.language || 'ru').toLowerCase();
  return lang.startsWith('ru') || lang.startsWith('en');
};

/**
 * Map agent step titles, phases, and short status lines to the active UI locale.
 * Leaves unknown text unchanged (e.g. user/Russian model output).
 */
export function localizeAgentText(
  raw: string | undefined | null,
  t?: TFunc,
): string {
  if (!raw) return '';
  const s = String(raw).trim();
  if (!s || !shouldLocalize()) return s;

  const tr: TFunc = t ?? ((key, opts) => i18n.t(key, opts));

  const exactKey = EXACT_LABEL_KEYS[s];
  if (exactKey) return tr(exactKey);

  let out = s;
  for (const { pattern, key } of PHRASE_REPLACEMENTS) {
    out = out.replace(pattern, () => tr(key));
  }
  return out;
}
