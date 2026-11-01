import i18next from 'i18next';
import { ChatZh } from '../../locales/zh/chat';

/** Report models share the active translator without initializing the app. */
export function reportText(key: keyof typeof ChatZh, values: Record<string, unknown> = {}): string {
  const fallback = ChatZh[key].replace(/\{\{\s*(\w+)\s*\}\}/g, (token, name: string) =>
    values[name] === undefined ? token : String(values[name]),
  );
  if (!i18next.isInitialized) return fallback;
  const translated = i18next.t(key, { ...values, defaultValue: fallback });
  return typeof translated === 'string' ? translated : fallback;
}
