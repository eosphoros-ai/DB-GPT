import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import FinancialReportArtifact from './FinancialReportArtifact';
import { syntheticComparison } from './comparison/synthetic-fixture';

const { getReport } = vi.hoisted(() => ({ getReport: vi.fn() }));
vi.mock('./api', () => ({ getReport }));
vi.mock('./FinancialReportView', () => ({
  default: ({ revisionAccess }: any) => (
    <select
      aria-label='test version'
      value={revisionAccess.selectedRevision || ''}
      onChange={event => revisionAccess.select(event.target.value || undefined)}
    >
      <option value=''>current</option>
      <option value='cited'>cited</option>
      <option value='other'>other</option>
      <option value='new-citation'>new-citation</option>
    </select>
  ),
}));

it('lets a later version selection override a citation until a new citation is clicked', async () => {
  getReport.mockResolvedValue(syntheticComparison());
  const reference = {
    kind: 'financial-report' as const,
    sessionId: 'scope',
    runId: syntheticComparison().report.run.id,
    revision: 'cited',
    published: true,
    title: 'synthetic',
  };
  const target = { runId: reference.runId, kind: 'fact' as const, refId: 'fact', revision: 'cited', requestId: 1 };
  const view = render(<FinancialReportArtifact reference={reference} citationTarget={target} />);
  fireEvent.change(await screen.findByLabelText('test version'), { target: { value: 'other' } });
  await waitFor(() => expect(getReport).toHaveBeenLastCalledWith('scope', reference.runId, expect.anything(), 'other'));
  fireEvent.change(await screen.findByLabelText('test version'), { target: { value: '' } });
  await waitFor(() =>
    expect(getReport).toHaveBeenLastCalledWith('scope', reference.runId, expect.anything(), undefined),
  );
  view.rerender(
    <FinancialReportArtifact
      reference={reference}
      citationTarget={{ ...target, revision: 'new-citation', requestId: 2 }}
    />,
  );
  await waitFor(() =>
    expect(getReport).toHaveBeenLastCalledWith('scope', reference.runId, expect.anything(), 'new-citation'),
  );
});
