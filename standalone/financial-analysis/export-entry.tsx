import React from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zh from '../../web/locales/zh';
import en from '../../web/locales/en';
import { financialText } from '../../web/new-components/financial-analysis/i18n';
import FinancialReportView from '../../web/new-components/financial-analysis/FinancialReportView';
import { financialReportTitle, supportedFinancialProtocol } from '../../web/new-components/financial-analysis/report-data';
import type { FinancialReportData } from '../../web/new-components/financial-analysis/types';
import { ChatContext } from './adapters/chat-context';

const language = document.documentElement.lang.toLowerCase().startsWith('en') ? 'en' : 'zh';
document.documentElement.lang = language === 'en' ? 'en' : 'zh-CN';
void i18n.use(initReactI18next).init({ lng: language, fallbackLng: 'zh', resources: { zh: { translation: zh }, en: { translation: en } }, interpolation: { escapeValue: false }, initImmediate: false });
const data: FinancialReportData = JSON.parse(document.getElementById('financial-report-data')!.textContent!);
if (!supportedFinancialProtocol(data)) throw new Error('Unsupported report snapshot');
document.title = financialReportTitle(data);
const questionAccess = { ask: async () => { throw new Error(financialText('financial.offline_question_unavailable')); } };
createRoot(document.getElementById('root')!).render(
  <ChatContext.Provider value={{ mode: 'light' }}>
    <ConfigProvider locale={language === 'en' ? enUS : zhCN} theme={{ token: { colorPrimary: '#0C75FC', borderRadius: 4, fontFamily: 'Segoe UI, Microsoft YaHei, system-ui, sans-serif' } }}>
      <FinancialReportView data={data} questionAccess={questionAccess} />
    </ConfigProvider>
  </ChatContext.Provider>,
);
