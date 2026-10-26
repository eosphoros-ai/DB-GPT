import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
import ArtifactCards, { splitQueryArtifacts, type StreamArtifact } from './ArtifactCards';

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
