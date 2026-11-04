import en from '@/locales/en/financial';
import zh from '@/locales/zh/financial';
import { act, render, screen } from '@testing-library/react';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import { expect, it, vi } from 'vitest';
import FinancialProgressPanel from '../chat/content/FinancialProgressPanel';
import ExecutionProcessPanel from './ExecutionProcessPanel';
import { supportLabels } from './FindingCard';
import { ReportDataProvider } from './ReportDataContext';
import ReportVersions from './ReportVersions';
import SourcePreviewPanel from './SourcePreviewPanel';
import ComparisonHeader from './comparison/ComparisonHeader';
import { comparisonReason } from './comparison/comparison-data';
import { syntheticComparison } from './comparison/synthetic-fixture';
import { financialText } from './i18n';
import { runStatusLabels } from './report-data';

vi.mock('./PdfPagePreview', () => ({ default: () => null }));

it('keeps financial locale keys and interpolation parameters identical', () => {
  expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort());
  const parameters = (value: string) => [...value.matchAll(/\{\{(\w+)\}\}/g)].map(match => match[1]).sort();
  for (const key of Object.keys(zh) as Array<keyof typeof zh>) {
    expect(parameters(en[key]), key).toEqual(parameters(zh[key]));
    expect(en[key], key).not.toMatch(/[\u3400-\u9fff]/);
    expect(en[key].trim(), key).not.toBe('');
  }
});

it.each([
  {
    language: 'en',
    summary:
      'Extracted 12 usable values; 3 items cannot be calculated. These counts describe extracted data, not coverage of the entire report.',
    elapsed: 'Elapsed 1.23 seconds',
    confirmation: 'Confirm the company and reporting year for synthetic-a.pdf.',
    page: '2024 · Metric reference: PDF physical page 2',
    header: 'Header (physical page 3): Revenue',
    unit: 'Unit statement (physical page 4): CNY',
  },
  {
    language: 'zh',
    summary: '已提取 12 个可用值，3 项不可计算。这表示当前提取范围，不代表整份年报覆盖率。',
    elapsed: '耗时 1.23 秒',
    confirmation: '请确认 synthetic-a.pdf 的公司和报告年度。',
    page: '2024 · 指标引用：PDF 物理第 2 页',
    header: '表头（物理第 3 页）：Revenue',
    unit: '单位声明（物理第 4 页）：CNY',
  },
])('renders complete parameterized report labels in $language', async expected => {
  await i18next.use(initReactI18next).init({
    lng: expected.language,
    resources: { zh: { translation: zh }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  const data = syntheticComparison();
  data.comparison.clarifications = [{ fileId: 'a' }];
  data.steps = [
    {
      id: 'quality',
      order: 1,
      type: 'analysis',
      title: 'Quality',
      detail: '',
      status: 'completed',
      capability: 'existing',
      elapsedMs: 1230,
    },
  ];
  data.workflow = {
    version: 1,
    status: 'draft',
    publishedAt: null,
    review: null,
    topics: [],
    history: [],
    dataQuality: {
      availableFacts: 12,
      missingFacts: [],
      unavailableCalculations: ['a', 'b', 'c'].map(id => ({ id, name: id, reason: 'missing_input' })),
    },
  };
  render(
    <ReportDataProvider data={data}>
      <ExecutionProcessPanel onStepSelect={() => {}} />
      <ComparisonHeader data={data} />
      <SourcePreviewPanel
        document={data.documents[0]}
        evidence={{ ...data.evidence[0], headerPage: 3, headerSnippet: 'Revenue', unitPage: 4, unitText: 'CNY' }}
        onBack={() => {}}
        sourceAccess={{ loadPage: async () => new Blob(), download: async () => {} }}
      />
    </ReportDataProvider>,
  );
  for (const text of [
    expected.summary,
    expected.elapsed,
    expected.confirmation,
    expected.page,
    expected.header,
    expected.unit,
  ]) {
    expect(screen.getByText(text)).toBeTruthy();
  }
});

it('updates progress, version controls and comparison labels when language changes after mounting', async () => {
  await i18next.use(initReactI18next).init({
    lng: 'zh',
    resources: { zh: { translation: zh }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  render(
    <>
      <FinancialProgressPanel
        isRunning
        onOpenReport={() => {}}
        tasks={[
          {
            id: 'financial-read',
            kind: 'financial-stage',
            content: zh['financial.stage_read'],
            status: 'in_progress',
            priority: 'high',
          },
        ]}
      />
      <ReportVersions revision='current' access={{ list: async () => [], select: () => {} }} />
      <ComparisonHeader data={syntheticComparison()} />
    </>,
  );
  expect(screen.getByRole('heading', { name: zh['financial.stage_read'] })).toBeTruthy();
  await act(async () => {
    await i18next.changeLanguage('en');
  });
  expect(screen.getByRole('heading', { name: 'Read financial report' })).toBeTruthy();
  expect(screen.getByLabelText('Report version')).toBeTruthy();
  expect(screen.getByLabelText('Comparison baseline')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'View existing analysis' })).toBeTruthy();
  expect(supportLabels.supported).toBe('Supported by evidence');
  expect(comparisonReason('missing_input')).toBe('No usable data');
  expect(financialText('financial.request_failed_please_retry')).toBe('Request failed. Please retry.');
  expect(runStatusLabels.pending).toBe('Pending');
  expect(runStatusLabels.running).toBe('Running');
  expect(runStatusLabels.failed).toBe('Failed');
  await act(async () => {
    await i18next.changeLanguage('zh');
  });
  expect(screen.getByRole('heading', { name: zh['financial.stage_read'] })).toBeTruthy();
  expect(supportLabels.supported).toBe(zh['financial.supported_by_evidence']);
  expect(runStatusLabels.pending).toBe(zh['financial.run_pending']);
  expect(runStatusLabels.failed).toBe(zh['financial.run_failed']);
});
