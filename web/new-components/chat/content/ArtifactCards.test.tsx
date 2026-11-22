import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { message } from 'antd';
import { describe, expect, it, vi } from 'vitest';
import { createExport, downloadExport, getReport } from '../../financial-analysis/api';
import { financialText } from '../../financial-analysis/i18n';
import { financialArtifact } from '../../financial-analysis/report-delivery';
import ArtifactCards, { splitQueryArtifacts, type StreamArtifact } from './ArtifactCards';
import QueryArtifactBlock from './QueryArtifactBlock';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../financial-analysis/api', () => ({
  getReport: vi.fn(),
  createExport: vi.fn(),
  downloadExport: vi.fn(),
}));
vi.mock('../../financial-analysis/FinancialReportView', () => ({ default: () => null }));

describe('ArtifactCards report delivery', () => {
  const reference = {
    kind: 'financial-report' as const,
    sessionId: 'financial-session',
    runId: '11111111-1111-4111-8111-111111111111',
    revision: 'published-revision',
    title: '财报分析',
    published: true,
  };

  it('omits unknown file size while preserving financial report preview', () => {
    const artifact = financialArtifact(reference, 'message');
    const onPreview = vi.fn();
    render(<ArtifactCards artifacts={[artifact]} onPreview={onPreview} />);

    expect(screen.getByText('HTML')).not.toBeNull();
    expect(screen.queryByText(/undefined|NaN|\b0 B\b/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'artifact_preview' }));
    expect(onPreview).toHaveBeenCalledWith(artifact);
  });

  it.each([
    { size: undefined, content: '<p>财报</p>', meta: 'HTML · 13 B' },
    { size: 2048, content: '<p>财报</p>', meta: 'HTML · 2.0 KB' },
    { size: 0, content: '', meta: 'HTML · 0 B' },
  ])('shows the actual byte size for inline HTML ($meta)', ({ size, content, meta }) => {
    render(<ArtifactCards artifacts={[{ id: 'html', type: 'html', name: 'report.html', size, content }]} />);
    expect(screen.getByText(meta)).not.toBeNull();
  });

  it('downloads the exported HTML for the referenced report revision', async () => {
    const report = { revision: reference.revision } as Awaited<ReturnType<typeof getReport>>;
    const file = {
      id: 'html-export',
      revision: reference.revision,
      format: 'html',
    } as Awaited<ReturnType<typeof createExport>>;
    vi.mocked(getReport).mockResolvedValueOnce(report);
    vi.mocked(createExport).mockResolvedValueOnce(file);
    vi.mocked(downloadExport).mockResolvedValueOnce(undefined);
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<ArtifactCards artifacts={[financialArtifact(reference, 'message')]} />);

    fireEvent.click(screen.getByRole('button', { name: 'artifact_download' }));

    await waitFor(() => expect(downloadExport).toHaveBeenCalledWith(reference.sessionId, reference.runId, file));
    expect(getReport).toHaveBeenCalledWith(reference.sessionId, reference.runId, undefined, reference.revision);
    expect(createExport).toHaveBeenCalledWith(reference.sessionId, reference.runId, reference.revision, 'html');
    expect(click).not.toHaveBeenCalled();
  });

  it('reports export failures without downloading the reference as a file', async () => {
    vi.mocked(getReport).mockResolvedValueOnce({ revision: reference.revision } as Awaited<
      ReturnType<typeof getReport>
    >);
    vi.mocked(createExport).mockRejectedValueOnce(new Error('export failed'));
    const error = vi.spyOn(message, 'error').mockImplementation(() => ({}) as ReturnType<typeof message.error>);
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<ArtifactCards artifacts={[financialArtifact(reference, 'message')]} />);

    fireEvent.click(screen.getByRole('button', { name: 'artifact_download' }));

    await waitFor(() =>
      expect(error).toHaveBeenCalledWith(
        financialText('financial.report_download_failed_retry_from_the_report_s_files_tab'),
      ),
    );
    expect(downloadExport).not.toHaveBeenCalled();
    expect(click).not.toHaveBeenCalled();
  });
});

const query = (id: string, rows = 3): StreamArtifact =>
  ({
    id,
    type: 'query',
    name: `查询结果 · ${rows} 行`,
    tier: 'final',
    content: {
      sql: `SELECT ${id}`,
      columns: ['a', 'b'],
      rows: Array.from({ length: rows }, (_, i) => [i, `r${i}`]),
      row_count: rows,
      truncated: false,
      db_name: 'Walmart_Sales',
    },
  }) as unknown as StreamArtifact;

const FIVE = () => [query('q1'), query('q2'), query('q3'), query('q4'), query('q5')];

/** SQL <pre> blocks rendered outside any <details> = expanded cards. */
const expandedCards = (container: HTMLElement) =>
  [...container.querySelectorAll('pre')].filter(p => !p.closest('details'));

describe('splitQueryArtifacts', () => {
  it('consolidates final formats and process files into one right-panel entry', () => {
    const onPreview = vi.fn();
    const items: StreamArtifact[] = [
      { id: 'er', type: 'html', name: 'Report.html', content: '<body data-dbgpt-er="1"><svg /></body>' },
      { id: 'drawio', type: 'file', name: 'er-diagram.drawio', content: { content: 'xml' } },
      { id: 'script', type: 'code', name: 'code_131.py', content: 'print(1)', tier: 'process' },
    ];
    const { container } = render(<ArtifactCards consolidate artifacts={items} onPreview={onPreview} />);
    expect(container.querySelector('iframe')).toBeNull();
    expect(container.querySelectorAll('button')).toHaveLength(1);
    expect(container.textContent).not.toContain('code_131.py');
    fireEvent.click(container.querySelector('button')!);
    expect(onPreview.mock.calls[0][0]).toMatchObject({
      type: 'artifact_bundle',
      content: { primaryId: 'er', items },
    });
  });
  it('renders ER HTML inline with zoom scripts and downloads available', () => {
    const content = '<html><body data-dbgpt-er="1"><svg></svg></body></html>';
    const { container } = render(<ArtifactCards artifacts={[{ id: 'er-1', name: 'ER 图', type: 'html', content }]} />);
    const iframe = container.querySelector('iframe');
    expect(iframe?.getAttribute('srcdoc')).toBe(content);
    expect(iframe?.getAttribute('sandbox')).toBe('allow-scripts allow-downloads');
  });

  it('keeps ordinary HTML reports in their existing cards', () => {
    const { container } = render(
      <ArtifactCards artifacts={[{ id: 'report-1', name: '报告', type: 'html', content: '<h1>报告</h1>' }]} />,
    );
    expect(container.querySelector('iframe')).toBeNull();
  });

  it('keeps the conversation summary compact without rendering a second ER', () => {
    const { container } = render(
      <ArtifactCards
        showInlineEr={false}
        artifacts={[
          { id: 'er-summary', name: 'ER 图.html', type: 'html', content: '<body data-dbgpt-er="1"><svg /></body>' },
        ]}
      />,
    );
    expect(container.querySelector('iframe')).toBeNull();
    expect(container.textContent).toContain('ER 图.html');
  });

  it('keeps everything expanded for zero or one query', () => {
    expect(splitQueryArtifacts([])).toEqual({ visible: [], folded: [] });
    const one = [query('q1')];
    expect(splitQueryArtifacts(one)).toEqual({ visible: one, folded: [] });
  });

  it('folds all but the latest query once there are several', () => {
    const { visible, folded } = splitQueryArtifacts(FIVE());
    expect(visible.map(a => a.id)).toEqual(['q5']);
    expect(folded.map(a => a.id)).toEqual(['q1', 'q2', 'q3', 'q4']);
  });

  it('folds every query for older rounds', () => {
    const five = FIVE();
    expect(splitQueryArtifacts(five, true)).toEqual({ visible: [], folded: five });
  });
});

describe('ArtifactCards query folding', () => {
  it('shows a single expanded card plus a collapsed per-query accordion', () => {
    const { container } = render(<ArtifactCards artifacts={FIVE()} />);
    const group = container.querySelector('details');
    expect(group).not.toBeNull();
    expect(group!.textContent).toContain('qa_intermediate_queries');
    // folded queries become compact rows (nested details), not stacked cards
    expect(group!.querySelectorAll('details')).toHaveLength(4);
    expect(expandedCards(container)).toHaveLength(1);
  });

  it('folds every card for older rounds (foldAllQueries)', () => {
    const { container } = render(<ArtifactCards artifacts={FIVE()} foldAllQueries />);
    const group = container.querySelector('details');
    expect(group).not.toBeNull();
    expect(group!.querySelectorAll('details')).toHaveLength(5);
    expect(expandedCards(container)).toHaveLength(0);
  });

  it('renders no group for a single query', () => {
    const { container } = render(<ArtifactCards artifacts={[query('only')]} />);
    expect(container.querySelectorAll('details')).toHaveLength(0);
    expect(screen.queryByText(/qa_intermediate_queries/)).toBeNull();
    expect(expandedCards(container)).toHaveLength(1);
  });
});

describe('query execution records', () => {
  const payload = {
    sql: 'SELECT 42 AS answer',
    columns: ['answer'],
    rows: [[42]],
    row_count: 1,
    db_name: 'test_db',
    execution: {
      status: 'succeeded' as const,
      started_at: '2026-10-27T06:00:00+00:00',
      duration_ms: 123,
      tool: 'sql_query',
      artifact_id: 'sql-record-1',
    },
  };

  it('shows SQL, result and actual execution metadata in one artifact', () => {
    const { container } = render(<QueryArtifactBlock payload={payload} />);
    expect(container.querySelector('pre')?.textContent).toBe(payload.sql);
    expect(screen.getByRole('columnheader', { name: 'answer' })).not.toBeNull();
    const record = screen.getByTestId('query-execution-record').textContent;
    expect(record).toContain('qa_execution_succeeded');
    expect(record).toContain('test_db');
    expect(record).toContain('123 ms');
    expect(record).toContain('sql-record-1');
    expect(record).toContain('sql_query');
  });

  it('shows an empty result as a successful execution', () => {
    render(<QueryArtifactBlock payload={{ ...payload, rows: [], row_count: 0 }} />);
    expect(screen.getByTestId('query-execution-record').textContent).toContain('qa_execution_succeeded');
    expect(screen.getByText('qa_empty')).not.toBeNull();
  });

  it('shows a failed attempt without result table or export actions', () => {
    render(
      <QueryArtifactBlock
        payload={{
          ...payload,
          rows: [],
          execution: { ...payload.execution, status: 'failed', error: 'SQL_QUERY_TIMEOUT' },
        }}
      />,
    );
    expect(screen.getByTestId('query-execution-record').textContent).toContain('qa_execution_failed');
    expect(screen.getByText('SQL_QUERY_TIMEOUT')).not.toBeNull();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByText(/qa_export/)).toBeNull();
  });

  it('does not invent execution metadata for old history payloads', () => {
    const { execution, ...legacy } = payload;
    render(<QueryArtifactBlock payload={legacy} />);
    expect(screen.queryByTestId('query-execution-record')).toBeNull();
    expect(screen.getByRole('table')).not.toBeNull();
  });
});
