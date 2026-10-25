import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReportDataProvider } from '../ReportDataContext';
import ReportVersions from '../ReportVersions';
import { isFinancialReportReference } from '../agent-artifact';
import { recoverFinancialHistory } from '../recover-history';
import { parseFinancialCitation, resolveFinancialCitation } from '../report-citations';
import { financialReportTitle, reportRunState, resolveEvidence, supportedFinancialProtocol } from '../report-data';
import ComparisonHeader from './ComparisonHeader';
import ComparisonMatrix from './ComparisonMatrix';
import ComparisonSections from './ComparisonSections';
import { syntheticComparison } from './synthetic-fixture';

describe('financial comparison protocol and evidence', () => {
  it('keeps protocol discrimination and history v2 independent', () => {
    const data = syntheticComparison();
    expect(supportedFinancialProtocol(data)).toBe(true);
    expect(supportedFinancialProtocol({ schemaVersion: 3, mode: 'comparison' })).toBe(false);
    const saved = JSON.parse(recoverFinancialHistory(data, 'scope').context);
    expect(saved.protocol_version).toBe(2);
    expect(saved.financial_report.mode).toBe('comparison');
    expect(saved.financial_report.title).toBe(financialReportTitle(data));
    expect(isFinancialReportReference(saved.financial_report)).toBe(true);
  });
  it('resolves both documents from the saved difference and pins revisions', () => {
    const data = syntheticComparison();
    const evidence = resolveEvidence(data, { calculationId: 'calc-difference' });
    expect(evidence.documents.map(document => document.id).sort()).toEqual(['doc-a', 'doc-b']);
    const citation = parseFinancialCitation(
      `#financial-report/${data.report.run.id}/calculation/calc-difference?revision=${data.revision}`,
    )!;
    expect(resolveFinancialCitation(data, citation)).toEqual({ calculationId: 'calc-difference' });
    expect(resolveFinancialCitation({ ...data, revision: 'another' }, citation)).toBeNull();
  });
  it('retains partial publication wording', () => {
    const data = syntheticComparison();
    expect(reportRunState(data).complete).toBe(false);
    data.analysis = { status: 'partial', modelName: 'synthetic', startedAt: '', rejectedCount: 0 };
    expect(reportRunState(data).label).toBe('分析中');
    data.analysis.completedAt = '2026-10-24';
    data.lifecycle.publicationStatus = 'published';
    expect(reportRunState(data).label).toBe('报告已生成');
  });
});

describe('comparison workspace', () => {
  it('explains a saved timeout without claiming the source data is missing', () => {
    const data = syntheticComparison();
    data.workflow = {
      version: 1,
      status: 'published',
      publishedAt: '2026-10-25',
      review: null,
      history: [],
      topics: [
        {
          id: 'cashflow',
          title: '现金流',
          section: 'cashflow',
          status: 'failed',
          attempts: 1,
          failures: 2,
          findingIds: [],
          history: [],
          errorCode: 'MODEL_TIMEOUT',
          note: '专题模型生成超时，可单独重试。',
        },
      ],
    };
    render(<ComparisonSections data={data} section='cashflow' onOpenEvidence={vi.fn()} />);
    expect(screen.getByText(/本项分析在限定时间内未完成/)).toBeTruthy();
    expect(screen.queryByText(/分析尚未形成或依据不足/)).toBeNull();
    expect(screen.queryByText(/正在形成本章节/)).toBeNull();
  });
  it('selects an exact immutable historical revision without changing its content', async () => {
    const select = vi.fn();
    const list = vi.fn().mockResolvedValue([
      {
        revision: 'saved-old',
        createdAt: '2026-10-24T10:00:00Z',
        publicationStatus: 'published',
        sha256: 'hash',
      },
    ]);
    render(<ReportVersions revision='current' access={{ list, select }} />);
    await waitFor(() => expect(screen.getByText(/报告已生成 ·/)).toBeTruthy());
    fireEvent.change(screen.getByLabelText('报告版本'), { target: { value: 'saved-old' } });
    expect(select).toHaveBeenCalledWith('saved-old');
  });
  it('shows missing/conflict/incomparable separately and opens source inputs', () => {
    const data = syntheticComparison();
    data.comparison.cells[0].comparability = { status: 'incomparable', rules: [], reasons: ['incompatible_basis'] };
    data.comparison.cells[1].dataStatus = 'conflict';
    data.comparison.cells[1].factId = null;
    data.comparison.cells[1].selectionReason = 'unexplained_conflicting_values';
    const open = vi.fn();
    render(<ComparisonMatrix data={data} codes={['revenue']} onOpenEvidence={open} />);
    expect(screen.getByText(/不可比：/)).toBeTruthy();
    expect(screen.getByText('冲突 · 待核对')).toBeTruthy();
    fireEvent.click(screen.getByText('较基准：50.00 元'));
    expect(open).toHaveBeenCalledWith({ calculationId: 'calc-difference' });
  });
  it('baseline changes request a new server version and leave saved values intact', () => {
    const data = syntheticComparison();
    const configure = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportDataProvider data={data}>
        <ComparisonHeader data={data} access={{ configure, resume: vi.fn() }} />
      </ReportDataProvider>,
    );
    fireEvent.change(screen.getByLabelText('比较基准'), { target: { value: 'b' } });
    expect(configure).toHaveBeenCalledWith({ kind: 'peer', baseline_file_id: 'b' }, data.revision);
    expect(data.calculations[0].result).toBe('50');
  });
});
