import en from '@/locales/en/financial';
import zh from '@/locales/zh/financial';
import { act, render, screen } from '@testing-library/react';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import { expect, it } from 'vitest';
import FinancialProgressPanel from '../chat/content/FinancialProgressPanel';
import { supportLabels } from './FindingCard';
import ReportVersions from './ReportVersions';
import ComparisonHeader from './comparison/ComparisonHeader';
import { comparisonReason } from './comparison/comparison-data';
import { syntheticComparison } from './comparison/synthetic-fixture';
import { financialText } from './i18n';

it('keeps financial locale keys and interpolation parameters identical', () => {
  expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort());
  const parameters = (value: string) => [...value.matchAll(/\{\{(\w+)\}\}/g)].map(match => match[1]).sort();
  for (const key of Object.keys(zh) as Array<keyof typeof zh>) {
    expect(parameters(en[key]), key).toEqual(parameters(zh[key]));
    expect(en[key], key).not.toMatch(/[\u3400-\u9fff]/);
    expect(en[key].trim(), key).not.toBe('');
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
  await act(async () => {
    await i18next.changeLanguage('zh');
  });
  expect(screen.getByRole('heading', { name: zh['financial.stage_read'] })).toBeTruthy();
  expect(supportLabels.supported).toBe(zh['financial.supported_by_evidence']);
});
