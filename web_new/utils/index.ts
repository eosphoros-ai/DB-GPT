import { format } from 'sql-formatter';

/** Theme */
export const STORAGE_THEME_KEY = '__db_gpt_theme_key';
/** Language */
export const STORAGE_LANG_KEY = '__db_gpt_lng_key';
/** Init Message */
export const STORAGE_INIT_MESSAGE_KET = '__db_gpt_im_key';
/** Flow nodes */
export const FLOW_NODES_KEY = '__db_gpt_static_flow_nodes_key';

export function formatSql(sql: string, lang?: string) {
  if (!sql) return '';
  try {
    return format(sql, { language: lang });
  } catch (e) {
    return sql;
  }
}

export * from './storage';
export * from './constants';
