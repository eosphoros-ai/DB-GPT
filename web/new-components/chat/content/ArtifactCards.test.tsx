import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ArtifactCards, { splitQueryArtifacts, type StreamArtifact } from './ArtifactCards';
import QueryArtifactBlock from './QueryArtifactBlock';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

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
