/** Supported web UI languages (i18next lng codes). */
export const SUPPORTED_LANGUAGES = ['en', 'zh', 'ru'] as const;

export type AppLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export function isAppLanguage(value: string): value is AppLanguage {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

/** Cycle en → zh → ru → en for the language toggle control. */
export function nextLanguage(current: string): AppLanguage {
  const index = SUPPORTED_LANGUAGES.indexOf(isAppLanguage(current) ? current : 'en');
  const nextIndex = (index + 1) % SUPPORTED_LANGUAGES.length;
  return SUPPORTED_LANGUAGES[nextIndex];
}
