import React from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zh from '../../web/locales/zh';
import FinancialReportView from '../../web/new-components/financial-analysis/FinancialReportView';
import { financialReportTitle, supportedFinancialProtocol } from '../../web/new-components/financial-analysis/report-data';
import type { FinancialReportData } from '../../web/new-components/financial-analysis/types';
import { ChatContext } from './adapters/chat-context';

void i18n.use(initReactI18next).init({ lng: 'zh', fallbackLng: 'zh', resources: { zh: { translation: zh } }, interpolation: { escapeValue: false }, initImmediate: false });
const data: FinancialReportData = JSON.parse(document.getElementById('financial-report-data')!.textContent!);
if (!supportedFinancialProtocol(data)) throw new Error('Unsupported report snapshot');
document.title = financialReportTitle(data);
const questionAccess = { ask: async () => { throw new Error('离线快照不能在线追问，请回到应用打开此报告。'); } };
createRoot(document.getElementById('root')!).render(
  <ChatContext.Provider value={{ mode: 'light' }}>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#0C75FC', borderRadius: 4, fontFamily: 'Segoe UI, Microsoft YaHei, system-ui, sans-serif' } }}>
      <FinancialReportView data={data} questionAccess={questionAccess} />
    </ConfigProvider>
  </ChatContext.Provider>,
);
