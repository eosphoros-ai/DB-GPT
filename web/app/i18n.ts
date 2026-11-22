import en from '@/locales/en';
import dashboardEn from '@/locales/en/dashboard';
import zh from '@/locales/zh';
import dashboardZh from '@/locales/zh/dashboard';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

export type I18nKeys = keyof typeof en;
interface Resources {
  translation: Record<I18nKeys, string>;
  dashboard: Record<string, string>;
}

i18n.use(initReactI18next).init({
  resources: {
    en: {
      translation: en,
      dashboard: dashboardEn,
    },
    zh: {
      translation: zh,
      dashboard: dashboardZh,
    },
  },
  lng: 'en',
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;

declare module 'i18next' {
  interface CustomTypeOptions {
    resources: Resources;
  }
}
