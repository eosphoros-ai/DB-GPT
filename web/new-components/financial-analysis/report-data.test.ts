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

function needsRevision(): ReportData {
  const data = singleReport();
  data.workflow = {
    version: 1,
    status: 'draft',
    publishedAt: null,
    review: null,
    history: [],
    topics: [
      {
        id: 'cashflow',
        title: '现金流',
        section: 'cashflow',
        status: 'needs_revision',
        attempts: 1,
        failures: 1,
        findingIds: [],
        note: '',
        history: [],
      },
    ],
  };
  data.analysis = { status: 'partial', modelName: 'synthetic', startedAt: '', rejectedCount: 1 };
  return data;
}

it('shows a retained revision draft as paused until work resumes', () => {
  const data = needsRevision();
  expect(reportRunState(data)).toEqual({
    label: financialText('financial.awaiting_revision_data_retained'),
    working: false,
    complete: false,
  });
  data.workflow!.topics[0].status = 'running';
  expect(reportRunState(data).working).toBe(true);
  data.workflow!.status = 'published';
  expect(reportRunState(data).complete).toBe(true);
  expect(reportRunState(data).working).toBe(false);
});

it.each(['analysis', 'extraction', 'parallel'] as const)(
  'keeps active %s work visible while a topic needs repair',
  mode => {
    const data = needsRevision();
    if (mode === 'analysis') data.analysis!.status = 'running';
    if (mode === 'extraction') data.report.run.status = 'running';
    if (mode === 'parallel') data.workflow!.parallelBatch = { status: 'running' };
    expect(reportRunState(data).working).toBe(true);
  },
);
