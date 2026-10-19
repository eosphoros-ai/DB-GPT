import type { DashboardWidget } from '@/types/dashboard';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DashboardCohortMatrix from './DashboardCohortMatrix';

const widget = {
  encoding: { row: 'cohort', column: 'age', value: 'retained', target: 'cohort_size', color: 'observed' },
  presentation: { unit: '月' },
} as DashboardWidget;
describe('source-backed cohort display', () => {
  it('shows both a percentage and people, distinguishing observed zero from a future period', () => {
    render(
      <DashboardCohortMatrix
        widget={widget}
        data={[
          { cohort: '2026-01-01', age: 0, retained: 2, cohort_size: 2, observed: 1 },
          { cohort: '2026-01-01', age: 1, retained: 1, cohort_size: 2, observed: 1 },
          { cohort: '2026-01-01', age: 2, retained: 0, cohort_size: 2, observed: 1 },
          { cohort: '2026-01-01', age: 3, retained: 0, cohort_size: 2, observed: 0 },
        ]}
      />,
    );
    const table = screen.getByRole('table');
    expect(within(table).getByText('50.0%')).toBeTruthy();
    expect(within(table).getByText('1 人')).toBeTruthy();
    expect(within(table).getByText('0.0%')).toBeTruthy();
    expect(within(table).getByText('未到期')).toBeTruthy();
  });
  it('does not manufacture a percentage for an invalid denominator', () => {
    render(
      <DashboardCohortMatrix
        widget={widget}
        data={[{ cohort: '2026-01-01', age: 0, retained: 2, cohort_size: 0, observed: 1 }]}
      />,
    );
    expect(screen.getByText('无数据')).toBeTruthy();
    expect(screen.queryByText('100.0%')).toBeNull();
  });
});
