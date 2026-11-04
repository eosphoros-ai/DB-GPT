import { describe, expect, it } from 'vitest';
import { syntheticComparison } from './comparison/synthetic-fixture';
import { financialText } from './i18n';
import { reportRunState } from './report-data';
import type { ReportData } from './types';

function singleReport(): ReportData {
  const comparison = syntheticComparison();
  return {
    ...comparison,
    schemaVersion: 1,
    mode: 'report',
    report: { ...comparison.report, companyName: 'Synthetic company', shortName: 'Synthetic', stockCode: '' },
    trends: { revenue: [], cashFlow: [], profit: [], expenses: [], financialUnit: '元', profitUnit: '元' },
    healthMetrics: [],
    statements: { unit: '元', periods: [], rows: [] },
  };
}

describe('single report run state', () => {
  it('stops showing active work when a draft analysis fails, while preserving publication', () => {
    const data = singleReport();
    data.workflow = { version: 1, status: 'draft', publishedAt: null, review: null, topics: [], history: [] };
    data.analysis = { status: 'failed', modelName: 'synthetic', startedAt: '', rejectedCount: 0 };
    expect(reportRunState(data)).toEqual({
      label: financialText('financial.data_available_analysis_incomplete'),
      working: false,
      complete: false,
    });
    data.workflow.status = 'published';
    expect(reportRunState(data)).toEqual({
      label: financialText('financial.report_generated'),
      working: false,
      complete: true,
    });
  });
});
