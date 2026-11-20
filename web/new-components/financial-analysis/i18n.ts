import zh from '@/locales/zh/financial';
import i18next from 'i18next';
import { useSyncExternalStore } from 'react';

type FinancialKey = keyof typeof zh;
type Parameters = Record<string, string | number | undefined>;

const stageKeys: Record<string, FinancialKey> = {
  'financial-read': 'financial.stage_read',
  'financial-analyze': 'financial.stage_analyze',
  'financial-review': 'financial.stage_review',
  'financial-publish': 'financial.stage_publish',
};

export function financialStageTitle(task: { id?: string; content: string }) {
  const key = task.id && stageKeys[task.id];
  return key ? financialText(key) : task.content;
}

export function financialText(key: FinancialKey, parameters: Parameters = {}): string {
  const fallback = zh[key];
  if (i18next.isInitialized) {
    return i18next.t(key, { ...parameters, defaultValue: fallback, keySeparator: false });
  }
  // Standalone component tests can render before the application's i18n bootstrap.
  return fallback.replace(/\{\{(\w+)\}\}/g, (_, name: string) => String(parameters[name] ?? ''));
}

function subscribe(onChange: () => void) {
  i18next.on('languageChanged', onChange);
  i18next.on('initialized', onChange);
  return () => {
    i18next.off('languageChanged', onChange);
    i18next.off('initialized', onChange);
  };
}

export function useFinancialLocale() {
  return useSyncExternalStore(
    subscribe,
    () => i18next.language || 'zh',
    () => 'zh',
  );
}
