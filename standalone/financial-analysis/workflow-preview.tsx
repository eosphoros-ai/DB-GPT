/** Browser acceptance harness. Uses actual report data and production components. */
import React from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zh from '../../web/locales/zh';
import FinancialAnalysisPage from '../../web/new-components/financial-analysis/FinancialAnalysisPage';
import type { ReportData } from '../../web/new-components/financial-analysis/types';
import { ChatContext } from './adapters/chat-context';

void i18n.use(initReactI18next).init({ lng: 'zh', resources: { zh: { translation: zh } }, initImmediate: false });
const data: ReportData = JSON.parse(document.getElementById('financial-report-data')!.textContent!);
const params = new URLSearchParams(location.search);
const status = params.get('state');
if (status === 'partial' && data.workflow) {
  data.workflow.status = 'published';
  if (data.analysis) data.analysis.status = 'partial';
  const topic = data.workflow.topics[0];
  Object.assign(topic, { status: 'failed', errorCode: 'FINDING_VALIDATION_FAILED', failures: 3,
    saveAttempts: 3, note: '本专题结论校验失败', issues: [{ finding_index: 0, field: 'summary', code: 'Reference not declared' }] });
  const step = data.steps.find(step => step.id === `topic-${topic.id}`);
  if (step) { step.status = 'failed'; step.detail = topic.note; }
  data.agent.summary = '部分分析：当前专题修订失败，保留已校验发现，其余专题已完成。';
}
if (status === 'running' && data.workflow) {
  data.workflow.status = 'draft';
  data.workflow.review = null;
  if (data.analysis) data.analysis.status = 'running';
  data.agent.summary = '财务数据已提取，正在逐专题分析。';
  data.workflow.topics.forEach((topic, index) => {
    topic.status = index === 0 ? 'running' : 'pending';
    topic.note = index === 0 ? '正在基于当前专题数据分析' : '尚未分析';
    topic.findingIds = [];
    topic.issues = [];
    topic.review = undefined;
    topic.failures = 0;
    topic.saveAttempts = 0;
    const step = data.steps.find(step => step.id === `topic-${topic.id}`);
    if (step) { step.status = index === 0 ? 'running' : 'pending'; step.detail = topic.note; }
  });
  data.steps.filter(step => ['review', 'publish'].includes(step.id)).forEach(step => { step.status = 'pending'; });
  data.findings = [];
  Object.values(data.sections).forEach(section => { section.findingIds = []; });
}
createRoot(document.getElementById('root')!).render(
  <ChatContext.Provider value={{ mode: 'light' }}>
    <ConfigProvider theme={{ token: { colorPrimary: '#0C75FC', fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif' } }}>
      <FinancialAnalysisPage data={data} embedded={params.has('embedded')} busy={status === 'running'}
        onTopicRetry={id => { document.documentElement.dataset.retryTopic = id; }} />
    </ConfigProvider>
  </ChatContext.Provider>,
);
