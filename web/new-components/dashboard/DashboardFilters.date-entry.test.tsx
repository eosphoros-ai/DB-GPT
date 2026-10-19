import type { DashboardFilter } from '@/types/dashboard';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import DashboardFilters from './DashboardFilters';

it('retains an unconfirmed date while the parent rerenders with unchanged values', async () => {
  const filters: DashboardFilter[] = [
    { id: 'dates', type: 'date_range', label: 'Dates', field: 'date', default: null, options: [] },
  ];
  const values = { dates: ['2026-10-12', '2026-10-18'] };
  const onChange = vi.fn();
  const view = render(<DashboardFilters filters={filters} values={values} onChange={onChange} />);
  const start = screen.getAllByRole('textbox')[0] as HTMLInputElement;
  fireEvent.focus(start);
  fireEvent.change(start, { target: { value: '2026-09-01' } });
  expect(start.value).toBe('2026-09-01');
  view.rerender(<DashboardFilters filters={filters} values={values} onChange={onChange} />);
  await waitFor(() => expect(start.value).toBe('2026-09-01'));
});
